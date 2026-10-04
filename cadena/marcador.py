"""El marcador: ¿estamos jugando bien? Lee nuestra puntuación del juego (GET /api/me), la compara con la lectura
anterior y avisa si algo va mal. SOLO LEE: no manda, no acepta, no publica nada.

    python marcador.py               una lectura, comparada con la anterior
    python marcador.py --cada 300    una lectura cada 5 minutos (Ctrl + C para parar)
    python marcador.py --historial   enseña las lecturas guardadas, sin llamar al juego

Cada lectura se guarda en runs/marcador.jsonl (sin la clave). Se lanza antes y después de cada sesión en vivo.

Alarmas (en rojo):
    neg_points baja           un trato con otro equipo nos ha hecho perder valor: mirar runs/tratos.jsonl
    score o rank empeoran     algo resta: mirar qué fila ha bajado
    cartas o dinero cambian   sin un programa nuestro en marcha (candados de jugar.py y duelos.py): otro juega con la clave

La clave se lee de BAZAAR_KEY (o de la variable de usuario de Windows). No se escribe en ningún sitio.
"""
import argparse
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(AQUI))                       # el SDK está en la raíz del repositorio
RUNS = os.path.join(AQUI, "runs")
HISTORIAL = os.path.join(RUNS, "marcador.jsonl")

# (campo, etiqueta, qué es mejor: +1 subir, −1 bajar, 0 solo informar)
FILAS = [
    ("score", "Puntuación", +1),
    ("rank", "Puesto", -1),
    ("negotiating", "  Negociar (de 30)", +1),
    ("duel_points", "    duelos", +1),
    ("ladder_points", "    escalera de vendedores", +1),
    ("neg_points", "    tratos con equipos", +1),
    ("market", "  Mercado (de 30)", +1),
    ("bench_efficiency", "    eficiencia del Market Test", +1),
    ("mm_points", "    valor creado en nuestro puesto", +1),
    ("cash", "Dinero", 0),
    ("cartas", "Cartas", 0),
    ("collection_value", "Valor de la colección", 0),
    ("deals", "Tratos hechos", 0),
]
ALARMAS = ("neg_points", "score", "rank")
ROJO, VERDE, GRIS, FIN = "\033[31m", "\033[32m", "\033[90m", "\033[0m"


def _clave():
    k = os.environ.get("BAZAAR_KEY")
    if k or os.name != "nt":
        return k
    try:                                                          # la variable de usuario de Windows, como lanzar-duelos.ps1
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as reg:
            return winreg.QueryValueEx(reg, "BAZAAR_KEY")[0]
    except OSError:
        return None


def foto(me, ahora=None):
    """Lo que se guarda de una lectura de /api/me: la puntuación y poco más (nunca la clave)."""
    s = me.get("score") or {}
    cartas = [a for a in me.get("assets") or [] if isinstance(a, dict) and a.get("kind") == "card"]
    f = {k: s.get(k) for k, _, _ in FILAS if k in s}
    f.update({"tick": me.get("tick"), "cash": me.get("cash"), "cartas": len(cartas),
              "collection_value": me.get("collection_value"), "hora": time.strftime("%H:%M", time.localtime(ahora))})
    return f


def comparar(antes, ahora, nuestro_en_marcha=False):
    """[(etiqueta, valor, cambio, color)] y la lista de alarmas. antes = la lectura anterior (o None)."""
    filas, alarmas = [], []
    for k, etiqueta, mejor in FILAS:
        v = ahora.get(k)
        if v is None:
            continue
        a = (antes or {}).get(k)
        cambio = round(v - a, 3) if isinstance(v, (int, float)) and isinstance(a, (int, float)) else None
        color = ""
        if cambio and mejor:
            color = VERDE if cambio * mejor > 0 else ROJO
        filas.append((etiqueta, v, cambio, color))
        if cambio and mejor and cambio * mejor < 0 and k in ALARMAS:
            alarmas.append(f"{etiqueta.strip()} ha empeorado: {a} → {v}")
    if antes and not nuestro_en_marcha:
        for k in ("cash", "cartas"):
            if isinstance(antes.get(k), (int, float)) and ahora.get(k) != antes.get(k):
                alarmas.append(f"{k} ha cambiado ({antes[k]} → {ahora[k]}) sin un programa nuestro en marcha en este "
                               "ordenador: ¿otro juega con la clave?")
    return filas, alarmas


def _nuestro_en_marcha():
    """¿Hay un programa nuestro jugando en este ordenador? Lo dicen sus candados (jugar.py y duelos.py), y solo si el
    programa que lo tomó sigue vivo: un candado que quedó de un programa cerrado a la fuerza no cuenta."""
    from t7 import candado
    duelos = os.environ.get("TEAM7_CANDADO_DUELOS") or os.path.join(AQUI, "duelos-acepta.lock")
    for ruta in (candado.RUTA, duelos):
        otro = candado.quien_lo_tiene(ruta)
        if otro and candado._vivo(otro.get("pid")):
            return True
    return False


def _anterior():
    if not os.path.exists(HISTORIAL):
        return None
    with open(HISTORIAL, encoding="utf-8") as f:
        lineas = [l for l in f if l.strip()]
    return json.loads(lineas[-1]) if lineas else None


def enseñar(antes, ahora, filas, alarmas):
    desde = f" · comparado con el tick {antes.get('tick')} ({antes.get('hora')})" if antes else " · primera lectura"
    print(f"\nMARCADOR  tick {ahora.get('tick')} ({ahora.get('hora')}){desde}")
    for etiqueta, v, cambio, color in filas:
        txt = f"{cambio:+g}" if cambio else ("=" if cambio == 0 else "")
        print(f"  {etiqueta:<34} {v!s:>9}  {color}{txt}{FIN if color else ''}")
    if alarmas:
        for a in alarmas:
            print(f"{ROJO}ALARMA    {a}{FIN}")
    elif antes:
        print(f"{VERDE}OK        nada ha empeorado{FIN}")


def una_lectura(b):
    ahora = foto(b.me())
    antes = _anterior()
    filas, alarmas = comparar(antes, ahora, _nuestro_en_marcha())
    enseñar(antes, ahora, filas, alarmas)
    os.makedirs(RUNS, exist_ok=True)
    with open(HISTORIAL, "a", encoding="utf-8") as f:
        f.write(json.dumps(ahora, ensure_ascii=False) + "\n")
    return alarmas


def historial():
    if not os.path.exists(HISTORIAL):
        print("Sin lecturas todavía.")
        return
    with open(HISTORIAL, encoding="utf-8") as f:
        for l in f:
            if l.strip():
                x = json.loads(l)
                print(f"tick {x.get('tick')} ({x.get('hora')}): score {x.get('score')} · puesto {x.get('rank')} · "
                      f"duelos {x.get('duel_points')} · escalera {x.get('ladder_points')} · tratos {x.get('neg_points')}"
                      f" · mercado {x.get('market')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cada", type=int, default=0, help="segundos entre lecturas (0 = una sola)")
    ap.add_argument("--historial", action="store_true", help="enseñar las lecturas guardadas, sin llamar al juego")
    a = ap.parse_args()
    if os.name == "nt":
        os.system("")                                             # colores en la consola de Windows
    if a.historial:
        return historial()
    clave = _clave()
    if not clave:
        sys.exit("Falta BAZAAR_KEY (la clave del equipo). No se escribe en ningún archivo.")
    from bazaar_sdk import Bazaar
    b = Bazaar(os.environ.get("BAZAAR_URL", "https://bazaar.causaprima.ai"), clave)
    while True:
        try:
            una_lectura(b)
        except Exception as e:                                    # un corte de red no para el marcador
            print("RED       sin respuesta del juego:", e)
        if not a.cada:
            break
        time.sleep(max(30, a.cada))                               # nunca más de una lectura cada 30 s


if __name__ == "__main__":
    main()
