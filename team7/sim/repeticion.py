"""Repetir los duelos reales: las ofertas que mandó el rival entran, una a una, en nuestra estrategia.

    python sim/repeticion.py                       # datos/duelos-reales-03-10.json (GET /api/duels?done=true)

Aproximación: el rival manda los mismos precios que mandó de verdad, aunque nosotros pidamos otra cosa (en el juego
reaccionaba a nuestras ofertas). Cuando se acaban sus mensajes, su última oferta sigue en pie hasta la ronda 16.
Solo cuenta lo que ganamos aceptando una de sus ofertas (no si él hubiera aceptado la nuestra), así que es un suelo.
Los duelos en que el rival no escribió nunca no se pueden repetir: se cuentan aparte.
Puntos = ganancia sobre nuestro límite × (1 − decay)^ronda, como el `result` del juego.
"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from sim import duelos as D  # noqa: E402
from agentes import params  # noqa: E402

DATOS = os.path.join(os.path.dirname(AQUI), "datos", "duelos-reales-03-10.json")
RONDAS = 16


def cargar(ruta=DATOS):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)["duels"]


def sus_precios(d):
    return [m["price"] for m in d["messages"] if m["from"] != "you" and m["price"] is not None]


def repetir(estrategia, d):
    """Devuelve {"puntos", "ronda", "precio"}; ronda None = sin trato."""
    rol, lim, delta = d["role"], d["your_limit"], 1 - d["decay_per_round"]
    suyas = sus_precios(d)
    T = max(RONDAS, len(suyas))
    # cuando se acaban sus mensajes, su última oferta sigue en pie hasta el final (un rival que se planta)
    suyas = suyas + [suyas[-1]] * (T - len(suyas)) if suyas else []
    st = {"rol": rol, "limite": lim, "rival": [], "nuestras": [], "ronda": 0, "rondas": T}
    for i, su in enumerate(suyas):
        st["rival"].append(su)
        st["ronda"] = i
        accion, precio = estrategia(st)[:2]
        if accion == "aceptar":
            return {"puntos": round(D.g(rol, lim, su) * delta ** i, 1), "ronda": i, "precio": su}
        if precio is not None:
            st["nuestras"].append(precio)
    return {"puntos": 0.0, "ronda": None, "precio": None}


def informe(estrategias, duelos):
    """Por estrategia: puntos totales, tratos, tratos a 0 y ofertas dentro del límite que dejó escapar."""
    con_mensajes = [d for d in duelos if sus_precios(d)]
    out = {"duelos": len(duelos), "repetibles": len(con_mensajes),
           "real": {"puntos": round(sum(d["result"] or 0 for d in con_mensajes), 1),
                    "tratos": sum(d["status"] == "deal" for d in con_mensajes)}}
    for nombre, est in estrategias.items():
        res = [(d, repetir(est, d)) for d in con_mensajes]
        escapadas = [d["duel"] for d, r in res if r["ronda"] is None
                     and any(D.g(d["role"], d["your_limit"], x) > 0 for x in sus_precios(d))]
        out[nombre] = {"puntos": round(sum(r["puntos"] for _, r in res), 1),
                       "tratos": sum(r["ronda"] is not None for _, r in res),
                       "tratos_a_cero": [d["duel"] for d, r in res if r["ronda"] is not None and r["puntos"] <= 0],
                       "escapadas": escapadas,
                       "fuera_del_limite": [d["duel"] for d, r in res if r["puntos"] < 0]}
    return out


if __name__ == "__main__":
    print(json.dumps(informe({"nuestra": D.nuestra_adaptativa(params.cargar())}, cargar()), ensure_ascii=False, indent=1))
