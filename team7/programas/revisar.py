"""La revisión antes de jugar: comprueba, SOLO LEYENDO, que todo está listo para jugar la cadena.

    python programas/revisar.py             lee el juego, dice qué está bien y qué falta, y escribe menus.borrador.json
    python programas/revisar.py --menus     además, añade a menus.json los vendedores del borrador que falten (lo ya escrito no se toca)

No manda mensajes, no abre conversaciones, no acepta nada y no abre sobres. La clave se lee de BAZAAR_KEY.

Qué mira, en este orden:
    1. el reloj: tick, segundos por tick, si el juego está en pausa
    2. nuestra caja y el modo de caja del día
    3. los valores: que nuestros multiplicadores y las rarezas se leen del juego (conocer el valor antes de comprar)
    4. la calculadora: que el valor que calculamos para cada carta nuestra coincide con el que da el juego
    5. los vendedores: quién hay, quién es nuevo y qué menú se entiende
    6. que no haya un STOP olvidado ni errores recientes

Cada línea empieza por OK, AVISO o FALTA. Con algún FALTA, no se lanza en vivo.
"""
import argparse
import json
import os
import sys
from collections import Counter

PROGRAMAS = os.path.dirname(os.path.abspath(__file__))
AQUI = os.path.dirname(PROGRAMAS)            # team7/: agentes/, sim/, datos/, runs/ y menus.json
sys.path.insert(0, PROGRAMAS)
RUNS = os.path.join(AQUI, "runs")
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(AQUI))  # bazaar_sdk.py vive en la raíz del repo

from agentes import menus as M  # noqa: E402
from agentes import situacion  # noqa: E402
from agentes import valor as V  # noqa: E402

def _json(ruta, por_defecto):
    if not os.path.exists(ruta):
        return por_defecto
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


TOLERANCIA = 0.06            # diferencia admitida entre nuestro valor de una carta y el del juego


def revisar(b, menus_actuales=None, stop=False):
    """Devuelve {"lineas": [(nivel, texto)], "faltas": n, "avisos": n, "borrador": menús propuestos, "dudas": [...]}.
    b = el cliente del juego (o uno de mentira). Nunca lanza: lo que falla se convierte en una línea FALTA."""
    lineas = []

    def di(nivel, texto):
        lineas.append((nivel, texto))

    def lee(nombre, llamada):
        try:
            return llamada()
        except Exception as e:
            di("FALTA", f"{nombre}: no se pudo leer ({type(e).__name__}: {e})")
            return None

    reloj = lee("reloj", b.clock)
    if isinstance(reloj, dict):
        di("AVISO" if reloj.get("paused") else "OK",
           f"reloj: tick {reloj.get('tick')}, {reloj.get('tick_seconds')} s por tick" + (" · EN PAUSA" if reloj.get("paused") else ""))

    me = lee("nuestro estado", b.me)
    cartas, cuenta = [], Counter()
    if isinstance(me, dict):
        activos = [a for a in me.get("assets") or [] if isinstance(a, dict)]
        cartas = [a for a in activos if a.get("kind") == "card" and a.get("ref")]
        cuenta = Counter(a["ref"] for a in cartas)
        sobres = sum(1 for a in activos if a.get("kind") == "pack")
        try:
            plan = situacion.plan({"efectivo": me.get("cash", 0), "cuenta": cuenta,
                                   "tick_segundos": (reloj or {}).get("tick_seconds")})
            di("OK" if plan["modo_caja"] == "holgado" else "AVISO",
               f"caja: {me.get('cash')} P, modo {plan['modo_caja']}, {max(0, plan['libre']):.0f} P libres sobre la reserva")
        except Exception as e:
            di("FALTA", f"plan del día: {type(e).__name__}: {e}")
        di("OK", f"cartas: {len(cartas)} · nivel {me.get('level')}")
        if sobres:
            di("AVISO", f"{sobres} sobre(s) sin abrir: hay que abrirlos antes de comprar")

        catalogo = lee("catálogo", b.catalog)
        avisos = V.configurar(me.get("affinity"), catalogo, cartas)
        if "affinity" not in me:
            di("FALTA", "multiplicadores: el juego no trae 'affinity'; se usan los supuestos, sin comprobar")
        for a in avisos:
            di("FALTA" if "no se entiende" in a or "no tenemos multiplicador" in a else "AVISO", a)
        di("OK", "multiplicadores en uso: " + ", ".join(f"{k} × {v}" for k, v in sorted(V.NUESTROS_MULT.items(), key=lambda x: -x[1])))
        di("OK" if V.RAREZAS else "AVISO", f"rarezas leídas del juego: {len(V.RAREZAS)} cartas")

        # la calculadora frente al juego, carta a carta: lo que perderíamos al dar cada una
        mal, vistas = [], 0
        for a in cartas:
            juego = a.get("your_value", a.get("value"))
            if not isinstance(juego, (int, float)):
                continue
            vistas += 1
            nuestro = V.valor_entregar(cuenta, [a["ref"]])
            entera = V.BASE[V.rareza(a["ref"])] * V.NUESTROS_MULT.get(V.barrio(a["ref"]), 1.0)
            if cuenta[a["ref"]] > 1 and abs(entera - juego) <= TOLERANCIA:
                continue                                         # de una repetida, el juego puede dar la copia entera
            if nuestro is None or abs(nuestro - juego) > TOLERANCIA:
                mal.append(f"{a['ref']} (juego {juego}, nosotros {nuestro if nuestro is None else round(nuestro, 2)})")
        if not vistas:
            di("AVISO", "calculadora: el juego no da el valor de nuestras cartas; no se puede comparar")
        elif mal:
            di("FALTA", f"calculadora: {len(mal)} de {vistas} cartas no coinciden con el juego: " + "; ".join(mal[:6]))
        else:
            di("OK", f"calculadora: las {vistas} cartas coinciden con el valor del juego")
        raras = sorted(r for r in cuenta if not V.conocida(r))
        if raras:
            di("AVISO", "cartas con las que no se opera (barrio o código sin valor conocido): " + ", ".join(raras))

    vendedores = lee("vendedores", b.dealers)
    borrador, dudas = M.del_juego(vendedores, cuenta) if vendedores is not None else ({}, [])
    lista = (vendedores.get("dealers") or vendedores.get("in_play") or vendedores.get("personas") or []) if isinstance(vendedores, dict) else vendedores
    ids = [str(d["id"]) for d in lista if isinstance(d, dict) and d.get("id") is not None] if isinstance(lista, list) else []
    if vendedores is not None:
        di("OK" if ids else "FALTA", "vendedores en el juego: " + (", ".join(ids) or "no se entiende la lista"))
    for v in ids:
        if v in (menus_actuales or {}):
            di("OK", f"{v}: está en menus.json")
        elif v in borrador:
            di("AVISO", f"{v}: no está en menus.json; borrador con {len(borrador[v]['vende'])} cartas que vende y "
                        f"{len(borrador[v]['compra'])} que compra")
        else:
            di("FALTA", f"{v}: no está en menus.json y su menú no se entiende: no se le abrirá nada")
    for d in dudas[:12]:
        di("AVISO", "menú · " + d)
    if not menus_actuales:
        di("FALTA", "no hay menus.json: no se abren conversaciones con vendedores (solo duelos y El Rastro)")

    if stop:
        di("FALTA", "hay un archivo runs/STOP: el Guardia no firmará nada hasta que se borre")
    faltas = sum(1 for n, _ in lineas if n == "FALTA")
    return {"lineas": lineas, "faltas": faltas, "avisos": sum(1 for n, _ in lineas if n == "AVISO"),
            "borrador": borrador, "dudas": dudas}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--menus", action="store_true", help="añadir a menus.json los vendedores del borrador que falten")
    a = ap.parse_args()
    from bazaar_sdk import Bazaar
    if not os.environ.get("BAZAAR_KEY"):
        sys.exit("Falta la variable de entorno BAZAAR_KEY (la clave del equipo). No se escribe en ningún archivo.")
    os.makedirs(RUNS, exist_ok=True)
    b = Bazaar(os.environ.get("BAZAAR_URL", "https://bazaar.causaprima.ai"), os.environ["BAZAAR_KEY"], wait_on_tick=False)
    ruta_menus = os.path.join(AQUI, "menus.json")
    try:
        actuales = _json(ruta_menus, None)
    except (OSError, ValueError) as e:
        actuales = None
        print(f"FALTA  menus.json no se puede leer: {e}")
    r = revisar(b, actuales, stop=os.path.exists(os.path.join(RUNS, "STOP")))
    for nivel, texto in r["lineas"]:
        print(f"{nivel:<6} {texto}")
    if r["borrador"]:
        ruta = os.path.join(AQUI, "menus.borrador.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(r["borrador"], f, ensure_ascii=False, indent=1, sort_keys=True)
        print(f"\nBorrador de menús escrito en {ruta}. Míralo antes de usarlo.")
        nuevos = sorted(set(r["borrador"]) - set(actuales or {}))
        if a.menus and nuevos:                                   # añade los vendedores que faltan; lo ya escrito no se toca
            with open(ruta_menus, "w", encoding="utf-8") as f:
                json.dump(dict(r["borrador"], **(actuales or {})), f, ensure_ascii=False, indent=1, sort_keys=True)
            print("menus.json: añadidos " + ", ".join(nuevos) + ". Vuelve a lanzar la revisión.")
    print(f"\n{'LISTO PARA EL SECO' if not r['faltas'] else 'NO LISTO'}: {r['faltas']} cosas que faltan, {r['avisos']} avisos.")
    print("Siguiente paso: jugar la cadena en seco (no manda ni acepta nada) con el programa que la conecte al juego")
    sys.exit(1 if r["faltas"] else 0)


if __name__ == "__main__":
    main()
