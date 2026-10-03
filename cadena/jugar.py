"""Jugar: conecta la cadena con el juego, para los VENDEDORES (el Regateador) y EL RASTRO (el Cambista).

No es un agente ni un paso del flujo: son las flechas con EL JUEGO. Lee el juego, llama a cadena.tick()
(Ojos → Contable → Cambista / Regateador → Guardia, con el Guion y el Ojeador al lado) y aplica lo que devuelve:
los precios del Regateador, los cierres y la ÚNICA firma del tick (de un vendedor o de El Rastro).

    python jugar.py                mira y escribe lo que haría. NO manda ni acepta nada (modo seco).
    python jugar.py --live         juega de verdad. Solo desde el ordenador que tiene la clave, y un solo proceso.
    python jugar.py --ticks 3      para tras 3 ticks (para la primera prueba en seco)

Vendedores (el Regateador): una conversación por vendedor, todos a la vez (hasta MAX_HILOS), según menus.json
(`python revisar.py --menus`). Qué abrir lo dice cadena.operaciones(): primero vender, luego comprar, con los consejos
del Guion (cartas guardadas para una fiebre) y del Ojeador (vendedores que descansan, El Rastro más barato, cartas que
se agotan). Los precios solo se mueven en un sentido y nunca se repiten; la oferta final se acepta si está dentro del
límite. Toda firma pasa por el Guardia.
El Rastro (el Cambista): acepta lo que firme el Guardia, y lo que ningún vendedor puede comprarnos hoy se anuncia
(rastro.publicar = 1); peticiones y cambios carta por carta con cambista.pedir = 1. No abre mercado propio.
Duelos: este programa NO los juega.

AVISO: nadie ha lanzado este archivo contra el juego. La forma de vendedores y del tablón está vista en la prueba en
seco del 3/10 (PRUEBA-EN-SECO-03-10.md); la de una conversación, en play.py. La primera vez SIEMPRE en seco, y mirar
runs/crudo.jsonl (la primera conversación tal cual) y runs/rastro-crudo.jsonl (el primer tablón).

Una sola aceptación por tick para TODO el equipo: en vivo toma el candado (t7/candado.py); si otro programa del mismo
ordenador lo tiene, no arranca. No lanzar a la vez dealers/smart_agent.py ni play.py: no toman el candado.
Parar todo: crear el archivo runs/STOP (o Ctrl + C). El Guardia deja de firmar y no se abre ni se publica nada más.
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
CALENDARIO_CADA = 20     # vendedores, calendario y catálogo (El Guion y El Ojeador) cada 20 ticks
MAX_HILOS = 6            # conversaciones con vendedores abiertas a la vez (una por vendedor)
MUDO_MAX = 4             # ticks seguidos sin entender la oferta de una conversación abierta antes de soltarla
ANUNCIO_DURA = 40        # ticks que vive un anuncio nuestro en El Rastro
MAX_ANUNCIOS_TICK, MAX_OFERTAS = 12, 30   # límites del juego: anuncios nuevos por tick y ofertas abiertas a la vez


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


def _precio(x):
    if isinstance(x, dict):
        x = x.get("price", x.get("cash"))
    return x if isinstance(x, (int, float)) else None


def _somos(nosotros):
    """Cómo nos llama el juego: el id ("t07", el autor de las ofertas) y el nombre ("Team 7"), más "me" y "you"."""
    return ((nosotros,) if isinstance(nosotros, str) else tuple(nosotros or ())) + ("me", "you")


def _oferta_del_otro(hilo, nosotros):
    """La oferta vigente de la otra parte en una conversación: (id, precio, final). None si no se entiende."""
    for o in reversed(hilo.get("standing_offers") or []):
        if o.get("maker") in _somos(nosotros) + (hilo.get("team"),) or o.get("status") not in (None, "open", "standing"):
            continue
        # el lado con dinero: comprándonos, el vendedor da {cash: 13} y pide {cash: 0, la carta}; el 0 no es su precio
        precio = next((p for p in (_precio(o.get("want")), _precio(o.get("give"))) if p), None)
        if precio is not None:
            return o.get("id"), precio, bool(o.get("final"))
    return None


def _ultimo_texto(hilo, nosotros):
    for m in reversed(hilo.get("messages") or []):
        autor = m.get("from", m.get("sender", m.get("author")))
        if autor is not None and autor not in _somos(nosotros) + (hilo.get("team"),):
            return m.get("text") or ""
    return ""


def _cartas(me):
    """{id de la carta como texto: la carta} de lo que tenemos (solo cartas con código)."""
    return {str(a["id"]): a for a in me.get("assets") or []
            if isinstance(a, dict) and a.get("kind") == "card" and a.get("ref") and a.get("id") is not None}


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


def vendedores_nuevos(b, est, menus):
    """Caras nuevas (y el nivel de cada vendedor, para la escalera): la primera vez que aparece un vendedor se guarda tal cual en runs/crudo.jsonl y se avisa.
    No se adivina su menú: hasta que alguien lo ponga en menus.json no se le abre nada."""
    try:
        res = b.dealers()
    except Exception as e:
        _linea("errores.jsonl", {"vendedores": str(e)})
        return []
    lista = (res.get("dealers") or res.get("in_play") or res.get("personas") or []) if isinstance(res, dict) else res
    # el juego real responde {"personas": [...]} (visto el 3/10); los anunciados traen "status": "announced"
    nuevos = []
    for d in lista if isinstance(lista, list) else []:
        vid = d.get("id") if isinstance(d, dict) else None
        if vid is not None and isinstance(d.get("level"), (int, float)):
            est.setdefault("niveles", {})[vid] = d["level"]     # la escalera: los niveles altos pesan más
        if vid is None or vid in est.setdefault("vendedores", []):
            continue
        est["vendedores"].append(vid)
        nuevos.append(vid)
        _linea("crudo.jsonl", {"tipo": "vendedor", "crudo": d})
        print(f"VENDEDOR     {vid}" + ("" if vid in (menus or {}) else " · no está en menus.json: no se le abre nada todavía"))
    return nuevos


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


def soltar_mudos(b, est, lectura, vivo):
    """Suelta las conversaciones abiertas en las que llevamos MUDO_MAX ticks sin entender la oferta del otro."""
    for hid in lectura.get("mudos") or []:
        print(f"SUELTA       conversación {hid}: {MUDO_MAX} ticks sin una oferta que entendamos (mirar runs/errores.jsonl)")
        if not vivo:
            continue
        try:
            b.close_thread(int(hid))
        except Exception as e:
            _linea("errores.jsonl", {"soltar": hid, "error": str(e)})
        est["hilos"].pop(hid, None)


def precios_de_venta(menus):
    """{ref: lo mejor que nos ofrece de entrada algún vendedor}: para que el plan del día sepa qué vender si falta caja."""
    precios = {}
    for menu in (menus or {}).values():
        for ref, precio in ((menu or {}).get("compra") or {}).items() if isinstance(menu, dict) else []:
            if isinstance(precio, (int, float)):
                precios[ref] = max(precios.get(ref, 0), precio)
    return precios


def abrir(b, me, est, plan, vivo, menus=None, tratos=None, mem=None, lectura=None):
    """Rellena los huecos: una conversación nueva por vendedor libre, según menus.json. Primero vender, luego comprar."""
    menus = _json(os.path.join(AQUI, "menus.json"), None) if menus is None else menus
    huecos = MAX_HILOS - len(est["hilos"])
    if not menus or huecos <= 0:
        return
    cuenta = Counter(a["ref"] for a in me.get("assets") or [] if a.get("kind") == "card" and a.get("ref"))
    for x in (est.get("anuncios") or {}).values():               # lo anunciado en El Rastro no se ofrece además a un vendedor
        cuenta[x["ref"]] -= 1
    abiertas = {h["vendedor"] for h in est["hilos"].values()}
    tope = plan["p"].get("tienda.tratos_por_vendedor_y_dia")
    if mem is not None:                                          # con sus consejeros (Guion, Ojeador): en t7/cadena.py
        ops = cadena.operaciones(cuenta, me.get("cash", 0), menus, mem, lectura or {}, plan["ordenes"], abiertas, tratos, tope)
    else:
        ops = cadena.cola_de_operaciones(cuenta, me.get("cash", 0), menus, plan["ordenes"], abiertas, tratos, tope)
    for op in ops[:huecos]:
        if op["lado"] == "venta":
            ids = sorted(a["id"] for a in me["assets"] if a.get("kind") == "card" and a.get("ref") == op["carta"])
            if not ids:
                continue
            tema = {"sell": {"assets": [ids[-1]]}}
        else:
            tema = {"buy": {"card": op["carta"]}}
        print(f"ABRIR        {op['vendedor']} · {op['lado']} {op['carta']}")
        if not vivo:
            continue
        try:
            r = b.open_thread(op["vendedor"], topic=tema)
            hid = r.get("id", r.get("thread_id", (r.get("thread") or {}).get("id")))
            if hid is not None:
                est["hilos"][str(hid)] = dict(op, suyas=[], nuestras=[])
        except Exception as e:
            _linea("errores.jsonl", {"abrir": op, "error": str(e)})


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


def leer(b, est, tick, con_tablon=True):
    """La lectura de la cadena: efectivo, cartas, las conversaciones con vendedores que abrimos nosotros y, cuando toca,
    el tablón de El Rastro (sin nuestras ofertas), el feed, el calendario, el catálogo y los niveles."""
    me = b.me()
    nosotros = tuple(x for x in (me.get("id"), me.get("name")) if x)   # las ofertas llevan el id ("t07"), no el nombre
    cartas = list(_cartas(me).values())
    V.configurar(cartas=cartas)                                  # la rareza de lo que tenemos, tal como la dice el juego
    lectura = {"tick": tick, "efectivo": me.get("cash", 0), "cuenta": Counter(a["ref"] for a in cartas),
               "vendedores": [], "duelos": [], "tablon": None, "mudos": []}
    hilos = est.setdefault("hilos", {})

    for hid, h in list(hilos.items()):                           # el Regateador: cada conversación que abrimos
        try:
            crudo = b.thread(int(hid))
        except Exception as e:                                   # un fallo afecta solo a esta conversación
            _linea("errores.jsonl", {"tick": tick, "hilo": hid, "error": str(e)})
            continue
        if not est.get("crudo_hilo"):
            est["crudo_hilo"] = True
            _linea("crudo.jsonl", {"tipo": "hilo", "crudo": crudo})
        estado = crudo.get("status")
        vigente = _oferta_del_otro(crudo, nosotros)
        if estado in ("deal", "walked", "closed", "cooloff") or vigente is None:
            if estado in ("deal", "walked", "closed", "cooloff"):
                hilos.pop(hid)
                if estado != "deal":                             # el motivo y until_tick: el Ojeador decide el descanso
                    lectura["vendedores"].append(dict(h, id=int(hid), suyas=h["suyas"] or [0],
                                                      cerrado=crudo.get("closed_reason") or estado,
                                                      until_tick=crudo.get("until_tick")))
            else:                                                # abierta, pero sin una oferta suya que entendamos
                h["mudo"] = h.get("mudo", 0) + 1
                if h["mudo"] >= MUDO_MAX:                        # no se queda ocupando el hueco de ese vendedor
                    lectura["mudos"].append(hid)
                    _linea("errores.jsonl", {"tick": tick, "hilo": hid, "error": "sin oferta entendida; se suelta",
                                             "crudo": crudo})
            continue
        h["mudo"] = 0
        oid, precio, final = vigente
        if not h["suyas"] or h["suyas"][-1] != precio:
            h["suyas"].append(precio)
        lectura["vendedores"].append({"id": int(hid), "vendedor": h["vendedor"], "lado": h["lado"], "carta": h["carta"],
                                      "suyas": list(h["suyas"]), "nuestras": list(h["nuestras"]), "final": final,
                                      "oferta_id": oid, "texto": _ultimo_texto(crudo, nosotros), "lista": h.get("lista")})

    if con_tablon:                                               # el Cambista: El Rastro
        try:
            res = b.board("rastro")
            ofertas = res.get("offers", []) if isinstance(res, dict) else res
            lectura["tablon"] = [o for o in ofertas or [] if isinstance(o, dict) and o.get("maker") not in nosotros]
            _linea("rastro-crudo.jsonl", {"tick": tick, "tablon": lectura["tablon"][:20]})
        except Exception as e:
            _linea("errores.jsonl", {"tick": tick, "rastro": str(e)})
        if isinstance(tick, int) and tick % (2 * RASTRO_CADA) == 0:   # el feed público: tratos hechos, para el Ojeador
            try:
                lectura["feed"] = b.feed(limit=100)
            except Exception as e:
                _linea("errores.jsonl", {"tick": tick, "feed": str(e)})
    lectura["calendario"] = est.pop("calendario_nuevo", None)    # lecturas crudas para el Guion y el Ojeador
    lectura["catalogo"] = est.pop("catalogo_nuevo", None)
    lectura["niveles"] = est.get("niveles")
    return lectura, me


def limpiar_hilos(b, est, vivo):
    """Al arrancar: una conversación abierta que no recordamos (de otra ejecución) ocupa el hueco de ese vendedor.
    Se cierra, como hace play.py, para poder abrir la nuestra."""
    try:
        res = b.my_threads()
    except Exception as e:
        _linea("errores.jsonl", {"mis_hilos": str(e)})
        return []
    lista = res.get("threads", []) if isinstance(res, dict) else res
    sueltas = [t for t in lista or [] if isinstance(t, dict) and t.get("status") == "open"
               and t.get("id") is not None and str(t["id"]) not in est.setdefault("hilos", {})]
    for t in sueltas:
        print(f"CIERRA       conversación {t['id']} con {t.get('with')}: abierta de otra ejecución"
              + ("" if vivo else " · en seco: no se cierra"))
        if vivo:
            try:
                b.close_thread(t["id"])
            except Exception as e:
                _linea("errores.jsonl", {"cerrar_suelta": t["id"], "error": str(e)})
    return sueltas


def aplicar(b, acciones, est, lectura, me, vivo):
    """Manda los precios del Regateador, cierra lo que toca y aplica la ÚNICA firma del tick (vendedor o El Rastro).
    En seco solo lo escribe. Los duelos no los juega este programa."""
    hilos = est.setdefault("hilos", {})
    for m in acciones["mensajes"]:
        if m["destino"] != "vendedor":
            continue
        print(f"PRECIO       conversación {m['id']} · {m['precio']} P · «{m['texto']}»" + ("" if vivo else " · en seco: no se manda"))
        if not vivo:
            continue
        try:
            b.say(m["id"], m["texto"], price=m["precio"])
            if str(m["id"]) in hilos:
                hilos[str(m["id"])]["nuestras"].append(m["precio"])
        except Exception as e:
            _linea("errores.jsonl", {"mensaje": m, "error": str(e)})
    for c in acciones["cerrar"]:
        if c.get("destino") != "vendedor":
            continue
        print(f"CIERRA       conversación {c['id']} · {c.get('motivo', '')}" + ("" if vivo else " · en seco: no se cierra"))
        if not vivo:
            continue
        try:
            b.close_thread(c["id"])
            hilos.pop(str(c["id"]), None)
        except Exception as e:
            _linea("errores.jsonl", {"cerrar": c, "error": str(e)})
    f = acciones["firma"]
    if not f:
        return None
    if f["destino"] == "rastro":
        return aceptar(b, f, lectura.get("tablon"), me, est, vivo)
    if f["destino"] == "vendedor" and f.get("oferta_id") is not None:
        print(f"FIRMA        vendedor · conversación {f['id']} · {f.get('motivo', '')}" + ("" if vivo else " · en seco: no se acepta"))
        if vivo:
            try:
                b.accept(f["oferta_id"])
                _linea("tratos.jsonl", {"conversacion": f["id"], "precio": f.get("precio"), "motivo": f.get("motivo")})
            except Exception as e:                               # nunca se repite a ciegas: se relee en el tick siguiente
                _linea("errores.jsonl", {"firma": f, "error": str(e)})
        return f
    return None


def un_tick(b, est, mem, tick, tick_segundos, vivo, stop, primero=False, t_horas=None):
    """Un tick entero. Un fallo aquí no tira el programa: se apunta y se espera al tick siguiente.
    Devuelve True si el tick se completó."""
    try:
        est.setdefault("hilos", {})
        menus = _json(os.path.join(AQUI, "menus.json"), None)
        dia = time.strftime("%Y-%m-%d")
        if primero or (isinstance(tick, int) and tick % CALENDARIO_CADA == 0):
            vendedores_nuevos(b, est, menus)
            leer_calendario(b, est)
        if primero:
            limpiar_hilos(b, est, vivo)
        toca = primero or (isinstance(tick, int) and tick % RASTRO_CADA == 0)
        lectura, me = leer(b, est, tick, con_tablon=toca)
        lectura["dia"] = dia
        lectura["t_hours"], lectura["tick_segundos"] = t_horas, tick_segundos   # la hora de juego, para el Ojeador
        plan = situacion.plan({"efectivo": lectura["efectivo"], "cuenta": lectura["cuenta"],
                               "tick_segundos": tick_segundos}, precios_venta=precios_de_venta(menus) or None)
        if primero:
            print(situacion.resumen(plan))
        acciones = cadena.tick(lectura, mem, plan["p"], plan["forzar"], plan["ordenes"], stop)
        for linea in acciones["diario"]:
            print(linea)
            _linea("diario.jsonl", {"linea": linea, "vivo": vivo})
        aplicar(b, acciones, est, lectura, me, vivo)
        soltar_mudos(b, est, lectura, vivo)
        if not stop and not abrir_sobres(b, me, vivo):           # tras abrir un sobre las cartas cambian: al tick siguiente
            tratos = cadena.tratos_de_hoy(mem, dia)
            abrir(b, me, est, plan, vivo, menus, tratos, mem=mem, lectura=lectura)
            if toca:
                anunciar(b, me, est, plan, tick, vivo, menus, tratos, primero, mem=mem, lectura=lectura)
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
    est = _json(os.path.join(RUNS, "jugar.json"), {"hilos": {}})
    mem = cadena.Memoria.de_dict(_json(os.path.join(RUNS, "memoria.json"), {}))
    print("EN VIVO" if a.live else "EN SECO: no se manda ni se acepta nada")
    if a.live:                                                   # un solo programa acepta a la vez (t7/candado.py)
        ok, motivo = candado.tomar(candado.RUTA, "jugar.py")
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
        t0 = time.time()
        seg = reloj.get("tick_seconds")
        hecho = un_tick(b, est, mem, tick, seg, a.live, os.path.exists(os.path.join(RUNS, "STOP")),
                        primero=hechos == 1, t_horas=reloj.get("t_hours"))
        try:
            _guardar(os.path.join(RUNS, "jugar.json"), est)
            _guardar(os.path.join(RUNS, "memoria.json"), mem.a_dict())
        except Exception as e:
            print("ERROR        no se pudo guardar el estado:", e)
        tardo = time.time() - t0
        if hecho and isinstance(seg, (int, float)) and tardo > 0.6 * seg:   # el latido rápido: avisar si no llegamos
            print(f"LENTO        el tick tardó {tardo:.1f} s de {seg} s: hay riesgo de saltarse ticks")


if __name__ == "__main__":
    main()
