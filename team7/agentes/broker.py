"""El Casamentero: empareja compradores y vendedores ajenos en el Market Test.

Lo que dice el kit: los comerciantes de prueba anuncian un precio alejado de su límite oculto; unos son pacientes y otros
se van pronto; la mayoría relaja su precio a medida que se le acaba la paciencia; los firmes no lo cambian nunca.
Puntúa la ganancia entre los límites REALES de los pares emparejados, frente a la máxima posible.

Cómo piensa:
1. Límite estimado de cada orden. Si relaja su precio en línea recta, ajustamos la recta precio = a + b·edad:
       límite ≈ a / (1 − h)      (h = holgura inicial supuesta, 25 %)
       se irá en la edad ≈ límite·h / b
   Si no se ha movido, se trata como firme: límite ≈ precio × (1 ± h).
2. Conjunto eficiente: compradores por límite estimado de mayor a menor, vendedores de menor a mayor; entran los k
   primeros pares en que el comprador supera al vendedor. Emparejar fuera de ese conjunto gasta a alguien valioso.
3. Esperar compensa (los precios se acercan y aparecen más cruces), salvo que alguien esté a punto de irse.
   Antes del tick de cierre: solo pares del conjunto, y solo si uno de los dos se va ya. Desde el cierre: todo lo que cruce,
   empezando por la mayor ganancia estimada.
Solo puede emparejar precios ANUNCIADOS que se cruzan (lo exige el juego).
"""


class Casamentero:
    def __init__(self, holgura=0.25, tick_cierre=12, ultimo_tick=15, prisa=1):
        self.h, self.cierre, self.fin, self.prisa = holgura, tick_cierre, ultimo_tick, prisa
        self.vistas = {}          # id -> {"lado", "llega", "precios": [(tick, precio)]}

    def _observar(self, tick, ordenes):
        for o in ordenes:
            v = self.vistas.setdefault(o["id"], {"lado": o["lado"], "llega": tick, "precios": []})
            if not v["precios"] or v["precios"][-1][1] != o["precio"] or v["precios"][-1][0] != tick:
                v["precios"].append((tick, o["precio"]))

    def estimar(self, oid, tick):
        """(límite estimado, ticks que le quedan estimados)."""
        v = self.vistas[oid]
        s = 1 if v["lado"] == "compra" else -1     # un comprador relaja SUBIENDO su precio
        pts = v["precios"]
        cambios = len({p for _, p in pts}) - 1
        if cambios == 0:
            return pts[-1][1] * (1 + s * self.h), 99
        xs = [t - v["llega"] for t, _ in pts]
        ys = [p for _, p in pts]
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        vx = sum((x - mx) ** 2 for x in xs) or 1
        b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / vx
        a = my - b * mx
        if s * b <= 0:
            return ys[-1] * (1 + s * self.h), 99
        lim = a / (1 - s * self.h) if s > 0 else a / (1 + self.h)
        se_va = abs(lim - a) / abs(b)
        return lim, se_va - (tick - v["llega"])

    def plan(self, tick, ordenes):
        """ordenes = [{"id", "lado": "compra"|"venta", "precio"}]. Devuelve [(id venta, id compra, precio)]."""
        self._observar(tick, ordenes)
        compras = {o["id"]: o["precio"] for o in ordenes if o["lado"] == "compra"}
        ventas = {o["id"]: o["precio"] for o in ordenes if o["lado"] == "venta"}
        est = {i: self.estimar(i, tick) for i in list(compras) + list(ventas)}
        cb = sorted(compras, key=lambda i: -est[i][0])
        cv = sorted(ventas, key=lambda i: est[i][0])
        k = 0
        while k < min(len(cb), len(cv)) and est[cb[k]][0] > est[cv[k]][0]:
            k += 1
        dentro = set(cb[:k]) | set(cv[:k])
        final = tick >= self.cierre or tick >= self.fin - 1
        pares = []
        for b_ in sorted(compras, key=lambda i: -est[i][0]):
            for v_ in sorted(ventas, key=lambda i: est[i][0]):
                if compras[b_] >= ventas[v_]:
                    pares.append((est[b_][0] - est[v_][0], v_, b_))
        pares.sort(reverse=True)
        hecho, plan = set(), []
        for gan, v_, b_ in pares:
            if v_ in hecho or b_ in hecho:
                continue
            if not final:
                if b_ not in dentro or v_ not in dentro:
                    continue
                if min(est[b_][1], est[v_][1]) > self.prisa:
                    continue
            hecho |= {v_, b_}
            plan.append((v_, b_, (compras[b_] + ventas[v_]) // 2))
        return plan


def cruce_simple(ordenes):
    """Lo que hace el puesto gratuito: el mejor comprador con el mejor vendedor mientras se crucen, al momento."""
    cb = sorted((o for o in ordenes if o["lado"] == "compra"), key=lambda o: -o["precio"])
    cv = sorted((o for o in ordenes if o["lado"] == "venta"), key=lambda o: o["precio"])
    plan = []
    for b_, v_ in zip(cb, cv):
        if b_["precio"] < v_["precio"]:
            break
        plan.append((v_["id"], b_["id"], (b_["precio"] + v_["precio"]) // 2))
    return plan
