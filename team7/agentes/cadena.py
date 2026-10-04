"""La cadena: todos los agentes, en orden, una vez por tick. Es lo que los encadena.

    lectura (solo números + el texto aparte)  →  tick()  →  acciones (mensajes, UNA firma como mucho, cierres, diario)

Sin red y sin azar: no llama al juego, no lee la clave y no acepta nada. Quien habla con el juego (el `play.py` del
repositorio u otro programa) solo tiene que hacer dos cosas: construir `lectura` y aplicar `acciones`.

Orden dentro de un tick (cada paso es un agente):
    1. Ojos          miran cómo estamos (/api/me, como la skill estado-equipo) y las mejores oportunidades (/api/feed,
                     /api/me/offers y el tablón). Solo miran: no pasan por el Escudo ni por el Guardia. Ver `ojos.py`.
                     Antes de mirar, ojear() guarda lo que llegó: calendario, niveles, tratos del feed, el tablón
                     (precios que piden y ofrecen) y los vendedores que descansan tras cupo agotado o enfado.
       Al lado:      Guion    anticipa lo que viene (calendario): lo apunta en el diario, no cambia ninguna decisión.
    2. Contable      ¿renta? ¿cuánto?: hace las cuentas con la calculadora y se las da a los negociadores (tope o suelo,
                     caja) y, con cada trato, la ficha que mira el Guardia. No decide. Ver `contable.py`.
    3. Negociadores  hacen el trámite, cada uno con sus números y sus ayudantes:
                       Comerciante  vendedores (tienda.py) y El Rastro (cambista.py)  + Portavoz · Escudo · Observador · Espía
                       Duelista     duelos                                           + Portavoz · Escudo · Espía
                     El Comerciante decide una vez qué comprar y vender y por qué canal (ver `comerciante.py`): no paga
                     más (ni vende por menos) que el último trato del feed, no compra/vende a un vendedor si los Ojos
                     lo ven mejor en El Rastro, y manda al Guardia las propuestas validadas de los Ojos.
                     Escudo: lee cada texto nuevo una vez (avisos por contraparte, modo firme, mala fe). Ver `defensa.py`.
                     Espía: lee pistas del texto y solo las apunta; pregunta en una conversación de prueba al día; en
                     duelos manda un canario y, si el rival lee el texto, una pregunta directa.
                     REGLA: lo que sale de un texto va al diario y a las palabras, nunca a un precio.
                     Observador: el perfil de cada vendedor (con quién ser duro); uno sin perfil propio es "desconocido".
                     Portavoz: escribe el mensaje de cada precio nuevo. (En El Rastro las ofertas no llevan texto: con el
                     Comerciante solo escribiría si un día hablamos con equipos por conversación.)
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
from types import SimpleNamespace

from . import comerciante, contable, defensa, duelo, guardia, guion, ojos, params, prioridad, sondas
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
        self.mercado = {}       # carta → últimos precios a los que otros equipos la anuncian en El Rastro (Ojos)
        self.demanda = {}       # carta → últimos precios que otros equipos OFRECEN por ella en El Rastro (Ojos)
        self.historial = {}     # carta → [[tick, precio, lado, quién]]: tablón y tratos del feed (Ojos)
        self.calendario = {}    # último /api/schedule leído + el tick en que se leyó (Guion)
        self.descansos = {}     # vendedor → hasta cuándo no se le abre nada (Ojos)
        self.niveles = {}       # vendedor → nivel: la escalera pesa más en los niveles altos
        self.sin_acuerdo = {}   # "vendedor|carta|día" → motivo: con NO_INSISTIR no se le vuelve a ofrecer ese día

    def a_dict(self):
        return {"sondeadas": self.sondeadas, "sondas": self.sondas, "pistas": self.pistas, "escenarios": self.escenarios, "mala_fe": self.mala_fe,
                "capturas": self.capturas, "avisos": self.escudo.cuenta, "frases": self.portavoz.usadas,
                "vistos": self.vistos, "tonos": self.tonos, "leen": self.leen, "preguntas": self.preguntas,
                "mercado": self.mercado, "demanda": self.demanda, "historial": self.historial,
                "calendario": self.calendario, "descansos": self.descansos, "niveles": self.niveles,
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
        m.calendario = d.get("calendario", {})
        m.descansos, m.niveles = d.get("descansos", {}), d.get("niveles", {})
        m.sin_acuerdo = d.get("sin_acuerdo", {})
        return m


# ---------------------------------------------------------------- lo que llega del juego, guardado por los Ojos
#
# Vive aquí y no en quien lanza la cadena (hoy jugar.py). Ese programa solo pone en la lectura
# lo que lee del juego, tal cual, cuando lo lee:
#   lectura["calendario"]  /api/schedule        lectura["tablon"]    board("rastro")  lectura["feed"]  /api/feed
#   lectura["niveles"]     {vendedor: nivel}    lectura["t_hours"]   de /api/clock    lectura["tick_segundos"]
#   y en cada vendedor cerrado: "cerrado" (closed_reason) y "until_tick"
# ojear() lo guarda en la memoria y deja en la lectura la "hora" de juego para el resto de la cadena.

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
    """Los Ojos al empezar el tick: guardan calendario, niveles, tratos del feed, el tablón y los descansos, y la hora."""
    t = lectura.get("tick")
    cal = lectura.get("calendario")
    if isinstance(cal, dict) and isinstance(cal.get("now_hours"), (int, float)):
        mem.calendario = {"now_hours": cal["now_hours"], "upcoming": cal.get("upcoming") or [], "tick": t}
    if isinstance(lectura.get("niveles"), dict):
        mem.niveles.update(lectura["niveles"])
    if lectura.get("feed"):                              # tratos hechos del feed público: precios reales pagados
        ojos.observar_feed(mem.historial, ojos.eventos(lectura["feed"]), t)
    tablon = [o for o in lectura.get("tablon") or [] if isinstance(o, dict)]
    if tablon:                                           # El Rastro: quién vende y quién pide qué, y a cuánto
        ojos.observar(mem.historial, tablon, t)
        ojos.apuntar_mercado(mem.mercado, tablon, mem.demanda)
    h = hora_de_juego(mem, lectura)
    for c in lectura.get("vendedores") or []:            # cupo agotado o enfado: ese vendedor descansa
        if isinstance(c, dict) and c.get("cerrado") and c.get("vendedor"):
            desc = ojos.descanso(c["cerrado"], h, t, c.get("until_tick"))
            if desc:
                mem.descansos[c["vendedor"]] = desc
    lectura["hora"] = h
    return lectura


def tick(lectura, mem, p=None, forzar=None, ordenes=None, stop=False):
    """Un tick entero. Devuelve acciones = {"mensajes", "firma", "cerrar", "diario", "mala_fe", "ojos"}."""
    p = p or params.cargar()
    forzar, ordenes = forzar or {}, ordenes or {}
    t = lectura.get("tick")
    cuenta, efectivo = lectura.get("cuenta", {}), lectura.get("efectivo", 0)
    mensajes, cerrar, cola, diario, mala_fe = [], [], [], [], []
    ofertas_duelo = []    # el servidor solo deja mandar un mensaje de duelo por equipo y tick: una sola, la más urgente
    try:                                                 # los Ojos primero: guardan lo que llegó del juego
        ojear(lectura, mem)
    except Exception as e:
        diario.append(f"tick {t}  {'ERROR':<10} Ojos: {type(e).__name__}: {e} · se sigue sin ellos")

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

    # ---------- al lado: el Guion (lo que viene) ----------
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

    # ---------- el Escudo, ayudante del Regateador y la Duelista: el texto nuevo, una vez ----------
    textos = defensa.mirar_textos(lectura, mem, apunta)
    mala_fe.extend(textos["mala_fe"])
    tratos_feed = ojos.tratos(mem)                       # referencia de los Ojos para el Comerciante
    tu = SimpleNamespace(lectura=lectura, mem=mem, p=p, ordenes=ordenes, cuenta=cuenta, efectivo=efectivo, vista=vista,
                         textos=textos, tratos=tratos_feed, apunta=apunta, mensajes=mensajes, cerrar=cerrar, cola=cola)

    # ---------- vendedores: Contable → Comerciante (tienda.py, con Portavoz, Observador y Espía) ----------
    for c in lectura.get("vendedores") or []:
        aislado(lambda x: comerciante.vendedor(x, tu), c, "vendedor")

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

    # ---------- El Rastro: Contable → Comerciante (cambista.py) ----------
    rastro_encendido = forzar.get("equipo") != "apagado" and forzar.get("rastro") != "apagado"
    tablon = lectura.get("tablon")
    if tablon and rastro_encendido:
        aislado(lambda x: comerciante.rastro(x, tu), tablon, "El Rastro")
    if vista.get("propuestas") and rastro_encendido:
        aislado(lambda x: comerciante.propuestas_ojos(x, tu), vista["propuestas"], "propuestas de los Ojos")

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
