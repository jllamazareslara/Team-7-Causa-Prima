"""La estrategia que medimos con los vendedores. Recibe el estado y solo ve números.

Antes había dos más para comparar (ana_actual y ganador); se quitaron el 3/10 porque la nuestra gana o empata en
los seis perfil/lado (sim/torneo_tienda.py).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agentes import tienda  # noqa: E402


def adaptativo(pf, p=None):
    """La nuestra (agentes.tienda) con un perfil dado."""
    return lambda st, perfil: tienda.decidir(st, pf, p)
