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
                     Con la caja corta elige con una mochila exacta el conjunto de compras que más gana EN TOTAL.
6. peticiones()      las peticiones que publicamos en El Rastro ("pago X por esta carta"): abren bajo (o un 15 % por
                     debajo de lo que ya funcionó), suben un poco cada vez que caducan, pasan en 1 P a otro equipo que
                     pida la misma carta y nunca pasan del tope. En el tramo final, directas al tope: el efectivo ya no
                     puntúa. Quien acepta paga la comisión.
7. trueques()        cambios carta por carta: damos repetidas por cartas que nos faltan, sin gastar efectivo.
REGLA: cada compra renta por sí sola (tope = lo que esa carta nos vale HOY × tope_pct). El bono de página solo
ordena la lista; nunca se paga de más por una carta "porque luego vendrá la otra".
"""
import math
from collections import defaultdict

from . import contable
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
        ev = contable.ficha(prop, cuenta, efectivo, mult=mult, reserva=reserva)     # las cuentas, de la Contable
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


def _mochila(filas, libre):
    """Qué compras hacer con el efectivo que hay para ganar lo máximo EN TOTAL (problema de la mochila, exacto).
    Ordenar por ganancia y llenar hasta acabar el dinero se equivoca cuando la caja es corta: dos poco comunes que
    ganan 15 cada una valen más que una rara que gana 21 si solo hay 50 P. Devuelve los índices elegidos."""
    libre = int(max(0, libre))
    mejor = [(0.0, ())] * (libre + 1)          # mejor[c] = (ganancia, índices) gastando como mucho c
    for i, f in enumerate(filas):
        coste = int(math.ceil(f["precio"]))
        if coste > libre:
            continue
        for c in range(libre, coste - 1, -1):
            g = mejor[c - coste][0] + f["gana"]
            if g > mejor[c][0] + 1e-9:
                mejor[c] = (g, mejor[c - coste][1] + (i,))
    return set(mejor[libre][1])


def tope_pct(p, final=False):
    """Parte de lo que nos vale que estamos dispuestos a pagar. En el tramo final del juego el efectivo ya no sirve
    para nada (no puntúa), así que se paga casi todo lo que vale: cada carta que entra sigue sumando."""
    return p["cambista.tope_pct_final"] if final else p["cambista.tope_pct_valor"]


def apertura(ref, tope, p, pagado=None):
    """A cuánto abre una petición. Sin datos: cambista.apertura_peticion × base de la rareza.
    Con datos (pagado = {rareza: [precios a los que ya nos vendieron]}): el 85 % de lo más barato que funcionó,
    porque si alguien aceptó ese precio quizá otro acepte algo menos."""
    r = V.rareza(ref)
    base = math.floor(p["cambista.apertura_peticion"] * V.BASE[r])
    hechos = [x for x in (pagado or {}).get(r, []) if isinstance(x, (int, float)) and x > 0]
    if hechos:
        base = math.floor(0.85 * min(hechos))
    return max(1, min(tope, base))


def lista_compra(cuenta, efectivo, p, mult=None, mercado=None, listas=None, pagado=None, final=False):
    """La lista de la compra, de la carta que más nos hace ganar a la que menos.

    Para cada carta que nos falta:
      nos_vale     lo que la colección gana HOY si entra (con el bono si es la última de su página)
      estrategico  lo que vale contando su parte del bono de página, si a la página le faltan pocas
                   (cambista.bono_si_faltan): así una página casi completa sube en la lista antes de llegar a la última
      precio       lo que esperamos pagar (precio_referencia)
      gana         estrategico − precio: lo que ordena la lista
      tope         lo máximo que pagamos: nos_vale × tope_pct (cada compra renta sola; casi todo en el tramo final)
      apertura     a cuánto abre una petición (ver apertura(): aprende de lo que ya nos vendieron)
      en_caja      la elige la mochila: el conjunto de compras que más gana EN TOTAL con lo que queda sobre la reserva
    No entra una carta que no conocemos, ni una que esperamos pagar más de lo que nos vale.
    Orden: primero lo que cabe en la caja (por ganancia), luego el resto, que sirve para cambios carta por carta."""
    mult = mult or V.NUESTROS_MULT
    bono_pct = p.get("valor.bono_pagina", 0.25)
    pct = tope_pct(p, final)
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
            tope = math.floor(nos_vale * pct)
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
                          "apertura": apertura(ref, tope, p, pagado), "motivo": motivo})
    filas.sort(key=lambda f: (-f["gana"], f["precio"], f["carta"]))
    elegidas = _mochila(filas, efectivo - p["guardia.reserva_efectivo"])
    for i, f in enumerate(filas):
        f["en_caja"] = i in elegidas
    filas.sort(key=lambda f: (not f["en_caja"], -f["gana"], f["precio"], f["carta"]))
    return filas


def peticiones(lista, cuenta, efectivo, p, activas=None, caducidades=None, mult=None, demanda=None, final=False):
    """Qué peticiones publicar ahora en El Rastro, siguiendo la lista de la compra.

    activas     = {ref: precio} de nuestras peticiones vivas: ese dinero ya está comprometido y esa carta ya está pedida
    caducidades = {ref: veces que su petición caducó sin respuesta}: cada una sube el precio
                  cambista.subida_por_caducidad × base de la rareza, sin pasar nunca del tope
    demanda     = {ref: [lo que otros equipos ofrecen por ella en El Rastro]}: si alguien compite por la misma carta,
                  pedimos 1 P más que el mejor mientras quepa en el tope (si no, el que vende elegiría al otro)
    final       = tramo final del juego: se pide directamente al tope, porque el efectivo ya no puntúa
    Una petición por carta, solo de lo que eligió la mochila, como mucho cambista.peticiones_max a la vez, y todas
    juntas sin bajar de la reserva. Cada una se pasa antes por la Contable: si no renta, no se publica."""
    activas, caducidades, demanda = activas or {}, caducidades or {}, demanda or {}
    mult = mult or V.NUESTROS_MULT
    comprometido = sum(activas.values())
    libre = efectivo - p["guardia.reserva_efectivo"] - comprometido
    hueco = int(p["cambista.peticiones_max"]) - len(activas)
    out = []
    for f in lista:
        if hueco <= 0:
            break
        ref = f["carta"]
        if not f.get("en_caja", True) or ref in activas or cuenta.get(ref, 0) > 0:
            continue
        subida = math.ceil(p["cambista.subida_por_caducidad"] * V.BASE[f["rareza"]])
        precio = f["tope"] if final else min(f["tope"], f["apertura"] + subida * caducidades.get(ref, 0))
        rival = max([x for x in demanda.get(ref, []) if isinstance(x, (int, float))], default=0)
        compite = rival >= precio and rival + 1 <= f["tope"]
        if compite:
            precio = int(rival) + 1
        if precio < 1 or precio > libre:
            continue
        ev = contable.ficha({"tipo": "equipo", "mercado": "rastro", "pagamos_comision": False,
                             "recibo": {"cartas": [ref], "primas": 0}, "entrego": {"cartas": [], "primas": precio}},
                            cuenta, efectivo - comprometido, mult=mult, reserva=p["guardia.reserva_efectivo"])
        if not ev["renta"]:
            continue
        out.append({"carta": ref, "precio": precio, "tope": f["tope"], "nos_vale": f["nos_vale"],
                    "gana": round(f["nos_vale"] - precio, 1),
                    "motivo": f["motivo"] + (f" · otro equipo ofrece {rival:g}: +1" if compite else "")
                    + (" · tramo final: al tope" if final else "")})
        libre -= precio
        hueco -= 1
    return out


def trueques(lista, cuenta, p, ocupadas=(), activas=(), mult=None, vivos=None):
    """Cambios carta por carta en El Rastro: damos lo que a nosotros nos vale poco (repetidas, barrios bajos) a cambio
    de una carta de la lista. No gasta efectivo, y a quien le falta nuestra carta le vale mucho más que a nosotros:
    ganan los dos, y con los equipos puntúa todo el valor ganado.

    Para cada carta que queremos (también las que no caben en la caja), ofrece como mucho 2 cartas nuestras vendibles,
    las de rareza más alta primero, hasta que su base sume cambista.trueque_ratio × la base de la que
    pedimos (nadie da una rara por una común). Solo si la Contable dice que renta y nos deja al menos el mismo margen
    que una compra (1 − cambista.tope_pct_valor de lo que vale).
    ocupadas = refs que no se pueden ofrecer (anunciadas, en venta con un vendedor, ya en otro cambio)
    activas  = refs que ya tienen (o tuvieron) un cambio: no se repite; si caducó, le toca a una petición con efectivo
    vivos    = cambios vivos ahora (si no se da, len(activas)). Como mucho cambista.trueques_max a la vez."""
    mult = mult or V.NUESTROS_MULT
    usadas = list(ocupadas)
    hueco = int(p["cambista.trueques_max"]) - (len(activas) if vivos is None else vivos)
    out = []
    for f in lista:
        if hueco <= 0:
            break
        quiero = f["carta"]
        if quiero in activas or cuenta.get(quiero, 0) > 0:
            continue
        disponible = dict(cuenta)
        for r in usadas:
            disponible[r] = disponible.get(r, 0) - 1
        candidatas = [(r, perd) for r, perd in vendibles(disponible, mult)
                      if V.conocida(r, mult) and V.rareza(r) in ("common", "uncommon")]
        candidatas.sort(key=lambda x: (-V.BASE[V.rareza(x[0])], x[1]))
        objetivo = p["cambista.trueque_ratio"] * V.BASE[f["rareza"]]
        doy, suma, actual = [], 0, dict(disponible)
        for r, _ in candidatas:
            if len(doy) == 2 or suma >= objetivo:
                break
            if actual.get(r, 0) <= 0 or V.protegida(actual, r, mult):
                continue
            doy.append(r)
            actual[r] -= 1
            suma += V.BASE[V.rareza(r)]
        if not doy or suma < objetivo:
            continue
        ev = contable.ficha({"tipo": "equipo", "mercado": "rastro", "pagamos_comision": False,
                             "recibo": {"cartas": [quiero], "primas": 0}, "entrego": {"cartas": doy, "primas": 0}},
                            cuenta, 0, mult=mult, reserva=0)
        if not ev["renta"] or ev["neto"] < (1 - p["cambista.tope_pct_valor"]) * f["nos_vale"]:
            continue
        out.append({"quiero": quiero, "doy": doy, "pierdo": ev["entrego"], "nos_vale": f["nos_vale"],
                    "gana": ev["neto"], "motivo": f["motivo"]})
        usadas.extend(doy)
        hueco -= 1
    return out


def resumen_compras(lista, n=6):
    """Las primeras líneas de la lista de la compra, para la pantalla y el diario."""
    if not lista:
        return ["COMPRAR      nada: no falta ninguna carta que nos valga más de lo que cuesta"]
    return [f"COMPRAR      {f['carta']:<7} nos vale {f['nos_vale']:>6.1f} · esperamos {f['precio']:>4} · "
            f"tope {f['tope']:>4} · gana {f['gana']:>6.1f}{'' if f['en_caja'] else ' · NO CABE EN LA CAJA'} · {f['motivo']}"
            for f in lista[:n]]
