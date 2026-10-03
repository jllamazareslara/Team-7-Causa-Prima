"""Las estrategias que comparamos con los vendedores. Todas reciben el mismo estado y solo ven números."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from t7 import tienda  # noqa: E402


def ana_actual(st, perfil):
    """rules/ana/dealer.py tal como se describe en "Para Ana": abre al 45 %, cede el 35 % del hueco, 14 rondas,
    acepta si repite precio dos veces. Solo compra."""
    s = 1 if st["lado"] == "compra" else -1
    suyo, lim, nos = st["suyas"][-1], st["limite"], st["nuestras"]
    dentro = s * (lim - suyo) >= 0
    if st["final"]:
        return ("aceptar", suyo, "") if dentro else ("retirarse", None, "")
    if len(st["suyas"]) >= 3 and st["suyas"][-1] == st["suyas"][-2] == st["suyas"][-3] and dentro:
        return ("aceptar", suyo, "repite")
    if not nos:
        a = math.floor(0.45 * st["suyas"][0]) if s > 0 else math.ceil(max(2 * (st.get("lista") or 0), 3 * st["suyas"][0]))
        return ("ofrecer", a if s * (lim - a) >= 0 else lim, "")
    if len(nos) >= 14:
        return ("aceptar", suyo, "") if dentro else ("retirarse", None, "")
    sig = nos[-1] + s * max(1, round(0.35 * s * (suyo - nos[-1])))
    if s * (sig - lim) > 0:
        sig = lim
    if s * (suyo - sig) <= 0 and dentro:
        return ("aceptar", suyo, "")
    if sig == nos[-1]:
        return ("retirarse", None, "")
    return ("ofrecer", sig, "")


def ganador(st, perfil):
    """Lo que hace el equipo que va primero: abre 45 % (Abuela) o 60 % (resto), sube el 11 % de la diferencia inicial,
    nunca repite, 16 rondas con Abuela y 10 con los demás. Vendiendo, abre en max(2 × lista, 3 × su oferta)."""
    s = 1 if st["lado"] == "compra" else -1
    suyo, lim, nos = st["suyas"][-1], st["limite"], st["nuestras"]
    dentro = s * (lim - suyo) >= 0
    if st["final"]:
        return ("aceptar", suyo, "") if dentro else ("retirarse", None, "")
    if not nos:
        if s > 0:
            a = math.floor((0.45 if perfil == "abuela" else 0.60) * st["suyas"][0])
        else:
            a = math.ceil(max(2 * (st.get("lista") or 0), 3 * st["suyas"][0]))
        if s * (a - lim) > 0:
            a = lim
        return ("ofrecer", a, "")
    if len(nos) >= (16 if perfil == "abuela" else 10):
        return ("aceptar", suyo, "") if dentro else ("retirarse", None, "")
    paso = max(1, round(0.11 * s * (st["suyas"][0] - nos[0])))
    sig = nos[-1] + s * paso
    if s * (sig - lim) > 0:
        sig = lim
    if s * (suyo - sig) <= 0 and dentro:
        return ("aceptar", suyo, "")
    if sig == nos[-1]:
        return ("retirarse", None, "")
    return ("ofrecer", sig, "")


def adaptativo(pf, p=None):
    """La nuestra (t7.tienda) con un perfil dado."""
    return lambda st, perfil: tienda.decidir(st, pf, p)
