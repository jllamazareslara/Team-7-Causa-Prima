"""La Contable en la cadena: hace las cuentas con la calculadora (`valor.py`) y se las pasa a quien las necesita.

¿Renta? ¿Cuánto? Va después de los Ojos y antes de los negociadores. No decide nada:
    para_vendedor(c, ...)   → los números del Regateador para una conversación: si conocemos la carta, cuánto nos vale,
                              nuestro tope (comprando) o suelo (vendiendo), si está protegida y cuánto deja pagar la caja
    ficha(propuesta, ...)   → la ficha que recibe el Guardia antes de cada firma (lo que entra, lo que sale, comisión, neto)
    para_duelo(d)           → los números de la Duelista antes de decidir: nuestro límite y lo que daría aceptar ya
    ganancia_duelo(...)     → lo que nos da un duelo a ese precio, calculado aquí y no por la Duelista
El Regateador negocia con sus números; el Guardia decide con su ficha.

Valores reales: jugando de verdad (jugar.py llama a `conectar`), la Contable usa SOLO el your_value del juego:
    nos_quita(carta)   lo que el juego nos quita al dar una copia (/api/me, se relee cada tick)
    nos_suma(carta)    lo que el juego nos suma con una copia más (/api/me/value, se pregunta una vez mientras no
                       cambien nuestras cartas)
Si el juego no da el valor de una carta, no hay número y no se opera con ella: nunca se cae a la calculadora.
Sin conectar (simulador, pruebas) no hay juego al que preguntar y se usa la calculadora (`valor.py`).
"""
import math

from . import duelo
from . import valor as V

_JUEGO = {"pedir": None}       # carta → your_value de una copia más (None si el juego no responde). Lo pone jugar.py


def conectar(pedir):
    """Desde aquí, solo valores del juego. pedir(carta) → your_value de /api/me/value o None. None desconecta."""
    _JUEGO["pedir"] = pedir


def conectada():
    return _JUEGO["pedir"] is not None


def nos_suma(carta, cuenta, mult=None):
    """Lo que nos suma recibir una copia más. Conectada: el your_value del juego, o None si no lo da."""
    if not conectada():
        return V.valor_recibir(cuenta, [carta], mult or V.NUESTROS_MULT)
    if carta not in V.VALOR_RECIBIR:
        _JUEGO["pedir"](carta)
    return V.VALOR_RECIBIR.get(carta)


def nos_quita(carta, cuenta, mult=None):
    """Lo que nos quita dar una copia (None si no la tenemos). Conectada: el your_value del juego, o None si no lo da."""
    if not conectada():
        return V.valor_entregar(cuenta, [carta], mult or V.NUESTROS_MULT)
    return V.VALOR_DAR.get(carta) if cuenta.get(carta, 0) > 0 else None


def para_completar(carta, ordenes):
    """¿Es de una página que el equipo quiere completar (hoy.json "completar")?"""
    return isinstance(carta, str) and V.barrio(carta) in (ordenes or {}).get("completar", ())


def caja_para_comprar(carta, cuenta, efectivo, p, ordenes):
    """Lo máximo que la caja deja pagar por esta carta: lo que queda sobre la reserva y, con la caja justa, el tope
    por trato (salvo la carta que completa una página o es de una página a completar, igual que en el Guardia)."""
    libre = math.floor(efectivo - p["guardia.reserva_efectivo"])
    tope = ordenes.get("tope_por_trato")
    if tope is None or V.estado_pagina(cuenta, V.barrio(carta))[1] == [carta] or para_completar(carta, ordenes):
        return libre
    return min(libre, tope)


def nos_quitan(cartas, cuenta):
    """Lo que nos quita dar estas cartas. Conectada: la suma de sus your_value; None si falta alguno, si no las
    tenemos o si va dos veces la misma (el juego solo da el valor de la copia que menos vale)."""
    if not conectada():
        return V.valor_entregar(cuenta, cartas)
    if len(set(cartas)) < len(cartas):
        return None
    vals = [nos_quita(r, cuenta) for r in cartas]
    return None if None in vals else sum(vals)


def limite_vendedor(lado, carta, cuenta):
    """Nuestro tope (comprando) o suelo (vendiendo) para esa carta, con el bono de página incluido.
    Conectada: solo el your_value del juego (None si no lo da). Sin conectar: la calculadora y, si ya tenemos el
    your_value, gana el más prudente: nunca pagar más de lo que nos suma ni vender por menos de lo que nos quita."""
    if lado == "compra":
        vals = [nos_suma(carta, cuenta)] if conectada() else [V.valor_recibir(cuenta, [carta]), V.VALOR_RECIBIR.get(carta)]
        vals = [v for v in vals if v is not None]
        return math.floor(min(vals)) if vals else None
    vals = [nos_quita(carta, cuenta)] if conectada() else [V.valor_entregar(cuenta, [carta]), V.VALOR_DAR.get(carta)]
    vals = [v for v in vals if v is not None]
    return math.ceil(max(vals) + 1) if vals else None


def para_vendedor(c, cuenta, efectivo, p, ordenes):
    """{"conocida", "nos_vale", "limite", "protegida", "caja", "motivo"}. Sin carta conocida no se calcula nada más.
    Conectada y sin your_value del juego para la carta, cuenta como no conocida: no se negocia a ciegas."""
    carta, lado = c.get("carta"), c.get("lado")
    nada = {"conocida": False, "nos_vale": None, "limite": None, "protegida": False, "caja": None}
    if not isinstance(carta, str) or not V.conocida(carta):
        return dict(nada, motivo="no sabemos cuánto nos vale (barrio o código nuevo)")
    if lado == "compra":
        nos_vale = nos_suma(carta, cuenta) if conectada() else V.VALOR_RECIBIR.get(carta, V.valor_recibir(cuenta, [carta]))
    else:
        nos_vale = nos_quita(carta, cuenta) if conectada() else V.VALOR_DAR.get(carta, V.valor_entregar(cuenta, [carta]))
    if conectada() and nos_vale is None and (lado == "compra" or cuenta.get(carta, 0) > 0):
        return dict(nada, motivo="el juego no nos ha dado su valor (your_value)")
    return {"conocida": True, "motivo": None, "nos_vale": nos_vale, "limite": limite_vendedor(lado, carta, cuenta),
            "protegida": lado == "venta" and V.protegida(cuenta, carta),
            "caja": caja_para_comprar(carta, cuenta, efectivo, p, ordenes) if lado == "compra" else None}


def ficha(propuesta, cuenta, efectivo, p=None, mult=None, reserva=None):
    """La ficha para el Guardia y para el Cambista. La reserva sale de `p` si no se da.
    Conectada: lo que entra y lo que sale se valora con el your_value del juego, carta a carta; si falta el de una,
    la ficha lleva un bloqueo y no renta. La calculadora solo pone las comprobaciones (reserva, efectivo, protegidas,
    páginas) y queda apuntada en "calculado" para comparar."""
    if reserva is None:
        reserva = p["guardia.reserva_efectivo"] if p else 0
    ev = V.evaluar(propuesta, cuenta, efectivo, mult or V.NUESTROS_MULT, reserva)
    return _con_el_juego(ev, propuesta, cuenta) if conectada() else ev


def _con_el_juego(ev, propuesta, cuenta):
    rec, ent = propuesta.get("recibo", {}), propuesta.get("entrego", {})
    rc, ec = rec.get("cartas") or [], ent.get("cartas") or []
    bloqueos = list(ev["bloqueos"])
    for lado, refs in (("recibimos", rc), ("damos", ec)):
        if len(set(refs)) < len(refs):
            bloqueos.append(f"{lado} dos copias de la misma carta: el juego solo da el valor de una")
    v_rc, v_ec, sin = 0.0, 0.0, []
    for r in rc:
        v = nos_suma(r, cuenta)
        sin += [] if v is not None else [r]
        v_rc += v or 0.0
    for r in ec:
        v = nos_quita(r, cuenta)
        sin += [] if v is not None else [r]
        v_ec += v or 0.0
    if sin:
        bloqueos.append("sin valor del juego (your_value) para " + ", ".join(sin))
    v_rec = v_rc + (rec.get("primas") or 0)
    v_ent = v_ec + (ent.get("primas") or 0)
    neto = v_rec - v_ent - ev["comision"]
    return dict(ev, recibo=round(v_rec, 2), entrego=round(v_ent, 2), neto=round(neto, 2),
                renta=neto > 0 and not bloqueos, bloqueos=bloqueos, cartas_recibo=round(v_rc, 2),
                cartas_entrego=round(v_ec, 2), fuente="juego",
                calculado={"recibo": ev["recibo"], "entrego": ev["entrego"], "neto": ev["neto"]})


def para_duelo(d):
    """{"rol", "limite", "aceptar_ya"}: nuestro límite (lo da el juego) y lo que nos daría aceptar ya la última oferta
    del rival (None si aún no ha ofrecido). No decide: la Duelista decide con estos números."""
    rol, limite = d["rol"], d["limite"]
    rival = (d.get("rival") or [None])[-1]
    return {"rol": rol, "limite": limite,
            "aceptar_ya": ganancia_duelo(rol, limite, rival) if isinstance(rival, (int, float)) else None}


def ganancia_duelo(rol, limite, precio):
    """Lo que nos da un duelo a `precio`. Negativo = fuera de nuestro límite."""
    return duelo.ganancia(rol, limite, precio)
