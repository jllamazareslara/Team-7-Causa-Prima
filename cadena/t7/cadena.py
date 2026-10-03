"""La cadena: todos los agentes, en orden, una vez por tick. Es lo que los encadena.

    lectura (solo números + el texto aparte)  →  tick()  →  acciones (mensajes, UNA firma como mucho, cierres, diario)

Sin red y sin azar: no llama al juego, no lee la clave y no acepta nada. Quien habla con el juego (el director:
`director.py` o el `play.py` del repositorio) solo tiene que hacer dos cosas: construir `lectura` y aplicar `acciones`.

Orden dentro de un tick (cada paso es un agente):
    1. Escudo        mira el texto que llega, cuenta avisos por contraparte y apunta candidatos a mala fe
                     (el texto dice un precio y la oferta pide otro). No cambia ninguna decisión.
    2. Espía         lee pistas del texto de los vendedores (número y tono) y solo las apunta; pregunta a un vendedor
                     en una conversación de prueba al día, con su escalera ya hecha; y en duelos manda un canario y,
                     si el rival lee el texto, una pregunta directa.
                     REGLA: lo que sale de un texto va al diario y a la elección de las palabras, nunca a un precio.
    3. Regateador    una decisión por conversación con un vendedor: precio nuevo, aceptar o retirarse.
    4. Duelista      una decisión por duelo.
    5. Cambista      lo que renta del tablón de El Rastro (solo cuando el director lo trae).
    6. Contable + Guardia   de todas las propuestas de aceptar, el Director elige el orden y el Guardia firma UNA.
    7. Portavoz      escribe el mensaje de cada precio nuevo (o una pregunta del Espía, si toca).
    8. Diario        una línea por decisión, con su motivo.

lectura = {
  "tick": n, "efectivo": n, "cuenta": {ref: copias},
  "vendedores": [{"id": hilo, "vendedor": "abuela", "lado": "compra"|"venta", "carta": ref,
                  "suyas": [su apertura, ...], "nuestras": [...], "final": bool, "oferta_id": id o None,
                  "texto": su último mensaje, "lista": precio de lista (vendiendo), "cerrado": None|"cooloff"|...}],
  "duelos":     [{"id", "rol": "seller"|"buyer", "limite", "rival": [...], "nuestras": [...], "ronda", "rondas",
                  "ticks_restantes", "texto", "escenario", "dias": bool}],
  "tablon":     ofertas de El Rastro tal como las da board("rastro"), o None si este tick no se ha leído
}
"""
import math
import re

from . import cambista, defensa, duelo, guardia, ojeador, params, prioridad, sondas, tienda
from . import valor as V
from .portavoz import Portavoz

DIA_POR_DEFECTO = 5          # duelos con día de entrega: día 5 hasta ver uno real


class Memoria:
    """Lo que la cadena recuerda entre ticks. Se puede guardar en disco con a_dict() y recuperar con de_dict()."""

    def __init__(self):
        self.portavoz = Portavoz()
        self.escudo = defensa.Contador()
        self.sondas = {}        # hilo → tipos de pregunta ya usados
        self.pistas = {}        # hilo → pista de su suelo sacada del texto
        self.escenarios = {}    # escenario → {rol: nuestro límite}: es el límite del rival cuando jugamos el otro lado
        self.mala_fe = []       # candidatos a señalar: lo decide el equipo, nunca la cadena
        self.capturas = {}      # vendedor → parte del rango capturada en cada trato (para la escalera)
        self.vistos = {}        # contraparte → último texto ya revisado (para no contar dos veces el mismo)
        self.tonos = {}         # hilo → [(nuestra oferta, "lejos"|"cerca")]: el termómetro del Espía
        self.leen = {}          # duelo → ¿el agente rival lee el texto? (lo dice el canario)
        self.preguntas = {}     # duelo → preguntas directas ya hechas
        self.sondeadas = {}     # "vendedor|día" → conversaciones en las que el Espía ha preguntado
        self.mercado = {}       # carta → últimos precios a los que otros equipos la anuncian en El Rastro (Cambista)
        self.demanda = {}       # carta → últimos precios que otros equipos OFRECEN por ella en El Rastro (Cambista)
        self.historial = {}     # carta → [[tick, precio, lado, quién]]: el mercado en el tiempo (Ojeador)

    def a_dict(self):
        return {"sondeadas": self.sondeadas, "sondas": self.sondas, "pistas": self.pistas, "escenarios": self.escenarios, "mala_fe": self.mala_fe,
                "capturas": self.capturas, "avisos": self.escudo.cuenta, "frases": self.portavoz.usadas,
                "vistos": self.vistos, "tonos": self.tonos, "leen": self.leen, "preguntas": self.preguntas,
                "mercado": self.mercado, "demanda": self.demanda, "historial": self.historial}

    @classmethod
    def de_dict(cls, d):
        m = cls()
        d = d or {}
        m.sondas, m.pistas = d.get("sondas", {}), d.get("pistas", {})
        m.sondeadas = d.get("sondeadas", {})
        m.escenarios, m.mala_fe = d.get("escenarios", {}), d.get("mala_fe", [])
        m.capturas, m.vistos = d.get("capturas", {}), d.get("vistos", {})
        m.tonos, m.leen, m.preguntas = d.get("tonos", {}), d.get("leen", {}), d.get("preguntas", {})
        m.escudo.cuenta, m.portavoz.usadas = d.get("avisos", {}), d.get("frases", {})
        m.mercado, m.demanda = d.get("mercado", {}), d.get("demanda", {})
        m.historial = d.get("historial", {})
        return m


def _solo_el_precio(texto, precio):
    """Filtro de salida mínimo: el mensaje no lleva otro número que nuestro precio."""
    return all(int(x) == int(precio) for x in re.findall(r"\d+", texto or ""))


def _limite_vendedor(c, cuenta):
    """Nuestro tope (comprando) o suelo (vendiendo) para esa carta, con el bono de página incluido."""
    if c["lado"] == "compra":
        return math.floor(V.valor_recibir(cuenta, [c["carta"]]))
    perdida = V.valor_entregar(cuenta, [c["carta"]])
    return None if perdida is None else math.ceil(perdida + 1)


def _propuesta_vendedor(c, precio):
    if c["lado"] == "compra":
        return {"tipo": "vendedor", "recibo": {"cartas": [c["carta"]]}, "entrego": {"primas": precio}}
    return {"tipo": "vendedor", "recibo": {"primas": precio}, "entrego": {"cartas": [c["carta"]]}}


def tick(lectura, mem, p=None, forzar=None, ordenes=None, stop=False):
    """Un tick entero. Devuelve acciones = {"mensajes", "firma", "cerrar", "diario", "mala_fe"}."""
    p = p or params.cargar()
    forzar, ordenes = forzar or {}, ordenes or {}
    t = lectura.get("tick")
    cuenta, efectivo = lectura.get("cuenta", {}), lectura.get("efectivo", 0)
    mensajes, cerrar, cola, diario, mala_fe = [], [], [], [], []

    def apunta(quien, texto):
        diario.append(f"tick {t}  {quien:<10} {texto}")

    def nuevo(clave, texto):
        """True solo la primera vez que vemos este texto de esta contraparte."""
        if not texto or mem.vistos.get(clave) == texto:
            return False
        mem.vistos[clave] = texto
        return True

    # ---------- vendedores: Escudo → Espía → Regateador ----------
    def paso_vendedor(c):
        hilo, quien, texto = str(c["id"]), c["vendedor"], c.get("texto") or ""
        es_nuevo = nuevo(hilo, texto)
        if es_nuevo:
            motivos, _ = mem.escudo.anotar(quien, texto)
            if motivos:
                apunta("ESCUDO", f"{quien}: {', '.join(motivos)}")
        if c.get("cerrado"):
            apunta("TIENDA", f"{quien} cerró la conversación ({c['cerrado']})")
            return
        if not V.conocida(c["carta"]):                       # conocer el valor antes de comprar: sin dato, no se opera
            cerrar.append({"destino": "vendedor", "id": c["id"], "motivo": "carta sin valor conocido"})
            apunta("TIENDA", f"{quien} · {c['carta']}: no sabemos cuánto nos vale (barrio o código nuevo), se cierra")
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
        motivo = defensa.incoherencia(texto, suya) if es_nuevo else None
        if motivo:
            mala_fe.append({"hilo": c["id"], "vendedor": quien, "motivo": motivo, "tick": t})
            apunta("ESCUDO", f"{quien} · candidato a mala fe: {motivo}. Lo decide el equipo.")

        limite = _limite_vendedor(c, cuenta)
        if limite is None or (c["lado"] == "venta" and V.protegida(cuenta, c["carta"])):
            cerrar.append({"destino": "vendedor", "id": c["id"], "motivo": "carta protegida o que ya no tenemos"})
            apunta("TIENDA", f"{quien} · {c['carta']}: protegida o ya no la tenemos, se cierra")
            return
        if c["lado"] == "compra":                            # no regatear por algo que la caja no puede pagar
            caja = _caja_para_comprar(c["carta"], cuenta, efectivo, p, ordenes)
            if caja < 1:
                cerrar.append({"destino": "vendedor", "id": c["id"], "motivo": "no hay caja para esta compra"})
                apunta("TIENDA", f"{quien} · {c['carta']}: no hay caja para comprar sin tocar la reserva, se cierra")
                return
            limite = min(limite, caja)
        pf = params.perfil(p, quien)
        st = {"lado": c["lado"], "limite": limite, "suyas": c["suyas"], "nuestras": c.get("nuestras", []),
              "final": bool(c.get("final")), "lista": c.get("lista")}
        if not st["nuestras"] and c["lado"] == "compra" and ordenes.get("compras") == "ninguna":
            cerrar.append({"destino": "vendedor", "id": c["id"], "motivo": "caja seca: no se abren compras"})
            apunta("TIENDA", f"{quien} · {c['carta']}: caja seca, no se abre la compra")
            return
        accion, precio, por_que = tienda.decidir(st, pf, p)
        apunta("TIENDA", f"{quien} · {c['lado']} {c['carta']} · él {suya} · {accion} {precio if precio is not None else ''} · {por_que}")
        if accion == "retirarse":
            cerrar.append({"destino": "vendedor", "id": c["id"], "motivo": por_que})
        elif accion == "aceptar":
            cola.append({"tipo": "final_vendedor" if st["final"] else "vendedor", "urgente": st["final"],
                         "destino": "vendedor", "id": c["id"], "oferta_id": c.get("oferta_id"), "precio": suya,
                         "propuesta": _propuesta_vendedor(c, suya), "vendedor": quien, "apertura": c["suyas"][0]})
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
                if txt and _solo_el_precio(txt, precio):
                    usadas.append(tipo)
                    if hilo not in de_prueba:
                        de_prueba.append(hilo)
                    apunta("ESPÍA", f"{quien} · pregunta «{tipo}» ({len(usadas)} de {pf.get('sondas_max', 0)})")
                else:
                    txt = None
            if txt is None:
                txt = mem.portavoz.vendedor(quien, precio, firme)
            mensajes.append({"destino": "vendedor", "id": c["id"], "precio": precio, "texto": txt})

    def aislado(paso, cosa, nombre):
        """Un fallo en una conversación, un duelo o una oferta afecta solo a esa: se apunta y el resto del tick sigue."""
        try:
            return paso(cosa)
        except Exception as e:
            ident = cosa.get("id") if isinstance(cosa, dict) else None
            apunta("ERROR", f"{nombre} {ident}: {type(e).__name__}: {e} · se salta, el resto sigue")
            return None

    for c in lectura.get("vendedores") or []:
        aislado(paso_vendedor, c, "vendedor")

    # ---------- duelos: Escudo → Duelista ----------
    def paso_duelo(d):
        quien = f"duelo-{d['id']}"
        if nuevo(quien, d.get("texto") or ""):
            if quien not in mem.leen and d.get("nuestras"):
                lee = sondas.lee_texto(d["texto"])
                if lee is not None:
                    mem.leen[quien] = lee
                    apunta("ESPÍA", f"{quien} · el rival {'lee' if lee else 'no lee'} el texto")
            if mem.preguntas.get(quien, 0) and d.get("rival"):
                dichos = [n for n in defensa.numeros(d["texto"]) if n != d["rival"][-1]]
                if dichos:
                    apunta("ESPÍA", f"{quien} · tras la pregunta, el rival escribe {dichos}: se apunta, no cambia ningún precio")
            motivos, _ = mem.escudo.anotar(quien, d["texto"])
            if motivos:
                apunta("ESCUDO", f"{quien}: {', '.join(motivos)}" + (" · modo firme" if mem.escudo.firme(quien) else ""))
        firme = mem.escudo.firme(quien)
        if forzar.get("duelo") == "apagado":
            return
        rol, lim = d["rol"], d["limite"]
        esc = d.get("escenario")
        lr = None
        if esc is not None:
            visto = mem.escenarios.setdefault(str(esc), {})
            visto[rol] = lim
            lr = visto.get("buyer" if rol == "seller" else "seller")
        st = {"rol": rol, "limite": lim, "rival": d.get("rival", []), "nuestras": d.get("nuestras", []),
              "ronda": d.get("ronda", len(d.get("nuestras", []))), "rondas": d.get("rondas"), "limite_rival": lr}
        accion, precio, por_que = duelo.decidir(st, p)
        apunta("DUELISTA", f"{quien} · {rol} · rival {st['rival'][-1] if st['rival'] else '—'} · {accion} "
                           f"{precio if precio is not None else ''} · {por_que}")
        if accion == "aceptar":
            quedan = d.get("ticks_restantes")
            cola.append({"tipo": "duelo", "urgente": quedan is not None and quedan <= 2, "destino": "duelo",
                         "id": d["id"], "precio": precio, "ganancia": duelo.ganancia(rol, lim, precio)})
        elif accion == "ofrecer":
            nuestras, rival = st["nuestras"], st["rival"]
            cedimos = bool(nuestras) and precio != nuestras[-1]
            cerca = bool(rival) and abs(rival[-1] - precio) <= 0.1 * max(abs(precio), 1)
            rival_firme = len(rival) >= 2 and rival[-1] == rival[-2]
            tactica, txt = mem.portavoz.duelo(precio, st["ronda"], cedimos, cerca, rival_firme, firme)
            if not firme:                                   # el Espía en duelos: solo palabras normales, nunca inyección
                canario = sondas.canario(st["ronda"], precio) if not nuestras else None
                pregunta = None if canario else sondas.pregunta_duelo(mem.leen.get(quien), mem.preguntas.get(quien, 0), precio)
                if canario and _solo_el_precio(canario, precio):
                    tactica, txt = "canario", canario
                elif pregunta and _solo_el_precio(pregunta, precio) and mem.preguntas.get(quien, 0) < 1:
                    mem.preguntas[quien] = mem.preguntas.get(quien, 0) + 1
                    tactica, txt = "pregunta", pregunta
            m = {"destino": "duelo", "id": d["id"], "precio": precio, "texto": txt, "tactica": tactica}
            if d.get("dias"):
                m["dias"], por_dia = duelo.mejor_dia(d.get("pesos_dias"), DIA_POR_DEFECTO)
                if not nuestras:
                    apunta("DUELISTA", f"{quien} · {por_dia}")
            mensajes.append(m)

    for d in lectura.get("duelos") or []:
        aislado(paso_duelo, d, "duelo")

    # ---------- El Rastro: Cambista ----------
    def paso_rastro(tablon):
        tablon = [o for o in tablon if isinstance(o, dict)]
        apuntar_mercado(mem.mercado, tablon, mem.demanda)
        mom, esc = lectura.get("momento") or {}, lectura.get("escasez") or {}
        pasado = {r: list(v) for r, v in mem.historial.items()}       # se compara con lo visto ANTES de este tick
        ojeador.observar(mem.historial, tablon, t)
        for o in cambista.oportunidades(tablon, cuenta, efectivo, reserva=p["guardia.reserva_efectivo"])[:3]:
            prop = o["propuesta"]
            compra = prop["recibo"]["cartas"] and not prop["entrego"]["cartas"] and len(prop["recibo"]["cartas"]) == 1
            if compra:                                   # el Ojeador decide CUÁNDO: ya, o esperar a que baje
                ref = prop["recibo"]["cartas"][0]
                ya, porque = ojeador.comprar_ahora(
                    ref, prop["entrego"]["primas"], V.valor_recibir(cuenta, [ref]),
                    ojeador.tendencia(pasado, ref, t if isinstance(t, (int, float)) else 0), mom,
                    esc.get(ref), completa=V.estado_pagina(cuenta, V.barrio(ref))[1] == [ref])
                if not ya:
                    apunta("OJEADOR", f"El Rastro · oferta {o['oferta']} ({ref} a {prop['entrego']['primas']}) · {porque}")
                    continue
            apunta("CAMBISTA", f"El Rastro · oferta {o['oferta']} de {o['maker']} · neto {o['neto']:+.1f}")
            oferta = next((x for x in tablon if x.get("id") == o["oferta"]), None)
            cola.append({"tipo": "equipo", "destino": "rastro", "id": o["oferta"], "oferta_id": o["oferta"],
                         "neto": o["neto"], "propuesta": o["propuesta"], "oferta_juego": oferta})

    if lectura.get("feed"):                              # tratos hechos del feed público: precios reales pagados
        aislado(lambda f: ojeador.observar_feed(mem.historial, f, t), lectura["feed"], "feed")
    tablon = lectura.get("tablon")
    if tablon and forzar.get("equipo") != "apagado" and forzar.get("rastro") != "apagado":
        aislado(paso_rastro, tablon, "El Rastro")

    # ---------- una sola firma: Director → Contable → Guardia ----------
    def orden(o):
        return (0 if o.get("urgente") else 1, {"duelo": 0, "final_vendedor": 1, "equipo": 2, "vendedor": 3}[o["tipo"]],
                -o.get("neto", 0))

    def paso_firma(o):
        """Devuelve la firma si el Guardia la da. Si ya hay una en este tick, el Guardia dice que no."""
        if o["tipo"] == "duelo":
            ok, motivo = guardia.revisar_duelo(o["ganancia"], firma is not None, stop, forzar)
            ev = None
        else:
            ok, motivo, ev, _ = guardia.revisar(o["propuesta"], o.get("oferta_juego"), cuenta, efectivo, p,
                                                ya_firmado_este_tick=firma is not None, stop=stop, forzar=forzar,
                                                tope_por_trato=ordenes.get("tope_por_trato"))
        apunta("GUARDIA", f"{o['destino']} {o['id']} · {'FIRMA' if ok else 'no firma'} · {motivo}")
        if not ok:
            return None
        if o["tipo"] in ("vendedor", "final_vendedor") and o["apertura"] != o["precio"]:
            mem.capturas.setdefault(o["vendedor"], []).append({"apertura": o["apertura"], "precio": o["precio"],
                                                               "dia": lectura.get("dia")})
        return {"destino": o["destino"], "id": o["id"], "oferta_id": o.get("oferta_id"), "precio": o.get("precio"),
                "motivo": motivo, "ficha": ev}

    firma = None
    for o in sorted(cola, key=orden):
        firma = aislado(paso_firma, o, "firma") or firma      # un error al revisar una propuesta nunca firma nada

    mem.mala_fe.extend(mala_fe)
    return {"mensajes": mensajes, "firma": firma, "cerrar": cerrar, "diario": diario, "mala_fe": mala_fe}


MERCADO_RECUERDA = 12      # precios vistos por carta que guarda el Cambista


def _apunta(d, ref, precio):
    vistos = d.setdefault(ref, [])
    vistos.append(precio)
    del vistos[:-MERCADO_RECUERDA]


def apuntar_mercado(mercado, tablon, demanda=None):
    """El Cambista aprende los precios del tablón de El Rastro (los últimos MERCADO_RECUERDA por carta):
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


def lista_compra(cuenta, efectivo, p, mercado=None, listas=None, pagado=None, final=False):
    """El Cambista compra: la lista de la compra (ver cambista.lista_compra)."""
    return cambista.lista_compra(cuenta, efectivo, p, mercado=mercado, listas=listas, pagado=pagado, final=final)


def peticiones_rastro(lista, cuenta, efectivo, p, activas=None, caducidades=None, demanda=None, final=False):
    """El Cambista compra: qué peticiones publicar en El Rastro ahora (ver cambista.peticiones)."""
    return cambista.peticiones(lista, cuenta, efectivo, p, activas, caducidades, demanda=demanda, final=final)


def trueques_rastro(lista, cuenta, p, ocupadas=(), activas=(), vivos=None):
    """El Cambista cambia: qué cambios carta por carta ofrecer en El Rastro (ver cambista.trueques)."""
    return cambista.trueques(lista, cuenta, p, ocupadas, activas, vivos=vivos)


def _caja_para_comprar(carta, cuenta, efectivo, p, ordenes):
    """Lo máximo que la caja deja pagar por esta carta: lo que queda sobre la reserva y, con la caja justa, el tope
    por trato (salvo la carta que completa una página, igual que en el Guardia)."""
    libre = math.floor(efectivo - p["guardia.reserva_efectivo"])
    tope = ordenes.get("tope_por_trato")
    if tope is None or V.estado_pagina(cuenta, V.barrio(carta))[1] == [carta]:
        return libre
    return min(libre, tope)


def anuncios_rastro(cuenta, p, activos=None, ocupadas=(), excluidas=(), listas=None, caducidades=None, maximo=12):
    """El Cambista vende: qué anunciar en El Rastro. Solo lo que podemos dar sin perder valor, nunca una protegida,
    y solo comunes y poco comunes (una rara la decide el equipo).

    activos     = {ref: anuncios nuestros vivos}: esa copia ya está anunciada
    ocupadas    = refs con una venta abierta con un vendedor: esa copia no se anuncia además
    excluidas   = refs que se guardan para los vendedores (les quedan tratos de escalera hoy)
    listas      = {ref: precio de lista}; sin dato, la base de su rareza
    caducidades = {ref: veces que su anuncio caducó sin venderse}: cada una baja el precio
    Devuelve [{"carta", "precio", "pierde"}], como mucho `maximo`. El precio nunca baja de lo que nos vale + 1."""
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
                        guardar=None, niveles=None, senales=None):
    """Qué operación abrir con cada vendedor que no tiene conversación: primero vender, luego comprar.

    menus = {vendedor: {"vende": {ref: precio de lista}, "compra": {ref: lo que ofrece de entrada}}}
    abiertas = vendedores que ya tienen conversación. Devuelve [{"vendedor", "lado", "carta", "lista"}], una por vendedor.
    tratos, max_tratos = calidad antes que cantidad: con max_tratos tratos regateados hoy con un vendedor (solo cuentan
    los tres mejores), ya no se le abren compras salvo la carta que completa una página. Vender sigue: da efectivo.
    Una carta cuyo valor no conocemos (barrio o código nuevo) no se abre nunca.
    guardar = {ref: vendedor al que sí se vende ahora, o None} (guion.reservadas): cartas que esperan una fiebre.
    Durante la fiebre van primero al vendedor de la fiebre.
    niveles = {vendedor: nivel}: los niveles altos pesan más en la escalera, así que sus operaciones van delante.
    senales = {ref: {"rastro": precio hoy en El Rastro con comisión o None, "escasa": bool}} (ojeador.senales_vendedor):
    una carta casi agotada se compra antes; con la escalera de ese vendedor ya hecha, no se le compra lo que
    sale más barato en El Rastro (lo compra el Cambista).
    """
    ordenes, tratos, guardar = ordenes or {}, tratos or {}, guardar or {}
    urgentes = set(ordenes.get("vender") or [])
    pendientes, usadas = [], set()
    for vendedor, menu in menus.items():
        if vendedor in abiertas or not isinstance(menu, dict):
            continue
        ventas = [(ref, perdida) for ref, perdida in cambista.vendibles(cuenta)
                  if ref in (menu.get("compra") or {}) and ref not in usadas and V.conocida(ref)
                  and (ref not in guardar or guardar[ref] == vendedor)
                  and V.rareza(ref) in ("common", "uncommon") and menu["compra"][ref] * 3 > perdida]
        ventas.sort(key=lambda x: (x[0] not in guardar, x[0] not in urgentes, x[1]))
        if ventas:
            ref = ventas[0][0]
            usadas.add(ref)
            pendientes.append({"vendedor": vendedor, "lado": "venta", "carta": ref, "lista": menu["compra"][ref]})
            continue
        if ordenes.get("compras") == "ninguna":
            continue
        cupo_lleno = max_tratos is not None and tratos.get(vendedor, 0) >= max_tratos
        compras = []
        for ref, lista in (menu.get("vende") or {}).items():
            if cuenta.get(ref, 0) > 0 or ref in usadas or not V.conocida(ref):
                continue
            vale = V.valor_recibir(cuenta, [ref])
            completa = V.estado_pagina(cuenta, V.barrio(ref))[1] == [ref]
            if vale < 0.8 * lista or (cupo_lleno and not completa):
                continue
            if ordenes.get("compras") == "escalera_y_pagina" and not completa and lista > (ordenes.get("tope_por_trato") or 0):
                continue
            s = (senales or {}).get(ref) or {}
            rastro = s.get("rastro")
            if cupo_lleno and rastro is not None and rastro < lista and not completa:
                continue                                  # escalera hecha y en El Rastro sale más barata
            compras.append((not completa, not s.get("escasa"), -(vale - lista), ref, lista))
        if compras:
            _, _, _, ref, lista = min(compras)
            usadas.add(ref)
            pendientes.append({"vendedor": vendedor, "lado": "compra", "carta": ref, "lista": lista})
    nivel = {v: n for v, n in (niveles or {}).items() if isinstance(n, (int, float)) and not isinstance(n, bool)}
    pendientes.sort(key=lambda o: -nivel.get(o["vendedor"], 0))        # estable: sin niveles, el orden de siempre
    return pendientes
