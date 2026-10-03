"""El Ojeador: mira el mercado en el tiempo y dice CUÁNDO comprar y vender, no solo si renta.

El Cambista ya sabe SI una oferta renta (precio < lo que nos vale). El Ojeador añade el CUÁNDO, con cuatro señales:

1. Historial     cada precio visto en El Rastro (anuncios, peticiones) y en el feed público (tratos hechos), con su tick.
2. Tendencia     por carta: ¿el precio que piden baja, sube o está quieto?, ¿cuántos venden y cuántos piden?
3. Momento       del juego entero, sacado del calendario: dinero nuevo para todos (vender), noche del sábado antes del
                 dinero del domingo (comprar), última hora del juego (el efectivo ya no puntúa: los demás pagan más →
                 vender; comprar sale caro), inicio de cada hora de juego (los cupos de los vendedores se renuevan).
4. Escasez       del catálogo: copias acuñadas / tirada. Una carta casi agotada no va a bajar → comprar ya, vender caro.

Y quién quiere qué: compradores_probables() junta el mapa de deseos y el cazador de páginas del Cambista.

Reglas fijas: nunca se paga más de lo que nos vale (eso lo sigue mirando la Contable y el Guardia). El Ojeador solo
puede decir "espera" a una compra que renta o subir/bajar un anuncio dentro de su suelo. Sin red y sin azar.
"""
from collections import defaultdict

from . import valor as V

GUARDA = 40                 # observaciones por carta que se recuerdan


# ── 1. historial ─────────────────────────────────────────────────────────────────────────────────────────────

def _ref_de(x):
    if isinstance(x, dict):
        x = x.get("ref") or x.get("card")
    return x if isinstance(x, str) else None


def observar(hist, tablon, tick):
    """Apunta en hist = {ref: [[tick, precio, lado, maker]]} lo que hay en el tablón. lado: "venta" (alguien vende
    una carta por efectivo) o "compra" (alguien ofrece efectivo por una carta). Una misma oferta vista varias veces
    se apunta una vez por tick como mucho."""
    for o in tablon or []:
        if not isinstance(o, dict):
            continue
        give, want = o.get("give") or {}, o.get("want") or {}
        cartas, pide = give.get("assets") or [], want.get("cards") or want.get("types") or []
        maker = o.get("maker")
        if len(cartas) == 1 and not pide and isinstance(want.get("cash"), (int, float)) and want["cash"] > 0:
            ref, lado, precio = _ref_de(cartas[0]), "venta", want["cash"]
        elif len(pide) == 1 and not cartas and isinstance(give.get("cash"), (int, float)) and give["cash"] > 0:
            ref, lado, precio = _ref_de(str(pide[0]).replace("card:", "")), "compra", give["cash"]
        else:
            continue
        if not ref:
            continue
        lista = hist.setdefault(ref, [])
        if not any(x[0] == tick and x[2] == lado and x[3] == maker and x[1] == precio for x in lista[-6:]):
            lista.append([tick, precio, lado, maker])
            del lista[:-GUARDA]


def observar_feed(hist, feed, tick):
    """Tratos hechos del feed público (lo más fiable: alguien pagó ese precio). Forma tolerante: cada evento con
    una carta (ref / card / asset.ref) y un precio (price / cash / amount). Lo que no se entiende se ignora."""
    if isinstance(feed, dict):
        eventos = feed.get("events") or feed.get("feed") or feed.get("items") or []
    else:
        eventos = feed or []
    for e in eventos if isinstance(eventos, list) else []:
        if not isinstance(e, dict):
            continue
        tipo = str(e.get("type") or e.get("kind") or "").lower()
        if tipo and not any(k in tipo for k in ("settle", "trade", "deal", "sale")):
            continue
        ref = _ref_de(e.get("ref") or e.get("card") or e.get("asset"))
        precio = next((e[k] for k in ("price", "cash", "amount") if isinstance(e.get(k), (int, float))), None)
        t = e.get("tick") if isinstance(e.get("tick"), (int, float)) else tick
        if ref and precio and precio > 0:
            lista = hist.setdefault(ref, [])
            if [t, precio, "trato", None] not in lista:
                lista.append([t, precio, "trato", None])
                del lista[:-GUARDA]


# ── 2. tendencia ─────────────────────────────────────────────────────────────────────────────────────────────

def _pendiente(puntos):
    """Recta de mínimos cuadrados precio = a + b·tick. Devuelve b (primas por tick), o 0 con menos de 3 puntos."""
    if len(puntos) < 3:
        return 0.0
    n = len(puntos)
    mx, my = sum(t for t, _ in puntos) / n, sum(p for _, p in puntos) / n
    sxx = sum((t - mx) ** 2 for t, _ in puntos)
    return 0.0 if sxx == 0 else sum((t - mx) * (p - my) for t, p in puntos) / sxx


def tendencia(hist, ref, ahora, ventana=120, umbral=0.15):
    """{"sentido": "baja"|"sube"|"quieto"|"sin datos", "cambio": cambio relativo previsto en la ventana,
        "minimo", "mediana", "vendedores", "compradores", "tratos"} con lo visto en los últimos `ventana` ticks.
    El sentido sale de lo que PIDEN los que venden y de los tratos hechos (lo que cuesta comprar)."""
    obs = [x for x in hist.get(ref, []) if isinstance(x[0], (int, float)) and ahora - x[0] <= ventana]
    precios = [(t, p) for t, p, lado, _ in obs if lado in ("venta", "trato")]
    out = {"sentido": "sin datos", "cambio": 0.0, "minimo": None, "mediana": None,
           "vendedores": len({m for _, _, l, m in obs if l == "venta"}),
           "compradores": len({m for _, _, l, m in obs if l == "compra"}),
           "tratos": sum(1 for x in obs if x[2] == "trato")}
    if not precios:
        return out
    ps = sorted(p for _, p in precios)
    out["minimo"], out["mediana"] = ps[0], ps[len(ps) // 2]
    if len(precios) < 3:
        out["sentido"] = "quieto"
        return out
    cambio = _pendiente(precios) * ventana / max(out["mediana"], 1)
    out["cambio"] = round(cambio, 3)
    out["sentido"] = "baja" if cambio <= -umbral else "sube" if cambio >= umbral else "quieto"
    return out


# ── 3. momento ───────────────────────────────────────────────────────────────────────────────────────────────

def momento(evs, h, fin_h=None):
    """Lo que dice el calendario sobre el mercado entero a la hora de juego h. evs = guion.eventos(calendario).
    {"fase": ..., "vender": factor para el precio de los anuncios, "comprar": "ya"|"normal"|"esperar", "motivo"}
    Fases (de más a menos fuerte):
      final        última hora antes de que se congelen los puntos: el efectivo ya no vale → los demás pagan más.
                   Vender caro; comprar solo lo que renta mucho (el Cambista ya paga casi todo en el tramo final).
      dinero_nuevo la hora después de "dinero para todos": todos tienen caja → vender un poco más caro.
      antes_dinero la última hora y media antes del dinero para todos: caja corta en todos → comprar ya, barato.
      normal       nada especial."""
    fin_h = fin_h if fin_h is not None else next((e["h"] for e in evs if e["accion"] == "end_round"), None)
    if fin_h is not None and 0 <= fin_h - h <= 1.0:
        return {"fase": "final", "vender": 1.25, "comprar": "esperar",
                "motivo": "última hora: el efectivo deja de valer y los demás pagan más"}
    for e in evs:
        if e["accion"] != "grant_all":
            continue
        if 0 <= h - e["h"] <= 1.0:
            return {"fase": "dinero_nuevo", "vender": 1.15, "comprar": "normal",
                    "motivo": f"todos acaban de recibir {e['params'].get('cash', '?')} P"}
        if 0 < e["h"] - h <= 1.5:
            return {"fase": "antes_dinero", "vender": 1.0, "comprar": "ya",
                    "motivo": "caja corta en todos antes del dinero nuevo: buen momento para comprar"}
    return {"fase": "normal", "vender": 1.0, "comprar": "normal", "motivo": ""}


def inicio_de_hora(t_hours, margen=0.1):
    """True en los primeros minutos de cada hora de juego, cuando se renuevan los cupos de los vendedores."""
    return isinstance(t_hours, (int, float)) and (t_hours % 1.0) < margen


# ── 4. escasez ───────────────────────────────────────────────────────────────────────────────────────────────

def escasez(catalogo):
    """{ref: acuñadas / tirada} desde catalog(). 1,0 = agotada (los sobres ya dan la rareza de abajo)."""
    out = {}
    sets = (catalogo or {}).get("sets") if isinstance(catalogo, dict) else None
    for s in (sets.values() if isinstance(sets, dict) else sets or []):
        for c in (s.get("cards") or []) if isinstance(s, dict) else []:
            if isinstance(c, dict) and isinstance(c.get("id"), str) and c.get("print_run"):
                m = c.get("minted")
                if isinstance(m, (int, float)):
                    out[c["id"]] = round(m / c["print_run"], 3)
    return out


# ── las decisiones ───────────────────────────────────────────────────────────────────────────────────────────

def comprar_ahora(ref, precio, nos_vale, tend, mom, esc=None, completa=False, escaso=0.8):
    """¿Comprar ya una oferta que renta (precio < nos_vale), o esperar a que baje? (decisión, motivo)
    Comprar ya si: completa página, la carta se agota, el precio sube, hay más compradores que vendedores, es el
    mínimo visto, o el momento es de comprar. Esperar solo si el precio BAJA con varios vendedores y el margen es
    pequeño (< 25 % de lo que vale): si el margen es grande, el riesgo de perderla pesa más."""
    if precio >= nos_vale:
        return False, "no renta"
    margen = (nos_vale - precio) / max(nos_vale, 1)
    if completa:
        return True, "completa página"
    if esc is not None and esc >= escaso:
        return True, f"casi agotada ({esc:.0%} acuñada)"
    if mom.get("comprar") == "ya":
        return True, mom.get("motivo") or "momento de comprar"
    if tend["sentido"] == "sube":
        return True, "el precio sube"
    if tend["compradores"] > tend["vendedores"]:
        return True, "más gente la pide que la vende"
    if tend["minimo"] is not None and precio <= tend["minimo"]:
        return True, "el más barato visto"
    if tend["sentido"] == "baja" and tend["vendedores"] >= 2 and margen < 0.25:
        return False, f"baja ({tend['cambio']:+.0%} previsto) con {tend['vendedores']} vendiendo: esperar"
    if mom.get("comprar") == "esperar" and margen < 0.25:
        return False, mom.get("motivo") or "momento de no comprar"
    return True, "renta"


def precio_venta(base, suelo, tend, mom, esc=None, escaso=0.8, tope=1.3):
    """Precio de un anuncio de venta ajustado al mercado, nunca por debajo de `suelo` (V.suelo_venta_rastro: valor + comisión + margen).
    Sube con el momento (dinero nuevo, final), con la escasez, si sube el precio o hay más compradores que
    vendedores; baja un poco si el precio baja con mucha oferta. Como mucho base × tope."""
    f = mom.get("vender", 1.0)
    if esc is not None and esc >= escaso:
        f *= 1.15
    if tend["sentido"] == "sube" or tend["compradores"] > tend["vendedores"]:
        f *= 1.1
    elif tend["sentido"] == "baja" and tend["vendedores"] >= 3:
        f *= 0.92
        if tend["minimo"] is not None:            # ponerse justo debajo del más barato, si cabe sobre el suelo
            return max(int(suelo), min(int(base * min(f, tope)), int(tend["minimo"]) - 1))
    return max(int(suelo), int(round(base * min(f, tope))))


# ── para el Regateador (vendedores) ──────────────────────────────────────────────────────────────────────────

def descanso(motivo, h=None, tick=None, until_tick=None, ticks_por_hora=120):
    """Hasta cuándo no se vuelve a abrir con un vendedor que cerró. {"hasta_h": x} o {"hasta_tick": n}, o None.
      persona_quota / sold_out  cupo de la hora agotado: hasta la hora de juego siguiente (los cupos son por hora)
      cooloff                   enfadado: hasta su until_tick (o media hora de juego si no lo dice)
    Sin hora de juego conocida, se cuenta en ticks (120 por hora a 30 s el tick)."""
    if motivo in ("persona_quota", "sold_out"):
        if isinstance(h, (int, float)):
            return {"hasta_h": int(h) + 1.0}
        return {"hasta_tick": (tick or 0) + ticks_por_hora} if isinstance(tick, (int, float)) else None
    if motivo == "cooloff":
        if isinstance(until_tick, (int, float)):
            return {"hasta_tick": until_tick}
        return {"hasta_tick": tick + ticks_por_hora // 2} if isinstance(tick, (int, float)) else None
    return None


def descansa(info, h=None, tick=None):
    """¿Sigue descansando este vendedor? info = lo que devolvió descanso()."""
    if not info:
        return False
    if "hasta_h" in info and isinstance(h, (int, float)):
        return h < info["hasta_h"]
    if "hasta_tick" in info and isinstance(tick, (int, float)):
        return tick < info["hasta_tick"]
    return False


def senales_vendedor(hist, refs, ahora, esc=None, ventana=120, comision=0.05, por_carta=1):
    """Para cada carta que vende un vendedor: {ref: {"rastro": lo que costaría hoy en El Rastro con la comisión
    (o None), "escasa": True si está casi agotada}}. El Regateador ordena sus compras con esto."""
    import math
    out = {}
    for ref in refs:
        t = tendencia(hist, ref, ahora, ventana)
        rastro = None if t["minimo"] is None else math.ceil(t["minimo"] * (1 + comision)) + por_carta
        out[ref] = {"rastro": rastro, "escasa": (esc or {}).get(ref, 0) >= 0.8}
    return out


def compradores_probables(hist, ref, veces=2):
    """Equipos que probablemente quieren esta carta: [(maker, mejor precio ofrecido, veces)], de más a menos.
    Quien la pide varias veces seguramente completa página con ella: a ese se le puede ofrecer directamente
    (list_offer con `to`) a su mejor precio visto."""
    pedidas = defaultdict(list)
    for t, p, lado, maker in hist.get(ref, []):
        if lado == "compra" and maker:
            pedidas[maker].append(p)
    out = [(m, max(ps), len(ps)) for m, ps in pedidas.items()]
    return sorted([x for x in out if x[2] >= 1], key=lambda x: (-(x[2] >= veces), -x[1]))


def informe(hist, ahora, refs=None, n=6):
    """Líneas para la pantalla: las cartas cuyo precio se mueve más."""
    refs = refs or list(hist)
    filas = []
    for ref in refs:
        t = tendencia(hist, ref, ahora)
        if t["sentido"] in ("baja", "sube"):
            filas.append((abs(t["cambio"]), ref, t))
    filas.sort(reverse=True)
    return [f"MERCADO      {ref:<7} {t['sentido']:<5} {t['cambio']:+.0%} · mín {t['minimo']} · "
            f"{t['vendedores']} venden / {t['compradores']} piden" for _, ref, t in filas[:n]]


# ── 5. precios para la lista de la compra del Cambista (mem.mercado / mem.demanda) ───────────────────────────────
#
#    mercado  ← lo que otros equipos PIDEN por una carta (anuncios que venden una carta por efectivo)
#    demanda  ← lo que otros equipos OFRECEN por una carta (peticiones que ofrecen efectivo por una carta)
#    vigilar(lectura, mem)    → los apunta del tablón de este tick (si llega); lo usan lista_compra() y peticiones()
#    precios(vista, carta)    → {"piden": el más barato que piden, "ofrecen": el más alto que ofrecen}, para el Regateador

def vigilar(lectura, mem):
    tablon = lectura.get("tablon")
    if tablon:
        apuntar_mercado(mem.mercado, [o for o in tablon if isinstance(o, dict)], mem.demanda)
    return {"mercado": mem.mercado, "demanda": mem.demanda}


def precios(vista, carta):
    piden, ofrecen = (vista.get("mercado") or {}).get(carta), (vista.get("demanda") or {}).get(carta)
    return {"piden": min(piden) if piden else None, "ofrecen": max(ofrecen) if ofrecen else None}


MERCADO_RECUERDA = 12      # precios vistos por carta que guarda el Ojeador


def _apunta(d, ref, precio):
    vistos = d.setdefault(ref, [])
    vistos.append(precio)
    del vistos[:-MERCADO_RECUERDA]


def apuntar_mercado(mercado, tablon, demanda=None):
    """El Ojeador apunta los precios del tablón de El Rastro (los últimos MERCADO_RECUERDA por carta):
    mercado  ← anuncios que venden UNA carta por efectivo: la lista de la compra espera pagar lo más barato visto
    demanda  ← peticiones que ofrecen efectivo por UNA carta: si otro equipo compite por una carta que queremos,
               nuestra petición pide 1 P más que él (mientras quepa en el tope)"""
    for o in tablon:
        give, want = o.get("give") or {}, o.get("want") or {}
        cartas, pide = give.get("assets") or [], want.get("cards") or []
        if len(cartas) == 1 and not give.get("cash") and not pide and isinstance(want.get("cash"), (int, float))                 and want["cash"] > 0:
            ref = cartas[0].get("ref") if isinstance(cartas[0], dict) else cartas[0]
            if isinstance(ref, str):
                _apunta(mercado, ref, want["cash"])
        elif demanda is not None and len(pide) == 1 and not cartas and isinstance(give.get("cash"), (int, float))                 and give["cash"] > 0 and isinstance(pide[0], str):
            _apunta(demanda, pide[0], give["cash"])
