"""Deterministic rule sets, one folder per team member:

    rules/baseline/   dealer.py  broker.py  duel.py     the default rules, the reference for everyone
    rules/<author>/   dealer.py  broker.py  duel.py     each member's rules, edited only on branch rules/<author>

Each file exposes a class `Rules`; the interface of each agent is documented in rules/baseline/<agent>.py.
A member may leave an agent untouched: a missing file falls back to the baseline and is reported as such.

Rules must be deterministic: same state in, same decision out (no randomness, no clock, no I/O), so the
benchmark in bench/ compares authors fairly and the live agents behave the way the benchmark says.
"""
import importlib.util
import os
import re

AGENTS = ("dealer", "broker", "duel")
ROOT = os.path.dirname(os.path.abspath(__file__))
NAME = re.compile(r"^[a-z][a-z0-9_]{0,30}$")


def authors(root: str = ROOT) -> list:
    """Every author folder under `root`, baseline first."""
    names = [n for n in os.listdir(root) if NAME.match(n) and os.path.isdir(os.path.join(root, n))]
    return sorted(names, key=lambda n: (n != "baseline", n))


def path(agent: str, author: str = "baseline", root: str = ROOT) -> str:
    """The rule file `author` uses for `agent`: their own, or the baseline's when they have none."""
    own = os.path.join(root, author, f"{agent}.py")
    return own if os.path.exists(own) else os.path.join(ROOT, "baseline", f"{agent}.py")


def load_file(file: str, label: str = ""):
    """An instance of the `Rules` class in `file`."""
    spec = importlib.util.spec_from_file_location(f"rules_{label or os.path.basename(file)[:-3]}", file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rules = mod.Rules()
    rules.author = label
    return rules


def load(agent: str, author: str = "baseline", root: str = ROOT):
    """An instance of `author`'s rules for `agent` (the baseline's when they have none)."""
    if agent not in AGENTS:
        raise ValueError(f"unknown agent {agent!r}, expected one of {AGENTS}")
    return load_file(path(agent, author, root), f"{author}_{agent}")
