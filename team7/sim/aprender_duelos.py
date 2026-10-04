"""Aprender de los duelos grabados: repite cada duelo real con otros ajustes de la Duelista y propone los mejores.
Sin red y sin azar: mismos datos, misma propuesta. NO cambia ningún ajuste: escribe la propuesta y el equipo decide.

    python sim/aprender_duelos.py           todos los datos/duelos-reales-*.json → resultados/duelos-aprendido.json
    python sim/aprender_duelos.py --rapido  rejilla pequeña (para las pruebas)

Cómo decide:
1. Repetición (sim/repeticion.py): las ofertas que mandó cada rival entran una a una en nuestra estrategia; cuenta lo
   que habríamos ganado aceptando una de ellas, con el decay de su sesión (12 rondas con decay 0,10; 16 con el resto).
   Es un suelo: no cuenta los duelos en que el rival habría aceptado nuestra oferta. Con día de entrega, cada precio
   se pasa a precio efectivo (precio + k × días), como hace duelos.py: un buen precio a un mal día puede restar.
2. Para no aprenderse de memoria unos pocos duelos, los 10 mejores ajustes de la repetición se prueban también contra
   los rivales inventados de sim/duelos.py (12 rondas, −10 %, como Duels III y la final). Solo se propone uno que no
   empeore ahí la media en más de 0,01 ni el peor rival en más de 0,02, y que nunca cierre fuera del límite.
3. Si nada mejora lo actual en al menos 1 %, la propuesta es no cambiar nada.

Además: el perfil de cada rival (cuántos duelos, tratos, si escribe, cuánto cede) — lo que el espía ve de ellos.
"""
import argparse
import glob
import itertools
import json
import os
import statistics
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
from sim import duelos as D, repeticion as R  # noqa: E402
from agentes import duelo, params  # noqa: E402

AJUSTES = ("duelo.apertura_vendedor", "duelo.apertura_comprador", "duelo.dureza_beta", "duelo.cuota_minima")
REJILLA = {"duelo.apertura_vendedor": (1.3, 1.45, 1.6, 1.8, 2.0), "duelo.apertura_comprador": (0.45, 0.5, 0.6, 0.7),
           "duelo.dureza_beta": (0.4, 0.6, 0.8, 1.0), "duelo.cuota_minima": (0.02, 0.05, 0.1, 0.2)}
RAPIDA = {"duelo.apertura_vendedor": (1.6, 2.0), "duelo.apertura_comprador": (0.45, 0.6),
          "duelo.dureza_beta": (0.6,), "duelo.cuota_minima": (0.05,)}
MEJORA_MINIMA = 0.01


def cargar_todos(carpeta=os.path.join(RAIZ, "datos")):
    """Todos los duelos grabados, sin repetir ids (gana la versión con más mensajes)."""
    por_id = {}
    for ruta in sorted(glob.glob(os.path.join(carpeta, "duelos-reales-*.json"))):
        with open(ruta, encoding="utf-8") as f:
            for d in json.load(f).get("duels") or []:
                if d.get("duel") is None or d.get("status") not in ("deal", "no_deal"):
                    continue                                     # solo los terminados
                viejo = por_id.get(d["duel"])
                if viejo is None or len(d.get("messages") or []) >= len(viejo.get("messages") or []):
                    por_id[d["duel"]] = d
    return [por_id[k] for k in sorted(por_id)]


def a_efectivo(d):
    """El duelo con cada precio pasado a precio efectivo (precio + k × días, ver agentes/duelo.py). Sin días, igual."""
    if "days" not in (d.get("issues") or []):
        return d
    k = duelo.k_dias(d.get("role"), d.get("your_days_weight"), d.get("days_meaning"))
    if k is None:
        return d
    msgs = [dict(m, price=duelo.precio_efectivo(m["price"], m.get("days"), k)) if m.get("price") is not None else m
            for m in d.get("messages") or []]
    return dict(d, messages=msgs)


def rondas_de(d):
    return 12 if (d.get("decay_per_round") or 0) >= 0.10 else 16


def repetir_todos(p, duelos):
    """{"puntos", "tratos", "fuera"} de nuestra estrategia con los ajustes p, cada duelo con el decay de su sesión."""
    puntos, tratos, fuera = 0.0, 0, 0
    for d in duelos:
        if not R.sus_precios(d):
            continue                                              # el rival no escribió: no se puede repetir
        T, decay = rondas_de(d), d.get("decay_per_round") or 0.06
        q = dict(p, **{"duelo.rondas": T, "duelo.descuento_ronda": round(1 - decay, 4)})
        R.RONDAS = T
        r = R.repetir(D.nuestra_adaptativa(q), a_efectivo(d))
        puntos += r["puntos"]
        tratos += r["ronda"] is not None
        fuera += r["puntos"] < 0
    R.RONDAS = 16
    return {"puntos": round(puntos, 1), "tratos": tratos, "fuera": fuera}


def inventados(p, n=120):
    q = dict(p, **{"duelo.rondas": 12, "duelo.descuento_ronda": 0.90})
    f = D.torneo({"x": D.nuestra_adaptativa(q)}, n=n, T=12, delta=0.90)["x"]
    return {"media": f["_media"], "peor": f["_peor"]}


def perfiles(duelos):
    """Por rival: duelos, tratos, puntos medios, si escribe, y cuánto cede de su primera a su última oferta."""
    out = {}
    for d in duelos:
        x = out.setdefault(d.get("rival") or "?", {"duelos": 0, "tratos": 0, "puntos": [], "mudo": 0, "cede": []})
        x["duelos"] += 1
        x["tratos"] += d.get("status") == "deal"
        x["puntos"].append(d.get("result") or 0)
        suyas = R.sus_precios(d)
        if not suyas:
            x["mudo"] += 1
        elif len(suyas) > 1 and suyas[0]:
            x["cede"].append(abs(suyas[-1] - suyas[0]) / suyas[0])
    return {r: {"duelos": x["duelos"], "tratos": x["tratos"], "puntos_medios": round(statistics.mean(x["puntos"]), 1),
                "no_escribe": x["mudo"], "cede_media": round(statistics.mean(x["cede"]), 2) if x["cede"] else None}
            for r, x in sorted(out.items(), key=lambda kv: -kv[1]["duelos"])}


def aprender(duelos, p=None, rejilla=REJILLA):
    p = p or params.cargar()
    actual = {k: p[k] for k in AJUSTES}
    base, base_inv = repetir_todos(p, duelos), inventados(p)
    probados = []
    for valores in itertools.product(*(rejilla[k] for k in AJUSTES)):
        ajuste = dict(zip(AJUSTES, valores))
        r = repetir_todos(dict(p, **ajuste), duelos)
        if r["fuera"] == 0:
            probados.append((r["puntos"], ajuste, r))
    probados.sort(key=lambda x: -x[0])
    propuesta = None
    for puntos, ajuste, r in probados[:10]:
        inv = inventados(dict(p, **ajuste))
        if inv["media"] >= base_inv["media"] - 0.01 and inv["peor"] >= base_inv["peor"] - 0.02:
            propuesta = {"ajustes": ajuste, "repeticion": r, "inventados": inv}
            break
    mejora = (propuesta["repeticion"]["puntos"] - base["puntos"]) / max(1.0, abs(base["puntos"])) if propuesta else 0
    if not propuesta or mejora < MEJORA_MINIMA or propuesta["ajustes"] == actual:
        propuesta, decision = None, "no cambiar nada: ningún ajuste mejora lo actual en al menos 1 % sin empeorar con los rivales inventados"
    else:
        cambios = {k: v for k, v in propuesta["ajustes"].items() if v != actual[k]}
        propuesta["hoy_json_ajustes"] = cambios
        decision = (f"proponer {cambios}: +{mejora:.1%} en la repetición "
                    f"({base['puntos']} → {propuesta['repeticion']['puntos']} P)")
    return {"duelos": len(duelos), "repetibles": sum(bool(R.sus_precios(d)) for d in duelos),
            "real": round(sum(d.get("result") or 0 for d in duelos), 1),
            "actual": {"ajustes": actual, "repeticion": base, "inventados": base_inv},
            "propuesta": propuesta, "decision": decision, "rivales": perfiles(duelos)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rapido", action="store_true", help="rejilla pequeña")
    a = ap.parse_args()
    duelos = cargar_todos()
    if not duelos:
        sys.exit("No hay duelos terminados en datos/duelos-reales-*.json (lanza grabador_duelos.py).")
    out = aprender(duelos, rejilla=RAPIDA if a.rapido else REJILLA)
    os.makedirs(os.path.join(RAIZ, "resultados"), exist_ok=True)
    with open(os.path.join(RAIZ, "resultados", "duelos-aprendido.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"{out['duelos']} duelos terminados ({out['repetibles']} con ofertas del rival) · reales {out['real']} P")
    ac = out["actual"]
    print(f"ACTUAL     {ac['ajustes']}\n           repetición {ac['repeticion']['puntos']} P, {ac['repeticion']['tratos']} tratos"
          f" · inventados media {ac['inventados']['media']} peor {ac['inventados']['peor']}")
    if out["propuesta"]:
        pr = out["propuesta"]
        print(f"PROPUESTA  {pr['ajustes']}\n           repetición {pr['repeticion']['puntos']} P, {pr['repeticion']['tratos']} tratos"
              f" · inventados media {pr['inventados']['media']} peor {pr['inventados']['peor']}")
        print(f"           en agentes/hoy.json → \"ajustes\": {json.dumps(pr['hoy_json_ajustes'])}")
    print("DECISIÓN   " + out["decision"])
    print("RIVALES    " + " · ".join(f"{r}: {x['tratos']}/{x['duelos']} tratos, {x['puntos_medios']} P, "
                                     f"{x['no_escribe']} mudos" for r, x in list(out["rivales"].items())[:8]))


if __name__ == "__main__":
    main()
