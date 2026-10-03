"""Torneo con vendedores simulados: qué estrategia captura más rango, en qué perfil, comprando y vendiendo.

    python sim/torneo_tienda.py            # 2.000 conversaciones por casilla, semilla fija: siempre el mismo resultado
"""
import itertools
import json
import os
import random
import statistics
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from sim import vendedores as V  # noqa: E402
from sim import estrategias as E  # noqa: E402
from t7 import params  # noqa: E402

N = int(os.environ.get("T7_N", 2000))
LISTAS = {"compra": [10, 10, 10, 25, 25, 26], "venta": [10, 10, 25]}


def medir(estrategia, perfil, lado, semilla=7, n=N, hipotesis="base"):
    rng = random.Random(semilla)
    caps, tratos, rondas, cooloff, con_zopa = [], 0, [], 0, 0
    caps_zopa = []
    for _ in range(n):
        lista = rng.choice(LISTAS[lado])
        v, lim = V.mundo(perfil, lado, lista, rng, hipotesis=hipotesis)
        hay_zopa = (v.s * (lim - v.limite)) >= 0
        r = V.jugar(v, lado, lim, lambda st: estrategia(st, perfil), lista=lista)
        caps.append(r["captura"])
        tratos += r["trato"]
        rondas.append(r["rondas"])
        cooloff += r["motivo"] == "cooloff"
        if hay_zopa:
            con_zopa += 1
            caps_zopa.append(r["captura"])
    return {"captura_media": round(statistics.mean(caps), 3),
            "captura_con_zopa": round(statistics.mean(caps_zopa), 3) if caps_zopa else None,
            "tratos": round(tratos / n, 3), "rondas": round(statistics.mean(rondas), 1),
            "cooloff": round(cooloff / n, 3)}


def robusto(estrategia, perfil, lado, n=N):
    """La misma estrategia en los cuatro mundos. nota = media de (media + peor mundo) / 2: premia no hundirse en ninguno."""
    por = {h: medir(estrategia, perfil, lado, n=n, hipotesis=h) for h in V.MUNDOS}
    caps = [m["captura_media"] for m in por.values()]
    return {"nota": round((statistics.mean(caps) + min(caps)) / 2, 3), "media": round(statistics.mean(caps), 3),
            "peor": round(min(caps), 3), "tratos": round(statistics.mean(m["tratos"] for m in por.values()), 3),
            "cooloff": round(statistics.mean(m["cooloff"] for m in por.values()), 3), "por_mundo": por}


def barrido(perfil, lado, p):
    """Prueba aperturas, paciencia estimada y margen para nuestra estrategia; devuelve la mejor y la tabla."""
    base = params.perfil(p, perfil)
    tabla = []
    aperturas = [0.05, 0.1, 0.15, 0.2, 0.3, 0.4] if lado == "compra" else [base["apertura_compra"]]
    for ap, pac, mar, kr in itertools.product(aperturas, [5, 7, 10], [0, 2], [0.0, 0.5, 1.0]):
        pf = dict(base, apertura_compra=ap, paciencia_estimada=pac, margen_rondas=mar, k_reciproco=kr)
        m = robusto(E.adaptativo(pf, p), perfil, lado, n=max(250, N // 8))
        m.pop("por_mundo")
        tabla.append({"apertura": ap, "paciencia": pac, "margen": mar, "k_reciproco": kr, **m})
    tabla.sort(key=lambda r: -r["nota"])
    return tabla


def main():
    p = params.cargar()
    out = {"n": N, "comparacion": {}, "barrido": {}}
    for perfil in V.PERFILES:
        for lado in ("compra", "venta"):
            tabla = barrido(perfil, lado, p)
            mejor = tabla[0]
            pf = dict(params.perfil(p, perfil), apertura_compra=mejor["apertura"],
                      paciencia_estimada=mejor["paciencia"], margen_rondas=mejor["margen"], k_reciproco=mejor["k_reciproco"])
            fila = {"ana_actual": robusto(E.ana_actual, perfil, lado),
                    "ganador": robusto(E.ganador, perfil, lado),
                    "nuestra_con_parametros_actuales": robusto(E.adaptativo(params.perfil(p, perfil), p), perfil, lado),
                    "nuestra_ajustada": robusto(E.adaptativo(pf, p), perfil, lado),
                    "ajuste": {k: mejor[k] for k in ("apertura", "paciencia", "margen", "k_reciproco")}}
            out["comparacion"][f"{perfil}/{lado}"] = fila
            out["barrido"][f"{perfil}/{lado}"] = tabla[:12]
            print(perfil, lado, json.dumps({k: (v["nota"], v["media"], v["peor"], v["tratos"]) if "nota" in v else v
                                            for k, v in fila.items()}, ensure_ascii=False))
    os.makedirs(os.path.join(os.path.dirname(AQUI), "resultados"), exist_ok=True)
    with open(os.path.join(os.path.dirname(AQUI), "resultados", "tienda.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
