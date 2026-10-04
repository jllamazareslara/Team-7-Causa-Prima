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
            self.assertEqual(candado.tomar(ruta, "jugar.py"), (True, ""))
            self.assertEqual(candado.quien_lo_tiene(ruta)["quien"], "jugar.py")
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
                ok, motivo = candado.tomar(ruta, "jugar.py", ahora=60)
                self.assertFalse(ok)
                self.assertIn("play.py", motivo)
            finally:
                vivo.kill()
                vivo.wait()
            self.assertTrue(candado.tomar(ruta, "jugar.py")[0])                # ya no corre: se libera
            candado.soltar(ruta)


class Hoy(unittest.TestCase):
    def test_hoy_compra_y_vende_agresivo(self):
        """Decisión del equipo (4/10): el Guardia compra y vende (sin solo_vender), con perfil agresivo:
        reserva 30, márgenes del 5 % y protegidas a 1,2 ×."""
        pl = situacion.plan({"efectivo": 300, "cuenta": {}})
        self.assertEqual((pl["p"]["rastro.publicar"], pl["p"]["cambista.pedir"], pl["ordenes"]["compras"]), (1, 1, "todas"))
        self.assertEqual((pl["p"]["guardia.reserva_efectivo"], pl["p"]["guardia.margen_compra"], pl["p"]["guardia.margen_venta"],
                          pl["p"]["guardia.protegida_factor"]), (30, 0.05, 0.05, 1.2))
        self.assertTrue(pl["ordenes"]["cerrar_en_rastro"])

    def test_solo_vender_sin_completar_no_pide(self):
        pl = situacion.plan({"efectivo": 300, "cuenta": {}}, hoy={"solo_vender": True, "ajustes": {"cambista.pedir": 1}})
        self.assertEqual((pl["p"]["cambista.pedir"], pl["ordenes"].get("pedir_completar")), (0, None))

    def test_la_carta_que_cierra_la_pagina_no_se_compra_a_un_vendedor(self):
        from t7 import cadena
        cuenta = {f"RET-0{i}": 1 for i in range(1, 10)}                       # falta solo RET-10
        menus = {"picaros": {"vende": {"RET-10": 63}, "compra": {}}}
        ordenes = {"compras": "ninguna", "completar": ["RET"], "reserva": 0, "margen_completar": 1.2}
        con = cadena.cola_de_operaciones(cuenta, 500, menus, ordenes)
        sin = cadena.cola_de_operaciones(cuenta, 500, menus, dict(ordenes, cerrar_en_rastro=True))
        self.assertEqual(([o["carta"] for o in con], sin), (["RET-10"], []))

    def test_sin_solo_vender_se_compra(self):
        pl = situacion.plan({"efectivo": 300, "cuenta": {}}, hoy={"ajustes": {"cambista.pedir": 1}})
        self.assertEqual((pl["p"]["cambista.pedir"], pl["ordenes"]["compras"]), (1, "todas"))

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

    def test_vendedores_reales(self):
        import tempfile
        import jugar
        jugar.RUNS = tempfile.mkdtemp()

        class Juego:
            def dealers(self):
                return {"personas": [{"id": "abuela", "level": 1, "status": "active"},
                                     {"id": "pilar", "level": 3, "status": "active"}]}

        est = {"hilos": {}}
        self.assertEqual(jugar.vendedores_nuevos(Juego(), est, {}), ["abuela", "pilar"])
        self.assertEqual(est["niveles"], {"abuela": 1, "pilar": 3})

    @unittest.skip("falta el programa que juegue duelos: jugar.py hace vendedores y El Rastro, no duelos")
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


class TablonSinNosotros(unittest.TestCase):
    def test_nuestros_anuncios_no_cuentan_como_competencia(self):
        """El juego firma las ofertas con un identificador (m5e6…), no con el nombre del equipo."""
        import jugar as rastro                                   # rastro.py es ahora jugar.py

        class Juego:
            def me(self):
                return {"id": "t07", "name": "Team 7", "cash": 78, "assets": [{"id": 274, "kind": "card", "ref": "MAL-04"}]}

            def board(self, venue):
                return {"offers": [
                    {"id": 1, "maker": "m5e679080", "give": {"assets": [{"id": 274, "ref": "MAL-04"}]}, "want": {"cash": 9},
                     "created_tick": 580, "expires_tick": 600},
                    {"id": 2, "maker": "m5e679080", "give": {"cash": 4}, "want": {"types": ["card:RET-02"]}},
                    {"id": 9, "maker": "m5e679080", "give": {"assets": [{"id": 651, "ref": "MAL-01"}]}, "want": {"cash": 14}},
                    {"id": 3, "maker": "mcd38ffd5", "give": {"assets": [{"id": 8345, "ref": "MAL-04"}]}, "want": {"cash": 7}}]}

            def my_offers(self):                                  # otro programa del equipo anunció la 9: también es nuestra
                return {"offers": [{"id": 9, "maker": "t07", "give": {"assets": [{"id": 651, "ref": "MAL-01"}]}},
                                   {"id": 3, "maker": "abuela", "to": "t07", "give": {"assets": [{"id": 730}]}}]}   # nos la hacen: no es nuestra

        est = {"anuncios": {}}                                    # nada en nuestro registro: solo lo que dice el juego
        with tempfile.TemporaryDirectory() as d:
            runs, rastro.RUNS = getattr(rastro, "RUNS", None), d
            try:
                lectura, _ = rastro.leer(Juego(), est, 581)
            finally:
                rastro.RUNS = runs
        self.assertEqual([o["id"] for o in lectura["tablon"]], [3])       # ni nuestro anuncio ni nuestra petición
        self.assertEqual(est["ocupadas_juego"], ["651"])                  # esa carta ya está comprometida: ni se anuncia ni se da
        me = {"assets": [{"id": 651, "kind": "card", "ref": "MAL-01"}]}
        self.assertIsNone(rastro.cartas_para({"want": {"types": ["card:MAL-01"]}}, me, est))
        self.assertEqual(rastro.cartas_para({"want": {"types": ["card:MAL-01"]}}, me, {}), [651])
        self.assertEqual(est["anuncio_dura"], 20)                         # pedimos 40: el juego da 20, y se aprende
        self.assertEqual(rastro._dura(est), 20)
        self.assertEqual(rastro._dura({}), rastro.ANUNCIO_VIVE)


class CambioCartaPorCarta(unittest.TestCase):
    """La oferta 8885 del 03/10, tal cual: dan LAV-08 y piden want.types = ["card:LAV-06"]. Se firmó creyendo dar 0."""
    OFERTA = {"id": 8885, "maker": "m89046474",
              "give": {"cash": 0, "assets": [{"id": 718, "kind": "card", "ref": "LAV-08"}], "types": []},
              "want": {"cash": 0, "assets": [], "types": ["card:LAV-06"]}}

    def test_la_carta_que_damos_cuenta(self):
        self.assertEqual(cambista.pedidas(self.OFERTA["want"]), ["LAV-06"])
        self.assertEqual(cambista.pedidas({"cards": ["LAT-03"]}), ["LAT-03"])
        self.assertIsNone(cambista.pedidas({"types": ["pack:LAV"]}))                # no sabemos valorarlo: no se toca
        cuenta = {"LAV-06": 2, "LAV-08": 1}                                         # repetida por repetida, y la comisión
        self.assertEqual(cambista.oportunidades([self.OFERTA], cuenta, 78, reserva=60, p=P), [])
        raro = dict(self.OFERTA, want={"cash": 0, "types": ["pack:LAV"]})
        self.assertEqual(cambista.oportunidades([raro], cuenta, 78, reserva=60, p=P), [])

    def test_el_ojeador_ve_la_demanda(self):
        from t7 import ojeador
        mercado, demanda = {}, {}
        ojeador.apuntar_mercado(mercado, [{"id": 1, "maker": "mab", "give": {"cash": 10, "assets": [], "types": []},
                                          "want": {"cash": 0, "assets": [], "types": ["card:RET-02"]}}], demanda)
        self.assertEqual(demanda, {"RET-02": [10]})


if __name__ == "__main__":
    unittest.main()
