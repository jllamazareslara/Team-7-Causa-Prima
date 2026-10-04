"""El guardia: la última puerta antes de `accept`. Es la ÚNICA función que puede devolver "firma".

No recibe texto: solo la oferta estructurada tal como la da el juego y nuestro estado.
Seis comprobaciones; si falla una, no se firma. Nadie tiene que aprobar: si pasa las seis, firma solo.

    1. STOP                      alguien ha parado el sistema
    2. una firma por tick        por categoría: el juego deja una aceptación de tienda/El Rastro por tick Y, aparte,
                                 una de duelo por tick — tienen cupos independientes (confirmado por Causa Prima:
                                 "duel messages and accepts have their own limits: they never block your trading")
    3. estructura entendida      un campo desconocido en la oferta = no
    4. la oferta no ha cambiado  la oferta del juego es la que el agente miró: las mismas cartas en cada lado (por su
                                 código, también "card:X") y el mismo dinero del mismo lado. Vale para El Rastro y para
                                 los vendedores (un vendedor que habla de RET-09 y ofrece RET-08 no se firma)
    5. buen negocio              mirando el valor de las cartas, sin romper nada: reserva de efectivo intacta,
                                 categoría no apagada, y dentro del tope por trato cuando la caja está justa
    6. según el juego            el buen negocio repetido con el your_value del juego (/api/me, /api/me/value)

Buen negocio (ajustes en parametros.json, decisión del equipo):
    comprando   neto ≥ guardia.margen_compra × valor de las cartas que recibimos   (0,10: pagar ≤ 90 % del valor)
    vendiendo   neto ≥ guardia.margen_venta × valor de las cartas que damos        (0,10: cobrar ≥ valor + 10 %)
    protegida   solo sale si lo recibido, sin comisión, ≥ guardia.protegida_factor × lo que perdemos al darla (1,5)
"""
from . import contable
from . import valor as V

BIENES_CONOCIDOS = {"cash", "assets", "cards", "types"}


def estructura_valida(oferta):
    """¿Entendemos exactamente qué se da y qué se pide? Un campo desconocido = no."""
    for lado in ("give", "want"):
        d = oferta.get(lado)
        if not isinstance(d, dict):
            return False
        if set(d) - BIENES_CONOCIDOS:
            return False
        if "cash" in d and (not isinstance(d["cash"], (int, float)) or d["cash"] < 0):
            return False
    return True


def _refs(lado):
    """Las cartas de un lado de la oferta del juego, por su código y ordenadas. None si trae algo que no es una carta
    que sepamos leer (assets sin ref, types que no son "card:X")."""
    refs = []
    for a in lado.get("assets") or []:
        if not (isinstance(a, dict) and isinstance(a.get("ref"), str)):
            return None
        refs.append(a["ref"])
    for t in lado.get("types") or []:
        if not (isinstance(t, str) and t.startswith("card:")):
            return None
        refs.append(t.split(":", 1)[1])
    for r in lado.get("cards") or []:
        if not isinstance(r, str):
            return None
        refs.append(r)
    return sorted(refs)


def coincide(propuesta, oferta_juego):
    """4. ¿La oferta del juego es lo que el agente cree que firma? None = sí; si no, el motivo.
    give = lo que nos dan (recibo), want = lo que nos piden (entrego): cartas y dinero, cada uno en su lado."""
    give, want = oferta_juego.get("give") or {}, oferta_juego.get("want") or {}
    rec, ent = propuesta.get("recibo") or {}, propuesta.get("entrego") or {}
    for que, juego, cree in (("nos da", give, rec), ("nos pide", want, ent)):
        cartas = _refs(juego)
        if cartas is None:
            return f"la oferta del juego {que} algo que no sabemos leer"
        if cartas != sorted(cree.get("cartas") or []):
            return (f"la oferta cambió: el juego {que} {', '.join(cartas) or 'ninguna carta'}, "
                    f"el agente creía {', '.join(cree.get('cartas') or []) or 'ninguna carta'}")
        dinero, creia = juego.get("cash") or 0, cree.get("primas") or 0
        if abs(dinero - creia) > 0.5:
            return f"la oferta cambió: el juego {que} {dinero} P, el agente creía {creia} P"
    return None


def exigido_por_valor(ev, p):
    """Lo mínimo que tiene que ganar un trato para ser buen negocio, según el valor de las cartas que se mueven."""
    return p["guardia.margen_compra"] * ev["cartas_recibo"] + p["guardia.margen_venta"] * ev["cartas_entrego"]


def segun_el_juego(propuesta, ev, p, sin_margen=False):
    """6. El mismo buen negocio, pero con el your_value que cuenta el juego (/api/me, /api/me/value) en lugar del
    calculado, cuando el juego nos lo ha dicho. Solo para una carta en un sentido. None = no hay pega.
    sin_margen: basta con ganar algo (cartas de una página a completar)."""
    rec, ent = propuesta.get("recibo", {}), propuesta.get("entrego", {})
    rc, ec = rec.get("cartas") or [], ent.get("cartas") or []
    if len(rc) == 1 and not ec and rc[0] in V.VALOR_RECIBIR:
        juego = V.VALOR_RECIBIR[rc[0]]
        neto = juego + (rec.get("primas") or 0) - (ent.get("primas") or 0) - ev["comision"]
        exigido = p["guardia.margen_compra"] * juego
    elif len(ec) == 1 and not rc and ec[0] in V.VALOR_DAR:
        juego = V.VALOR_DAR[ec[0]]
        neto = (rec.get("primas") or 0) - (ent.get("primas") or 0) - ev["comision"] - juego
        exigido = p["guardia.margen_venta"] * juego
    else:
        return None
    if sin_margen:
        exigido = 0
    if neto <= 0 or neto < exigido:
        return f"según el juego no renta lo bastante ({neto:+.1f}, pide {exigido:+.1f}; your_value {juego})"
    return None


def revisar_duelo(ganancia, ya_firmado_este_tick=False, stop=False, forzar=None):
    """Un duelo no mueve efectivo ni cartas: solo importa quedar dentro de nuestro límite (ganancia ≥ 0)."""
    if stop:
        return False, "STOP activado"
    if (forzar or {}).get("duelo") == "apagado":
        return False, "categoría duelo apagada"
    if ya_firmado_este_tick:
        return False, "ya se firmó una oferta en este tick: espera al siguiente"
    if ganancia < 0:
        return False, "duelo fuera del límite"
    return True, f"duelo dentro del límite (+{ganancia:.0f})"


def revisar(propuesta, oferta_juego, cuenta, efectivo, p, ya_firmado_este_tick=False, stop=False, forzar=None,
            tope_por_trato=None, ev=None, para_completar=False, **_):
    """Devuelve (firma: bool, motivo, ficha, estado). estado = "firma" | "espera" | "bloqueo".

    propuesta      = lo que el agente cree que firma (para la calculadora)
    oferta_juego   = la oferta tal como está en el juego ahora mismo; se comprueba que coincide con la propuesta
    forzar         = {categoría: "apagado"} (sale de hoy.json a través del plan del día)
    tope_por_trato = lo máximo que puede comprometer una compra cuando la caja está justa (None = sin tope)
    ev             = la ficha que ya hizo la Contable (contable.ficha); si no llega, se la pide aquí a la Contable
    para_completar = compra de cartas de una página a completar (hoy.json): basta con que renta algo, sin el margen
                     de buen negocio, porque el bono de página llega solo con la última (riesgo aceptado por el equipo)
    """
    if ev is None:
        ev = contable.ficha(propuesta, cuenta, efectivo, p)
    if stop:
        return False, "STOP activado", ev, "bloqueo"
    if ya_firmado_este_tick:
        return False, "ya se firmó una oferta en este tick: espera al siguiente", ev, "espera"
    if oferta_juego is not None:
        if not estructura_valida(oferta_juego):
            return False, "la oferta del juego trae algo que no entendemos", ev, "bloqueo"
        distinta = coincide(propuesta, oferta_juego)
        if distinta:
            return False, distinta, ev, "bloqueo"
    cat = propuesta.get("categoria", propuesta.get("tipo", ""))
    if (forzar or {}).get(cat) == "apagado":
        return False, f"categoría {cat} apagada", ev, "bloqueo"
    protegidas = ev.get("protegidas", [])
    bloqueos = [b for b in ev["bloqueos"] if b not in {f"{r} está protegida" for r in protegidas}]
    if protegidas:
        pide = p["guardia.protegida_factor"] * ev["cartas_entrego"]
        if ev["recibo"] - ev["comision"] < pide:
            bloqueos.insert(0, f"{', '.join(protegidas)} protegida: solo sale por {pide:.0f} P o más")
    if bloqueos:
        return False, "; ".join(bloqueos), ev, "bloqueo"
    if ev["neto"] <= 0:
        return False, f"no renta ({ev['neto']:+.1f})", ev, "bloqueo"
    exigido = 0 if para_completar else exigido_por_valor(ev, p)
    if ev["neto"] < exigido:
        return False, f"no renta lo bastante ({ev['neto']:+.1f}, pide {exigido:+.1f})", ev, "bloqueo"
    no_juego = segun_el_juego(propuesta, ev, p, sin_margen=para_completar)
    if no_juego:
        return False, no_juego, ev, "bloqueo"
    completa = any("PÁGINA COMPLETA" in a for a in ev["avisos"])
    if tope_por_trato is not None and ev["compromete"] > tope_por_trato and not completa:
        return False, f"caja justa: compromete {ev['compromete']:.0f} P, tope {tope_por_trato} P por trato", ev, "bloqueo"
    return True, f"{ev['compromete']:.0f} P, gana {ev['neto']:+.1f}", ev, "firma"
