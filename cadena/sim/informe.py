"""Informe final con los parámetros elegidos (parametros.json). Semillas fijas: siempre da lo mismo.
    python sim/informe.py      → resultados/resumen.json
"""
import json
import os
import random
import statistics
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from sim import torneo_tienda as T, estrategias as E, duelos as D, mercado as M, repeticion as R  # noqa: E402
from t7 import params  # noqa: E402
from t7.broker import Casamentero, cruce_simple  # noqa: E402

P = params.cargar()
out = {"tienda": {}, "duelos": {}, "mercado": {}}
for perfil in ("abuela", "chato", "desconocido"):
    for lado in ("compra", "venta"):
        fila = {}
        for nombre, est in (("nuestra", E.adaptativo(params.perfil(P, perfil), P)),):
            r = T.robusto(est, perfil, lado, n=800)
            fila[nombre] = {k: r[k] for k in ("nota", "media", "peor", "tratos", "cooloff")} | {
                "por_mundo": {w: m["captura_media"] for w, m in r["por_mundo"].items()}}
        out["tienda"][f"{perfil}/{lado}"] = fila
        print(perfil, lado, {k: v["nota"] for k, v in fila.items()})

# las tres sesiones del calendario: Duelos I (16 rondas, −6 %), Duelos II (16, −8 %), Duelos III (12, −10 %)
for sesion, T_, delta in (("duelos_I", 16, 0.94), ("duelos_II", 16, 0.92), ("duelos_III", 12, 0.90)):
    f = D.torneo({"nuestra": D.nuestra_adaptativa(P)}, n=250, T=T_, delta=delta)["nuestra"]
    out["duelos"][sesion] = {"media": f["_media"], "peor": f["_peor"],
                             "por_rival": {r: x["parte"] for r, x in f.items() if not r.startswith("_")}}
    print("duelos", sesion, f["_media"])
t = D.torneo({"nuestra_con_memoria": D.nuestra_adaptativa(P)}, n=250, memoria=True)
out["duelos"]["memoria_de_escenario"] = t["nuestra_con_memoria"]["_media"]
out["duelos"]["repeticion_reales"] = R.informe({"nuestra": D.nuestra_adaptativa(P)}, R.cargar())
print("duelos reales repetidos", out["duelos"]["repeticion_reales"]["nuestra"]["puntos"], "frente a",
      out["duelos"]["repeticion_reales"]["real"]["puntos"])

for nombre, kw in {"base": {}, "muchos_firmes": {"p_firme": 0.5}, "muy_impacientes": {"p_impaciente": 0.8},
                   "escasez_vendedores": {"n": 8, "n_venta": 4}}.items():
    rng = random.Random(5)
    S = [M.sesion(rng, **kw) for _ in range(300)]
    out["mercado"][nombre] = {
        "puesto_gratuito": round(statistics.mean(M.jugar(g, lambda t_, o: cruce_simple(o)) for g in S), 3),
        "casamentero_inmediato": round(statistics.mean(M.jugar(g, Casamentero(tick_cierre=0).plan) for g in S), 3),
        "casamentero_espera": round(statistics.mean(M.jugar(g, Casamentero(tick_cierre=12, prisa=1).plan) for g in S), 3)}
    print("mercado", nombre, out["mercado"][nombre])

os.makedirs(os.path.join(os.path.dirname(AQUI), "resultados"), exist_ok=True)
with open(os.path.join(os.path.dirname(AQUI), "resultados", "resumen.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
