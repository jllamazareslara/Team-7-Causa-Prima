"""Baseline broker rules: starter_broker.py's bench matching, which is what the free auto stall does.

Your copy lives in rules/<your name>/broker.py (created by `python3 -m bench.new_member <your name>`). Interface:

    plan(book) -> [(sell_id, buy_id, price), ...]
        Called once per tick with the broker's view of the book. `book["bench_offers"]` holds the
        Market Test's offers as the API shows them: {"id": "b12-7", "want": {"cash": ask}} for a seller,
        {"id": "b12-8", "give": {"cash": bid}} for a buyer (`book["tick"]` is the current tick).
        Return the matches to try this tick; a refused match costs nothing.
        The rule object lives for the whole session, so it may remember earlier books in `self`
        (quote history, refused pairs, ...), as long as it stays deterministic.

What scores: the gains realised between the traders' *true* limits, as a share of the possible gains.
Traders quote away from limits they keep hidden; most relax their quotes as their patience runs out,
the firm ones never do, and some leave soon. Crossing quotes at the midpoint earns half the points.
"""


class Rules:
    def plan(self, book: dict) -> list:
        plan, runs = [], {}
        for o in book.get("bench_offers") or []:
            asks, bids = runs.setdefault(o["id"].split("-")[0], ([], []))
            if o["want"]["cash"]:
                asks.append((o["want"]["cash"], o["id"]))
            else:
                bids.append((o["give"]["cash"], o["id"]))
        for asks, bids in runs.values():
            for (ask, sell), (bid, buy) in zip(sorted(asks, key=lambda a: a[0]), sorted(bids, key=lambda b: -b[0])):
                if bid < ask:
                    break
                plan.append((sell, buy, (ask + bid) // 2))
        return plan
