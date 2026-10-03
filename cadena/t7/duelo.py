"""La Duelista: duelos de precio contra otro equipo (y versión con día de entrega).

Lo que sabemos: cada lado ve solo su límite; fuera del límite resta; sin trato, cero; cada ronda encoge el trato
(descuento δ ≈ 0,94). Cada escenario se juega dos veces, una desde cada lado.

Cómo piensa, en tres fórmulas:

1. Cuánto pedir en la ronda t de T (curva de concesión "Boulware", la de los ganadores de la competición ANAC):
       margen(t) = margen_inicial × (1 − (t/T)^(1/β)) + margen_final × (t/T)^(1/β)
   con β < 1: casi no se mueve hasta el final. margen = distancia a nuestro límite, en nuestro favor.

2. Dónde está su límite (modelo del rival): sus pasos se van encogiendo con razón q = paso_k / paso_(k−1);
   lo que le queda por ceder es paso_k × q / (1 − q). Su límite estimado = su último precio + eso.
   Con la memoria de escenario (lo jugamos desde el otro lado) su límite se conoce exacto. Ojo, medido en el simulador:
   pedir el 85 % de la tarta conocida, o recortar el ancla a su límite, sale PEOR. Se usa solo para no cerrar nunca
   si no hay tarta y para fijar la cuota mínima.

3. Cuándo aceptar (regla "AC_next" con descuento): aceptamos su precio si
       lo que nos da su precio ≥ δ × lo que nos daría nuestra próxima oferta
   porque esperar una ronda cuesta (1 − δ) aunque la acepte. En la última ronda, cualquier precio dentro del límite.

Nunca: ofrecer ni aceptar fuera de nuestro límite. Lo que escriba el rival no entra aquí: solo sus números.
"""
import math


def ganancia(rol, limite, precio):
    """Lo que nos da un trato a `precio`. Negativo = fuera del límite."""
    return precio - limite if rol == "seller" else limite - precio


def limite_rival_estimado(rol, rivales):
    """Extrapola dónde se parará el rival por cómo se encogen sus pasos. None si no hay datos."""
    if len(rivales) < 3:
        return None
    s = 1 if rol == "seller" else -1        # si vendemos, el rival compra y sus precios suben; si compramos, bajan
    pasos = [s * (b - a) for a, b in zip(rivales, rivales[1:])]
    p1, p2 = pasos[-1], pasos[-2]
    if p1 <= 0 or p2 <= 0:
        return rivales[-1]
    q = min(p1 / p2, 0.9)
    return rivales[-1] + s * p1 * q / (1 - q)


def decidir(st, p):
    """st = {"rol": "seller"|"buyer", "limite": n, "rival": [sus precios], "nuestras": [...], "ronda": t, "rondas": T,
             "limite_rival": n o None (memoria de escenario)}
    Devuelve (acción, precio, motivo): "ofrecer" | "aceptar" | "esperar"."""
    rol, lim = st["rol"], float(st["limite"])
    s = 1 if rol == "seller" else -1                   # signo de "más para nosotros"
    T = st.get("rondas") or p["duelo.rondas"]
    t = min(st.get("ronda", len(st["nuestras"])), T - 1)
    delta, beta = p["duelo.descuento_ronda"], p["duelo.dureza_beta"]
    rivales, nuestras = st["rival"], st["nuestras"]
    su = rivales[-1] if rivales else None

    # margen inicial: el ancla (apertura) o, con memoria de escenario, el 85 % de la tarta conocida
    lr = st.get("limite_rival")
    tarta_est = None
    if lr is not None and ganancia(rol, lim, lr) <= 0:
        return ("esperar", None, "memoria de escenario: no hay tarta, cualquier trato nos haría perder")
    if lr is not None:
        # conocer su límite no hace que acepte cerca de él: solo evita pedir algo imposible y cerrar por debajo
        tarta = abs(lr - lim)
        ancla = lim * p["duelo.apertura_vendedor"] if rol == "seller" else lim * p["duelo.apertura_comprador"]
        m0 = abs(ancla - lim)                          # medido: recortar el ancla a su límite empeora (0,395 frente a 0,432)
        mfin = max(1.0, p["duelo.cuota_minima"] * tarta)
    else:
        ancla = lim * p["duelo.apertura_vendedor"] if rol == "seller" else lim * p["duelo.apertura_comprador"]
        m0 = abs(ancla - lim)
        est = limite_rival_estimado(rol, rivales)
        tarta_est = abs(est - lim) if est is not None and ganancia(rol, lim, est) > 0 else None
        mfin = max(1.0, p["duelo.cuota_minima"] * (tarta_est if tarta_est else m0))
        if tarta_est:                                   # no pedir más de lo que cabe en su límite estimado
            m0 = min(m0, max(tarta_est * 0.95, mfin))
    # Parche B (silencio del rival): si llevamos ofertas sin que nos contesten con precio, aflojar la curva.
    # Boulware duro gana en el simulador pero deja 9 de 9 no-deals en vivo (rival calla, esperamos hasta el final,
    # el decay se come la tarta). Cada oferta nuestra sin respuesta sube `beta_eff` → curva más lineal.
    silencio = max(0, len(nuestras) - len(rivales))
    beta_eff = beta * (1 + 0.5 * silencio) if silencio >= 2 else beta
    x = (t / max(T - 1, 1)) ** (1 / beta_eff)
    margen = m0 * (1 - x) + mfin * x
    # Parche A (última ronda al límite): si hay tarta y es la última ronda, el margen mínimo del 5 % puede
    # dejarnos por encima del límite real del rival y perder el trato. Mejor ir al límite que no cerrar.
    # Solo si sabemos (memoria) o estimamos que hay tarta positiva; si no, mantener el Boulware normal.
    if t >= T - 1 and (lr is not None or (tarta_est or 0) > 0):
        margen = 0.0
    nuestra = lim + s * margen
    nuestra = math.ceil(nuestra) if s > 0 else math.floor(nuestra)
    if nuestra % 5 == 0:                                # número preciso, no redondo
        nuestra += s
    if su is not None and ganancia(rol, lim, su) >= 0:
        g_su, g_nuestra = ganancia(rol, lim, su), ganancia(rol, lim, nuestra)
        if g_su >= delta * g_nuestra:
            return ("aceptar", su, f"su precio da {g_su:.0f}; esperar una ronda daría como mucho {delta * g_nuestra:.0f}")
        if t >= T - 1:
            return ("aceptar", su, "última ronda: algo es mejor que cero")
    if ganancia(rol, lim, nuestra) < 0:
        nuestra = lim + s
    if nuestras and nuestra == nuestras[-1] and t < T - 1:
        return ("ofrecer", nuestra, "mantenemos el precio")
    return ("ofrecer", nuestra, f"ronda {t + 1}/{T}: margen {margen:.0f}")


# ---------- duelos con día de entrega ----------

def mejor_dia(pesos, por_defecto=5, hacia=None):
    """El día de entrega que más nos vale según `your_days_weight`. Su forma real aún no se ha visto en un duelo:
    se entiende una lista (posición = día) o un diccionario {día: peso}. Con cualquier otra cosa, el día por defecto.
    Devuelve (día, motivo). Un mensaje con precio y sin día lo rechaza el juego, así que siempre sale un día.

    hacia: "pronto" o "tarde" si hay una pista de lo que prefiere el rival (ver dia_preferido_rival). Entre los
    días que nos cuestan casi lo mismo que el mejor (dentro del 5 % de nuestro propio rango de valores por día),
    se elige el más cercano a esa preferencia: cedemos lo que apenas nos cuesta, nunca lo que sí nos importa."""
    try:
        if isinstance(pesos, dict):
            pares = [(int(k), float(v)) for k, v in pesos.items()]
        elif isinstance(pesos, (list, tuple)):
            pares = [(i, float(v)) for i, v in enumerate(pesos)]
        else:
            pares = []
    except (TypeError, ValueError):
        pares = []
    pares = [(d, v) for d, v in pares if 0 <= d <= 10]
    if len(pares) < 2 or len({v for _, v in pares}) < 2:
        return por_defecto, f"día {por_defecto}: no hay pesos por día que entendamos"
    if hacia in ("pronto", "tarde"):
        mejor, rango = max(v for _, v in pares), max(v for _, v in pares) - min(v for _, v in pares)
        cercanos = [(d, v) for d, v in pares if mejor - v <= 0.05 * rango]
        if len(cercanos) > 1:
            d = (min if hacia == "pronto" else max)(cercanos, key=lambda x: x[0])[0]
            return d, f"día {d}: casi tan bueno como nuestro mejor, y el rival parece preferir {hacia}"
    d = max(pares, key=lambda x: (x[1], -abs(x[0] - por_defecto)))[0]
    return d, f"día {d}: el que más nos vale según nuestros pesos"


def paquetes_iguales(rol, lim, pesos, margen, dias=range(11)):
    """Todos los (precio, día) que nos dan la misma utilidad `margen`. pesos[d] = lo que nos vale el día d (en primas).
    Ofrecer dos de ellos muy distintos revela qué le importa al rival."""
    s = 1 if rol == "seller" else -1
    return [(math.ceil(lim + s * (margen - pesos[d])) if s > 0 else math.floor(lim + s * (margen - pesos[d])), d)
            for d in dias]


def dia_preferido_rival(sus_ofertas):
    """El rival propone días que le convienen: si sus días suben, prefiere tarde; si bajan o se quedan bajos, pronto."""
    if not sus_ofertas:
        return None
    dias = [d for _, d in sus_ofertas]
    return "tarde" if sum(dias) / len(dias) > 5 else "pronto" if sum(dias) / len(dias) < 5 else None
