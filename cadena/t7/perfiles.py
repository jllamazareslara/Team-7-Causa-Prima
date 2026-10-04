"""El Observador: con quién somos duros, con quién no, y cómo se clasifica a un vendedor nuevo.

La tabla de abajo es la respuesta a "¿dónde negociar extremo y con quién?". Cada fila sale del simulador o de las reglas.
Un vendedor nuevo empieza como "desconocido" (prudente); tras su primera conversación (el sondeo) se le asigna el perfil
más parecido según tres medidas: cuánto imita nuestros pasos (k̂), cuántas rondas aguanta, y si se ofendió.
"""
import json
import os

MATRIZ = [
    # contraparte, dureza, apertura, cómo, ataque (sondas), por qué
    ("Abuela", "EXTREMA", "10 % de lo que pide", "pasos repartidos hasta su paciencia, frases amables", "sí, 2 por conversación",
     "Imita nuestros pasos y perdona. En el simulador el ancla extrema da 0,54 de rango frente a 0,42 del equipo que gana."),
    ("Chato", "EXTREMA en precio, CERO en palabras", "10 % de lo que pide", "solo números, 7 rondas", "no",
     "Estricto y rencoroso: el riesgo no está en el ancla sino en repetir o en trucos. Simulado: 0,55 frente a 0,20."),
    ("Pilar (coleccionista)", "MEDIA al venderle", "2 × su oferta (no 3)", "pasos fijos del 11 %, de usted y hablando de su álbum",
     "no", "Paga bien lo que le gusta (SAL y RET primero) y se acuerda (memoria 0,7): un ancla extrema la puede echar."),
    ("Pícaros (tramposos)", "MEDIA, sin creer nada", "50 % de lo que piden", "nombrando siempre la carta, sin prisa",
     "no", "Cambian la carta en la oferta (lo para el Guardia) y su «final», «agotado» y plazos son faroles: no se acepta"
     " una final sin más y, si pasa del tope, nos vamos y se vuelve luego. Visto 4/10: rara 73 → ~62-64."),
    ("Don Ernesto (banco)", "BAJA en palabras, paciente en precio", "40 % de lo que pide", "de usted, breve y serio, 12 rondas",
     "no", "Estricto 1,0, memoria 1,0, astucia 0,95 y nunca tiene prisa: un ancla extrema o un truco cierran la puerta."
     " No se le insiste con una carta que no quiso. Vende legendarias a 585 y compra épicas y legendarias."),
    ("Vendedor nuevo", "PRUDENTE, luego según perfil", "15 %", "primera conversación = sondeo", "no hasta conocerlo",
     "No sabemos si se ofende. El sondeo mide cómo cede y en qué ronda da la final."),
    ("Vender a un vendedor", "MEDIA", "max(2 × lista, 3 × su oferta)", "pasos fijos del 11 %", "como al comprar",
     "Aquí el ancla agresiva no aporta más: ganó la regla del equipo que va primero."),
    ("Duelo contra un equipo", "ALTA pero creíble", "coste × 2,0 / valor × 0,45", "curva Boulware β 0,6 + aceptar si ≥ 94 % de nuestra siguiente",
     "palabras sí (farol, prisa, autoridad); inyección no",
     "Sin trato es cero para los dos: la firmeza rinde, pero cada ronda cuesta un 6 %. Simulado: 0,43 frente a 0,39 de Juan."),
    ("Equipos en El Rastro", "SUAVE: gana-gana", "35 % de lo que nos vale lo que falta", "precio fijo que baja 1 P por caducidad",
     "no", "Aquí puntúa TODO el valor ganado y ellos valoran distinto: el valor sale de cambiar, no de apretar."),
    ("Quien completa página con nuestra repetida", "ALTA", "su mejor precio visto", "cobrar caro: para él vale valor + bono", "no",
     "Una repetida que nos vale 2,8 puede valerle 80 a quien le falta para completar."),
    ("Market Test", "no es negociación", "—", "puesto gratuito hasta tener libros reales", "—",
     "En nuestro simulador ningún broker supera al puesto. El kit dice que se puede: falta ver datos reales (grabador de Juan)."),
]

PERFILES_CONOCIDOS = {"abuela": {"k": 0.85, "paciencia": 13, "se_ofende": False},
                      "chato": {"k": 0.7, "paciencia": 8, "se_ofende": True}}


def clasificar(k_medido, rondas_hasta_final, se_ofendio):
    """Perfil conocido más parecido a lo observado en el sondeo."""
    def dist(p):
        return abs(p["k"] - k_medido) / 0.5 + abs(p["paciencia"] - rondas_hasta_final) / 5 + (p["se_ofende"] != se_ofendio) * 1.0
    return min(PERFILES_CONOCIDOS, key=lambda n: dist(PERFILES_CONOCIDOS[n]))


class Memoria:
    """Lo observado de cada vendedor, en disco: rondas hasta la final, k̂, ofertas finales. Sirve para corregir
    paciencia_estimada con datos reales (se usa el percentil bajo: mejor llegar antes que tarde)."""

    def __init__(self, ruta):
        self.ruta = ruta
        self.d = json.load(open(ruta, encoding="utf-8")) if os.path.exists(ruta) else {}

    def anotar(self, vendedor, **obs):
        self.d.setdefault(vendedor, []).append(obs)
        with open(self.ruta, "w", encoding="utf-8") as f:
            json.dump(self.d, f, ensure_ascii=False, indent=1)

    def paciencia(self, vendedor, por_defecto):
        r = sorted(o["rondas_final"] for o in self.d.get(vendedor, []) if o.get("rondas_final"))
        return r[max(0, len(r) // 5 - 1)] if len(r) >= 3 else por_defecto
