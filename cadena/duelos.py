"""La Duelista en vivo: el programa que juega la cadena SOLO en los duelos. Lee /api/duels, llama a cadena.tick()
y, si el Guardia firma un duelo, lo acepta o manda el precio (y el día, en los de dos temas).

    python duelos.py                mira y escribe lo que haría. NO manda ni acepta nada (modo seco).
    python duelos.py --live         juega de verdad. Solo desde el ordenador que tiene la clave, y un solo proceso.
    python duelos.py --ticks 3      para tras 3 ticks (para la primera prueba en seco)

Campos del duelo real (confirmados dos veces hoy: contra un duelo en vivo del equipo, y contra el PDF oficial de
Causa Prima "Duels: how they work"): el id es d["duel"], no d["id"]; la ronda es d["rounds"], no d["round"]; no hay
"max_rounds" (se deriva de d["deadline_tick"] menos el tick actual); rival_offer es un objeto {"price": ...} o None
(d.get("rival_offer") puede venir también como número suelto, se admite igual); el peso por día es
d["your_days_weight"]; d["issues"] trae ["price"] o ["price", "days"].

Los duelos tienen su propia cuota de aceptación por tick, aparte de la tienda y El Rastro (PDF oficial: "duel
messages and accepts have their own limits: they never block your trading") — por eso este programa es independiente
de rastro.py y no comparte su candado. Pero SÍ hay que evitar que dos programas jueguen los MISMOS duelos a la vez
(se pisarían el uno al otro): no lances esto a la vez que play.py duel con la misma clave. Antes de lanzar en vivo,
para el otro.

Parar todo: crear el archivo runs/STOP (o Ctrl + C). El Guardia deja de firmar duelos en el tick siguiente.
La clave se lee de la variable de entorno BAZAAR_KEY. No se escribe en ningún archivo ni en el diario.
"""
import argparse
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(AQUI))  # bazaar_sdk.py vive en la raíz del repo

from t7 import cadena, candado  # noqa: E402

for _salida in (sys.stdout, sys.stderr):     # una consola de Windows (cp1252) no sabe escribir "→": que no pare el programa
    if hasattr(_salida, "reconfigure"):
        _salida.reconfigure(errors="replace")

RUNS = os.path.join(AQUI, "runs")
# candado propio: no comparte cupo con rastro.py (cada uno tiene su cuota en el juego), pero sí protege contra
# dos instancias de duelos.py a la vez.
CANDADO = os.environ.get("TEAM7_CANDADO_DUELOS") or os.path.join(RUNS, "..", "duelos-acepta.lock")


def _linea(nombre, d):
    """Una línea en un archivo de runs/. Apuntar nunca puede tirar el programa."""
    try:
        os.makedirs(RUNS, exist_ok=True)
        with open(os.path.join(RUNS, nombre), "a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False, default=str) + "\n")
    except OSError as e:
        print("ERROR        no se pudo escribir en", nombre, e)


def _precio(x):
    """El precio de una oferta del rival, sea un número suelto o un objeto {"price": ...} (las dos formas vistas)."""
    if isinstance(x, dict):
        x = x.get("price", x.get("cash"))
    return x if isinstance(x, (int, float)) else None


def leer(b, est, tick):
    """lectura["duelos"] con los nombres que espera cadena.tick(), traducidos desde el duelo real del juego."""
    lectura = {"tick": tick, "duelos": []}
    try:
        res = b.duels()
    except Exception as e:                                       # si los duelos no se pueden leer, se reintenta el tick siguiente
        _linea("errores.jsonl", {"tick": tick, "duelos": str(e)})
        return lectura
    duelos = res.get("duels", []) if isinstance(res, dict) else res
    for d in duelos if isinstance(duelos, list) else []:
        if not est.get("crudo"):
            est["crudo"] = True
            _linea("crudo.jsonl", {"crudo": d})                   # el primer duelo tal cual lo manda el juego
        if not isinstance(d, dict) or d.get("duel") is None:
            continue
        rol, limite = str(d.get("role", "")).lower(), d.get("your_limit")
        if rol not in ("seller", "buyer") or not isinstance(limite, (int, float)):
            continue                                              # no se juega lo que no se entiende
        msgs = d.get("messages") or []                            # el historial real, no lo que recuerde este proceso:
        nuestras = [m["price"] for m in msgs if m.get("from") == "you" and m.get("price") is not None]
        rival = [m["price"] for m in msgs if m.get("from") != "you" and m.get("price") is not None]
        rival_paquetes = [(m["price"], m["days"]) for m in msgs if m.get("from") != "you"
                          and m.get("price") is not None and isinstance(m.get("days"), int)]
        vigente = _precio(d.get("rival_offer"))
        if vigente is not None and (not rival or rival[-1] != vigente):
            rival.append(vigente)
        plazo, ronda = d.get("deadline_tick"), d.get("rounds", len(nuestras))
        restantes = plazo - tick if isinstance(plazo, (int, float)) and isinstance(tick, (int, float)) else None
        esc = next((d[k] for k in ("scenario", "scenario_id", "scenario_ref", "case", "item")
                    if d.get(k) is not None and not isinstance(d[k], (dict, list))), None)
        # el descuento por ronda lo dice el propio duelo: 0,06 en Duelos I y 0,08 en Duelos II (calendario del
        # juego). Se pasa tal cual en vez de suponerlo: marca cuándo deja de compensar seguir hablando.
        decay = d.get("decay_per_round")
        descuento = 1 - decay if isinstance(decay, (int, float)) and 0 <= decay < 1 else None
        lectura["duelos"].append({"id": d["duel"], "rol": rol, "limite": limite, "rival": rival, "nuestras": nuestras,
                                  "ronda": ronda, "rondas": ronda + max(1, restantes) if restantes is not None else None,
                                  "texto": d.get("rival_text") or d.get("last_message") or "",
                                  "ticks_restantes": restantes, "escenario": esc,
                                  "dias": "days" in (d.get("issues") or []), "pesos_dias": d.get("your_days_weight"),
                                  "rival_paquetes": rival_paquetes, "descuento": descuento})
    return lectura


def aplicar(b, acciones, vivo):
    """Manda los mensajes de duelo y, si el Guardia firmó, acepta. En seco solo lo escribe (ya lo hace el diario)."""
    for m in acciones["mensajes"]:
        if m.get("destino") != "duelo" or not vivo:
            continue
        try:
            b.duel_say(m["id"], m["texto"], price=m["precio"], days=m.get("dias"))
        except Exception as e:
            _linea("errores.jsonl", {"mensaje": m, "error": str(e)})
    f = acciones.get("firma_duelo")
    if f and vivo:
        try:
            b.duel_accept(f["id"])
        except Exception as e:                                    # nunca se repite a ciegas: se relee en el tick siguiente
            _linea("errores.jsonl", {"firma_duelo": f, "error": str(e)})


def un_tick(b, est, mem, tick, vivo, stop):
    """Un tick de duelos. Un fallo aquí no tira el programa: se apunta y se espera al tick siguiente."""
    try:
        lectura = leer(b, est, tick)
        acciones = cadena.tick(lectura, mem, stop=stop)
        for linea in acciones["diario"]:
            print(linea)
            _linea("diario.jsonl", {"linea": linea, "vivo": vivo})
        aplicar(b, acciones, vivo)
        return True
    except Exception as e:
        print("ERROR       ", f"{type(e).__name__}: {e}")
        _linea("errores.jsonl", {"tick": tick, "error": f"{type(e).__name__}: {e}"})
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--live", action="store_true", help="jugar de verdad (sin esto, solo mira)")
    ap.add_argument("--ticks", type=int, default=0, help="parar tras N ticks (0 = sin fin)")
    a = ap.parse_args()
    from bazaar_sdk import Bazaar
    if not os.environ.get("BAZAAR_KEY"):
        sys.exit("Falta la variable de entorno BAZAAR_KEY (la clave del equipo). No se escribe en ningún archivo.")
    os.makedirs(RUNS, exist_ok=True)
    b = Bazaar(os.environ.get("BAZAAR_URL", "https://bazaar.causaprima.ai"), os.environ["BAZAAR_KEY"], wait_on_tick=False)
    est = {}
    mem = cadena.Memoria()
    print("EN VIVO" if a.live else "EN SECO: no se manda ni se acepta nada")
    if a.live:
        ok, motivo = candado.tomar(CANDADO, "duelos.py")
        if not ok:
            sys.exit("NO SE LANZA   " + motivo)
    try:
        hechos, ultimo = 0, None
        while not a.ticks or hechos < a.ticks:
            try:                                                  # un corte de red no tira el programa: espera y sigue
                reloj = b.clock()
            except Exception as e:
                print("RED          sin respuesta del juego, se reintenta:", e)
                time.sleep(2.0)
                continue
            tick = reloj.get("tick")
            if reloj.get("paused") or tick == ultimo:
                time.sleep(min(2.0, max(0.2, float(reloj.get("next_tick_in") or 1.0))))
                continue
            ultimo, hechos = tick, hechos + 1
            un_tick(b, est, mem, tick, a.live, os.path.exists(os.path.join(RUNS, "STOP")))
    finally:
        if a.live:
            candado.soltar(CANDADO)


if __name__ == "__main__":
    main()
