"""El Guion, sin red: el calendario real del 3/10 (datos/calendario-03-10.json) y la jugada de cada evento."""
import json
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
from t7 import comerciante, guion, novedades, params  # noqa: E402

P = params.cargar()

with open(os.path.join(RAIZ, "datos", "calendario-03-10.json"), encoding="utf-8") as _f:
    CAL = json.load(_f)
EVS = guion.eventos(CAL)
MULT = {"LAT": 1.6, "RET": 1.3, "LAV": 1.1, "CHA": 0.9, "SAL": 0.7, "MAL": 0.5}


class Guion(unittest.TestCase):
    def test_todos_los_eventos_tienen_jugada_conocida(self):
        self.assertEqual(len(EVS), len(CAL["upcoming"]))
        self.assertEqual([e for e in EVS if guion.jugada(e)["clave"] == "otro"], [])

    def test_fiebre_salamanca(self):
        f = guion.fiebres(EVS)
        self.assertEqual(len(f), 1)
        self.assertEqual((f[0]["vendedor"], f[0]["barrio"], f[0]["pct"], f[0]["hasta"]), ("pilar", "SAL", 25.0, "17:30"))
        self.assertAlmostEqual(f[0]["hasta_h"], 11.15)

    def test_guardar_salamanca_antes_y_durante_y_soltar_despues(self):
        cuenta = {"SAL-01": 2, "SAL-03": 1, "LAT-02": 1}
        self.assertEqual(guion.bloqueadas(cuenta, EVS, 1.0), [])               # más de 6 h antes: libre
        self.assertEqual(guion.bloqueadas(cuenta, EVS, 3.825), ["SAL-01", "SAL-03"])
        self.assertEqual(guion.bloqueadas(cuenta, EVS, 10.0), ["SAL-01", "SAL-03"])
        self.assertEqual(guion.bloqueadas(cuenta, EVS, 11.2), [])              # la fiebre ya se rompió

    def test_venta_fiebre_solo_con_margen_y_nunca_romper_pagina(self):
        f = guion.fiebres(EVS)[0]
        venta = guion.venta_fiebre({"SAL-01": 2, "SAL-09": 1, "LAT-02": 1}, f, MULT)
        refs = [v["ref"] for v in venta]
        self.assertNotIn("LAT-02", refs)
        self.assertEqual(refs.count("SAL-01"), 2)                              # 12,5 P frente a 7 y 1,75: las dos
        self.assertTrue(all(v["margen"] > 0 and v["precio_fiebre"] > v["nos_vale"] for v in venta))
        self.assertEqual(venta, sorted(venta, key=lambda v: -v["margen"]))
        pagina = {f"SAL-{i:02d}": 1 for i in range(1, 11)}                     # página completa: nada se vende suelto
        self.assertEqual(guion.venta_fiebre(pagina, f, MULT), [])

    def test_duelos_proponen_descuento_y_dia(self):
        d2 = next(e for e in EVS if e["params"].get("name") == "Duels II")
        j = guion.jugada(d2)
        self.assertEqual(j["hoy"], {"duelo": {"descuento_ronda": 0.92}})
        self.assertTrue(any("days" in x for x in j["antes"]))
        self.assertTrue(any("sin respuesta" in x for x in j["antes"]))

    def test_aviso_con_antelacion(self):
        ya = guion.ahora(EVS, 4.8)
        self.assertIn("Duels I", [j["titulo"] for _, j, _ in ya["preparar"]])
        self.assertEqual(ya["activo"], [])
        fiebre = guion.ahora(EVS, 7.5)                                          # 1 h 39 min antes: dentro de las 2 h
        self.assertIn("fiebre", [j["clave"] for _, j, _ in fiebre["preparar"]])
        self.assertEqual(len(guion.ahora(EVS, 10.0)["activo"]), 1)

    def test_hora_de_pared(self):
        self.assertEqual(guion.hora(16.7, EVS).strftime("%H:%M"), "09:32")     # domingo, anclado a day_opens
        self.assertEqual(guion.hora(5.15, EVS, (3.825, "10:10")).strftime("%H:%M"), "11:29")

    def test_linea_de_tiempo_y_niveles_sin_anunciar(self):
        texto = guion.linea_de_tiempo(EVS, 3.825, (3.825, "10:10"), {"SAL-01": 2})
        self.assertIn("Fiebre SAL", texto)
        self.assertIn("FIEBRE SAL: vender a pilar SAL-01", texto)
        self.assertIn("mala fe", " ".join(guion.sin_anunciar("radio")["antes"]))

    def test_el_vigia_avisa_con_el_calendario_en_horas(self):
        def lect(h):
            return {"clock": {"tick": 1, "tick_seconds": 30, "paused": False, "limits": {}},
                    "schedule": dict(CAL, now_hours=h), "levels": [], "dealers": [], "catalog": {"sets": []},
                    "venues": [], "me": None}
        antes, ahora = novedades.foto(lect(7.0)), novedades.foto(lect(7.5))
        nov = novedades.comparar(antes, ahora)
        fiebre = [n for n in nov if n["tipo"] == "pronto" and "Fiebre" in n["titulo"]]
        self.assertEqual(len(fiebre), 1)
        self.assertTrue(any("NO vender" in c for c in novedades.consejo(fiebre[0])))
        self.assertEqual([n for n in novedades.comparar(ahora, novedades.foto(lect(7.6))) if "Fiebre" in n["titulo"]], [])


class Plan(unittest.TestCase):
    """Lo añadido con el plan del sábado: reservas para la fiebre, niveles, rumores, valor de sobres, grabador."""

    def test_reservadas_antes_nadie_durante_solo_pilar(self):
        cuenta = {"SAL-01": 2, "LAT-02": 1}
        self.assertEqual(guion.reservadas(cuenta, EVS, 5.0), {"SAL-01": None})
        self.assertEqual(guion.reservadas(cuenta, EVS, 9.5), {"SAL-01": "pilar"})
        self.assertEqual(guion.reservadas(cuenta, EVS, 11.5), {})

    def test_cola_respeta_fiebre_y_niveles(self):
        from t7 import cadena
        cuenta = {"SAL-01": 3, "MAL-02": 3}
        menus = {"abuela": {"compra": {"SAL-01": 6, "MAL-02": 4}}, "pilar": {"compra": {"SAL-01": 12}}}
        antes = comerciante.cola_de_operaciones(cuenta, 200, menus, guardar={"SAL-01": None})
        self.assertNotIn("SAL-01", [o["carta"] for o in antes])                     # a nadie antes de la fiebre
        durante = comerciante.cola_de_operaciones(cuenta, 200, menus, guardar={"SAL-01": "pilar"},
                                             niveles={"abuela": 1, "pilar": 3})
        self.assertEqual(durante[0], {"vendedor": "pilar", "lado": "venta", "carta": "SAL-01", "lista": 12})
        self.assertEqual(next(o for o in durante if o["vendedor"] == "abuela")["carta"], "MAL-02")

    def test_rumores(self):
        self.assertEqual(guion.rumor("Dicen que Pilar tendrá fiebre por Salamanca", EVS, 3.8)[0], "confirmado")
        self.assertEqual(guion.rumor("El Chato regala sobres de oro esta noche", EVS, 3.8)[0], "sin_confirmar")

    def test_peso_del_nivel_en_la_escalera(self):
        from t7 import prioridad
        self.assertAlmostEqual(prioridad.mejora_escalera([0.5], 0.6, nivel=3), 3 * prioridad.mejora_escalera([0.5], 0.6))

    def test_ev_sobre_a_nuestros_valores(self):
        from t7 import valor as V
        barrio = {"id": "sobre_barrio", "slots": [{"common": 1.0}, {"common": 1.0}, {"common": 0.75, "uncommon": 0.25}],
                  "expected_book": 33.8}
        lat = V.ev_sobre(barrio, {}, precio=30, barrios=["LAT"], mult=MULT)
        mal = V.ev_sobre(barrio, {}, precio=30, barrios=["MAL"], mult=MULT)
        self.assertAlmostEqual(lat["ev"], 33.75 * 1.6, delta=0.2)                   # colección vacía: libro × multiplicador
        self.assertTrue(lat["conviene"])
        self.assertFalse(mal["conviene"])

    def test_grabador_normaliza_y_rejuega(self):
        import tempfile
        import grabador
        crudas = [{"id": "b1-1", "side": "buy", "price": 30}, {"id": "b1-2", "side": "sell", "price": 20},
                  {"id": "b1-3", "give": {"cash": 25}, "want": {"cards": ["X"]}}, {"id": "b1-4", "want": {"cash": 22}},
                  {"id": "raro"}]
        norm = grabador.normalizar(crudas)
        self.assertEqual([(o["id"], o["lado"], o["precio"]) for o in norm],
                         [("b1-1", "compra", 30), ("b1-2", "venta", 20), ("b1-3", "compra", 25), ("b1-4", "venta", 22)])
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "100.jsonl"), "w", encoding="utf-8") as f:
                for t in range(4):
                    f.write(json.dumps({"tick": 100 + t, "ordenes": norm}) + "\n")
            tabla = grabador.rejugar(d)
        self.assertEqual(tabla[0][1]["automatico"], 13)                             # (30−20) + (25−22)


class OjosYComerciante(unittest.TestCase):
    """Sin Ojeador: los Ojos guardan el tablón, el feed y los descansos; el Comerciante elige canal con eso."""

    @staticmethod
    def tablon(precio, maker="t01", ref="LAT-09", lado="venta"):
        if lado == "venta":
            return [{"id": 1, "maker": maker, "give": {"assets": [{"ref": ref}]}, "want": {"cash": precio}}]
        return [{"id": 2, "maker": maker, "give": {"cash": precio}, "want": {"cards": [ref]}}]

    def test_historial_del_tablon(self):
        from t7 import ojos
        h = {}
        for i, p in enumerate([60, 56, 52, 48, 44]):
            ojos.observar(h, self.tablon(p, maker=f"t0{i % 3}"), 10 * i)
        ojos.observar(h, self.tablon(44, maker="t01"), 40)                    # misma oferta, mismo tick: no se repite
        self.assertEqual(len(h["LAT-09"]), 5)
        self.assertEqual(ojos.en_rastro(h, "LAT-09", 40), {"minimo": 44, "vendedores": 3, "compradores": 0})
        self.assertIsNone(ojos.en_rastro(h, "LAT-09", 400)["minimo"])         # lo viejo no cuenta
        self.assertEqual(ojos.en_rastro({}, "X-01", 0), {"minimo": None, "vendedores": 0, "compradores": 0})

    def test_feed_tolerante(self):
        from t7 import ojos
        h = {}
        ojos.observar_feed(h, {"events": [{"type": "settlement", "ref": "LAV-10", "price": 50, "tick": 5},
                                          {"type": "pack_opened", "ref": "LAV-01"}, "basura"]}, 6)
        self.assertEqual(h, {"LAV-10": [[5, 50, "trato", None]]})

    def test_descanso_de_vendedores(self):
        from t7 import ojos
        d = ojos.descanso("persona_quota", h=5.4, tick=300)
        self.assertEqual(d, {"hasta_h": 6.0})
        self.assertTrue(ojos.descansa(d, h=5.9) and not ojos.descansa(d, h=6.01))
        self.assertEqual(ojos.descanso("cooloff", tick=300, until_tick=340), {"hasta_tick": 340})
        self.assertEqual(ojos.descanso("sold_out", tick=300), {"hasta_tick": 420})   # sin hora de juego: en ticks
        self.assertIsNone(ojos.descanso("walked", h=5.0, tick=300))                   # se fue: se puede volver
        self.assertFalse(ojos.descansa(None, h=5.0))

    def test_el_comerciante_elige_canal(self):
        from t7 import ojos
        h = {}
        ojos.observar(h, self.tablon(5, ref="LAT-01"), 10)                    # en El Rastro: 5 → 7 con comisión
        self.assertEqual((comerciante.precio_rastro(h, "LAT-01", 20), comerciante.precio_rastro(h, "LAT-02", 20)), (7, None))
        s = {ref: {"rastro": comerciante.precio_rastro(h, ref, 20)} for ref in ("LAT-01", "LAT-02", "LAT-03")}
        menus = {"abuela": {"vende": {"LAT-01": 10, "LAT-02": 10, "LAT-03": 10}}}
        cuenta = {"LAV-01": 1}
        self.assertEqual(len(comerciante.cola_de_operaciones(cuenta, 300, menus, senales=s)), 1)   # sin escalera hecha, sigue
        hecha = comerciante.cola_de_operaciones(cuenta, 300, menus, tratos={"abuela": 3}, max_tratos=3, senales=s)
        self.assertEqual(hecha, [])                    # escalera hecha: solo compraría lo que completa página

    def test_todo_vive_en_la_cadena(self):
        """Quien lance la cadena solo pasa lecturas crudas: calendario, feed, tablón, cierres de vendedores."""
        from t7 import cadena
        mem = cadena.Memoria()
        lectura = {"tick": 100, "t_hours": 10.0, "calendario": CAL, "niveles": {"pilar": 3},
                   "feed": {"events": [{"type": "settlement", "ref": "MAL-01", "price": 9}]},
                   "tablon": self.tablon(7, ref="SAL-02"),
                   "vendedores": [{"vendedor": "abuela", "cerrado": "persona_quota", "suyas": [0], "nuestras": []}],
                   "cuenta": {"SAL-01": 2}, "efectivo": 300}
        cadena.ojear(lectura, mem)
        self.assertEqual((lectura["hora"], mem.niveles), (10.0, {"pilar": 3}))
        self.assertNotIn("momento", lectura)                                   # sin Ojeador: ni momento ni escasez
        self.assertEqual(mem.descansos["abuela"], {"hasta_h": 11.0})
        self.assertIn("MAL-01", mem.historial)
        self.assertEqual(mem.mercado, {"SAL-02": [7]})
        menus = {"abuela": {"compra": {"SAL-01": 5}}, "pilar": {"compra": {"SAL-01": 12}}}
        ops = comerciante.operaciones({"SAL-01": 2}, 300, menus, mem, lectura)
        self.assertEqual([(o["vendedor"], o["carta"]) for o in ops], [("pilar", "SAL-01")])   # abuela descansa; fiebre
        sin_reloj = {"tick": 220, "tick_segundos": 30}                      # 120 ticks después, sin t_hours
        self.assertAlmostEqual(cadena.hora_de_juego(mem, sin_reloj), CAL["now_hours"] + 1.0)
        mem2 = cadena.Memoria.de_dict(mem.a_dict())
        self.assertEqual((mem2.descansos, mem2.niveles), (mem.descansos, mem.niveles))
        anuncios = comerciante.anuncios({"SAL-01": 2, "MAL-02": 3}, P, mem, lectura)
        self.assertNotIn("SAL-01", [a["carta"] for a in anuncios])                          # espera a la fiebre
        self.assertTrue(anuncios and all(a["precio"] >= a["pierde"] + 1 for a in anuncios))

    def test_la_cadena_ya_no_espera(self):
        """Antes el Ojeador hacía esperar una compra que rentaba si el precio bajaba. Ahora decide la Contable."""
        from t7 import cadena
        mem = cadena.Memoria()
        acc = cadena.tick({"tick": 40, "efectivo": 300, "cuenta": {}, "tablon": self.tablon(94)}, mem)
        self.assertFalse(any("OJEADOR" in d for d in acc["diario"]))
        self.assertIn("LAT-09", mem.historial)
        self.assertIn("historial", cadena.Memoria.de_dict(mem.a_dict()).a_dict())


if __name__ == "__main__":
    unittest.main()
