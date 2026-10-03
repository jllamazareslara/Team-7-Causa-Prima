"""La cadena: todos los agentes, en orden, una vez por tick. Es lo que los encadena.

    lectura (solo números + el texto aparte)  →  tick()  →  acciones (mensajes, UNA firma como mucho, cierres, diario)

Sin red y sin azar: no llama al juego, no lee la clave y no acepta nada. Quien habla con el juego (el director:
`director.py` o el `play.py` del repositorio) solo tiene que hacer dos cosas: construir `lectura` y aplicar `acciones`.

Orden dentro de un tick (cada paso es un agente):
    1. Ojos          cuentan qué pasa en el mercado y si hay novedades: novedades del juego (Vigía), perfil de cada
                     vendedor (Observador) y precios de El Rastro. Solo miran. Ver `ojos.py`.
    2. Contable      hace las cuentas para todos con la calculadora: tope o suelo de cada conversación, lo que deja
                     pagar la caja, y la ficha de cada trato que va a firmar el Guardia. No decide. Ver `contable.py`.
    3. Negociadores  hacen el trámite, cada uno con sus números:
                       Regateador  una decisión por conversación con un vendedor: precio nuevo, aceptar o retirarse.
                       Duelista    una decisión por duelo.
                       Cambista    lo que renta del tablón de El Rastro (solo cuando el director lo trae).
                     Ayudantes del Regateador y de la Duelista (no son pasos propios):
                       Escudo      mira el texto que llega, cuenta avisos por contraparte y apunta candidatos a mala fe.
                       Espía       lee pistas del texto y solo las apunta; pregunta en una conversación de prueba al día;
                                   en duelos manda un canario y, si el rival lee el texto, una pregunta directa.
                                   REGLA: lo que sale de un texto va al diario y a las palabras, nunca a un precio.
                       Portavoz    escribe el mensaje de cada precio nuevo.
    4. Guardia       confirma al final: de todas las propuestas de aceptar firma UNA, con la ficha de la Contable.
    5. Diario        una línea por decisión, con su motivo.

lectura = {
  "tick": n, "efectivo": n, "cuenta": {ref: copias},
  "vendedores": [{"id": hilo, "vendedor": "abuela", "lado": "compra"|"venta", "carta": ref,
                  "suyas": [su apertura, ...], "nuestras": [...], "final": bool, "oferta_id": id o None,
                  "texto": su último mensaje, "lista": precio de lista (vendiendo), "cerrado": None|"cooloff"|...}],
  "duelos":     [{"id", "rol": "seller"|"buyer", "limite", "rival": [...], "nuestras": [...], "ronda", "rondas",
                  "ticks_restantes", "texto", "escenario", "dias": bool}],
  "tablon":     ofertas de El Rastro tal como las da board("rastro"), o None si este tick no se ha leído,
  "novedades":  lo nuevo del juego según el Vigía (novedades.comparar), o nada
}
"""
import math
import re

from . import cambista, contable, defensa, duelo, guardia, ojeador, ojos, params, prioridad, sondas, tienda
from .ojos import MERCADO_RECUERDA, apuntar_mercado  # noqa: F401  (se usan desde fuera: director y pruebas)
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

    # ---------- 1. Ojos: qué pasa en el mercado y qué hay de nuevo ----------
    vista = ojos.mirar(lectura, mem, p, apunta)

    # ---------- vendedores: Contable → Regateador (con Escudo, Espía y Portavoz) ----------
    def paso_vendedor(c):
        hilo, quien, texto = str(c["id"]), c["vendedor"], c.get("texto") or ""
        cuentas = contable.para_vendedor(c, cuenta, efectivo, p, ordenes)
        es_nuevo = nuevo(hilo, texto)
        if es_nuevo:
            motivos, _ = mem.escudo.anotar(quien, texto)
            if motivos:
                apunta("ESCUDO", f"{quien}: {', '.join(motivos)}")
        if c.get("cerrado"):
            apunta("TIENDA", f"{quien} cerró la conversación ({c['cerrado']})")
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
        motivo = defensa.incoherencia(texto, suya) if es_nuevo else None
        if motivo:
            mala_fe.append({"hilo": c["id"], "vendedor": quien, "motivo": motivo, "tick": t})
            apunta("ESCUDO", f"{quien} · candidato a mala fe: {motivo}. Lo decide el equipo.")

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
        pf = vista["perfiles"].get(quien) or params.perfil(p, quien)       # el perfil lo traen los Ojos
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

    # ---------- duelos: Duelista (con Escudo, Espía y Portavoz) ----------
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

    # ---------- El Rastro: Cambista (los precios ya los apuntaron los Ojos) ----------
    def paso_rastro(tablon):
        tablon = [o for o in tablon if isinstance(o, dict)]
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

    # ---------- una sola firma: la Contable hace la ficha, el Guardia confirma ----------
    def orden(o):
        return (0 if o.get("urgente") else 1, {"duelo": 0, "final_vendedor": 1, "equipo": 2, "vendedor": 3}[o["tipo"]],
                -o.get("neto", 0))

    def paso_firma(o):
        """Devuelve la firma si el Guardia la da. Si ya hay una en este tick, el Guardia dice que no."""
        if o["tipo"] == "duelo":
            gan = contable.ganancia_duelo(o["rol"], o["limite"], o["precio"])
            apunta("CONTABLE", f"duelo {o['id']} · {o['rol']} · límite {o['limite']} · precio {o['precio']} · gana {gan:+.0f}")
            ok, motivo = guardia.revisar_duelo(gan, firma is not None, stop, forzar)
            ev = None
        else:
            ev = contable.ficha(o["propuesta"], cuenta, efectivo, p)
            apunta("CONTABLE", f"{o['destino']} {o['id']} · recibo {ev['recibo']:.1f} · entrego {ev['entrego']:.1f} · "
                               f"comisión {ev['comision']} · neto {ev['neto']:+.1f}")
            ok, motivo, ev, _ = guardia.revisar(o["propuesta"], o.get("oferta_juego"), cuenta, efectivo, p,
                                                ya_firmado_este_tick=firma is not None, stop=stop, forzar=forzar,
                                                tope_por_trato=ordenes.get("tope_por_trato"), ev=ev)
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
                        guardar=None, niveles=None):
    """Qué operación abrir con cada vendedor que no tiene conversación: primero vender, luego comprar.

    menus = {vendedor: {"vende": {ref: precio de lista}, "compra": {ref: lo que ofrece de entrada}}}
    abiertas = vendedores que ya tienen conversación. Devuelve [{"vendedor", "lado", "carta", "lista"}], una por vendedor.
    tratos, max_tratos = calidad antes que cantidad: con max_tratos tratos regateados hoy con un vendedor (solo cuentan
    los tres mejores), ya no se le abren compras salvo la carta que completa una página. Vender sigue: da efectivo.
    Una carta cuyo valor no conocemos (barrio o código nuevo) no se abre nunca.
    guardar = {ref: vendedor al que sí se vende ahora, o None} (guion.reservadas): cartas que esperan una fiebre.
    Durante la fiebre van primero al vendedor de la fiebre.
    niveles = {vendedor: nivel}: los niveles altos pesan más en la escalera, así que sus operaciones van delante.
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
            compras.append((not completa, -(vale - lista), ref, lista))
        if compras:
            _, _, ref, lista = min(compras)
            usadas.add(ref)
            pendientes.append({"vendedor": vendedor, "lado": "compra", "carta": ref, "lista": lista})
    nivel = {v: n for v, n in (niveles or {}).items() if isinstance(n, (int, float)) and not isinstance(n, bool)}
    pendientes.sort(key=lambda o: -nivel.get(o["vendedor"], 0))        # estable: sin niveles, el orden de siempre
    return pendientes
