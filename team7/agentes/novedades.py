"""Novedades: qué ha cambiado en el juego desde la última foto, y qué proponemos hacer con cada cambio.

Sin red y sin azar. `vigia.py` hace las lecturas (solo GET) y llama aquí:

    foto(lecturas)            → lo que importa de clock, schedule, levels, dealers, catalog, venues y me, ya resumido
    comparar(antes, ahora)    → la lista de novedades
    consejo(novedad, ctx)     → qué proponemos hacer, en frases cortas (reglas fijas, las mismas de "Los agentes")
    informe(novedades, ctx)   → el texto para la pantalla y para runs/novedades.jsonl

No sabemos la forma exacta de todas las respuestas del juego: se leen con tolerancia. Lo que no se entiende no se
inventa: sale como "ha cambiado, mirar el crudo".
"""
import json

from . import guion, params, situacion
from . import valor as V

VOLATIL = ("in_", "eta", "remaining", "countdown", "status", "now", "minted", "activity", "volume", "trades", "count")
CAMPOS_TICK = ("tick", "at_tick", "start_tick", "starts_at_tick", "opens_at_tick", "open_tick", "at")
AVISO_TICKS = 20          # avisar cuando algo del calendario empieza en estos ticks o menos
SALTO_EFECTIVO = 100      # una subida así de golpe es dinero de la organización, no un trato
SALTO_PUESTO = 3
NOMBRE = {"schedule": "calendario", "levels": "nivel", "dealers": "vendedor", "venues": "mercado"}


def _listas(res):
    """[(grupo, elemento)]: los diccionarios que haya en una lista, o en las listas de un diccionario."""
    if isinstance(res, list):
        return [("", x) for x in res if isinstance(x, dict)]
    out = []
    if isinstance(res, dict):
        for k, v in res.items():
            if isinstance(v, list):
                out += [(str(k), x) for x in v if isinstance(x, dict)]
    return out


def _estable(it):
    """Los datos sencillos de un elemento, sin lo que cambia en cada tick (cuentas atrás, actividad)."""
    out = {}
    for k, v in it.items():
        if any(s in str(k).lower() for s in VOLATIL):
            continue
        if isinstance(v, str):
            out[k] = v[:200]
        elif isinstance(v, (int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, list) and all(isinstance(x, (str, int, float)) for x in v):
            out[k] = v[:12]
    return out


def _clave(it):
    for k in ("id", "ref", "key", "slug"):
        if it.get(k) is not None:
            return str(it[k])
    return json.dumps(_estable(it), sort_keys=True, ensure_ascii=False, default=str)[:160]


def foto(lecturas):
    """lecturas = {"clock", "schedule", "levels", "dealers", "catalog", "venues", "me"}: cada una, la respuesta del
    juego o None si no se pudo leer. Una lectura que falta no borra lo que se sabía: se compara solo lo leído."""
    f = {}
    reloj = lecturas.get("clock") if isinstance(lecturas.get("clock"), dict) else None
    f["reloj"] = None if reloj is None else {"tick": reloj.get("tick"), "ritmo": reloj.get("tick_seconds"),
                                              "pausa": bool(reloj.get("paused")),
                                              "limites": reloj.get("limits") if isinstance(reloj.get("limits"), dict) else {}}
    for nombre in NOMBRE:
        res = lecturas.get(nombre)
        f[nombre] = None if res is None else {(f"{g}|{_clave(x)}" if g else _clave(x)): _estable(x) for g, x in _listas(res)}
    cal = lecturas.get("schedule")
    f["ahora_h"] = cal.get("now_hours") if isinstance(cal, dict) else None    # el calendario real va en horas de juego
    cat = lecturas.get("catalog")
    f["barrios"] = None if not isinstance(cat, dict) else {
        str(s.get("id")): str(s.get("name") or s.get("id")) for s in cat.get("sets") or [] if isinstance(s, dict) and s.get("id")}
    me = lecturas.get("me")
    if not isinstance(me, dict):
        f["me"] = None
    else:
        bienes = [a for a in me.get("assets") or [] if isinstance(a, dict)]
        f["me"] = {"efectivo": me.get("cash"), "nivel": me.get("level"),
                   "abiertos": sorted(str(x) for x in me.get("unlocked") or []),
                   "sobres": sum(1 for a in bienes if a.get("kind") == "pack"),
                   "puesto": (me.get("score") or {}).get("rank") if isinstance(me.get("score"), dict) else None,
                   "congelado": bool(me.get("frozen")),
                   "afinidad": me.get("affinity") if isinstance(me.get("affinity"), dict) else {}}
    f["avisados"] = []
    return f


def _tick_de(item):
    for k in CAMPOS_TICK:
        if isinstance(item.get(k), (int, float)) and not isinstance(item.get(k), bool):
            return item[k]
    return None


def comparar(antes, ahora):
    """Las novedades entre dos fotos: [{"tipo", "titulo", "dato"}]. Con antes = None, una sola: la foto inicial."""
    if not antes:
        me, reloj = ahora.get("me") or {}, ahora.get("reloj") or {}
        return [{"tipo": "inicio", "titulo": "Primera foto del juego", "dato": {
            "tick": reloj.get("tick"), "segundos por tick": reloj.get("ritmo"), "efectivo": me.get("efectivo"),
            "nivel": me.get("nivel"), "vendedores": len(ahora.get("dealers") or {}), "barrios": sorted(ahora.get("barrios") or {}),
            "calendario": len(ahora.get("schedule") or {})}}]
    nov = []
    ra, rh = antes.get("reloj"), ahora.get("reloj")
    if ra and rh:
        if rh["ritmo"] != ra["ritmo"] and rh["ritmo"] is not None:
            nov.append({"tipo": "ritmo", "titulo": f"El tick pasa de {ra['ritmo']} s a {rh['ritmo']} s", "dato": rh["ritmo"]})
        if rh["pausa"] != ra["pausa"]:
            nov.append({"tipo": "pausa", "titulo": "El juego está en pausa" if rh["pausa"] else "El juego vuelve a andar", "dato": rh["pausa"]})
        cambios = {k: [ra["limites"].get(k), v] for k, v in rh["limites"].items() if ra["limites"].get(k) != v}
        if cambios and ra["limites"]:
            nov.append({"tipo": "limites", "titulo": "Cambian los límites del juego: " +
                        ", ".join(f"{k} {a} → {b}" for k, (a, b) in cambios.items()), "dato": cambios})
    for nombre, tipo in NOMBRE.items():
        a, h = antes.get(nombre), ahora.get(nombre)
        if a is None or h is None:
            continue
        for clave in h:
            if clave not in a:
                grupo = clave.split("|", 1)[0] if "|" in clave else ""
                etiqueta = h[clave].get("name") or h[clave].get("title") or h[clave].get("kind") or h[clave].get("type") or clave
                nov.append({"tipo": tipo, "titulo": f"Nuevo en {tipo}" + (f" ({grupo})" if grupo else "") + f": {etiqueta}",
                            "dato": h[clave], "grupo": grupo})
    if antes.get("barrios") is not None and ahora.get("barrios") is not None:
        for b, nombre in ahora["barrios"].items():
            if b not in antes["barrios"]:
                nov.append({"tipo": "barrio", "titulo": f"Barrio nuevo: {nombre} ({b})", "dato": b})
    ma, mh = antes.get("me"), ahora.get("me")
    if ma and mh:
        ea, eh = ma.get("efectivo"), mh.get("efectivo")
        if isinstance(ea, (int, float)) and isinstance(eh, (int, float)) and eh - ea >= SALTO_EFECTIVO:
            nov.append({"tipo": "dinero", "titulo": f"El efectivo sube de {ea:.0f} a {eh:.0f} P de golpe", "dato": eh})
        if mh.get("nivel") != ma.get("nivel") and mh.get("nivel") is not None:
            nov.append({"tipo": "subimos", "titulo": f"Pasamos del nivel {ma.get('nivel')} al {mh.get('nivel')}", "dato": mh.get("nivel")})
        for v in mh["abiertos"]:
            if v not in ma["abiertos"]:
                nov.append({"tipo": "abierto", "titulo": f"Ya podemos tratar con {v}", "dato": v})
        if mh["sobres"] > ma["sobres"]:
            nov.append({"tipo": "sobre", "titulo": f"Tenemos {mh['sobres'] - ma['sobres']} sobre(s) nuevo(s) sin abrir", "dato": mh["sobres"]})
        pa, ph = ma.get("puesto"), mh.get("puesto")
        if isinstance(pa, (int, float)) and isinstance(ph, (int, float)) and abs(ph - pa) >= SALTO_PUESTO:
            nov.append({"tipo": "puesto", "titulo": f"Pasamos del puesto {pa:.0f}.º al {ph:.0f}.º", "dato": ph})
        if mh["congelado"] and not ma["congelado"]:
            nov.append({"tipo": "congelado", "titulo": "El juego nos ha congelado la cuenta", "dato": True})
    # lo que está a punto de empezar: se avisa una vez
    avisados = list(antes.get("avisados") or [])
    tick = (rh or {}).get("tick")
    if isinstance(tick, (int, float)):
        for clave, item in (ahora.get("schedule") or {}).items():
            t = _tick_de(item)
            if t is not None and 0 < t - tick <= AVISO_TICKS and clave not in avisados:
                avisados.append(clave)
                etiqueta = item.get("name") or item.get("title") or item.get("kind") or item.get("type") or clave
                nov.append({"tipo": "pronto", "titulo": f"Empieza en {t - tick:.0f} ticks: {etiqueta}", "dato": item})
    # el calendario real (/api/schedule) va en horas (at_hours / now_hours): cada jugada de guion.py dice con
    # cuántas horas de antelación hay que prepararla (2 h una fiebre, 1,5 h el cierre de un vendedor, 30 min un duelo)
    h = ahora.get("ahora_h")
    if isinstance(h, (int, float)):
        for clave, item in (ahora.get("schedule") or {}).items():
            if not isinstance(item.get("at_hours"), (int, float)) or clave in avisados:
                continue
            j = guion.jugada(_evento(item))
            falta = item["at_hours"] - h
            if 0 < falta <= j["aviso_h"]:
                avisados.append(clave)
                nov.append({"tipo": "pronto", "titulo": f"Empieza en {falta * 60:.0f} min: {j['titulo']}", "dato": item})
    ahora["avisados"] = avisados
    return nov


def _texto(dato):
    return json.dumps(dato, ensure_ascii=False, default=str).lower()


def _evento(item):
    """Un elemento del calendario (ya resumido por _estable, sin params) en la forma que entiende guion.jugada."""
    return {"h": item.get("at_hours") or 0, "accion": str(item.get("action") or ""), "nota": str(item.get("note") or ""),
            "params": item.get("params") if isinstance(item.get("params"), dict) else {}, "wall": item.get("wall")}


def _de_calendario(dato, ctx):
    if isinstance(dato, dict) and dato.get("action"):
        j = guion.jugada(_evento(dato))
        if j["clave"] != "otro":
            return j["antes"] + j["durante"]
    t = _texto(dato)
    if "duel" in t:
        out = ["Antes de la sesión: no abrir regateos nuevos con vendedores 2 o 3 ticks antes; los duelos se llevan la única aceptación del tick.",
               "Mirar el primer duelo en runs/crudo.jsonl: rondas y descuento reales van a hoy.json (\"duelo\")."]
        if "day" in t or "two" in t or "issue" in t:
            out.append("Es con día de entrega: la Duelista ya manda siempre un día. Comprobar en el crudo cómo llega your_days_weight.")
        return out
    if "bench" in t or "market" in t or "test" in t:
        return ["Market Test: lanzar el grabador antes de que empiece. Sin mercado propio puntúa el puesto gratuito."]
    if "dealer" in t or "vendedor" in t:
        return _CONSEJOS["vendedor"](dato, ctx)
    if "set" in t or "release" in t or "barrio" in t:
        return ["Sale un barrio: en cuanto aparezca en el catálogo, este vigía dirá si nos conviene según nuestro multiplicador."]
    return ["Novedad del calendario que no sabemos clasificar: leerla y decidir."]


def _de_vendedor(dato, ctx):
    return ["Pegar su menú en menus.json: sin él, no se le abre ninguna conversación.",
            "Primera conversación = sondeo: apertura prudente (15 %), apuntar cuánto imita nuestros pasos y en qué ronda da la final.",
            "Bastan 3 tratos regateados con lo más barato: solo cuentan los tres mejores, y los vendedores de nivel alto pesan más.",
            "Sin preguntas del Espía hasta tener esos 3 tratos."]


def _de_barrio(dato, ctx):
    m = (ctx.get("afinidad") or {}).get(dato, V.NUESTROS_MULT.get(dato))
    if m is None:
        return [f"No sabemos nuestro multiplicador de {dato}: leer me()[\"affinity\"] antes de comprar nada de ese barrio."]
    if m >= 1.3:
        return [f"{dato} nos vale mucho (× {m}): comprar comunes y poco comunes regateando; sus primeras copias quedan protegidas.",
                "Las raras solo salen de sobres o de otros equipos: pedirlas en El Rastro."]
    if m <= 0.7:
        return [f"{dato} nos vale poco (× {m}): no comprar. Lo que salga en sobres se vende a quien lo tenga alto."]
    return [f"{dato} nos vale normal (× {m}): comprar solo lo justo para los 3 tratos regateados de cada vendedor."]


def _de_dinero(dato, ctx):
    p = ctx.get("p") or params.cargar()
    modo, libre = situacion.modo_caja(dato, p)
    out = [f"Caja {modo}: {libre:.0f} P libres sobre la reserva de {p['guardia.reserva_efectivo']} P."]
    if dato >= situacion.RESERVA_MERCADO:
        out.append(f"Llega para abrir mercado propio ({situacion.RESERVA_MERCADO} P). Solo si el broker supera al puesto gratuito "
                   "con libros reales; si se decide, poner \"guardar_para_mercado\": true en hoy.json.")
    return out


_CONSEJOS = {
    "inicio": lambda d, c: ["Es la foto de partida: a partir de ahora se avisa de cada cambio."],
    "ritmo": lambda d, c: [f"El programa que juega lee el ritmo del juego. Con ticks de {d} s, vigilar la línea LENTO en su pantalla.",
                           "La espera de una persona se cuenta en segundos, no en ticks: no hay que tocar nada."],
    "pausa": lambda d, c: ["Con el juego en pausa no hay ticks: buen momento para ajustar hoy.json y menus.json."] if d else
                          ["Comprobar que el programa que juega sigue en marcha y que hoy.json está al día."],
    "limites": lambda d, c: ["Revisar en el programa que juega los límites de conversaciones, anuncios por tick y ofertas abiertas."],
    "calendario": _de_calendario,
    "pronto": _de_calendario,
    "nivel": lambda d, c: guion.sin_anunciar((d or {}).get("kind") or (d or {}).get("type") if isinstance(d, dict) else None)["antes"],
    "vendedor": _de_vendedor,
    "abierto": _de_vendedor,
    "mercado": lambda d, c: ["Otro mercado abierto. Si su comisión es menor que la de El Rastro (5 % + 1 P), nuestras ventas rinden más ahí.",
                             "Apuntar quién lo abre: es dato para decidir si abrimos el nuestro."],
    "barrio": _de_barrio,
    "dinero": _de_dinero,
    "subimos": lambda d, c: ["Hay un vendedor más para nosotros: ver su aviso.", "Desde el nivel 2 se puede abrir mercado propio."],
    "sobre": lambda d, c: ["Abrirlo antes de comprar, para no comprar una carta que venía dentro. Hay que hacerlo al arrancar."],
    "puesto": lambda d, c: ["El puesto depende también de los demás. Mirar qué bloque ha cambiado antes de tocar nada."],
    "congelado": lambda d, c: ["Parar la cadena (runs/STOP) y preguntar en la mesa de organización."],
}


def consejo(novedad, ctx=None):
    """Qué proponemos hacer con esta novedad: lista de frases. ctx = {"afinidad": {...}, "p": ajustes} (opcional)."""
    f = _CONSEJOS.get(novedad["tipo"])
    return f(novedad.get("dato"), ctx or {}) if f else ["Ha cambiado algo que no sabemos leer: mirar runs/vigia-crudo.json."]


def informe(novedades, ctx=None):
    """El texto para la pantalla: cada novedad con lo que proponemos."""
    lineas = []
    for n in novedades:
        lineas.append(f"NOVEDAD      {n['titulo']}")
        if n["tipo"] in ("calendario", "nivel", "vendedor", "mercado", "pronto", "inicio") and n.get("dato"):
            lineas.append("             " + json.dumps(n["dato"], ensure_ascii=False, default=str)[:300])
        lineas += ["  PROPUESTA  " + c for c in consejo(n, ctx)]
    return "\n".join(lineas)
