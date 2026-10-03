"""La calculadora: cuánto nos vale cada cosa y si un trato renta.

Fórmula (medida con nuestras cartas, al céntimo):
    valor de una copia = base de la rareza × multiplicador del barrio × factor de copia (1 · 0,25 · 0,1)
    bono de página      = 25 % de la suma de las 10 primeras copias (5 comunes, 3 poco comunes, 2 raras)
                          + 10 % más si además están la épica y la legendaria (supuesto)
    valor de la colección = suma de copias + bonos

El valor de una carta concreta es MARGINAL: lo que la colección gana al recibirla o pierde al darla.
Así salen solos los casos difíciles: la repetida que vale 2,8, la carta que completa una página (+106 en La Latina),
o la carta que rompe una página completa (Lavapiés: 83,9 una común).
"""
import math

BASE = {"common": 10, "uncommon": 25, "rare": 70, "epic": 180, "legendary": 450}
FACTOR_COPIA = [1.0, 0.25]          # la tercera copia y siguientes: 0,1
FACTOR_RESTO = 0.1
NUESTROS_MULT = {"LAT": 1.6, "RET": 1.3, "LAV": 1.1, "CHA": 0.9, "SAL": 0.7, "MAL": 0.5}
PAGINA = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10"]
RAREZAS = {}                        # ref → rareza leída del juego (catálogo y nuestras cartas). Manda sobre el número.
TIRADA = {300: "common", 90: "uncommon", 30: "rare", 9: "epic", 3: "legendary"}


def _num(ref):
    """El número de la carta dentro de su barrio ("LAT-09" → 9). None si el código no tiene esa forma."""
    try:
        return int(str(ref).split("-")[1])
    except (IndexError, ValueError):
        return None


def rareza(ref):
    """Lo que diga el juego (RAREZAS). Si no lo sabemos, por el número: 01..05 comunes, 06..08 poco comunes,
    09..10 raras, 11 épica, 12 legendaria (comprobado con La Latina y Lavapiés). Un código que no se entiende
    cuenta como común, lo más barato, para no pagar nunca de más; conocida() dice que con esa carta no se opera."""
    if ref in RAREZAS:
        return RAREZAS[ref]
    n = _num(ref)
    if n is None:
        return "common"
    return "common" if n <= 5 else "uncommon" if n <= 8 else "rare" if n <= 10 else "epic" if n == 11 else "legendary"


def barrio(ref):
    return str(ref).split("-")[0]


def conocida(ref, mult=NUESTROS_MULT):
    """¿Sabemos cuánto nos vale esta carta? Hace falta el multiplicador de su barrio y una rareza (del juego o del número).
    Regla del día: conocer el valor ANTES de comprar. Con una carta no conocida no se abre ni se sigue ningún trato."""
    return barrio(ref) in mult and (ref in RAREZAS or _num(ref) is not None)


def pagina(b):
    """Las cartas que forman la página de un barrio: sus comunes, poco comunes y raras. Con el catálogo del juego,
    las que diga el catálogo; sin él, las diez primeras."""
    del_juego = sorted(r for r, x in RAREZAS.items() if barrio(r) == b and x in ("common", "uncommon", "rare"))
    return del_juego if len(del_juego) >= len(PAGINA) else [f"{b}-{x}" for x in PAGINA]


def _extras(b):
    """La épica y la legendaria del barrio (dan el 10 % extra con la página completa)."""
    del_juego = sorted(r for r, x in RAREZAS.items() if barrio(r) == b and x in ("epic", "legendary"))
    return del_juego if len(del_juego) >= 2 else [f"{b}-11", f"{b}-12"]


def _leer_afinidad(a):
    """Nuestros multiplicadores tal como los da me()["affinity"], en la forma que vengan. {} si no se entienden."""
    def numero(x):
        if isinstance(x, dict):
            x = next((x[k] for k in ("multiplier", "mult", "value", "affinity") if k in x), None)
        return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and 0 < x < 10 else None

    pares = []
    if isinstance(a, dict):
        pares = list(a.items())
    elif isinstance(a, list):
        pares = [(next((x[k] for k in ("set", "id", "code") if k in x), None), x) for x in a if isinstance(x, dict)]
    return {str(k): numero(v) for k, v in pares if k is not None and numero(v) is not None}


def _leer_catalogo(cat):
    """{ref: rareza} sacado de catalog(): por el campo rarity, por el valor base (book) o por la tirada."""
    sets = (cat or {}).get("sets") if isinstance(cat, dict) else None
    sets = list(sets.values()) if isinstance(sets, dict) else sets if isinstance(sets, list) else []
    por_base, out = {v: k for k, v in BASE.items()}, {}
    for s in sets:
        for c in (s.get("cards") or []) if isinstance(s, dict) else []:
            if not isinstance(c, dict):
                continue
            ref = c.get("id", c.get("ref"))
            r = c.get("rarity") if c.get("rarity") in BASE else por_base.get(c.get("book")) or TIRADA.get(c.get("print_run"))
            if isinstance(ref, str) and r:
                out[ref] = r
    return out


def configurar(afinidad=None, catalogo=None, cartas=None):
    """Pone los datos del juego en lugar de los supuestos: multiplicadores (me()["affinity"]), rarezas (catalog())
    y las rarezas de las cartas que tenemos (me()["assets"]). No lanza nunca: devuelve los avisos para el diario.

    Los multiplicadores se cambian EN el diccionario NUESTROS_MULT, que es el que usan todas las funciones."""
    avisos = []
    m = _leer_afinidad(afinidad)
    if m:
        for k, v in sorted(m.items()):
            if NUESTROS_MULT.get(k) != v:
                avisos.append(f"multiplicador de {k}: {NUESTROS_MULT.get(k, 'sin dato')} → {v} (dato del juego)")
        NUESTROS_MULT.update(m)
    elif afinidad is not None:
        avisos.append("multiplicadores: no se entiende lo que da el juego; se usan los supuestos")
    nuevas = _leer_catalogo(catalogo)
    if catalogo is not None and not nuevas:
        avisos.append("catálogo: no se entiende; la rareza sale del número de la carta")
    for c in cartas or []:
        if isinstance(c, dict) and isinstance(c.get("ref"), str) and c.get("rarity") in BASE:
            nuevas[c["ref"]] = c["rarity"]
    for ref, r in sorted(nuevas.items()):
        if _num(ref) is not None and ref not in RAREZAS and rareza(ref) != r:
            avisos.append(f"{ref}: el juego dice {r}; por el número habríamos supuesto {rareza(ref)}")
        RAREZAS[ref] = r
    for b in sorted({barrio(r) for r in nuevas} - set(NUESTROS_MULT)):
        avisos.append(f"barrio {b}: no tenemos multiplicador; no se opera con sus cartas")
    return avisos


def factor(n_copia):
    """n_copia empieza en 1: la primera copia vale entera."""
    return FACTOR_COPIA[n_copia - 1] if n_copia <= len(FACTOR_COPIA) else FACTOR_RESTO


def valor_coleccion(cuenta, mult=NUESTROS_MULT, bono=0.25, bono_extra=0.10):
    """cuenta = {ref: copias}. Devuelve el valor total para nosotros."""
    total, barrios = 0.0, {}
    for ref, n in cuenta.items():
        if n <= 0:
            continue
        b = barrio(ref)
        unidad = BASE[rareza(ref)] * mult.get(b, 1.0)
        total += unidad * sum(factor(i) for i in range(1, n + 1))
        barrios.setdefault(b, set()).add(ref)
    for b, tengo in barrios.items():
        pag = pagina(b)
        if all(r in tengo for r in pag):
            suma = sum(BASE[rareza(r)] * mult.get(b, 1.0) for r in pag)
            total += bono * suma
            if all(r in tengo for r in _extras(b)):
                total += bono_extra * suma
    return total


def valor_recibir(cuenta, refs, mult=NUESTROS_MULT):
    """Lo que gana la colección si entran estas cartas."""
    nueva = dict(cuenta)
    for r in refs:
        nueva[r] = nueva.get(r, 0) + 1
    return valor_coleccion(nueva, mult) - valor_coleccion(cuenta, mult)


def valor_entregar(cuenta, refs, mult=NUESTROS_MULT):
    """Lo que pierde la colección si salen estas cartas. None si no las tenemos."""
    nueva = dict(cuenta)
    for r in refs:
        if nueva.get(r, 0) <= 0:
            return None
        nueva[r] -= 1
    return valor_coleccion(cuenta, mult) - valor_coleccion(nueva, mult)


def comision_rastro(precio, cartas, pct=0.05, por_carta=1):
    return math.ceil(precio * pct) + por_carta * cartas if precio or cartas else 0


def protegida(cuenta, ref, mult=NUESTROS_MULT):
    """No se vende nunca: primera copia de los tres barrios que más nos valen, o una carta que rompe una página completa."""
    if cuenta.get(ref, 0) <= 0:
        return False
    if cuenta[ref] >= 2:
        return False
    top3 = sorted(mult, key=mult.get, reverse=True)[:3]
    if barrio(ref) in top3:
        return True
    perdida = valor_entregar(cuenta, [ref], mult)
    propio = BASE[rareza(ref)] * mult.get(barrio(ref), 1.0)
    return perdida is not None and perdida > propio + 0.01


def estado_pagina(cuenta, b):
    """(cuántas cartas de la página tenemos, cuáles faltan)."""
    pag = pagina(b)
    faltan = [r for r in pag if cuenta.get(r, 0) <= 0]
    return len(pag) - len(faltan), faltan


def evaluar(propuesta, cuenta, efectivo, mult=NUESTROS_MULT, reserva=0):
    """La ficha de la calculadora para una propuesta.

    propuesta = {
      "tipo": "vendedor" | "equipo" | "duelo" | "sobre",
      "recibo": {"cartas": [refs], "primas": n},
      "entrego": {"cartas": [refs], "primas": n},
      "comision": n (opcional; si no, se calcula para El Rastro cuando "mercado" == "rastro" y pagamos nosotros),
      "mercado": "rastro" | "vendedor" | ...,  "pagamos_comision": bool,
      "apertura_rival": n, "suelo_estimado": n   (solo con vendedores: para la parte del rango capturada)
    }
    """
    rec, ent = propuesta.get("recibo", {}), propuesta.get("entrego", {})
    rc, rp = rec.get("cartas", []), rec.get("primas", 0) or 0
    ec, ep = ent.get("cartas", []), ent.get("primas", 0) or 0
    bloqueos, avisos = [], []

    v_rec = valor_recibir(cuenta, rc, mult) + rp
    perdida = valor_entregar(cuenta, ec, mult)
    if perdida is None:
        bloqueos.append("entregamos una carta que no tenemos")
        perdida = 0.0
    v_ent = perdida + ep

    com = propuesta.get("comision")
    if com is None:
        com = 0
        if propuesta.get("mercado") == "rastro" and propuesta.get("pagamos_comision"):
            precio = max(rp, ep)
            com = comision_rastro(precio, len(rc) + len(ec))
    neto = v_rec - v_ent - com

    for r in ec:
        if protegida(cuenta, r, mult):
            bloqueos.append(f"{r} está protegida")
    gasto = ep + com - rp
    if gasto > 0 and efectivo - gasto < reserva:      # una venta nunca rompe la reserva: la rellena
        bloqueos.append(f"rompe la reserva: quedarían {efectivo - gasto:.0f} P de {reserva}")
    if efectivo - ep - com < 0:
        bloqueos.append("no hay efectivo suficiente")

    despues = dict(cuenta)
    for r in rc:
        despues[r] = despues.get(r, 0) + 1
    for r in ec:
        despues[r] = despues.get(r, 0) - 1
    for b in sorted({barrio(r) for r in rc + ec}):
        a, _ = estado_pagina(cuenta, b)
        d, faltan = estado_pagina(despues, b)
        if d != a:
            avisos.append(f"{b}: {a} → {d} de 10" + (" · PÁGINA COMPLETA" if d == 10 else
                                                      f" · falta {len(faltan)}" if len(faltan) <= 2 else ""))

    tipo = propuesta.get("tipo", "equipo")
    puntos, captura = {
        "vendedor": "negociar · escalera de vendedores (parte del rango capturada)",
        "equipo": "negociar · valor ganado con equipos",
        "duelo": "negociar · duelos (parte de la tarta)",
        "sobre": "nada: lo que sale de un sobre es suerte",
    }.get(tipo, "negociar"), None
    ap, su = propuesta.get("apertura_rival"), propuesta.get("suelo_estimado")
    if tipo == "vendedor" and ap is not None and su is not None and ap != su:
        pagado = ep if ep else rp
        captura = (ap - pagado) / (ap - su) if ep else (pagado - ap) / (su - ap)

    return {
        "recibo": round(v_rec, 2), "entrego": round(v_ent, 2), "comision": com, "neto": round(neto, 2),
        "renta": neto > 0 and not bloqueos, "puntos": puntos, "captura": None if captura is None else round(captura, 3),
        "compromete": ep + com, "avisos": avisos, "bloqueos": bloqueos,
    }


def liquidez(cuenta, efectivo, precios, objetivo, mult=NUESTROS_MULT, rastro=False):
    """¿Conviene vender cartas pequeñas para tener más efectivo? Lo decide sola.

    precios  = {ref: primas que nos dan por una copia} (oferta del vendedor o anuncio de El Rastro)
    objetivo = efectivo que queremos tener (guardia.colchon_efectivo)

    Solo propone ventas que no pierden valor (lo cobrado, sin la comisión, ≥ lo que la carta nos vale),
    nunca una protegida y nunca una rara o mejor (esas las decide el equipo). Va de la que más gana a la que menos,
    recalculando tras cada venta: la tercera copia vale 0,1, la segunda 0,25, y la última vuelve a valer entera.
    "necesaria" marca las ventas que hacen falta para llegar al objetivo; el resto ganan valor pero pueden esperar.
    """
    actual, caja, ventas = dict(cuenta), efectivo, []
    while True:
        mejor = None
        for ref, precio in precios.items():
            if actual.get(ref, 0) <= 0 or rareza(ref) not in ("common", "uncommon") or protegida(actual, ref, mult):
                continue
            com = comision_rastro(precio, 1) if rastro else 0
            pierde = valor_entregar(actual, [ref], mult)
            neto = precio - com - pierde
            if neto >= 0 and (mejor is None or neto > mejor["neto"]):
                mejor = {"ref": ref, "precio": precio, "comision": com, "pierde": round(pierde, 2), "neto": round(neto, 2)}
        if mejor is None:
            break
        mejor["necesaria"] = caja < objetivo
        actual[mejor["ref"]] -= 1
        caja += mejor["precio"] - mejor["comision"]
        ventas.append(mejor)
    return {"efectivo": efectivo, "objetivo": objetivo, "falta": max(0, objetivo - efectivo), "ventas": ventas,
            "efectivo_final": caja, "gana": round(sum(v["neto"] for v in ventas), 2), "llega": caja >= objetivo}


def ficha(ev, titulo):
    """El texto que va al diario."""
    lineas = [f"OPERACIÓN    {titulo}",
              f"RECIBO       {ev['recibo']:.1f}",
              f"ENTREGO      {ev['entrego']:.1f}" + (f" + comisión {ev['comision']}" if ev['comision'] else ""),
              f"NETO         {ev['neto']:+.1f}  → {'RENTA' if ev['renta'] else 'NO RENTA'}",
              f"PUNTOS       {ev['puntos']}" + (f" · rango capturado {ev['captura']:.0%}" if ev.get('captura') is not None else "")]
    if ev["avisos"]:
        lineas.append("ÁLBUM        " + " | ".join(ev["avisos"]))
    lineas.append("BLOQUEOS     " + (" | ".join(ev["bloqueos"]) if ev["bloqueos"] else "ninguno"))
    return "\n".join(lineas)


def _de_rareza(b, r):
    """Las cartas de rareza r del barrio b: las del catálogo si se ha leído, si no por el número."""
    del_juego = sorted(x for x, y in RAREZAS.items() if barrio(x) == b and y == r)
    return del_juego or [f"{b}-{i:02d}" for i in range(1, 13) if rareza(f"{b}-{i:02d}") == r]


def ev_sobre(sobre, cuenta, precio=None, barrios=None, mult=NUESTROS_MULT):
    """Lo que vale para NOSOTROS un sobre, de media, antes de abrirlo. La suerte no puntúa: un sobre solo conviene
    si su valor medio a nuestros multiplicadores supera lo que pagamos.

    sobre   = un elemento de catalog()["packs"]: {"id", "slots": [{"common": 0.75, "uncommon": 0.25}, ...], "expected_book"}
    barrios = los barrios de los que puede salir (sobre de barrio: el elegido; si no, los ya publicados)
    Cada hueco se valora con la colección de ahora (aproximación: no suma lo que traen los otros huecos del mismo sobre).
    Devuelve {"id", "ev", "libro", "precio", "conviene", "detalle"}."""
    barrios = [b for b in (barrios or list(mult)) if b in mult]
    detalle, ev = [], 0.0
    for hueco in (sobre or {}).get("slots") or []:
        v_hueco = 0.0
        for r, prob in hueco.items():
            if r not in BASE or not isinstance(prob, (int, float)):
                continue
            medias = []
            for b in barrios:
                cartas = _de_rareza(b, r)
                if cartas:
                    medias.append(sum(valor_recibir(cuenta, [c], mult) for c in cartas) / len(cartas))
            v_hueco += prob * (sum(medias) / len(medias) if medias else 0.0)
        detalle.append(round(v_hueco, 1))
        ev += v_hueco
    return {"id": (sobre or {}).get("id"), "ev": round(ev, 1), "libro": (sobre or {}).get("expected_book"),
            "precio": precio, "conviene": None if precio is None else ev > precio, "detalle": detalle}
