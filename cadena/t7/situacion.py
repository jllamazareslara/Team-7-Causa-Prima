"""La situación del día: adapta los ajustes de todos los agentes a lo que hay hoy, sin tocar código.

Entra:  el estado leído del juego (efectivo, cartas, segundos por tick) y hoy.json (las noticias del día).
Sale:   un plan = modo de caja, ajustes cambiados con su motivo, categorías forzadas y órdenes para la cadena.

Sin red y sin azar: mismo estado y mismo hoy.json, mismo plan. Los agentes no cambian: reciben los ajustes del plan
(plan["p"]) en vez de los de parametros.json, y el guardia recibe plan["forzar"] y el tope por trato.

Modos de caja (libre = efectivo − guardia.reserva_efectivo):
    holgado  efectivo ≥ colchón                → todo normal
    justo    efectivo < colchón, o libre < 3 compras baratas
                                               → vender antes de comprar; comprar solo lo de la escalera y lo que
                                                 completa página; sin sobres; cada trato compromete como mucho libre / 3
    seco     libre < la compra más barata      → no se abre ninguna compra; se vende, se cambia carta por carta
                                                 y se juegan los duelos, que no cuestan efectivo
"""
import json
import os

from . import params
from .valor import liquidez

RUTA_HOY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hoy.json")
TRATOS_ESCALERA = 3            # cuentan los tres mejores tratos por vendedor: el efectivo libre se reparte entre tres
APERTURA_TRAS_ENFADOS = 0.20   # "Lo que no sabemos": si un vendedor corta mucho, apertura al 20 %
ENFADOS_PARA_SUBIR = 2
RESERVA_MERCADO = 270          # 250 de fianza + 20: lo que cuesta abrir mercado propio


def leer_hoy(ruta=RUTA_HOY):
    """Las noticias del día. Si el archivo no existe, no hay noticias."""
    if not os.path.exists(ruta):
        return {}
    with open(ruta, encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


def modo_caja(efectivo, p, compra_minima=10):
    """Devuelve (modo, efectivo libre). compra_minima = el precio de lista más barato que hay hoy."""
    libre = efectivo - p["guardia.reserva_efectivo"]
    if libre < compra_minima:
        return "seco", libre
    if efectivo < max(p["guardia.colchon_efectivo"], p["guardia.reserva_efectivo"] + TRATOS_ESCALERA * compra_minima):
        return "justo", libre
    return "holgado", libre


def plan(estado, hoy=None, precios_venta=None):
    """estado = {"efectivo": n, "cuenta": {ref: copias}, "tick_segundos": n (opcional)}
    hoy    = el contenido de hoy.json (si es None, se lee del archivo)
    precios_venta = {ref: primas que nos dan por una copia}, para saber qué vender si falta efectivo (opcional)
    """
    hoy = leer_hoy() if hoy is None else hoy
    base = params.cargar()
    cambios, motivos, avisos, forzar, ordenes = {}, [], [], {}, {}

    def cambia(nombre, valor, motivo):
        if nombre not in base:
            avisos.append(f"{nombre}: ese ajuste no existe, se ignora")
            return
        if valor != base[nombre]:
            cambios[nombre] = valor
            motivos.append(f"{nombre}: {base[nombre]} → {valor} · {motivo}")

    # 1. Lo que el equipo ha decidido hoy a mano.
    for nombre, valor in (hoy.get("ajustes") or {}).items():
        cambia(nombre, valor, "decidido hoy por el equipo")
    if hoy.get("guardar_para_mercado"):
        cambia("guardia.reserva_efectivo", RESERVA_MERCADO, "se guarda lo que cuesta abrir mercado propio")
    if hoy.get("mesa_permite_inyeccion_equipos"):
        cambia("ataque.inyeccion_equipos", 1, "la mesa de organización lo ha confirmado")
    duelo = hoy.get("duelo") or {}
    if duelo.get("rondas"):
        cambia("duelo.rondas", duelo["rondas"], "visto en un duelo real")
    if duelo.get("descuento_ronda"):
        cambia("duelo.descuento_ronda", duelo["descuento_ronda"], "visto en un duelo real")
    for vendedor, veces in (hoy.get("enfados") or {}).items():
        nombre = f"tienda.{vendedor}.apertura_compra"
        if veces >= ENFADOS_PARA_SUBIR and nombre in base and base[nombre] < APERTURA_TRAS_ENFADOS:
            cambia(nombre, APERTURA_TRAS_ENFADOS, f"{vendedor} ha cortado {veces} conversaciones: abrimos menos abajo")
    for cat in hoy.get("apagar") or []:
        forzar[cat] = "apagado"

    # 2. La caja.
    p = params.cargar(cambios=cambios)
    efectivo = estado["efectivo"]
    modo, libre = modo_caja(efectivo, p, hoy.get("compra_minima", 10))
    ordenes["compras"] = "todas"
    ordenes["ventas_primero"] = modo != "holgado"
    ordenes["tope_por_trato"] = None
    if modo != "holgado":
        tope = max(0, libre // TRATOS_ESCALERA)
        ordenes["tope_por_trato"] = tope
        ordenes["compras"] = "ninguna" if modo == "seco" else "escalera_y_pagina"
        forzar["sobre"] = "apagado"
        motivos.append(f"caja {modo}: quedan {max(0, libre):.0f} P libres, tope de {tope} P por trato")
    ordenes["sin_coste"] = ["duelos", "vender a vendedores", "cambios carta por carta", "Market Test del puesto gratuito"]
    if hoy.get("solo_vender"):                          # el equipo solo quiere vender (las repetidas): nada de compras
        ordenes["compras"] = "ninguna"
        cambios["cambista.pedir"] = 0                     # manda sobre lo que diga "ajustes"
        motivos[:] = [m for m in motivos if not m.startswith("cambista.pedir:")]
        motivos.append("solo vender: no se abren compras a vendedores, no se publican peticiones ni cambios y no se "
                       "compra en El Rastro")

    # 3. Qué vender para volver al colchón, sin perder valor.
    ventas = None
    if modo != "holgado" and precios_venta:
        ventas = liquidez(estado.get("cuenta", {}), efectivo, precios_venta, p["guardia.colchon_efectivo"])
        ordenes["vender"] = [v["ref"] for v in ventas["ventas"] if v["necesaria"]]
        if not ventas["llega"]:
            avisos.append(f"vendiendo todo lo que no pierde valor se llega a {ventas['efectivo_final']:.0f} P, "
                          f"no a {p['guardia.colchon_efectivo']}")

    p = params.cargar(cambios=cambios)
    avisos.extend(p["_avisos"])
    return {"modo_caja": modo, "efectivo": efectivo, "libre": libre, "cambios": cambios, "motivos": motivos,
            "forzar": forzar, "ordenes": ordenes, "ventas": ventas, "avisos": avisos, "p": p}


def resumen(pl):
    """Lo que se enseña en pantalla y se apunta en el diario al empezar el día y cada vez que cambia el modo."""
    o = pl["ordenes"]
    lineas = [f"CAJA         {pl['modo_caja'].upper()} · {pl['efectivo']:.0f} P, {max(0, pl['libre']):.0f} libres",
              f"COMPRAS      {o['compras']}" + (f" · tope {o['tope_por_trato']} P por trato" if o['tope_por_trato'] is not None else ""),
              f"PRIMERO      {'vender' if o['ventas_primero'] else 'lo normal: vender repetidas, luego comprar'}"]
    if o.get("vender"):
        lineas.append("VENDER       " + ", ".join(o["vender"]))
    lineas.append("SIN COSTE    " + ", ".join(o["sin_coste"]))
    lineas.append("FORZADO      " + (", ".join(f"{k}: {v}" for k, v in sorted(pl["forzar"].items())) or "nada"))
    lineas += ["CAMBIO       " + m for m in pl["motivos"]]
    lineas += ["AVISO        " + a for a in pl["avisos"]]
    return "\n".join(lineas)
