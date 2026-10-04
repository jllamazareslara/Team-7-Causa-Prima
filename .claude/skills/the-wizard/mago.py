"""The Wizard: la mejor oportunidad del Team 7 ahora mismo (solo lectura). Nunca imprime claves ni actúa.

    python .claude/skills/the-wizard/mago.py               las mejores oportunidades, la mejor primero
    python .claude/skills/the-wizard/mago.py --top 20      más filas
    python .claude/skills/the-wizard/mago.py --json        todo en JSON (sin claves)

Junta, en una sola mirada:
    1. los Ojos           la última vista de cadena/runs/ojos.json (si está en marcha), con su edad
    2. el Bazaar          todos los mercados abiertos (/api/venues y su tablón): El Rastro y los de otros equipos, cada
                          uno con SU comisión; y el feed (/api/feed): a qué precio se están cerrando tratos
    3. nuestro mercado    nuestro puesto (me.venue) y nuestras ofertas abiertas (/api/me/offers): las que ya no rentan
    4. los vendedores     sus menús (/api/dealers): lo que venden y compran y a qué precio de lista
Cada oportunidad lleva la fórmula del valor desglosada y se compara con el juego:
    your_value = book × factor_copia × afinidad + bono_página
    book: común 10 · poco común 25 · rara 70 · épica 180 · legendaria 450
    factor_copia: 1.ª copia 1,0 · 2.ª 0,25 · 3.ª y siguientes 0,10
    afinidad (Team 7): LAT 1,6 · RET 1,3 · LAV 1,1 · CHA 0,9 · SAL 0,7 · MAL 0,5 (se lee del juego, /api/me affinity)
    bono_página al completar 10/10: 0,25 × 265 × afinidad (+ 0,10 × 265 × afinidad con las extras 11-12)
Si la fórmula y el your_value no coinciden, se avisa: manda el del juego.
Y valora cada carta con el your_value del juego: el de nuestra copia (/api/me) al vender y GET /api/me/value al
comprar (solo para las cartas que podrían rentar, para no gastar llamadas). Lo que no tiene valor del juego no se
propone. La clave se lee de BAZAAR_KEY (y la URL de BAZAAR_URL). Solo GET.
"""
import argparse
import json
import math
import os
import re
import sys
import time
from collections import Counter

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(AQUI, "..", "..", ".."))
CADENA = os.path.join(REPO, "cadena")
sys.path.insert(0, REPO)
sys.path.insert(0, CADENA)

for _salida in (sys.stdout, sys.stderr):
    if hasattr(_salida, "reconfigure"):
        _salida.reconfigure(errors="replace")

RASTRO = {"pct": 0.05, "por_carta": 1}          # comisión de El Rastro: 5 % + 1 P por carta (la paga quien acepta)
TOPE = {"pct": 0.10, "por_carta": 5}            # comisión desconocida: el tope de las reglas, para no quedarnos cortos
MARGEN = 0.10                                   # buen negocio del equipo (guardia.margen_compra / margen_venta)


# ---------------------------------------------------------------- utilidades

def tapar(x):
    """Quita cualquier clave: campos *key*/*token*/*secret* y valores tk-... / bk_..."""
    if isinstance(x, dict):
        return {k: "<OCULTA>" if re.search("key|token|secret", k, re.I) else tapar(v) for k, v in x.items()}
    if isinstance(x, list):
        return [tapar(v) for v in x]
    if isinstance(x, str) and re.match(r"^(tk-|bk_)", x):
        return "<OCULTA>"
    return x


def _lista(x, *claves):
    if isinstance(x, list):
        return x
    if isinstance(x, dict):
        for k in claves:
            if isinstance(x.get(k), list):
                return x[k]
    return []


def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def comision(precio, cartas, fee):
    return math.ceil(precio * fee["pct"]) + fee["por_carta"] * cartas if precio or cartas else 0


def cartas_de(lado):
    """Las cartas de un lado de una oferta (assets con ref, types "card:X"). None si trae algo que no es carta."""
    refs = []
    for a in (lado or {}).get("assets") or []:
        if not (isinstance(a, dict) and isinstance(a.get("ref"), str)):
            return None
        refs.append(a["ref"])
    for t in (lado or {}).get("types") or []:
        if not (isinstance(t, str) and t.startswith("card:")):
            return None
        refs.append(t.split(":", 1)[1])
    return refs


# ---------------------------------------------------------------- leer

def ojos_vista():
    """La vista más reciente de los Ojos (carpeta principal o el worktree wt-ojos), con su edad en segundos."""
    sitios = [os.path.join(CADENA, "runs", "ojos.json"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp", "wt-ojos", "cadena", "runs", "ojos.json")]
    vistas = [(os.path.getmtime(s), s) for s in sitios if os.path.exists(s)]
    if not vistas:
        return None
    t, ruta = max(vistas)
    try:
        with open(ruta, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    return {"ruta": ruta, "edad_s": round(time.time() - t), "tick": d.get("tick"), "hora": d.get("hora"),
            "vista": d.get("vista") or {}}


def leer(b, tablones_max=25):
    """Todo lo que hace falta, solo GET. Un fallo en una parte no tira las demás: se apunta en "fallos"."""
    datos, fallos = {}, []

    def intenta(nombre, f, defecto=None):
        try:
            return f()
        except Exception as e:                        # noqa: BLE001  (se apunta y se sigue)
            fallos.append(f"{nombre}: {e}")
            return defecto

    datos["me"] = tapar(intenta("me", b.me, {}) or {})
    datos["venues"] = intenta("venues", b.venues, {})
    datos["feed"] = intenta("feed", lambda: b.feed(150), {})
    datos["dealers"] = intenta("dealers", b.dealers, {})
    datos["mis_ofertas"] = intenta("mis ofertas", b.my_offers, {})
    ids = ["rastro"] + [v["id"] for v in mercados(datos["venues"]) if v["id"] != "rastro"]
    datos["tablones"] = {}
    for v in ids[:tablones_max]:
        datos["tablones"][v] = _lista(intenta(f"tablón {v}", lambda v=v: b.board(v), {}), "offers")
    datos["fallos"] = fallos
    return datos


def mercados(venues):
    """[{"id", "nombre", "fee": {"pct", "por_carta"}, "conocida": bool}] de /api/venues. El Rastro siempre está."""
    out, vistos = [], set()
    for v in _lista(venues, "venues", "items"):
        if not isinstance(v, dict):
            continue
        vid = v.get("id") or v.get("venue") or v.get("slug")
        if vid is None or v.get("status") in ("closed", "frozen"):
            continue
        vid = str(vid)
        bps = _num(v.get("fee_bps"))
        por = _num(v.get("fee_per_card"))
        fee = {"pct": bps / 10000 if bps is not None else TOPE["pct"], "por_carta": por if por is not None else TOPE["por_carta"]}
        if vid == "rastro":
            fee = dict(RASTRO)
        out.append({"id": vid, "nombre": v.get("name") or vid, "fee": fee,
                    "conocida": vid == "rastro" or bps is not None, "dueño": v.get("owner") or v.get("team")})
        vistos.add(vid)
    if "rastro" not in vistos:
        out.insert(0, {"id": "rastro", "nombre": "El Rastro", "fee": dict(RASTRO), "conocida": True, "dueño": None})
    return out


def precios_feed(feed):
    """{carta: [precios de tratos de UNA carta]}, del más reciente al más viejo."""
    out = {}
    for e in _lista(feed, "events", "feed", "items"):
        pl = e.get("payload") if isinstance(e.get("payload"), dict) else e
        cartas = [x for x in pl.get("items") or [] if isinstance(x, dict) and x.get("kind", "card") == "card"]
        precio = _num(pl.get("price"))
        if len(cartas) == 1 and precio is not None and cartas[0].get("ref"):
            out.setdefault(cartas[0]["ref"], []).append(precio)
    return out


# ---------------------------------------------------------------- valorar

class Valores:
    """El your_value del juego: el de nuestra copia que menos vale (me.assets) y el de una copia más (/api/me/value),
    pedido una sola vez por carta. La calculadora (cadena/t7/valor.py) solo decide a qué cartas preguntar."""

    def __init__(self, b, me):
        from t7 import valor as V
        self.V, self.b, self.pedidas = V, b, 0
        cartas = [a for a in me.get("assets") or [] if isinstance(a, dict) and a.get("kind") == "card" and a.get("ref")]
        V.configurar(me.get("affinity"), None, cartas)
        self.cuenta = Counter(a["ref"] for a in cartas)
        self.dar = {}
        for a in cartas:
            v = _num(a.get("your_value"))
            if v is not None:
                self.dar[a["ref"]] = min(v, self.dar.get(a["ref"], v))
        self.recibir = {}

    def calculado(self, ref):
        return self.V.valor_recibir(self.cuenta, [ref]) if self.V.conocida(ref) else None

    def nos_suma(self, ref, precio_max=None):
        """your_value de una copia más. Si la calculadora dice que ni de lejos llega a precio_max, no se pregunta."""
        if ref in self.recibir:
            return self.recibir[ref]
        calc = self.calculado(ref)
        if calc is None or (precio_max is not None and calc < 0.7 * precio_max):
            return None
        try:
            r = self.b.value(ref)
            self.pedidas += 1
            v = _num(r.get("your_value", r.get("value")) if isinstance(r, dict) else r)
        except Exception:                             # noqa: BLE001
            v = None
        self.recibir[ref] = v
        return v

    def nos_quita(self, ref):
        return self.dar.get(ref) if self.cuenta.get(ref, 0) > 0 else None

    def protegida(self, ref):
        return self.V.protegida(self.cuenta, ref)

    def formula(self, ref, lado):
        """La fórmula, desglosada: (texto, valor). compra = la copia que entra; venta = la copia que sale."""
        V = self.V
        if not V.conocida(ref):
            return None, None
        b, rar = V.barrio(ref), V.rareza(ref)
        book, afin = V.BASE[rar], V.NUESTROS_MULT.get(b, 1.0)
        n = self.cuenta.get(ref, 0) + (1 if lado == "compra" else 0)        # nº de la copia que entra o sale
        if n < 1:
            return None, None
        fac = V.factor(n)
        antes = dict(self.cuenta)
        despues = dict(antes)
        despues[ref] = despues.get(ref, 0) + (1 if lado == "compra" else -1)
        completa_con = antes if lado == "venta" else despues                # la cuenta con la página entera
        sin = despues if lado == "venta" else antes
        suma_pag = sum(V.BASE[V.rareza(r)] for r in V.pagina(b))
        bono, txt_bono = 0.0, ""
        llena = lambda c: all(c.get(r, 0) > 0 for r in V.pagina(b))       # noqa: E731
        if llena(completa_con) and not llena(sin):
            bono = 0.25 * suma_pag * afin
            txt_bono = f" + 0,25 × {suma_pag} × {afin:g} (página)"
            extras = V._extras(b)
            if extras and all(completa_con.get(r, 0) > 0 for r in extras):
                bono += 0.10 * suma_pag * afin
                txt_bono += f" + 0,10 × {suma_pag} × {afin:g} (extras)"
        valor = book * fac * afin + bono
        return f"{book} × {fac:g} × {afin:g}{txt_bono} = {valor:.1f}", round(valor, 2)

    def completa(self, ref):
        return self.V.estado_pagina(self.cuenta, self.V.barrio(ref))[1] == [ref] if self.V.conocida(ref) else False


# ---------------------------------------------------------------- oportunidades

def oportunidades(datos, val, nosotros):
    """Todas las oportunidades con su ganancia neta (P, ya sin comisión), de mayor a menor.
    tipo: "aceptar" (está en un tablón ahora), "vendedor" (precio de lista de un menú: se puede regatear) o
    "publicar" (petición o anuncio nuestro en un mercado sin comisión, al precio del último trato del feed)."""
    ops = []
    fees = {m["id"]: m for m in mercados(datos.get("venues"))}
    nuestro = (datos.get("me") or {}).get("venue") or ""
    nuestro = str(nuestro.get("venue") or nuestro.get("id") or "") if isinstance(nuestro, dict) else str(nuestro)

    # 1. aceptar ya: ofertas de UNA carta por dinero en cualquier tablón (menos el nuestro: self_venue)
    for venue, ofertas in (datos.get("tablones") or {}).items():
        m = fees.get(venue) or {"fee": TOPE, "conocida": False, "nombre": venue}
        for o in ofertas:
            if not isinstance(o, dict) or o.get("maker") in nosotros or o.get("status") not in (None, "open"):
                continue
            if o.get("to") not in (None, *nosotros):
                continue
            da, pide = cartas_de(o.get("give")), cartas_de(o.get("want"))
            if da is None or pide is None:
                continue
            cash_da, cash_pide = _num((o.get("give") or {}).get("cash")) or 0, _num((o.get("want") or {}).get("cash")) or 0
            if len(da) == 1 and not pide and cash_pide and not cash_da:            # nos venden una carta
                ref, precio = da[0], cash_pide
                com = comision(precio, 1, m["fee"])
                v = val.nos_suma(ref, precio + com)
                if v is None:
                    continue
                gana = v - precio - com
                ops.append({"tipo": "aceptar", "lado": "compra", "carta": ref, "precio": precio, "comision": com,
                            "vale": v, "gana": round(gana, 1), "margen_ok": gana >= MARGEN * v, "donde": venue,
                            "oferta": o.get("id"), "de": o.get("maker"), "completa": val.completa(ref),
                            "comision_conocida": m["conocida"]})
            elif len(pide) == 1 and not da and cash_da and not cash_pide:          # nos compran una carta
                ref, precio = pide[0], cash_da
                pierde = val.nos_quita(ref)
                if pierde is None or val.protegida(ref):
                    continue
                com = comision(precio, 1, m["fee"])
                gana = precio - com - pierde
                ops.append({"tipo": "aceptar", "lado": "venta", "carta": ref, "precio": precio, "comision": com,
                            "vale": pierde, "gana": round(gana, 1), "margen_ok": gana >= MARGEN * pierde,
                            "donde": venue, "oferta": o.get("id"), "de": o.get("maker"), "completa": False,
                            "comision_conocida": m["conocida"]})

    # 2. vendedores: precio de lista del menú (sin comisión; se regatea a la baja comprando y al alza vendiendo)
    try:
        from t7 import menus as M
        menus, _ = M.del_juego(datos.get("dealers") or {}, dict(val.cuenta))
    except Exception:                                 # noqa: BLE001
        menus = {}
    abiertos = set((datos.get("me") or {}).get("unlocked") or [])
    for quien, menu in menus.items():
        if abiertos and quien not in abiertos:
            continue
        for ref, precio in (menu.get("vende") or {}).items():
            if val.cuenta.get(ref, 0) > 0 or not _num(precio):
                continue
            v = val.nos_suma(ref, precio)
            if v is None or v <= precio:
                continue
            ops.append({"tipo": "vendedor", "lado": "compra", "carta": ref, "precio": precio, "comision": 0, "vale": v,
                        "gana": round(v - precio, 1), "margen_ok": v - precio >= MARGEN * v, "donde": quien,
                        "completa": val.completa(ref)})
        for ref, precio in (menu.get("compra") or {}).items():
            pierde = val.nos_quita(ref)
            if pierde is None or val.protegida(ref) or not _num(precio) or precio <= pierde:
                continue
            ops.append({"tipo": "vendedor", "lado": "venta", "carta": ref, "precio": precio, "comision": 0,
                        "vale": pierde, "gana": round(precio - pierde, 1), "margen_ok": precio - pierde >= MARGEN * pierde,
                        "donde": quien, "completa": False})

    # 3. publicar en un mercado sin comisión, al precio del último trato visto en el feed
    gratis = [mm["id"] for mm in fees.values() if mm["conocida"] and mm["fee"]["pct"] == 0 and mm["fee"]["por_carta"] == 0
              and mm["id"] != nuestro]
    if gratis:
        for ref, precios in precios_feed(datos.get("feed")).items():
            ultimo = precios[0]
            if val.cuenta.get(ref, 0) == 0:
                v = val.nos_suma(ref, ultimo)
                if v is not None and v - ultimo >= MARGEN * v:
                    ops.append({"tipo": "publicar", "lado": "compra", "carta": ref, "precio": ultimo, "comision": 0,
                                "vale": v, "gana": round(v - ultimo, 1), "margen_ok": True, "donde": gratis[0],
                                "completa": val.completa(ref), "feed": precios[:5]})
            elif val.cuenta[ref] > 1 and not val.protegida(ref):
                pierde = val.nos_quita(ref)
                if pierde is not None and ultimo - pierde >= MARGEN * pierde and ultimo - pierde >= 1:
                    ops.append({"tipo": "publicar", "lado": "venta", "carta": ref, "precio": ultimo, "comision": 0,
                                "vale": pierde, "gana": round(ultimo - pierde, 1), "margen_ok": True, "donde": gratis[0],
                                "completa": False, "feed": precios[:5]})

    puntos = {"aceptar": "negociar · valor ganado con equipos", "publicar": "negociar · valor ganado con equipos",
              "vendedor": "negociar · escalera de vendedores"}
    for o in ops:                                     # la fórmula, siempre, y si coincide con el juego
        o["formula"], o["valor_formula"] = val.formula(o["carta"], o["lado"])
        o["formula_ok"] = o["valor_formula"] is None or abs(o["valor_formula"] - o["vale"]) <= 0.5
        o["puntos"] = puntos[o["tipo"]] if o["gana"] > 0 else "no suma puntos: no gana valor"
    orden = {"aceptar": 0, "vendedor": 1, "publicar": 2}
    ops.sort(key=lambda x: (not x["margen_ok"], -x["gana"] - (25 if x["completa"] else 0), orden[x["tipo"]]))
    return [o for o in ops if o["gana"] > 0]


def revisar_nuestras(datos, val, fees):
    """Nuestras ofertas abiertas que ya no rentan con el your_value de ahora (para cancelarlas si el usuario quiere)."""
    malas = []
    for o in _lista(datos.get("mis_ofertas"), "offers"):
        if not isinstance(o, dict) or o.get("status") not in (None, "open", "queued"):
            continue
        if o.get("to") is not None and o.get("maker") not in ("me", "you") and o.get("mine") is False:
            continue
        da, pide = cartas_de(o.get("give")), cartas_de(o.get("want"))
        if da is None or pide is None:
            continue
        cash_da, cash_pide = _num((o.get("give") or {}).get("cash")) or 0, _num((o.get("want") or {}).get("cash")) or 0
        if len(da) == 1 and not pide and cash_pide:          # anuncio nuestro: vendemos da[0]
            pierde = val.nos_quita(da[0])
            if pierde is not None and cash_pide < pierde + 1:
                malas.append({"oferta": o.get("id"), "que": f"vendemos {da[0]} a {cash_pide} P y nos quita {pierde:.1f}"})
        elif len(pide) == 1 and not da and cash_da:          # petición nuestra: compramos pide[0]
            v = val.recibir.get(pide[0])
            if v is not None and cash_da >= v:
                malas.append({"oferta": o.get("id"), "que": f"pagamos {cash_da} P por {pide[0]} y nos suma {v:.1f}"})
    return malas


# ---------------------------------------------------------------- contar

def linea(o):
    accion = {("aceptar", "compra"): "COMPRAR ya", ("aceptar", "venta"): "VENDER ya",
              ("vendedor", "compra"): "COMPRAR a vendedor", ("vendedor", "venta"): "VENDER a vendedor",
              ("publicar", "compra"): "PEDIR (publicar)", ("publicar", "venta"): "ANUNCIAR (publicar)"}[(o["tipo"], o["lado"])]
    extra = []
    if o.get("oferta") is not None:
        extra.append(f"oferta {o['oferta']}")
    if o["comision"]:
        extra.append(f"comisión {o['comision']}" + ("" if o.get("comision_conocida", True) else " (supuesta)"))
    if o["completa"]:
        extra.append("COMPLETA PÁGINA")
    if not o["margen_ok"]:
        extra.append("no llega al 10 %")
    if o.get("feed"):
        extra.append("feed " + ", ".join(str(p) for p in o["feed"]))
    if o.get("formula") and not o.get("formula_ok", True):
        extra.append(f"OJO: la fórmula da {o['valor_formula']:.1f} y el juego {o['vale']:.1f} (manda el juego)")
    cabeza = (f"{accion:20} {o['carta']:7} {o['precio']:>4} P en {o['donde']:<10} · nos {'suma' if o['lado'] == 'compra' else 'quita'} "
              f"{o['vale']:.1f} · gana {o['gana']:+.1f}" + (" · " + " · ".join(extra) if extra else ""))
    if o.get("formula"):
        cabeza += f"\n{'':23}fórmula: {o['formula']} · puntos: {o.get('puntos')}"
    return cabeza


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    from bazaar_sdk import Bazaar
    key = os.environ.get("BAZAAR_KEY")
    if not key:
        sys.exit("Falta BAZAAR_KEY en el entorno (no la escribas en archivos ni en el chat).")
    b = Bazaar(os.environ.get("BAZAAR_URL", "https://bazaar.causaprima.ai"), key)

    ojos = ojos_vista()
    datos = leer(b)
    me = datos["me"]
    nosotros = tuple(str(x) for x in (me.get("id"), me.get("name")) if x) + ("me", "you")
    val = Valores(b, me)
    ops = oportunidades(datos, val, nosotros)
    fees = {m["id"]: m for m in mercados(datos.get("venues"))}
    malas = revisar_nuestras(datos, val, fees)

    if a.json:
        print(json.dumps(tapar({"ojos": ojos, "oportunidades": ops, "nuestras_malas": malas, "fallos": datos["fallos"],
                                "mercados": list(fees.values()), "llamadas_value": val.pedidas}),
                         ensure_ascii=False, indent=1, default=str))
        return

    s = (me.get("score") or {})
    print(f"THE WIZARD · tick {me.get('tick')} · {me.get('cash')} P · puntos {s.get('score')} (puesto {s.get('rank')})")
    if ojos:
        v = ojos["vista"]
        print(f"Ojos: vista del tick {ojos['tick']} (hace {ojos['edad_s']} s) · {len(v.get('propuestas') or [])} propuestas · "
              f"{len(v.get('descartadas') or [])} descartadas" + (" · VIEJA: lanza los Ojos para refrescar" if ojos["edad_s"] > 120 else ""))
        for pr in (v.get("propuestas") or [])[:3]:
            print(f"   Ojos proponen: {pr.get('lado')} {pr.get('carta')} a {pr.get('precio')} (oferta {pr.get('aceptar')}) · {pr.get('motivo')}")
    else:
        print("Ojos: sin vista (no están en marcha)")
    v_nuestro = me.get("venue").get("venue") if isinstance(me.get("venue"), dict) else me.get("venue")
    gratis = [m["id"] for m in fees.values() if m["conocida"] and m["fee"]["pct"] == 0 and m["fee"]["por_carta"] == 0
              and m["id"] != v_nuestro]
    print(f"Mercados leídos: {len(datos['tablones'])} · sin comisión: {', '.join(gratis) or 'ninguno'} · "
          f"nuestro: {(me.get('venue') or {}).get('venue') if isinstance(me.get('venue'), dict) else me.get('venue')} · "
          f"/api/me/value pedidas: {val.pedidas}")
    for f in datos["fallos"]:
        print(f"   fallo al leer {f}")

    if not ops:
        print("\nNinguna oportunidad que gane algo ahora mismo.")
    else:
        mejor = ops[0]
        print("\nLA MEJOR OPORTUNIDAD")
        print("   " + linea(mejor))
        print(f"\nOtras ({min(len(ops) - 1, a.top)} de {len(ops) - 1}):")
        for o in ops[1:a.top + 1]:
            print("   " + linea(o))
    if malas:
        print("\nNuestras ofertas que ya no rentan:")
        for m in malas:
            print(f"   oferta {m['oferta']}: {m['que']}")
    print("\nSolo miro: nada se compra, vende, publica ni acepta sin que lo pidas y fijes un tope.")


if __name__ == "__main__":
    main()
