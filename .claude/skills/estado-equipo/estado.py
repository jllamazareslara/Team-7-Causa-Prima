"""Estado del equipo desde GET /api/me (solo lectura). Nunca imprime claves.

    python .claude/skills/estado-equipo/estado.py                 resumen: dinero, puntos, álbum, repetidas
    python .claude/skills/estado-equipo/estado.py --valor RET-06  además, cuánto nos vale UNA copia más de esa carta
    python .claude/skills/estado-equipo/estado.py --json          el /api/me entero, con las claves tapadas

La clave se lee de BAZAAR_KEY (y la URL de BAZAAR_URL). Solo hace GET: no abre, ofrece ni acepta nada.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO)
from bazaar_sdk import Bazaar  # noqa: E402

for _salida in (sys.stdout, sys.stderr):
    if hasattr(_salida, "reconfigure"):
        _salida.reconfigure(errors="replace")


def tapar(x):
    """Quita cualquier clave: campos *key*/*token*/*secret* y valores tk-... / bk_..."""
    if isinstance(x, dict):
        return {k: "<OCULTA>" if re.search("key|token|secret", k, re.I) else tapar(v) for k, v in x.items()}
    if isinstance(x, list):
        return [tapar(v) for v in x]
    if isinstance(x, str) and re.match(r"^(tk-|bk_)", x):
        return "<OCULTA>"
    return x


def resumen(me):
    s = me.get("score") or {}
    print(f"{me.get('name')} ({me.get('id')}) · tick {me.get('tick')} · nivel {me.get('level')} · "
          f"{'CONGELADO' if me.get('frozen') else 'activo'}")
    print(f"Dinero: {me.get('cash')} P · valor de la colección {me.get('collection_value')}")
    print(f"Vendedores abiertos: {', '.join(me.get('unlocked') or [])}")
    print(f"\nPuntuación {s.get('score')} (puesto {s.get('rank')})")
    print(f"  Negociar {s.get('negotiating')}  ← duelos {s.get('duel_points')} · escalera {s.get('ladder_points')} · "
          f"tratos {s.get('neg_points')}")
    print(f"  Mercado  {s.get('market')}  ← Market Test {s.get('bench_points')} (eficiencia {s.get('bench_efficiency')}, "
          f"puesto {s.get('bench_venue')}) · mercado {s.get('mm_points')}")
    print(f"  Tratos {s.get('deals')} · suerte {s.get('luck')} (no puntúa) · penalizaciones {s.get('adjustments')}")

    cartas = [a for a in me.get("assets") or [] if a.get("kind") == "card"]
    otras = [a for a in me.get("assets") or [] if a.get("kind") != "card"]
    tengo = Counter(a.get("ref") for a in cartas)
    al = me.get("album") or {}
    print(f"\nÁlbum {al.get('filled')}/{al.get('slots')}")
    for p in al.get("pages") or []:
        faltan = [f"{p['set']}-{n:02d}" for n in range(1, 11) if f"{p['set']}-{n:02d}" not in tengo]
        marca = "completa" if p.get("complete") else "faltan " + ", ".join(faltan)
        print(f"  {p['set']} {p.get('name')}: {p.get('have')}/{p.get('of')} · {marca}")

    print("\nRepetidas (la copia de más vale poco para nosotros, mucho para quien le falta):")
    rep = sorted(r for r, n in tengo.items() if n > 1)
    for r in rep:
        vals = sorted((a.get("your_value") for a in cartas if a.get("ref") == r), reverse=True)
        print(f"  {r} ×{tengo[r]} · your_value {vals}")
    if not rep:
        print("  ninguna")
    if otras:
        print(f"\nOtros activos: {Counter(a.get('kind') for a in otras)}")
    v = me.get("venue") or {}
    if v:
        print(f"\nPuesto {v.get('venue')} «{v.get('name')}» · {v.get('status')} · comisión {v.get('fee_bps')} bps · "
              f"tratos {v.get('trades')} · valor creado {v.get('value_created')}")
    print(f"Conversaciones abiertas: {me.get('open_threads')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--valor", nargs="*", default=[], help="cartas para GET /api/me/value (una copia más)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not os.environ.get("BAZAAR_KEY"):
        sys.exit("Falta BAZAAR_KEY en el entorno (no la escribas en ningún archivo).")
    b = Bazaar(os.environ.get("BAZAAR_URL", "https://bazaar.causaprima.ai"), os.environ["BAZAAR_KEY"], wait_on_tick=False)
    me = tapar(b.me())
    if a.json:
        print(json.dumps(me, ensure_ascii=False, indent=1))
    else:
        resumen(me)
    for carta in a.valor:
        print(f"Una copia más de {carta}: your_value {tapar(b.value(carta)).get('your_value')}")


if __name__ == "__main__":
    main()
