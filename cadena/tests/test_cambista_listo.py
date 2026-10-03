"""Lo que faltaba para el Cambista: márgenes iguales que el Guardia, un solo programa que acepta, datos reales."""
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
from t7 import cambista, candado, guardia, params, situacion  # noqa: E402

P = params.cargar()


def anuncio(precio, ref="LAT-09"):
    return {"id": 7, "maker": "t03", "give": {"assets": [{"kind": "card", "ref": ref}]}, "want": {"cash": precio}}


class Margenes(unittest.TestCase):
    def test_solo_propone_lo_que_el_guardia_firma(self):
        # LAT-09 nos vale 112. Con la comisión (5 % + 1) pagar 98 cuesta 104: neto 8, por debajo del 10 % (11,2).
        justo = cambista.oportunidades([anuncio(98)], {}, 300, reserva=60)
        self.assertEqual(len(justo), 1)                                   # sin ajustes: renta, se propondría
        self.assertEqual(cambista.oportunidades([anuncio(98)], {}, 300, reserva=60, p=P), [])
        bueno = cambista.oportunidades([anuncio(90)], {}, 300, reserva=60, p=P)
        self.assertEqual(len(bueno), 1)
        ev = bueno[0]["ficha"]
        self.assertGreaterEqual(ev["neto"], guardia.exigido_por_valor(ev, P))

    def test_lo_que_propone_lo_firma_el_guardia(self):
        o = cambista.oportunidades([anuncio(90)], {}, 300, reserva=60, p=P)[0]
        firma, motivo, _, _ = guardia.revisar(o["propuesta"], anuncio(90), {}, 300, P)
        self.assertTrue(firma, motivo)


class Candado(unittest.TestCase):
    def test_uno_solo_acepta(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "acepta.lock")
            self.assertEqual(candado.tomar(ruta, "rastro.py"), (True, ""))
            self.assertEqual(candado.quien_lo_tiene(ruta)["quien"], "rastro.py")
            self.assertTrue(candado.tomar(ruta, "otra vez el mismo")[0])          # el mismo proceso: sigue siendo suyo
            candado.soltar(ruta)
            self.assertIsNone(candado.quien_lo_tiene(ruta))

    def test_otro_proceso_vivo_bloquea_y_uno_muerto_no(self):
        import json
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, "acepta.lock")
            vivo = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
            try:
                with open(ruta, "w", encoding="utf-8") as f:
                    json.dump({"pid": vivo.pid, "quien": "play.py", "desde": 0}, f)
                ok, motivo = candado.tomar(ruta, "rastro.py", ahora=60)
                self.assertFalse(ok)
                self.assertIn("play.py", motivo)
            finally:
                vivo.kill()
                vivo.wait()
            self.assertTrue(candado.tomar(ruta, "rastro.py")[0])                # ya no corre: se libera
            candado.soltar(ruta)


class Hoy(unittest.TestCase):
    def test_venta_y_compra_encendidas(self):
        pl = situacion.plan({"efectivo": 300, "cuenta": {}})
        self.assertEqual((pl["p"]["rastro.publicar"], pl["p"]["cambista.pedir"]), (1, 1))

    def test_datos_reales_en_el_repositorio(self):
        self.assertTrue(os.path.exists(os.path.join(RAIZ, "datos", "estado-actual.json")))


if __name__ == "__main__":
    unittest.main()


class FormasReales(unittest.TestCase):
    """Formas vistas en el juego real el 3/10 en la prueba en seco (sin claves)."""
    DUELO = {"duel": 2334, "session": 2, "status": "live", "role": "buyer", "item": "La Heroína del Dos de Mayo",
             "issues": ["price"], "your_days_weight": None, "your_limit": 150, "rival": "Rival Verde",
             "deadline_tick": 523, "decay_per_round": 0.06, "rounds": 3,
             "your_offer": {"id": 3887, "price": 89, "tick": 511, "days": 0},
             "rival_offer": {"id": 3906, "price": 139, "tick": 511, "days": 0},
             "messages": [{"tick": 511, "from": "Rival Verde", "text": "I will meet you partway at 139 P.", "price": 139}]}

    @unittest.skip("falta el programa que juegue duelos y vendedores: director.py se quitó (rastro.py solo hace El Rastro)")
    def test_duelo_y_vendedores_reales(self):
        import director

        class Juego:
            def me(self):
                return {"name": "Team 7", "cash": 184, "assets": []}

            def duels(self):
                return {"duels": [FormasReales.DUELO, dict(FormasReales.DUELO, duel=1, status="done")]}

            def dealers(self):
                return {"personas": [{"id": "abuela", "level": 1, "status": "active"},
                                     {"id": "pilar", "level": 3, "status": "active"}]}

        est = {"hilos": {}, "duelos": {}}
        lectura, _ = director.leer(Juego(), est, 512)
        d = lectura["duelos"]
        self.assertEqual(len(d), 1)                                       # el terminado no se juega
        self.assertEqual((d[0]["id"], d[0]["rival"], d[0]["nuestras"], d[0]["ticks_restantes"], d[0]["rondas"]),
                         (2334, [139], [89], 11, 3))
        self.assertIn("139", d[0]["texto"])
        director.vendedores_nuevos(Juego(), est, {})
        self.assertEqual(est["niveles"], {"abuela": 1, "pilar": 3})
