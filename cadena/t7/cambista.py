"""El Cambista: El Rastro y los cambios con otros equipos. Aquí está el valor grande.

Por qué: con los vendedores solo cuentan los tres mejores tratos (como porcentaje de su rango). Con los equipos cuenta
TODO el valor ganado, medido con nuestros valores privados. Y los valores privados son muy distintos entre equipos:
una repetida nos vale 0,5–4 y a quien le falta para completar página le puede valer 50–150 (bono del 25 %).

Cuatro herramientas:
1. vendibles()       qué podemos dar perdiendo poco (repetidas, barrios bajos), nunca lo protegido
2. precio_anuncio()  a cuánto anunciar, y cómo baja si caduca: max(lista × 0,9 − caducidades, lo que nos vale + 1)
3. oportunidades()   cada oferta del tablón pasada por la calculadora, en los dos sentidos (comprar y vender)
4. mapa_deseos()     qué barrios valora cada equipo, deducido de lo que pide y paga en público
   y cazador de páginas: quien pide UNA carta concreta varias veces probablemente completa página → cobrar caro.
"""
import math
from collections import defaultdict

from . import valor as V


def vendibles(cuenta, mult=V.NUESTROS_MULT):
    """[(ref, lo que perdemos al darla)] de menos a más pérdida. Nunca cartas protegidas."""
    out = []
    for ref, n in cuenta.items():
        if n <= 0 or V.protegida(cuenta, ref, mult):
            continue
        perdida = V.valor_entregar(cuenta, [ref], mult)
        if perdida is not None:
            out.append((ref, round(perdida, 2)))
    return sorted(out, key=lambda x: x[1])


def precio_anuncio(lista_vendedor, perdida, caducidades, p):
    """Precio de un anuncio de venta en El Rastro. El que acepta paga la comisión."""
    inicial = math.ceil(p["rastro.precio_inicial_lista"] * lista_vendedor)
    minimo = math.ceil(perdida + 1)
    return max(inicial - p["rastro.bajada_por_caducidad"] * caducidades, minimo)


def oportunidades(tablon, cuenta, efectivo, mult=V.NUESTROS_MULT, reserva=0):
    """tablon = [{"id", "maker", "give": {...}, "want": {...}}] tal como lo da board("rastro").
    Devuelve las ofertas que nos convendría ACEPTAR, de más a menos neto, con su ficha."""
    out = []
    for o in tablon:
        give, want = o.get("give", {}), o.get("want", {})
        recibo_cartas = [a["ref"] if isinstance(a, dict) else a for a in give.get("assets", [])]
        entrego_cartas = list(want.get("cards", []))
        prop = {"tipo": "equipo", "mercado": "rastro", "pagamos_comision": True,
                "recibo": {"cartas": recibo_cartas, "primas": give.get("cash", 0) or 0},
                "entrego": {"cartas": entrego_cartas, "primas": want.get("cash", 0) or 0}}
        if not recibo_cartas and not entrego_cartas:
            continue
        ev = V.evaluar(prop, cuenta, efectivo, mult, reserva)
        if ev["renta"]:
            out.append({"oferta": o["id"], "maker": o.get("maker"), "neto": ev["neto"], "ficha": ev, "propuesta": prop})
    return sorted(out, key=lambda x: -x["neto"])


def peticion(ref, cuenta, mult=V.NUESTROS_MULT, fraccion=0.35):
    """Cuánto ofrecer de entrada por una carta que nos falta: una fracción (ancla) de lo que nos vale DE VERDAD,
    bono de página incluido. Se sube poco a poco hasta como mucho el 70 %."""
    v = V.valor_recibir(cuenta, [ref], mult)
    return {"carta": ref, "nos_vale": round(v, 1), "apertura": math.floor(v * fraccion), "tope": math.floor(v * 0.70)}


def mapa_deseos(observaciones):
    """observaciones = [{"maker", "ref", "precio", "lado": "compra"|"venta"}] vistas en el tablón a lo largo del día.
    Devuelve {maker: [(barrio, interés)]}: interés = precio medio que paga dividido por la base de la rareza
    (≈ su multiplicador de ese barrio, sin contar bonos). Quien paga 16 por una común de un barrio lo tiene a ×1,6."""
    acum = defaultdict(lambda: defaultdict(list))
    for ob in observaciones:
        if ob["lado"] != "compra":
            continue
        acum[ob["maker"]][V.barrio(ob["ref"])].append(ob["precio"] / V.BASE[V.rareza(ob["ref"])])
    return {m: sorted(((b, round(sum(x) / len(x), 2)) for b, x in d.items()), key=lambda t: -t[1])
            for m, d in acum.items()}


def cazador_de_paginas(observaciones, cuenta, mult=V.NUESTROS_MULT, veces=2):
    """Cartas que alguien pide una y otra vez (señal de que le falta para completar) y que podemos dar.
    Devuelve [(ref, maker, su mejor precio visto, lo que perdemos)]: aquí se cobra caro."""
    pedidas = defaultdict(list)
    for ob in observaciones:
        if ob["lado"] == "compra":
            pedidas[(ob["ref"], ob["maker"])].append(ob["precio"])
    disponibles = dict(vendibles(cuenta, mult))
    out = [(ref, maker, max(ps), disponibles[ref]) for (ref, maker), ps in pedidas.items()
           if len(ps) >= veces and ref in disponibles]
    return sorted(out, key=lambda x: -(x[2] - x[3]))
