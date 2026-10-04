"""El Grabador de duelos y el aprendizaje, sin red."""
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
import grabador_duelos as G  # noqa: E402
from sim import aprender_duelos as A  # noqa: E402


def duelo(i, status="live", mensajes=1, rounds=1):
    return {"duel": i, "status": status, "rounds": rounds, "role": "seller", "rival": "Rival Oro", "your_limit": 50,
            "decay_per_round": 0.06, "messages": [{"from": "Rival Oro", "price": 60}] * mensajes, "result": 0}


class Juego:
    def __init__(self, terminados, en_juego):
        self.t, self.v = terminados, en_juego

    def duels(self, done=False):
        return {"duels": self.t if done else self.v}


class Grabador(unittest.TestCase):
    def test_se_queda_la_version_con_mas_informacion(self):
        todos, recien = G.fusionar([duelo(1, mensajes=3)], [duelo(1, mensajes=1), duelo(2)])
        self.assertEqual([(d["duel"], len(d["messages"])) for d in todos], [(1, 3), (2, 1)])   # no se pierde nada
        self.assertEqual(recien, [])
        todos, recien = G.fusionar(todos, [duelo(1, status="deal", mensajes=4)])
        self.assertEqual((todos[0]["status"], recien), ("deal", [1]))
        _, recien = G.fusionar(todos, [duelo(1, status="deal", mensajes=4)])
        self.assertEqual(recien, [])                                        # un terminado se anuncia una sola vez

    def test_una_pasada_guarda_y_conserva_lo_que_habia(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, "duelos-reales-04-10.json")
            G.guardar(ruta, [duelo(7, status="no_deal")])
            G.una_pasada(Juego([duelo(8, status="deal")], [duelo(9)]), ruta)
            self.assertEqual([d["duel"] for d in G.leer_archivo(ruta)], [7, 8, 9])

    def test_sin_respuesta_no_se_borra_el_archivo(self):
        class Caido:
            def duels(self, done=False):
                raise OSError("sin red")
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, "duelos-reales-04-10.json")
            G.guardar(ruta, [duelo(7, status="deal")])
            G.una_pasada(Caido(), ruta)
            self.assertEqual([d["duel"] for d in G.leer_archivo(ruta)], [7])


class Aprender(unittest.TestCase):
    def test_con_los_duelos_reales_sale_lo_mismo_que_la_repeticion(self):
        duelos = A.cargar_todos()
        self.assertGreaterEqual(len(duelos), 68)
        out = A.aprender(duelos, rejilla=A.RAPIDA)
        self.assertEqual(out["actual"]["repeticion"]["fuera"], 0)            # nunca fuera del límite
        self.assertEqual(out, A.aprender(duelos, rejilla=A.RAPIDA))          # determinista
        self.assertIn("Rival Oro", out["rivales"])
        if out["propuesta"]:
            self.assertEqual(out["propuesta"]["repeticion"]["fuera"], 0)

    def test_las_rondas_salen_del_decay(self):
        self.assertEqual((A.rondas_de({"decay_per_round": 0.10}), A.rondas_de({"decay_per_round": 0.08})), (12, 16))


class DiasReales(unittest.TestCase):
    """Duels II (3/10): your_days_weight es un número y days_meaning su sentido. Casos reales del grabador."""
    COMPRA = {"duel": 5635, "status": "live", "role": "buyer", "your_limit": 86, "issues": ["price", "days"],
              "your_days_weight": 4.02, "days_meaning": "each delivery day costs you this much cash", "deadline_tick": 30,
              "rounds": 0, "rival_offer": {"price": 50, "days": 10}, "rival": "Rival Noche",
              "messages": [{"tick": 10, "from": "Rival Noche", "price": 50, "days": 10, "text": "50 P, day 10."}]}
    VENTA = {"duel": 6088, "status": "live", "role": "seller", "your_limit": 74, "issues": ["price", "days"],
             "your_days_weight": 1.12, "days_meaning": "each delivery day adds this much cash to your side",
             "deadline_tick": 30, "rounds": 0, "rival_offer": {"price": 123, "days": 10}, "rival": "Rival Plata",
             "messages": [{"tick": 10, "from": "Rival Plata", "price": 123, "days": 10, "text": "123 P, day 10."}]}

    def jugar(self, d):
        import duelos
        from t7 import cadena

        class Juego:
            def duels(self, done=False):
                return {"duels": [d]}
        lectura = duelos.leer(Juego(), {}, 10)
        return lectura["duelos"][0], cadena.tick(lectura, cadena.Memoria())

    def test_el_dia_entra_en_la_cuenta(self):
        from t7 import duelo
        k = duelo.k_dias("buyer", 4.02, self.COMPRA["days_meaning"])
        self.assertAlmostEqual(86 - duelo.precio_efectivo(50, 10, k), -4.2, places=2)        # el −4,2 del duelo 5635
        k = duelo.k_dias("seller", 1.12, self.VENTA["days_meaning"])
        self.assertAlmostEqual(duelo.precio_efectivo(123, 10, k) - 74, 60.2, places=2)       # el +60,2 del duelo 6088
        self.assertEqual((duelo.dia_bueno("buyer", 4.02), duelo.dia_bueno("seller", 1.12)), (0, 10))
        self.assertIsNone(duelo.k_dias("buyer", 4.02, None))                                 # sin sentido, como antes

    def test_no_acepta_un_buen_precio_con_un_mal_dia(self):
        leido, ac = self.jugar(self.COMPRA)
        self.assertEqual(leido["rival"], [90.2])                                             # 50 + 10 × 4,02
        self.assertFalse(ac.get("firma_duelo"))
        m = [x for x in ac["mensajes"] if x.get("destino") == "duelo"]
        self.assertEqual(len(m), 1)
        from t7 import duelo
        k = leido["k_dias"]
        self.assertLessEqual(duelo.precio_efectivo(m[0]["precio"], m[0]["dias"], k), 86)     # lo que pedimos, dentro del límite

    def test_el_precio_escrito_no_cruza_el_limite(self):
        from t7 import duelo
        self.assertEqual(duelo.precio_a_mandar("seller", 138, 10, 5.44, 86), 86)      # 84 sería por debajo del coste
        self.assertEqual(duelo.precio_a_mandar("seller", 160, 10, 5.44, 86), 106)     # dentro del límite: tal cual
        self.assertEqual(duelo.precio_a_mandar("buyer", 59, 5, 3.0, 50), 44)
        self.assertEqual(duelo.precio_a_mandar("buyer", 59, 0, 3.0, 50), 50)          # nunca por encima del valor

    def test_acepta_lo_que_si_renta_con_el_dia(self):
        _, ac = self.jugar(self.VENTA)
        self.assertEqual((ac.get("firma_duelo") or {}).get("id"), 6088)

    def test_la_repeticion_cuenta_el_dia(self):
        r = A.repetir_todos(A.params.cargar(), [dict(self.COMPRA, status="deal", result=-4.2, decay_per_round=0.08)])
        self.assertEqual((r["fuera"], r["tratos"]), (0, 0))                                  # ya no se cierra a −4,2


if __name__ == "__main__":
    unittest.main()
