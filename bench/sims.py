"""Offline, seeded simulators of the three games our agents play. They are models of the real game built
from RULES.md and the starter docstrings, not the server: the numbers below are assumptions, tune them as
we learn how the real dealers, bench traders and duel rivals behave (and say so in the commit).

Every simulator takes a rule object and a seed and returns a dict of metrics; same rules + same seed =
same result, so a change in score is a change in the rules.
"""
import random

# ---------------------------------------------------------------------------------------------- dealer


def dealer_episode(rules, seed: int) -> dict:
    """One haggle with a dealer selling one item. The dealer has a secret floor, opens well above it,
    concedes only after we move (in proportion to our step), ignores repeated prices, and after its
    patience names a final offer."""
    rng = random.Random(seed)
    floor = rng.randint(8, 60)
    open_ask = round(floor * rng.uniform(1.6, 2.4))
    value = floor * rng.uniform(1.0, 2.2)          # what the item is worth to us
    patience = rng.randint(5, 12)
    reciprocity = rng.uniform(0.6, 1.2)            # primas the dealer gives back per prima we move
    max_rounds = getattr(rules, "max_rounds", 14)
    cap = rules.cap(value)

    ask, asks, ours, final, stalls = open_ask, [open_ask], [], False, 0
    paid = None
    for rnd in range(max_rounds):
        s = {"ask": ask, "open_ask": open_ask, "prev_ask": asks[-2] if len(asks) > 1 else None, "asks": list(asks),
             "final": final, "our_offer": ours[-1] if ours else None, "our_offers": list(ours), "round": rnd, "cap": cap}
        d = rules.decide(s)
        if d[0] == "accept":
            paid = ask
            break
        if d[0] == "walk" or final:
            break
        p = int(d[1])
        if p >= ask:  # we bid at or above her ask: she takes it at her ask
            paid = ask
            break
        step = p - ours[-1] if ours else 0
        ours.append(p)
        if step <= 0 and len(ours) > 1:
            stalls += 1  # repeating (or going back) earns nothing and spends patience
        else:
            ask = max(floor, ask - max(1, round(step * reciprocity)) if step > 0 else ask)
        if p >= floor and p >= ask - 1:  # close enough to her floor and her ask: she accepts our offer
            paid = p
            break
        if rnd + 1 + stalls >= patience:
            final, ask = True, max(floor, ask - max(1, (ask - floor) // 3))
        asks.append(ask)
    span = max(1, open_ask - floor)
    share = 0.0 if paid is None or paid >= open_ask else (open_ask - paid) / span
    return {"deal": paid is not None, "share": share, "surplus": (value - paid) if paid is not None else 0.0,
            "overpaid": paid is not None and paid > value, "rounds": rnd + 1}


# ---------------------------------------------------------------------------------------------- broker


def broker_session(rules, seed: int, n: int = 14, ticks: int = 16, max_matches: int = 20) -> dict:
    """One Market Test session. Buyers hold a hidden value, sellers a hidden cost; each quotes away from it
    by a hidden shade, arrives at some tick, relaxes its quote towards its limit as its patience runs out
    (unless it is firm) and leaves when patience ends. A match succeeds when both are still there and the
    price lies between their *true* limits (cost <= price <= value). Efficiency = realised true gains over
    the best possible gains."""
    rng = random.Random(seed)
    traders = {}
    for i in range(n):
        for side in ("s", "b"):
            limit = rng.randint(40, 110)
            shade = rng.uniform(0.10, 0.40) * limit
            arrive = rng.randint(0, ticks // 3)
            patience = rng.randint(2, 10)
            traders[f"b1-{side}{i}"] = {"side": side, "limit": limit, "shade": shade, "arrive": arrive,
                                        "leave": arrive + patience, "patience": patience,
                                        "firm": rng.random() < 0.3, "done": False}
    values = sorted((t["limit"] for t in traders.values() if t["side"] == "b"), reverse=True)
    costs = sorted(t["limit"] for t in traders.values() if t["side"] == "s")
    best = sum(v - c for v, c in zip(values, costs) if v > c)

    def quote(t, tick):
        left = 1.0 if t["firm"] else max(0.3, (t["leave"] - tick) / t["patience"])  # nobody quotes its true limit
        q = t["shade"] * left
        return round(t["limit"] + q) if t["side"] == "s" else max(1, round(t["limit"] - q))

    gains, matches, refused = 0.0, 0, 0
    for tick in range(ticks):
        live = {k: t for k, t in traders.items() if t["arrive"] <= tick < t["leave"] and not t["done"]}
        book = {"tick": tick, "bench_offers": [
            {"id": k, "want": {"cash": quote(t, tick) if t["side"] == "s" else 0},
             "give": {"cash": quote(t, tick) if t["side"] == "b" else 0}} for k, t in sorted(live.items())]}
        for sell, buy, price in list(rules.plan(book))[:max_matches]:
            s, b = live.get(sell), live.get(buy)
            if not s or not b or s["done"] or b["done"] or s["side"] != "s" or b["side"] != "b" \
                    or not (s["limit"] <= price <= b["limit"]):
                refused += 1
                continue
            s["done"] = b["done"] = True
            gains += b["limit"] - s["limit"]
            matches += 1
    return {"efficiency": gains / best if best else 1.0, "matches": matches, "refused": refused}


# ---------------------------------------------------------------------------------------------- duels


class _Bot:
    """A rival with a fixed style: `exp` < 1 concedes early (conceder), > 1 holds then caves (boulware)."""

    def __init__(self, exp: float, margin: float, max_rounds: int):
        self.exp, self.margin, self.max_rounds = exp, margin, max_rounds

    def decide(self, s):
        buyer = s["role"] == "buyer"
        limit, rival = s["limit"], s["rival_offer"]
        t = min(1.0, s["round"] / max(1, self.max_rounds - 1)) ** self.exp
        start = limit * (1 - self.margin) if buyer else limit * (1 + self.margin)
        p = round(start + (limit - start) * t)
        if rival is not None and ((rival <= p) if buyer else (rival >= p)):
            return ("accept",)
        return ("offer", max(1, p))


BOTS = {"conceder": (0.5, 0.35), "linear": (1.0, 0.40), "boulware": (3.0, 0.45), "hardliner": (8.0, 0.30)}


def duel_episode(buyer, seller, seed: int, max_rounds: int = 10, discount: float = 0.95) -> dict:
    """One duel. Returns each side's score: its share of the pie times discount**round (negative when it
    agreed beyond its own limit, 0 with no deal)."""
    rng = random.Random(seed)
    cost = rng.randint(30, 90)
    value = cost + rng.randint(-10, 60)            # sometimes there is no deal to be had
    pie = value - cost
    sides = {"buyer": (buyer, value), "seller": (seller, cost)}
    offers = {"buyer": [], "seller": []}
    order = ("seller", "buyer") if seed % 2 else ("buyer", "seller")
    for msg in range(2 * max_rounds):
        me = order[msg % 2]
        other = "seller" if me == "buyer" else "buyer"
        rules, limit = sides[me]
        rnd = msg // 2
        s = {"role": me, "limit": limit, "rival_offer": offers[other][-1] if offers[other] else None,
             "rival_offers": list(offers[other]), "our_offers": list(offers[me]), "round": rnd,
             "max_rounds": max_rounds, "discount": discount}
        d = rules.decide(s)
        if d[0] == "accept" and offers[other]:
            price = offers[other][-1]
            if pie <= 0:
                return {"deal": True, "buyer": (value - price) / max(1, abs(cost)), "seller": (price - cost) / max(1, abs(cost)), "rounds": rnd}
            f = discount ** rnd
            return {"deal": True, "buyer": (value - price) / pie * f, "seller": (price - cost) / pie * f, "rounds": rnd}
        if d[0] == "walk":
            break
        if d[0] == "offer":
            offers[me].append(int(d[1]))
    return {"deal": False, "buyer": 0.0, "seller": 0.0, "rounds": max_rounds}
