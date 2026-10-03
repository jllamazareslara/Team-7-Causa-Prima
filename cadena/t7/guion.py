"""El Guion: lo que va a pasar en el juego y la jugada preparada para cada cosa, ANTES de que pase.

Sin red y sin azar. Lee el calendario del juego (`GET /api/schedule`, o un archivo guardado) y devuelve:

    eventos(calendario)                → la lista ordenada [{h, accion, nota, params, wall}]
    jugada(evento)                     → la jugada preparada: aviso (horas antes), qué hacer antes, durante, y
                                         lo que se propone poner en hoy.json
    fiebres(eventos)                   → ventanas en que un vendedor paga de más por un barrio
    bloqueadas(cuenta, eventos, h)     → cartas que NO se venden ahora porque viene una fiebre que las paga mejor
    venta_fiebre(cuenta, fiebre)       → qué copias venderle al vendedor en la fiebre, con el precio mínimo
    ahora(eventos, h)                  → lo que toca preparar ya (dentro del aviso de cada jugada) y lo que está activo
    sin_anunciar(tipo)                 → jugada por defecto para un nivel nuevo que aún no conocemos
    linea_de_tiempo(eventos, reloj)    → el texto para la pantalla

    python -m t7.guion datos/calendario-03-10.json --ahora 3.825 --hora 10:10     (desde noche-03-10, sin red)

Reglas fijas de la pantalla grande (pistas del 3/10): un trato por encima de nuestro valor resta puntos; un duelo
sin respuesta da 0 a los dos; cada ronda de duelo encoge el pastel; el volumen no puntúa; repetir precio no es un paso.
"""
import argparse
import datetime as dt
import json
import re
import sys

from . import valor as V

BARRIOS = {"lavapiés": "LAV", "lavapies": "LAV", "malasaña": "MAL", "malasana": "MAL", "la latina": "LAT",
           "latina": "LAT", "salamanca": "SAL", "el retiro": "RET", "retiro": "RET", "chamberí": "CHA", "chamberi": "CHA"}
FIEBRE = re.compile(r"pays (?P<pct>\d+(?:[.,]\d+)?) ?% over book for (?P<barrio>[^\d,.;]+?)"
                    r"(?: until (?P<hasta>\d{1,2}:\d{2}))?\s*$", re.I)
FIN_FIEBRE = ("breaks", "ends", "over", "back to normal")


def _codigo_barrio(texto):
    t = (texto or "").strip().lower()
    return BARRIOS.get(t) or (t.upper() if len(t) == 3 else None)


def eventos(calendario):
    """Acepta la respuesta de /api/schedule ({"upcoming": [...]}) o directamente la lista."""
    lista = calendario.get("upcoming", []) if isinstance(calendario, dict) else calendario or []
    out = []
    for e in lista:
        if not isinstance(e, dict) or not isinstance(e.get("at_hours"), (int, float)):
            continue
        out.append({"h": float(e["at_hours"]), "accion": str(e.get("action") or ""), "nota": str(e.get("note") or ""),
                    "params": e.get("params") if isinstance(e.get("params"), dict) else {}, "wall": e.get("wall")})
    return sorted(out, key=lambda e: e["h"])


def ahora_h(calendario):
    return calendario.get("now_hours") if isinstance(calendario, dict) else None


# ── la hora de pared ──────────────────────────────────────────────────────────────────────────────────────────

def _wall(e):
    try:
        return dt.datetime.fromisoformat(e["wall"])
    except (TypeError, ValueError, KeyError):
        return None


def hora(h, evs, reloj=None):
    """Hora de Madrid aproximada de la hora de juego h. reloj = (h_ahora, "HH:MM") la ancla al día de hoy.
    Las horas de juego solo corren con las puertas abiertas: tras un "day_opens" con hora se ancla ahí."""
    abre = [e for e in evs if e["accion"] == "day_opens" and _wall(e) and e["h"] <= h]
    if abre:
        a = max(abre, key=lambda e: e["h"])
        return _wall(a) + dt.timedelta(hours=h - a["h"])
    if reloj:
        h0, hhmm = reloj
        base = dt.datetime.combine(dt.date.today(), dt.time(*map(int, hhmm.split(":"))))
        return base + dt.timedelta(hours=h - h0)
    cierra = [e for e in evs if e["accion"] == "day_closes" and _wall(e) and e["h"] >= h]
    if cierra:
        c = min(cierra, key=lambda e: e["h"])
        return _wall(c) - dt.timedelta(hours=c["h"] - h)
    return None


def _hhmm(t):
    return "??:??" if t is None else t.strftime("%a %H:%M").replace("Sat", "sáb").replace("Sun", "dom")


# ── las jugadas preparadas ────────────────────────────────────────────────────────────────────────────────────

def _j(clave, titulo, aviso_h, antes, durante=(), hoy=None):
    return {"clave": clave, "titulo": titulo, "aviso_h": aviso_h, "antes": list(antes), "durante": list(durante),
            "hoy": hoy or {}}


def _fiebre_de(e):
    m = FIEBRE.search(e["nota"])
    if not m:
        return None
    quien = e["params"].get("id") or e["nota"][:m.start()].split(":")[-1].strip() or None   # sin params: el nombre de la nota
    return {"vendedor": quien, "barrio": _codigo_barrio(m.group("barrio")),
            "pct": float(m.group("pct").replace(",", ".")), "hasta": m.group("hasta"), "desde_h": e["h"]}


def jugada(e):
    a, p, nota = e["accion"], e["params"], e["nota"].lower()
    if a == "duels":
        dos = "days" in (p.get("issues") or []) or "day" in nota
        hoy = {"duelo": {"descuento_ronda": round(1 - p["decay"], 2)}} if isinstance(p.get("decay"), (int, float)) else {}
        return _j("duelos", p.get("name") or e["nota"], 0.5,
                  ["Agente de duelos ENCENDIDO 10 min antes: un duelo sin respuesta = 0 para los dos.",
                   f"El pastel pierde un {p.get('decay', '?')} por ronda: abrir con una oferta que el otro pueda aceptar y cerrar pronto.",
                   "No abrir regateos nuevos con vendedores 2-3 ticks antes: el duelo se lleva la aceptación del tick."]
                  + (["Dos temas (precio + día 0-10): mandar siempre `days`; ceder el día que nos importa poco a cambio de precio."]
                     if dos else []),
                  ["Mirar el primer duelo en runs/crudo.jsonl y corregir hoy.json → duelo si las rondas no cuadran."], hoy)
    if a == "bench":
        duro = "hard" in nota
        return _j("market_test", "Market Test duro" if duro else "Market Test", 0.1,
                  ["Cuenta el mejor mercado abierto durante la sesión: el puesto gratuito da ya la mitad.",
                   "No cerrar ni cambiar de mercado justo antes: la ronda promedia las sesiones."]
                  + (["Traders más firmes e impacientes: si hay broker propio, emparejar antes (en el tick 1-4), no esperar."]
                     if duro else []))
    if a == "persona_opens":
        quien = p.get("persona") or "?"
        return _j("vendedor_abre", f"{quien} abre para todos", 0.5,
                  [f"`python revisar.py` y luego `--menus`: el menú de {quien} en menus.json antes de que abra.",
                   f"Elegir 3 cartas que {quien} vende y que nos valen MÁS que su precio (GET /api/me/value).",
                   "Los niveles altos pesan más en la escalera: sus 3 tratos van antes que más tratos con Abuela."],
                  ["Primera conversación = sondeo: apertura prudente, pasos pequeños y distintos (20→21→22), nunca repetir.",
                   "Si da su oferta final dentro de nuestro valor, aceptarla: un trato que falta cuenta 0."])
    if a == "persona_patch":
        f = _fiebre_de(e)
        if f:
            b = f["barrio"] or "?"
            return _j("fiebre", f"Fiebre {b}: {f['vendedor']} paga +{f['pct']:.0f} % sobre catálogo", 2.0,
                      [f"Desde ya: NO vender cartas de {b} a nadie más (ni El Rastro ni otro vendedor): guion.bloqueadas().",
                       f"Preparar la lista: guion.venta_fiebre() dice qué copias de {b} nos valen menos que su precio de fiebre.",
                       f"Si {b} nos vale poco y otro equipo vende copias por debajo de nuestro valor, comprarlas antes."],
                      [f"Abrir venta con {f['vendedor']}: empezar por encima del precio de fiebre y bajar a pasos pequeños.",
                       "Nunca vender por debajo de lo que la carta nos vale (protegidas fuera).",
                       f"Termina a las {f['hasta'] or '?'} o con el aviso de fin: lo que quede se vende normal después."],
                      {"guion_fiebre": f})
        if any(s in nota for s in FIN_FIEBRE):
            return _j("fin_fiebre", f"Fin de la fiebre ({p.get('id')})", 0.25,
                      ["Último aviso: lo que aún queramos venderle con la fiebre, ahora.",
                       "Después, sus precios vuelven: volver a ofrecer esas cartas en El Rastro o a otros equipos."])
        return _j("cambio_vendedor", f"Cambio en {p.get('id')}: {e['nota']}", 0.5,
                  ["Leer la nota: si cambia lo que paga o vende, ajustar menus.json y lo que guardamos."])
    if a == "set_release":
        b = p.get("set") or "?"
        m = V.NUESTROS_MULT.get(b)
        return _j("barrio", f"Sale {b}", 0.5,
                  [f"Nuestro multiplicador de {b}: {m if m is not None else 'sin dato'} (confirmar con me()['affinity']).",
                   "Alto (≥ 1,3): comprar comunes y poco comunes regateando. Bajo (≤ 0,7): no comprar, vender lo que salga.",
                   "Las primeras copias del barrio llegan escasas: no pagar por encima de nuestro valor por ser nuevas."])
    if a == "grant_all":
        return _j("dinero", f"+{p.get('cash', '?')} P para todos", 0.25,
                  ["La caja pasa a holgada: gastarlo en los 3 tratos regateados que falten con cada vendedor, no en sobres.",
                   "Todos los equipos tienen el mismo dinero a la vez: los vendedores se vacían rápido en su cupo de la hora."])
    if a == "round":
        return _j("ronda", f"Empieza {p.get('name') or 'una ronda'}", 0.25,
                  ["La ronda cuenta por la parte del día jugada: los tratos de la primera hora valen igual que los de la última.",
                   "Escalera nueva por ronda: rehacer los 3 mejores tratos con cada vendedor."])
    if a == "persona" and p.get("enabled") is False:
        quien = p.get("id") or "?"
        return _j("cierra_vendedor", f"Cierra {quien} (final)", 1.5,
                  [f"Completar los 3 tratos de escalera con {quien} antes: después ya no se puede.",
                   f"Vender a {quien} lo que solo él compra a buen precio.",
                   "Después solo quedan duelos y equipos: cancelar conversaciones abiertas con él."])
    if a == "day_closes":
        return _j("cierre", e["nota"] or "Cierre", 0.5,
                  ["Fuera de hora las ofertas siguen abiertas y se liquidan al abrir: cancelar en El Rastro las que ya no queremos al precio de ahora.",
                   "Cerrar conversaciones a medias: los vendedores no esperan a mañana.",
                   "Guardar runs/ y el diario: material para el jurado."])
    if a == "day_opens":
        ts = p.get("tick_seconds")
        return _j("apertura", e["nota"] or "Abre el día", 0.25,
                  [f"Tick de {ts} s: poner tick_segundos = {ts} en hoy.json." if ts else "Comprobar el tick en /api/clock.",
                   "`python revisar.py` antes de lanzar nada."], hoy={"tick_segundos": ts} if ts else {})
    if a == "end_round":
        return _j("congelado", "Los puntos se congelan", 0.5,
                  ["Solo tratos claramente buenos: un trato fuera de nuestro valor ya no tiene tiempo de compensarse."])
    if a == "announce":
        return _j("anuncio", e["nota"] or "Anuncio", 0.25, ["Mirar la pantalla grande y el feed: el anuncio dice qué cambia."])
    return _j("otro", e["nota"] or a, 0.5, ["Novedad que no conocemos: leerla, mirar /api/levels y decidir."])


def sin_anunciar(tipo):
    """Jugada por defecto para un nivel nuevo de /api/levels según su tipo (persona, radio u otro)."""
    t = (tipo or "").lower()
    if t == "persona":
        return _j("vendedor_nuevo", "Vendedor nuevo anunciado", 0,
                  ["revisar.py --menus en cuanto tenga menú; 3 tratos regateados, empezando por lo más barato que nos valga más.",
                   "Si se abre antes a quien tiene tratos regateados con el anterior: hacerlos ya con el anterior."])
    if t == "radio":
        return _j("noticias", "Fuente de noticias", 0,
                  ["Mezcla verdad y rumor: solo se apunta (sondas.cuaderno). Ningún precio cambia por una noticia.",
                   "Un rumor que coincide con el calendario (/api/schedule) es cierto; uno que no, se espera a verlo.",
                   "Marcar mala fe (POST /api/flags) solo cuando el texto contradice la oferta estructurada."])
    return _j("nivel_nuevo", f"Nivel nuevo ({tipo or 'sin tipo'})", 0,
              ["Leer su `how` en /api/levels cuando se active: dice cómo se usa.",
               "Si es una forma nueva de comerciar, probarla con UN trato pequeño antes de meterla en la cadena."])


# ── fiebres ──────────────────────────────────────────────────────────────────────────────────────────────────

def fiebres(evs):
    """[{vendedor, barrio, pct, hasta, desde_h, hasta_h}]. hasta_h = el aviso de fin del mismo vendedor, o None."""
    out = []
    for i, e in enumerate(evs):
        if e["accion"] != "persona_patch":
            continue
        f = _fiebre_de(e)
        if not f:
            continue
        fin = next((x["h"] for x in evs[i + 1:] if x["accion"] == "persona_patch"
                    and x["params"].get("id") == f["vendedor"] and any(s in x["nota"].lower() for s in FIN_FIEBRE)), None)
        out.append(f | {"hasta_h": fin})
    return out


def bloqueadas(cuenta, evs, h, horizonte=6.0):
    """Cartas nuestras que no se venden ahora a otro sitio: su barrio tiene una fiebre que empieza en menos de
    `horizonte` horas o que está activa (salvo al propio vendedor de la fiebre, que es justo a quien se venden)."""
    barrios = {f["barrio"] for f in fiebres(evs)
               if f["barrio"] and f["desde_h"] - horizonte <= h and (f["hasta_h"] is None or h < f["hasta_h"])}
    return sorted(r for r, n in cuenta.items() if n > 0 and V.barrio(r) in barrios)


def reservadas(cuenta, evs, h, horizonte=6.0):
    """{ref: vendedor al que SÍ se puede vender ahora, o None = a nadie}. Antes de la fiebre las cartas del barrio no
    se venden a nadie (ni siquiera al vendedor de la fiebre, que todavía paga el precio normal); durante la fiebre,
    solo a él. Lo usan cadena.cola_de_operaciones (vendedores) y cadena.anuncios (El Rastro)."""
    out = {}
    for f in fiebres(evs):
        if not f["barrio"] or h < f["desde_h"] - horizonte or (f["hasta_h"] is not None and h >= f["hasta_h"]):
            continue
        activa = h >= f["desde_h"]
        for r, n in cuenta.items():
            if n > 0 and V.barrio(r) == f["barrio"]:
                out[r] = f["vendedor"] if activa else None
    return out


def rumor(texto, evs, h=None):
    """Radio Rastro / El Tablón mezclan verdad y rumor. Un rumor se cree solo si el calendario oficial lo confirma.
    Devuelve ("confirmado", evento) si una palabra clave del rumor (vendedor, barrio, fiebre, duelo, Market Test)
    coincide con un evento futuro del calendario; ("sin_confirmar", None) si no. Nunca cambia un precio."""
    t = (texto or "").lower()
    claves = [g for g in RUMOR_GRUPOS if any(k in t for k in g)]
    if not claves:                                    # un nombre suelto no basta: tiene que decir QUÉ pasa
        return "sin_confirmar", None
    nombres = [n for n in list(BARRIOS) + ["pilar", "chato", "abuela"] if n in t]
    for e in evs:
        if h is not None and e["h"] < h:
            continue
        n = (e["nota"] + " " + json.dumps(e["params"], ensure_ascii=False)).lower()
        if any(k in n for g in claves for k in g) and (not nombres or any(x in n for x in nombres)):
            return "confirmado", e
    return "sin_confirmar", None


RUMOR_GRUPOS = (("fever", "fiebre"), ("duel", "duelo"), ("market test", "bench"), ("release", "sale el barrio"),
                ("opens", "abre"), ("close", "cierra"), ("allowance", "primas"), ("freeze", "congela"))


def venta_fiebre(cuenta, fiebre, mult=None):
    """Qué copias venderle al vendedor de la fiebre: [{ref, precio_fiebre, nos_vale, margen}], de más a menos
    margen. Se va quitando copia a copia (la segunda copia vale menos que la primera). Nunca una protegida
    (rompe página o primera copia de un barrio top) ni una que nos vale más que su precio de fiebre."""
    mult = V.NUESTROS_MULT if mult is None else mult
    resto, out = dict(cuenta), []
    while True:
        mejor = None
        for ref, n in resto.items():
            if n <= 0 or V.barrio(ref) != fiebre["barrio"] or V.protegida(resto, ref, mult):
                continue
            precio = V.BASE[V.rareza(ref)] * (1 + fiebre["pct"] / 100)
            pierde = V.valor_entregar(resto, [ref], mult)
            if pierde is not None and precio - pierde > 0.5 and (mejor is None or precio - pierde > mejor["margen"]):
                mejor = {"ref": ref, "precio_fiebre": round(precio, 1), "nos_vale": round(pierde, 1),
                         "margen": round(precio - pierde, 1)}
        if mejor is None:
            return out
        out.append(mejor)
        resto[mejor["ref"]] -= 1


# ── lo que toca ahora ────────────────────────────────────────────────────────────────────────────────────────

def ahora(evs, h):
    """{"preparar": [(evento, jugada, horas que faltan)], "activo": [fiebres en curso]}."""
    prep = []
    for e in evs:
        j = jugada(e)
        falta = e["h"] - h
        if 0 <= falta <= j["aviso_h"]:
            prep.append((e, j, falta))
    activo = [f for f in fiebres(evs) if f["desde_h"] <= h and (f["hasta_h"] is None or h < f["hasta_h"])]
    return {"preparar": prep, "activo": activo}


def linea_de_tiempo(evs, h=None, reloj=None, cuenta=None):
    lineas = []
    for e in evs:
        if h is not None and e["h"] < h:
            continue
        j = jugada(e)
        lineas.append(f"{_hhmm(hora(e['h'], evs, reloj))}  {j['titulo']}   (preparar {j['aviso_h']:g} h antes)")
        lineas += ["        ANTES    " + x for x in j["antes"]]
        lineas += ["        DURANTE  " + x for x in j["durante"]]
        if j["hoy"]:
            lineas.append("        HOY.JSON " + json.dumps(j["hoy"], ensure_ascii=False))
    if cuenta:
        for f in fiebres(evs):
            v = venta_fiebre(cuenta, f)
            lineas.append(f"FIEBRE {f['barrio']}: vender a {f['vendedor']} " +
                          (", ".join(f"{x['ref']} (≥ {x['precio_fiebre']} P, nos vale {x['nos_vale']})" for x in v) or "nada"))
    return "\n".join(lineas)


def main(argv=None):
    ap = argparse.ArgumentParser(description="El Guion: jugada preparada para cada evento del calendario (sin red).")
    ap.add_argument("calendario", help="JSON guardado de GET /api/schedule")
    ap.add_argument("--ahora", type=float, help="hora de juego actual (now_hours); por defecto la del archivo")
    ap.add_argument("--hora", help="hora de Madrid ahora, HH:MM, para poner horas de pared")
    ap.add_argument("--cartas", help="JSON {ref: copias} de nuestras cartas, para la lista de la fiebre")
    a = ap.parse_args(argv)
    for s in (sys.stdout,):
        if hasattr(s, "reconfigure"):
            s.reconfigure(errors="replace")
    with open(a.calendario, encoding="utf-8") as f:
        cal = json.load(f)
    h = a.ahora if a.ahora is not None else ahora_h(cal)
    cuenta = None
    if a.cartas:
        with open(a.cartas, encoding="utf-8") as f:
            cuenta = json.load(f)
    print(linea_de_tiempo(eventos(cal), h, (h, a.hora) if a.hora and h is not None else None, cuenta))


if __name__ == "__main__":
    main()
