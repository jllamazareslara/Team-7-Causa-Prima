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
             "limite_rival": n o None (memoria de escenario), "x": estado por ticks (solo en vivo, ver decidir_vivo)}
    Devuelve (acción, precio, motivo): "ofrecer" | "aceptar" | "esperar".
    Con st["x"] (lo pone duelos.py en vivo) decide la Duelista por ticks; sin él, la de rondas de siempre."""
    if isinstance(st.get("x"), dict):
        accion, precio, _, motivo = decidir_vivo(st, p)
        return (accion, precio, motivo)
    return _decidir_rondas(st, p)


def _decidir_rondas(st, p):
    """La Duelista de rondas (turnos alternos): la usan los simuladores antiguos y los duelos sin estado por ticks."""
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
#
# Forma real (Duels II, 3/10): your_days_weight es UN número y days_meaning dice su sentido:
#     comprando  "each delivery day costs you this much cash"          ganancia = límite − precio − peso × días
#     vendiendo  "each delivery day adds this much cash to your side"  ganancia = precio − límite + peso × días
# Visto en vivo: aceptar 50 P a día 10 con límite 86 y peso 4,02 dio −4,2 (duelo 5635), porque solo se miraba el precio.
# Por eso todo se pasa a PRECIO EFECTIVO = precio + k × días, que se compara con el límite como un precio normal:
# decidir(), la Contable y el Guardia no cambian. Al mandar, se elige el día y se vuelve al precio que se escribe.

def k_dias(rol, peso, sentido):
    """El k del precio efectivo (precio + k × días), o None si el peso o su sentido no se entienden."""
    if not isinstance(peso, (int, float)) or isinstance(peso, bool) or rol not in ("seller", "buyer"):
        return None
    s = sentido.lower() if isinstance(sentido, str) else ""
    if "add" in s or "suma" in s or "añade" in s:
        signo = 1                                          # cada día nos da peso
    elif "cost" in s or "cuesta" in s:
        signo = -1                                         # cada día nos quita peso
    else:
        signo = 1 if rol == "seller" else -1               # texto nuevo: lo visto en los 21 duelos reales del 3/10
    return signo * peso * (1 if rol == "seller" else -1)


def precio_efectivo(precio, dias, k):
    """El precio de un paquete (precio, días) como si fuera solo precio. Sin k o sin días, el precio tal cual."""
    if k is None or not isinstance(dias, (int, float)) or isinstance(dias, bool):
        return precio
    return round(precio + k * dias, 2)


def dia_bueno(rol, k):
    """El día que más nos vale con k: vendiendo, más días suben el precio efectivo si k > 0; comprando, lo bajan si k < 0."""
    if not k:
        return None
    mas_dias_mejor = k > 0 if rol == "seller" else k < 0
    return 10 if mas_dias_mejor else 0


def precio_a_mandar(rol, efectivo, dia, k, limite=None):
    """El precio que se escribe para que (precio, día) valga `efectivo`. Redondeado a nuestro favor, nunca menos de 1.
    Con `limite`, el precio escrito tampoco cruza nuestro límite (vendiendo, nunca por debajo del coste; comprando,
    nunca por encima del valor): las reglas dicen que un trato fuera del límite resta, y no sabemos si miran el precio
    escrito o el que vale con el día. Así el día solo suma."""
    if k is None or dia is None:
        return efectivo
    x = efectivo - k * dia
    x = math.ceil(x) if rol == "seller" else math.floor(x)
    if isinstance(limite, (int, float)):
        x = max(x, math.ceil(limite)) if rol == "seller" else min(x, math.floor(limite))
    return max(1, x)


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


# ---------- la Duelista por ticks (Duels III y la final): callar no cuesta ----------
#
# Medido en los 83 duelos terminados del 3/10 (datos/duelos-reales-03-10.json), sin una sola excepción:
#     resultado = ganancia × (1 − decay)^rondas            rondas = min(mensajes nuestros, mensajes del rival)
#     ganancia  = precio − coste + peso × días (vendiendo) · valor − precio − peso × días (comprando)
# Lo que sale de ahí:
#   1. Callar no encoge el trato. Si el rival manda diez ofertas y nosotros una, cuenta UNA ronda. Aceptar su oferta
#      sin haber escrito nada no descuenta nada (duelos 5810 y 6088: 45,4 y 60,2 enteros).
#   2. Repetir la misma oferta cada tick era lo que quemaba los puntos: "122?" quince veces mientras el rival subía
#      solo (duelo 2440: 16 rondas, 10 P convertidos en 3,7). Nuestra oferta sigue en pie sin repetirla.
#   3. Muchos rivales caminan solos hacia nosotros tick a tick y luego se plantan. Mientras caminan, se les deja venir.
#   4. El juego deja UNA aceptación por equipo y tick: con cuatro duelos que acaban a la vez no se puede esperar todos
#      al último tick. El 3/10 cinco duelos llegaron al plazo con una oferta del rival dentro del límite y sin aceptar
#      (71 P en la mesa); dos de ellos acababan en el mismo tick. Cada duelo tiene su turno y un tick de reserva.
#
# Qué hace, en orden:
#   a. Oferta del rival dentro de nuestro límite: aceptar si el tiempo se acaba, si ya nos da lo que pedíamos o si
#      el rival se ha plantado. Si sigue mejorando, callar y esperar (no cuesta). Plantado y con margen de tiempo,
#      UNA contraoferta si compensa: cambiar el día cuando a nosotros nos importa claramente más, o pedir algo más
#      cuando lo que ofrece es poco.
#   b. Rival mudo: escuchar un tick y después bajar poco a poco cada tick (gratis: sin mensajes suyos no hay rondas),
#      alternando el día cuando no está claro a quién le importa más.
#   c. Rival que habla pero fuera de nuestro límite: si viene solo y llega a tiempo, callar. Si no, hablar pocas
#      veces y en pasos grandes; al final, bajar cada tick hasta el margen mínimo.
# Nunca ofrece ni acepta fuera del límite (todo va en precio efectivo: precio + k × días).

def _aj(p, nombre, defecto):
    """Un ajuste de parametros.json; si falta (archivo antiguo), el valor por defecto."""
    v = p.get(nombre)
    return defecto if v is None else v


def _margenes(rol, lim, p):
    """(margen inicial, margen mínimo): lo que pedimos de más sobre nuestro límite al abrir y al final."""
    ancla = lim * p["duelo.apertura_vendedor"] if rol == "seller" else lim * p["duelo.apertura_comprador"]
    m0 = max(abs(ancla - lim), 2.0)
    mmin = max(float(_aj(p, "duelo.margen_minimo", 1.0)), p["duelo.cuota_minima"] * m0)
    return m0, min(mmin, m0)


def peso_rival(rol, x, p):
    """Cuánto le importa cada día al rival. Si ha cambiado de día entre dos ofertas, lo que movió el precio por día;
    si no, lo habitual en los duelos reales (vendedores ≈ 2,6 por día; compradores ≈ 3,6)."""
    estimados = []
    riv = x.get("riv") or []
    for a, b in zip(riv, riv[1:]):
        if all(isinstance(m[3], (int, float)) for m in (a, b)) and a[3] != b[3]:
            estimados.append(abs((b[2] - a[2]) / (b[3] - a[3])))
    if estimados:
        estimados.sort()
        return min(12.0, max(0.3, estimados[len(estimados) // 2]))
    return float(_aj(p, "duelo.peso_rival_comprador", 3.6) if rol == "seller" else _aj(p, "duelo.peso_rival_vendedor", 2.6))


def _dia(rol, lim, x, p, margen, n_riv):
    """El día que acompaña a una oferta nuestra de `margen`. El día se le da a quien probablemente le importa más
    (el precio compensa: nuestra ganancia es la misma). Vendiendo, nunca un día que obligue a escribir un precio
    por debajo del coste."""
    k = x.get("k")
    if not x.get("dos") or not k:
        return None
    w, wr = abs(k), peso_rival(rol, x, p)
    mio, suyo = (10, 0) if rol == "seller" else (0, 10)
    if w >= 1.25 * wr:
        dia = mio
    elif w <= 0.8 * wr:
        dia = suyo
    elif n_riv == 0:                                        # rival mudo: los mensajes son gratis, se enseñan los dos
        dia = mio if int(x.get("edad") or 0) % 2 else suyo
    elif int(_aj(p, "duelo.dia_en_duda", 0)):               # en duda: pedimos nuestro día
        dia = mio
    else:                                                   # en duda: el día que propone él
        vig = x.get("vigente")
        dia = vig[2] if vig and isinstance(vig[2], (int, float)) else suyo
    return _dia_posible(rol, lim, w, margen, dia)


def _dia_posible(rol, lim, w, margen, dia):
    """El día más cercano a `dia` que deja escribir un precio válido: vendiendo, precio escrito ≥ coste
    (margen − w × día ≥ 0); comprando, precio escrito ≥ 1."""
    if rol == "seller":
        dia = min(dia, int(max(0.0, margen) // w))
    else:
        dia = min(dia, int(max(0.0, lim - margen - 1) // w))
    return int(max(0, min(10, dia)))


def decidir_vivo(st, p):
    """La decisión de un tick. st["x"] lo arma duelos.py con el duelo tal como lo manda el juego:
        tick, quedan (ticks hasta el plazo), edad (ticks desde que lo vimos), turno (orden de cierre entre los duelos
        que acaban a la vez), n_nos / n_riv (mensajes de cada lado), nos / riv = [[tick, efectivo, precio, días], ...],
        vigente = [efectivo, precio, días] de la oferta del rival que se aceptaría ahora, dos (¿hay día?), k.
    Devuelve (acción, precio efectivo, día o None, motivo)."""
    rol, lim, x = st["rol"], float(st["limite"]), st["x"]
    s = 1 if rol == "seller" else -1
    tick = x.get("tick") if isinstance(x.get("tick"), (int, float)) else 0
    edad = max(0, int(x.get("edad") or 0))
    quedan = x.get("quedan")
    if not isinstance(quedan, (int, float)) or isinstance(quedan, bool):
        quedan = max(1, int(p["duelo.rondas"]) - edad)
    cierre = int(_aj(p, "duelo.cierre_ticks", 2)) + int(x.get("turno") or 0)
    pac = int(_aj(p, "duelo.paciencia", 2))
    escuchar = int(_aj(p, "duelo.escuchar_ticks", 1))
    m0, mmin = _margenes(rol, lim, p)
    riv, nos = x.get("riv") or [], x.get("nos") or []
    n_o = int(x["n_nos"]) if isinstance(x.get("n_nos"), (int, float)) else len(nos)
    n_r = int(x["n_riv"]) if isinstance(x.get("n_riv"), (int, float)) else len(riv)
    vig = x.get("vigente")
    g_su = ganancia(rol, lim, vig[0]) if vig and isinstance(vig[0], (int, float)) else None
    g_mio = ganancia(rol, lim, nos[-1][1]) if nos else None
    t_mia = nos[-1][0] if nos else None
    con_dia = bool(x.get("dos") and x.get("k"))

    # cómo se mueve el rival, medido en lo que nos da a nosotros
    mejor, t_mej = None, None
    for m in riv:
        g = ganancia(rol, lim, m[1])
        if mejor is None or g > mejor + 0.5:
            mejor, t_mej = g, m[0]
    sin_mejora = tick - t_mej if t_mej is not None else None
    retrocede = g_su is not None and mejor is not None and g_su < mejor - 0.5
    parado = sin_mejora is None or sin_mejora > pac or retrocede
    paso = 0.0
    if len(riv) >= 2 and riv[-1][0] > riv[0][0]:
        g1 = ganancia(rol, lim, riv[-1][1])
        paso = (g1 - ganancia(rol, lim, riv[0][1])) / (riv[-1][0] - riv[0][0])
        if paso > 0 and riv[-1][0] > riv[-2][0]:            # si frena, cuenta el último paso
            paso = min(paso, (g1 - ganancia(rol, lim, riv[-2][1])) / (riv[-1][0] - riv[-2][0]))

    # ¿se mueve solo? Mejoró alguna vez sin que hubiéramos escrito nada entre dos ofertas suyas
    autonomo = any(ganancia(rol, lim, b_[1]) > ganancia(rol, lim, a_[1]) + 0.5
                   and not any(a_[0] <= m[0] <= b_[0] for m in nos) for a_, b_ in zip(riv, riv[1:]))

    # lo que pediríamos ahora: baja con el tiempo, del ancla al margen mínimo, y llega abajo cuando toca cerrar
    largo = max(1, edad + quedan - cierre - escuchar)
    frac = min(1.0, max(0.0, (edad - escuchar) / largo))
    f = frac ** (1 / max(0.1, p["duelo.dureza_beta"]))
    margen = m0 * (1 - f) + mmin * f

    def oferta(m, motivo, dia=None):
        m = max(m, mmin)
        e = lim + s * m
        e = math.ceil(e) if s > 0 else max(1, math.floor(e))
        if ganancia(rol, lim, e) <= 0:                      # límite tan bajo que no cabe pedir nada: no se ofrece
            return ("esperar", None, None, "no cabe una oferta con ganancia dentro de nuestro límite")
        if con_dia:
            dia = _dia(rol, lim, x, p, m, n_r) if dia is None else _dia_posible(rol, lim, abs(x["k"]), m, dia)
        else:
            dia = None
        if nos and abs(nos[-1][1] - e) < 0.5 and (dia is None or nos[-1][3] == dia):
            return ("esperar", None, None, "nuestra oferta sigue en pie: repetirla no aporta y puede costar una ronda")
        return ("ofrecer", e, dia, motivo)

    # ---------- a. hay una oferta suya dentro de nuestro límite ----------
    if g_su is not None and g_su > 0:
        if quedan <= cierre:
            if (int(_aj(p, "duelo.apurar", 1)) and not int(x.get("turno") or 0) and quedan == cierre and quedan >= 2
                    and sin_mejora is not None and sin_mejora <= 1 and not retrocede):
                return ("esperar", None, None, f"su oferta (+{g_su:.0f}) ha mejorado en el último tick y es el último "
                                               f"duelo en cerrar: un tick más, y se acepta")
            return ("aceptar", vig[0], None, f"se acaba el tiempo (quedan {quedan} ticks): +{g_su:.0f} es mejor que cero")
        if g_mio is not None and g_su >= g_mio:
            return ("aceptar", vig[0], None, f"nos da +{g_su:.0f}, al menos lo que pedíamos (+{g_mio:.0f})")
        if g_su >= float(_aj(p, "duelo.aceptar_ya_desde", 1.0)) * m0:
            return ("aceptar", vig[0], None, f"nos da +{g_su:.0f}, más de lo que pediríamos al abrir (+{m0:.0f}): se coge ya")
        reactivo = (not autonomo and len(riv) >= 2 and t_mia is not None and t_mej is not None and t_mej >= t_mia
                    and not retrocede)
        # el día: si a nosotros nos importa claramente más, UNA vez pedimos nuestro día compensándole en precio.
        # Solo cuando ya no está mejorando por su cuenta (plantado, o de los que solo se mueven si nos movemos).
        if (con_dia and isinstance(vig[2], (int, float)) and int(_aj(p, "duelo.cambiar_dia", 1)) and (parado or reactivo)
                and quedan > cierre + 2):
            w, wr = abs(x["k"]), peso_rival(rol, x, p)
            mio = 10 if rol == "seller" else 0
            gana = (w - wr) * abs(mio - vig[2])
            # una contraoferta puede costar una ronda (−10 % de todo): solo si el día vale al menos la mitad de lo
            # que ya tenemos en la mesa (con una probabilidad de que acepte de 1 entre 4 ya sale a cuenta)
            if w > 1.1 * wr and gana >= max(8.0, 0.5 * g_su) and not any(m[3] == mio for m in nos):
                return oferta(g_su + gana, f"el día nos importa más ({w:.1f} por día frente a ~{wr:.1f}): "
                                            f"le compensamos en precio y pedimos nuestro día", dia=mio)
        # un rival que solo se mueve cuando nos movemos: esperar no trae nada; o seguimos el ojo por ojo, o cerramos
        if reactivo and tick > t_mia:
            antes = [ganancia(rol, lim, m[1]) for m in riv if m[0] < t_mia]
            cedio = mejor - max(antes) if antes else 0.0
            if (cedio > 0.2 * g_su + 1 and min(n_o, n_r) < int(_aj(p, "duelo.rondas_max", 4)) and quedan > cierre + 1
                    and g_mio is not None and g_mio > g_su + 2):
                m = max(g_su + 1, g_mio - max(1.0, float(_aj(p, "duelo.ojo_por_ojo", 0.3)) * cedio))
                return oferta(m, f"responde a cada oferta nuestra (acaba de ceder {cedio:.0f}): otro paso pequeño, "
                                 f"pedimos margen {m:.0f}")
            return ("aceptar", vig[0], None, f"ya no cede lo bastante para pagar otra ronda: cerrar en +{g_su:.0f}")
        if not parado:
            return ("esperar", None, None, f"su oferta ya vale +{g_su:.0f} y sigue mejorando: callar no cuesta rondas")
        contras = sum(1 for m in nos if riv and m[0] >= riv[0][0])
        if contras < int(_aj(p, "duelo.contras_max", 1)) and quedan > cierre + pac + 1:
            if g_su < float(_aj(p, "duelo.contra_si_menos_de", 0.15)) * m0 and margen > 1.2 * g_su + 1:
                return oferta(g_su + 0.5 * (margen - g_su), f"se ha plantado en +{g_su:.0f}, que es poco: una contraoferta",
                              dia=vig[2] if con_dia and isinstance(vig[2], (int, float)) else None)
        if int(_aj(p, "duelo.cerrar_al_plantarse", 0)):
            return ("aceptar", vig[0], None, f"el rival se ha plantado en +{g_su:.0f}: cerrar ya, sin gastar más rondas")
        # Plantado no es terminado: el 3/10 varios rivales lentos pararon unos ticks y siguieron bajando (duelos 277,
        # 2309, 2334). Su oferta sigue en pie y esperar callados no descuenta nada: se acepta cuando llega el turno.
        return ("esperar", None, None, f"su oferta (+{g_su:.0f}) sigue en pie y callar no cuesta: se acepta a "
                                       f"{cierre} ticks del final, o antes si mejora lo que pedimos")

    # ---------- b. el rival no ha escrito nada ----------
    if n_r == 0:
        if edad < escuchar and not nos:
            return ("esperar", None, None, "primer tick: escuchamos (aceptar su oferta sin haber hablado no encoge el trato)")
        return oferta(margen, f"rival mudo: bajamos poco a poco, gratis (margen {margen:.0f})")

    # ---------- c. el rival habla, pero su oferta no nos sirve ----------
    if len(riv) <= 1 and sin_mejora is not None and sin_mejora <= pac and not nos:
        return ("esperar", None, None, "acaba de abrir: miramos si camina solo antes de hablar")
    if g_su is not None and autonomo and not parado and paso > 0 and (1 - g_su) / paso <= quedan - cierre - 1:
        return ("esperar", None, None, f"viene solo hacia nosotros ({paso:+.1f} por tick) y llega a tiempo: callar no cuesta")
    remate = quedan <= cierre + int(_aj(p, "duelo.ticks_remate", 3))
    if autonomo and nos and not remate:
        return ("esperar", None, None, "se mueve solo y nuestra oferta ya está en pie: no gastamos rondas en contestarle")
    respondio = (len(riv) >= 2 and t_mia is not None and t_mej is not None and t_mej >= t_mia and not retrocede
                 and not autonomo)
    toca = t_mia is None or remate or (tick - t_mia) > pac or (respondio and tick > t_mia)
    if min(n_o, n_r) >= int(_aj(p, "duelo.rondas_max", 4)) and not remate:
        return ("esperar", None, None, "ya hemos gastado las rondas previstas: esperamos al remate")
    if not toca:
        return ("esperar", None, None, "esperamos su respuesta a nuestra oferta (no repetimos)")
    if respondio and not remate and g_mio is not None:
        # ojo por ojo con descuento: se mueve cuando nos movemos, así que cedemos solo una parte de lo que él cedió
        antes = [ganancia(rol, lim, m[1]) for m in riv if m[0] < t_mia]
        cedio = mejor - max(antes) if antes else 0.0
        m = max(margen, g_mio - max(1.0, float(_aj(p, "duelo.ojo_por_ojo", 0.3)) * max(0.0, cedio)))
        return oferta(m, f"responde a nuestras ofertas (cedió {cedio:.0f}): cedemos una parte y pedimos margen {m:.0f}")
    return oferta(margen, ("remate: " if remate else "") + f"pedimos margen {margen:.0f} sobre nuestro límite")


def dia_oferta(st, p):
    """El día que acompaña a la oferta que decidir() acaba de devolver (None sin estado por ticks o sin día)."""
    if not isinstance(st.get("x"), dict):
        return None
    return decidir_vivo(st, p)[2]
