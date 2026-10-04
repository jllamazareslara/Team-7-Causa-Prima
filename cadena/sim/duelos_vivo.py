"""Duelos por ticks, de punta a punta y sin red: un juego falso con las reglas MEDIDAS en los duelos reales del 3/10
hace jugar al programa de verdad (duelos.un_tick: leer → cadena.tick → Guardia → aplicar) contra rivales inventados.

    python sim/duelos_vivo.py                      600 duelos, tabla por tipo de rival
    python sim/duelos_vivo.py --n 2000 --semilla 7
    python sim/duelos_vivo.py --cadena RUTA        juega el código de otra carpeta cadena/ (para comparar con main)
    python sim/duelos_vivo.py --ajustes '{"duelo.paciencia": 1}'     prueba otros ajustes sin tocar archivos
    python sim/duelos_vivo.py --precio             duelos solo de precio
    python sim/duelos_vivo.py --reales             repite tick a tick los duelos reales grabados (suelo de lo que se saca)
    python sim/duelos_vivo.py --reales --datos datos/duelos-reales-04-10.json     lo mismo con los de hoy

Reglas del juego falso (las que salen de datos/duelos-reales-03-10.json, 83 duelos terminados sin excepción):
    ganancia   vendiendo precio − coste + peso × días · comprando valor − precio − peso × días
    resultado  ganancia × (1 − decay)^rondas si es positiva; la ganancia tal cual si es negativa
    rondas     min(mensajes nuestros, mensajes del rival)
    reloj      12 ticks por duelo; un mensaje por lado y tick; UNA aceptación por equipo y tick; lo aceptado se
               cierra en el tick siguiente con la oferta que estaba en pie al aceptar; sin trato al plazo, cero
    formato    el de GET /api/duels (duel, role, your_limit, your_days_weight, days_meaning, rival_offer, messages...)
Los rivales son SUPUESTOS: copian lo visto el 3/10 (mudos, caminantes, plantados, los que aceptan lo nuestro...),
pero la mezcla real de hoy no se conoce. Por eso la tabla sale por tipo de rival y no solo la media.
"""
import argparse
import json
import math
import os
import random
import sys

T_DUELO = 12
DECAY = 0.10
LENTOS = 0.35          # parte de los rivales cuyo agente no llega a todos los ticks (supuesto)


def u(rol, lim, w, precio, dias):
    """Ganancia real de un lado con el paquete (precio, días)."""
    d = dias or 0
    return precio - lim + w * d if rol == "seller" else lim - precio - w * d


# ---------- rivales: f(v) -> ("ofrecer", precio, día) | ("aceptar",) | ("esperar",) ----------
# v = {"rol", "lim", "w", "t" (tick del duelo, desde 0), "quedan", "mias" [(tick, precio, día)], "suyas" (las nuestras),
#      "en_pie" (nuestra oferta en pie: (precio, día) o None), "dos" (¿hay día?), "mem" (libreta del rival)}

def _mi_dia(v, politica="propio"):
    if not v["dos"]:
        return None
    if politica == "cinco":
        return 5
    if politica == "sigue" and v["suyas"]:
        return v["suyas"][-1][2]
    return 10 if v["rol"] == "seller" else 0


def _acepta_si(v, minimo):
    """¿Acepta nuestra oferta en pie? Solo si le da al menos `minimo` (y siempre dentro de su límite)."""
    if v["en_pie"] is None:
        return False
    g = u(v["rol"], v["lim"], v["w"], *v["en_pie"])
    return g > 0 and g >= minimo


def _precio(v, margen):
    s = 1 if v["rol"] == "seller" else -1
    x = v["lim"] + s * max(margen, 1)
    return max(1, int(math.ceil(x) if s > 0 else math.floor(x)))


def ausente(v):
    return ("esperar",)


def aceptador(margen):
    """No escribe; acepta lo nuestro si le deja `margen` × su límite (duelos 2450, 2451, 302)."""
    return lambda v: ("aceptar",) if _acepta_si(v, margen * v["lim"]) else ("esperar",)


def caminante(c, abre=0.6, politica="propio"):
    """Camina solo cada tick (margen × (1 − c)^k) y acepta lo nuestro si le da al menos lo que pediría él después."""
    def f(v):
        k = len(v["mias"])
        m, sig = abre * v["lim"] * (1 - c) ** k, abre * v["lim"] * (1 - c) ** (k + 1)
        d = _mi_dia(v, politica)
        if _acepta_si(v, u(v["rol"], v["lim"], v["w"], _precio(v, sig), d)):
            return ("aceptar",)
        if v["quedan"] <= 1 and _acepta_si(v, 0):
            return ("aceptar",)
        return ("ofrecer", _precio(v, m), d)
    return f


def lineal_planta(paso=0.04, abre=0.55, suelo=0.06, politica="propio"):
    """Sube un paso fijo cada tick y se planta a `suelo` de su límite (Verde, Sol, Oro el 3/10). Acepta lo nuestro
    solo si mejora lo que él mismo pide."""
    def f(v):
        k = len(v["mias"])
        m = max(suelo, abre - paso * k) * v["lim"]
        d = _mi_dia(v, politica)
        if _acepta_si(v, u(v["rol"], v["lim"], v["w"], _precio(v, m), d)):
            return ("aceptar",)
        if v["mias"] and v["mias"][-1][1] == _precio(v, m) and len(v["mias"]) >= 2 and v["mias"][-2][1] == _precio(v, m):
            return ("esperar",)                                # plantado: lo dice dos veces y calla
        return ("ofrecer", _precio(v, m), d)
    return f


def firme(m=0.2, cede=1.0, politica="propio"):
    """Dice un precio y no se mueve. Acepta lo nuestro si le da `cede` × lo que pide (1 = solo su precio)."""
    def f(v):
        d = _mi_dia(v, politica)
        pide = u(v["rol"], v["lim"], v["w"], _precio(v, m * v["lim"]), d)
        if _acepta_si(v, cede * pide):
            return ("aceptar",)
        if v["quedan"] <= 1 and _acepta_si(v, 0.3 * pide):
            return ("aceptar",)
        return ("ofrecer", _precio(v, m * v["lim"]), d) if len(v["mias"]) < 2 else ("esperar",)
    return f


def reciproco(abre=0.5, parte=0.35, politica="propio"):
    """Solo se mueve cuando nos movemos: cada oferta nueva nuestra, cede `parte` de la distancia. Al final acepta
    cualquier cosa dentro de su límite."""
    def f(v):
        s = 1 if v["rol"] == "seller" else -1
        d = _mi_dia(v, politica)
        mem = v["mem"]
        if not v["mias"]:
            mem["vistas"] = len(v["suyas"])
            return ("ofrecer", _precio(v, abre * v["lim"]), d)
        mia = v["mias"][-1][1]
        if _acepta_si(v, 0) and (v["quedan"] <= 2 or s * (v["en_pie"][0] - mia) >= 0):
            return ("aceptar",)
        if len(v["suyas"]) > mem.get("vistas", 0):
            mem["vistas"] = len(v["suyas"])
            nueva = mia + parte * (v["suyas"][-1][1] - mia)
            if s * (nueva - v["lim"]) < 1:
                nueva = v["lim"] + s
            nueva = int(math.ceil(nueva) if s > 0 else math.floor(nueva))
            if _acepta_si(v, u(v["rol"], v["lim"], v["w"], nueva, d)):
                return ("aceptar",)
            return ("ofrecer", nueva, d) if nueva != mia else ("esperar",)
        return ("esperar",)
    return f


def del_kit(politica="propio"):
    """El duel_agent.py del kit del equipo: abre ×1,6 / ×0,6, cede 30-25-20-15 % de la distancia, no puja contra sí
    mismo (dos ticks quieto y un salto), acepta al 94 % de lo que pediría, y a dos ticks del final lo que haya."""
    pasos = [0.30, 0.25, 0.20, 0.15]

    def f(v):
        s = 1 if v["rol"] == "seller" else -1
        d, mem, n = _mi_dia(v, politica), v["mem"], len(v["mias"])
        suelo = v["lim"] + s * max(0.03 * v["lim"], 1)
        rival = v["en_pie"][0] if v["en_pie"] else None
        movido = len(v["suyas"]) > mem.get("vistas", 0)
        mem["vistas"] = len(v["suyas"])
        urgente = v["quedan"] <= 2
        if not n:
            nxt = v["lim"] * (1.6 if s > 0 else 0.6)
        else:
            base = v["mias"][-1][1]
            parado = not movido and mem.get("quieto", 0) >= 2
            frac = 0.5 if parado else pasos[min(n - 1, 3)]
            meta = suelo if rival is None else (max(rival, suelo) if s > 0 else min(rival, suelo))
            nxt = base + frac * (meta - base)
        if urgente:
            nxt = suelo
        nxt = max(nxt, suelo) if s > 0 else min(nxt, suelo)
        nxt = max(1, int(math.ceil(nxt) if s > 0 else math.floor(nxt)))
        if v["en_pie"] is not None:
            g, pide = u(v["rol"], v["lim"], v["w"], *v["en_pie"]), u(v["rol"], v["lim"], v["w"], nxt, d)
            if g >= 0 and (g >= 0.94 * pide or urgente or n >= 5):
                return ("aceptar",)
        if n and not movido and not urgente:
            mem["quieto"] = mem.get("quieto", 0) + 1
            if mem["quieto"] <= 2:
                return ("esperar",)
        if n and nxt == v["mias"][-1][1]:
            return ("esperar",)
        mem["quieto"] = 0
        return ("ofrecer", nxt, d)
    return f


def boulware(beta=0.6, politica="propio"):
    """Nuestra Duelista antigua: manda cada tick, casi no cede hasta el final, acepta si le damos δ × lo que pediría."""
    def f(v):
        s = 1 if v["rol"] == "seller" else -1
        d = _mi_dia(v, politica)
        x = (v["t"] / (T_DUELO - 1)) ** (1 / beta)
        m0 = abs(v["lim"] * (1.6 if s > 0 else 0.6) - v["lim"])
        m = m0 * (1 - x) + max(1.0, 0.05 * m0) * x
        precio = _precio(v, m)
        if _acepta_si(v, 0.9 * u(v["rol"], v["lim"], v["w"], precio, d)) or (v["quedan"] <= 1 and _acepta_si(v, 0)):
            return ("aceptar",)
        return ("ofrecer", precio, d)
    return f


def mitad(politica="sigue"):
    """Agente de lenguaje que parte la diferencia: abre ×1,4 y propone el punto medio entre lo suyo y lo nuestro;
    si callamos, cede un 10 % cada tick. Acepta en cuanto gana un 8 % de su límite."""
    def f(v):
        s = 1 if v["rol"] == "seller" else -1
        d = _mi_dia(v, politica)
        if _acepta_si(v, 0.08 * v["lim"]) or (v["quedan"] <= 1 and _acepta_si(v, 0)):
            return ("aceptar",)
        if not v["mias"]:
            return ("ofrecer", _precio(v, 0.4 * v["lim"]), d)
        mia = v["mias"][-1][1]
        nueva = (mia + v["suyas"][-1][1]) / 2 if v["suyas"] else mia + 0.1 * (v["lim"] - mia)
        if s * (nueva - v["lim"]) < 1:
            nueva = v["lim"] + s
        nueva = int(math.ceil(nueva) if s > 0 else math.floor(nueva))
        return ("ofrecer", nueva, d) if nueva != mia else ("esperar",)
    return f


def generoso(politica="propio"):
    """Agente de lenguaje amable (duelos 5690 y 5691): abre bajo y espera; cuando nos movemos, da un paso grande, y
    acepta lo nuestro en cuanto nos hemos movido una vez y le queda un 5 % de su límite."""
    def f(v):
        s = 1 if v["rol"] == "seller" else -1
        d, mem = _mi_dia(v, politica), v["mem"]
        if not v["mias"]:
            mem["vistas"] = len(v["suyas"])
            return ("ofrecer", _precio(v, 0.6 * v["lim"]), d)
        if len(v["suyas"]) >= 2 and _acepta_si(v, 0.05 * v["lim"]):
            return ("aceptar",)
        if v["quedan"] <= 2 and _acepta_si(v, 0):
            return ("aceptar",)
        if len(v["suyas"]) > mem.get("vistas", 0):
            mem["vistas"] = len(v["suyas"])
            mia = v["mias"][-1][1]
            nueva = mia + 0.3 * (v["suyas"][-1][1] - mia)
            if s * (nueva - v["lim"]) < 1:
                nueva = v["lim"] + s
            nueva = int(math.ceil(nueva) if s > 0 else math.floor(nueva))
            return ("ofrecer", nueva, d) if nueva != mia else ("esperar",)
        return ("esperar",)
    return f


_NUESTROS = []


def _los_nuestros():
    """t7/duelo.py y t7/params.py de ESTA carpeta, aunque se esté jugando el código de otra (--cadena)."""
    if not _NUESTROS:
        import importlib.util
        t7 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "t7")
        for nombre in ("duelo", "params"):
            spec = importlib.util.spec_from_file_location("rival_" + nombre, os.path.join(t7, nombre + ".py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _NUESTROS.append(mod)
    return _NUESTROS


def francotirador(v):
    """Un rival que juega como nuestra Duelista por ticks (otro equipo con la misma idea)."""
    duelo, params = _los_nuestros()
    p = v["mem"].setdefault("p", params.cargar(cambios={"duelo.rondas": T_DUELO, "duelo.descuento_ronda": 1 - DECAY}))
    k = v["w"] if v["dos"] else None
    ef = lambda pr, d: duelo.precio_efectivo(pr, d, k)       # noqa: E731
    x = {"tick": v["t"], "quedan": v["quedan"], "edad": v["t"], "turno": 0, "n_nos": len(v["mias"]),
         "n_riv": len(v["suyas"]), "nos": [[t, ef(pr, d), pr, d] for t, pr, d in v["mias"]],
         "riv": [[t, ef(pr, d), pr, d] for t, pr, d in v["suyas"]],
         "vigente": [ef(*v["en_pie"]), v["en_pie"][0], v["en_pie"][1]] if v["en_pie"] else None, "dos": v["dos"], "k": k}
    accion, e, dia, _ = duelo.decidir_vivo({"rol": v["rol"], "limite": v["lim"], "x": x}, p)
    if accion == "aceptar":
        return ("aceptar",)
    if accion == "ofrecer":
        return ("ofrecer", duelo.precio_a_mandar(v["rol"], e, dia, k, v["lim"]), dia)
    return ("esperar",)


def lento(bot, cada, fase):
    """El mismo rival, pero su agente tarda: solo actúa un tick de cada `cada` (hoy los ticks duran 15 s y un agente
    que llama a un modelo de lenguaje no llega a todos; el 3/10 varios rivales escribían a saltos)."""
    def f(v):
        return bot(v) if (v["t"] + fase) % cada == 0 or v["quedan"] <= 1 else ("esperar",)
    return f


# (nombre, peso en la mezcla, fábrica). Los pesos son una apuesta razonada con lo visto el 3/10: no se conocen.
RIVALES = [
    ("ausente", 0.13, lambda r: ausente),
    ("aceptador", 0.08, lambda r: aceptador(r.choice([0.0, 0.05, 0.15]))),
    ("caminante", 0.20, lambda r: caminante(r.choice([0.15, 0.3, 0.5]), politica=r.choice(["propio", "propio", "sigue"]))),
    ("sube_y_se_planta", 0.14, lambda r: lineal_planta(r.choice([0.03, 0.05]), suelo=r.choice([0.04, 0.12]))),
    ("firme", 0.10, lambda r: firme(r.choice([0.12, 0.25]), cede=r.choice([1.0, 0.4]))),
    ("reciproco", 0.07, lambda r: reciproco()),
    ("del_kit", 0.07, lambda r: del_kit()),
    ("boulware", 0.07, lambda r: boulware(r.choice([0.4, 0.8]))),
    ("parte_la_diferencia", 0.05, lambda r: mitad()),
    ("generoso", 0.06, lambda r: generoso(r.choice(["propio", "sigue"]))),
    ("como_nosotros", 0.03, lambda r: francotirador),
]


# ---------- el juego falso ----------

class Rechazo(Exception):
    pass


class Juego:
    """Lo que el programa ve como `b`: duels(), duel_say(), duel_accept(). Y avanzar() para pasar de tick."""

    def __init__(self, rng, dos=True, decay=DECAY, ticks=T_DUELO):
        self.rng, self.dos, self.decay, self.ticks = rng, dos, decay, ticks
        self.tick, self.duelos, self.sig = 1000, {}, 1
        self.acepto_en, self.rechazos = None, []

    def abrir(self, rol, coste, valor, w_s, w_b, nombre, bot):
        lim, lim_r = (coste, valor) if rol == "seller" else (valor, coste)
        w, w_r = (w_s, w_b) if rol == "seller" else (w_b, w_s)
        d = {"id": self.sig, "rol": rol, "lim": lim, "w": w, "rol_r": "buyer" if rol == "seller" else "seller",
             "lim_r": lim_r, "w_r": w_r, "t0": self.tick, "plazo": self.tick + self.ticks, "msgs": [], "nos": None,
             "riv": None, "estado": "live", "bot": bot, "nombre": nombre, "mem": {}, "pendiente": None,
             "dijo": set(), "antes": self.rng.random() < 0.35, "resultado": 0.0, "trato": None, "rondas": 0,
             "tarta": max(valor - coste, valor - coste + 10 * (w_s - w_b))}
        self.duelos[self.sig] = d
        self.sig += 1
        return d

    # --- lo que llama el programa ---
    def duels(self, done=False):
        out = []
        for d in self.duelos.values():
            if (d["estado"] == "live") == bool(done):
                continue
            out.append({"duel": d["id"], "session": 4, "status": d["estado"], "role": d["rol"], "item": "El Oso y el Madroño",
                        "issues": ["price", "days"] if self.dos else ["price"],
                        "your_days_weight": round(d["w"], 2) if self.dos else None,
                        "days_meaning": (("each delivery day adds this much cash to your side" if d["rol"] == "seller"
                                          else "each delivery day costs you this much cash") if self.dos else None),
                        "your_limit": d["lim"], "rival": "Rival Oro", "deadline_tick": d["plazo"],
                        "decay_per_round": self.decay, "rounds": self._rondas(d),
                        "your_offer": dict(d["nos"]) if d["nos"] else None, "rival_offer": dict(d["riv"]) if d["riv"] else None,
                        "result": None, "price": None, "days": None, "messages": [dict(m) for m in d["msgs"]]})
        return {"duels": out}

    def duel_say(self, duel_id, text="", price=None, days=None):
        d = self.duelos.get(duel_id)
        if d is None or d["estado"] != "live":
            raise self._no("duel_closed")
        if ("you", self.tick) in d["dijo"]:
            raise self._no("too_many_messages")
        if price is not None:
            if isinstance(price, bool) or not isinstance(price, int) or price < 1:
                raise self._no("bad_price")
            if self.dos and (days is None or not 0 <= days <= 10):
                raise self._no("missing_days")
        d["dijo"].add(("you", self.tick))
        self._mensaje(d, "you", text, price, days if self.dos else None)
        return {"ok": True}

    def duel_accept(self, duel_id):
        d = self.duelos.get(duel_id)
        if d is None or d["estado"] != "live":
            raise self._no("duel_closed")
        if self.acepto_en == self.tick:
            raise self._no("too_many_accepts")
        if d["riv"] is None:
            raise self._no("nothing_to_accept")
        self.acepto_en = self.tick
        if d["pendiente"] is None:
            d["pendiente"] = ("nosotros", d["riv"]["price"], d["riv"]["days"])
        return {"ok": True}

    # --- el reloj ---
    def rivales(self, antes):
        for d in self.duelos.values():
            if d["estado"] != "live" or d["antes"] != antes or d["pendiente"]:
                continue
            v = {"rol": d["rol_r"], "lim": d["lim_r"], "w": d["w_r"], "t": self.tick - d["t0"], "quedan": d["plazo"] - self.tick,
                 "mias": [(m["tick"], m["price"], m["days"]) for m in d["msgs"] if m["from"] != "you" and m["price"] is not None],
                 "suyas": [(m["tick"], m["price"], m["days"]) for m in d["msgs"] if m["from"] == "you" and m["price"] is not None],
                 "en_pie": (d["nos"]["price"], d["nos"]["days"]) if d["nos"] else None, "dos": self.dos, "mem": d["mem"]}
            r = d["bot"](v)
            if r[0] == "aceptar" and d["nos"]:
                d["pendiente"] = ("rival", d["nos"]["price"], d["nos"]["days"])
            elif r[0] == "ofrecer":
                self._mensaje(d, "Rival Oro", "", int(r[1]), r[2] if self.dos else None)

    def avanzar(self):
        self.tick += 1
        for d in self.duelos.values():
            if d["estado"] != "live":
                continue
            if d["pendiente"]:
                quien, precio, dias = d["pendiente"]
                g = u(d["rol"], d["lim"], d["w"] if self.dos else 0, precio, dias)
                d["rondas"] = self._rondas(d)
                d["resultado"] = g * (1 - self.decay) ** d["rondas"] if g > 0 else g
                d["estado"], d["trato"] = "deal", (quien, precio, dias)
            elif self.tick >= d["plazo"]:
                d["estado"] = "no_deal"

    # --- por dentro ---
    def _mensaje(self, d, de, texto, precio, dias):
        d["msgs"].append({"tick": self.tick, "from": de, "text": texto, "price": precio, "days": dias})
        if precio is not None:
            oferta = {"id": len(d["msgs"]), "price": precio, "tick": self.tick, "days": dias if dias is not None else 0}
            d["nos" if de == "you" else "riv"] = oferta

    def _rondas(self, d):
        return min(sum(1 for m in d["msgs"] if m["from"] == "you"), sum(1 for m in d["msgs"] if m["from"] != "you"))

    def _no(self, codigo):
        self.rechazos.append((self.tick, codigo))
        return Rechazo(codigo)


def escenario(rng):
    """(coste, valor, peso del vendedor, peso del comprador). Pesos como los vistos el 3/10; un 8 % sin tarta."""
    coste = rng.uniform(30, 170)
    valor = coste * (rng.uniform(1.08, 1.9) if rng.random() > 0.08 else rng.uniform(0.75, 0.98))
    return round(coste), round(valor), round(rng.uniform(0.8, 6.0), 2), round(rng.uniform(1.5, 9.0), 2)


def torneo(n=600, semilla=11, dos=True, a_la_vez=4, ajustes=None, callado=True, registro=None):
    """Juega n duelos en tandas de `a_la_vez` (acaban en el mismo tick, como en el juego) con el programa real.
    registro: una lista donde se guarda cada línea del diario (para mirar después por qué hizo algo)."""
    import duelos as prog
    from t7 import cadena
    if callado:
        prog._linea = (lambda nombre, d: registro.append(d)) if registro is not None else (lambda *a, **k: None)
    if hasattr(prog, "ajustes"):
        original = prog.__dict__.setdefault("_ajustes_de_verdad", prog.ajustes)

        def con_cambios(hoy=None):
            p = original({"duelo": {"rondas": T_DUELO, "descuento_ronda": 1 - DECAY}, "ajustes": ajustes or {}}
                         if ajustes is not None else hoy)
            return p
        prog.ajustes = con_cambios
    rng = random.Random(semilla)
    nombres, pesos = [r[0] for r in RIVALES], [r[1] for r in RIVALES]
    fabricas = {r[0]: r[2] for r in RIVALES}
    juego, est, mem = Juego(rng, dos=dos), {}, cadena.Memoria()
    hechos, errores = [], 0
    salida, nada = sys.stdout, open(os.devnull, "w", encoding="utf-8")
    while len(hechos) < n:
        tanda = []
        for i in range(a_la_vez):
            c, v, ws, wb = escenario(rng)
            nombre = rng.choices(nombres, pesos)[0]
            bot = fabricas[nombre](rng)
            if nombre != "ausente" and rng.random() < LENTOS:     # una parte de los rivales va a saltos
                bot = lento(bot, rng.choice([2, 3]), rng.randrange(3))
            tanda.append(juego.abrir("seller" if (len(hechos) + i) % 2 == 0 else "buyer", c, v, ws, wb, nombre, bot))
        for _ in range(T_DUELO):
            juego.rivales(antes=True)
            if callado:
                sys.stdout = nada
            try:
                ok = prog.un_tick(juego, est, mem, juego.tick, True, False)
            finally:
                sys.stdout = salida
            errores += not ok
            juego.rivales(antes=False)
            juego.avanzar()
        hechos.extend(tanda)
        for d in tanda:                                           # no acumular memoria entre tandas
            juego.duelos.pop(d["id"], None)
    nada.close()
    return hechos, errores, juego.rechazos


# ---------- los duelos reales, repetidos tick a tick ----------

class Repetido:
    """Un duelo real del grabador vuelto a jugar: las ofertas del rival llegan en el tick en que llegaron de verdad
    (se ven un tick después, lo prudente) y el programa decide. El rival NO contesta a lo nuestro ni lo acepta: es
    un suelo de lo que habríamos sacado aceptando una de sus ofertas."""

    def __init__(self, real):
        self.real = real
        self.suyos = sorted((m for m in real.get("messages") or [] if m.get("from") != "you"), key=lambda m: m.get("tick") or 0)
        ticks = [m.get("tick") for m in real.get("messages") or [] if isinstance(m.get("tick"), (int, float))]
        self.plazo = real["deadline_tick"]
        self.t0 = min(ticks) if ticks else self.plazo - T_DUELO
        self.tick, self.msgs, self.riv, self.nos, self.trato = self.t0, [], None, None, None

    def duels(self, done=False):
        if done or self.trato:
            return {"duels": []}
        r = self.real
        return {"duels": [{"duel": r["duel"], "status": "live", "role": r["role"], "item": r.get("item"),
                           "issues": r.get("issues"), "your_days_weight": r.get("your_days_weight"),
                           "days_meaning": r.get("days_meaning"), "your_limit": r["your_limit"], "rival": r.get("rival"),
                           "deadline_tick": self.plazo, "decay_per_round": r.get("decay_per_round"),
                           "rounds": self._rondas(), "your_offer": self.nos, "rival_offer": self.riv,
                           "messages": [dict(m) for m in self.msgs]}]}

    def duel_say(self, duel_id, text="", price=None, days=None):
        self.msgs.append({"tick": self.tick, "from": "you", "text": text, "price": price, "days": days})
        self.nos = {"price": price, "days": days if days is not None else 0, "tick": self.tick}

    def duel_accept(self, duel_id):
        if self.riv and not self.trato:
            self.trato = (self.riv["price"], self.riv.get("days"))

    def _rondas(self):
        return min(sum(1 for m in self.msgs if m["from"] == "you"), sum(1 for m in self.msgs if m["from"] != "you"))

    def jugar(self, prog, cadena):
        est, mem = {}, cadena.Memoria()
        while self.tick < self.plazo and not self.trato:
            for m in self.suyos:
                if (m.get("tick") or 0) < self.tick and m not in self.msgs:
                    self.msgs.append(m)
                    if m.get("price") is not None:
                        self.riv = {"price": m["price"], "days": m.get("days") or 0, "tick": m.get("tick")}
            prog.un_tick(self, est, mem, self.tick, True, False)
            self.tick += 1
        if not self.trato:
            return 0.0, None
        r, (precio, dias) = self.real, self.trato
        dos = "days" in (r.get("issues") or [])
        signo = 1 if r["role"] == "seller" else -1
        g = signo * (precio - r["your_limit"]) + (signo * (r.get("your_days_weight") or 0) * (dias or 0) if dos else 0)
        rondas = self._rondas()
        return (g * (1 - (r.get("decay_per_round") or DECAY)) ** rondas if g > 0 else g), rondas


def repetir_reales(ajustes=None, ruta=None):
    """Los duelos reales terminados en los que el rival escribió, jugados por el programa. Devuelve el resumen."""
    import duelos as prog
    from t7 import cadena
    prog._linea = lambda *a, **k: None
    if hasattr(prog, "ajustes") and ajustes is not None:
        original = prog.__dict__.setdefault("_ajustes_de_verdad", prog.ajustes)
        prog.ajustes = lambda hoy=None: original({"ajustes": ajustes})
    ruta = ruta or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datos", "duelos-reales-03-10.json")
    with open(ruta, encoding="utf-8") as f:
        reales = [d for d in json.load(f)["duels"] if d.get("status") in ("deal", "no_deal")]
    salida, nada = sys.stdout, open(os.devnull, "w", encoding="utf-8")
    out = {"duelos": 0, "real": 0.0, "repetido": 0.0, "tratos_real": 0, "tratos": 0, "fuera": 0, "rondas": 0, "detalle": []}
    for d in reales:
        if not any(m.get("from") != "you" and m.get("price") is not None for m in d.get("messages") or []):
            continue
        rep = Repetido(d)
        sys.stdout = nada
        try:
            puntos, rondas = rep.jugar(prog, cadena)
        finally:
            sys.stdout = salida
        out["duelos"] += 1
        out["real"] += d.get("result") or 0
        out["repetido"] += puntos
        out["tratos_real"] += d.get("status") == "deal"
        out["tratos"] += rondas is not None
        out["fuera"] += puntos < 0
        out["rondas"] += rondas or 0
        out["detalle"].append((d["duel"], round(d.get("result") or 0, 1), round(puntos, 1), rondas))
    nada.close()
    return out


def tabla(hechos):
    filas = {}
    for d in hechos:
        for clave in (d["nombre"], "TODOS"):
            f = filas.setdefault(clave, {"n": 0, "tratos": 0, "puntos": 0.0, "fuera": 0, "rondas": 0, "tarta": 0.0,
                                         "con_tarta": 0, "sin_cerrar": 0})
            f["n"] += 1
            f["tratos"] += d["estado"] == "deal"
            f["puntos"] += d["resultado"]
            f["fuera"] += d["resultado"] < 0
            f["rondas"] += d["rondas"] if d["estado"] == "deal" else 0
            if d["tarta"] > 0:
                f["tarta"] += d["tarta"]
                f["con_tarta"] += 1
                f["sin_cerrar"] += d["estado"] != "deal"
    return filas


def imprimir(filas):
    print(f"{'rival':22} {'duelos':>6} {'tratos':>7} {'P/duelo':>8} {'parte de la tarta':>18} {'rondas':>7} {'fuera':>6}")
    for clave in sorted(filas, key=lambda k: (k == "TODOS", k)):
        f = filas[clave]
        print(f"{clave:22} {f['n']:6d} {f['tratos'] / f['n']:7.0%} {f['puntos'] / f['n']:8.2f} "
              f"{f['puntos'] / f['tarta'] if f['tarta'] else 0:18.1%} {f['rondas'] / max(1, f['tratos']):7.2f} {f['fuera']:6d}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--semilla", type=int, default=11)
    ap.add_argument("--cadena", default=None, help="carpeta cadena/ cuyo código se juega (por defecto, esta)")
    ap.add_argument("--ajustes", default=None, help='JSON con ajustes, p. ej. {"duelo.paciencia": 1}')
    ap.add_argument("--precio", action="store_true", help="duelos solo de precio")
    ap.add_argument("--json", action="store_true", help="salida en JSON")
    ap.add_argument("--reales", action="store_true", help="repite tick a tick los duelos reales del grabador")
    ap.add_argument("--datos", default=None, help="archivo del grabador para --reales (por defecto, el del 3/10)")
    a = ap.parse_args()
    raiz = os.path.abspath(a.cadena) if a.cadena else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, raiz)
    sys.path.insert(0, os.path.dirname(raiz))
    if a.reales:
        r = repetir_reales(json.loads(a.ajustes) if a.ajustes is not None else None, ruta=a.datos)
        print(f"{r['duelos']} duelos reales en los que el rival escribió")
        print(f"  lo que pasó de verdad      {r['real']:7.1f} P · {r['tratos_real']} tratos")
        print(f"  repetidos con este código  {r['repetido']:7.1f} P · {r['tratos']} tratos · rondas medias "
              f"{r['rondas'] / max(1, r['tratos']):.2f} · fuera del límite {r['fuera']}")
        print("  (suelo: el rival repetido no contesta ni acepta lo nuestro)")
        if a.json:
            print(json.dumps(r["detalle"]))
        return
    hechos, errores, rechazos = torneo(a.n, a.semilla, dos=not a.precio,          # sin --ajustes: lo que diga hoy.json
                                       ajustes=json.loads(a.ajustes) if a.ajustes is not None else None)
    filas = tabla(hechos)
    if a.json:
        print(json.dumps({"filas": filas, "errores": errores, "rechazos": len(rechazos)}, ensure_ascii=False))
        return
    imprimir(filas)
    por_codigo = {}
    for _, c in rechazos:
        por_codigo[c] = por_codigo.get(c, 0) + 1
    print(f"ticks con error del programa: {errores} · peticiones rechazadas por el juego: {por_codigo or 0}")


if __name__ == "__main__":
    main()
