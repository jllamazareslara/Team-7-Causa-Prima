"""La cadena: todos los agentes, en orden, una vez por tick. Es lo que los encadena.

    lectura (solo números + el texto aparte)  →  tick()  →  acciones (mensajes, UNA firma como mucho, cierres, diario)

Sin red y sin azar: no llama al juego, no lee la clave y no acepta nada. Quien habla con el juego (el `play.py` del
repositorio u otro programa) solo tiene que hacer dos cosas: construir `lectura` y aplicar `acciones`.

Orden dentro de un tick (cada paso es un agente):
    1. Ojos          miran cómo estamos (/api/me, como la skill estado-equipo) y las mejores oportunidades (/api/feed,
                     /api/me/offers y el tablón). Solo miran: no pasan por el Escudo ni por el Guardia. Ver `ojos.py`.
       Al lado:      Guion    anticipa lo que viene (calendario): lo apunta en el diario, no cambia ninguna decisión.
                     Ojeador  vigila los precios de El Rastro y se los pasa al Regateador y al Cambista. Ver `ojeador.py`.
    2. Contable      ¿renta? ¿cuánto?: hace las cuentas con la calculadora y se las da a los negociadores (tope o suelo,
                     caja) y, con cada trato, la ficha que mira el Guardia. No decide. Ver `contable.py`.
    3. Negociadores  hacen el trámite, cada uno con sus números y sus ayudantes:
                       Cambista    El Rastro y equipos            + Portavoz · Ojos
                       Duelista    duelos                         + Portavoz · Escudo · Espía
                       Regateador  vendedores                     + Portavoz · Escudo · Observador · Espía · Ojos
                     Ojos como referencia: el Regateador no paga más (ni vende por menos) que el último trato del feed
                     y no compra/vende al vendedor si los Ojos proponen algo mejor en El Rastro; el Cambista manda al
                     Guardia las propuestas de los Ojos y no anuncia por menos ni pide por más que el último trato.
                     Escudo: lee cada texto nuevo una vez (avisos por contraparte, modo firme, mala fe). Ver `defensa.py`.
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
  "me":         /api/me con las claves tapadas (Ojos), "mis_ofertas": /api/me/offers (Ojos), "feed": /api/feed (opcional),
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
        ojeador.observar_feed(mem.historial, ojos.eventos(lectura["feed"]), t)
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
    precio ajustado al mercado y al momento (Ojeador), nunca por debajo de V.suelo_venta_rastro (valor + comisión + margen).
    Sin demanda no se malvende: una carta que nadie pide y que ya venden cambista.sin_demanda_vendedores equipos no se
    anuncia (se guarda para cambios). Cazador de páginas: a quien pide la misma carta cambista.caza_veces veces no se
    le vende por debajo de lo mejor que ha ofrecido."""
    excluidas = set(excluidas) | set(_reservadas(cuenta, mem, lectura))
    t = lectura.get("tick") if isinstance(lectura.get("tick"), (int, float)) else 0
    obs = [{"maker": m, "ref": ref, "precio": pr, "lado": lado}
           for ref, xs in (mem.historial or {}).items() if V.conocida(ref)
           for tk, pr, lado, m in xs if lado == "compra" and isinstance(pr, (int, float)) and isinstance(tk, (int, float))
           and t - tk <= 120]
    caza = {}
    for ref, _, mejor, _ in cambista.cazador_de_paginas(obs, cuenta, veces=int(p.get("cambista.caza_veces", 2))):
        caza[ref] = max(caza.get(ref, 0), mejor)
    minimo_vend = int(p.get("cambista.sin_demanda_vendedores", 0))
    sin_demanda = set()
    if minimo_vend:
        for ref, n in cuenta.items():
            if n > 0 and ref not in caza:
                tend = ojeador.tendencia(mem.historial, ref, t)
                if tend["compradores"] == 0 and tend["vendedores"] >= minimo_vend:
                    sin_demanda.add(ref)
    out = anuncios_rastro(cuenta, p, activos, ocupadas, excluidas | sin_demanda, listas, caducidades, maximo)
    tratos_feed = ojos.tratos(mem)
    mom = lectura.get("momento") or {"fase": "normal", "vender": 1.0}
    for n in out:
        antes = n["precio"]
        suelo = V.suelo_venta_rastro(n["pierde"], p.get("guardia.margen_venta", 0.10))
        n["precio"] = ojeador.precio_venta(antes, suelo, ojeador.tendencia(mem.historial, n["carta"], t),
                                           mom, mem.escasez.get(n["carta"]))
        if n["carta"] in caza and n["precio"] < caza[n["carta"]]:
            n["precio"] = math.ceil(caza[n["carta"]])
            n["cazador"] = f"la pide varias veces, hasta {caza[n['carta']]} P"
        if n["precio"] != antes:
            n["ojeador"] = f"{antes} → {n['precio']} ({mom.get('fase', 'normal')})"
        trato = tratos_feed.get(n["carta"])
        if trato is not None and n["precio"] < trato:    # los Ojos: no se anuncia por menos que el último trato
            n["ojos"] = f"último trato {trato}: {n['precio']} → {math.ceil(trato)}"
            n["precio"] = math.ceil(trato)
    return out


def _propuesta_vendedor(c, precio):
    if c["lado"] == "compra":
        return {"tipo": "vendedor", "recibo": {"cartas": [c["carta"]]}, "entrego": {"primas": precio}}
    return {"tipo": "vendedor", "recibo": {"primas": precio}, "entrego": {"cartas": [c["carta"]]}}


def tick(lectura, mem, p=None, forzar=None, ordenes=None, stop=False):
    """Un tick entero. Devuelve acciones = {"mensajes", "firma", "cerrar", "diario", "mala_fe", "ojos"}."""
    p = p or params.cargar()
    forzar, ordenes = forzar or {}, ordenes or {}
    t = lectura.get("tick")
    cuenta, efectivo = lectura.get("cuenta", {}), lectura.get("efectivo", 0)
    mensajes, cerrar, cola, diario, mala_fe = [], [], [], [], []
    ofertas_duelo = []    # el servidor solo deja mandar un mensaje de duelo por equipo y tick: una sola, la más urgente
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

    # ---------- 1. Ojos: cómo estamos y las mejores oportunidades (solo miran: ni Escudo ni Guardia) ----------
    vista = ojos.mirar(lectura, mem, apunta, p)

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

    # ---------- el Escudo, ayudante del Regateador y la Duelista: el texto nuevo, una vez ----------
    textos = defensa.mirar_textos(lectura, mem, apunta)
    mala_fe.extend(textos["mala_fe"])
    tratos_feed = ojos.tratos(mem)                       # referencia de los Ojos para el Regateador

    # ---------- vendedores: Contable → Regateador (con Portavoz, Observador y Espía) ----------
    def paso_vendedor(c):
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

    for c in lectura.get("vendedores") or []:
        aislado(paso_vendedor, c, "vendedor")

    # ---------- duelos: Contable → Duelista (con Portavoz y Espía) ----------
    def paso_duelo(d):
        quien = f"duelo-{d['id']}"
        if quien in textos["textos_nuevos"]:
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
              "ronda": d.get("ronda", len(d.get("nuestras", []))), "rondas": d.get("rondas"), "limite_rival": lr}
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
                # Parche C (sonda inicial): en la primera oferta sin información del rival, mandamos el día central
                # (DIA_POR_DEFECTO = 5) en vez de nuestro mejor día. Elegir nuestro mejor día desde el principio
                # revela nuestra preferencia; el 5 fuerza al rival a mostrar la suya en su contrapropuesta y
                # desbloquea `hacia` a partir de la ronda siguiente, cuando ya podemos ceder en el día que apenas
                # nos cuesta a cambio de ganar en precio (la tarta crece ahí, según el PDF del juego).
                if not nuestras and not paquetes_rival:
                    m["dias"], por_dia = DIA_POR_DEFECTO, f"día {DIA_POR_DEFECTO}: sonda inicial para medir preferencia del rival"
                elif duelo.dia_bueno(rol, d.get("k_dias")) is not None:   # peso real: un número con su sentido
                    m["dias"] = duelo.dia_bueno(rol, d["k_dias"])
                    por_dia = f"día {m['dias']}: el que más nos vale (k = {d['k_dias']:+.2f} por día)"
                else:
                    m["dias"], por_dia = duelo.mejor_dia(d.get("pesos_dias"), DIA_POR_DEFECTO, hacia=hacia)
                k = d.get("k_dias")
                if k is not None:                           # `precio` es efectivo: el que se escribe depende del día
                    m["precio"] = duelo.precio_a_mandar(rol, precio, m["dias"], k, lim)
                    por_dia += f" · se escribe {m['precio']} (vale {precio} con el día)"
                if not nuestras or hacia or k is not None:
                    apunta("DUELISTA", f"{quien} · {por_dia}")
            quedan = d.get("ticks_restantes")
            ofertas_duelo.append((quedan if isinstance(quedan, (int, float)) else float("inf"), m))

    for d in lectura.get("duelos") or []:
        aislado(paso_duelo, d, "duelo")
    # Una oferta por duelo por tick (lo que permite el servidor: `messages_per_side_per_tick: 1` por lado del duelo,
    # no un total global). Antes el agente se auto-limitaba a UNA oferta de duelo por tick, lo que con 10-14 duelos
    # simultáneos en Duels II dejaba varios sin oferta (visto en vivo el 3/10 en d5820, d5821, d5765, d5764, d5998,
    # d5810 con `mios=[]` todo el duelo, aunque el rival ofrecía precios dentro del límite). Se mandan todas,
    # ordenadas por plazo (urgentes primero por si la cola de red tira del rate_limit del SDK).
    if ofertas_duelo:
        for _, m in sorted(ofertas_duelo, key=lambda x: x[0]):
            mensajes.append(m)

    # ---------- El Rastro: Contable → Cambista (con los precios del Ojeador y el Portavoz) ----------
    def paso_rastro(tablon):
        tablon = [o for o in tablon if isinstance(o, dict)]
        mom, esc = lectura.get("momento") or {}, lectura.get("escasez") or {}
        pasado = {r: list(v) for r, v in mem.historial.items()}       # se compara con lo visto ANTES de este tick
        ojeador.observar(mem.historial, tablon, t)
        for o in cambista.oportunidades(tablon, cuenta, efectivo, reserva=p["guardia.reserva_efectivo"], p=p)[:3]:
            prop = o["propuesta"]
            if ordenes.get("compras") == "ninguna" and prop["recibo"]["cartas"] and not prop["entrego"]["cartas"] and \
                    not (ordenes.get("pedir_completar") and all(contable.para_completar(r, ordenes) for r in prop["recibo"]["cartas"])):
                continue                                 # solo vender o caja seca: en El Rastro no se compra (salvo páginas a completar)
            compra = prop["recibo"]["cartas"] and not prop["entrego"]["cartas"] and len(prop["recibo"]["cartas"]) == 1
            if compra:                                   # el Ojeador decide CUÁNDO: ya, o esperar a que baje
                ref = prop["recibo"]["cartas"][0]
                ya, porque = ojeador.comprar_ahora(
                    ref, prop["entrego"]["primas"], o["ficha"]["cartas_recibo"],     # lo que nos suma, de la Contable
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

    def paso_propuestas_ojos(props):                     # el Cambista manda al Guardia lo que validaron los Ojos
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

    if vista.get("propuestas") and forzar.get("equipo") != "apagado" and forzar.get("rastro") != "apagado":
        aislado(paso_propuestas_ojos, vista["propuestas"], "propuestas de los Ojos")

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
        revisar = None
        if o["tipo"] == "duelo":
            gan = contable.ganancia_duelo(o["rol"], o["limite"], o["precio"])
            apunta("CONTABLE", f"duelo {o['id']} · {o['rol']} · límite {o['limite']} · precio {o['precio']} · gana {gan:+.0f}")
            ok, motivo = guardia.revisar_duelo(gan, ya_firmado, stop, forzar)
            ev = None
        else:
            revisar = {}
            recibo = (o["propuesta"].get("recibo") or {}).get("cartas") or []
            completar = bool(recibo) and not (o["propuesta"].get("entrego") or {}).get("cartas") and \
                o["tipo"] in ("vendedor", "final_vendedor") and all(contable.para_completar(r, ordenes) for r in recibo)
            tope = None if completar else ordenes.get("tope_por_trato")   # página a completar: sin tope por trato
            ev = contable.ficha(o["propuesta"], cuenta, efectivo, p)
            apunta("CONTABLE", f"{o['destino']} {o['id']} · recibo {ev['recibo']:.1f} · entrego {ev['entrego']:.1f} · "
                               f"comisión {ev['comision']} · neto {ev['neto']:+.1f}")
            ok, motivo, ev, _ = guardia.revisar(o["propuesta"], o.get("oferta_juego"), cuenta, efectivo, p,
                                                ya_firmado_este_tick=ya_firmado, stop=stop, forzar=forzar,
                                                tope_por_trato=tope, ev=ev, para_completar=completar)
            revisar = {"tope_por_trato": tope, "para_completar": completar, "forzar": forzar}
        apunta("GUARDIA", f"{o['destino']} {o['id']} · {'FIRMA' if ok else 'no firma'} · {motivo}")
        if not ok:
            return
        if o["tipo"] in ("vendedor", "final_vendedor") and o["apertura"] != o["precio"]:
            mem.capturas.setdefault(o["vendedor"], []).append({"apertura": o["apertura"], "precio": o["precio"],
                                                               "dia": lectura.get("dia")})
        firmado[categoria] = {"destino": o["destino"], "id": o["id"], "oferta_id": o.get("oferta_id"),
                              "precio": o.get("precio"), "motivo": motivo, "ficha": ev}
        if o["destino"] == "vendedor":                  # jugar.py lo vuelve a pasar por el Guardia justo antes de aceptar
            firmado[categoria].update(propuesta=o["propuesta"], revisar=revisar)

    for o in sorted(cola, key=prioridad.clave):        # el orden dentro de cada categoría vive en prioridad.py
        aislado(paso_firma, o, "firma")                 # un error al revisar una propuesta nunca firma nada

    mem.mala_fe.extend(mala_fe)
    return {"mensajes": mensajes, "firma": firmado["tienda"], "firma_duelo": firmado["duelo"],
            "cerrar": cerrar, "diario": diario, "mala_fe": mala_fe, "ojos": vista}


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
    senales = {ref: {"rastro": precio hoy en El Rastro con comisión o None, "escasa": bool}} (ojeador.senales_vendedor):
    una carta casi agotada se compra antes; con la escalera de ese vendedor ya hecha, no se le compra lo que
    sale más barato en El Rastro (lo compra el Cambista).
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
            compras.append((not completa, not objetivo, not s.get("escasa"), -(vale - lista), ref, lista))
        if compras:
            *_, ref, lista = min(compras)
            usadas.add(ref)
            pendientes.append({"vendedor": vendedor, "lado": "compra", "carta": ref, "lista": lista})
    nivel = {v: n for v, n in (niveles or {}).items() if isinstance(n, (int, float)) and not isinstance(n, bool)}
    pendientes.sort(key=lambda o: -nivel.get(o["vendedor"], 0))        # estable: sin niveles, el orden de siempre
    return pendientes
