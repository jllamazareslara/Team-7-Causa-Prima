"""Los Ojos: lo primero de cada tick. Lo ven todo, lo validan con la Contable y hacen la propuesta:
    1. ven      cómo estamos y las oportunidades (ofertas que venden lo que nos falta o piden lo que tenemos repetido)
    2. validan  cada oportunidad con la ficha de la Contable (`contable.ficha`: valor que entra y sale, comisión de
                El Rastro, reserva de caja, cartas protegidas) y el margen del equipo (guardia.margen_compra/venta)
    3. proponen las que pasan, la de más neto primero. Solo proponen: no aceptan nada, no pasan por el Guardia ni por
                el Escudo, y no leen el texto de nadie. Quien acepta es una persona del equipo.

Leen tres cosas del juego (solo GET, con `leer(b)`; las claves se tapan como en la skill estado-equipo):
    /api/me                    cómo estamos: dinero, puntos, álbum, repetidas (lo mismo que la skill estado-equipo)
    /api/feed                  lo que pasa: tratos hechos (precios) y avisos del juego (límites, vendedores, niveles)
    /api/me/offers + tablón    las ofertas: las nuestras, las que nos hacen y las de El Rastro

y entregan la `vista` con lo más importante:
    vista = {
      "estado":        {"efectivo", "puntos", "puesto", "negociar", "mercado", "faltan": {barrio: [cartas]},
                        "casi": [barrios a 1 o 2 cartas de completar], "repetidas": {carta: copias}},
      "comprar":       ofertas que VENDEN una carta que nos falta, primero las que completan página y luego las más baratas,
      "vender":        ofertas que PIDEN una carta que tenemos repetida, la de más margen sobre su your_value primero,
      "precios":       {carta: [precios de los tratos recientes del feed]},
      "avisos":        avisos nuevos del feed (cada uno una vez),
      "para_nosotros": ofertas que otros nos hacen a nosotros,
      "abiertas":      cuántas ofertas nuestras siguen abiertas (máx. 30),
      "propuestas":    lo que la Contable valida: [{"aceptar": oferta, "lado", "carta", "precio", "neto", "comision",
                        "avisos", "motivo"}], la de más neto primero,
      "descartadas":   lo que la Contable no valida, con el motivo,
    }
Lo que falte en la lectura se salta: la vista sale con lo que haya.
"""
import re
from collections import Counter

from . import contable, ojeador
from . import valor as V

TIPOS_TRATO = ("settle", "trade", "deal", "sale")
TIPOS_AVISO = ("limit", "unlock", "level", "dealer", "venue", "news", "bench", "duel", "release", "schedule", "rule")
MAX_LISTA = 8              # oportunidades de cada clase que se entregan
MAX_PRECIOS = 6            # precios recientes por carta


# ---------------------------------------------------------------- leer el juego (red, solo GET)

def tapar(x):
    """Quita cualquier clave: campos *key*/*token*/*secret* y valores tk-... / bk_... (igual que estado-equipo)."""
    if isinstance(x, dict):
        return {k: "<OCULTA>" if re.search("key|token|secret", k, re.I) else tapar(v) for k, v in x.items()}
    if isinstance(x, list):
        return [tapar(v) for v in x]
    if isinstance(x, str) and re.match(r"^(tk-|bk_)", x):
        return "<OCULTA>"
    return x


def leer(b, feed=True, tablon=True):
    """Lo que miran los Ojos, leído del juego. Solo GET: no abre, ofrece ni acepta nada. Una lectura que falla se
    deja en None y la vista sale sin ella."""
    def intenta(f):
        try:
            return tapar(f())
        except Exception:
            return None
    lectura = {"me": intenta(b.me), "mis_ofertas": intenta(b.my_offers)}
    if feed:
        lectura["feed"] = intenta(lambda: b.feed(limit=100))
    if tablon:
        res = intenta(lambda: b.board("rastro"))
        lectura["tablon"] = res.get("offers") if isinstance(res, dict) else res
    return lectura


# ---------------------------------------------------------------- mirar (sin red)

def _lista(x, *claves):
    if isinstance(x, dict):
        x = next((x[k] for k in claves if isinstance(x.get(k), list)), [])
    return [e for e in x or [] if isinstance(e, dict)]


def _ref(x):
    if isinstance(x, dict):
        x = x.get("ref") or x.get("card")
    return x.replace("card:", "") if isinstance(x, str) else None


def _numero(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def estado(me, cuenta=None):
    """Cómo estamos, de /api/me (como el resumen de la skill estado-equipo)."""
    me = me if isinstance(me, dict) else {}
    cartas = [a for a in _lista(me.get("assets")) if a.get("kind", "card") == "card" and _ref(a)]
    tengo = Counter(_ref(a) for a in cartas) if cartas else Counter(cuenta or {})
    s = me.get("score") if isinstance(me.get("score"), dict) else {"score": me.get("score")}
    faltan, casi = {}, []
    for p in _lista(me.get("album"), "pages"):
        barrio = p.get("set")
        if not isinstance(barrio, str) or p.get("complete"):
            continue
        faltan[barrio] = [f"{barrio}-{n:02d}" for n in range(1, (p.get("of") or 10) + 1) if tengo[f"{barrio}-{n:02d}"] == 0]
        if 0 < len(faltan[barrio]) <= 2:
            casi.append(barrio)
    valores = {}                                    # carta → your_value de nuestra copia que menos nos vale
    for a in cartas:
        v = _numero(a.get("your_value"))
        if v is not None:
            valores[_ref(a)] = min(v, valores.get(_ref(a), v))
    return {"efectivo": me.get("cash"), "puntos": s.get("score"), "puesto": s.get("rank", me.get("rank")),
            "negociar": s.get("negotiating"), "mercado": s.get("market"),
            "faltan": faltan, "casi": sorted(casi), "repetidas": {r: n for r, n in sorted(tengo.items()) if n > 1},
            "_valores": valores, "_cuenta": dict(tengo)}


def _vende_una(o):
    """(carta, precio) si la oferta vende UNA carta por efectivo."""
    give, want = o.get("give") or {}, o.get("want") or {}
    cartas, pide = give.get("assets") or [], want.get("cards") or want.get("types") or want.get("assets") or []
    if len(cartas) == 1 and not pide and _numero(want.get("cash")) and want["cash"] > 0:
        return _ref(cartas[0]), want["cash"]
    return None, None


def _pide_una(o):
    """(carta, precio) si la oferta ofrece efectivo por UNA carta."""
    give, want = o.get("give") or {}, o.get("want") or {}
    pide = want.get("cards") or want.get("types") or want.get("assets") or []
    if len(pide) == 1 and not give.get("assets") and _numero(give.get("cash")) and give["cash"] > 0:
        return _ref(pide[0]), give["cash"]
    return None, None


def oportunidades(ofertas, est):
    """De las ofertas de otros: qué nos conviene comprar (nos falta) y a quién vender (lo tenemos repetido)."""
    falta = {c: b for b, cs in est["faltan"].items() for c in cs}
    comprar, vender = [], []
    for o in ofertas:
        carta, precio = _vende_una(o)
        if carta in falta:
            completa = len(est["faltan"][falta[carta]]) == 1
            comprar.append({"oferta": o.get("id"), "carta": carta, "precio": precio, "completa_pagina": completa,
                            "de": o.get("maker"), "oferta_juego": o})
        carta, precio = _pide_una(o)
        if carta in est["repetidas"]:
            nos_vale = est["_valores"].get(carta)
            vender.append({"oferta": o.get("id"), "carta": carta, "precio": precio, "nos_vale": nos_vale,
                           "margen": round(precio - nos_vale, 2) if nos_vale is not None else None, "de": o.get("maker"),
                           "oferta_juego": o})
    comprar.sort(key=lambda x: (not x["completa_pagina"], x["precio"], str(x["oferta"])))
    vender.sort(key=lambda x: (-(x["margen"] if x["margen"] is not None else x["precio"]), str(x["oferta"])))
    return comprar[:MAX_LISTA], vender[:MAX_LISTA]


def eventos(feed):
    """Los eventos del feed, planos. El juego los da como {"id", "tick", "type", "payload": {...}}; un trato
    ("settlement") lleva payload.items[] (las cartas) y payload.price. Se sube lo del payload al evento y, si el trato
    es de UNA carta, su ref, para que el Ojeador lo entienda."""
    planos = []
    for e in _lista(feed, "events", "feed", "items"):
        pl = e.get("payload") if isinstance(e.get("payload"), dict) else {}
        plano = dict(pl, **{k: v for k, v in e.items() if k != "payload"})
        cartas = [x for x in pl.get("items") or [] if isinstance(x, dict) and x.get("kind", "card") == "card"]
        if len(cartas) == 1 and not plano.get("ref"):
            plano["ref"] = cartas[0].get("ref")
        planos.append(plano)
    return planos


def validar(comprar, vender, cuenta, efectivo, p):
    """La Contable valida cada oportunidad con su ficha. Pasa si renta (neto > 0, sin bloqueos: reserva, protegida,
    caja) y el neto llega al margen del equipo sobre el valor de la carta. Devuelve (propuestas, descartadas)."""
    propuestas, descartadas = [], []
    for lado, lista in (("compra", comprar), ("venta", vender)):
        for o in lista:
            carta, precio = o["carta"], o["precio"]
            if not V.conocida(carta):
                descartadas.append(dict(o, lado=lado, motivo="carta sin valor conocido"))
                continue
            if lado == "compra":
                prop = {"tipo": "equipo", "recibo": {"cartas": [carta]}, "entrego": {"primas": precio}}
            else:
                prop = {"tipo": "equipo", "recibo": {"primas": precio}, "entrego": {"cartas": [carta]}}
            prop = dict(prop, mercado="rastro", pagamos_comision=True)
            ev = contable.ficha(prop, cuenta, efectivo, p)
            exigido = p["guardia.margen_compra"] * ev["cartas_recibo"] + p["guardia.margen_venta"] * ev["cartas_entrego"]
            neto = ev["neto"]
            juego = (V.VALOR_RECIBIR if lado == "compra" else V.VALOR_DAR).get(carta)
            if juego is not None:                       # el your_value del juego manda si es más prudente
                neto_juego = (juego - precio if lado == "compra" else precio - juego) - ev["comision"]
                margen = p["guardia.margen_compra"] if lado == "compra" else p["guardia.margen_venta"]
                neto, exigido = min(neto, neto_juego), max(exigido, margen * juego)
            fila = {"aceptar": o["oferta"], "lado": lado, "carta": carta, "precio": precio, "neto": round(neto, 2),
                    "comision": ev["comision"], "your_value": juego, "avisos": ev["avisos"], "de": o.get("de"),
                    "propuesta": prop, "oferta_juego": o.get("oferta_juego")}
            if ev["bloqueos"]:
                descartadas.append(dict(fila, motivo="; ".join(ev["bloqueos"])))
            elif neto <= 0 or neto < exigido:
                descartadas.append(dict(fila, motivo=f"no renta lo bastante (neto {neto:+.1f}, pide {exigido:+.1f})"))
            else:
                propuestas.append(dict(fila, motivo=f"neto {neto:+.1f} (pide {exigido:+.1f})"
                                       + (f" · {', '.join(ev['avisos'])}" if ev["avisos"] else "")))
    propuestas.sort(key=lambda x: (-x["neto"], str(x["aceptar"])))
    return propuestas, descartadas


def tratos(mem):
    """{carta: precio del último trato hecho} que los Ojos han visto en el feed (guardado en mem.historial)."""
    out = {}
    for ref, xs in (getattr(mem, "historial", None) or {}).items():
        hechos = [x for x in xs if len(x) > 2 and x[2] == "trato" and _numero(x[1])]
        if hechos:
            out[ref] = max(hechos, key=lambda x: x[0] if _numero(x[0]) is not None else -1)[1]
    return out


def mejor_propuesta(vista, lado, carta):
    """La mejor propuesta validada de los Ojos para esa carta en ese lado ("compra" / "venta"), o None."""
    return next((x for x in (vista or {}).get("propuestas") or [] if x["lado"] == lado and x["carta"] == carta), None)


def avisos(feed, mem):
    """Los avisos del juego en el feed (no los tratos), cada uno una vez."""
    nuevos = []
    for e in eventos(feed):
        tipo = str(e.get("type") or e.get("kind") or "").lower()
        if not tipo or any(k in tipo for k in TIPOS_TRATO) or not any(k in tipo for k in TIPOS_AVISO):
            continue
        clave = f"aviso|{e.get('id', (tipo, e.get('tick')))}"
        if mem.vistos.get(clave):
            continue
        mem.vistos[clave] = 1
        texto = e.get("text") or e.get("message") or e.get("summary") or             " · ".join(f"{k} {v}" for k, v in e.items() if k not in ("id", "tick", "t", "type", "scope", "actor", "kind")
                       and isinstance(v, (str, int, float)))
        nuevos.append({"tipo": tipo, "tick": e.get("tick"), "texto": str(texto)[:160]})
    return nuevos


def mirar(lectura, mem, apunta=None, p=None):
    """La vista del tick: cómo estamos, las mejores oportunidades y, validadas por la Contable, las propuestas.
    Sin `p` (los parámetros del equipo) no se valida nada. Tolera piezas rotas: lo que no se entiende se salta."""
    apunta = apunta or (lambda *_: None)
    est = estado(lectura.get("me"), lectura.get("cuenta"))
    if est["efectivo"] is None:
        est["efectivo"] = lectura.get("efectivo")
    mias = _lista(lectura.get("mis_ofertas"), "offers")
    me = lectura.get("me") if isinstance(lectura.get("me"), dict) else {}
    somos = {str(x) for x in (me.get("id"), me.get("name"), me.get("team")) if x}
    para_nosotros = [{"oferta": o.get("id"), "de": o.get("maker"), "da": o.get("give"), "pide": o.get("want")}
                     for o in mias if o.get("to") and str(o.get("to")) in somos and str(o.get("maker")) not in somos]
    abiertas = sum(1 for o in mias if str(o.get("maker")) in somos and o.get("status", "open") == "open")

    ofertas = _lista(lectura.get("tablon")) + [o for o in mias if str(o.get("maker")) not in somos]
    comprar, vender = oportunidades(ofertas, est)

    tratos = {}
    ojeador.observar_feed(tratos, eventos(lectura.get("feed")), lectura.get("tick"))
    precios = {r: [x[1] for x in v][-MAX_PRECIOS:] for r, v in sorted(tratos.items())}
    nuevos = avisos(lectura.get("feed"), mem)

    propuestas, descartadas = [], []
    if p is not None and isinstance(est["efectivo"], (int, float)):
        propuestas, descartadas = validar(comprar, vender, est["_cuenta"], est["efectivo"], p)
    est.pop("_valores"), est.pop("_cuenta")
    apunta("OJOS", f"efectivo {est['efectivo']} · puntos {est['puntos']} (puesto {est['puesto']}) · "
                   f"faltan {sum(len(v) for v in est['faltan'].values())} · repetidas {len(est['repetidas'])}"
                   + (f" · casi: {', '.join(est['casi'])}" if est["casi"] else ""))
    if comprar:
        c = comprar[0]
        apunta("OJOS", f"comprar: {c['carta']} a {c['precio']} (oferta {c['oferta']})"
                       + (" · completa página" if c["completa_pagina"] else "") + f" · {len(comprar)} en total")
    if vender:
        v = vender[0]
        apunta("OJOS", f"vender: {v['carta']} a {v['precio']} (oferta {v['oferta']}, nos vale {v['nos_vale']})"
                       f" · {len(vender)} en total")
    if para_nosotros:
        apunta("OJOS", f"{len(para_nosotros)} ofertas para nosotros: " + ", ".join(str(o["oferta"]) for o in para_nosotros))
    if precios:
        apunta("OJOS", "tratos del feed: " + " · ".join(f"{r} {p[-1]}" for r, p in list(precios.items())[:MAX_LISTA]))
    for a in nuevos:
        apunta("OJOS", f"aviso del juego ({a['tipo']}): {a['texto']}")
    for x in propuestas[:3]:
        apunta("PROPUESTA", f"{'comprar' if x['lado'] == 'compra' else 'vender'} {x['carta']} a {x['precio']} · "
                            f"aceptar oferta {x['aceptar']} · {x['motivo']}")
    if (comprar or vender) and not propuestas and p is not None:
        apunta("PROPUESTA", f"ninguna: la Contable no valida ninguna de {len(comprar) + len(vender)} oportunidades"
                            + (f" ({descartadas[0]['carta']}: {descartadas[0]['motivo']})" if descartadas else ""))
    return {"estado": est, "comprar": comprar, "vender": vender, "precios": precios, "avisos": nuevos,
            "para_nosotros": para_nosotros, "abiertas": abiertas, "propuestas": propuestas, "descartadas": descartadas}
