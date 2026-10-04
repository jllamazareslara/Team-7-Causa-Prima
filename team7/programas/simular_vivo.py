"""Simular `jugar.py --live` SIN RED: el mismo código que juega en vivo, contra un juego de mentira, y un log de cada trato.

    python programas/simular_vivo.py                     200 ticks, semilla 1
    python programas/simular_vivo.py --ticks 500 --semilla 7
    python programas/simular_vivo.py --efectivo 300      empezar con otra caja (por defecto, la de datos/estado-actual.json)

No llama al juego ni lee la clave: `jugar.py` recibe un `JuegoSimulado` en lugar del SDK y cree que juega en vivo
(acepta, manda precios, abre conversaciones, publica en El Rastro). No toma el candado ni toca runs/: todo va a
runs/simulacion/<fecha-hora>/:

    tratos.jsonl     UNA línea por trato hecho, apuntada por el juego simulado (la verdad: qué pasó de verdad)
    resumen.json     tratos por canal, efectivo y valor de la colección al empezar y al acabar
    pantalla.txt     lo que jugar.py escribe en pantalla
    diario.jsonl, tratos.jsonl de jugar, errores.jsonl...   lo que jugar.py apunta, como en vivo

El mundo de mentira (todo supuesto, cámbialo aquí si sabemos más):
    - vendedores: los de menus.json, con el modelo de sim/vendedores.py (imitan nuestros pasos, límite secreto,
      paciencia y oferta final). Si cortan, la conversación queda en cooloff 60 ticks.
    - El Rastro: 15 equipos de mentira ponen unos 12 anuncios y peticiones vivos, a 0,5-1,6 × la base de la rareza
      (vender) o 0,3-1,0 × (pedir). Quien acepta paga la comisión (5 % + 1 por carta).
    - lo que publicamos: cada tick, un 25 % de probabilidad de que alguien se lo quede si el precio entra en lo que
      pagaría un equipo al azar.
    - nuestro your_value: el de la calculadora (agentes/valor.py) con los multiplicadores supuestos.
Con la misma semilla, la misma simulación.
"""
import argparse
import io
import json
import os
import random
import sys
import time
from collections import Counter
from contextlib import redirect_stdout

PROGRAMAS = os.path.dirname(os.path.abspath(__file__))
AQUI = os.path.dirname(PROGRAMAS)            # team7/: agentes/, sim/, datos/, runs/ y menus.json
sys.path.insert(0, PROGRAMAS)
sys.path.insert(0, AQUI)

import jugar  # noqa: E402
from sim import vendedores as SV  # noqa: E402
from agentes import cadena  # noqa: E402
from agentes import valor as V  # noqa: E402

NOSOTROS = "t07"
EQUIPOS = [f"t{n:02d}" for n in range(1, 17) if n != 7]
TICK_SEGUNDOS = 15                  # el domingo 4/10 el tick dura 15 s
COOLOFF_TICKS = 60


class JuegoSimulado:
    """Lo que jugar.py usa del SDK (bazaar_sdk.Bazaar), sin red."""

    SDK = {"clock", "me", "value", "catalog", "schedule", "dealers", "venues", "feed", "open_pack", "my_threads",
           "open_thread", "thread", "say", "close_thread", "board", "my_offers", "list_offer", "cancel", "accept"}

    def __getattribute__(self, nombre):
        if nombre in JuegoSimulado.SDK:                          # cuántas llamadas al juego hace jugar.py
            object.__getattribute__(self, "llamadas")[nombre] += 1
        return object.__getattribute__(self, nombre)

    def __init__(self, cartas, efectivo, menus, semilla, log):
        self.llamadas, self.tick = Counter(), 0
        self.rng = random.Random(semilla)
        self.tick, self.siguiente_id, self.log = 0, 1000, log
        self.efectivo, self.menus = float(efectivo), menus or {}
        self.activos = []
        for ref in cartas:
            self._dar_carta(ref)
        self.hilos = {}            # id → {"vendedor", "lado", "carta", "v": Vendedor, "status", "ofertas", "mensajes", ...}
        self.tablon = []           # ofertas vivas de El Rastro (de otros equipos y nuestras)
        self.eventos = []          # el feed público: tratos hechos
        self.refs = [f"{b}-{n:02d}" for b in V.NUESTROS_MULT for n in range(1, 13) if V.rareza(f"{b}-{n:02d}")]

    # ---------------------------------------------------------------- utilidades
    def _id(self):
        self.siguiente_id += 1
        return self.siguiente_id

    def _dar_carta(self, ref):
        self.activos.append({"id": self._id(), "kind": "card", "ref": ref})

    def _quitar_carta(self, aid=None, ref=None):
        a = next((x for x in self.activos if (aid is not None and x["id"] == aid) or (aid is None and x["ref"] == ref)), None)
        if a is None:
            raise RuntimeError(f"no tenemos la carta {aid or ref}")
        self.activos.remove(a)
        return a["ref"]

    def cuenta(self):
        return Counter(a["ref"] for a in self.activos)

    def valor_coleccion(self):
        return round(V.valor_coleccion(self.cuenta()), 1)

    def _apunta(self, canal, lado, carta, precio, con, comision=0.0, nos_vale=None):
        antes = self.efectivo
        fila = {"tick": self.tick, "canal": canal, "con": con, "lado": lado, "carta": carta, "precio": precio,
                "comision": round(comision, 2), "nos_vale": None if nos_vale is None else round(nos_vale, 1),
                "efectivo": round(antes, 1), "coleccion": self.valor_coleccion()}
        self.log.write(json.dumps(fila, ensure_ascii=False) + "\n")
        self.log.flush()
        self.eventos.append({"id": self._id(), "tick": self.tick, "type": "settlement",
                          "payload": {"items": [{"kind": "card", "ref": carta}], "price": precio}})

    # ---------------------------------------------------------------- reloj, nosotros, catálogo
    def clock(self):
        self.tick += 1
        self._mover_rastro()
        return {"tick": self.tick, "tick_seconds": TICK_SEGUNDOS, "t_hours": self.tick * TICK_SEGUNDOS / 3600,
                "paused": False, "next_tick_in": 0}

    def me(self):
        cuenta = self.cuenta()
        activos = [dict(a, your_value=round(V.valor_entregar(cuenta, [a["ref"]]) or 0, 1)) for a in self.activos]
        return {"id": NOSOTROS, "name": "Team 7", "cash": round(self.efectivo, 1), "assets": activos}

    def value(self, carta):
        return {"card": carta, "your_value": round(V.valor_recibir(self.cuenta(), [carta]), 1)}

    def catalog(self):
        return {}

    def schedule(self):
        return {"now_hours": self.tick * TICK_SEGUNDOS / 3600, "upcoming": []}

    def dealers(self):
        """Con su menú, en una forma que agentes/menus.py entiende: así jugar.py usa los menús «del juego»."""
        return {"personas": [{"id": v, "level": 1,
                              "menu": {"sells": [{"card": r, "price": x} for r, x in (m.get("vende") or {}).items()],
                                       "buys": [{"card": r, "price": x} for r, x in (m.get("compra") or {}).items()]}}
                             for v, m in self.menus.items()]}

    def venues(self):
        return {"venues": [{"id": "rastro", "fee_bps": 500, "fee_per_card": 1}] +
                          [{"id": v, "fee_bps": 0, "fee_per_card": 0} for v in ("v01", "v02", "v07")]}

    def feed(self, limit=100):
        return {"events": self.eventos[-limit:]}

    def open_pack(self, aid):
        raise RuntimeError("no hay sobres en la simulación")

    # ---------------------------------------------------------------- vendedores
    def my_threads(self, status=None):
        return {"threads": [{"id": h, "with": x["vendedor"], "status": x["status"]} for h, x in self.hilos.items()]}

    def open_thread(self, with_, topic=None, venue=None):
        menu = self.menus.get(with_) or {}
        if any(x["vendedor"] == with_ and x["status"] == "open" for x in self.hilos.values()):
            raise RuntimeError("thread_exists")
        if "buy" in (topic or {}):                         # compramos: el vendedor vende
            lado, carta = "compra", topic["buy"]["card"]
            lista, aid = menu["vende"][carta], None
        else:                                              # vendemos: el vendedor compra
            aid = topic["sell"]["assets"][0]
            carta = next(a["ref"] for a in self.activos if a["id"] == aid)
            lado, lista = "venta", menu["compra"][carta] / 0.35      # menus.json da lo que ofrece de entrada (≈ 35 % de su techo)
        perfil = with_ if with_ in SV.PERFILES else "desconocido"
        v, _ = SV.mundo(perfil, lado, lista, self.rng)
        hid = self._id()
        self.hilos[hid] = {"vendedor": with_, "lado": lado, "carta": carta, "aid": aid, "v": v, "status": "open",
                           "ofertas": [], "mensajes": []}
        self._oferta_vendedor(hid, v.precio)
        return {"id": hid}

    def _oferta_vendedor(self, hid, precio, final=False):
        h = self.hilos[hid]
        for o in h["ofertas"]:
            o["status"] = "replaced"
        precio = max(1, int(round(precio)))
        carta = {"id": self._id(), "ref": h["carta"]} if h["lado"] == "compra" else {"id": h["aid"], "ref": h["carta"]}
        if h["lado"] == "compra":
            o = {"id": self._id(), "maker": h["vendedor"], "status": "open", "final": final,
                 "give": {"cash": 0, "assets": [carta]}, "want": {"cash": precio}}
        else:
            o = {"id": self._id(), "maker": h["vendedor"], "status": "open", "final": final,
                 "give": {"cash": precio}, "want": {"cash": 0, "assets": [carta]}}
        h["ofertas"].append(o)
        h["mensajes"].append({"from": h["vendedor"], "text": f"{'Última oferta: ' if final else ''}{precio}"})

    def thread(self, tid):
        h = self.hilos[tid]
        out = {"id": tid, "status": h["status"], "standing_offers": [dict(o) for o in h["ofertas"]],
               "messages": list(h["mensajes"])}
        if h["status"] != "open":
            out["closed_reason"], out["until_tick"] = h.get("motivo", h["status"]), h.get("hasta")
        return out

    def say(self, tid, text, price=None):
        h = self.hilos[tid]
        if h["status"] != "open":
            raise RuntimeError("thread_closed")
        h["mensajes"].append({"from": NOSOTROS, "text": text})
        if price is None:
            return {}
        if h["ofertas"] and h["ofertas"][-1].get("final"):           # ya dio su oferta final: se va
            h["status"], h["motivo"] = "walked", "walked"
            return {}
        que, p = h["v"].responde(price)
        if que == "cerrado":
            h["status"], h["motivo"], h["hasta"] = "cooloff", p, self.tick + COOLOFF_TICKS
        else:
            self._oferta_vendedor(tid, p, final=que == "final")
        return {}

    def close_thread(self, tid):
        if tid in self.hilos and self.hilos[tid]["status"] == "open":
            self.hilos[tid]["status"], self.hilos[tid]["motivo"] = "closed", "closed"

    # ---------------------------------------------------------------- El Rastro
    def _base(self, ref):
        return V.BASE[V.rareza(ref)]

    def _mover_rastro(self):
        """Caducan ofertas, otros equipos ponen nuevas y alguien se queda (o no) lo que publicamos."""
        self.tablon = [o for o in self.tablon if o["expires_tick"] > self.tick]
        ajenas = [o for o in self.tablon if o["maker"] != NOSOTROS]
        while len(ajenas) < 12:
            ref = self.rng.choice(self.refs)
            if self.rng.random() < 0.6:
                o = {"give": {"cash": 0, "assets": [{"id": self._id(), "ref": ref}]},
                     "want": {"cash": max(1, round(self._base(ref) * self.rng.uniform(0.5, 1.6)))}}
            else:
                o = {"give": {"cash": max(1, round(self._base(ref) * self.rng.uniform(0.3, 1.0)))}, "want": {"cards": [ref]}}
            o.update(id=self._id(), maker=self.rng.choice(EQUIPOS), venue="rastro", status="open",
                     created_tick=self.tick, expires_tick=self.tick + self.rng.randint(10, 30))
            self.tablon.append(o)
            ajenas.append(o)
        for o in [x for x in self.tablon if x["maker"] == NOSOTROS]:
            if self.rng.random() >= 0.25:
                continue
            give, want = o["give"], o["want"]
            otro = self.rng.choice(EQUIPOS)
            if give.get("assets") and want.get("cash"):              # vendemos una carta
                ref = next(a["ref"] for a in self.activos if a["id"] == give["assets"][0]["id"])
                if want["cash"] <= self._base(ref) * self.rng.uniform(0.6, 2.0):
                    pierde = V.valor_entregar(self.cuenta(), [ref])
                    self._quitar_carta(aid=give["assets"][0]["id"])
                    self.efectivo += want["cash"]
                    self.tablon.remove(o)
                    self._apunta("rastro · nuestro anuncio", "venta", ref, want["cash"], otro, nos_vale=pierde)
            elif give.get("cash") and want.get("cards"):             # pedimos una carta con dinero
                ref = want["cards"][0]
                if give["cash"] >= self._base(ref) * self.rng.uniform(0.4, 1.0) and self.efectivo >= give["cash"]:
                    gana = V.valor_recibir(self.cuenta(), [ref])
                    self.efectivo -= give["cash"]
                    self._dar_carta(ref)
                    self.tablon.remove(o)
                    self._apunta("rastro · nuestra petición", "compra", ref, give["cash"], otro, nos_vale=gana)
            elif give.get("assets") and want.get("cards") and self.rng.random() < 0.5:   # cambio carta por carta
                dimos = [self._quitar_carta(aid=a["id"]) for a in give["assets"]]
                for ref in want["cards"]:
                    self._dar_carta(ref)
                self.tablon.remove(o)
                self._apunta("rastro · nuestro cambio", "cambio", "+".join(dimos) + " → " + "+".join(want["cards"]), 0, otro)

    def board(self, venue):
        return {"offers": [dict(o) for o in self.tablon if o.get("venue", "rastro") == venue]}

    def my_offers(self):
        return {"offers": [dict(o) for o in self.tablon if o["maker"] == NOSOTROS]}

    def list_offer(self, give, want, venue=None, expires_in_ticks=40):
        give = dict(give)
        if give.get("assets"):
            give["assets"] = [{"id": aid, "ref": next(a["ref"] for a in self.activos if a["id"] == aid)}
                              for aid in give["assets"]]
        o = {"id": self._id(), "maker": NOSOTROS, "venue": venue or "rastro", "status": "open", "give": give,
             "want": dict(want), "created_tick": self.tick, "expires_tick": self.tick + expires_in_ticks}
        self.tablon.append(o)
        return {"id": o["id"]}

    def cancel(self, oid):
        self.tablon = [o for o in self.tablon if not (o["id"] == oid and o["maker"] == NOSOTROS)]

    def accept(self, oid, assets=None):
        for hid, h in self.hilos.items():                           # una oferta de un vendedor
            o = next((x for x in h["ofertas"] if x["id"] == oid), None)
            if o is None:
                continue
            if h["status"] != "open" or o["status"] != "open":
                raise RuntimeError("offer_not_open")
            if h["lado"] == "compra":
                precio = o["want"]["cash"]
                if precio > self.efectivo:
                    raise RuntimeError("insufficient_cash")
                nos_vale = V.valor_recibir(self.cuenta(), [h["carta"]])
                self.efectivo -= precio
                self._dar_carta(h["carta"])
            else:
                precio = o["give"]["cash"]
                nos_vale = V.valor_entregar(self.cuenta(), [h["carta"]])
                self._quitar_carta(aid=h["aid"])
                self.efectivo += precio
            h["status"], o["status"] = "deal", "accepted"
            self._apunta("vendedor", h["lado"], h["carta"], precio, h["vendedor"], nos_vale=nos_vale)
            return {"ok": True}
        o = next((x for x in self.tablon if x["id"] == oid), None)   # una oferta de El Rastro
        if o is None:
            raise RuntimeError("offer_not_found")
        if o["maker"] == NOSOTROS:
            raise RuntimeError("self_trade")
        give, want = o["give"], o["want"]
        if give.get("assets"):                                       # nos venden una carta
            ref, precio = give["assets"][0]["ref"], want["cash"]
            com = V.comision_rastro(precio, 1)
            if precio + com > self.efectivo:
                raise RuntimeError("insufficient_cash")
            nos_vale = V.valor_recibir(self.cuenta(), [ref])
            self.efectivo -= precio + com
            self._dar_carta(ref)
            lado = "compra"
        else:                                                        # nos compran una carta
            ref, precio = want["cards"][0], give["cash"]
            com = V.comision_rastro(precio, 1)
            nos_vale = V.valor_entregar(self.cuenta(), [ref])
            self._quitar_carta(aid=(assets or [None])[0], ref=ref)
            self.efectivo += precio - com
            lado = "venta"
        self.tablon.remove(o)
        self._apunta("rastro · aceptamos", lado, ref, precio, o["maker"], comision=com, nos_vale=nos_vale)
        return {"ok": True}



def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ticks", type=int, default=200)
    ap.add_argument("--semilla", type=int, default=1)
    ap.add_argument("--efectivo", type=float, default=None)
    a = ap.parse_args()

    estado = json.load(open(os.path.join(AQUI, "datos", "estado-actual.json"), encoding="utf-8"))
    cartas = [c["ref"] for c in estado.get("cards") or [] if isinstance(c, dict) and c.get("ref")]
    efectivo = estado.get("cash", 0) if a.efectivo is None else a.efectivo
    menus = json.load(open(os.path.join(AQUI, "menus.json"), encoding="utf-8"))

    carpeta = os.path.join(AQUI, "runs", "simulacion", time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(carpeta, exist_ok=True)
    jugar.RUNS = carpeta                                         # nada de runs/ real: ni estado, ni STOP, ni candado

    with open(os.path.join(carpeta, "tratos.jsonl"), "a", encoding="utf-8") as log:
        b = JuegoSimulado(cartas, efectivo, menus, a.semilla, log)
        inicio = {"efectivo": round(b.efectivo, 1), "coleccion": b.valor_coleccion(), "cartas": len(b.activos)}
        pantalla = io.StringIO()
        est, mem = {"hilos": {}}, cadena.Memoria()
        por_tick, un_tick = [], jugar.un_tick

        def contando(juego, *args, **kw):                        # cuántas llamadas al juego hace cada tick
            antes = sum(juego.llamadas.values())
            r = un_tick(juego, *args, **kw)
            por_tick.append(sum(juego.llamadas.values()) - antes)
            return r
        jugar.un_tick = contando
        with redirect_stdout(pantalla):
            try:
                jugar._jugar(b, est, mem, argparse.Namespace(live=True, ticks=a.ticks))
            finally:
                jugar.cancelar_todo(b, est, True, "fin de la simulación")
        open(os.path.join(carpeta, "pantalla.txt"), "w", encoding="utf-8").write(pantalla.getvalue())

    tratos = [json.loads(x) for x in open(os.path.join(carpeta, "tratos.jsonl"), encoding="utf-8") if '"canal"' in x]
    fin = {"efectivo": round(b.efectivo, 1), "coleccion": b.valor_coleccion(), "cartas": len(b.activos)}
    resumen = {"ticks": a.ticks, "semilla": a.semilla, "inicio": inicio, "fin": fin,
               "ganancia": round((fin["efectivo"] + fin["coleccion"]) - (inicio["efectivo"] + inicio["coleccion"]), 1),
               "llamadas_por_tick": {"mediana": sorted(por_tick)[len(por_tick) // 2] if por_tick else 0,
                                     "max": max(por_tick or [0]),
                                     "mas_de_20": sum(1 for n in por_tick if n > 20)},
               "tratos": len(tratos), "por_canal": dict(Counter(t["canal"] for t in tratos)),
               "errores": sum(1 for _ in open(os.path.join(carpeta, "errores.jsonl"), encoding="utf-8"))
               if os.path.exists(os.path.join(carpeta, "errores.jsonl")) else 0}
    json.dump(resumen, open(os.path.join(carpeta, "resumen.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"SIMULACIÓN   {a.ticks} ticks · semilla {a.semilla} · sin red")
    for t in tratos:
        extra = f" · nos vale {t['nos_vale']}" if t["nos_vale"] is not None else ""
        print(f"  tick {t['tick']:>4}  {t['canal']:<26} {t['lado']:<7} {t['carta']:<18} {t['precio']:>6} P  con {t['con']}{extra}")
    print(f"TRATOS       {resumen['tratos']} · " + ", ".join(f"{k}: {v}" for k, v in resumen["por_canal"].items()))
    print(f"EFECTIVO     {inicio['efectivo']} → {fin['efectivo']}")
    print(f"COLECCIÓN    {inicio['coleccion']} → {fin['coleccion']}  ({inicio['cartas']} → {fin['cartas']} cartas)")
    print(f"GANANCIA     {resumen['ganancia']:+} (efectivo + colección)")
    print(f"ERRORES      {resumen['errores']} (errores.jsonl)")
    ll = resumen["llamadas_por_tick"]
    print(f"LLAMADAS     al juego por tick: mediana {ll['mediana']}, como mucho {ll['max']}, "
          f"{ll['mas_de_20']} ticks con más de 20 (tick de {TICK_SEGUNDOS} s)")
    print(f"LOG          {os.path.relpath(carpeta, AQUI)}/tratos.jsonl · pantalla.txt · diario.jsonl")


if __name__ == "__main__":
    main()
