"""La Duelista por ticks (Duels III y la final), sin red: las reglas del juego medidas en los duelos reales del 3/10
y lo que la Duelista hace con ellas. Todo pasa por el programa de verdad (duelos.leer → cadena.tick → Guardia)."""
import contextlib
import io
import json
import os
import random
import re
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
import duelos  # noqa: E402
from sim import duelos_vivo as V  # noqa: E402
from t7 import cadena, duelo  # noqa: E402

duelos._linea = lambda *a, **k: None          # las pruebas no escriben en runs/
AJUSTES_DE_VERDAD = duelos.ajustes


def ajustes(**cambios):
    """Ajustes fijos para las pruebas (no dependen de lo que diga hoy.json ese día)."""
    base = {"duelo.apertura_vendedor": 1.6, "duelo.apertura_comprador": 0.6, "duelo.dureza_beta": 0.6}
    return AJUSTES_DE_VERDAD({"duelo": {"rondas": 12, "descuento_ronda": 0.9},
                           "ajustes": dict(base, **{k.replace("__", "."): v for k, v in cambios.items()})})


def reales():
    with open(os.path.join(RAIZ, "datos", "duelos-reales-03-10.json"), encoding="utf-8") as f:
        return json.load(f)["duels"]


def jugar(juego, ticks=V.T_DUELO, p=None):
    """El programa real contra el juego falso. Devuelve los diarios de cada tick."""
    est, mem, diarios = {}, cadena.Memoria(), []
    p = p or ajustes()
    duelos.ajustes = lambda hoy=None: p
    try:
        for _ in range(ticks):
            juego.rivales(antes=True)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                ok = duelos.un_tick(juego, est, mem, juego.tick, True, False)
            diarios.append((ok, buf.getvalue()))
            juego.rivales(antes=False)
            juego.avanzar()
    finally:
        duelos.ajustes = AJUSTES_DE_VERDAD
    return diarios


class ReglasMedidas(unittest.TestCase):
    """Lo que el juego hace de verdad, comprobado duelo a duelo. Si un día deja de cumplirse, la Duelista por ticks
    hay que revisarla: se apoya en esto."""

    def test_el_resultado_es_ganancia_por_decay_elevado_a_rondas(self):
        vistos = 0
        for d in reales():
            if d.get("status") != "deal":
                continue
            signo = 1 if d["role"] == "seller" else -1
            g = signo * (d["price"] - d["your_limit"])
            if "days" in d["issues"]:
                g += signo * d["your_days_weight"] * (d["days"] or 0)      # vendiendo suma, comprando cuesta
            esperado = g * (1 - d["decay_per_round"]) ** d["rounds"] if g > 0 else g
            self.assertAlmostEqual(esperado, d["result"], delta=0.11, msg=f"duelo {d['duel']}")
            vistos += 1
        self.assertGreaterEqual(vistos, 59)

    def test_las_rondas_son_los_mensajes_del_que_menos_ha_escrito(self):
        for d in reales():
            if d.get("status") not in ("deal", "no_deal"):
                continue
            nuestros = sum(1 for m in d["messages"] if m["from"] == "you")
            suyos = sum(1 for m in d["messages"] if m["from"] != "you")
            self.assertEqual(d["rounds"], min(nuestros, suyos), f"duelo {d['duel']}")

    def test_el_sentido_del_dia_es_siempre_el_mismo(self):
        for d in reales():
            if "days" in d["issues"]:
                self.assertIn("adds" if d["role"] == "seller" else "costs", d["days_meaning"], f"duelo {d['duel']}")


class NoQuemarRondas(unittest.TestCase):
    def test_con_rival_mudo_escucha_un_tick_y_luego_baja_sin_repetir(self):
        """El 3/10 mandamos «40 P?» once veces seguidas. Ahora: primer tick callados, y después cada oferta es
        distinta de la anterior, baja siempre y nunca cruza el límite."""
        j = V.Juego(random.Random(1))
        d = j.abrir("seller", 100, 160, 2.0, 2.0, "ausente", V.ausente)
        jugar(j)
        nuestros = [m for m in d["msgs"] if m["from"] == "you"]
        self.assertEqual([m for m in nuestros if m["tick"] == d["t0"]], [])
        self.assertGreaterEqual(len(nuestros), 5)
        valen = [m["price"] + 2.0 * m["days"] for m in nuestros]                 # lo que nos da cada oferta
        for a, b in zip(nuestros, nuestros[1:]):
            self.assertNotEqual((a["price"], a["days"]), (b["price"], b["days"]))
        self.assertEqual(valen, sorted(valen, reverse=True))
        self.assertGreater(min(valen), 100)
        self.assertTrue(all(m["price"] >= 100 and 0 <= m["days"] <= 10 for m in nuestros))

    def test_al_rival_que_camina_solo_no_se_le_escribe(self):
        """Duelo real 5633: Rival Sol subió solo de 32 a 72. Con un mensaje nuestro sacamos 16,6; callados y
        aceptando al final, el trato entra entero."""
        real = next(d for d in reales() if d["duel"] == 5633)
        rep = V.Repetido(real)
        duelos.ajustes = lambda hoy=None: ajustes()
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                puntos, rondas = rep.jugar(duelos, cadena)
        finally:
            duelos.ajustes = AJUSTES_DE_VERDAD
        self.assertEqual([m for m in rep.msgs if m["from"] == "you"], [])
        self.assertEqual(rondas, 0)
        self.assertGreaterEqual(puntos, 16.6)

    def test_una_oferta_mejor_que_nuestra_apertura_se_coge_sin_hablar(self):
        for numero, minimo in ((6088, 60.2), (5810, 45.4)):
            real = next(d for d in reales() if d["duel"] == numero)
            rep = V.Repetido(real)
            duelos.ajustes = lambda hoy=None: ajustes(duelo__apertura_vendedor=1.35)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    puntos, rondas = rep.jugar(duelos, cadena)
            finally:
                duelos.ajustes = AJUSTES_DE_VERDAD
            self.assertEqual(rondas, 0, numero)
            self.assertAlmostEqual(puntos, minimo, delta=0.1, msg=numero)


class NuncaFueraDelLimite(unittest.TestCase):
    def test_un_buen_precio_con_el_dia_en_contra_no_se_acepta(self):
        """Duelos reales 5635 (−4,2) y 5888 (−3,1): el precio estaba dentro del límite, pero el día 10 costaba más."""
        for numero in (5635, 5888):
            real = next(d for d in reales() if d["duel"] == numero)
            rep = V.Repetido(real)
            with contextlib.redirect_stdout(io.StringIO()):
                puntos, _ = rep.jugar(duelos, cadena)
            self.assertGreaterEqual(puntos, 0, numero)

    def test_todos_los_duelos_reales_repetidos_sin_un_trato_que_reste(self):
        r = V.repetir_reales({"duelo.apertura_vendedor": 1.6, "duelo.apertura_comprador": 0.6, "duelo.dureza_beta": 0.6})
        self.assertEqual(r["fuera"], 0)
        self.assertGreaterEqual(r["duelos"], 60)
        # aceptando solo ofertas que el rival hizo de verdad ya se saca más de lo que pasó (799 P), tratos suyos incluidos
        self.assertGreater(r["repetido"], r["real"])

    def test_mil_duelos_inventados_sin_un_trato_que_reste_ni_un_error(self):
        hechos, errores, rechazos = V.torneo(n=400, semilla=5, ajustes={})
        self.assertEqual(errores, 0)
        self.assertEqual(rechazos, [])                               # ni dos aceptaciones en un tick, ni mensaje sin día
        self.assertEqual([d["id"] for d in hechos if d["resultado"] < 0], [])
        self.assertGreater(sum(d["estado"] == "deal" for d in hechos) / len(hechos), 0.6)

    def test_el_texto_dice_el_precio_que_se_escribe(self):
        """Con día de entrega la Duelista piensa en precio efectivo; lo que se manda (y lo que dice el texto) es el
        precio escrito. Un texto con otro número es un candidato a que el rival nos señale por mala fe."""
        j = V.Juego(random.Random(3))
        tanda = [j.abrir(rol, 80, 130, 4.5, 2.0, "ausente", V.ausente) for rol in ("seller", "buyer")]
        vistos = []
        original = j.duel_say

        def espia(duel_id, text="", price=None, days=None):
            vistos.append((text, price, days))
            return original(duel_id, text, price=price, days=days)
        j.duel_say = espia
        jugar(j)
        self.assertGreater(len(vistos), 8)
        for texto, precio, dias in vistos:
            self.assertEqual({int(n) for n in re.findall(r"\d+", texto)} - {precio}, set(), texto)
            self.assertTrue(0 <= dias <= 10)
        for d in tanda:
            for m in d["msgs"]:
                self.assertTrue(m["price"] >= 80 if d["rol"] == "seller" else m["price"] <= 130)


class CierreATiempo(unittest.TestCase):
    def test_cuatro_duelos_que_acaban_a_la_vez_cierran_los_cuatro(self):
        """El juego deja UNA aceptación por equipo y tick. El 3/10 se esperó al último tick con varios duelos a la
        vez y cinco tratos dentro del límite se quedaron sin cerrar (2367, 2467, 2487, 2550, 2551)."""
        j = V.Juego(random.Random(2))
        tanda = [j.abrir("seller" if i % 2 == 0 else "buyer", 100, 150, 1.0, 1.0, "firme", V.firme(0.2, cede=1.0, politica="cinco"))
                 for i in range(4)]
        jugar(j)
        self.assertEqual([d["estado"] for d in tanda], ["deal"] * 4)
        self.assertEqual(j.rechazos, [])
        self.assertTrue(all(d["resultado"] > 0 for d in tanda))

    def test_los_turnos_de_cierre_son_distintos(self):
        ds = [{"id": i, "rol": "seller", "limite": 100, "x": {"plazo": 50, "riv": []}} for i in range(4)]
        ds.append({"id": 9, "rol": "seller", "limite": 100, "x": {"plazo": 60, "riv": []}})
        duelos.repartir_turnos(ds)
        self.assertEqual(sorted(d["x"]["turno"] for d in ds[:4]), [0, 1, 2, 3])
        self.assertEqual(ds[4]["x"]["turno"], 0)                                 # otro plazo, otra cola

    def test_sin_tiempo_acepta_lo_que_hay_dentro_del_limite(self):
        x = {"tick": 20, "quedan": 2, "edad": 10, "turno": 0, "n_nos": 1, "n_riv": 3, "nos": [[11, 150, 150, None]],
             "riv": [[10, 104, 104, None], [11, 104, 104, None], [12, 104, 104, None]], "vigente": [104, 104, None],
             "dos": False, "k": None}
        accion, precio, _, _ = duelo.decidir_vivo({"rol": "seller", "limite": 100, "x": x}, ajustes())
        self.assertEqual((accion, precio), ("aceptar", 104))
        x["vigente"] = [99, 99, None]                                            # fuera del límite: jamás
        self.assertNotEqual(duelo.decidir_vivo({"rol": "seller", "limite": 100, "x": x}, ajustes())[0], "aceptar")


class OfertaCambiada(unittest.TestCase):
    """Aceptar cierra con lo que esté en pie en ese momento: si el rival cambia su oferta a peor entre que leemos y
    aceptamos, no se acepta."""
    BASE = {"duel": 4, "status": "live", "role": "buyer", "your_limit": 120, "issues": ["price", "days"],
            "your_days_weight": 3.0, "days_meaning": "each delivery day costs you this much cash", "deadline_tick": 40,
            "rounds": 0, "rival_offer": {"price": 80, "days": 0}, "your_offer": None,
            "messages": [{"tick": 30, "from": "Rival Oro", "text": "", "price": 80, "days": 0}]}

    def jugar(self, despues, tick=38, primero=None):
        primero = dict(primero or self.BASE)

        class Juego:
            lecturas, aceptados = 0, []

            def duels(self, done=False):
                Juego.lecturas += 1
                return {"duels": [primero if Juego.lecturas == 1 else despues]}

            def duel_say(self, *a, **k):
                pass

            def duel_accept(self, duel_id):
                Juego.aceptados.append(duel_id)
        with contextlib.redirect_stdout(io.StringIO()):
            duelos.un_tick(Juego(), {}, cadena.Memoria(), tick, True, False)
        return Juego.aceptados

    def test_si_sigue_igual_se_acepta(self):
        self.assertEqual(self.jugar(dict(self.BASE)), [4])

    def test_si_la_cambia_a_peor_no_se_acepta(self):
        fuera = dict(self.BASE, rival_offer={"price": 110, "days": 10})        # 120 − 110 − 30 = −20: ni con el plazo encima
        self.assertEqual(self.jugar(fuera), [])
        # con tiempo por delante: una oferta muy buena (70 a día 0, +50) se coge en el acto...
        buena = dict(self.BASE, rival_offer={"price": 70, "days": 0},
                     messages=[{"tick": 30, "from": "Rival Oro", "text": "", "price": 70, "days": 0}])
        self.assertEqual(self.jugar(dict(buena), tick=31, primero=buena), [4])
        # ...pero si al ir a aceptar ya es 70 a día 10 (+20), no: se vuelve a decidir en el tick siguiente
        cambiada = dict(buena, rival_offer={"price": 70, "days": 10})
        self.assertEqual(self.jugar(cambiada, tick=31, primero=buena), [])

    def test_con_el_plazo_encima_algo_dentro_del_limite_se_acepta(self):
        peor = dict(self.BASE, rival_offer={"price": 80, "days": 10})          # +10: peor que lo firmado, pero es el final
        self.assertEqual(self.jugar(peor, tick=39), [4])


class Ajustes(unittest.TestCase):
    def test_hoy_json_manda_sobre_parametros(self):
        p = duelos.ajustes({"duelo": {"rondas": 12, "descuento_ronda": 0.9},
                            "ajustes": {"duelo.apertura_vendedor": 1.8, "tienda.venta.paso_fijo": 0.3, "duelo.no_existe": 1}})
        self.assertEqual((p["duelo.rondas"], p["duelo.descuento_ronda"], p["duelo.apertura_vendedor"]), (12, 0.9, 1.8))
        self.assertNotEqual(p["tienda.venta.paso_fijo"], 0.3)                    # solo toca lo de los duelos
        self.assertNotIn("duelo.no_existe", p)

    def test_un_hoy_json_roto_no_para_los_duelos(self):
        p = duelos.ajustes("esto no es un objeto")
        self.assertIn("duelo.apertura_vendedor", p)
        self.assertTrue(any("hoy.json" in a for a in p["_avisos"]))

    def test_el_objeto_no_es_el_escenario(self):
        """El mismo objeto sale con límites distintos en cada duelo: guardar «el límite del rival» por objeto hacía
        creer que no había tarta y dejaba duelos sin jugar."""
        class Juego:
            def duels(self, done=False):
                return {"duels": [{"duel": 1, "role": "seller", "your_limit": 83, "item": "El Tren Fantasma",
                                   "issues": ["price"], "deadline_tick": 30, "rounds": 0, "messages": []}]}
        self.assertIsNone(duelos.leer(Juego(), {}, 20)["duelos"][0]["escenario"])


class Robustez(unittest.TestCase):
    def test_duelos_rotos_no_tiran_el_tick_ni_firman_nada_raro(self):
        """Campos que faltan, tipos que no tocan, números absurdos: el tick sigue y no se acepta nada que reste."""
        rng = random.Random(7)
        raros = [None, "", "x", -5, 0, 10 ** 9, 3.7, [], {}, True, [1, 2], {"price": "caro"}, float("1e300")]
        bueno = {"duel": 1, "status": "live", "role": "buyer", "your_limit": 120, "issues": ["price", "days"],
                 "your_days_weight": 3.0, "days_meaning": "each delivery day costs you this much cash", "deadline_tick": 40,
                 "rounds": 1, "rival": "Rival Oro", "rival_offer": {"price": 90, "days": 4},
                 "your_offer": {"price": 70, "days": 0},
                 "messages": [{"tick": 28, "from": "Rival Oro", "text": "hola", "price": 95, "days": 4},
                              {"tick": 29, "from": "you", "text": "70", "price": 70, "days": 0},
                              {"tick": 30, "from": "Rival Oro", "text": "", "price": 90, "days": 4}]}
        for caso in range(400):
            d = json.loads(json.dumps(bueno))
            for _ in range(rng.randint(1, 3)):
                sitios = [d] + [m for m in d.get("messages") or [] if isinstance(m, dict)] if isinstance(d.get("messages"), list) else [d]
                if isinstance(d.get("rival_offer"), dict):
                    sitios.append(d["rival_offer"])
                donde = rng.choice([x for x in sitios if x])
                clave = rng.choice(sorted(donde))
                if rng.random() < 0.3:
                    donde.pop(clave)
                else:
                    donde[clave] = rng.choice(raros)

            class Juego:
                aceptados = []

                def duels(self, done=False):
                    return {"duels": [d, 7, None]}

                def duel_say(self, *a, **k):
                    pass

                def duel_accept(self, duel_id):
                    Juego.aceptados.append(duel_id)
            with contextlib.redirect_stdout(io.StringIO()) as salida:
                tick = rng.choice([31, 37, 38, 39])
                self.assertTrue(duelos.un_tick(Juego(), {}, cadena.Memoria(), tick, True, False), f"caso {caso}: {d}")
            self.assertNotIn("ERROR       ", salida.getvalue().replace("ERROR      duelo", ""), f"caso {caso}: {d}")
            if Juego.aceptados:                                    # si acepta, es que lo que hay en pie nos deja ganancia
                ro = d.get("rival_offer")
                self.assertIsInstance(ro, dict, f"caso {caso}")
                precio, dias = ro.get("price"), ro.get("days")
                self.assertIsInstance(precio, (int, float), f"caso {caso}")
                peso = d.get("your_days_weight")
                coste_dia = (peso if isinstance(peso, (int, float)) and not isinstance(peso, bool) else 0) * \
                    (dias if isinstance(dias, (int, float)) and not isinstance(dias, bool) else 0)
                self.assertGreaterEqual(d["your_limit"] - precio - coste_dia, 0, f"caso {caso}: {d}")

    def test_misma_situacion_misma_decision(self):
        x = {"tick": 14, "quedan": 8, "edad": 4, "turno": 1, "n_nos": 1, "n_riv": 2, "nos": [[11, 60, 60, 0]],
             "riv": [[10, 131, 91, 10], [12, 126, 86, 10]], "vigente": [126, 86, 10], "dos": True, "k": 4.0}
        st = {"rol": "buyer", "limite": 120, "x": x}
        p = ajustes()
        self.assertEqual(duelo.decidir_vivo(st, p), duelo.decidir_vivo(json.loads(json.dumps(st)), p))
        self.assertEqual(duelo.decidir(st, p)[:2], duelo.decidir_vivo(st, p)[:2])


if __name__ == "__main__":
    unittest.main()
