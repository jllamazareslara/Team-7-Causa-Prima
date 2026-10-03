"""El Cambista en El Rastro: el programa que juega la cadena SOLO en El Rastro. Lee el tablón, llama a cadena.tick() y,
si el Guardia firma una oferta de El Rastro, la acepta. Además publica anuncios, peticiones y cambios carta por carta
cuando sus interruptores están encendidos.

    python rastro.py                mira y escribe lo que haría. NO manda ni acepta nada (modo seco).
    python rastro.py --live         juega de verdad. Solo desde el ordenador que tiene la clave, y un solo proceso.
    python rastro.py --ticks 3      para tras 3 ticks (para la primera prueba en seco)

AVISO: nadie ha lanzado este archivo contra el juego. Las funciones de publicar vienen del antiguo director.py (probadas
contra un juego de mentira); la forma real de las ofertas de board("rastro") todavía no se ha visto. Por eso:
  1. la primera vez SIEMPRE en seco, y mirar runs/rastro-crudo.jsonl: ahí queda el primer tablón tal cual;
  2. una oferta que no se entiende no se acepta (el Guardia rechaza un campo desconocido).

Interruptores (t7/parametros.json o "ajustes" en t7/hoy.json):
    aceptar ofertas del tablón       siempre que el Guardia firme (una por tick como mucho)
    rastro.publicar = 1              publica anuncios de venta (viene a 0)
    cambista.pedir = 1               publica peticiones de compra y cambios carta por carta (viene a 0)

Una sola aceptación por tick para TODO el equipo: en vivo toma el candado (t7/candado.py); si otro programa del mismo
ordenador lo tiene (play.py, por ejemplo), no arranca.
Parar todo: crear el archivo runs/STOP (o Ctrl + C). El Guardia deja de firmar y no se publica nada más.
La clave se lee de la variable de entorno BAZAAR_KEY. No se escribe en ningún archivo ni en el diario.
"""
import argparse
import json
import os
import sys
import time
from collections import Counter

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), "bazaar-kit"))

from t7 import cadena, cambista, candado, ojeador, situacion  # noqa: E402
from t7 import valor as V  # noqa: E402

for _salida in (sys.stdout, sys.stderr):     # una consola de Windows (cp1252) no sabe escribir "→": que no pare el programa
    if hasattr(_salida, "reconfigure"):
        _salida.reconfigure(errors="replace")

RUNS = os.path.join(AQUI, "runs")
RASTRO_CADA = 3          # El Rastro se lee un tick de cada tres: no gastar peticiones al juego
CALENDARIO_CADA = 20     # calendario y catálogo (El Guion y El Ojeador) cada 20 ticks
ANUNCIO_DURA = 40        # ticks que vive un anuncio nuestro en El Rastro
MAX_ANUNCIOS_TICK, MAX_OFERTAS = 12, 30   # límites del juego: anuncios nuevos por tick y ofertas abiertas a la vez


def reservadas(est, tick, dura_trueque):
    """Copias comprometidas AHORA en un anuncio o un cambio vivos de El Rastro: {ref: cuántas}. Se la pasamos a
    cadena.tick() para que el Cambista no proponga aceptar una oferta del tablón que pediría una de esas copias
    (ya la ofrecimos o prometimos por otro lado; aceptar también esa la dejaría sin cubrir, "asset_gone")."""
    out = Counter()
    for x in (est.get("anuncios") or {}).values():
        if isinstance(tick, int) and tick - x["tick"] < ANUNCIO_DURA:
            out[x["ref"]] += 1
    dura = int(dura_trueque or 0)
    for x in (est.get("trueques") or {}).values():
        if isinstance(tick, int) and tick - x["tick"] < dura:
            for ref in x.get("doy", []):
                out[ref] += 1
    return out


def _json(ruta, por_defecto):
    if not os.path.exists(ruta):
        return por_defecto
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _guardar(ruta, d):
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def _linea(nombre, d):
    """Una línea en un archivo de runs/. Apuntar nunca puede tirar el programa."""
    try:
        with open(os.path.join(RUNS, nombre), "a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False, default=str) + "\n")
    except OSError as e:
        print("ERROR        no se pudo escribir en", nombre, e)


def preparar(b):
    """Antes del primer tick: nuestros multiplicadores y las rarezas, leídos del juego en vez de supuestos.
    Si algo falla o no se entiende, se sigue con los supuestos y se dice."""
    try:
        me = b.me()
        catalogo = b.catalog()
        avisos = V.configurar(me.get("affinity"), catalogo, [a for a in me.get("assets") or [] if isinstance(a, dict)])
        _linea("crudo.jsonl", {"tipo": "valores", "affinity": me.get("affinity"), "multiplicadores": dict(V.NUESTROS_MULT),
                               "rarezas_del_juego": len(V.RAREZAS), "avisos": avisos})
    except Exception as e:
        avisos = [f"no se pudieron leer los valores del juego ({e}): se usan los supuestos"]
        _linea("errores.jsonl", {"preparar": str(e)})
    print("VALORES      " + ", ".join(f"{k} × {v}" for k, v in sorted(V.NUESTROS_MULT.items(), key=lambda x: -x[1]))
          + f" · {len(V.RAREZAS)} cartas con rareza del juego")
    for a in avisos:
        print("AVISO        " + a)
    return avisos


def abrir_sobres(b, me, vivo):
    """Abre los sobres que tengamos ANTES de comprar, para no comprar una carta que venía dentro.
    Devuelve cuántos se han abierto de verdad (en seco, ninguno)."""
    sobres = [a for a in me.get("assets") or [] if isinstance(a, dict) and a.get("kind") == "pack" and a.get("id") is not None]
    abiertos = 0
    for a in sobres:
        print(f"SOBRE        {a.get('name', a.get('ref', a['id']))}: " + ("se abre" if vivo else "se abriría (en seco)"))
        if not vivo:
            continue
        try:
            _linea("crudo.jsonl", {"tipo": "sobre", "crudo": b.open_pack(a["id"])})
            abiertos += 1
        except Exception as e:                                   # un sobre que no se abre no bloquea las compras
            _linea("errores.jsonl", {"sobre": a.get("id"), "error": str(e)})
    return abiertos


def precios_de_venta(menus):
    """{ref: lo mejor que nos ofrece de entrada algún vendedor}: para que el plan del día sepa qué vender si falta caja."""
    precios = {}
    for menu in (menus or {}).values():
        for ref, precio in ((menu or {}).get("compra") or {}).items() if isinstance(menu, dict) else []:
            if isinstance(precio, (int, float)):
                precios[ref] = max(precios.get(ref, 0), precio)
    return precios


def anunciar(b, me, est, plan, tick, vivo, menus=None, tratos=None, primero=False, mem=None, lectura=None):
    """El Cambista vende: anuncia en El Rastro lo que podemos dar sin perder valor (qué y a cuánto lo dice la cadena).

    Solo publica en vivo y con rastro.publicar = 1. Con 0 (como viene), enseña una vez lo que anunciaría y no manda nada.
    Lo que un vendedor todavía puede comprarnos hoy para su escalera no se anuncia: va primero al vendedor.
    est["anuncios"] = {id de la carta: {"ref", "precio", "tick", "caducidades"}}: a los ANUNCIO_DURA ticks se da por
    caducado y se vuelve a anunciar más barato. Devuelve lo que ha anunciado (o anunciaría)."""
    p, forzar = plan["p"], plan["forzar"]
    publicar = bool(p.get("rastro.publicar"))
    if not isinstance(tick, int) or "apagado" in (forzar.get("rastro"), forzar.get("equipo")) or not (publicar or primero):
        return []
    ids = {str(a["id"]): a for a in me.get("assets") or []
           if isinstance(a, dict) and a.get("kind") == "card" and a.get("ref") and a.get("id") is not None}
    ads = est.setdefault("anuncios", {})
    for aid in [x for x in ads if x not in ids]:                 # vendida, o ya no es nuestra
        ads.pop(aid)
    vivos = {aid: x for aid, x in ads.items() if tick - x["tick"] < ANUNCIO_DURA}
    caducidades = {}
    for aid, x in ads.items():
        if aid not in vivos:
            caducidades[x["ref"]] = max(caducidades.get(x["ref"], 0), x["caducidades"] + 1)
    menus, tratos = menus or {}, tratos or {}
    tope = p.get("tienda.tratos_por_vendedor_y_dia")
    listas, guardadas = {}, set()
    for vendedor, menu in menus.items():
        if not isinstance(menu, dict):
            continue
        listas.update({r: x for r, x in (menu.get("vende") or {}).items() if isinstance(x, (int, float))})
        if tope is None or tratos.get(vendedor, 0) < tope:
            guardadas.update(menu.get("compra") or {})
    ocupadas = [h["carta"] for h in (est.get("hilos") or {}).values() if h.get("lado") == "venta"]
    ocupadas += [r for x in (est.get("trueques") or {}).values()                 # ya ofrecidas en un cambio
                 if tick - x["tick"] < p.get("cambista.peticion_dura_ticks", 10) for r in x["doy"]]
    cuenta = Counter(a["ref"] for a in ids.values())
    maximo = max(0, min(MAX_ANUNCIOS_TICK, MAX_OFERTAS - len(vivos)))
    activos = Counter(x["ref"] for x in vivos.values())
    if mem is not None:                                          # con sus consejeros (Guion, Ojeador): en t7/cadena.py
        nuevos = cadena.anuncios(cuenta, p, mem, lectura or {"tick": tick}, activos, ocupadas, guardadas, listas,
                                 caducidades, maximo)
    else:
        nuevos = cadena.anuncios_rastro(cuenta, p, activos, ocupadas, guardadas, listas, caducidades, maximo=maximo)
    for n in nuevos:
        libres = sorted(aid for aid, a in ids.items() if a["ref"] == n["carta"] and aid not in vivos)
        if not libres:
            continue
        aid = libres[0]
        mandar = vivo and publicar
        print(f"ANUNCIO      {n['carta']} a {n['precio']} P en El Rastro (nos vale {n['pierde']})"
              + (f" · Ojeador {n['ojeador']}" if n.get("ojeador") else "")
              + ("" if mandar else " · no se publica: " + ("en seco" if publicar else "rastro.publicar = 0")))
        if not mandar:
            continue
        try:
            b.list_offer(give={"assets": [ids[aid]["id"]]}, want={"cash": n["precio"]}, venue="rastro",
                         expires_in_ticks=ANUNCIO_DURA)
            ads[aid] = vivos[aid] = {"ref": n["carta"], "precio": n["precio"], "tick": tick,
                                     "caducidades": caducidades.get(n["carta"], 0)}
        except Exception as e:                                   # un anuncio que falla no para nada: se apunta
            _linea("errores.jsonl", {"anuncio": n, "error": str(e)})
    return nuevos


FIN_JUEGO = "2026-10-04T15:00:00+02:00"     # domingo 15:00, Madrid. Si la organización lo mueve: "fin_juego" en t7/hoy.json


def minutos_al_final(ahora=None):
    """Minutos que quedan de juego (reloj de pared). Si el calendario se retrasa, se corrige en t7/hoy.json."""
    from datetime import datetime, timezone
    fin = (_json(os.path.join(AQUI, "t7", "hoy.json"), {}) or {}).get("fin_juego") or FIN_JUEGO
    try:
        fin = datetime.fromisoformat(fin)
    except (TypeError, ValueError):
        return None
    return (fin - (ahora or datetime.now(timezone.utc))).total_seconds() / 60


def pedir(b, me, est, plan, tick, vivo, mem, menus=None, primero=False, ahora=None):
    """El Cambista compra: publica en El Rastro peticiones ("pago X por esta carta") y cambios carta por carta
    ("te doy estas repetidas por esta carta"), siguiendo la lista de la compra.

    Solo publica en vivo y con cambista.pedir = 1. Con 0 (como viene), enseña una vez la lista y lo que pediría.
    est["peticiones"] = {carta: {"precio", "tick", "caducidades", "id"}} y est["trueques"] = {carta: {"doy", "tick", "id"}}:
    a los cambista.peticion_dura_ticks se dan por caducados; una petición vuelve un poco más cara, sin pasar del tope.
    Cuando la carta ya es nuestra se cancela lo que siga vivo por ella (una segunda copia vale el 25 %), y si una
    petición viva era el único camino, su precio se apunta en est["pagado"]: la siguiente de esa rareza abre más abajo.
    En los últimos cambista.minutos_final minutos de juego el efectivo ya no sirve: se pide al tope.
    Devuelve las peticiones y los cambios que ha publicado (o publicaría)."""
    p, forzar, ordenes = plan["p"], plan["forzar"], plan.get("ordenes") or {}
    publicar = bool(p.get("cambista.pedir"))
    if not isinstance(tick, int) or "apagado" in (forzar.get("rastro"), forzar.get("equipo")) or not (publicar or primero):
        return []
    cartas = {str(a["id"]): a for a in me.get("assets") or []
              if isinstance(a, dict) and a.get("kind") == "card" and a.get("ref") and a.get("id") is not None}
    cuenta = Counter(a["ref"] for a in cartas.values())
    efectivo = me.get("cash") or 0
    dura = int(p["cambista.peticion_dura_ticks"])
    pets, trus = est.setdefault("peticiones", {}), est.setdefault("trueques", {})
    pagado = est.setdefault("pagado", {})

    def cancelar(x, que):
        if vivo and publicar and x.get("id") is not None and tick - x["tick"] < dura:
            try:
                b.cancel(x["id"])
            except Exception as e:
                _linea("errores.jsonl", {"cancelar": que, "error": str(e)})

    for ref in [r for r in set(pets) | set(trus) if cuenta.get(r, 0) > 0]:        # ya la tenemos
        x, t = pets.pop(ref, None), trus.pop(ref, None)
        if x and tick - x["tick"] < dura and not t:
            pagado.setdefault(V.rareza(ref), []).append(x["precio"])          # la petición funcionó: aprender
            del pagado[V.rareza(ref)][:-10]
        for y, que in ((x, "peticion"), (t, "trueque")):
            if y:
                cancelar(y, f"{que} {ref}")
    vivas = {r: x for r, x in pets.items() if tick - x["tick"] < dura}
    caducidades = {r: x["caducidades"] + 1 for r, x in pets.items() if r not in vivas}
    trus_vivos = {r: x for r, x in trus.items() if tick - x["tick"] < dura}
    listas = {}
    for menu in (menus or {}).values():
        if isinstance(menu, dict):
            listas.update({r: x for r, x in (menu.get("vende") or {}).items() if isinstance(x, (int, float))})
    quedan = minutos_al_final(ahora)
    final = quedan is not None and 0 < quedan <= p["cambista.minutos_final"]
    lista = cadena.lista_compra(cuenta, efectivo, p, getattr(mem, "mercado", None), listas, pagado, final)
    if primero:
        for linea in cambista.resumen_compras(lista):
            print(linea)
    mandar = vivo and publicar
    nota = "" if mandar else " · no se publica: " + ("en seco" if publicar else "cambista.pedir = 0")

    # 1. cambios carta por carta: no gastan efectivo, así que van aunque la caja esté seca
    anunciadas = [x["ref"] for aid, x in (est.get("anuncios") or {}).items() if tick - x["tick"] < ANUNCIO_DURA]
    en_venta = [h["carta"] for h in (est.get("hilos") or {}).values() if h.get("lado") == "venta"]
    comprometidas = [r for x in trus_vivos.values() for r in x["doy"]]
    cambios = cadena.trueques_rastro(lista, cuenta, p, anunciadas + en_venta + comprometidas, set(trus), len(trus_vivos))
    usados = {aid for aid, x in (est.get("anuncios") or {}).items() if tick - x["tick"] < ANUNCIO_DURA}
    usados |= {aid for x in trus_vivos.values() for aid in x.get("ids", [])}
    for c in cambios:
        print(f"CAMBIO       damos {' + '.join(c['doy'])} (nos valen {c['pierdo']}) por {c['quiero']} (nos vale {c['nos_vale']}) "
              f"· gana {c['gana']:+.1f} · {c['motivo']}{nota}")
        if not mandar:
            continue
        ids = []
        for ref in c["doy"]:
            aid = next((a for a in sorted(cartas) if cartas[a]["ref"] == ref and a not in usados and a not in ids), None)
            if aid is None:
                break
            ids.append(aid)
        if len(ids) != len(c["doy"]):
            continue
        try:
            r = b.list_offer(give={"assets": [cartas[a]["id"] for a in ids]}, want={"cards": [c["quiero"]]},
                             venue="rastro", expires_in_ticks=dura)
            r = r if isinstance(r, dict) else {}
            trus[c["quiero"]] = {"doy": c["doy"], "ids": ids, "tick": tick, "id": r.get("id", (r.get("offer") or {}).get("id"))}
            usados.update(ids)
        except Exception as e:
            _linea("errores.jsonl", {"trueque": c, "error": str(e)})

    # 2. peticiones con efectivo, solo de lo que eligió la mochila
    if ordenes.get("compras") == "ninguna":                     # caja seca: no se compromete efectivo
        return cambios
    nuevas = cadena.peticiones_rastro(lista, cuenta, efectivo, p, {r: x["precio"] for r, x in vivas.items()}, caducidades,
                                      getattr(mem, "demanda", None), final)
    for n in nuevas:
        if n["carta"] in trus_vivos or any(c["quiero"] == n["carta"] for c in cambios):
            continue                                            # ya se pide con un cambio: no pagar además
        print(f"PETICIÓN     {n['carta']} a {n['precio']} P en El Rastro (nos vale {n['nos_vale']}, tope {n['tope']}) · {n['motivo']}{nota}")
        if not mandar:
            continue
        try:
            r = b.list_offer(give={"cash": n["precio"]}, want={"cards": [n["carta"]]}, venue="rastro",
                             expires_in_ticks=dura)
            r = r if isinstance(r, dict) else {}
            oid = r.get("id", (r.get("offer") or {}).get("id"))
            pets[n["carta"]] = {"precio": n["precio"], "tick": tick, "caducidades": caducidades.get(n["carta"], 0), "id": oid}
        except Exception as e:                                   # una petición que falla no para nada: se apunta
            _linea("errores.jsonl", {"peticion": n, "error": str(e)})
    return cambios + nuevas


def _cartas(me):
    """{id de la carta como texto: la carta} de lo que tenemos (solo cartas con código)."""
    return {str(a["id"]): a for a in me.get("assets") or []
            if isinstance(a, dict) and a.get("kind") == "card" and a.get("ref") and a.get("id") is not None}


def leer_calendario(b, est):
    """Calendario y catálogo del juego (solo GET), tal cual, para la cadena: El Guion y El Ojeador (t7/cadena.py, ojear)."""
    try:
        cal = b.schedule()
        if isinstance(cal, dict) and isinstance(cal.get("now_hours"), (int, float)):
            est["calendario_nuevo"] = cal
    except Exception as e:
        _linea("errores.jsonl", {"calendario": str(e)})
    try:
        est["catalogo_nuevo"] = b.catalog()
    except Exception as e:
        _linea("errores.jsonl", {"catalogo": str(e)})


def leer(b, tick, con_tablon=True, est=None):
    """La lectura que necesita la cadena para El Rastro: efectivo, cartas y el tablón sin nuestras propias ofertas;
    y, cuando toca, el feed público, el calendario y el catálogo para El Guion y El Ojeador."""
    me = b.me()
    nosotros = me.get("name")
    cartas = list(_cartas(me).values())
    V.configurar(cartas=cartas)                                  # la rareza de lo que tenemos, tal como la dice el juego
    lectura = {"tick": tick, "efectivo": me.get("cash", 0), "cuenta": Counter(a["ref"] for a in cartas),
               "vendedores": [], "duelos": [], "tablon": None}
    if con_tablon:
        try:                                                     # si El Rastro no se puede leer, el tick sigue sin él
            res = b.board("rastro")
            ofertas = res.get("offers", []) if isinstance(res, dict) else res
            lectura["tablon"] = [o for o in ofertas or [] if isinstance(o, dict) and o.get("maker") != nosotros]
            _linea("rastro-crudo.jsonl", {"tick": tick, "tablon": lectura["tablon"][:20]})
        except Exception as e:
            _linea("errores.jsonl", {"tick": tick, "rastro": str(e)})
        if isinstance(tick, int) and tick % (2 * RASTRO_CADA) == 0:   # el feed público: tratos hechos, para el Ojeador
            try:
                lectura["feed"] = b.feed(limit=100)
            except Exception as e:
                _linea("errores.jsonl", {"tick": tick, "feed": str(e)})
    est = est if est is not None else {}
    lectura["calendario"] = est.pop("calendario_nuevo", None)    # lecturas crudas para la cadena (El Guion y El Ojeador)
    lectura["catalogo"] = est.pop("catalogo_nuevo", None)
    return lectura, me


def cartas_para(oferta, me, est):
    """Los ids de nuestras copias que pide una oferta (want.cards = ["LAT-03"] o want.types = ["card:LAT-03"]).
    [] si no pide cartas; None si nos falta alguna libre. Una copia ya anunciada o comprometida en un cambio no se da."""
    want = oferta.get("want") or {}
    refs = [r for r in want.get("cards") or [] if isinstance(r, str)]
    refs += [t.split(":", 1)[1] for t in want.get("types") or [] if isinstance(t, str) and t.startswith("card:")]
    ocupadas = set(est.get("anuncios") or {}) | {aid for x in (est.get("trueques") or {}).values() for aid in x.get("ids", [])}
    nuestras, elegidas = _cartas(me), []
    for ref in refs:
        libre = next((aid for aid in sorted(nuestras) if nuestras[aid]["ref"] == ref
                      and aid not in ocupadas and aid not in elegidas), None)
        if libre is None:
            return None
        elegidas.append(libre)
    return [nuestras[aid]["id"] for aid in elegidas]


def aceptar(b, firma, tablon, me, est, vivo):
    """Si el Guardia firmó una oferta de El Rastro, se acepta (en vivo). Devuelve los ids de cartas que se dan, o None."""
    if not firma or firma.get("destino") != "rastro":
        return None
    oferta = next((o for o in tablon or [] if o.get("id") == firma.get("oferta_id")), None)
    if oferta is None:
        print(f"FIRMA        oferta {firma.get('oferta_id')} ya no está en el tablón: no se acepta")
        return None
    dar = cartas_para(oferta, me, est)
    if dar is None:
        print(f"FIRMA        oferta {firma['oferta_id']}: no tenemos libre la carta que pide, no se acepta")
        return None
    print(f"FIRMA        El Rastro · oferta {firma['oferta_id']} · {firma.get('motivo', '')}"
          + (f" · damos {dar}" if dar else "") + ("" if vivo else " · en seco: no se acepta"))
    if vivo:
        try:
            b.accept(firma["oferta_id"], assets=dar or None)
            _linea("rastro-tratos.jsonl", {"oferta": oferta, "damos": dar, "motivo": firma.get("motivo")})
        except Exception as e:                                   # nunca se repite a ciegas: se relee en el tick siguiente
            _linea("errores.jsonl", {"aceptar": firma.get("oferta_id"), "error": str(e)})
    return dar


def un_tick(b, est, mem, tick, tick_segundos, vivo, stop, primero=False, t_horas=None):
    """Un tick de El Rastro. Un fallo aquí no tira el programa: se apunta y se espera al tick siguiente.
    Devuelve True si el tick se completó."""
    try:
        menus = _json(os.path.join(AQUI, "menus.json"), None)
        toca = primero or (isinstance(tick, int) and tick % RASTRO_CADA == 0)
        if primero or (isinstance(tick, int) and tick % CALENDARIO_CADA == 0):
            leer_calendario(b, est)
        lectura, me = leer(b, tick, con_tablon=toca, est=est)
        lectura["t_hours"], lectura["tick_segundos"] = t_horas, tick_segundos   # la hora de juego, para El Ojeador
        plan = situacion.plan({"efectivo": lectura["efectivo"], "cuenta": lectura["cuenta"],
                               "tick_segundos": tick_segundos}, precios_venta=precios_de_venta(menus) or None)
        if primero:
            print(situacion.resumen(plan))
        lectura["reservadas"] = reservadas(est, tick, plan["p"].get("cambista.peticion_dura_ticks"))
        acciones = cadena.tick(lectura, mem, plan["p"], plan["forzar"], plan["ordenes"], stop)
        for linea in acciones["diario"]:
            print(linea)
            _linea("diario.jsonl", {"linea": linea, "vivo": vivo})
        aceptar(b, acciones["firma"], lectura["tablon"], me, est, vivo)
        if toca and not stop and not abrir_sobres(b, me, vivo):  # tras abrir un sobre las cartas cambian: al tick siguiente
            anunciar(b, me, est, plan, tick, vivo, menus, cadena.tratos_de_hoy(mem, time.strftime("%Y-%m-%d")), primero,
                     mem=mem, lectura=lectura)
            pedir(b, me, est, plan, tick, vivo, mem, menus, primero)
        if primero or (isinstance(tick, int) and tick % CALENDARIO_CADA == 0):
            mom = lectura.get("momento") or {}
            if mom.get("fase", "normal") != "normal":
                print(f"MOMENTO      {mom['fase']}: {mom.get('motivo', '')}")
            for linea in ojeador.informe(mem.historial, tick if isinstance(tick, int) else 0):
                print(linea)
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
    est = _json(os.path.join(RUNS, "rastro.json"), {})
    mem = cadena.Memoria.de_dict(_json(os.path.join(RUNS, "memoria.json"), {}))
    print("EN VIVO" if a.live else "EN SECO: no se manda ni se acepta nada")
    if a.live:                                                   # un solo programa acepta a la vez (t7/candado.py)
        ok, motivo = candado.tomar(candado.RUTA, "rastro.py")
        if not ok:
            sys.exit("NO SE LANZA   " + motivo)
    try:
        _jugar(b, est, mem, a)
    finally:
        if a.live:
            candado.soltar(candado.RUTA)


def _jugar(b, est, mem, a):
    preparar(b)
    hechos, ultimo = 0, None
    while not a.ticks or hechos < a.ticks:
        try:                                                     # un corte de red no tira el programa: espera y sigue
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
        un_tick(b, est, mem, tick, reloj.get("tick_seconds"), a.live, os.path.exists(os.path.join(RUNS, "STOP")),
                primero=hechos == 1, t_horas=reloj.get("t_hours"))
        try:
            _guardar(os.path.join(RUNS, "rastro.json"), est)
            _guardar(os.path.join(RUNS, "memoria.json"), mem.a_dict())
        except Exception as e:
            print("ERROR        no se pudo guardar el estado:", e)


if __name__ == "__main__":
    main()
