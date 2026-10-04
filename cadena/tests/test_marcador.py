"""El marcador, sin red: qué guarda de /api/me y cuándo avisa."""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import marcador  # noqa: E402


def me(score=21.95, rank=16, neg=-273.6, cash=241, cartas=30, key="tk-no-se-guarda"):
    return {"tick": 1036, "cash": cash, "collection_value": 988.4, "starter_broker_key": key,
            "assets": [{"kind": "card", "ref": f"LAV-0{i % 9 + 1}"} for i in range(cartas)],
            "score": {"score": score, "rank": rank, "negotiating": 12.6, "duel_points": 10.31, "ladder_points": 0.34,
                      "neg_points": neg, "market": 9.35, "bench_efficiency": 0.891, "mm_points": 1.7, "deals": 64}}


class Marcador(unittest.TestCase):
    def test_la_foto_no_guarda_la_clave(self):
        f = marcador.foto(me())
        self.assertEqual((f["score"], f["neg_points"], f["cartas"], f["cash"]), (21.95, -273.6, 30, 241))
        self.assertNotIn("tk-no-se-guarda", str(f))

    def test_avisa_si_bajan_los_tratos_o_el_puesto(self):
        antes = marcador.foto(me())
        _, alarmas = marcador.comparar(antes, marcador.foto(me(neg=-280.0, rank=17)), nuestro_en_marcha=True)
        self.assertEqual(len(alarmas), 2)
        self.assertTrue(any("tratos con equipos" in a for a in alarmas) and any("Puesto" in a for a in alarmas))

    def test_sin_cambios_no_avisa(self):
        antes = marcador.foto(me())
        filas, alarmas = marcador.comparar(antes, marcador.foto(me()), nuestro_en_marcha=False)
        self.assertEqual(alarmas, [])
        self.assertTrue(all(c in (0, None) for _, _, c, _ in filas))

    def test_cartas_que_cambian_sin_programa_nuestro(self):
        antes = marcador.foto(me())
        _, alarmas = marcador.comparar(antes, marcador.foto(me(cash=214, cartas=37)), nuestro_en_marcha=False)
        self.assertEqual(len(alarmas), 2)
        _, alarmas = marcador.comparar(antes, marcador.foto(me(cash=214, cartas=37)), nuestro_en_marcha=True)
        self.assertEqual(alarmas, [])

    def test_mejorar_no_es_alarma(self):
        antes = marcador.foto(me())
        _, alarmas = marcador.comparar(antes, marcador.foto(me(score=23.0, rank=14, neg=-200.0)), nuestro_en_marcha=True)
        self.assertEqual(alarmas, [])


if __name__ == "__main__":
    unittest.main()
