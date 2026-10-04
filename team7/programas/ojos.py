"""Los Ojos en vivo: cada 12 segundos lo ven todo, lo validan con la Contable y hacen la propuesta (no aceptan nada).

    python programas/ojos.py                 sin parar: una mirada cada 12 segundos
    python programas/ojos.py --ticks 1       una sola mirada
    python programas/ojos.py --segundos 30   una mirada cada 30 segundos

Cada mirada escribe en pantalla su propuesta (o por qué no hay) y las oportunidades; ojos.json se reescribe cada vez.

Solo lee (GET /api/clock, /api/me, /api/feed, /api/me/offers y el tablón de El Rastro): no abre conversaciones, no
manda mensajes y no acepta nada. Por eso no lleva candado ni modo --live, y puede estar en marcha a la vez que
duelos.py o jugar.py. No pasa por el Escudo ni por el Guardia.

Escribe en runs/: ojos.json (la última vista, la lee la skill /ojos) y ojos.jsonl (una línea por mirada).
Parar: crear el archivo runs/STOP (o Ctrl + C). La clave se lee de BAZAAR_KEY y nunca se escribe: /api/me se tapa.
"""
import argparse
import json
import os
import sys
import time

PROGRAMAS = os.path.dirname(os.path.abspath(__file__))
AQUI = os.path.dirname(PROGRAMAS)            # team7/: agentes/, sim/, datos/, runs/ y menus.json
sys.path.insert(0, PROGRAMAS)
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(AQUI))  # bazaar_sdk.py vive en la raíz del repo

from agentes import ojos, params  # noqa: E402
from agentes import valor as V  # noqa: E402

for _salida in (sys.stdout, sys.stderr):     # una consola de Windows (cp1252) no sabe escribir "→": que no pare el programa
    if hasattr(_salida, "reconfigure"):
        _salida.reconfigure(errors="replace")

RUNS = os.path.join(AQUI, "runs")
ULTIMA = os.path.join(RUNS, "ojos.json")


class Memoria:
    """Lo que los Ojos recuerdan entre miradas: los avisos ya dados (sobrevive a un reinicio, en ojos.json)."""

    def __init__(self, vistos=None):
        self.vistos = vistos or {}


def _guardar(vista, tick, mem):
    """La última vista en ojos.json y una línea en ojos.jsonl. Apuntar nunca puede tirar el programa."""
    try:
        os.makedirs(RUNS, exist_ok=True)
        foto = {"tick": tick, "hora": time.strftime("%Y-%m-%d %H:%M:%S"), "vista": vista, "vistos": mem.vistos}
        with open(ULTIMA + ".tmp", "w", encoding="utf-8") as f:
            json.dump(foto, f, ensure_ascii=False, indent=1, default=str)
        os.replace(ULTIMA + ".tmp", ULTIMA)
        with open(os.path.join(RUNS, "ojos.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"tick": tick, "hora": foto["hora"], "vista": vista}, ensure_ascii=False, default=str) + "\n")
    except OSError as e:
        print("ERROR        no se pudo escribir en runs/:", e)


def _recordar():
    try:
        with open(ULTIMA, encoding="utf-8") as f:
            return Memoria(json.load(f).get("vistos"))
    except (OSError, ValueError):
        return Memoria()


def una_mirada(b, mem, tick):
    """Una mirada. Un fallo aquí no tira el programa: se apunta y se espera al tick siguiente."""
    try:
        lectura = dict(ojos.leer(b), tick=tick)
        cartas = [a for a in ((lectura.get("me") or {}).get("assets") or []) if isinstance(a, dict) and a.get("kind") == "card"]
        if cartas:                                                # la Contable cuenta con el your_value del juego (como jugar.py)
            V.configurar(cartas=cartas)
            V.valores_del_juego(cartas=cartas)
            est = ojos.estado(lectura.get("me"))                  # lo que una copia más nos suma, según el juego,
            comprar, _ = ojos.oportunidades(ojos._lista(lectura.get("tablon")), est)   # para las cartas que se proponen comprar
            for carta in sorted({c["carta"] for c in comprar})[:5]:
                if carta not in V.VALOR_RECIBIR:
                    try:
                        V.valores_del_juego(recibir={carta: b.value(carta)})
                    except Exception:
                        pass
        lineas = []
        vista = ojos.mirar(lectura, mem, lambda quien, texto: lineas.append(f"{quien:<10} {texto}"), params.cargar())
        hora = time.strftime("%H:%M:%S")                          # cada mirada: su propuesta y sus oportunidades
        print(f"---- {hora} · tick {tick} " + "-" * 60)
        for linea in lineas:
            print(f"{linea}")
        if not vista["propuestas"] and not vista["descartadas"]:
            print(f"{'PROPUESTA':<10} ninguna: no hay oportunidades en las ofertas de ahora")
        _guardar(vista, tick, mem)
        return vista
    except Exception as e:
        print("ERROR       ", f"{type(e).__name__}: {e}")
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ticks", type=int, default=0, help="parar tras N miradas (0 = sin fin)")
    ap.add_argument("--segundos", type=float, default=12, help="mirar cada N segundos")
    a = ap.parse_args()
    from bazaar_sdk import Bazaar
    if not os.environ.get("BAZAAR_KEY"):
        sys.exit("Falta la variable de entorno BAZAAR_KEY (la clave del equipo). No se escribe en ningún archivo.")
    b = Bazaar(os.environ.get("BAZAAR_URL", "https://bazaar.causaprima.ai"), os.environ["BAZAAR_KEY"], wait_on_tick=False)
    mem = _recordar()
    print("OJOS: ven, validan con la Contable y proponen; no mandan ni aceptan nada")
    hechas, empezo = 0, time.monotonic()
    while not a.ticks or hechas < a.ticks:
        if hechas:                                                # cada N segundos justos: se descuenta lo que tardó la mirada
            time.sleep(max(1.0, a.segundos - (time.monotonic() - empezo)))
            empezo = time.monotonic()
        if os.path.exists(os.path.join(RUNS, "STOP")):
            print("STOP         runs/STOP existe: los Ojos se cierran")
            break
        try:                                                      # un corte de red no tira el programa: espera y sigue
            reloj = b.clock()
        except Exception as e:
            print("RED          sin respuesta del juego, se reintenta:", e)
            time.sleep(2.0)
            continue
        hechas += 1
        if reloj.get("paused"):                                   # juego en pausa: no hay nada nuevo que ver
            continue
        una_mirada(b, mem, reloj.get("tick"))


if __name__ == "__main__":
    main()
