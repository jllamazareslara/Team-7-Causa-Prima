"""El Guion, sin red: el calendario real del 3/10 (datos/calendario-03-10.json) y la jugada de cada evento."""
import json
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
from t7 import guion, novedades  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
