"""La Contable en la cadena: hace las cuentas con la calculadora (`valor.py`) y se las pasa a quien las necesita.

¿Renta? ¿Cuánto? Va después de los Ojos y antes de los negociadores. No decide nada:
    para_vendedor(c, ...)   → los números del Regateador para una conversación: si conocemos la carta, cuánto nos vale,
                              nuestro tope (comprando) o suelo (vendiendo), si está protegida y cuánto deja pagar la caja
    ficha(propuesta, ...)   → la ficha que recibe el Guardia antes de cada firma (lo que entra, lo que sale, comisión, neto)
    para_duelo(d)           → los números de la Duelista antes de decidir: nuestro límite y lo que daría aceptar ya
    ganancia_duelo(...)     → lo que nos da un duelo a ese precio, calculado aquí y no por la Duelista
El Regateador negocia con sus números; el Guardia decide con su ficha.
"""
import math

from . import duelo
from . import valor as V


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


def limite_vendedor(lado, carta, cuenta):
    """Nuestro tope (comprando) o suelo (vendiendo) para esa carta, con el bono de página incluido.
    Si el juego ya nos ha dicho su your_value (/api/me, /api/me/value), gana el más prudente de los dos:
    nunca pagar más de lo que el juego nos suma ni vender por menos de lo que nos quita."""
    if lado == "compra":
        tope = math.floor(V.valor_recibir(cuenta, [carta]))
        juego = V.VALOR_RECIBIR.get(carta)
        return tope if juego is None else min(tope, math.floor(juego))
    perdida = V.valor_entregar(cuenta, [carta])
    juego = V.VALOR_DAR.get(carta)
    if juego is not None:
        perdida = juego if perdida is None else max(perdida, juego)
    return None if perdida is None else math.ceil(perdida + 1)


def para_vendedor(c, cuenta, efectivo, p, ordenes):
    """{"conocida", "nos_vale", "limite", "protegida", "caja"}. Sin carta conocida no se calcula nada más."""
    carta, lado = c.get("carta"), c.get("lado")
    if not isinstance(carta, str) or not V.conocida(carta):
        return {"conocida": False, "nos_vale": None, "limite": None, "protegida": False, "caja": None}
    if lado == "compra":
        nos_vale = V.VALOR_RECIBIR.get(carta, V.valor_recibir(cuenta, [carta]))
    else:
        nos_vale = V.VALOR_DAR.get(carta, V.valor_entregar(cuenta, [carta]))
    return {"conocida": True, "nos_vale": nos_vale, "limite": limite_vendedor(lado, carta, cuenta),
            "protegida": lado == "venta" and V.protegida(cuenta, carta),
            "caja": caja_para_comprar(carta, cuenta, efectivo, p, ordenes) if lado == "compra" else None}


def ficha(propuesta, cuenta, efectivo, p=None, mult=None, reserva=None):
    """La ficha de la calculadora para el Guardia y para el Cambista. La reserva sale de `p` si no se da."""
    if reserva is None:
        reserva = p["guardia.reserva_efectivo"] if p else 0
    return V.evaluar(propuesta, cuenta, efectivo, mult or V.NUESTROS_MULT, reserva)


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
