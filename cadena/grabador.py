"""El Grabador: guarda el libro de cada Market Test para decidir con datos si nuestro broker supera al automático.

    python grabador.py                        graba: lee el libro una vez por tick (SOLO GET), sin fin
    python grabador.py --rejugar runs/bench   sin red: rejuega cada sesión grabada con el automático y con El Casamentero

Por qué: el Market Test da la mitad de los puntos al que empareja como el puesto gratuito; los puntos completos son
para la media de los tres mejores. Abrir un mercado "board" con broker propio solo compensa si, con libros REALES,
El Casamentero (t7/broker.py) hace más que el cruce automático (broker.cruce_simple). Esto lo mide antes de gastar 270 P.

Clave del broker: BAZAAR_BROKER_KEY, o la starter_broker_key que da me() con el puesto gratuito (la del equipo:
BAZAAR_KEY o bazaar-kit/.env). No se escribe en ningún archivo. No empareja, no anuncia, no acepta: solo lee.
Escribe runs/bench/<tick de inicio>.jsonl: una línea por tick con las órdenes de prueba (bench_offers) normalizadas
y las crudas, para comprobar la forma la primera vez.
"""
import argparse
import glob
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(AQUI))  # bazaar_sdk.py vive en la raíz del repo, no en una subcarpeta "bazaar-kit"

from t7 import broker  # noqa: E402

CARPETA = os.path.join(AQUI, "runs", "bench")


def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def normalizar(crudas):
    """[{"id", "lado": "compra"|"venta", "precio"}] desde bench_offers, en la forma que venga. Lo que no se entiende
    se deja fuera (y queda en el crudo)."""
    out = []
    for o in crudas if isinstance(crudas, list) else []:
        if not isinstance(o, dict) or o.get("id") is None:
            continue
        lado = str(o.get("side") or o.get("lado") or o.get("kind") or "").lower()
        give, want = o.get("give") or {}, o.get("want") or {}
        if lado in ("buy", "bid", "buyer", "compra"):
            lado = "compra"
        elif lado in ("sell", "ask", "seller", "venta"):
            lado = "venta"
        elif isinstance(give, dict) and _num(give.get("cash")) is not None:
            lado = "compra"
        elif isinstance(want, dict) and _num(want.get("cash")) is not None:
            lado = "venta"
        else:
            continue
        precio = _num(o.get("price"))
        if precio is None:
            precio = _num((give if lado == "compra" else want).get("cash")) if isinstance(give, dict) and isinstance(want, dict) else None
        if precio is not None:
            out.append({"id": o["id"], "lado": lado, "precio": precio})
    return out


def _libro(bk):
    lib = bk.book()
    crudas = lib.get("bench_offers") if isinstance(lib, dict) else None
    return crudas or [], lib


def clave_broker(b):
    if os.environ.get("BAZAAR_BROKER_KEY"):
        return os.environ["BAZAAR_BROKER_KEY"]
    me = b.me()
    return me.get("starter_broker_key") or (me.get("starter_stall") or {}).get("broker_key")


def grabar(b, bk, max_ticks=0):
    os.makedirs(CARPETA, exist_ok=True)
    ultimo, sesion, hechos = None, None, 0
    while not max_ticks or hechos < max_ticks:
        try:
            reloj = bk.clock()
        except Exception as e:
            print("RED          sin respuesta:", e)
            time.sleep(2.0)
            continue
        tick = reloj.get("tick")
        if reloj.get("paused") or tick == ultimo:
            time.sleep(min(2.0, max(0.2, float(reloj.get("next_tick_in") or 1.0))))
            continue
        ultimo, hechos = tick, hechos + 1
        try:
            crudas, lib = _libro(bk)
        except Exception as e:
            print("ERROR        libro:", e)
            continue
        if not crudas:
            if sesion:
                print(f"FIN          sesión {sesion} grabada")
            sesion = None
            continue
        sesion = sesion or tick
        norm = normalizar(crudas)
        with open(os.path.join(CARPETA, f"{sesion}.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"tick": tick, "ordenes": norm, "crudas": crudas,
                                "liquidaciones": lib.get("settlements") or lib.get("recent") if isinstance(lib, dict) else None},
                               ensure_ascii=False, default=str) + "\n")
        print(f"BENCH        tick {tick}: {len(norm)} órdenes entendidas de {len(crudas)}")


def _ganancia(pares, precios):
    """Ganancia ANUNCIADA (compra − venta) de los pares: aproximación, los límites reales están ocultos."""
    return sum(precios[c] - precios[v] for v, c, _ in pares)


def rejugar(ruta):
    """Cada sesión grabada, tick a tick: cada estrategia ve las órdenes que siguen vivas y no emparejadas por ella."""
    archivos = sorted(glob.glob(os.path.join(ruta, "*.jsonl"))) if os.path.isdir(ruta) else [ruta]
    tabla = []
    for a in archivos:
        with open(a, encoding="utf-8") as f:
            ticks = [json.loads(x) for x in f if x.strip()]
        res = {}
        for nombre, hacer in (("automatico", lambda: (lambda t, o: broker.cruce_simple(o))),
                              ("casamentero", lambda: broker.Casamentero(tick_cierre=max(0, len(ticks) - 4),
                                                                        ultimo_tick=len(ticks) - 1).plan)):
            plan_fn, usados, total, precios = hacer(), set(), 0.0, {}
            for i, t in enumerate(ticks):
                vivas = [o for o in t["ordenes"] if o["id"] not in usados]
                precios.update({o["id"]: o["precio"] for o in vivas})
                pares = plan_fn(i, vivas)
                pares = [p for p in pares if p[0] not in usados and p[1] not in usados]
                usados |= {x for p in pares for x in p[:2]}
                total += _ganancia(pares, precios)
            res[nombre] = round(total, 1)
        tabla.append((os.path.basename(a), res))
        print(f"{os.path.basename(a):>16}  automático {res['automatico']:>8}   casamentero {res['casamentero']:>8}")
    if tabla:
        gana = sum(1 for _, r in tabla if r["casamentero"] > r["automatico"])
        print(f"El Casamentero gana en {gana} de {len(tabla)} sesiones (ganancia anunciada, no la real).")
    return tabla


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rejugar", help="carpeta o archivo .jsonl grabado: rejuega sin red")
    ap.add_argument("--ticks", type=int, default=0, help="parar tras N ticks (0 = sin fin)")
    a = ap.parse_args()
    for s in (sys.stdout,):
        if hasattr(s, "reconfigure"):
            s.reconfigure(errors="replace")
    if a.rejugar:
        rejugar(a.rejugar)
        return
    from bazaar_sdk import Bazaar
    import vigia
    url, clave = vigia.credenciales()
    if not clave:
        sys.exit("Falta la clave del equipo (BAZAAR_KEY o bazaar-kit/.env).")
    b = Bazaar(url, clave, wait_on_tick=False)
    kb = clave_broker(b)
    if not kb:
        sys.exit("No hay clave de broker: ni BAZAAR_BROKER_KEY ni starter_broker_key en me().")
    grabar(b, b.broker(kb), a.ticks)


if __name__ == "__main__":
    main()
