"""Commit a rules change on your rules/<author> branch with its benchmark score before and after.

    python3 -m bench.contribute "R3 esperar dos asks iguales"          # commit
    python3 -m bench.contribute "R3 esperar dos asks iguales" --push   # commit, check and push
    python3 -m bench.contribute --dry-run                               # only show the scores

It refuses when you are not on a rules/<author> branch, when anything outside rules/<author>/ changed, or when
a changed rule file fails. The commit message records, for every agent you changed, the score of the last
committed version (or the baseline) and of the new one, on the same seeds as bench.diagnose:

    rules/ana dealer: R3 esperar dos asks iguales (dealer 0.279 -> 0.301)
"""
import argparse
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import rules  # noqa: E402
from bench.run import safe_score  # noqa: E402


def git(*args, check=True):
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if check and out.returncode:
        sys.exit(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout.strip() if out.returncode == 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("message", nargs="?", default="", help="what changed, e.g. 'R3 esperar dos asks iguales'")
    ap.add_argument("--push", action="store_true", help="after committing, run bench.guard and push the branch")
    ap.add_argument("--dry-run", action="store_true", help="show the scores, commit nothing")
    ap.add_argument("--seeds", type=int, default=300)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if not branch.startswith("rules/"):
        sys.exit(f"Estás en '{branch}'. Las reglas se aportan en tu rama rules/<tu_nombre>: "
                 "`git switch rules/<tu_nombre>` o `python3 -m bench.new_member <tu_nombre>`.")
    author = branch.split("/", 1)[1]
    mine = f"rules/{author}/"
    changed = sorted(set(git("diff", "--name-only", "HEAD").split() + git("ls-files", "--others", "--exclude-standard").split()))
    outside = [f for f in changed if not f.startswith(mine)]
    if outside:
        sys.exit(f"Hay cambios fuera de {mine}: {', '.join(outside)}. Deshazlos o llévalos a otra rama antes de aportar.")
    agents = sorted({os.path.basename(f)[:-3] for f in changed if f.endswith(".py")} & set(rules.AGENTS))
    if not agents:
        sys.exit(f"No hay cambios en {mine}{{dealer,broker,duel}}.py que aportar.")

    seeds, parts, tmp = list(range(a.seeds)), [], tempfile.mkdtemp(prefix="bazaar-contrib-")
    for ag in agents:
        old_src = git("show", f"HEAD:{mine}{ag}.py", check=False)
        if old_src is None:
            old_make = lambda ag=ag: rules.load(ag, "baseline")  # noqa: E731
        else:
            old_file = os.path.join(tmp, f"old_{ag}.py")
            with open(old_file, "w", encoding="utf-8") as fh:
                fh.write(old_src + "\n")
            old_make = lambda f=old_file: rules.load_file(f, "old")  # noqa: E731
        new_file = os.path.join(rules.ROOT, author, f"{ag}.py")
        if not os.path.exists(new_file):
            sys.exit(f"{mine}{ag}.py was deleted: the agent would fall back to baseline. Restore it or commit by hand.")
        before = safe_score(ag, old_make, seeds)
        after = safe_score(ag, lambda f=new_file: rules.load_file(f, author), seeds)
        if after.get("score") is None:
            sys.exit(f"{mine}{ag}.py falla, no se aporta:\n{after['trace']}")
        b = before.get("score")
        print(f"{ag}: {'?' if b is None else f'{b:.3f}'} -> {after['score']:.3f}"
              + ("" if b is None else f"  ({after['score'] - b:+.3f})"))
        parts.append(f"{ag} {'?' if b is None else f'{b:.3f}'} -> {after['score']:.3f}")

    if a.dry_run:
        return
    if not a.message:
        sys.exit("Falta el mensaje: python3 -m bench.contribute \"R<n> qué cambiaste\"")
    git("add", "--", mine)
    git("commit", "-m", f"rules/{author} {', '.join(agents)}: {a.message} ({'; '.join(parts)})")
    print(git("log", "-1", "--format=%h %s"))
    if a.push:
        if subprocess.run([sys.executable, "-m", "bench.guard"], cwd=ROOT).returncode:
            sys.exit("bench.guard falló: no se sube.")
        out = subprocess.run(["git", "push", "-u", "origin", branch], cwd=ROOT)
        sys.exit(out.returncode)


if __name__ == "__main__":
    main()
