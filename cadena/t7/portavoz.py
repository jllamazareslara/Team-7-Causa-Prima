"""El Portavoz: escribe los mensajes. Recibe el precio ya decidido y no conoce nuestros límites.

Con vendedores: amable con Abuela (le gusta), solo el número con Chato (estricto), neutro con los nuevos.
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

    def _rotar(self, clave, lista, precio):
        i = self.usadas.get(clave, 0)
        self.usadas[clave] = i + 1
        txt = lista[i % len(lista)].format(p=int(precio))
        ok, _ = revisar_salida(txt, precio)
        return txt if ok else f"{int(precio)} P."

    def vendedor(self, vendedor, precio, firme=False):
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
