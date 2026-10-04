"""El Comerciante: UNA decisión de qué comprar y vender, y a cuánto como mucho, para los dos canales.

    vendedores  (canal 1)  la conversación la regatea `tienda.py`: pasos pequeños, el vendedor imita, sus 3 mejores tratos
    El Rastro   (canal 2)  anuncios, peticiones y cambios los pone `cambista.py`; las ofertas de otros se aceptan si rentan

Las dos herramientas no cambian: cada canal puntúa distinto (con un vendedor, la parte de su rango en sus tres mejores
tratos del día; en El Rastro, todo el valor ganado). Lo que es UNO es la decisión:
    - qué vender:   cambista.vendibles() sirve a los dos canales (nunca una protegida, nunca una que guarda el Guion)
    - qué comprar:  lo que nos suma según la Contable; una página a completar va primero en los dos
    - qué canal:    con los Ojos. Si El Rastro da mejor precio (propuestas validadas, o lo más barato que piden allí con
                    la comisión) no se compra ni vende a un vendedor; nunca se paga más ni se vende por menos que el
                    último trato del feed.
Ayudantes en los vendedores: Portavoz (el mensaje), Escudo (el texto), Observador (con quién ser duro), Espía (pistas).

Sin red y sin azar. Lo llama la cadena en cada tick (vendedor, rastro, propuestas_ojos) y quien lanza la cadena para
abrir conversaciones y publicar (operaciones, anuncios, lista_compra, peticiones_rastro, trueques_rastro).
"""
import math

from . import cambista, contable, defensa, guion, ojos, params, sondas, tienda
from . import valor as V

NO_INSISTIR = {"pilar"}      # memoria y astucia altas: una carta que no quiso a nuestro precio no se le ofrece otra vez ese día
VENTANA = 120                # ticks de El Rastro que cuentan (una hora de juego a 30 s el tick)


def precio_rastro(hist, ref, ahora, comision=0.05, por_carta=1):
    """Lo que costaría hoy esa carta en El Rastro con la comisión (lo más barato que piden o el último trato en los
    últimos VENTANA ticks), o None si nadie la vende."""
    minimo = ojos.en_rastro(hist, ref, ahora, VENTANA)["minimo"]
    return None if minimo is None else math.ceil(minimo * (1 + comision)) + por_carta


def _reservadas(cuenta, mem, lectura):
    h = lectura.get("hora")
    if not mem.calendario or h is None:
        return {}
    return guion.reservadas(dict(cuenta), guion.eventos(mem.calendario), h)


def operaciones(cuenta, efectivo, menus, mem, lectura, ordenes=None, abiertas=(), tratos=None, max_tratos=None):
    """Qué abrir con los vendedores: cola_de_operaciones() + El Guion (cartas que esperan una fiebre) + los Ojos
    (vendedores que descansan; lo que sale más barato en El Rastro) + niveles de la escalera.
    Es lo que llama quien lanza la cadena para abrir conversaciones con vendedores."""
    t = lectura.get("tick")
    ahora = t if isinstance(t, (int, float)) else 0
    quietos = {v for v, d in mem.descansos.items() if ojos.descansa(d, lectura.get("hora"), t)}
    refs = {r for m in (menus or {}).values() if isinstance(m, dict) for r in (m.get("vende") or {})}
    senales = {ref: {"rastro": precio_rastro(mem.historial, ref, ahora)} for ref in refs}
    hoy = f"|{lectura.get('dia')}"
    evitar = {tuple(k[:-len(hoy)].split("|", 1)) for k in mem.sin_acuerdo if k.endswith(hoy)}
    return cola_de_operaciones(cuenta, efectivo, menus, ordenes, set(abiertas) | quietos, tratos, max_tratos,
                               guardar=_reservadas(cuenta, mem, lectura), niveles=mem.niveles, senales=senales,
                               evitar=evitar)


def anuncios(cuenta, p, mem, lectura, activos=None, ocupadas=(), excluidas=(), listas=None, caducidades=None, maximo=12):
    """Qué anunciar en El Rastro: anuncios_rastro() sin las cartas que esperan una fiebre (Guion), nunca por debajo de
    V.suelo_venta_rastro (valor + comisión + margen) ni del último trato del feed (Ojos).
    Sin demanda no se malvende: una carta que nadie pide y que ya venden cambista.sin_demanda_vendedores equipos no se
    anuncia (se guarda para cambios). Cazador de páginas: a quien pide la misma carta cambista.caza_veces veces no se
    le vende por debajo de lo mejor que ha ofrecido."""
    excluidas = set(excluidas) | set(_reservadas(cuenta, mem, lectura))
    t = lectura.get("tick") if isinstance(lectura.get("tick"), (int, float)) else 0
    obs = [{"maker": m, "ref": ref, "precio": pr, "lado": lado}
           for ref, xs in (mem.historial or {}).items() if V.conocida(ref)
           for tk, pr, lado, m in xs if lado == "compra" and isinstance(pr, (int, float)) and isinstance(tk, (int, float))
           and t - tk <= VENTANA]
    caza = {}
    for ref, _, mejor, _ in cambista.cazador_de_paginas(obs, cuenta, veces=int(p.get("cambista.caza_veces", 2))):
        caza[ref] = max(caza.get(ref, 0), mejor)
    minimo_vend = int(p.get("cambista.sin_demanda_vendedores", 0))
    sin_demanda = set()
    if minimo_vend:
        for ref, n in cuenta.items():
            if n > 0 and ref not in caza:
                visto = ojos.en_rastro(mem.historial, ref, t, VENTANA)
                if visto["compradores"] == 0 and visto["vendedores"] >= minimo_vend:
                    sin_demanda.add(ref)
    out = anuncios_rastro(cuenta, p, activos, ocupadas, excluidas | sin_demanda, listas, caducidades, maximo)
    tratos_feed = ojos.tratos(mem)
    for n in out:
        if n["carta"] in caza and n["precio"] < caza[n["carta"]]:
            n["precio"] = math.ceil(caza[n["carta"]])
            n["cazador"] = f"la pide varias veces, hasta {caza[n['carta']]} P"
        trato = tratos_feed.get(n["carta"])
        if trato is not None and n["precio"] < trato:    # los Ojos: no se anuncia por menos que el último trato
            n["ojos"] = f"último trato {trato}: {n['precio']} → {math.ceil(trato)}"
            n["precio"] = math.ceil(trato)
    return out


def _propuesta_vendedor(c, precio):
    if c["lado"] == "compra":
        return {"tipo": "vendedor", "recibo": {"cartas": [c["carta"]]}, "entrego": {"primas": precio}}
    return {"tipo": "vendedor", "recibo": {"primas": precio}, "entrego": {"cartas": [c["carta"]]}}


# ---------------------------------------------------------------- los pasos de cada tick (los llama cadena.tick)

def vendedor(c, tu):
    """Una conversación con un vendedor: la Contable da tope o suelo, el Comerciante elige canal (si El Rastro lo da
    mejor, se cierra aquí) y tienda.py regatea. Añade a tu.mensajes, tu.cerrar o tu.cola."""
    lectura, mem, p, ordenes, cuenta, efectivo = tu.lectura, tu.mem, tu.p, tu.ordenes, tu.cuenta, tu.efectivo
    apunta, cerrar, cola, mensajes = tu.apunta, tu.cerrar, tu.cola, tu.mensajes
    textos, tratos_feed, vista = tu.textos, tu.tratos, tu.vista
    hilo, quien, texto = str(c["id"]), c["vendedor"], c.get("texto") or ""
    cuentas = contable.para_vendedor(c, cuenta, efectivo, p, ordenes)
    es_nuevo = hilo in textos["textos_nuevos"]
    def sin_acuerdo(motivo):                         # con Pilar no se insiste: esa carta, ese día, ya no
        if quien in NO_INSISTIR:
            mem.sin_acuerdo[f"{quien}|{c['carta']}|{lectura.get('dia')}"] = motivo
    if c.get("cerrado"):
        apunta("TIENDA", f"{quien} cerró la conversación ({c['cerrado']})")
        sin_acuerdo(c["cerrado"])
        return
    if not cuentas["conocida"]:                          # conocer el valor antes de comprar: sin dato, no se opera
        cerrar.append({"destino": "vendedor", "id": c["id"], "motivo": "carta sin valor conocido"})
        apunta("TIENDA", f"{quien} · {c['carta']}: {cuentas.get('motivo') or 'no sabemos cuánto nos vale'}, se cierra")
        return
    suya = c["suyas"][-1]
    pista = sondas.pista_suelo(texto, suya, c["lado"]) if es_nuevo else None
    if pista is not None and mem.pistas.get(hilo) != pista:
        mem.pistas[hilo] = pista
        apunta("ESPÍA", f"{quien} · pista de su límite: {pista} (se comprueba con sus ofertas)")
    if es_nuevo and c.get("nuestras"):
        term = sondas.Termometro()
        term.lecturas = [tuple(x) for x in mem.tonos.get(hilo, [])]
        if term.anotar(c["nuestras"][-1], texto):
            mem.tonos[hilo] = [list(x) for x in term.lecturas]
            apunta("ESPÍA", f"{quien} · termómetro: {term.lecturas[-1][1]} con {term.lecturas[-1][0]} · "
                            f"horquilla {term.horquilla(c['lado'])}")

    limite = cuentas["limite"]
    if limite is None or cuentas["protegida"]:
        cerrar.append({"destino": "vendedor", "id": c["id"], "motivo": "carta protegida o que ya no tenemos"})
        apunta("TIENDA", f"{quien} · {c['carta']}: protegida o ya no la tenemos, se cierra")
        return
    if c["lado"] == "compra":                            # no regatear por algo que la caja no puede pagar
        caja = cuentas["caja"]
        if caja < 1:
            cerrar.append({"destino": "vendedor", "id": c["id"], "motivo": "no hay caja para esta compra"})
            apunta("TIENDA", f"{quien} · {c['carta']}: no hay caja para comprar sin tocar la reserva, se cierra")
            return
        limite = min(limite, caja)
    # ---- el canal: lo decide el Comerciante con lo que ven los Ojos (último trato y El Rastro) ----
    trato = tratos_feed.get(c["carta"])               # los Ojos: el último trato hecho por esa carta en el feed
    if trato is not None:
        antes = limite
        limite = min(limite, math.floor(trato)) if c["lado"] == "compra" else max(limite, math.ceil(trato))
        if limite != antes:
            apunta("OJOS", f"{quien} · {c['carta']}: último trato {trato} → {'tope' if c['lado'] == 'compra' else 'suelo'} "
                           f"{antes} → {limite}")
    mejor = ojos.mejor_propuesta(vista, c["lado"], c["carta"])
    if mejor and (mejor["precio"] + mejor["comision"] < suya if c["lado"] == "compra"
                  else mejor["precio"] - mejor["comision"] > suya):
        motivo = (f"los Ojos la ven {'más barata' if c['lado'] == 'compra' else 'mejor pagada'} en El Rastro "
                  f"({mejor['precio']}, oferta {mejor['aceptar']})")
        cerrar.append({"destino": "vendedor", "id": c["id"], "motivo": motivo})
        apunta("TIENDA", f"{quien} · {c['lado']} {c['carta']} · él {suya}: {motivo}, se cierra")
        return
    apunta("CONTABLE", f"{quien} · {c['lado']} {c['carta']} · nos vale {cuentas['nos_vale']:.1f} · "
                       f"{'tope' if c['lado'] == 'compra' else 'suelo'} {limite}")
    pf = params.perfil(p, quien)                         # el Observador: con quién ser duro
    if pf["perfil"] == "desconocido" and mem.vistos.get(f"observador|{quien}") is None:
        mem.vistos[f"observador|{quien}"] = "desconocido"
        apunta("OBSERVADOR", f"{quien}: vendedor sin perfil propio, se le trata con prudencia")
    st = {"lado": c["lado"], "limite": limite, "suyas": c["suyas"], "nuestras": c.get("nuestras", []),
          "final": bool(c.get("final")), "lista": c.get("lista")}
    if c["lado"] == "compra":
        st["caja"] = cuentas["caja"]
    if not st["nuestras"] and c["lado"] == "compra" and ordenes.get("compras") == "ninguna" and \
            not contable.para_completar(c["carta"], ordenes):
        cerrar.append({"destino": "vendedor", "id": c["id"], "motivo": "caja seca: no se abren compras"})
        apunta("TIENDA", f"{quien} · {c['carta']}: caja seca, no se abre la compra")
        return
    accion, precio, por_que = tienda.decidir(st, pf, p)
    apunta("TIENDA", f"{quien} · {c['lado']} {c['carta']} · él {suya} · {accion} {precio if precio is not None else ''} · {por_que}")
    if accion == "retirarse":
        cerrar.append({"destino": "vendedor", "id": c["id"], "motivo": por_que})
        sin_acuerdo(por_que)
        if c["lado"] == "compra" and not st["nuestras"] and not tienda.caja_llega(st.get("caja"), suya):
            mem.sin_acuerdo[f"{quien}|{c['carta']}|{lectura.get('dia')}"] = por_que   # hoy no se le vuelve a abrir
    elif accion == "aceptar":
        cola.append({"tipo": "final_vendedor" if st["final"] else "vendedor", "urgente": st["final"],
                     "destino": "vendedor", "id": c["id"], "oferta_id": c.get("oferta_id"), "precio": suya,
                     "propuesta": _propuesta_vendedor(c, suya), "vendedor": quien, "apertura": c["suyas"][0],
                     "oferta_juego": c.get("oferta_juego")})   # la oferta tal como la da el juego: el Guardia mira la carta
    else:
        firme = mem.escudo.firme(quien)
        usadas = mem.sondas.setdefault(hilo, [])
        ok, _ = sondas.permitida("vendedor", pf.get("sondas_max", 0), len(usadas), p, texto, c.get("cerrado"))
        # una conversación de prueba al día, y solo con la escalera de ese vendedor ya hecha: un enfado no cuesta puntos
        dia = lectura.get("dia")
        hechos = sum(1 for x in mem.capturas.get(quien, []) if x.get("dia") == dia)
        de_prueba = mem.sondeadas.setdefault(f"{quien}|{dia}", [])
        ok = ok and hechos >= p.get("espia.tras_tratos", 3) and \
            (hilo in de_prueba or len(de_prueba) < p.get("espia.conversaciones_por_dia", 1))
        txt = None
        if ok and not firme and st["nuestras"]:          # nunca en la apertura: primero el ancla
            tipo, txt = sondas.siguiente(usadas, precio)
            if txt and defensa.revisar_salida(txt, precio)[0]:
                usadas.append(tipo)
                if hilo not in de_prueba:
                    de_prueba.append(hilo)
                apunta("ESPÍA", f"{quien} · pregunta «{tipo}» ({len(usadas)} de {pf.get('sondas_max', 0)})")
            else:
                txt = None
        if txt is None:
            txt = mem.portavoz.vendedor(quien, precio, firme, carta=c["carta"])
        mensajes.append({"destino": "vendedor", "id": c["id"], "precio": precio, "texto": txt})


def rastro(tablon, tu):
    """El tablón de El Rastro: lo que renta según la Contable va a la cola del Guardia, sin esperar."""
    p, ordenes, cuenta, efectivo, apunta, cola = tu.p, tu.ordenes, tu.cuenta, tu.efectivo, tu.apunta, tu.cola
    tablon = [o for o in tablon if isinstance(o, dict)]
    for o in cambista.oportunidades(tablon, cuenta, efectivo, reserva=p["guardia.reserva_efectivo"], p=p)[:3]:
        prop = o["propuesta"]
        if ordenes.get("compras") == "ninguna" and prop["recibo"]["cartas"] and not prop["entrego"]["cartas"] and \
                not (ordenes.get("pedir_completar") and all(contable.para_completar(r, ordenes) for r in prop["recibo"]["cartas"])):
            continue                                 # solo vender o caja seca: en El Rastro no se compra (salvo páginas a completar)
        apunta("CAMBISTA", f"El Rastro · oferta {o['oferta']} de {o['maker']} · neto {o['neto']:+.1f}")
        oferta = next((x for x in tablon if x.get("id") == o["oferta"]), None)
        cola.append({"tipo": "equipo", "destino": "rastro", "id": o["oferta"], "oferta_id": o["oferta"],
                     "neto": o["neto"], "propuesta": o["propuesta"], "oferta_juego": oferta})


def propuestas_ojos(props, tu):
    """Lo que los Ojos ya validaron con la Contable va a la cola del Guardia (sin repetir ofertas)."""
    ordenes, apunta, cola = tu.ordenes, tu.apunta, tu.cola
    en_cola = {o.get("oferta_id") for o in cola}
    for x in props[:3]:
        compra = x["lado"] == "compra"
        if x["aceptar"] in en_cola or (compra and ordenes.get("compras") == "ninguna"
                                       and not contable.para_completar(x["carta"], ordenes)):
            continue
        apunta("CAMBISTA", f"propuesta de los Ojos · oferta {x['aceptar']} · {x['lado']} {x['carta']} a {x['precio']} · "
                           f"neto {x['neto']:+.1f}")
        cola.append({"tipo": "equipo", "destino": "rastro", "id": x["aceptar"], "oferta_id": x["aceptar"],
                     "neto": x["neto"], "propuesta": x["propuesta"], "oferta_juego": x.get("oferta_juego")})


# ---------------------------------------------------------------- dónde vender cada carta, ANTES de abrir nada

ORDEN_CANAL = {"oferta": 0, "vendedor": 1, "anuncio": 2}     # a igual neto, lo seguro primero
RASTRO = (0.05, 1)                                           # la comisión de las reglas, si el juego no da otra


def comision(venue, precio, comisiones=None):
    """Lo que cuesta vender a ese precio en ese mercado, con la comisión REAL que da /api/venues (ojos.comisiones).
    Un mercado que el juego no ha dicho cuenta como El Rastro según las reglas: de más, nunca de menos."""
    pct, por_carta = (comisiones or {}).get(venue) or (comisiones or {}).get("rastro") or RASTRO
    return V.comision_rastro(precio, 1, pct, por_carta) if precio else 0


def precio_real(hist, tablon, ref, ahora):
    """Lo que el mercado paga HOY por esa carta, solo con datos del juego: el último trato del feed en la última hora,
    o, si no hay, lo más barato que piden ahora otros equipos por ella (el tablón). None si no hay ningún dato real."""
    hechos = [x for x in hist.get(ref, []) if x[2] == "trato" and isinstance(x[0], (int, float)) and ahora - x[0] <= VENTANA]
    if hechos:
        return max(hechos, key=lambda x: x[0])[1]
    piden = [o["want"]["cash"] for o in tablon or [] if isinstance((o.get("want") or {}).get("cash"), (int, float))
             and [a.get("ref") if isinstance(a, dict) else a for a in (o.get("give") or {}).get("assets") or []] == [ref]]
    return min(piden) if piden else None


def canales_de_venta(cuenta, menus, tablon, mem, lectura, excluidas=(), descansan=(), cupo_lleno=(), comisiones=None,
                     venue_anuncio=None):
    """Para cada carta que se puede vender, dónde sacamos más, mirado ANTES de abrir una conversación o publicar.
    Solo con valores reales y del momento (la API), nada supuesto:

        oferta    alguien ya pide esa carta con dinero en el tablón (El Rastro o el mercado de otro equipo):
                  su precio menos la comisión real de ese mercado
        vendedor  un vendedor libre que la compra: lo que ofrece de entrada en su menú (dealers() del juego)
        anuncio   publicarla nosotros: lo que el mercado paga hoy (precio_real: último trato del feed o lo que piden
                  otros equipos) menos la comisión real del mercado donde se publicaría (venue_anuncio)

    Lo que nos quita darla es el your_value del juego (cambista.vendibles → contable.nos_quita).
    Gana el neto más alto; a igual neto, lo seguro (oferta, luego vendedor). Si ninguno da más de lo que nos vale,
    no se vende. Sin ningún precio real, se anuncia (precio de anuncio de siempre, con su suelo) y se dice.
    Devuelve {ref: {"canal", "donde", "neto", "perdida", "opciones": [(canal, donde, neto)]}}."""
    t = lectura.get("tick") if isinstance(lectura.get("tick"), (int, float)) else 0
    venue_anuncio = venue_anuncio or (lambda precio: "rastro")
    out = {}
    for ref, perdida in cambista.vendibles(cuenta):
        if ref in excluidas or not V.conocida(ref):
            continue
        opciones = []
        for o in tablon or []:
            give, want = o.get("give") or {}, o.get("want") or {}
            precio = give.get("cash")
            if cambista.pedidas(want) == [ref] and not give.get("assets") and isinstance(precio, (int, float)) and precio > 0:
                opciones.append(("oferta", o.get("id"), round(precio - comision(o.get("venue") or "rastro", precio, comisiones), 2)))
        for vendedor, menu in (menus or {}).items():
            ofrece = ((menu or {}).get("compra") or {}).get(ref) if isinstance(menu, dict) else None
            if isinstance(ofrece, (int, float)) and vendedor not in descansan and vendedor not in cupo_lleno:
                opciones.append(("vendedor", vendedor, float(ofrece)))
        real = precio_real(mem.historial, tablon, ref, t)
        anunciable = V.rareza(ref) in ("common", "uncommon")      # una rara o mejor la decide el equipo
        if anunciable and real is not None:
            venue = venue_anuncio(real)
            opciones.append(("anuncio", venue, round(real - comision(venue, real, comisiones), 2)))
        if opciones:
            canal, donde, neto = max(opciones, key=lambda x: (x[2], -ORDEN_CANAL[x[0]]))
            if neto <= perdida:
                canal, donde = "ninguno", None
        elif anunciable:                                          # ningún precio real: se anuncia, como siempre
            canal, donde, neto = "anuncio", "sin precio real", None
        else:
            continue
        out[ref] = {"canal": canal, "donde": donde, "neto": neto, "perdida": perdida,
                    "opciones": sorted(opciones, key=lambda x: -x[2])}
    return out


# ---------------------------------------------------------------- abrir y publicar (los llama quien lanza la cadena)

def lista_compra(cuenta, efectivo, p, mercado=None, listas=None, pagado=None, final=False):
    """El Cambista compra: la lista de la compra (ver cambista.lista_compra)."""
    return cambista.lista_compra(cuenta, efectivo, p, mercado=mercado, listas=listas, pagado=pagado, final=final)


def peticiones_rastro(lista, cuenta, efectivo, p, activas=None, caducidades=None, demanda=None, final=False, tratos=None):
    """El Cambista compra: qué peticiones publicar en El Rastro ahora (ver cambista.peticiones).
    tratos = {carta: último trato visto por los Ojos} (ojos.tratos): no se ofrece más que eso."""
    out = []
    for n in cambista.peticiones(lista, cuenta, efectivo, p, activas, caducidades, demanda=demanda, final=final):
        trato = (tratos or {}).get(n["carta"])
        if trato is not None and n["precio"] > trato:
            if math.floor(trato) < 1:
                continue
            n = dict(n, precio=math.floor(trato), motivo=n["motivo"] + f" · los Ojos: último trato {trato}")
            n["gana"] = round(n["nos_vale"] - n["precio"], 1)
        out.append(n)
    return out


def trueques_rastro(lista, cuenta, p, ocupadas=(), activas=(), vivos=None):
    """El Cambista cambia: qué cambios carta por carta ofrecer en El Rastro (ver cambista.trueques)."""
    return cambista.trueques(lista, cuenta, p, ocupadas, activas, vivos=vivos)


def anuncios_rastro(cuenta, p, activos=None, ocupadas=(), excluidas=(), listas=None, caducidades=None, maximo=12):
    """El Cambista vende: qué anunciar en El Rastro. Solo lo que podemos dar sin perder valor, nunca una protegida,
    y solo comunes y poco comunes (una rara la decide el equipo).

    activos     = {ref: anuncios nuestros vivos}: esa copia ya está anunciada
    ocupadas    = refs con una venta abierta con un vendedor: esa copia no se anuncia además
    excluidas   = refs que se guardan para los vendedores (les quedan tratos de escalera hoy)
    listas      = {ref: precio de lista}; sin dato, la base de su rareza
    caducidades = {ref: veces que su anuncio caducó sin venderse}: cada una baja el precio
    Devuelve [{"carta", "precio", "pierde"}], como mucho `maximo`. El precio nunca baja de V.suelo_venta_rastro."""
    actual = dict(cuenta)
    for ref, n in (activos or {}).items():
        actual[ref] = actual.get(ref, 0) - n
    for ref in ocupadas:
        actual[ref] = actual.get(ref, 0) - 1
    out = []
    while len(out) < maximo:
        candidatas = [(ref, perdida) for ref, perdida in cambista.vendibles(actual)
                      if ref not in excluidas and V.conocida(ref) and V.rareza(ref) in ("common", "uncommon")]
        if not candidatas:
            break
        ref, perdida = candidatas[0]
        lista = (listas or {}).get(ref) or V.BASE[V.rareza(ref)]
        out.append({"carta": ref, "pierde": perdida,
                    "precio": cambista.precio_anuncio(lista, perdida, (caducidades or {}).get(ref, 0), p)})
        actual[ref] -= 1
    return out


def tratos_de_hoy(mem, dia):
    """{vendedor: tratos regateados cerrados hoy}. Sirve para la regla "calidad antes que cantidad"."""
    return {v: sum(1 for c in cs if c.get("dia") == dia) for v, cs in mem.capturas.items()}


def cola_de_operaciones(cuenta, efectivo, menus, ordenes=None, abiertas=(), tratos=None, max_tratos=None,
                        guardar=None, niveles=None, senales=None, evitar=()):
    """Qué operación abrir con cada vendedor que no tiene conversación: primero vender, luego comprar.

    menus = {vendedor: {"vende": {ref: precio de lista}, "compra": {ref: lo que ofrece de entrada}}}
    abiertas = vendedores que ya tienen conversación. Devuelve [{"vendedor", "lado", "carta", "lista"}], una por vendedor.
    tratos, max_tratos = calidad antes que cantidad: con max_tratos tratos regateados hoy con un vendedor (solo cuentan
    los tres mejores), ya no se le abren compras salvo la carta que completa una página. Vender sigue: da efectivo.
    Una carta cuyo valor no conocemos (barrio o código nuevo) no se abre nunca.
    guardar = {ref: vendedor al que sí se vende ahora, o None} (guion.reservadas): cartas que esperan una fiebre.
    Durante la fiebre van primero al vendedor de la fiebre.
    niveles = {vendedor: nivel}: los niveles altos pesan más en la escalera, así que sus operaciones van delante.
    senales = {ref: {"rastro": precio hoy en El Rastro con comisión o None}} (precio_rastro): con la escalera de ese
    vendedor ya hecha, no se le compra lo que sale más barato en El Rastro (se compra allí).
    evitar = {(vendedor, carta)} que hoy ya acabaron sin acuerdo con un vendedor de NO_INSISTIR: no se repiten.
    ordenes["completar"] = páginas a completar (hoy.json): sus cartas van delante, también con solo_vender y sin cupo,
    al vendedor más barato y solo con margen_completar × la lista libre sobre la reserva (si no, se espera a las ventas).
    ordenes["escalera"] = comprar para la escalera (hoy.json): también con solo_vender, a cada vendedor que aún no tiene
    max_tratos tratos hoy se le compra una carta que nos falte con lista ≤ ordenes["tope_escalera"].
    """
    ordenes, tratos, guardar = ordenes or {}, tratos or {}, guardar or {}
    urgentes = set(ordenes.get("vender") or [])
    pendientes, usadas = [], set()
    mas_barato = {}                                       # ref → la lista más baja entre los vendedores
    for menu in menus.values():
        for ref, lista in ((menu.get("vende") or {}).items() if isinstance(menu, dict) else ()):
            if isinstance(lista, (int, float)):
                mas_barato[ref] = min(mas_barato.get(ref, lista), lista)
    for vendedor, menu in menus.items():
        if vendedor in abiertas or not isinstance(menu, dict):
            continue
        ventas = [(ref, perdida) for ref, perdida in cambista.vendibles(cuenta)
                  if ref in (menu.get("compra") or {}) and ref not in usadas and V.conocida(ref)
                  and (ref not in guardar or guardar[ref] == vendedor) and not contable.para_completar(ref, ordenes)
                  and (vendedor, ref) not in evitar
                  and V.rareza(ref) in ("common", "uncommon") and menu["compra"][ref] * 3 > perdida]
        # la de mejor coste-beneficio: lo que nos ofrece de entrada menos lo que perdemos al darla
        ventas.sort(key=lambda x: (x[0] not in guardar, x[0] not in urgentes, -(menu["compra"][x[0]] - x[1]), x[1]))
        if ventas:
            ref = ventas[0][0]
            usadas.add(ref)
            pendientes.append({"vendedor": vendedor, "lado": "venta", "carta": ref, "lista": menu["compra"][ref]})
            continue
        if ordenes.get("compras") == "ninguna" and not ordenes.get("completar") and not ordenes.get("escalera"):
            continue
        cupo_lleno = max_tratos is not None and tratos.get(vendedor, 0) >= max_tratos
        compras = []
        for ref, lista in (menu.get("vende") or {}).items():
            if cuenta.get(ref, 0) > 0 or ref in usadas or not V.conocida(ref) or (vendedor, ref) in evitar:
                continue
            objetivo = contable.para_completar(ref, ordenes)     # página que el equipo quiere completar (hoy.json)
            escalera = ordenes.get("escalera") and not cupo_lleno and lista <= (ordenes.get("tope_escalera") or 0)
            if ordenes.get("compras") == "ninguna" and not (objetivo or escalera):
                continue                                  # solo vender: salvo páginas a completar y la escalera
            if objetivo and lista > mas_barato.get(ref, lista):
                continue                                  # una página a completar se compra al vendedor más barato
            if objetivo:                                  # primero la más cara: las baratas guardan caja para las que cuestan más
                mas_caras = sum(mas_barato[r] for r in V.estado_pagina(cuenta, V.barrio(ref))[1]
                                if r != ref and mas_barato.get(r, 0) > lista)
                if efectivo - ordenes.get("reserva", 0) < ordenes.get("margen_completar", 1) * (lista + mas_caras):
                    continue                              # se espera a que las ventas llenen la caja
            if not tienda.caja_llega(efectivo - ordenes.get("reserva", 0), lista):
                continue                                  # la caja no llega a su precio: no se abre (ni se le cansa)
            vale = contable.nos_suma(ref, cuenta)        # jugando: el your_value del juego
            if vale is None:
                continue                                  # sin valor del juego no se abre
            completa = V.estado_pagina(cuenta, V.barrio(ref))[1] == [ref]
            if objetivo and completa and ordenes.get("cerrar_en_rastro"):
                continue                                  # la que cierra la página, de otro equipo: el salto de valor puntúa
            if vale < 0.8 * lista or (cupo_lleno and not (completa or objetivo)):
                continue
            if ordenes.get("compras") == "escalera_y_pagina" and not (completa or objetivo) and \
                    lista > (ordenes.get("tope_por_trato") or 0):
                continue
            s = (senales or {}).get(ref) or {}
            rastro = s.get("rastro")
            if cupo_lleno and rastro is not None and rastro < lista and not (completa or objetivo):
                continue                                  # escalera hecha y en El Rastro sale más barata
            compras.append((not completa, not objetivo, -(vale - lista), ref, lista))
        if compras:
            *_, ref, lista = min(compras)
            usadas.add(ref)
            pendientes.append({"vendedor": vendedor, "lado": "compra", "carta": ref, "lista": lista})
    nivel = {v: n for v, n in (niveles or {}).items() if isinstance(n, (int, float)) and not isinstance(n, bool)}
    pendientes.sort(key=lambda o: -nivel.get(o["vendedor"], 0))        # estable: sin niveles, el orden de siempre
    return pendientes
