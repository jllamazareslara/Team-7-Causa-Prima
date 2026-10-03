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

Y para COMPRAR (añadido el 3/10, la estrategia de páginas):
5. lista_compra()    qué cartas nos faltan, cuánto nos vale cada una y cuál comprar primero. La idea: el bono de página
                     (25 % de la suma de la página) solo llega con la ÚLTIMA carta, así que una página a la que le
                     faltan 1 o 2 cartas vale mucho más que cartas sueltas. Ordena por lo que esperamos ganar
                     (lo que nos vale − lo que esperamos pagar) y marca lo que cabe en la caja.
6. peticiones()      las peticiones que publicamos en El Rastro ("pago X por esta carta"): abren bajo, suben un poco
                     cada vez que caducan sin respuesta y nunca pasan del tope. Quien acepta paga la comisión.
REGLA: cada compra renta por sí sola (tope = lo que esa carta nos vale HOY × tope_pct). El bono de página solo
ordena la lista; nunca se paga de más por una carta "porque luego vendrá la otra".
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


# ---------------------------------------------------------------- comprar: la estrategia de páginas

def precio_referencia(ref, mercado=None, listas=None):
    """Lo que esperamos pagar por una carta: lo más barato que se ha visto anunciado en El Rastro; si no se ha visto,
    el precio de lista de un vendedor; si no, la base de su rareza (lo que le vale a un equipo con ese barrio a ×1,0)."""
    vistos = [x for x in (mercado or {}).get(ref, []) if isinstance(x, (int, float)) and x > 0]
    if vistos:
        return min(vistos)
    lista = (listas or {}).get(ref)
    if isinstance(lista, (int, float)) and lista > 0:
        return lista
    return V.BASE[V.rareza(ref)]


def _candidatas(cuenta, b, mult):
    """Las cartas de un barrio que nos interesa tener: las que faltan de su página; con la página completa,
    la épica y la legendaria (dan el 10 % extra)."""
    _, faltan = V.estado_pagina(cuenta, b)
    faltan = [r for r in faltan if V.conocida(r, mult)]
    if faltan:
        return faltan, faltan
    return [r for r in V._extras(b) if cuenta.get(r, 0) <= 0 and V.conocida(r, mult)], []


def lista_compra(cuenta, efectivo, p, mult=None, mercado=None, listas=None):
    """La lista de la compra, de la carta que más nos hace ganar a la que menos.

    Para cada carta que nos falta:
      nos_vale     lo que la colección gana HOY si entra (con el bono si es la última de su página)
      estrategico  lo que vale contando su parte del bono de página, si a la página le faltan pocas
                   (cambista.bono_si_faltan): así una página casi completa sube en la lista antes de llegar a la última
      precio       lo que esperamos pagar (precio_referencia)
      gana         estrategico − precio: lo que ordena la lista
      tope         lo máximo que pagamos: nos_vale × cambista.tope_pct_valor (cada compra renta sola)
      apertura     a cuánto abre una petición: cambista.apertura_peticion × base de la rareza
      en_caja      cabe en lo que queda sobre la reserva, contando las de antes en la lista
    No entra una carta que no conocemos, ni una que esperamos pagar más de lo que nos vale."""
    mult = mult or V.NUESTROS_MULT
    bono_pct = p.get("valor.bono_pagina", 0.25)
    filas = []
    for b in sorted(mult):
        candidatas, faltan = _candidatas(cuenta, b, mult)
        if not candidatas:
            continue
        propio = {r: V.BASE[V.rareza(r)] * mult[b] for r in V.pagina(b)}
        bono = bono_pct * sum(propio.values())
        reparte = 0 < len(faltan) <= p["cambista.bono_si_faltan"]
        suma_faltan = sum(propio.get(r, 0) for r in faltan) or 1
        for ref in candidatas:
            nos_vale = V.valor_recibir(cuenta, [ref], mult)
            completa = faltan == [ref]
            estrategico = nos_vale if completa or not reparte else nos_vale + bono * propio.get(ref, 0) / suma_faltan
            precio = precio_referencia(ref, mercado, listas)
            tope = math.floor(nos_vale * p["cambista.tope_pct_valor"])
            if tope < 1 or estrategico <= precio:
                continue
            nombre = f"{b} {len(V.pagina(b)) - len(faltan)}/{len(V.pagina(b))}"
            motivo = (f"completa la página de {b}: +{bono:.0f} de bono" if completa else
                      f"{nombre}: con las {len(faltan)} que faltan llega el bono de {bono:.0f}" if reparte else
                      f"épica o legendaria de {b}: página completa, +10 %" if not faltan else
                      f"primera copia de {b} ({nombre})")
            filas.append({"carta": ref, "barrio": b, "rareza": V.rareza(ref), "faltan": len(faltan),
                          "completa": completa, "nos_vale": round(nos_vale, 1), "estrategico": round(estrategico, 1),
                          "precio": precio, "gana": round(estrategico - precio, 1), "tope": tope,
                          "apertura": max(1, min(tope, math.floor(p["cambista.apertura_peticion"] * V.BASE[V.rareza(ref)]))),
                          "motivo": motivo})
    filas.sort(key=lambda f: (-f["gana"], f["precio"], f["carta"]))
    libre = efectivo - p["guardia.reserva_efectivo"]
    for f in filas:
        f["en_caja"] = f["precio"] <= libre
        if f["en_caja"]:
            libre -= f["precio"]
    return filas


def peticiones(lista, cuenta, efectivo, p, activas=None, caducidades=None, mult=None):
    """Qué peticiones publicar ahora en El Rastro, siguiendo la lista de la compra.

    activas     = {ref: precio} de nuestras peticiones vivas: ese dinero ya está comprometido y esa carta ya está pedida
    caducidades = {ref: veces que su petición caducó sin respuesta}: cada una sube el precio
                  cambista.subida_por_caducidad × base de la rareza, sin pasar nunca del tope
    Una petición por carta, como mucho cambista.peticiones_max a la vez, y todas juntas sin bajar de la reserva.
    Cada una se pasa antes por la Contable: si no renta, no se publica (nadie la firmará por nosotros después)."""
    activas, caducidades = activas or {}, caducidades or {}
    mult = mult or V.NUESTROS_MULT
    comprometido = sum(activas.values())
    libre = efectivo - p["guardia.reserva_efectivo"] - comprometido
    hueco = int(p["cambista.peticiones_max"]) - len(activas)
    out = []
    for f in lista:
        if hueco <= 0:
            break
        ref = f["carta"]
        if ref in activas or cuenta.get(ref, 0) > 0:
            continue
        subida = math.ceil(p["cambista.subida_por_caducidad"] * V.BASE[f["rareza"]])
        precio = min(f["tope"], f["apertura"] + subida * caducidades.get(ref, 0))
        if precio < 1 or precio > libre:
            continue
        ev = V.evaluar({"tipo": "equipo", "mercado": "rastro", "pagamos_comision": False,
                        "recibo": {"cartas": [ref], "primas": 0}, "entrego": {"cartas": [], "primas": precio}},
                       cuenta, efectivo - comprometido, mult, p["guardia.reserva_efectivo"])
        if not ev["renta"]:
            continue
        out.append({"carta": ref, "precio": precio, "tope": f["tope"], "nos_vale": f["nos_vale"],
                    "gana": round(f["nos_vale"] - precio, 1), "motivo": f["motivo"]})
        libre -= precio
        hueco -= 1
    return out


def resumen_compras(lista, n=6):
    """Las primeras líneas de la lista de la compra, para la pantalla y el diario."""
    if not lista:
        return ["COMPRAR      nada: no falta ninguna carta que nos valga más de lo que cuesta"]
    return [f"COMPRAR      {f['carta']:<7} nos vale {f['nos_vale']:>6.1f} · esperamos {f['precio']:>4} · "
            f"tope {f['tope']:>4} · gana {f['gana']:>6.1f}{'' if f['en_caja'] else ' · NO CABE EN LA CAJA'} · {f['motivo']}"
            for f in lista[:n]]
