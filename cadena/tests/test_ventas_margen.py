"""Margen de las ventas del Cambista (3/10 por la tarde): sin demanda no se malvende, al cazador de páginas se le cobra
lo que ha ofrecido, y los cambios carta por carta tienen su propio interruptor (cambista.cambiar)."""
import os
import sys
import unittest
from collections import Counter

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
from t7 import cadena, comerciante, params  # noqa: E402

P = params.cargar()
C = Counter({"MAL-01": 3, "LAT-03": 2, "LAT-08": 1})


def mem_con(hist):
    mem = cadena.Memoria()
    mem.historial = hist
    return mem


def refs(an):
    return [a["carta"] for a in an]


class SinDemanda(unittest.TestCase):
    def test_nadie_la_pide_y_muchos_la_venden_no_se_anuncia(self):
        hist = {"MAL-01": [[95, 6, "venta", "m1"], [96, 5, "venta", "m2"], [97, 5, "venta", "m3"]]}
        an = comerciante.anuncios(C, P, mem_con(hist), {"tick": 100})
        self.assertNotIn("MAL-01", refs(an))
        self.assertIn("LAT-03", refs(an))                                  # la otra repetida sí

    def test_con_un_comprador_si_se_anuncia(self):
        hist = {"MAL-01": [[95, 6, "venta", "m1"], [96, 5, "venta", "m2"], [97, 4, "compra", "m4"]]}
        self.assertIn("MAL-01", refs(comerciante.anuncios(C, P, mem_con(hist), {"tick": 100})))

    def test_con_el_ajuste_a_cero_se_anuncia_siempre(self):
        hist = {"MAL-01": [[95, 6, "venta", "m1"], [96, 5, "venta", "m2"]]}
        p = dict(P, **{"cambista.sin_demanda_vendedores": 0})
        self.assertIn("MAL-01", refs(comerciante.anuncios(C, p, mem_con(hist), {"tick": 100})))

    def test_lo_viejo_no_cuenta(self):
        hist = {"MAL-01": [[1, 6, "venta", "m1"], [2, 5, "venta", "m2"]]}         # hace más de 120 ticks
        self.assertIn("MAL-01", refs(comerciante.anuncios(C, P, mem_con(hist), {"tick": 400})))


class CazadorDePaginas(unittest.TestCase):
    def test_quien_la_pide_varias_veces_paga_lo_que_ofrecio(self):
        hist = {"LAT-03": [[90, 18, "compra", "m9"], [95, 22, "compra", "m9"]]}
        an = {a["carta"]: a for a in comerciante.anuncios(C, P, mem_con(hist), {"tick": 100})}
        self.assertGreaterEqual(an["LAT-03"]["precio"], 22)
        self.assertIn("cazador", an["LAT-03"])

    def test_una_sola_vez_no_es_cazador(self):
        hist = {"LAT-03": [[95, 40, "compra", "m9"]]}
        an = {a["carta"]: a for a in comerciante.anuncios(C, P, mem_con(hist), {"tick": 100})}
        self.assertNotIn("cazador", an["LAT-03"])

    def test_el_cazador_salta_el_filtro_sin_demanda(self):
        hist = {"MAL-01": [[90, 6, "venta", "m1"], [91, 5, "venta", "m2"],
                           [92, 15, "compra", "m9"], [93, 16, "compra", "m9"]]}
        an = {a["carta"]: a for a in comerciante.anuncios(C, P, mem_con(hist), {"tick": 100})}
        self.assertGreaterEqual(an["MAL-01"]["precio"], 16)

    def test_nunca_por_debajo_de_lo_que_nos_vale(self):
        hist = {"LAT-03": [[90, 1, "compra", "m9"], [95, 1, "compra", "m9"]]}
        for a in comerciante.anuncios(C, P, mem_con(hist), {"tick": 100}):
            self.assertGreaterEqual(a["precio"], a["pierde"] + 1)


class Ajustes(unittest.TestCase):
    def test_cambios_encendidos_y_cuatro_a_la_vez(self):
        self.assertEqual(P["cambista.cambiar"], 1)
        self.assertEqual(P["cambista.trueques_max"], 4)


class MejorCanal(unittest.TestCase):
    """Antes de abrir una venta: oferta del tablón, vendedor o anuncio, solo con valores reales (la API)."""
    CUENTA = Counter({"MAL-01": 3})

    def canales(self, tablon=(), menus=None, hist=None, comisiones=None, **kw):
        return comerciante.canales_de_venta(self.CUENTA, menus or {}, list(tablon), mem_con(hist or {}), {"tick": 100},
                                            comisiones=comisiones, **kw)["MAL-01"]

    def test_gana_el_neto_mas_alto(self):
        pide = {"id": 5, "maker": "t05", "venue": "rastro", "give": {"cash": 20}, "want": {"cards": ["MAL-01"]}}
        menus = {"abuela": {"compra": {"MAL-01": 12}}}
        c = self.canales([pide], menus, comisiones={"rastro": (0.05, 1)})
        self.assertEqual((c["canal"], c["donde"], c["neto"]), ("oferta", 5, 18))     # 20 - (1 + 1)
        c = self.canales([dict(pide, give={"cash": 13})], menus, comisiones={"rastro": (0.05, 1)})
        self.assertEqual((c["canal"], c["donde"]), ("vendedor", "abuela"))           # 13 - 2 = 11 < 12

    def test_la_comision_es_la_del_juego(self):
        pide = {"id": 5, "maker": "t05", "venue": "v02", "give": {"cash": 12}, "want": {"cards": ["MAL-01"]}}
        menus = {"abuela": {"compra": {"MAL-01": 11}}}
        self.assertEqual(self.canales([pide], menus, comisiones={"v02": (0, 0)})["canal"], "oferta")      # gratis: 12
        self.assertEqual(self.canales([pide], menus, comisiones={})["canal"], "vendedor")                 # sin dato: como El Rastro

    def test_el_anuncio_solo_con_precio_real(self):
        menus = {"abuela": {"compra": {"MAL-01": 8}}}
        self.assertEqual(self.canales(menus=menus)["canal"], "vendedor")             # sin trato ni anuncio ajeno
        c = self.canales(menus=menus, hist={"MAL-01": [[90, 15, "trato", None]]}, comisiones={"rastro": (0.05, 1)})
        self.assertEqual((c["canal"], c["neto"]), ("anuncio", 13))                   # el último trato del feed
        viejo = {"MAL-01": [[-100, 15, "trato", None]]}                                 # hace más de una hora: no cuenta
        self.assertEqual(self.canales(menus=menus, hist=viejo)["canal"], "vendedor")
        self.assertEqual(self.canales()["donde"], "sin precio real")                 # sin ningún dato: se anuncia y se dice

    def test_vendedor_que_descansa_no_cuenta(self):
        menus = {"abuela": {"compra": {"MAL-01": 30}}, "chato": {"compra": {"MAL-01": 20}}}
        self.assertEqual(self.canales(menus=menus, descansan={"abuela"})["donde"], "chato")
        self.assertEqual(self.canales(menus=menus, cupo_lleno={"abuela", "chato"})["donde"], "sin precio real")

    def test_comisiones_de_venues(self):
        from t7 import ojos
        r = ojos.comisiones({"venues": [{"id": "rastro", "fee_bps": 500, "fee_per_card": 1}, {"id": "v02", "fee_bps": 0},
                                        {"id": "raro"}]})
        self.assertEqual(r, {"rastro": (0.05, 1), "v02": (0.0, 0)})


if __name__ == "__main__":
    unittest.main()
