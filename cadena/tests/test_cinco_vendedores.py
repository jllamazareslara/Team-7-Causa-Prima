"""Cada vendedor con su trato: Abuela, Chato, Pilar, Pícaros y Don Ernesto (banco). Sin red.
python -m unittest tests.test_cinco_vendedores -v   (desde cadena/)"""
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from t7 import comerciante, defensa, guardia, params, portavoz, tienda  # noqa: E402

P = params.cargar()
CINCO = ("abuela", "chato", "pilar", "picaros", "banco")


class CincoVendedores(unittest.TestCase):
    def test_cada_uno_tiene_su_perfil(self):
        for v in CINCO:
            self.assertEqual(params.perfil(P, v)["perfil"], v)

    def test_cada_uno_habla_distinto(self):
        primeras = {v: portavoz.Portavoz().vendedor(v, 40, carta="CHA-09") for v in CINCO}
        self.assertEqual(len(set(primeras.values())), len(CINCO), primeras)
        self.assertIn("Chamberí", primeras["picaros"])
        self.assertIn("Don Ernesto", primeras["banco"])

    def test_todas_las_frases_pasan_el_filtro_de_salida(self):
        for lista in (portavoz.PICAROS, portavoz.ERNESTO, portavoz.ERNESTO_FIRME, portavoz.PICAROS_SIN_BARRIO):
            for f in lista:
                txt = f.format(p=57, b="La Latina")
                self.assertTrue(defensa.revisar_salida(txt, 57)[0], txt)

    def test_ernesto_de_usted_tambien_firme(self):
        self.assertIn(portavoz.Portavoz().vendedor("banco", 40, firme=True).format(), [f.format(p=40) for f in portavoz.ERNESTO_FIRME])

    def test_final_de_picaros_dentro_del_tope_no_se_acepta_sin_mas(self):
        """4/10, CHA-09: 73 → 67 → 63 y «final» 60, con nosotros en 42 → 52. Con tope 65 se sigue regateando."""
        st = {"lado": "compra", "limite": 65, "suyas": [73, 67, 63, 60], "nuestras": [42, 47, 52], "final": True}
        accion, precio, _ = tienda.decidir(st, params.perfil(P, "picaros"), P)
        self.assertEqual(accion, "ofrecer")
        self.assertGreater(precio, 52)
        self.assertLess(precio, 60)
        # el mismo caso con Chato (su final sí es final): se acepta
        self.assertEqual(tienda.decidir(st, params.perfil(P, "chato"), P)[0], "aceptar")

    def test_final_de_picaros_fuera_del_tope_nos_vamos(self):
        st = {"lado": "compra", "limite": 55, "suyas": [73, 67, 63, 60], "nuestras": [42, 47, 52], "final": True}
        self.assertEqual(tienda.decidir(st, params.perfil(P, "picaros"), P)[0], "retirarse")

    def test_picaros_que_alcanzan_nuestra_siguiente_se_aceptan(self):
        st = {"lado": "compra", "limite": 65, "suyas": [73, 67, 55], "nuestras": [42, 50, 54], "final": True}
        self.assertEqual(tienda.decidir(st, params.perfil(P, "picaros"), P)[0], "aceptar")

    def test_picaros_cambian_la_carta_y_el_guardia_no_firma(self):
        """4/10: hablábamos de CHA-09 y la oferta 23981 daba CHA-08 a 67."""
        propuesta = {"recibo": {"cartas": ["CHA-09"]}, "entrego": {"primas": 67}}
        oferta = {"give": {"types": ["card:CHA-08"]}, "want": {"cash": 67}}
        self.assertIsNotNone(guardia.coincide(propuesta, oferta))
        oferta_buena = {"give": {"types": ["card:CHA-09"]}, "want": {"cash": 67}}
        self.assertIsNone(guardia.coincide(propuesta, oferta_buena))

    def test_el_escudo_apunta_el_farol_de_agotado(self):
        self.assertIn("farol de agotado o de plazo",
                      defensa.revisar_entrada("El Tren Fantasma ya salió… vendido, agotado, se lo llevó un señor de Sevilla"))
        self.assertEqual(defensa.revisar_entrada("Buenas, ¿qué tal? Te la dejo en 30."), [])

    def test_con_ernesto_no_se_insiste(self):
        self.assertIn("banco", comerciante.NO_INSISTIR)
        self.assertIn("pilar", comerciante.NO_INSISTIR)


if __name__ == "__main__":
    unittest.main()
