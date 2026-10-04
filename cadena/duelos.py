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

from t7 import cadena, candado, duelo, params, situacion  # noqa: E402

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


_HOY_BUENO = []
_ULTIMOS = []          # los últimos ajustes leídos bien, por si un archivo se está guardando justo cuando se lee


def ajustes(hoy=None):
    """Los ajustes de la Duelista: parametros.json con lo que diga hoy.json encima (su bloque "duelo" y los
    "ajustes" que empiezan por "duelo."). Se relee en cada tick: cambiar hoy.json cambia el duelo sin relanzar.
    Si un archivo no se puede leer (se está guardando justo entonces, o está roto), se sigue con lo último que se
    leyó bien y se avisa: editar los ajustes en mitad de un duelo no puede parar el programa."""
    aviso = None
    try:
        hoy = situacion.leer_hoy() if hoy is None else hoy
        if not isinstance(hoy, dict):
            raise ValueError("hoy.json no es un objeto")
        _HOY_BUENO[:] = [hoy]
    except (OSError, ValueError, AttributeError) as e:           # hoy.json a medio guardar: el último que se leyó bien
        hoy = _HOY_BUENO[0] if _HOY_BUENO else {}
        de_donde = "el último leído" if _HOY_BUENO else "parametros.json"
        aviso = f"hoy.json no se puede leer ({type(e).__name__}): se sigue con {de_donde}"
    de_hoy = hoy.get("ajustes") if isinstance(hoy.get("ajustes"), dict) else {}
    cambios = {k: v for k, v in de_hoy.items() if isinstance(k, str) and k.startswith("duelo.") and _num(v)}
    bloque = hoy.get("duelo") if isinstance(hoy.get("duelo"), dict) else {}
    for corto in ("rondas", "descuento_ronda"):
        if _num(bloque.get(corto)) and bloque.get(corto):
            cambios["duelo." + corto] = bloque[corto]
    try:
        p = params.cargar(cambios=cambios)
        _ULTIMOS[:] = [p]
    except (OSError, ValueError, KeyError, TypeError) as e:      # parametros.json a medio guardar: los últimos buenos
        if not _ULTIMOS:
            raise
        p = dict(_ULTIMOS[0])
        aviso = f"parametros.json no se puede leer ({type(e).__name__}): se sigue con los últimos ajustes buenos"
    if aviso:
        p["_avisos"] = list(p.get("_avisos") or []) + [aviso]
    return p


def _mensajes(d, k, lado):
    """[[tick, efectivo, precio, días], ...] de un lado ("you" o el rival), solo los mensajes que llevan precio."""
    out = []
    for m in d.get("messages") or []:
        if not isinstance(m, dict) or (m.get("from") == "you") != (lado == "you"):
            continue
        if _num(m.get("price")) and m["price"] > 0:
            dias = m.get("days") if _num(m.get("days")) and 0 <= m["days"] <= 10 else None
            if k is not None and dias is None:
                continue                                          # con día en juego, un precio sin día no se puede valorar
            out.append([m.get("tick") if _num(m.get("tick")) else 0,
                        duelo.precio_efectivo(m["price"], dias, k), m["price"], dias])
    return out


def estado_por_ticks(d, k, tick, est):
    """El estado que usa la Duelista por ticks (st["x"], ver t7/duelo.py): mensajes de cada lado, oferta del rival
    que se aceptaría ahora, ticks que quedan y ticks desde que vimos el duelo."""
    msgs = [m for m in d.get("messages") or [] if isinstance(m, dict)]
    nos, riv = _mensajes(d, k, "you"), _mensajes(d, k, "rival")
    ro, vigente = d.get("rival_offer"), None
    pr = _precio(ro)
    if _num(pr) and pr > 0:
        dias = ro.get("days") if isinstance(ro, dict) and _num(ro.get("days")) and 0 <= ro["days"] <= 10 else None
        if k is None or dias is not None:                      # con día en juego, una oferta sin día no se puede valorar
            vigente = [duelo.precio_efectivo(pr, dias, k), pr, dias]
    plazo = d.get("deadline_tick") if _num(d.get("deadline_tick")) else None
    vistos = est.setdefault("visto", {})
    primero = vistos.setdefault(d["duel"], min([tick] + [m[0] for m in nos + riv if m[0]]) if isinstance(tick, (int, float)) else 0)
    return {"tick": tick, "quedan": plazo - tick if plazo is not None and _num(tick) else None,
            "edad": tick - primero if isinstance(tick, (int, float)) else 0, "turno": 0,
            "n_nos": sum(1 for m in msgs if m.get("from") == "you"), "n_riv": sum(1 for m in msgs if m.get("from") != "you"),
            "nos": nos, "riv": riv, "vigente": vigente, "dos": "days" in (d.get("issues") or []), "k": k,
            "plazo": plazo}


def repartir_turnos(duelos):
    """El juego deja una aceptación por equipo y tick: los duelos que acaban en el mismo tick cierran en ticks
    distintos. Turno 0 = el último en cerrar: el rival que ha mejorado su oferta más recientemente (el que más
    puede dar todavía). Los demás cierran uno, dos y tres ticks antes."""
    por_plazo = {}
    for d in duelos:
        por_plazo.setdefault(d["x"].get("plazo"), []).append(d)
    for grupo in por_plazo.values():
        def ultima_mejora(d):
            mejor, t = None, -1
            for m in d["x"]["riv"]:
                g = duelo.ganancia(d["rol"], d["limite"], m[1])
                if mejor is None or g > mejor + 0.5:
                    mejor, t = g, m[0]
            return t
        for i, d in enumerate(sorted(grupo, key=lambda d: (-ultima_mejora(d), str(d["id"])))):
            d["x"]["turno"] = i
            d["x"]["solo"] = len(grupo) == 1 and len(duelos) == 1    # nadie más puede necesitar la última aceptación


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) < 1e12


def _traducir(d, tick, est):
    """Un duelo del juego con los nombres que espera cadena.tick(). None si no se entiende (no se juega)."""
    if not isinstance(d, dict) or not isinstance(d.get("duel"), (int, str)) or isinstance(d.get("duel"), bool):
        return None
    rol, limite = str(d.get("role", "")).lower(), d.get("your_limit")
    if rol not in ("seller", "buyer") or not _num(limite) or limite <= 0:
        return None                                               # no se juega lo que no se entiende
    temas = [t for t in d["issues"] if isinstance(t, str)] if isinstance(d.get("issues"), list) else []
    if "days" not in temas and _num(d.get("your_days_weight")):   # trae peso por día: hay día, diga lo que diga issues
        temas = temas + ["days"]
    # con día de entrega, cada precio pasa a precio efectivo (precio + k × días): ver t7/duelo.py
    k = duelo.k_dias(rol, d.get("your_days_weight"), d.get("days_meaning")) if "days" in temas else None
    if "days" in temas and k is None:
        return None                                               # hay día y no sabemos lo que nos cuesta: no se juega
    msgs = [m for m in d.get("messages") or [] if isinstance(m, dict)] if isinstance(d.get("messages"), list) else []
    d = dict(d, messages=msgs, issues=temas)
    nos, riv = _mensajes(d, k, "you"), _mensajes(d, k, "rival")   # el historial real, no lo que recuerde este proceso
    nuestras, rival = [m[1] for m in nos], [m[1] for m in riv]
    rival_paquetes = [(m[2], int(m[3])) for m in riv if m[3] is not None]
    x = estado_por_ticks(d, k, tick, est)
    if x["vigente"] is not None and (not rival or rival[-1] != x["vigente"][0]):
        rival.append(x["vigente"][0])
    plazo = d.get("deadline_tick") if _num(d.get("deadline_tick")) else None
    ronda = d.get("rounds") if _num(d.get("rounds")) else len(nuestras)
    restantes = plazo - tick if plazo is not None and _num(tick) else None
    # "item" NO es el escenario: el mismo objeto sale con límites distintos en cada duelo (El Tren Fantasma:
    # coste 83 en uno, valor 114 con un rival que pedía 73 en otro). Solo vale un identificador de escenario real.
    esc = next((d[c] for c in ("scenario", "scenario_id", "scenario_ref", "case")
                if d.get(c) is not None and not isinstance(d[c], (dict, list))), None)
    texto = d.get("rival_text") or d.get("last_message") or ""
    return {"id": d["duel"], "rol": rol, "limite": limite, "rival": rival, "nuestras": nuestras,
            "ronda": ronda, "rondas": ronda + max(1, restantes) if restantes is not None else None,
            "texto": texto if isinstance(texto, str) else "", "ticks_restantes": restantes, "escenario": esc,
            "dias": "days" in temas, "pesos_dias": d.get("your_days_weight"), "k_dias": k,
            "rival_paquetes": rival_paquetes, "x": x}


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
        try:                                                      # un duelo que no se entiende no para a los demás
            leido = _traducir(d, tick, est)
        except Exception as e:
            _linea("errores.jsonl", {"tick": tick, "duelo_ilegible": str(d)[:300], "error": f"{type(e).__name__}: {e}"})
            continue
        if leido is not None:
            lectura["duelos"].append(leido)
    repartir_turnos(lectura["duelos"])
    rechazadas = est.get("rechazadas") or {}
    for d in lectura["duelos"]:                                   # solo el tick siguiente al rechazo
        d["x"]["rechazada"] = _num(tick) and rechazadas.get(d["id"]) == tick - 1
    return lectura


def sigue_en_pie(b, firma, lectura):
    """Aceptar cierra con la oferta del rival que esté en pie EN ESE MOMENTO, no con la que leímos al empezar el tick.
    Antes de aceptar se relee el duelo: se acepta si lo que hay ahora nos da al menos lo que firmó el Guardia (o, con
    el plazo encima, si al menos queda dentro del límite). Devuelve (¿aceptar?, motivo)."""
    leido = next((d for d in lectura.get("duelos") or [] if d.get("id") == firma.get("id")), None)
    if leido is None or not _num(firma.get("precio")):
        return True, "sin datos para comprobar"
    try:
        res = b.duels()
    except Exception as e:                                        # si no se puede releer, se acepta lo firmado
        return True, f"no se pudo releer ({type(e).__name__})"
    ahora = next((d for d in (res.get("duels", []) if isinstance(res, dict) else res) or []
                  if isinstance(d, dict) and d.get("duel") == firma["id"]), None)
    if ahora is None:
        return False, "el duelo ya no está en juego"
    vig = estado_por_ticks(dict(ahora, messages=[]), leido.get("k_dias"), lectura.get("tick"), {})["vigente"]
    if vig is None:
        return False, "el rival ya no tiene una oferta que se pueda valorar"
    firmado = duelo.ganancia(leido["rol"], leido["limite"], firma["precio"])
    hay = duelo.ganancia(leido["rol"], leido["limite"], vig[0])
    quedan = leido.get("ticks_restantes")
    if hay >= firmado - 0.5 or (hay > 0 and _num(quedan) and quedan <= 2):
        return True, f"en pie: +{hay:.1f}"
    return False, f"el rival ha cambiado su oferta: ahora da {hay:+.1f}, se firmó {firmado:+.1f}"


def aplicar(b, acciones, vivo, lectura=None, est=None):
    """Acepta lo que firmó el Guardia (primero: es lo que corre prisa) y manda los mensajes de duelo. En seco solo lo
    escribe (ya lo hace el diario)."""
    f = acciones.get("firma_duelo")
    if f and vivo:
        try:
            ok, motivo = sigue_en_pie(b, f, lectura or {})
        except Exception as e:                                    # si la comprobación falla, vale lo que firmó el Guardia
            ok, motivo = True, f"no se pudo comprobar ({type(e).__name__})"
        if not ok:
            print(f"NO SE ACEPTA duelo {f.get('id')}: {motivo}")
            _linea("errores.jsonl", {"firma_duelo": f, "no_aceptado": motivo})
        else:
            try:
                b.duel_accept(f["id"])
            except Exception as e:                                # nunca se repite a ciegas: se relee en el tick siguiente
                print(f"ERROR        aceptar duelo {f.get('id')}: {e}")
                _linea("errores.jsonl", {"firma_duelo": f, "error": str(e)})
                if est is not None:                               # el tick siguiente la firma es para otro duelo
                    est.setdefault("rechazadas", {})[f.get("id")] = (lectura or {}).get("tick")
    for m in acciones["mensajes"]:
        if m.get("destino") != "duelo" or not vivo:
            continue
        if f and m.get("id") == f.get("id"):
            continue                                              # ese duelo se está cerrando: no se le manda nada más
        try:
            b.duel_say(m["id"], m["texto"], price=m["precio"], days=m.get("dias"))
        except Exception as e:
            print(f"ERROR        mensaje al duelo {m.get('id')}: {e}")
            _linea("errores.jsonl", {"mensaje": m, "error": str(e)})


def un_tick(b, est, mem, tick, vivo, stop):
    """Un tick de duelos. Un fallo aquí no tira el programa: se apunta y se espera al tick siguiente."""
    try:
        lectura = leer(b, est, tick)
        p = ajustes()
        for aviso in p.get("_avisos") or []:
            if aviso not in est.setdefault("avisos", set()):
                est["avisos"].add(aviso)
                print("AVISO       ", aviso)
        acciones = cadena.tick(lectura, mem, p=p, stop=stop)
        for linea in acciones["diario"]:
            print(linea)
            _linea("diario.jsonl", {"linea": linea, "vivo": vivo})
        aplicar(b, acciones, vivo, lectura, est)
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
