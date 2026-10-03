"""Duelos simulados: nuestras estrategias contra ocho tipos de rival y entre ellas.

Protocolo (supuesto, a confirmar con un duelo real): por turnos; quien habla manda un precio o acepta el último del otro.
Una ronda = un mensaje de cada lado. Sin trato tras T rondas, cero. Puntuación de cada lado:
    parte de la tarta = (su ganancia / tarta) × δ^ronda       (negativa si cerró fuera de su límite)
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from t7 import duelo  # noqa: E402


def g(rol, lim, precio):
    return precio - lim if rol == "seller" else lim - precio


# ---------- rivales: cada uno es f(estado) -> (acción, precio) con el mismo estado que el nuestro ----------

def rival_concesion(c, abre):
    """Los 20 rivales "normales" de Para Ana: oferta_k = apertura + (límite − apertura)(1 − (1 − c)^k)."""
    def f(st):
        rol, lim, k = st["rol"], st["limite"], len(st["nuestras"])
        s = 1 if rol == "seller" else -1
        a = lim * abre if rol == "seller" else lim / abre
        mia = a + (lim - a) * (1 - (1 - c) ** k)
        sig = a + (lim - a) * (1 - (1 - c) ** (k + 1))
        su = st["rival"][-1] if st["rival"] else None
        if su is not None and g(rol, lim, su) >= 0 and s * (su - sig) >= 0:
            return ("aceptar", su)
        if su is not None and st["ronda"] >= st["rondas"] - 1 and g(rol, lim, su) >= 0:
            return ("aceptar", su)
        return ("ofrecer", round(mia))
    return f


def rival_ancla(st):
    """Las reglas de Juan: abre ×1,6 / ×0,6, no cede, acepta si llegamos a su ancla, última ronda acepta dentro del límite."""
    rol, lim = st["rol"], st["limite"]
    a = round(lim * 1.6) if rol == "seller" else round(lim * 0.6)
    su = st["rival"][-1] if st["rival"] else None
    if su is not None and g(rol, lim, su) >= g(rol, lim, a):
        return ("aceptar", su)
    if su is not None and st["ronda"] >= st["rondas"] - 1 and g(rol, lim, su) >= 0:
        return ("aceptar", su)
    return ("ofrecer", a)


def rival_tiempo(beta, abre=1.5):
    """Concesión por tiempo (Boulware si beta < 1, cede pronto si beta > 1) y acepta si le damos al menos su siguiente."""
    def f(st):
        rol, lim, T, t = st["rol"], st["limite"], st["rondas"], st["ronda"]
        s = 1 if rol == "seller" else -1
        a = lim * abre if rol == "seller" else lim / abre
        x = (t / max(T - 1, 1)) ** (1 / beta)
        mia = a + (lim + s * 1 - a) * x
        su = st["rival"][-1] if st["rival"] else None
        if su is not None and g(rol, lim, su) >= g(rol, lim, mia):
            return ("aceptar", su)
        if su is not None and t >= T - 1 and g(rol, lim, su) >= 0:
            return ("aceptar", su)
        return ("ofrecer", round(mia))
    return f


def rival_espejo(st):
    """Ojo por ojo: cede lo mismo que cedimos nosotros en el último paso."""
    rol, lim = st["rol"], st["limite"]
    s = 1 if rol == "seller" else -1
    nos, riv = st["nuestras"], st["rival"]
    if not nos:
        return ("ofrecer", round(lim * 1.5 if rol == "seller" else lim / 1.5))
    su = riv[-1] if riv else None
    paso = abs(riv[-1] - riv[-2]) if len(riv) >= 2 else 0
    sig = nos[-1] - s * max(paso, 1)
    if s * (sig - lim) < 0:
        sig = lim + s
    if su is not None and g(rol, lim, su) >= g(rol, lim, sig):
        return ("aceptar", su)
    if su is not None and st["ronda"] >= st["rondas"] - 1 and g(rol, lim, su) >= 0:
        return ("aceptar", su)
    return ("ofrecer", round(sig))


def rival_ingenuo(st):
    """Un agente de lenguaje "amable": cede un 20 % por ronda y acepta en cuanto gana un 10 % de su límite."""
    rol, lim = st["rol"], st["limite"]
    s = 1 if rol == "seller" else -1
    su = st["rival"][-1] if st["rival"] else None
    if su is not None and g(rol, lim, su) >= 0.10 * abs(lim) and st["ronda"] >= 1:
        return ("aceptar", su)
    a = lim * 1.3 if rol == "seller" else lim / 1.3
    mia = a + (lim - a) * (1 - 0.8 ** len(st["nuestras"]))
    if su is not None and st["ronda"] >= st["rondas"] - 1 and g(rol, lim, su) >= 0:
        return ("aceptar", su)
    return ("ofrecer", round(mia))


def rival_duro(st):
    """No se mueve de ×1,8 hasta las dos últimas rondas; entonces acepta cualquier cosa dentro de su límite."""
    rol, lim = st["rol"], st["limite"]
    su = st["rival"][-1] if st["rival"] else None
    if su is not None and st["ronda"] >= st["rondas"] - 2 and g(rol, lim, su) >= 0:
        return ("aceptar", su)
    return ("ofrecer", round(lim * 1.8 if rol == "seller" else lim / 1.8))


def rival_mitad(st):
    """Propone siempre el punto medio entre su última oferta y la nuestra."""
    rol, lim = st["rol"], st["limite"]
    s = 1 if rol == "seller" else -1
    su = st["rival"][-1] if st["rival"] else None
    if not st["nuestras"]:
        return ("ofrecer", round(lim * 1.4 if rol == "seller" else lim / 1.4))
    mid = (st["nuestras"][-1] + (su if su is not None else st["nuestras"][-1])) / 2
    if s * (mid - lim) < 0:
        mid = lim
    if su is not None and g(rol, lim, su) >= g(rol, lim, mid):
        return ("aceptar", su)
    if su is not None and st["ronda"] >= st["rondas"] - 1 and g(rol, lim, su) >= 0:
        return ("aceptar", su)
    return ("ofrecer", round(mid))


RIVALES = {
    "concesion_lenta": rival_concesion(0.15, 1.5),
    "concesion_media": rival_concesion(0.30, 1.5),
    "concesion_rapida": rival_concesion(0.50, 1.6),
    "ancla_firme": rival_ancla,
    "boulware": rival_tiempo(0.3),
    "cede_pronto": rival_tiempo(3.0),
    "espejo": rival_espejo,
    "ingenuo": rival_ingenuo,
    "duro": rival_duro,
    "punto_medio": rival_mitad,
}


# ---------- nuestras candidatas ----------

def nuestra_adaptativa(p):
    return lambda st: duelo.decidir(st, p)[:2]


def nuestra_juan(st):
    return rival_ancla(st)


def nuestra_betty_v1(st):
    """duel_agent.py (versión del viernes), simplificado: abre ×1,6/×0,6, cede 30/25/20/15 % hacia el rival,
    acepta si su precio vale el 94 % de nuestra siguiente, cualquiera dentro del límite tras 5 mensajes o al final."""
    rol, lim = st["rol"], st["limite"]
    s = 1 if rol == "seller" else -1
    nos, su = st["nuestras"], (st["rival"][-1] if st["rival"] else None)
    n = len(nos)
    if not n:
        sig = lim * 1.6 if rol == "seller" else lim * 0.6
    else:
        frac = [0.30, 0.25, 0.20, 0.15][min(n - 1, 3)]
        meta = su if su is not None else lim
        if s * (meta - lim) < 0:
            meta = lim + s * max(lim * 0.03, 1)
        sig = nos[-1] + frac * (meta - nos[-1])
    sig = math.ceil(sig) if s > 0 else math.floor(sig)
    if su is not None and g(rol, lim, su) >= 0:
        if g(rol, lim, su) >= 0.94 * g(rol, lim, sig) or n >= 5 or st["ronda"] >= st["rondas"] - 1:
            return ("aceptar", su)
    return ("ofrecer", sig)


# ---------- el duelo ----------

def escenario(rng):
    coste = rng.uniform(30, 300)
    valor = coste * (rng.uniform(1.05, 2.2) if rng.random() > 0.1 else rng.uniform(0.7, 0.98))
    return round(coste), round(valor)


def jugar(nuestra, rival, rol_nuestro, coste, valor, T, delta, abrimos, memoria=False):
    """Devuelve (nuestra parte, su parte, ronda, ¿trato?)."""
    lim_n = coste if rol_nuestro == "seller" else valor
    rol_r = "buyer" if rol_nuestro == "seller" else "seller"
    lim_r = valor if rol_nuestro == "seller" else coste
    tarta = valor - coste
    st_n = {"rol": rol_nuestro, "limite": lim_n, "rival": [], "nuestras": [], "ronda": 0, "rondas": T,
            "limite_rival": lim_r if memoria else None}
    st_r = {"rol": rol_r, "limite": lim_r, "rival": [], "nuestras": [], "ronda": 0, "rondas": T}
    orden = [(nuestra, st_n, st_r), (rival, st_r, st_n)]
    if not abrimos:
        orden.reverse()
    for t in range(T):
        for f, yo, otro in orden:
            yo["ronda"] = otro["ronda"] = t
            accion, precio = f(yo)
            if accion == "aceptar" and yo["rival"]:
                pr = yo["rival"][-1]
                if tarta <= 0:
                    return (min(0, g(rol_nuestro, lim_n, pr) / abs(tarta or 1)), 0, t, True)
                fn = (delta ** t) * g(rol_nuestro, lim_n, pr) / tarta
                fr = (delta ** t) * g(rol_r, lim_r, pr) / tarta
                return (fn if g(rol_nuestro, lim_n, pr) >= 0 else g(rol_nuestro, lim_n, pr) / tarta, fr, t, True)
            if accion == "aceptar":
                accion, precio = "ofrecer", yo["nuestras"][-1] if yo["nuestras"] else yo["limite"]
            if accion == "esperar" or precio is None:
                continue
            yo["nuestras"].append(precio)
            otro["rival"].append(precio)
    return (0.0, 0.0, T, False)


def torneo(estrategias, n=400, semilla=11, T=8, delta=0.94, memoria=False):
    """Cada estrategia contra cada rival, n escenarios × 2 roles × quién abre. Devuelve tabla."""
    rng = random.Random(semilla)
    escenarios = [escenario(rng) for _ in range(n)]
    tabla = {}
    for nombre, est in estrategias.items():
        fila = {}
        for rn, rv in RIVALES.items():
            partes, tratos, perdidas = [], 0, 0
            for i, (c, v) in enumerate(escenarios):
                for rol in ("seller", "buyer"):
                    fn, fr, t, trato = jugar(est, rv, rol, c, v, T, delta, abrimos=(i % 2 == 0), memoria=memoria)
                    partes.append(fn)
                    tratos += trato
                    perdidas += fn < 0
            fila[rn] = {"parte": round(sum(partes) / len(partes), 3), "tratos": round(tratos / len(partes), 3),
                        "perdidas": perdidas}
        fila["_media"] = round(sum(x["parte"] for x in fila.values()) / len(RIVALES), 3)
        fila["_peor"] = min(x["parte"] for k, x in fila.items() if not k.startswith("_"))
        tabla[nombre] = fila
    return tabla
