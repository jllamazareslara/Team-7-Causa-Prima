"""Vendedores simulados, sin red. Siguen lo que dicen las reglas y lo poco que hemos visto:

- solo se mueven si nos movemos: ceden k × nuestro paso (k secreto por conversación)
- tienen un límite secreto (suelo comprando, techo vendiendo) que no cruzan
- repetir precio no los mueve; a uno estricto, dos repeticiones le hacen cortar (cooloff)
- su paciencia son N rondas; entonces dan una oferta final, de tres maneras posibles (no sabemos cuál usa cada uno)
- un vendedor puede "ofenderse" con una apertura muy baja: entonces su paciencia se reduce a la mitad
- visto con Abuela (sobre): pidió 30, bajó a 26, 25 y dio 24 final mientras subíamos de 2 en 2 → k ≈ 0,5–1

Cada mundo es una hipótesis. Las estrategias se comparan en TODOS: la buena es la que gana en la mayoría
y no se hunde en ninguno.
"""
import math
import random

PERFILES = {
    #             k            suelo/apertura   paciencia     p(ofende) umbral ofensa  estricto
    "abuela":     ((0.5, 1.2), (0.55, 0.85), (10, 16), 0.15, 0.20, 0.0),
    "chato":      ((0.4, 1.0), (0.60, 0.90), (6, 10), 0.60, 0.40, 1.0),
    "desconocido": ((0.3, 1.5), (0.50, 0.90), (4, 14), 0.40, 0.35, 0.5),
}
FINALES = ("su_precio", "punto_medio", "cerca_del_suelo")


class Vendedor:
    """lado = "compra" (nosotros compramos: él baja) o "venta" (nosotros vendemos: él sube)."""

    def __init__(self, lado, apertura, limite, k, paciencia, final, ofensa, estricto, ofensa_dura=False, tope_cesion=None,
                 rng=None):
        self.s = 1 if lado == "compra" else -1        # sentido en que se mueve NUESTRO precio
        self.ofensa_dura, self.tope_cesion, self.rng = ofensa_dura, tope_cesion, rng or random.Random(0)
        self.precio, self.apertura, self.limite = apertura, apertura, limite
        self.k, self.n, self.final, self.ofensa, self.estricto = k, paciencia, final, ofensa, estricto
        self.ronda, self.ultimo, self.repes, self.cerrado = 0, None, 0, None

    def _cruza(self, x):
        """¿x cruza su límite? (comprando: x por debajo de su suelo)."""
        return self.s * (self.limite - x) > 0

    def responde(self, nuestro):
        """Nuestro mensaje con precio. Devuelve ("trato", p) | ("oferta", p) | ("final", p) | ("cerrado", motivo)."""
        s = self.s
        self.ronda += 1
        if self.ultimo is None:
            if self.ofensa and s * (self.apertura * self.ofensa - nuestro) > 0:
                if self.ofensa_dura:
                    if self.rng.random() < 0.5:
                        self.cerrado = "cooloff"
                        return ("cerrado", "cooloff")
                    self.k /= 2
                self.n = max(2, self.n // 2)
            mueve = 0.25 * self.k * s * (self.apertura - nuestro)
        else:
            paso = s * (nuestro - self.ultimo)
            if paso <= 0:
                self.repes += 1
                if self.estricto and self.repes >= 2:
                    self.cerrado = "cooloff"
                    return ("cerrado", "cooloff")
                mueve = 0
            else:
                mueve = self.k * paso
        if self.tope_cesion is not None:
            mueve = min(mueve, self.tope_cesion * self.apertura)
        self.ultimo = nuestro
        nuevo = self.precio - s * mueve
        if self._cruza(nuevo):
            nuevo = self.limite
        nuevo = math.ceil(nuevo) if s > 0 else math.floor(nuevo)
        if s * (nuestro - nuevo) >= 0 and not self._cruza(nuestro):
            return ("trato", nuestro)
        self.precio = nuevo
        if self.ronda >= self.n:
            if self.final == "su_precio":
                f = self.precio
            elif self.final == "punto_medio":
                f = (self.precio + nuestro) / 2
            else:
                f = self.limite + 0.3 * (self.precio - self.limite)
            f = math.ceil(f) if s > 0 else math.floor(f)
            if self._cruza(f):
                f = self.limite
            self.precio = f
            return ("final", f)
        return ("oferta", self.precio)


MUNDOS = {
    "base": {},
    "ofensa_dura": {"ofensa_dura": True},          # una apertura muy baja le hace cortar la mitad de las veces
    "cesion_con_tope": {"tope_cesion": 0.06},     # nunca cede más del 6 % de su apertura por ronda, demos el paso que demos
    "suelo_alto": {"suelo": (0.80, 0.95)},          # casi no tiene margen
}


def mundo(perfil, lado, lista, rng, valor=None, hipotesis="base"):
    """Un vendedor al azar dentro de la hipótesis del perfil, y nuestro límite para esa carta."""
    h = MUNDOS[hipotesis]
    (k0, k1), (f0, f1), (n0, n1), p_of, umbral, p_estricto = PERFILES[perfil]
    k = rng.uniform(k0, k1)
    n = rng.randint(n0, n1)
    ofensa = umbral if rng.random() < p_of else 0
    estricto = rng.random() < p_estricto
    final = rng.choice(FINALES)
    if "suelo" in h:
        f0, f1 = h["suelo"]
    if lado == "compra":
        apertura = round(lista * rng.uniform(1.0, 1.2))
        limite = apertura * rng.uniform(f0, f1)
        nuestro_limite = valor if valor is not None else round(lista * rng.uniform(0.9, 1.7), 1)
    else:   # vende el vendedor: nos ofrece poco y sube hasta un techo
        apertura = max(1, round(lista * rng.uniform(0.25, 0.45)))
        limite = lista * rng.uniform(0.6, 1.0)
        nuestro_limite = valor if valor is not None else round(lista * rng.uniform(0.05, 0.4), 1) + 1
    v = Vendedor(lado, apertura, limite, k, n, final, ofensa, estricto, h.get("ofensa_dura", False), h.get("tope_cesion"), rng)
    return v, nuestro_limite


def jugar(v, lado, nuestro_limite, decidir, max_rondas=30, lista=None):
    """Juega una conversación. Devuelve dict con trato, precio, captura, rondas, motivo."""
    s = 1 if lado == "compra" else -1
    st = {"lado": lado, "limite": nuestro_limite, "suyas": [v.precio], "nuestras": [], "final": False, "lista": lista}
    for _ in range(max_rondas):
        accion, precio, motivo = decidir(st)
        if accion == "aceptar":
            return _fin(v, s, st["suyas"][-1], len(st["nuestras"]), "aceptamos")
        if accion == "retirarse":
            return _fin(v, s, None, len(st["nuestras"]), motivo)
        if st["final"]:
            return _fin(v, s, None, len(st["nuestras"]), "no aceptamos su final")
        st["nuestras"].append(precio)
        r, x = v.responde(precio)
        if r == "trato":
            return _fin(v, s, x, len(st["nuestras"]), "acepta el nuestro")
        if r == "cerrado":
            return _fin(v, s, None, len(st["nuestras"]), x)
        st["suyas"].append(x)
        st["final"] = r == "final"
    return _fin(v, s, None, max_rondas, "demasiadas rondas")


def _fin(v, s, precio, rondas, motivo):
    if precio is None:
        return {"trato": False, "precio": None, "captura": 0.0, "rondas": rondas, "motivo": motivo}
    rango = s * (v.apertura - v.limite)
    captura = s * (v.apertura - precio) / rango if rango > 0 else 1.0
    return {"trato": True, "precio": precio, "captura": max(-1.0, min(1.0, captura)), "rondas": rondas, "motivo": motivo}
