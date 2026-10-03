"""Lee parametros.json y recorta cada valor a su rango. Un valor fuera de rango se avisa, no se acepta."""
import json
import os

RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "parametros.json")


def cargar(ruta=RUTA, cambios=None):
    """Devuelve {nombre: valor}. `cambios` permite probar otros valores sin tocar el archivo (lo usa el simulador)."""
    with open(ruta, encoding="utf-8") as f:
        crudo = json.load(f)
    p, avisos = {}, []
    for nombre, d in crudo.items():
        if nombre.startswith("_"):
            continue
        v = (cambios or {}).get(nombre, d["valor"])
        if v < d["min"] or v > d["max"]:
            avisos.append(f"{nombre}={v} fuera de [{d['min']}, {d['max']}]: se usa el límite")
            v = min(max(v, d["min"]), d["max"])
        p[nombre] = v
    p["_avisos"] = avisos
    return p


def perfil(p, vendedor):
    """Los ajustes de tienda de un vendedor; uno desconocido usa los prudentes."""
    clave = vendedor if f"tienda.{vendedor}.apertura_compra" in p else "desconocido"
    pref = f"tienda.{clave}."
    return {k[len(pref):]: v for k, v in p.items() if k.startswith(pref)} | {"perfil": clave}
