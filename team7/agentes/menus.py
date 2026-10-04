"""Los menús de los vendedores, sacados de lo que da el juego en dealers().

La cadena solo abre conversaciones con lo que diga menus.json = {vendedor: {"vende": {ref: precio de lista},
"compra": {ref: lo que ofrece de entrada}}}. Escribirlo a mano con cada vendedor nuevo es lento; esto lo propone solo.

No sabemos la forma exacta del menú del juego (nadie la ha visto todavía), así que se aceptan las formas razonables y
TODO lo que no se entiende sale en `dudas`, sin adivinar. Lo que sale de aquí es un BORRADOR: lo mira una persona
(revisar.py lo escribe en menus.borrador.json) antes de usarlo.

Sin red y sin azar.
"""
import re

from . import valor as V

CARTA = re.compile(r"^[A-Z]{2,5}-\d{1,3}$")
LADO_VENDE = ("sells", "sell", "selling", "for_sale", "vende")
LADO_COMPRA = ("buys", "buy", "buying", "wants", "compra")
CLAVES_PRECIO = ("price", "list", "list_price", "ask", "bid", "cash", "book")
CLAVES_REF = ("card", "ref", "id")


def _precio(v):
    if isinstance(v, dict):
        v = next((v[k] for k in CLAVES_PRECIO if isinstance(v.get(k), (int, float))), None)
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else None


def _barrios(x):
    """None = todos los barrios (p.ej. sets: "released"); si no, el conjunto de barrios, venga uno o una lista."""
    if x is None or x == "released":
        return None
    return {x} if isinstance(x, str) else set(x) if isinstance(x, list) else None


def _de_rareza(rareza, barrios, lado, cuenta):
    """Las cartas concretas de una rareza: vendiendo él, las del catálogo; comprando él, las que tenemos nosotros."""
    refs = cuenta if lado == "compra" else V.RAREZAS
    return sorted(r for r in refs if V.rareza(r) == rareza and (barrios is None or V.barrio(r) in barrios)
                  and (lado != "compra" or cuenta.get(r, 0) > 0))


def _lado(x, lado, cuenta, dudas, quien):
    """{ref: precio} de un lado del menú, venga como diccionario o como lista."""
    out = {}

    def pon(ref, rareza, barrio, precio, origen):
        if precio is None:
            dudas.append(f"{quien} · {lado}: sin precio en {origen!r}")
        elif isinstance(ref, str) and CARTA.match(ref):
            out[ref] = precio
        elif rareza in V.BASE:
            refs = _de_rareza(rareza, barrio, lado, cuenta)
            if not refs and lado == "vende":
                dudas.append(f"{quien} · vende {rareza}: sin catálogo no sabemos qué cartas son")
            for r in refs:
                out.setdefault(r, precio)
        else:
            dudas.append(f"{quien} · {lado}: no es una carta ni una rareza: {origen!r}")

    if isinstance(x, dict):
        for k, v in x.items():
            if k in ("cards", "rarities", "items") and isinstance(v, (dict, list)):
                out.update(_lado(v, lado, cuenta, dudas, quien))
            elif k in ("packs", "pack"):
                continue                                         # los sobres no van en el menú
            else:
                pon(k, k, None, _precio(v), {k: v})
    elif isinstance(x, list):
        for it in x:
            if not isinstance(it, dict):
                dudas.append(f"{quien} · {lado}: elemento que no se entiende: {it!r}")
                continue
            if it.get("kind") == "pack" or "pack" in it:
                continue
            ref = next((it[k] for k in CLAVES_REF if isinstance(it.get(k), str)), None)
            pon(ref, it.get("rarity"), _barrios(it.get("sets", it.get("set"))), _precio(it), it)
    elif x is not None:
        dudas.append(f"{quien} · {lado}: forma que no se entiende: {x!r}")
    return out


def del_juego(vendedores, cuenta=None):
    """vendedores = lo que devuelve dealers() (o su lista). Devuelve (menus, dudas).

    menus solo trae vendedores de los que se entendió algo. dudas = textos para una persona: lo que no se entendió."""
    cuenta = cuenta or {}
    lista = (vendedores.get("dealers") or vendedores.get("in_play") or vendedores.get("personas") or []) if isinstance(vendedores, dict) else vendedores
    menus, dudas = {}, []
    for d in lista if isinstance(lista, list) else []:
        if not isinstance(d, dict) or d.get("id") is None:
            dudas.append(f"vendedor que no se entiende: {d!r}")
            continue
        quien, menu = str(d["id"]), d.get("menu")
        if menu is None:
            dudas.append(f"{quien}: sin menú (anunciado, o todavía no abierto para nosotros)")
            continue
        vende, compra = {}, {}
        if isinstance(menu, dict):
            for k, v in menu.items():
                if k in LADO_VENDE:
                    vende.update(_lado(v, "vende", cuenta, dudas, quien))
                elif k in LADO_COMPRA:
                    compra.update(_lado(v, "compra", cuenta, dudas, quien))
                else:
                    dudas.append(f"{quien}: parte del menú que no se entiende: {k!r}")
        elif isinstance(menu, list):
            for it in menu:
                lado = str(it.get("side", it.get("action", ""))).lower() if isinstance(it, dict) else ""
                if lado in LADO_VENDE:
                    vende.update(_lado([it], "vende", cuenta, dudas, quien))
                elif lado in LADO_COMPRA:
                    compra.update(_lado([it], "compra", cuenta, dudas, quien))
                else:
                    dudas.append(f"{quien}: línea del menú sin lado (vende o compra): {it!r}")
        else:
            dudas.append(f"{quien}: menú con una forma que no se entiende")
        if vende or compra:
            menus[quien] = {"vende": vende, "compra": compra}
    return menus, dudas
