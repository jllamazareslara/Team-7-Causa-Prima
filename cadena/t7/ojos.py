"""Los Ojos: lo primero de cada tick. Cuentan qué pasa en el mercado y si hay novedades. Solo miran: no deciden nada.

Juntan a tres que antes iban sueltos:
    Vigía       las novedades del juego. `vigia.py` las lee aparte (solo GET) y el director las pasa en lectura["novedades"].
    Observador  el perfil de cada vendedor: con quién ser duro (`perfiles.py` y los ajustes tienda.<vendedor>.*).
                Un vendedor sin perfil propio se trata como "desconocido" (prudente) y se avisa una vez.
    Precios     lo que otros equipos piden y ofrecen en El Rastro (antes lo apuntaba el Cambista).

Entregan la `vista` a la Contable y a los negociadores:
    vista = {"novedades": [...], "perfiles": {vendedor: ajustes}, "nuevos": [vendedores sin perfil propio],
             "mercado": {carta: [precios pedidos]}, "demanda": {carta: [precios ofrecidos]}}
"""
from . import params


def _titulo(n):
    return n.get("titulo") or n.get("title") or str(n) if isinstance(n, dict) else str(n)


def mirar(lectura, mem, p, apunta=None):
    """Mira la lectura del tick y devuelve la vista. Tolera piezas rotas: lo que no se entiende se salta."""
    apunta = apunta or (lambda *_: None)

    novedades = [n for n in (lectura.get("novedades") or []) if n]
    for n in novedades:
        apunta("OJOS", f"novedad: {_titulo(n)}")

    perfiles, nuevos = {}, []
    for c in lectura.get("vendedores") or []:
        quien = c.get("vendedor") if isinstance(c, dict) else None
        if not isinstance(quien, str) or quien in perfiles:
            continue
        perfiles[quien] = params.perfil(p, quien)
        if perfiles[quien]["perfil"] == "desconocido":
            nuevos.append(quien)
            if mem.vistos.get(f"ojos|{quien}") is None:
                mem.vistos[f"ojos|{quien}"] = "desconocido"
                apunta("OJOS", f"{quien}: vendedor sin perfil propio, se le trata con prudencia")

    tablon = lectura.get("tablon")
    if tablon:
        apuntar_mercado(mem.mercado, [o for o in tablon if isinstance(o, dict)], mem.demanda)

    return {"novedades": novedades, "perfiles": perfiles, "nuevos": nuevos,
            "mercado": mem.mercado, "demanda": mem.demanda}


MERCADO_RECUERDA = 12      # precios vistos por carta que guardan los Ojos


def _apunta(d, ref, precio):
    vistos = d.setdefault(ref, [])
    vistos.append(precio)
    del vistos[:-MERCADO_RECUERDA]


def apuntar_mercado(mercado, tablon, demanda=None):
    """Los Ojos apuntan los precios del tablón de El Rastro (los últimos MERCADO_RECUERDA por carta):
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
