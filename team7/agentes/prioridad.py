"""Qué operación hacer primero: la que más puntos añade, no la que más tratos hace.

Dos reglas del juego lo deciden todo:
- Con cada vendedor, por nivel y por día, cuentan los TRES mejores tratos (como parte de su rango capturada).
  Un cuarto trato solo suma si supera al peor de esos tres. Y la parte capturada no depende del precio:
  regatear una común de 10 P puntúa igual que una poco común de 25 P → los tres tratos se hacen con lo MÁS BARATO,
  o vendiendo repetidas (no gasta efectivo).
- Con los equipos cuenta todo el valor ganado → no hay techo: cada trato que renta suma.

Los duelos tienen su propio cupo de aceptación por tick, aparte del de la tienda/El Rastro (confirmado por Causa
Prima: "duel messages and accepts have their own limits: they never block your trading"), así que esta prioridad
ordena cada categoría por separado, no una contra otra:

Duelos: el más urgente primero (menos ticks hasta el plazo).
Tienda y equipos, con la única aceptación de esa categoría: 1. oferta final de vendedor que mejora el top 3
2. trato con equipo de más neto  3. trato con vendedor que mejora el top 3.
"""


def mejora_escalera(top3, captura_esperada, nivel=1):
    """Lo que un trato nuevo con ese vendedor añade a su media de los tres mejores (0 si no entra).
    nivel: las reglas dicen que los niveles altos pesan más (sin decir cuánto); se supone proporcional al nivel."""
    peso = nivel if isinstance(nivel, (int, float)) and nivel > 0 else 1
    t = sorted(top3, reverse=True)[:3]
    if len(t) < 3:
        return peso * ((sum(t) + captura_esperada) / 3 - sum(t) / 3)
    return peso * max(0.0, captura_esperada - t[-1]) / 3


def carta_para_escalera(candidatas, efectivo):
    """La operación de vendedor que conviene para la escalera: vender una repetida si se puede (gana efectivo),
    si no, comprar lo más barato que nos falte. candidatas = [{"lado", "ref", "lista", "perdida_o_valor"}]."""
    ventas = [c for c in candidatas if c["lado"] == "venta"]
    if ventas:
        return min(ventas, key=lambda c: c["perdida_o_valor"])
    compras = [c for c in candidatas if c["lado"] == "compra" and c["lista"] <= efectivo]
    return min(compras, key=lambda c: c["lista"]) if compras else None


RANGO = {"duelo": 0, "final_vendedor": 1, "equipo": 2, "vendedor": 3}


def clave(o):
    """El orden en que el Guardia revisa las propuestas de aceptar (la cadena las ordena con esta clave)."""
    return (0 if o.get("urgente") else 1, RANGO.get(o["tipo"], 9), -o.get("mejora", 0), -o.get("neto", 0))


def elegir_aceptacion(cola):
    """cola = [{"tipo": "duelo"|"final_vendedor"|"equipo"|"vendedor", "urgente": bool, "mejora": x, "neto": y, ...}]
    Devuelve la que se lleva la aceptación de este tick."""
    return min(cola, key=clave) if cola else None
