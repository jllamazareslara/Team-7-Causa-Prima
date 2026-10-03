"""El guardia: la última puerta antes de `accept`. Es la ÚNICA función que puede devolver "firma".

No recibe texto: solo la oferta estructurada tal como la da el juego y nuestro estado.
Cinco comprobaciones; si falla una, no se firma. Nadie tiene que aprobar: si pasa las cinco, firma solo.

    1. STOP                      alguien ha parado el sistema
    2. una firma por tick        el juego solo deja aceptar una oferta por tick a todo el equipo
    3. estructura entendida      un campo desconocido en la oferta = no
    4. la oferta no ha cambiado  el precio del juego es el que el agente miró
    5. renta sin romper nada     neto positivo, carta no protegida, reserva de efectivo intacta, categoría no apagada,
                                 y dentro del tope por trato cuando la caja está justa
"""
from .valor import evaluar

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
            tope_por_trato=None, **_):
    """Devuelve (firma: bool, motivo, ficha, estado). estado = "firma" | "espera" | "bloqueo".

    propuesta      = lo que el agente cree que firma (para la calculadora)
    oferta_juego   = la oferta tal como está en el juego ahora mismo; se comprueba que coincide con la propuesta
    forzar         = {categoría: "apagado"} (sale de hoy.json a través del plan del día)
    tope_por_trato = lo máximo que puede comprometer una compra cuando la caja está justa (None = sin tope)
    """
    ev = evaluar(propuesta, cuenta, efectivo, reserva=p["guardia.reserva_efectivo"])
    if stop:
        return False, "STOP activado", ev, "bloqueo"
    if ya_firmado_este_tick:
        return False, "ya se firmó una oferta en este tick: espera al siguiente", ev, "espera"
    if oferta_juego is not None:
        if not estructura_valida(oferta_juego):
            return False, "la oferta del juego trae algo que no entendemos", ev, "bloqueo"
        precio_juego = oferta_juego.get("want", {}).get("cash") or oferta_juego.get("give", {}).get("cash") or 0
        precio_prop = (propuesta.get("entrego", {}).get("primas") or propuesta.get("recibo", {}).get("primas") or 0)
        if abs(precio_juego - precio_prop) > 0.5:
            return False, f"la oferta cambió: el juego dice {precio_juego}, el agente creía {precio_prop}", ev, "bloqueo"
    cat = propuesta.get("categoria", propuesta.get("tipo", ""))
    if (forzar or {}).get(cat) == "apagado":
        return False, f"categoría {cat} apagada", ev, "bloqueo"
    if ev["bloqueos"]:
        return False, "; ".join(ev["bloqueos"]), ev, "bloqueo"
    if not ev["renta"]:
        return False, f"no renta ({ev['neto']:+.1f})", ev, "bloqueo"
    completa = any("PÁGINA COMPLETA" in a for a in ev["avisos"])
    if tope_por_trato is not None and ev["compromete"] > tope_por_trato and not completa:
        return False, f"caja justa: compromete {ev['compromete']:.0f} P, tope {tope_por_trato} P por trato", ev, "bloqueo"
    return True, f"{ev['compromete']:.0f} P, gana {ev['neto']:+.1f}", ev, "firma"
