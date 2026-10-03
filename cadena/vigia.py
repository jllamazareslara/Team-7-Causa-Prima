"""El vigía: mira el juego y avisa de lo nuevo, con lo que proponemos hacer.

    python vigia.py               una pasada
    python vigia.py --cada 60     sin parar: una pasada cada 60 segundos, con un pitido cuando hay novedades

Solo lee (siete lecturas por pasada). No abre conversaciones, no manda mensajes y no acepta nada: puede estar en marcha
a la vez que el director. Novedades que vigila: ritmo y límites del juego, calendario (duelos, Market Test, barrios,
vendedores), niveles, vendedores, barrios nuevos, mercados abiertos, y lo nuestro (efectivo, nivel, sobres, puesto).

Escribe en runs/: vigia.json (la última foto), novedades.jsonl (cada novedad con su propuesta) y vigia-crudo.json
(las respuestas del juego tal cual, sin nuestros datos ni ninguna clave).

La clave se toma de la variable BAZAAR_KEY o, si no está, de bazaar-kit/.env. No se escribe en ningún archivo.
"""
import argparse
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(os.path.dirname(AQUI), "bazaar-kit")
sys.path.insert(0, AQUI)
sys.path.insert(0, KIT)

from t7 import novedades, params  # noqa: E402

for _salida in (sys.stdout, sys.stderr):     # una consola de Windows (cp1252) no sabe escribir "→": que no pare el programa
    if hasattr(_salida, "reconfigure"):
        _salida.reconfigure(errors="replace")

RUNS = os.path.join(AQUI, "runs")
LECTURAS = ("clock", "schedule", "levels", "dealers", "catalog", "venues", "me")


def credenciales():
    """(url, clave) de las variables de entorno o de bazaar-kit/.env."""
    env = {}
    ruta = os.path.join(KIT, ".env")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                if "=" in linea and not linea.lstrip().startswith("#"):
                    k, v = linea.strip().split("=", 1)
                    env[k.strip()] = v.strip()
    return (os.environ.get("BAZAAR_URL") or env.get("BAZAAR_URL") or "https://bazaar.causaprima.ai",
            os.environ.get("BAZAAR_KEY") or env.get("BAZAAR_KEY"))


def leer(b, pausa=0.3):
    """Las siete lecturas. Una que falla queda en None y no estropea las demás."""
    out, errores = {}, []
    for nombre in LECTURAS:
        try:
            out[nombre] = getattr(b, nombre)()
        except Exception as e:
            out[nombre] = None
            errores.append(f"{nombre}: {e}")
        time.sleep(pausa)                    # despacio: la clave comparte el límite de peticiones con el director
    return out, errores


def pasada(b, runs=None, pausa=0.3):
    """Una pasada completa: lee, compara con la foto anterior, apunta y devuelve (novedades, texto)."""
    runs = runs or RUNS
    os.makedirs(runs, exist_ok=True)
    ruta = os.path.join(runs, "vigia.json")
    antes = None
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            antes = json.load(f)
    lecturas, errores = leer(b, pausa)
    ahora = novedades.foto(lecturas)
    for k, v in (antes or {}).items():       # lo que hoy no se pudo leer se queda como estaba
        if ahora.get(k) is None:
            ahora[k] = v
    nov = novedades.comparar(antes, ahora)
    ctx = {"afinidad": (ahora.get("me") or {}).get("afinidad"), "p": params.cargar()}
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(ahora, f, ensure_ascii=False, indent=1, default=str)
    with open(os.path.join(runs, "vigia-crudo.json"), "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in lecturas.items() if k != "me"}, f, ensure_ascii=False, indent=1, default=str)
    hora = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join(runs, "novedades.jsonl"), "a", encoding="utf-8") as f:
        for n in nov:
            f.write(json.dumps({"hora": hora, "tick": (ahora.get("reloj") or {}).get("tick"), **n,
                                "propuesta": novedades.consejo(n, ctx)}, ensure_ascii=False, default=str) + "\n")
    texto = novedades.informe(nov, ctx)
    if errores:
        texto += ("\n" if texto else "") + "\n".join("SIN LEER     " + e for e in errores)
    return nov, texto


def pitido():
    try:
        import winsound
        winsound.MessageBeep()
    except Exception:
        print("\a", end="")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cada", type=int, default=0, help="segundos entre pasadas (0 = una sola pasada)")
    a = ap.parse_args()
    url, clave = credenciales()
    if not clave:
        sys.exit("Falta la clave del equipo: variable BAZAAR_KEY o bazaar-kit/.env.")
    from bazaar_sdk import Bazaar
    b = Bazaar(url, clave, wait_on_tick=False)
    while True:
        try:
            nov, texto = pasada(b)
            hora = time.strftime("%H:%M:%S")
            if texto:
                print(f"--- {hora} ---\n{texto}")
            else:
                print(f"{hora}  sin novedades")
            if nov and not (len(nov) == 1 and nov[0]["tipo"] == "inicio"):
                pitido()
        except Exception as e:               # un corte de red no para el vigía
            print("ERROR       ", f"{type(e).__name__}: {e}")
        if not a.cada:
            break
        time.sleep(max(15, a.cada))


if __name__ == "__main__":
    main()
