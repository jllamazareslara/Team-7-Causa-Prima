"""Pruebas sin red de la revisión antes de jugar (revisar.py) y de los menús sacados del juego (t7/menus.py)."""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import revisar  # noqa: E402
from t7 import menus as M  # noqa: E402
from t7 import valor as V  # noqa: E402


class ConValoresLimpios(unittest.TestCase):
    """Cada prueba deja los multiplicadores y las rarezas como estaban."""

    def setUp(self):
        self.mult, self.rarezas = dict(V.NUESTROS_MULT), dict(V.RAREZAS)

    def tearDown(self):
        V.NUESTROS_MULT.clear()
        V.NUESTROS_MULT.update(self.mult)
        V.RAREZAS.clear()
        V.RAREZAS.update(self.rarezas)


class Menus(ConValoresLimpios):
    def test_menu_por_rareza_por_carta_y_lo_que_no_se_entiende(self):
        V.RAREZAS.update({"RET-01": "common", "RET-02": "common", "RET-06": "uncommon", "RET-09": "rare"})
        vendedores = {"dealers": [
            {"id": "abuela", "menu": {"sells": {"common": 10, "uncommon": 25, "packs": {"sobre_barrio": 26}},
                                      "buys": {"common": 4}}},
            {"id": "chato", "menu": {"sells": [{"card": "RET-09", "price": 70}, {"kind": "pack", "id": "sobre", "price": 30},
                                               {"rarity": "common", "set": "RET", "list": 11}],
                                     "buys": [{"rarity": "uncommon", "bid": 9}], "humor": "malo"}},
            {"id": "boveda"},
            {"id": "raro", "menu": "ven a verme"},
            "basura"]}
        menus, dudas = M.del_juego(vendedores, {"LAT-03": 2, "LAT-08": 1})
        self.assertEqual(menus["abuela"], {"vende": {"RET-01": 10, "RET-02": 10, "RET-06": 25}, "compra": {"LAT-03": 4}})
        self.assertEqual(menus["chato"], {"vende": {"RET-09": 70, "RET-01": 11, "RET-02": 11}, "compra": {"LAT-08": 9}})
        self.assertEqual(sorted(menus), ["abuela", "chato"])
        self.assertEqual(len(dudas), 4)                           # humor, boveda sin menú, raro, basura

    def test_sin_catalogo_no_se_adivina_lo_que_vende(self):
        V.RAREZAS.clear()
        menus, dudas = M.del_juego([{"id": "abuela", "menu": {"sells": {"common": 10}}}], {})
        self.assertEqual(menus, {})
        self.assertTrue(any("sin catálogo" in d for d in dudas))
        self.assertEqual(M.del_juego(None), ({}, []))
        self.assertEqual(M.del_juego("basura"), ({}, []))


class Juego:
    """Un juego de mentira, sano. Las pruebas cambian lo que necesitan."""
    valor_lat = 16.0

    def clock(self):
        return {"tick": 200, "tick_seconds": 30, "paused": False}

    def me(self):
        return {"name": "t07", "cash": 300, "level": 2, "affinity": dict(V.NUESTROS_MULT),
                "assets": [{"id": 1, "kind": "card", "ref": "LAT-01", "rarity": "common", "your_value": self.valor_lat},
                           {"id": 2, "kind": "card", "ref": "MAL-01", "rarity": "common", "your_value": 5.0},
                           {"id": 3, "kind": "pack", "ref": "sobre_barrio"}, "basura"]}

    def catalog(self):
        return {"sets": [{"id": s, "cards": [{"id": f"{s}-01", "book": 10}]} for s in ("LAT", "MAL", "RET")]}

    def dealers(self):
        return {"dealers": [{"id": "abuela", "menu": {"sells": {"common": 10}, "buys": {"common": 4}}},
                            {"id": "nuevo", "menu": "?"}]}


class Revision(ConValoresLimpios):
    def niveles(self, r, nivel):
        return [t for n, t in r["lineas"] if n == nivel]

    def test_juego_sano_con_un_vendedor_nuevo(self):
        r = revisar.revisar(Juego(), {"abuela": {"vende": {}, "compra": {}}})
        self.assertEqual(r["faltas"], 1)                          # solo el vendedor nuevo, cuyo menú no se entiende
        self.assertIn("nuevo", self.niveles(r, "FALTA")[0])
        self.assertTrue(any("calculadora: las 2 cartas coinciden" in t for t in self.niveles(r, "OK")))
        self.assertTrue(any("sobre" in t for t in self.niveles(r, "AVISO")))
        self.assertEqual(r["borrador"]["abuela"]["vende"], {"LAT-01": 10, "MAL-01": 10, "RET-01": 10})

    def test_sin_menus_no_esta_listo(self):
        r = revisar.revisar(Juego(), None)
        self.assertTrue(any("no hay menus.json" in t for t in self.niveles(r, "FALTA")))
        self.assertTrue(any("abuela: no está en menus.json; borrador" in t for t in self.niveles(r, "AVISO")))

    def test_la_calculadora_que_no_coincide_es_una_falta(self):
        class Distinto(Juego):
            valor_lat = 99.0
        r = revisar.revisar(Distinto(), {"abuela": {}, "nuevo": {}})
        self.assertTrue(any("calculadora: 1 de 2" in t for t in self.niveles(r, "FALTA")))

    def test_multiplicador_distinto_se_avisa_y_se_usa(self):
        class Otro(Juego):
            valor_lat = 9.0

            def me(self):
                return dict(Juego.me(self), affinity={"LAT": 0.9, "MAL": 0.5, "RET": 1.6})
        r = revisar.revisar(Otro(), {"abuela": {}, "nuevo": {}})
        self.assertEqual(V.NUESTROS_MULT["LAT"], 0.9)
        self.assertTrue(any("multiplicador de LAT" in t for t in self.niveles(r, "AVISO")))
        self.assertEqual(r["faltas"], 0)                          # con el dato del juego, la calculadora coincide

    def test_un_juego_caido_no_revienta(self):
        class Caido:
            def __getattr__(self, nombre):
                def falla(*a, **k):
                    raise RuntimeError("sin red")
                return falla
        r = revisar.revisar(Caido(), None, stop=True)
        self.assertGreaterEqual(r["faltas"], 4)
        self.assertTrue(any("STOP" in t for t in self.niveles(r, "FALTA")))


if __name__ == "__main__":
    unittest.main()
