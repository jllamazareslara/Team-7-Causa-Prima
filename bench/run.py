"""Benchmark the rule folders in this working tree, on the same seeds for everyone.

    python3 -m bench.run                     # every folder in rules/, every agent, 300 seeds -> results/benchmark.md
    python3 -m bench.run --agent dealer      # one agent
    python3 -m bench.run --author ana        # baseline + one author
    python3 -m bench.run --seeds 1000        # more seeds, tighter numbers

To compare everyone's branches at once, use `python3 -m bench.diagnose` instead.

Headline score per agent (higher is better):
    dealer  mean share of the dealer's range captured (no deal = 0), the ladder metric
    broker  mean Market Test efficiency (realised true gains / possible gains)
    duel    mean pie share against the house bots and the baseline, as buyer and as seller
"""
import argparse
import json
import os
import statistics
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import rules  # noqa: E402
from bench import sims  # noqa: E402


def _mean(xs):
    return statistics.fmean(xs) if xs else 0.0


def duel_rivals():
    """The fixed duel opponents every author meets: the house bots and the baseline rules."""
    rivals = {"bot:" + k: (lambda k=k: sims._Bot(*sims.BOTS[k], 10)) for k in sims.BOTS}
    rivals["baseline"] = lambda: rules.load("duel", "baseline")
    return rivals


def score(agent, make, seeds, rivals=None):
    """Metrics of the rules built by `make()` on `agent`. A fresh rule object per episode."""
    if agent == "dealer":
        eps = [sims.dealer_episode(make(), s) for s in seeds]
        return {"score": _mean([e["share"] for e in eps]),
                "deal_rate": _mean([e["deal"] for e in eps]),
                "avg_surplus": _mean([e["surplus"] for e in eps]),
                "overpaid_rate": _mean([e["overpaid"] for e in eps]),
                "avg_rounds": _mean([e["rounds"] for e in eps])}
    if agent == "broker":
        eps = [sims.broker_session(make(), s) for s in seeds]
        return {"score": _mean([e["efficiency"] for e in eps]),
                "avg_matches": _mean([e["matches"] for e in eps]),
                "avg_refused": _mean([e["refused"] for e in eps])}
    per_rival, all_scores, deals = {}, [], []
    for name, rival in (rivals or duel_rivals()).items():
        xs = []
        for s in seeds:
            as_buyer = sims.duel_episode(make(), rival(), s)
            as_seller = sims.duel_episode(rival(), make(), s)
            xs += [as_buyer["buyer"], as_seller["seller"]]
            deals += [as_buyer["deal"], as_seller["deal"]]
        per_rival[name] = _mean(xs)
        all_scores += xs
    return {"score": _mean(all_scores), "deal_rate": _mean(deals),
            "loss_rate": _mean([x < 0 for x in all_scores]), "vs": per_rival}


def safe_score(agent, make, seeds, rivals=None):
    """score(), but a broken rule file becomes an error row instead of stopping everyone's benchmark."""
    try:
        return score(agent, make, seeds, rivals)
    except Exception as e:
        return {"score": None, "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc(limit=4)}


def table(title, rows, base=None):
    """Markdown table of {label: metrics}, best score first, with Δ against `base`."""
    cols = sorted({k for r in rows.values() for k, v in r.items() if k != "score" and isinstance(v, (int, float))})
    out = [f"| {title} | score | Δ vs baseline | " + " | ".join(cols) + " |", "|---|---|---|" + "---|" * len(cols)]
    for label, r in sorted(rows.items(), key=lambda kv: -(kv[1]["score"] if kv[1].get("score") is not None else -1e9)):
        if r.get("score") is None:
            out.append(f"| {label} | ERROR | | {r.get('error', '')} |" + " |" * max(0, len(cols) - 1))
            continue
        delta = "" if base is None or label == "baseline" else f"{r['score'] - base:+.3f}"
        out.append(f"| {label} | {r['score']:.3f} | {delta} | " + " | ".join(f"{r.get(c, 0):.3f}" for c in cols) + " |")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", choices=rules.AGENTS, action="append")
    ap.add_argument("--author", action="append")
    ap.add_argument("--seeds", type=int, default=300)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
    seeds = list(range(a.seeds))
    authors = ["baseline"] + [x for x in (a.author or rules.authors()) if x != "baseline"]
    res = {}
    for agent in a.agent or rules.AGENTS:
        res[agent] = {}
        for author in authors:
            own = os.path.exists(os.path.join(rules.ROOT, author, f"{agent}.py"))
            label = author if own or author == "baseline" else f"{author} (= baseline)"
            res[agent][label] = safe_score(agent, lambda: rules.load(agent, author), seeds)
    md = [f"# Rules benchmark ({a.seeds} seeds)", "", "Same seeds for everyone. Δ is the change against `baseline`.", ""]
    for agent, rows in res.items():
        base = rows["baseline"].get("score")
        md += [f"## {agent}", ""] + table("author", {k: v for k, v in rows.items() if k != "baseline"} | {"baseline": rows["baseline"]}, base) + [""]
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    with open(os.path.join(ROOT, "results", "benchmark.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    with open(os.path.join(ROOT, "results", "benchmark.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("\n".join(md))


if __name__ == "__main__":
    main()
