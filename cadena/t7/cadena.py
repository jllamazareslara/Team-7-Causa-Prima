"""La cadena: todos los agentes, en orden, una vez por tick. Es lo que los encadena.

    lectura (solo números + el texto aparte)  →  tick()  →  acciones (mensajes, UNA firma como mucho, cierres, diario)

Sin red y sin azar: no llama al juego, no lee la clave y no acepta nada. Quien habla con el juego (el `play.py` del
repositorio u otro programa) solo tiene que hacer dos cosas: construir `lectura` y aplicar `acciones`.

Orden dentro de un tick (cada paso es un agente):
    1. Ojos          leen el juego y pasan los números a la Contable. Ayudante: el Escudo (texto sospechoso: avisos por
                     contraparte, modo firme, candidatos a mala fe). Ver `ojos.py`.
       Al lado:      Guion    anticipa lo que viene (calendario): lo apunta en el diario, no cambia ninguna decisión.
                     Ojeador  vigila los precios de El Rastro y se los pasa al Regateador y al Cambista. Ver `ojeador.py`.
    2. Contable      ¿renta? ¿cuánto?: hace las cuentas con la calculadora y se las da a los negociadores (tope o suelo,
                     caja) y, con cada trato, la ficha que mira el Guardia. No decide. Ver `contable.py`.
    3. Negociadores  hacen el trámite, cada uno con sus números y sus ayudantes:
                       Cambista    El Rastro y equipos            + Portavoz
                       Duelista    duelos                         + Portavoz · Espía
                       Regateador  vendedores                     + Portavoz · Observador · Espía
                     Espía: lee pistas del texto y solo las apunta; pregunta en una conversación de prueba al día; en
                     duelos manda un canario y, si el rival lee el texto, una pregunta directa.
                     REGLA: lo que sale de un texto va al diario y a las palabras, nunca a un precio.
                     Observador: el perfil de cada vendedor (con quién ser duro); uno sin perfil propio es "desconocido".
                     Portavoz: escribe el mensaje de cada precio nuevo. (En El Rastro las ofertas no llevan texto: con el
                     Cambista solo escribiría si un día hablamos con equipos por conversación.)
    4. Guardia       el único que firma: de todas las propuestas de aceptar firma UNA, con la ficha de la Contable.
    5. Diario        una línea por decisión, con su motivo.

lectura = {
  "tick": n, "efectivo": n, "cuenta": {ref: copias},
  "vendedores": [{"id": hilo, "vendedor": "abuela", "lado": "compra"|"venta", "carta": ref,
                  "suyas": [su apertura, ...], "nuestras": [...], "final": bool, "oferta_id": id o None,
                  "texto": su último mensaje, "lista": precio de lista (vendiendo), "cerrado": None|"cooloff"|...}],
  "duelos":     [{"id", "rol": "seller"|"buyer", "limite", "rival": [...], "nuestras": [...], "ronda", "rondas",
                  "ticks_restantes", "texto", "escenario", "dias": bool}],
  "tablon":     ofertas de El Rastro tal como las da board("rastro"), o None si este tick no se ha leído,
  "calendario": la respuesta de schedule() para el Guion (opcional), "hora": horas de juego ahora (opcional)
}
"""
import math
from . import cambista, contable, defensa, duelo, guardia, guion, ojeador, ojos, params, prioridad, sondas, tienda
from .ojeador import MERCADO_RECUERDA, apuntar_mercado  # noqa: F401  (se usan desde fuera: pruebas)
from . import valor as V
from .portavoz import Portavoz

DIA_POR_DEFECTO = 5          # duelos con día de entrega: día 5 hasta ver uno real
NO_INSISTIR = {"pilar"}      # memoria y astucia altas: una carta que no quiso a nuestro precio no se le ofrece otra vez ese día


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
        self.calendario = {}    # último /api/schedule leído + el tick en que se leyó (Guion y Ojeador)
        self.escasez = {}       # carta → acuñadas / tirada, del catálogo (Ojeador)
        self.descansos = {}     # vendedor → hasta cuándo no se le abre nada (Ojeador)
        self.niveles = {}       # vendedor → nivel: la escalera pesa más en los niveles altos
        self.sin_acuerdo = {}   # "vendedor|carta|día" → motivo: con NO_INSISTIR no se le vuelve a ofrecer ese día

    def a_dict(self):
        return {"sondeadas": self.sondeadas, "sondas": self.sondas, "pistas": self.pistas, "escenarios": self.escenarios, "mala_fe": self.mala_fe,
                "capturas": self.capturas, "avisos": self.escudo.cuenta, "frases": self.portavoz.usadas,
                "vistos": self.vistos, "tonos": self.tonos, "leen": self.leen, "preguntas": self.preguntas,
                "mercado": self.mercado, "demanda": self.demanda, "historial": self.historial,
                "calendario": self.calendario, "escasez": self.escasez, "descansos": self.descansos, "niveles": self.niveles,
                "sin_acuerdo": self.sin_acuerdo}

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
        m.calendario, m.escasez = d.get("calendario", {}), d.get("escasez", {})
        m.descansos, m.niveles = d.get("descansos", {}), d.get("niveles", {})
        m.sin_acuerdo = d.get("sin_acuerdo", {})
        return m


# ---------------------------------------------------------------- El Ojeador y El Guion dentro de la cadena
#
# Viven aquí y no en quien lanza la cadena (hoy jugar.py). Ese programa solo pone en la lectura
# lo que lee del juego, tal cual, cuando lo lee:
#   lectura["calendario"]  /api/schedule        lectura["catalogo"]  /api/catalog     lectura["feed"]  /api/feed
#   lectura["niveles"]     {vendedor: nivel}    lectura["t_hours"]   de /api/clock    lectura["tick_segundos"]
#   y en cada vendedor cerrado: "cerrado" (closed_reason) y "until_tick"
# ojear() lo guarda en la memoria y deja en la lectura "hora", "momento" y "escasez" para el resto de la cadena.

def hora_de_juego(mem, lectura):
    """La hora de juego: la del reloj si viene; si no, la del último calendario más los ticks pasados desde entonces."""
    if isinstance(lectura.get("t_hours"), (int, float)):
        return lectura["t_hours"]
    cal, t = mem.calendario, lectura.get("tick")
    if not cal or not isinstance(cal.get("now_hours"), (int, float)):
        return None
    if isinstance(t, (int, float)) and isinstance(cal.get("tick"), (int, float)):
        return cal["now_hours"] + (t - cal["tick"]) * (lectura.get("tick_segundos") or 30) / 3600
    return cal["now_hours"]


def ojear(lectura, mem):
    """Paso del Ojeador al empezar el tick: guarda lo que llegó del juego y calcula hora, momento y escasez."""
    t = lectura.get("tick")
    cal = lectura.get("calendario")
    if isinstance(cal, dict) and isinstance(cal.get("now_hours"), (int, float)):
        mem.calendario = {"now_hours": cal["now_hours"], "upcoming": cal.get("upcoming") or [], "tick": t}
    if lectura.get("catalogo"):
        esc = ojeador.escasez(lectura["catalogo"])
        if esc:
            mem.escasez = esc
    if isinstance(lectura.get("niveles"), dict):
        mem.niveles.update(lectura["niveles"])
    if lectura.get("feed"):                              # tratos hechos del feed público: precios reales pagados
        ojeador.observar_feed(mem.historial, lectura["feed"], t)
    h = hora_de_juego(mem, lectura)
    for c in lectura.get("vendedores") or []:            # cupo agotado o enfado: ese vendedor descansa
        if isinstance(c, dict) and c.get("cerrado") and c.get("vendedor"):
            desc = ojeador.descanso(c["cerrado"], h, t, c.get("until_tick"))
            if desc:
                mem.descansos[c["vendedor"]] = desc
    lectura["hora"] = h
    if mem.calendario and h is not None:
        lectura["momento"] = ojeador.momento(guion.eventos(mem.calendario), h)
    else:
        lectura.setdefault("momento", {"fase": "normal", "vender": 1.0, "comprar": "normal", "motivo": ""})
    lectura["escasez"] = mem.escasez
    return lectura


def _reservadas(cuenta, mem, lectura):
    h = lectura.get("hora")
    if not mem.calendario or h is None:
        return {}
    return guion.reservadas(dict(cuenta), guion.eventos(mem.calendario), h)


def operaciones(cuenta, efectivo, menus, mem, lectura, ordenes=None, abiertas=(), tratos=None, max_tratos=None):
    """El Regateador con sus consejeros: cola_de_operaciones() + El Guion (cartas que esperan una fiebre) +
    El Ojeador (vendedores que descansan, El Rastro más barato, cartas que se agotan) + niveles de la escalera.
    Es lo que llama quien lanza la cadena para abrir conversaciones con vendedores."""
    t = lectura.get("tick")
    quietos = {v for v, d in mem.descansos.items() if ojeador.descansa(d, lectura.get("hora"), t)}
    refs = {r for m in (menus or {}).values() if isinstance(m, dict) for r in (m.get("vende") or {})}
    senales = ojeador.senales_vendedor(mem.historial, refs, t if isinstance(t, (int, float)) else 0, mem.escasez)
    hoy = f"|{lectura.get('dia')}"
    evitar = {tuple(k[:-len(hoy)].split("|", 1)) for k in mem.sin_acuerdo if k.endswith(hoy)}
    return cola_de_operaciones(cuenta, efectivo, menus, ordenes, set(abiertas) | quietos, tratos, max_tratos,
                               guardar=_reservadas(cuenta, mem, lectura), niveles=mem.niveles, senales=senales,
                               evitar=evitar)


def anuncios(cuenta, p, mem, lectura, activos=None, ocupadas=(), excluidas=(), listas=None, caducidades=None, maximo=12):
    """El Cambista vende con sus consejeros: anuncios_rastro() sin las cartas que esperan una fiebre (Guion) y con el
    precio ajustado al mercado y al momento (Ojeador), nunca por debajo de lo que nos vale + 1."""
    excluidas = set(excluidas) | set(_reservadas(cuenta, mem, lectura))
    out = anuncios_rastro(cuenta, p, activos, ocupadas, excluidas, listas, caducidades, maximo)
    t = lectura.get("tick") if isinstance(lectura.get("tick"), (int, float)) else 0
    mom = lectura.get("momento") or {"fase": "normal", "vender": 1.0}
    for n in out:
        antes = n["precio"]
        n["precio"] = ojeador.precio_venta(antes, math.ceil(n["pierde"] + 1), ojeador.tendencia(mem.historial, n["carta"], t),
                                           mom, mem.escasez.get(n["carta"]))
        if n["precio"] != antes:
            n["ojeador"] = f"{antes} → {n['precio']} ({mom.get('fase', 'normal')})"
    return out


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
    try:                                                 # el Ojeador primero: hora, momento, escasez, descansos
        ojear(lectura, mem)
    except Exception as e:
        diario.append(f"tick {t}  {'ERROR':<10} Ojeador: {type(e).__name__}: {e} · se sigue sin él")

    def apunta(quien, texto):
        diario.append(f"tick {t}  {quien:<10} {texto}")

    def aislado(paso, cosa, nombre):
        """Un fallo en una conversación, un duelo o una oferta afecta solo a esa: se apunta y el resto del tick sigue."""
        try:
            return paso(cosa)
        except Exception as e:
            ident = cosa.get("id") if isinstance(cosa, dict) else None
            apunta("ERROR", f"{nombre} {ident}: {type(e).__name__}: {e} · se salta, el resto sigue")
            return None

    # ---------- 1. Ojos (con el Escudo): leen el juego ----------
    vista = ojos.mirar(lectura, mem, apunta)
    mala_fe.extend(vista["mala_fe"])

    # ---------- al lado: Guion (lo que viene) y Ojeador (los precios) ----------
    def paso_guion(cal):                                 # el calendario y la hora ya los guardó ojear()
        h = lectura.get("hora")
        if h is None:
            return
        for e, j, falta in guion.ahora(guion.eventos(cal), h)["preparar"]:
            clave = f"guion|{j['clave']}|{e['h']}"
            if mem.vistos.get(clave) is None:                # cada evento se avisa una vez
                mem.vistos[clave] = j["titulo"]
                apunta("GUION", f"{j['titulo']} en {falta:.1f} h" + (f" · {j['antes'][0]}" if j["antes"] else ""))

    if mem.calendario:
        aislado(paso_guion, mem.calendario, "guion")
    precios = ojeador.vigilar(lectura, mem)

    # ---------- vendedores: Contable → Regateador (con Portavoz, Observador y Espía) ----------
    def paso_vendedor(c):
        hilo, quien, texto = str(c["id"]), c["vendedor"], c.get("texto") or ""
        cuentas = contable.para_vendedor(c, cuenta, efectivo, p, ordenes)
        es_nuevo = hilo in vista["textos_nuevos"]
        def sin_acuerdo(motivo):                         # con Pilar no se insiste: esa carta, ese día, ya no
            if quien in NO_INSISTIR:
                mem.sin_acuerdo[f"{quien}|{c['carta']}|{lectura.get('dia')}"] = motivo
        if c.get("cerrado"):
            apunta("TIENDA", f"{quien} cerró la conversación ({c['cerrado']})")
            sin_acuerdo(c["cerrado"])
            return
        if not cuentas["conocida"]:                          # conocer el valor antes de comprar: sin dato, no se opera
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
        apunta("CONTABLE", f"{quien} · {c['lado']} {c['carta']} · nos vale {cuentas['nos_vale']:.1f} · "
                           f"{'tope' if c['lado'] == 'compra' else 'suelo'} {limite}")
        pr = ojeador.precios(precios, c["carta"])
        if pr["piden"] is not None or pr["ofrecen"] is not None:
            apunta("OJEADOR", f"{quien} · {c['carta']} en El Rastro: piden {pr['piden']} · ofrecen {pr['ofrecen']}")
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

    for c in lectura.get("vendedores") or []:
        aislado(paso_vendedor, c, "vendedor")

    # ---------- duelos: Contable → Duelista (con Portavoz y Espía) ----------
    def paso_duelo(d):
        quien = f"duelo-{d['id']}"
        if quien in vista["textos_nuevos"]:
            if quien not in mem.leen and d.get("nuestras"):
                lee = sondas.lee_texto(d["texto"])
                if lee is not None:
                    mem.leen[quien] = lee
                    apunta("ESPÍA", f"{quien} · el rival {'lee' if lee else 'no lee'} el texto")
            if mem.preguntas.get(quien, 0) and d.get("rival"):
                dichos = [n for n in defensa.numeros(d["texto"]) if n != d["rival"][-1]]
                if dichos:
                    apunta("ESPÍA", f"{quien} · tras la pregunta, el rival escribe {dichos}: se apunta, no cambia ningún precio")
        firme = mem.escudo.firme(quien)
        if forzar.get("duelo") == "apagado":
            return
        cuentas = contable.para_duelo(d)                     # la Contable da los números antes de que la Duelista decida
        rol, lim = cuentas["rol"], cuentas["limite"]
        apunta("CONTABLE", f"{quien} · {rol} · límite {lim}" + (f" · aceptar ya da {cuentas['aceptar_ya']:+.0f}"
                                                                if cuentas["aceptar_ya"] is not None else ""))
        esc = d.get("escenario")
        lr = None
        if esc is not None:
            visto = mem.escenarios.setdefault(str(esc), {})
            visto[rol] = lim
            lr = visto.get("buyer" if rol == "seller" else "seller")
        st = {"rol": rol, "limite": lim, "rival": d.get("rival", []), "nuestras": d.get("nuestras", []),
              "ronda": d.get("ronda", len(d.get("nuestras", []))), "rondas": d.get("rondas"), "limite_rival": lr,
              "descuento": d.get("descuento")}
        accion, precio, por_que = duelo.decidir(st, p)
        apunta("DUELISTA", f"{quien} · {rol} · rival {st['rival'][-1] if st['rival'] else '—'} · {accion} "
                           f"{precio if precio is not None else ''} · {por_que}")
        if accion == "aceptar":
            quedan = d.get("ticks_restantes")
            cola.append({"tipo": "duelo", "urgente": quedan is not None and quedan <= 2, "destino": "duelo",
                         "id": d["id"], "precio": precio, "rol": rol, "limite": lim})
        elif accion == "ofrecer":
            nuestras, rival = st["nuestras"], st["rival"]
            cedimos = bool(nuestras) and precio != nuestras[-1]
            cerca = bool(rival) and abs(rival[-1] - precio) <= 0.1 * max(abs(precio), 1)
            rival_firme = len(rival) >= 2 and rival[-1] == rival[-2]
            tactica, txt = mem.portavoz.duelo(precio, st["ronda"], cedimos, cerca, rival_firme, firme)
            if not firme:                                   # el Espía en duelos: solo palabras normales, nunca inyección
                canario = sondas.canario(st["ronda"], precio) if not nuestras else None
                pregunta = None if canario else sondas.pregunta_duelo(mem.leen.get(quien), mem.preguntas.get(quien, 0), precio)
                if canario and defensa.revisar_salida(canario, precio)[0]:
                    tactica, txt = "canario", canario
                elif pregunta and defensa.revisar_salida(pregunta, precio)[0] and mem.preguntas.get(quien, 0) < 1:
                    mem.preguntas[quien] = mem.preguntas.get(quien, 0) + 1
                    tactica, txt = "pregunta", pregunta
            m = {"destino": "duelo", "id": d["id"], "precio": precio, "texto": txt, "tactica": tactica}
            if d.get("dias"):
                paquetes_rival = d.get("rival_paquetes") or []
                hacia = duelo.dia_preferido_rival(paquetes_rival) if len(paquetes_rival) >= 2 else None
                m["dias"], por_dia = duelo.mejor_dia(d.get("pesos_dias"), DIA_POR_DEFECTO, hacia=hacia)
                if not nuestras or hacia:
                    apunta("DUELISTA", f"{quien} · {por_dia}")
            mensajes.append(m)

    for d in lectura.get("duelos") or []:
        aislado(paso_duelo, d, "duelo")

    # ---------- El Rastro: Contable → Cambista (con los precios del Ojeador y el Portavoz) ----------
    def paso_rastro(tablon):
        tablon = [o for o in tablon if isinstance(o, dict)]
        mom, esc = lectura.get("momento") or {}, lectura.get("escasez") or {}
        pasado = {r: list(v) for r, v in mem.historial.items()}       # se compara con lo visto ANTES de este tick
        ojeador.observar(mem.historial, tablon, t)
        for o in cambista.oportunidades(tablon, cuenta, efectivo, reserva=p["guardia.reserva_efectivo"], p=p)[:3]:
            prop = o["propuesta"]
            if ordenes.get("compras") == "ninguna" and prop["recibo"]["cartas"] and not prop["entrego"]["cartas"]:
                continue                                 # solo vender o caja seca: en El Rastro no se compra
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

    tablon = lectura.get("tablon")
    if tablon and forzar.get("equipo") != "apagado" and forzar.get("rastro") != "apagado":
        aislado(paso_rastro, tablon, "El Rastro")

    # ---------- la firma: la Contable hace la ficha, el Guardia confirma ----------
    # El PDF oficial de Causa Prima lo confirma: "Duel messages and accepts have their own limits: they never
    # block your trading". Los duelos tienen su propio cupo de aceptación por tick, aparte del de la tienda y
    # El Rastro: los dos pueden firmar en el mismo tick, cada uno dentro de su propia categoría.
    firmado = {"duelo": None, "tienda": None}

    def paso_firma(o):
        """Devuelve la firma si el Guardia la da. Si ya hay una firma de esta misma categoría en este tick
        (duelo, o tienda/equipo), el Guardia dice que no; una firma de la otra categoría no cuenta."""
        categoria = "duelo" if o["tipo"] == "duelo" else "tienda"
        ya_firmado = firmado[categoria] is not None
        if o["tipo"] == "duelo":
            gan = contable.ganancia_duelo(o["rol"], o["limite"], o["precio"])
            apunta("CONTABLE", f"duelo {o['id']} · {o['rol']} · límite {o['limite']} · precio {o['precio']} · gana {gan:+.0f}")
            ok, motivo = guardia.revisar_duelo(gan, ya_firmado, stop, forzar)
            ev = None
        else:
            recibo = (o["propuesta"].get("recibo") or {}).get("cartas") or []
            completar = bool(recibo) and not (o["propuesta"].get("entrego") or {}).get("cartas") and \
                o["tipo"] in ("vendedor", "final_vendedor") and all(contable.para_completar(r, ordenes) for r in recibo)
            tope = None if completar else ordenes.get("tope_por_trato")   # página a completar: sin tope por trato
            ev = contable.ficha(o["propuesta"], cuenta, efectivo, p)
            apunta("CONTABLE", f"{o['destino']} {o['id']} · recibo {ev['recibo']:.1f} · entrego {ev['entrego']:.1f} · "
                               f"comisión {ev['comision']} · neto {ev['neto']:+.1f}")
            ok, motivo, ev, _ = guardia.revisar(o["propuesta"], o.get("oferta_juego"), cuenta, efectivo, p,
                                                ya_firmado_este_tick=firma is not None, stop=stop, forzar=forzar,
                                                tope_por_trato=tope, ev=ev, para_completar=completar)
        apunta("GUARDIA", f"{o['destino']} {o['id']} · {'FIRMA' if ok else 'no firma'} · {motivo}")
        if not ok:
            return
        if o["tipo"] in ("vendedor", "final_vendedor") and o["apertura"] != o["precio"]:
            mem.capturas.setdefault(o["vendedor"], []).append({"apertura": o["apertura"], "precio": o["precio"],
                                                               "dia": lectura.get("dia")})
        firmado[categoria] = {"destino": o["destino"], "id": o["id"], "oferta_id": o.get("oferta_id"),
                              "precio": o.get("precio"), "motivo": motivo, "ficha": ev}

    for o in sorted(cola, key=prioridad.clave):        # el orden dentro de cada categoría vive en prioridad.py
        aislado(paso_firma, o, "firma")                 # un error al revisar una propuesta nunca firma nada

    mem.mala_fe.extend(mala_fe)
    return {"mensajes": mensajes, "firma": firmado["tienda"], "firma_duelo": firmado["duelo"],
            "cerrar": cerrar, "diario": diario, "mala_fe": mala_fe}


def lista_compra(cuenta, efectivo, p, mercado=None, listas=None, pagado=None, final=False):
    """El Cambista compra: la lista de la compra (ver cambista.lista_compra)."""
    return cambista.lista_compra(cuenta, efectivo, p, mercado=mercado, listas=listas, pagado=pagado, final=final)


def peticiones_rastro(lista, cuenta, efectivo, p, activas=None, caducidades=None, demanda=None, final=False):
    """El Cambista compra: qué peticiones publicar en El Rastro ahora (ver cambista.peticiones)."""
    return cambista.peticiones(lista, cuenta, efectivo, p, activas, caducidades, demanda=demanda, final=final)


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
    senales = {ref: {"rastro": precio hoy en El Rastro con comisión o None, "escasa": bool}} (ojeador.senales_vendedor):
    una carta casi agotada se compra antes; con la escalera de ese vendedor ya hecha, no se le compra lo que
    sale más barato en El Rastro (lo compra el Cambista).
    evitar = {(vendedor, carta)} que hoy ya acabaron sin acuerdo con un vendedor de NO_INSISTIR: no se repiten.
    ordenes["completar"] = páginas a completar (hoy.json): sus cartas van delante, también con solo_vender y sin cupo,
    al vendedor más barato y solo con margen_completar × la lista libre sobre la reserva (si no, se espera a las ventas).
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
        if ordenes.get("compras") == "ninguna" and not ordenes.get("completar"):
            continue
        cupo_lleno = max_tratos is not None and tratos.get(vendedor, 0) >= max_tratos
        compras = []
        for ref, lista in (menu.get("vende") or {}).items():
            if cuenta.get(ref, 0) > 0 or ref in usadas or not V.conocida(ref) or (vendedor, ref) in evitar:
                continue
            objetivo = contable.para_completar(ref, ordenes)     # página que el equipo quiere completar (hoy.json)
            if ordenes.get("compras") == "ninguna" and not objetivo:
                continue
            if objetivo and lista > mas_barato.get(ref, lista):
                continue                                  # una página a completar se compra al vendedor más barato
            if objetivo:                                  # primero la más cara: las baratas guardan caja para las que cuestan más
                mas_caras = sum(mas_barato[r] for r in V.estado_pagina(cuenta, V.barrio(ref))[1]
                                if r != ref and mas_barato.get(r, 0) > lista)
                if efectivo - ordenes.get("reserva", 0) < ordenes.get("margen_completar", 1) * (lista + mas_caras):
                    continue                              # se espera a que las ventas llenen la caja
            if not tienda.caja_llega(efectivo - ordenes.get("reserva", 0), lista):
                continue                                  # la caja no llega a su precio: no se abre (ni se le cansa)
            vale = V.valor_recibir(cuenta, [ref])
            completa = V.estado_pagina(cuenta, V.barrio(ref))[1] == [ref]
            if vale < 0.8 * lista or (cupo_lleno and not (completa or objetivo)):
                continue
            if ordenes.get("compras") == "escalera_y_pagina" and not (completa or objetivo) and \
                    lista > (ordenes.get("tope_por_trato") or 0):
                continue
            s = (senales or {}).get(ref) or {}
            rastro = s.get("rastro")
            if cupo_lleno and rastro is not None and rastro < lista and not (completa or objetivo):
                continue                                  # escalera hecha y en El Rastro sale más barata
            compras.append((not completa, not objetivo, not s.get("escasa"), -(vale - lista), ref, lista))
        if compras:
            *_, ref, lista = min(compras)
            usadas.add(ref)
            pendientes.append({"vendedor": vendedor, "lado": "compra", "carta": ref, "lista": lista})
    nivel = {v: n for v, n in (niveles or {}).items() if isinstance(n, (int, float)) and not isinstance(n, bool)}
    pendientes.sort(key=lambda o: -nivel.get(o["vendedor"], 0))        # estable: sin niveles, el orden de siempre
    return pendientes
