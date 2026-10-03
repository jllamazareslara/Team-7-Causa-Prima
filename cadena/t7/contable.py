"""La Contable en la cadena: hace las cuentas con la calculadora (`valor.py`) y se las pasa a quien las necesita.

¿Renta? ¿Cuánto? Va después de los Ojos y antes de los negociadores. No decide nada:
    para_vendedor(c, ...)   → los números del Regateador para una conversación: si conocemos la carta, cuánto nos vale,
                              nuestro tope (comprando) o suelo (vendiendo), si está protegida y cuánto deja pagar la caja
    ficha(propuesta, ...)   → la ficha que recibe el Guardia antes de cada firma (lo que entra, lo que sale, comisión, neto)
    ganancia_duelo(...)     → lo que nos da un duelo a ese precio, calculado aquí y no por la Duelista
El Regateador negocia con sus números; el Guardia decide con su ficha.
"""
import math

from . import duelo
from . import valor as V


def caja_para_comprar(carta, cuenta, efectivo, p, ordenes):
    """Lo máximo que la caja deja pagar por esta carta: lo que queda sobre la reserva y, con la caja justa, el tope
    por trato (salvo la carta que completa una página, igual que en el Guardia)."""
    libre = math.floor(efectivo - p["guardia.reserva_efectivo"])
    tope = ordenes.get("tope_por_trato")
    if tope is None or V.estado_pagina(cuenta, V.barrio(carta))[1] == [carta]:
        return libre
    return min(libre, tope)


def limite_vendedor(lado, carta, cuenta):
    """Nuestro tope (comprando) o suelo (vendiendo) para esa carta, con el bono de página incluido."""
    if lado == "compra":
        return math.floor(V.valor_recibir(cuenta, [carta]))
    perdida = V.valor_entregar(cuenta, [carta])
    return None if perdida is None else math.ceil(perdida + 1)


def para_vendedor(c, cuenta, efectivo, p, ordenes):
    """{"conocida", "nos_vale", "limite", "protegida", "caja"}. Sin carta conocida no se calcula nada más."""
    carta, lado = c.get("carta"), c.get("lado")
    if not isinstance(carta, str) or not V.conocida(carta):
        return {"conocida": False, "nos_vale": None, "limite": None, "protegida": False, "caja": None}
    if lado == "compra":
        nos_vale = V.valor_recibir(cuenta, [carta])
    else:
        nos_vale = V.valor_entregar(cuenta, [carta])
    return {"conocida": True, "nos_vale": nos_vale, "limite": limite_vendedor(lado, carta, cuenta),
            "protegida": lado == "venta" and V.protegida(cuenta, carta),
            "caja": caja_para_comprar(carta, cuenta, efectivo, p, ordenes) if lado == "compra" else None}


def ficha(propuesta, cuenta, efectivo, p=None, mult=None, reserva=None):
    """La ficha de la calculadora para el Guardia y para el Cambista. La reserva sale de `p` si no se da."""
    if reserva is None:
        reserva = p["guardia.reserva_efectivo"] if p else 0
    return V.evaluar(propuesta, cuenta, efectivo, mult or V.NUESTROS_MULT, reserva)


def ganancia_duelo(rol, limite, precio):
    """Lo que nos da un duelo a `precio`. Negativo = fuera de nuestro límite."""
    return duelo.ganancia(rol, limite, precio)
