"""El Grabador de duelos: guarda cada duelo nuestro, ronda a ronda, para aprender de ellos. SOLO LEE: no manda
mensajes, no acepta, no toca nada. Puede correr a la vez que duelos.py (no comparte su candado: no acepta nada).

    python grabador_duelos.py              lee una vez /api/duels (en juego y terminados) y guarda
    python grabador_duelos.py --cada 30    lee cada 30 s (mínimo 15) hasta Ctrl + C

Guarda en datos/duelos-reales-DD-MM.json, con la misma forma que GET /api/duels?done=true ({"duels": [...]}), que es
la que leen sim/repeticion.py y sim/aprender_duelos.py. Un duelo se guarda una vez por id: si vuelve con más rondas
o terminado, se reemplaza (nunca se pierde uno que ya estaba). Lo que ya había en el archivo se conserva.

La clave se lee de BAZAAR_KEY (o de la variable de usuario de Windows). No se escribe en ningún sitio.
"""
import argparse
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(AQUI))                        # el SDK está en la raíz del repositorio
DATOS = os.path.join(AQUI, "datos")
TERMINADOS = ("deal", "no_deal", "expired", "walked", "closed")


def ruta_del_dia(ahora=None):
    return os.path.join(DATOS, time.strftime("duelos-reales-%d-%m.json", time.localtime(ahora)))


def _lista(res):
    if isinstance(res, dict):
        res = res.get("duels") or res.get("items") or []
    return [d for d in res or [] if isinstance(d, dict) and d.get("duel") is not None]


def _avance(d):
    """Cuánto sabemos de un duelo: terminado > más mensajes > más rondas. Se queda la versión con más información."""
    return (d.get("status") in TERMINADOS, len(d.get("messages") or []), d.get("rounds") or 0)


def fusionar(guardados, nuevos):
    """guardados y nuevos = listas de duelos. Devuelve (lista fusionada ordenada por id, ids terminados nuevos)."""
    por_id = {d["duel"]: d for d in guardados}
    recien = []
    for d in nuevos:
        viejo = por_id.get(d["duel"])
        if viejo is None or _avance(d) >= _avance(viejo):
            if d.get("status") in TERMINADOS and (viejo is None or viejo.get("status") not in TERMINADOS):
                recien.append(d["duel"])
            por_id[d["duel"]] = d
    return [por_id[k] for k in sorted(por_id)], recien


def leer_archivo(ruta):
    try:
        with open(ruta, encoding="utf-8") as f:
            return _lista(json.load(f))
    except (OSError, ValueError):
        return []


def guardar(ruta, duelos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"duels": duelos}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ruta)                                         # nunca se queda un archivo a medias


def resumen(d):
    lim, precio, res = d.get("your_limit"), d.get("price"), d.get("result")
    dias = f" · día {d.get('days')}" if d.get("days") is not None else ""
    return (f"duelo {d['duel']} · sesión {d.get('session')} · {d.get('role')} contra {d.get('rival')} · límite {lim} · "
            f"{d.get('status')}" + (f" a {precio}{dias} · {res} puntos" if d.get("status") == "deal" else "")
            + f" · {d.get('rounds')} rondas")


def una_pasada(b, ruta=None):
    ruta = ruta or ruta_del_dia()
    vistos = []
    for terminados in (True, False):                              # los terminados y los que están en juego
        try:
            vistos += _lista(b.duels(done=terminados))
        except Exception as e:                                    # un fallo de red no pierde lo guardado
            print("RED          /api/duels" + ("?done=true" if terminados else "") + ":", e)
    todos, recien = fusionar(leer_archivo(ruta), vistos)
    if vistos:
        guardar(ruta, todos)
    for d in todos:
        if d["duel"] in recien:
            print("GRABADO      " + resumen(d))
    en_juego = sum(d.get("status") not in TERMINADOS for d in todos)
    print(f"{time.strftime('%H:%M:%S')}  {len(todos)} duelos en {os.path.basename(ruta)} · {len(recien)} terminados nuevos"
          f" · {en_juego} en juego")
    return recien


def _clave():
    k = os.environ.get("BAZAAR_KEY")
    if k or os.name != "nt":
        return k
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as reg:
            return winreg.QueryValueEx(reg, "BAZAAR_KEY")[0]
    except OSError:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cada", type=int, default=0, help="segundos entre lecturas (0 = una sola; mínimo 15)")
    a = ap.parse_args()
    clave = _clave()
    if not clave:
        sys.exit("Falta BAZAAR_KEY (la clave del equipo). No se escribe en ningún archivo.")
    from bazaar_sdk import Bazaar
    b = Bazaar(os.environ.get("BAZAAR_URL", "https://bazaar.causaprima.ai"), clave, wait_on_tick=False)
    while True:
        una_pasada(b)
        if not a.cada:
            break
        time.sleep(max(15, a.cada))


if __name__ == "__main__":
    main()
