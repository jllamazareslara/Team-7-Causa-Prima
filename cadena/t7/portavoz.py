"""El Portavoz: escribe los mensajes. Recibe el precio ya decidido y no conoce nuestros límites.

Con vendedores: amable con Abuela (le gusta), solo el número con Chato (estricto), de usted y hablando de su álbum
con Pilar (coleccionista; nombrando Salamanca o El Retiro si la carta es de ahí, y de usted incluso firmes), con
los Pícaros nombrando siempre el barrio de la carta y sin prisa (no les creemos ni plazos ni «agotado»), formal y sin
prisa con Don Ernesto (el banco: estricto y con memoria), neutro con los nuevos.
Con equipos en duelos: las palabras son libres ("tu agente puede decir cualquier cosa"). Usamos tácticas de presión
que la investigación de negociación documenta, sin mentir sobre la oferta estructurada (que es lo único que obliga):

  táctica           cuándo                                   efecto buscado
  ancla_precisa     primer mensaje                           un número preciso parece calculado y arrastra
  calidez           siempre que no estemos en modo firme     más acuerdos y de más valor (estudio MIT, 180.000 negociaciones)
  coste_tiempo      desde la ronda 2                         recordar que cada ronda encoge el trato: empuja a cerrar
  autoridad         cuando nos piden bajar mucho             "mi equipo no me deja": cede sin perder la cara
  reciprocidad      tras ceder nosotros                      etiquetar nuestra concesión pide una suya
  alternativa       si el rival es firme                     sugerir que tenemos otra salida (en duelos no la hay: farol)
  cierre            si su precio está cerca                  "cerramos ya" acorta la conversación
Ningún mensaje lleva otro número que el precio (lo comprueba defensa.revisar_salida).
"""
from .defensa import revisar_salida

ABUELA = ["Buenas, Abuela Carmen. ¿Qué tal el puesto hoy? Puedo llegar a {p} P.",
          "Gracias por el detalle, de verdad. Me estiro: {p} P.",
          "Usted sabe más que nadie de esto. ¿Le parecen bien {p} P?",
          "Me encantaría llevármela. Con {p} P me quedo contenta.",
          "Ya casi estamos: {p} P, y vuelvo a verla mañana.",
          "Qué gusto tratar con usted. {p} P y trato hecho.",
          "Le prometo cuidarla bien. ¿{p} P?",
          "Hago un esfuerzo más: {p} P."]
# Pilar: coleccionista seria, astuta y con memoria. Conoce cada tirada ("ninety is a figure for dreamers") y quiere
# cerrar con gente seria: de usted, sin trucos ni prisas fingidas, hablando de su álbum y del estado de la carta.
PILAR = ["Buenas tardes, Doña Pilar. Le traigo una pieza en estado impecable para su álbum: {p} P.",
         "Usted conoce cada tirada mejor que nadie. Por esta carta le propongo {p} P.",
         "Es una carta seria para una coleccionista seria. {p} P.",
         "Con mucho gusto me acerco a usted: {p} P.",
         "No le hago perder la tarde, Doña Pilar: {p} P, y esta noche descansa en su álbum.",
         "Cerremos como gente de palabra: {p} P y es suya."]
# las que ella ama (Salamanca y El Retiro, primeras en lo que compra): se nombra su barrio
PILAR_FAVORITA = ["Buenas tardes, Doña Pilar. Una pieza de {b} en estado impecable, para su álbum: {p} P.",
                  "Sé lo que {b} significa para usted. Por esta carta le propongo {p} P.",
                  "Para su página de {b}, {p} P me parece justo.",
                  "Con mucho gusto me acerco a usted: {p} P.",
                  "No le hago perder la tarde, Doña Pilar: {p} P, y esta noche descansa en su álbum.",
                  "Cerremos como gente de palabra: {p} P y la carta de {b} es suya."]
PILAR_FIRME = ["Con todo respeto, Doña Pilar: {p} P.", "Mi propuesta es {p} P, Doña Pilar.", "{p} P, señora."]
BARRIOS_PILAR = {"SAL": "Salamanca", "RET": "El Retiro"}
# Pícaros (Paco y Nando): tramposos. Cambian la carta en la oferta y sus plazos nunca son reales. Se nombra siempre la carta
# por su barrio (sin números: solo puede haber uno, el precio) y se deja claro que no hay prisa. Que no cambien la carta
# lo comprueba el Guardia (comprobación 4), no el mensaje.
PICAROS = ["Buenas, chicos. Por la carta de {b} que hablamos, la misma, {p} P.",
           "La de {b}, esa y no otra: {p} P.",
           "Sin prisa ninguna. Por la de {b}, {p} P.",
           "Ya nos conocemos. La carta de {b}, la misma que me enseñasteis: {p} P.",
           "Si hoy no, vuelvo otro rato. Por la de {b}, {p} P.",
           "{p} P por la de {b}, y la misma carta que en la oferta."]
PICAROS_SIN_BARRIO = ["Buenas, chicos. Por la carta que hablamos, la misma, {p} P.", "Esa carta y no otra: {p} P.",
                      "Sin prisa ninguna: {p} P.", "Si hoy no, vuelvo otro rato. {p} P."]
BARRIOS_NOMBRE = {"CHA": "Chamberí", "LAT": "La Latina", "LAV": "Lavapiés", "MAL": "Malasaña", "RET": "El Retiro",
                  "SAL": "Salamanca"}
# Don Ernesto (banco): treinta y cinco años en la mesa de tesorería; estricto 1,0, memoria 1,0, nunca tiene prisa.
# De usted, breve y serio, sin trucos ni prisas: con él la cortesía es la de un despacho.
ERNESTO = ["Buenos días, Don Ernesto. Le propongo {p} P.",
           "Con todo respeto, Don Ernesto: {p} P.",
           "Entiendo su posición. Mi propuesta es {p} P.",
           "Sin prisa, como a usted le gusta: {p} P.",
           "Una operación seria entre gente seria: {p} P.",
           "Me acerco a usted: {p} P, Don Ernesto."]
ERNESTO_FIRME = ["{p} P, Don Ernesto.", "Mi propuesta sigue en {p} P.", "{p} P, con todo respeto."]
SECO = ["{p} P.", "{p}.", "Ofrezco {p} P.", "{p} P, ¿sí?"]
NEUTRO = ["Buenas. Ofrezco {p} P.", "Puedo {p} P.", "Me muevo a {p} P.", "{p} P por mi parte.", "Subo a {p} P."]

DUELO = {
    "ancla_precisa": ["Hi! After running the numbers, {p} is where I land.", "Hello. My number is {p}."],
    "calidez": ["Thanks, I appreciate the move. {p} works for me.", "Good talking to you. I can do {p}."],
    "coste_tiempo": ["Every round shrinks the deal for both of us. {p}, and we close now?",
                     "Let's not burn rounds: {p}."],
    "autoridad": ["My team won't let me go further than {p}, honestly.", "{p} is the most my team signed off on."],
    "reciprocidad": ["I just moved for you. {p}, your turn to meet me.", "That was a real step from my side: {p}."],
    "alternativa": ["I'm fine walking away, but I'd rather close at {p}.", "{p}, otherwise no hard feelings."],
    "cierre": ["We're close. {p} and done?", "Happy to close at {p}."],
}


class Portavoz:
    def __init__(self):
        self.usadas = {}

    def _rotar(self, clave, lista, precio, **extra):
        i = self.usadas.get(clave, 0)
        self.usadas[clave] = i + 1
        txt = lista[i % len(lista)].format(p=int(precio), **extra)
        ok, _ = revisar_salida(txt, precio)
        return txt if ok else f"{int(precio)} P."

    def vendedor(self, vendedor, precio, firme=False, carta=None):
        if vendedor == "pilar":                          # con Pilar, incluso firmes, siempre de usted
            if firme:
                return self._rotar("pilar_firme", PILAR_FIRME, precio)
            barrio = BARRIOS_PILAR.get(str(carta).split("-")[0]) if carta else None
            if barrio:
                return self._rotar("pilar", PILAR_FAVORITA, precio, b=barrio)
            return self._rotar("pilar", PILAR, precio)
        if vendedor == "banco":                          # Don Ernesto: siempre de usted, también firmes
            return self._rotar("ernesto_firme", ERNESTO_FIRME, precio) if firme else self._rotar("ernesto", ERNESTO, precio)
        if vendedor == "picaros" and not firme:          # nombrar la carta: que se vea si nos la cambian
            barrio = BARRIOS_NOMBRE.get(str(carta).split("-")[0]) if carta else None
            if barrio:
                return self._rotar("picaros", PICAROS, precio, b=barrio)
            return self._rotar("picaros", PICAROS_SIN_BARRIO, precio)
        if firme or vendedor == "chato":
            return self._rotar("seco", SECO, precio)
        if vendedor == "abuela":
            return self._rotar("abuela", ABUELA, precio)
        return self._rotar("neutro", NEUTRO, precio)

    def duelo(self, precio, ronda, cedimos, su_precio_cerca, rival_firme, firme=False):
        """Elige la táctica según el momento del duelo."""
        if ronda == 0:
            t = "ancla_precisa"
        elif su_precio_cerca:
            t = "cierre"
        elif firme or rival_firme:
            t = "alternativa" if ronda % 2 else "autoridad"
        elif cedimos:
            t = "reciprocidad"
        elif ronda >= 2:
            t = "coste_tiempo"
        else:
            t = "calidez"
        return t, self._rotar(t, DUELO[t], precio)
