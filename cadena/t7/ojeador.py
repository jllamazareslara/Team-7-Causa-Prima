"""El Ojeador: vigila los precios de El Rastro y pasa esos valores al Regateador y al Cambista. Va al lado de la cadena.

Solo mira y apunta, no decide:
    mercado  ← lo que otros equipos PIDEN por una carta (anuncios que venden una carta por efectivo)
    demanda  ← lo que otros equipos OFRECEN por una carta (peticiones que ofrecen efectivo por una carta)
Guarda los últimos MERCADO_RECUERDA precios por carta en la memoria (`mem.mercado`, `mem.demanda`).

    vigilar(lectura, mem)    → {"mercado": ..., "demanda": ...}, después de apuntar el tablón de este tick (si llega)
    precios(vista, carta)    → {"piden": el más barato que piden, "ofrecen": el más alto que ofrecen} (None si no hay)
"""


def vigilar(lectura, mem):
    tablon = lectura.get("tablon")
    if tablon:
        apuntar_mercado(mem.mercado, [o for o in tablon if isinstance(o, dict)], mem.demanda)
    return {"mercado": mem.mercado, "demanda": mem.demanda}


def precios(vista, carta):
    piden, ofrecen = (vista.get("mercado") or {}).get(carta), (vista.get("demanda") or {}).get(carta)
    return {"piden": min(piden) if piden else None, "ofrecen": max(ofrecen) if ofrecen else None}


MERCADO_RECUERDA = 12      # precios vistos por carta que guarda el Ojeador


def _apunta(d, ref, precio):
    vistos = d.setdefault(ref, [])
    vistos.append(precio)
    del vistos[:-MERCADO_RECUERDA]


def apuntar_mercado(mercado, tablon, demanda=None):
    """El Ojeador apunta los precios del tablón de El Rastro (los últimos MERCADO_RECUERDA por carta):
    mercado  ← anuncios que venden UNA carta por efectivo: la lista de la compra espera pagar lo más barato visto
    demanda  ← peticiones que ofrecen efectivo por UNA carta: si otro equipo compite por una carta que queremos,
               nuestra petición pide 1 P más que él (mientras quepa en el tope)"""
    for o in tablon:
        give, want = o.get("give") or {}, o.get("want") or {}
        cartas, pide = give.get("assets") or [], want.get("cards") or []
        if len(cartas) == 1 and not give.get("cash") and not pide and isinstance(want.get("cash"), (int, float))                 and want["cash"] > 0:
            ref = cartas[0].get("ref") if isinstance(cartas[0], dict) else cartas[0]
            if isinstance(ref, str):
                _apunta(mercado, ref, want["cash"])
        elif demanda is not None and len(pide) == 1 and not cartas and isinstance(give.get("cash"), (int, float))                 and give["cash"] > 0 and isinstance(pide[0], str):
            _apunta(demanda, pide[0], give["cash"])
