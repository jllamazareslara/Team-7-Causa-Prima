"""Create your own branch and rule folder, starting from the baseline.

    python3 -m bench.new_member ana          # branch rules/ana from main, with rules/ana/{dealer,broker,duel}.py
    git push -u origin rules/ana

Names: lower case letters, digits and _, starting with a letter (they are folder and branch names).
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import rules  # noqa: E402


def git(*args):
    subprocess.run(["git", *args], cwd=ROOT, check=True)


def main():
    if len(sys.argv) != 2 or not rules.NAME.match(sys.argv[1]) or sys.argv[1] == "baseline":
        sys.exit(__doc__)
    name = sys.argv[1]
    base = "origin/main" if subprocess.run(["git", "rev-parse", "-q", "--verify", "origin/main"], cwd=ROOT,
                                           capture_output=True).returncode == 0 else "main"
    git("switch", "-c", f"rules/{name}", base)
    folder = os.path.join(rules.ROOT, name)
    if os.path.exists(folder):
        sys.exit(f"rules/{name}/ already exists on {base}: work on it there")
    os.makedirs(folder)
    for agent in rules.AGENTS:
        shutil.copy(os.path.join(rules.ROOT, "baseline", f"{agent}.py"), os.path.join(folder, f"{agent}.py"))
    git("add", folder)
    git("commit", "-m", f"rules/{name}: start from baseline")
    print(f"\nListo: rama rules/{name} con rules/{name}/. Edita solo esa carpeta y sube con: git push -u origin rules/{name}")


if __name__ == "__main__":
    main()
