"""Full diagnostic of everyone's rules, across everyone's branches.

    python3 -m bench.diagnose                # fetch, benchmark every commit of every rules/<author> branch
    python3 -m bench.diagnose --seeds 100    # faster
    python3 -m bench.diagnose --no-fetch     # use the refs you already have

For every branch rules/<author> (on origin, or local when it is not pushed) it takes each commit that changed
rules/<author>/ since the branch left main, extracts that author's rule files *as they were at that commit*, and
scores them with the simulators of the current working tree. Everyone is measured with the same yardstick
and the same seeds, whatever version of bench/ their branch carries.

Writes results/diagnostico.md (+ .json):
  * ranking per agent of each author's best version, and the best rule set overall with its rules (R1, R2, ...)
  * the evolution of each author, commit by commit, with the change each commit made
  * a duel tournament between everyone's best duel rules
  * warnings: broken rule files, and branches that touch files outside their own folder
"""
import argparse
import ast
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import rules  # noqa: E402
from bench.run import duel_rivals, safe_score, table  # noqa: E402

AGENTS = rules.AGENTS


def git(*args, check=True):
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if check and out.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {out.stderr.strip()}")
    return out.stdout.strip() if out.returncode == 0 else None


def branches():
    """{author: ref} for every rules/<author> branch, the pushed one when it exists."""
    found = {}
    for ref in (git("for-each-ref", "--format=%(refname:short)", "refs/heads/rules/") or "").splitlines():
        found[ref.split("/", 1)[1]] = ref
    for ref in (git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin/rules/") or "").splitlines():
        found[ref.split("/", 2)[2]] = ref
    return {a: r for a, r in sorted(found.items()) if rules.NAME.match(a) and a != "baseline"}


def rule_lines(source):
    """The 'R1 ...', 'R2 ...' lines of a rule file's docstring: what the author says the rules are."""
    try:
        doc = ast.get_docstring(ast.parse(source)) or ""
    except SyntaxError:
        return []
    out = []
    for line in doc.splitlines():
        s = line.strip()
        if s[:1] == "R" and s[1:2].isdigit():
            out.append(s)
        elif out and s and line.startswith("    "):
            out[-1] += " " + s  # continuation of the previous rule
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=300)
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--main", default=None, help="the branch everyone starts from (default origin/main, else main)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not a.no_fetch:
        git("fetch", "--prune", "origin", check=False)
    main_ref = a.main or ("origin/main" if git("rev-parse", "--verify", "-q", "origin/main", check=False) else "main")
    seeds = list(range(a.seeds))
    rivals = duel_rivals()
    base = {ag: safe_score(ag, lambda ag=ag: rules.load(ag, "baseline"), seeds, rivals) for ag in AGENTS}

    report = {"seeds": a.seeds, "main": main_ref, "baseline": base, "authors": {}, "warnings": []}
    tmp = tempfile.mkdtemp(prefix="bazaar-diag-")
    cache = {}  # blob id -> metrics: a file unchanged between commits is scored once
    baseline_src = {}
    for ag in AGENTS:
        with open(rules.path(ag), encoding="utf-8") as fh:
            baseline_src[ag] = " ".join(fh.read().split())  # whitespace-insensitive: CRLF checkouts compare equal
    for author, ref in branches().items():
        print(f"{author}: {ref}", file=sys.stderr)
        fork = git("merge-base", main_ref, ref, check=False) or main_ref
        outside = [f for f in (git("diff", "--name-only", f"{fork}..{ref}") or "").splitlines()
                   if f and not f.startswith(f"rules/{author}/")]
        if outside:
            report["warnings"].append(f"`{ref}` toca archivos fuera de `rules/{author}/`: " + ", ".join(f"`{f}`" for f in outside))
        commits = (git("rev-list", "--reverse", f"{fork}..{ref}", "--", f"rules/{author}") or "").split()
        history = []
        for sha in commits:
            when, who, subject = git("log", "-1", "--format=%ad%x09%an%x09%s", "--date=format:%d/%m %H:%M", sha).split("\t", 2)
            row = {"sha": sha[:7], "when": when, "who": who, "subject": subject, "agents": {}}
            for ag in AGENTS:
                blob = git("rev-parse", "-q", "--verify", f"{sha}:rules/{author}/{ag}.py", check=False)
                if not blob:
                    continue  # this author has no rules for this agent yet: baseline
                if blob not in cache:
                    src = git("cat-file", "-p", blob)
                    if " ".join(src.split()) == baseline_src[ag]:
                        cache[blob] = None  # an untouched copy of the baseline: not the author's own rules
                if cache.get(blob, 0) is None:
                    continue
                if blob not in cache:
                    f = os.path.join(tmp, f"{author}_{ag}_{blob[:10]}.py")
                    with open(f, "w", encoding="utf-8") as fh:
                        fh.write(src + "\n")
                    cache[blob] = {**safe_score(ag, lambda f=f: rules.load_file(f, author), seeds, rivals),
                                   "rules": rule_lines(src), "file": f}
                    if cache[blob].get("score") is None:
                        report["warnings"].append(f"`{author}/{ag}.py` en {sha[:7]} falla: {cache[blob]['error']}")
                row["agents"][ag] = {"blob": blob, **cache[blob]}
            history.append(row)
        report["authors"][author] = {"ref": ref, "commits": history}

    # best version of each author per agent
    best = {ag: {} for ag in AGENTS}
    for author, info in report["authors"].items():
        for row in info["commits"]:
            for ag, m in row["agents"].items():
                cur = best[ag].get(author)
                if m.get("score") is not None and (cur is None or m["score"] > cur["score"]):
                    best[ag][author] = {**m, "sha": row["sha"], "when": row["when"], "subject": row["subject"]}

    # duel tournament between the best duel rules of everyone (and the baseline)
    players = {"baseline": rivals["baseline"]} | {a: (lambda f=m["file"], a=a: rules.load_file(f, a)) for a, m in best["duel"].items()}
    tournament = {p: safe_score("duel", make, seeds, {q: r for q, r in players.items() if q != p}) for p, make in players.items()} \
        if len(players) > 1 else {}
    report["best"] = {ag: {a: {k: v for k, v in m.items() if k not in ("file", "trace")} for a, m in rows.items()} for ag, rows in best.items()}
    report["tournament"] = tournament

    md = [f"# Diagnóstico de reglas ({a.seeds} semillas)", "",
          f"Ramas `rules/<autor>` comparadas desde `{main_ref}`, todas medidas con los simuladores de esta copia "
          f"(`bench/sims.py`) y las mismas semillas. Δ = cambio frente a `baseline`.", "",
          "Última versión de cada rama (baseline = no ha cambiado ese agente):", "",
          "| autor | rama | commits | " + " | ".join(AGENTS) + " |", "|---|---|---|" + "---|" * len(AGENTS),
          "| baseline | `" + main_ref + "` | | " + " | ".join(f"{base[ag]['score']:.3f}" if base[ag].get("score") is not None else "ERROR" for ag in AGENTS) + " |"]
    for author, info in report["authors"].items():
        tip = {}
        for row in info["commits"]:
            tip.update(row["agents"])
        cells = []
        for ag in AGENTS:
            m, b = tip.get(ag), base[ag].get("score")
            if m is None:
                cells.append("baseline")
            elif m.get("score") is None:
                cells.append("ERROR")
            else:
                cells.append(f"{m['score']:.3f}" + ("" if b is None else f" ({m['score'] - b:+.3f})"))
        md.append(f"| {author} | `{info['ref']}` | {len(info['commits'])} | " + " | ".join(cells) + " |")
    if not report["authors"]:
        md.append("| — | no hay ramas `rules/<autor>` todavía | | | | |")

    md += ["", "## Mejores reglas por agente", ""]
    for ag in AGENTS:
        b = base[ag].get("score")
        rows = {"baseline": base[ag]} | {f"{au} @ {m['sha']}": m for au, m in best[ag].items()}
        md += [f"### {ag}", ""] + table("autor @ commit", rows, b) + [""]
        winner = max(best[ag].items(), key=lambda kv: kv[1]["score"], default=None)
        if winner and b is not None and winner[1]["score"] > b:
            au, m = winner
            md += [f"**Mejor: {au}** (`{m['sha']}`, {m['when']}, {m['score'] - b:+.3f} sobre baseline) — {m['subject']}", ""]
            md += [f"- {r}" for r in m["rules"]] or ["- (sin líneas R1, R2... en el docstring)"]
            md.append("")
        else:
            md += ["Nadie supera todavía al baseline en este agente.", ""]

    md += ["## Evolución de cada autor", "",
           "Cada fila es un commit que cambió `rules/<autor>/`; el número es el score del agente tras el commit "
           "y entre paréntesis el cambio frente al commit anterior del mismo autor.", ""]
    for author, info in report["authors"].items():
        md += [f"### {author}", "", "| commit | fecha | quién | mensaje | " + " | ".join(AGENTS) + " |",
               "|---|---|---|---|" + "---|" * len(AGENTS)]
        prev = {ag: base[ag].get("score") for ag in AGENTS}
        for row in info["commits"]:
            cells = []
            for ag in AGENTS:
                m = row["agents"].get(ag)
                if not m:
                    cells.append("baseline")
                elif m.get("score") is None:
                    cells.append("ERROR")
                else:
                    d = "" if prev[ag] is None or m["score"] == prev[ag] else f" ({m['score'] - prev[ag]:+.3f})"
                    cells.append(f"{m['score']:.3f}{d}")
                    prev[ag] = m["score"]
            md.append(f"| `{row['sha']}` | {row['when']} | {row['who']} | {row['subject'][:60]} | " + " | ".join(cells) + " |")
        md.append("")

    if tournament:
        names = list(players)
        md += ["## Torneo de duelos (mejor versión de cada uno)", "",
               "Fila contra columna, como comprador y como vendedor: parte media del pastel que se lleva la fila.", "",
               "| | " + " | ".join(names) + " | media |", "|---|" + "---|" * (len(names) + 1)]
        for p in names:
            vs = tournament[p].get("vs") or {}
            md.append(f"| **{p}** | " + " | ".join("—" if q == p else f"{vs.get(q, 0):.3f}" for q in names)
                      + f" | {tournament[p].get('score') or 0:.3f} |")
        md.append("")

    md += ["## Avisos", ""] + ([f"- {w}" for w in report["warnings"]] or ["- Ninguno."])
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    with open(os.path.join(ROOT, "results", "diagnostico.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    for info in report["authors"].values():
        for row in info["commits"]:
            for m in row["agents"].values():
                m.pop("file", None), m.pop("trace", None)
    with open(os.path.join(ROOT, "results", "diagnostico.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1, ensure_ascii=False)
    print("\n".join(md))


if __name__ == "__main__":
    main()
