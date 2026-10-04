"""Market Test simulado, según la descripción del kit (starter_broker.py) y de "Para Ana":
16 ticks; compradores y vendedores con límite oculto; anuncian alejados de él (holgura 10–40 %); los que relajan acercan
su precio en línea recta hasta su límite al final de su paciencia y se van; los firmes no se mueven nunca.
Eficiencia = ganancia real de los pares emparejados / máxima posible con todos los límites reales.
"""
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agentes.broker import Casamentero, cruce_simple  # noqa: E402

TICKS = 16


def sesion(rng, n=6, p_firme=0.2, p_impaciente=0.4, n_venta=None, holgura=(0.10, 0.40)):
    gente = []
    nv = n if n_venta is None else n_venta
    for i in range(n + nv):
        lado = "compra" if i < n else "venta"
        lim = rng.uniform(40, 120) if lado == "compra" else rng.uniform(30, 110)
        tipo = "firme" if rng.random() < p_firme else "impaciente" if rng.random() < p_impaciente else "paciente"
        pac = rng.randint(6, 16) if tipo == "firme" else rng.randint(2, 6) if tipo == "impaciente" else rng.randint(8, 16)
        gente.append({"id": f"b1-{i}", "lado": lado, "lim": lim, "h": rng.uniform(*holgura), "tipo": tipo,
                      "pac": pac, "llega": rng.randint(0, 8)})
    return gente


def precio(x, tick):
    edad = tick - x["llega"]
    s = 1 if x["lado"] == "compra" else -1
    h = x["h"] if x["tipo"] == "firme" else x["h"] * (1 - min(edad / x["pac"], 1))
    return round(x["lim"] * (1 - s * h))


def maximo(gente):
    cb = sorted((x["lim"] for x in gente if x["lado"] == "compra"), reverse=True)
    cv = sorted(x["lim"] for x in gente if x["lado"] == "venta")
    return sum(max(0, b - v) for b, v in zip(cb, cv))


def jugar(gente, plan_fn):
    vivos, ganancia = {}, 0.0
    for tick in range(TICKS):
        for x in gente:
            if x["llega"] == tick:
                vivos[x["id"]] = x
        for i in [i for i, x in vivos.items() if tick - x["llega"] >= x["pac"]]:
            del vivos[i]
        ordenes = [{"id": i, "lado": x["lado"], "precio": precio(x, tick)} for i, x in vivos.items()]
        for v_, b_, _ in plan_fn(tick, ordenes):
            if v_ in vivos and b_ in vivos and precio(vivos[b_], tick) >= precio(vivos[v_], tick):
                ganancia += vivos[b_]["lim"] - vivos[v_]["lim"]
                del vivos[v_], vivos[b_]
    m = maximo(gente)
    return ganancia / m if m > 0 else 1.0


def comparar(n=400, semilla=5, **kw):
    rng = random.Random(semilla)
    sesiones = [sesion(rng, **kw) for _ in range(n)]
    res = {"puesto_gratuito": statistics.mean(jugar(g, lambda t, o: cruce_simple(o)) for g in sesiones)}
    for cierre in (8, 10, 12, 14):
        for prisa in (0, 1, 2):
            res[f"casamentero_c{cierre}_p{prisa}"] = statistics.mean(
                jugar(g, Casamentero(tick_cierre=cierre, prisa=prisa).plan) for g in sesiones)
    return {k: round(v, 3) for k, v in res.items()}


if __name__ == "__main__":
    for nombre, kw in {"base": {}, "muchos_firmes": {"p_firme": 0.5}, "muy_impacientes": {"p_impaciente": 0.8},
                       "mas_gente": {"n": 10}}.items():
        r = comparar(**kw)
        mejor = max(r, key=r.get)
        print(nombre, "puesto", r["puesto_gratuito"], "mejor", mejor, r[mejor])
