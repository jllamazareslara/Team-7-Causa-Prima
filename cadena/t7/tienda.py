"""El Regateador: compra y vende a los vendedores del juego.

Lo que sabemos de ellos (reglas): solo se mueven si nos movemos; pasos pequeños reciben pasos pequeños; repetir precio no
consigue nada; cada conversación tiene un límite secreto; cuando se acaba su paciencia dan una oferta final.

De ahí sale la idea central: si el vendedor IMITA nuestros pasos con un factor k, el precio de encuentro es

        encuentro = nuestra_apertura + (su_apertura − nuestra_apertura) / (1 + k)

y NO depende del tamaño de nuestros pasos. Depende de dónde abrimos. Por eso abrimos bajo (ancla) y repartimos el
camino entre las rondas que quedan antes de que se le acabe la paciencia:

        paso = distancia_que_queda / ((1 + k̂) × rondas_que_quedan)

k̂ se mide en vivo: lo que ha cedido él / lo que hemos cedido nosotros (con un valor inicial por perfil).
Reciprocidad: si k̂ < 0,5 (él cede poco), nuestro paso no pasa de lo que él cedió en su último paso.
Vendiendo usamos pasos fijos del 11 % de la diferencia inicial: en el simulador aguantan mejor a un vendedor que cede poco.
Cuando él deja de moverse está en su suelo: aceptamos su precio (es el mejor posible, puntúa 100 %).

Todo es simétrico al vender: "subir" pasa a ser "bajar". s = +1 comprando, −1 vendiendo.
Puntúa: (su apertura − lo pagado) / (su apertura − su suelo). Nunca se cruza nuestro tope (comprando) o suelo (vendiendo).
"""
import math


def _redondear(x, s):
    """Comprando redondeamos hacia abajo (nos favorece), vendiendo hacia arriba."""
    return math.floor(x) if s > 0 else math.ceil(x)


def imitacion_estimada(nuestras, suyas, s, k0, peso=3.0):
    """k̂ = (lo que cedió él desde nuestra apertura + k0·peso) / (lo que cedimos nosotros + peso)."""
    if len(nuestras) < 2 or len(suyas) < 2:
        return k0
    nuestro = s * (nuestras[-1] - nuestras[0])
    suyo = s * (suyas[1] - suyas[-1])        # suyas[1] es su respuesta a nuestra apertura
    return max(0.05, (suyo + k0 * peso) / (max(nuestro, 0) + peso))


def apertura(lado, su_precio, pf, lista=None, p=None):
    if lado == "compra":
        return max(1, math.floor(pf["apertura_compra"] * su_precio))
    mult_oferta = pf.get("venta_multiplo_oferta") or (p["tienda.venta.multiplo_oferta"] if p else 3.0)   # propio del vendedor (Pilar)
    mult_lista = p["tienda.venta.multiplo_lista"] if p else 2.0
    return math.ceil(max(mult_oferta * su_precio, mult_lista * (lista or 0)))


def decidir(st, pf, p=None):
    """st = {"lado": "compra"|"venta", "limite": tope o suelo, "suyas": [su apertura, ...], "nuestras": [...],
             "final": bool, "lista": precio de lista (vendiendo)}
    pf = perfil del vendedor (params.perfil). Devuelve (acción, precio, motivo).
    acciones: "ofrecer", "aceptar", "retirarse"."""
    s = 1 if st["lado"] == "compra" else -1
    lim, suyas, nuestras = st["limite"], st["suyas"], st["nuestras"]
    suyo = suyas[-1]
    dentro = s * (lim - suyo) >= 0                     # su precio no cruza nuestro límite

    if st.get("final"):
        return ("aceptar", suyo, "oferta final dentro de nuestro límite") if dentro else \
               ("retirarse", None, "oferta final fuera de nuestro límite: irse no cuesta nada")

    if not nuestras:
        a = apertura(st["lado"], suyas[0], pf, st.get("lista"), p)
        if s * (a - lim) > 0:
            a = lim
        if s * (suyo - a) <= 0:                         # ya nos ofrece algo mejor que nuestra apertura
            return ("aceptar", suyo, "su primer precio ya es mejor que nuestra apertura") if dentro else \
                   ("retirarse", None, "fuera de límite")
        return ("ofrecer", a, f"apertura al {pf['apertura_compra']:.0%} de su precio" if s > 0 else "apertura alta")

    ultimo = nuestras[-1]
    k = imitacion_estimada(nuestras, suyas, s, pf["imitacion_inicial"])
    quedan = max(1, pf["paciencia_estimada"] - pf["margen_rondas"] - len(nuestras))
    distancia = s * (suyo - ultimo)
    paso = max(1, _redondear(distancia / ((1 + k) * quedan), 1))
    # reciprocidad: si él cede poco (k̂ bajo), no corremos hacia él; cedemos lo que él cedió, como mucho
    if s > 0 and len(suyas) >= 3 and k < pf.get("k_reciproco", 0.5):
        su_paso = s * (suyas[-2] - suyas[-1])
        paso = max(1, min(paso, math.ceil(su_paso * pf.get("factor_reciproco", 1.0))))
    if s < 0:
        # vendiendo: pasos fijos del 11 % de la diferencia inicial (lo del equipo que va primero; ganó en el simulador)
        fijo = p["tienda.venta.paso_fijo"] if p else 0.11
        paso = max(1, round(fijo * s * (suyas[0] - nuestras[0])))
    siguiente = ultimo + s * paso
    if s * (siguiente - lim) > 0:
        siguiente = lim

    # se ha parado: dos respuestas seguidas cediendo menos de un cuarto de nuestro paso → está en su suelo
    if pf.get("aceptar_si_se_para", 0) and len(suyas) >= 3 and len(nuestras) >= 2:
        p1, p2 = s * (suyas[-2] - suyas[-1]), s * (suyas[-3] - suyas[-2])
        n1, n2 = s * (nuestras[-1] - nuestras[-2]), s * (nuestras[-2] - nuestras[-3]) if len(nuestras) >= 3 else s * (nuestras[-1] - nuestras[-2])
        if p1 <= 0.25 * max(n1, 1) and p2 <= 0.25 * max(n2, 1) and dentro:
            return ("aceptar", suyo, "ha dejado de ceder: está en su suelo")

    if s * (suyo - siguiente) <= 0 and dentro:
        return ("aceptar", suyo, "su precio ya alcanza nuestra oferta siguiente")
    if siguiente == ultimo:
        return ("retirarse", None, "llegamos a nuestro límite y él no baja")
    return ("ofrecer", siguiente, f"paso {paso} (k̂ {k:.2f}, quedan {quedan} rondas)")
