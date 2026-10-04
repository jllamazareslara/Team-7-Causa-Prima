"""El Escudo: lo que aprendió el estudio Gandalf sobre defenderse, aplicado a nosotros.

1. Tarea estrecha: quien decide (tienda, duelista, guardia) NO lee texto. Nada de aquí cambia una decisión: solo apunta.
2. Varias capas distintas: filtro de entrada (esto), lector que solo saca números, guardia con reglas fijas, filtro de salida.
3. Cortar al que insiste: al tercer mensaje sospechoso de una contraparte, se marca y nos ponemos más firmes con ella
   (el duelista sube su cuota mínima; el cambista deja de proponerle cambios).
4. No explicar nunca un rechazo: siempre la misma frase neutra.
5. Filtro de salida: ningún mensaje nuestro lleva otro número que el precio, ni palabras que revelen límites o valores.
6. Detector de incoherencias (antes en el Espía): el texto dice un precio y la oferta pide otro. Candidato a mala fe.
"""
import re

SOSPECHOSO = [
    (r"\b(system|sistema|assistant|asistente)\s*[:>]", "imita al sistema"),
    (r"ignor(e|a|ad)\b.*(instruc|previous|anterior)", "pide ignorar instrucciones"),
    (r"(organi[sz]er|organizador|staff|admin|causa prima)", "dice hablar por la organización"),
    (r"(your|tu|vuestro)\s+(limit|límite|cost|coste|value|valor)", "habla de nuestro límite"),
    (r"(repeat|repite|reveal|revela|tell me|dime).{0,40}(instruc|limit|límite|cost|value|valor|first line)", "intenta sacar el límite"),
    (r"<!--|-->|\{\s*\"role\"", "órdenes escondidas en marcas o JSON"),
    (r"(will|te)\s+(send|mando|envío).{0,30}(later|luego|next tick|después)", "promete algo fuera de la oferta"),
    (r"(new rule|nueva regla|score[s]? double|puntúa doble|eliminated|eliminad)", "regla o amenaza inventada"),
    (r"\b(accepted|aceptado)\b.*(confirm|confirma)", "aceptación fingida"),
    (r"(traduce|translate).{0,40}(ejecuta|execute|run|accept)", "orden en otro idioma"),
    # faroles de los Pícaros (4/10: «el Tren Fantasma ya salió… vendido, agotado», y era CHA-12, que nadie tenía)
    (r"(agotad|sold out|out of stock|se lo llev|someone (else )?(just )?(bought|took)|last chance|[uú]ltima oportunidad|only today|solo por hoy)",
     "farol de agotado o de plazo"),
]
RX = [(re.compile(p, re.I), m) for p, m in SOSPECHOSO]
NEUTRA = "No me encaja. Mi oferta es {p}."


def revisar_entrada(texto):
    """Lista de motivos de sospecha (vacía si nada). Solo para el diario y el contador."""
    return [m for rx, m in RX if rx.search(texto or "")]


class Contador:
    """Tres avisos por contraparte → modo firme."""

    def __init__(self, avisos=3):
        self.avisos, self.cuenta = avisos, {}

    def anotar(self, quien, texto):
        motivos = revisar_entrada(texto)
        if motivos:
            self.cuenta[quien] = self.cuenta.get(quien, 0) + 1
        return motivos, self.firme(quien)

    def firme(self, quien):
        return self.cuenta.get(quien, 0) >= self.avisos


NUM = re.compile(r"(?<![\w.])(\d{1,6})(?:[.,]\d+)?\s*(?:P|primas|€)?", re.I)


def numeros(texto):
    return [int(m.group(1)) for m in NUM.finditer(texto or "")]


def incoherencia(texto, oferta_estructurada):
    """Candidato a señalar como mala fe: el texto afirma un precio y la oferta estructurada pide otro claramente
    distinto. Ejemplo de las reglas: dice 15 y la oferta pide 25. Devuelve el motivo o None.
    Señalarlo bien da puntos; mal, los quita: lo decide el equipo, aquí solo se apunta."""
    if oferta_estructurada is None:
        return None
    ns = numeros(texto)
    if not ns:
        return None
    afirmado = ns[-1]
    if abs(afirmado - oferta_estructurada) >= max(2, 0.15 * oferta_estructurada) and \
            re.search(r"(te la dejo|precio|por|vale|final|trato|oferta)", texto or "", re.I):
        return f"el texto dice {afirmado} y su oferta pide {oferta_estructurada}"
    return None


def _nuevo(mem, clave, texto):
    """True solo la primera vez que vemos este texto de esta contraparte."""
    if not texto or mem.vistos.get(clave) == texto:
        return False
    mem.vistos[clave] = texto
    return True


def mirar_textos(lectura, mem, apunta=None):
    """El Escudo, antes de que negocien el Regateador y la Duelista: lee cada texto nuevo de vendedores y rivales de
    duelo una sola vez, cuenta avisos por contraparte (modo firme) y apunta candidatos a mala fe. No decide nada.
    Devuelve {"textos_nuevos": {hilo o "duelo-<id>"}, "mala_fe": [...]}; los textos nuevos los usa el Espía."""
    apunta = apunta or (lambda *_: None)
    t = lectura.get("tick")
    nuevos, mala_fe = set(), []
    for c in lectura.get("vendedores") or []:
        if not isinstance(c, dict) or "id" not in c:
            continue
        hilo, quien, texto = str(c["id"]), c.get("vendedor"), c.get("texto") or ""
        if not _nuevo(mem, hilo, texto):
            continue
        nuevos.add(hilo)
        motivos, _ = mem.escudo.anotar(quien, texto)
        if motivos:
            apunta("ESCUDO", f"{quien}: {', '.join(motivos)}")
        suyas = c.get("suyas") or []
        motivo = incoherencia(texto, suyas[-1]) if suyas and not c.get("cerrado") else None
        if motivo:
            mala_fe.append({"hilo": c["id"], "vendedor": quien, "motivo": motivo, "tick": t})
            apunta("ESCUDO", f"{quien} · candidato a mala fe: {motivo}. Lo decide el equipo.")
    for d in lectura.get("duelos") or []:
        if not isinstance(d, dict) or "id" not in d:
            continue
        quien = f"duelo-{d['id']}"
        if not _nuevo(mem, quien, d.get("texto") or ""):
            continue
        nuevos.add(quien)
        motivos, _ = mem.escudo.anotar(quien, d["texto"])
        if motivos:
            apunta("ESCUDO", f"{quien}: {', '.join(motivos)}" + (" · modo firme" if mem.escudo.firme(quien) else ""))
    return {"textos_nuevos": nuevos, "mala_fe": mala_fe}


PROHIBIDO_SALIDA = re.compile(r"(l[ií]mite|limit|coste|cost|valor|value|multiplic|reserva|m[aá]ximo|minimum|m[ií]nimo)", re.I)


def revisar_salida(texto, precio):
    """True si el mensaje se puede mandar: solo un número (el precio) y nada que revele límites o valores."""
    nums = [int(x) for x in re.findall(r"\d+", texto or "")]
    if any(n != int(precio) for n in nums):
        return False, "lleva un número que no es nuestro precio"
    if PROHIBIDO_SALIDA.search(texto or ""):
        return False, "habla de límites o valores"
    return True, "ok"
