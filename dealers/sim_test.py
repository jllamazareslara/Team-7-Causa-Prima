"""Offline test of dealers/smart_agent.py: fake dealers, no network, no real primas.

    python dealers/sim_test.py
"""
import json
import threading
import os
import sys

os.environ.setdefault("BAZAAR_KEY", "fake")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smart_agent as s  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data")
load = lambda n: json.load(open(os.path.join(DATA, f"{n}.json"), encoding="utf-8"))  # noqa: E731
ME, CAT, DEALERS, VALUES = load("me"), load("catalog"), load("dealers"), load("values")
RARITY = {c["id"]: c["rarity"] for st in CAT["sets"] for c in st["cards"]}

# (opening ask, floor, rounds of patience before a final offer), guessed from live threads and menus
PRICES = {
    "abuela": {"pack": (30, 24), "common": (12, 8), "uncommon": (29, 22), "patience": 6, "step": 2,
               "buys": {"common": (3, 6), "uncommon": (8, 14)}},
    "chato": {"pack": (188, 150), "uncommon": (32, 26), "rare": (96, 80), "patience": 3, "step": 4,
              "buys": {"uncommon": (13, 16), "rare": (30, 50)}},
}
ASSETS = {a["id"]: a for a in ME["assets"]}  # sell threads: (opening bid, ceiling) per rarity in "buys" above


class FakeBazaar:
    def __init__(self, cash, prices=PRICES):
        self.cash, self.prices, self.threads, self.next_id, self.sent, self.bought = cash, prices, {}, 1, [], []
        self.sold, self.listed, self.lock = [], [], threading.RLock()

    def _offer(self, t, price, final=False):
        cash = {"want": {"cash": 0}, "give": {"cash": price}} if t["sell"] else {"want": {"cash": price}, "give": {"cash": 0}}
        o = {"id": self.next_id, "maker": t["with"], "status": "open", **cash, "final": final}
        self.next_id += 1
        for x in t["standing_offers"]:
            x["status"] = "withdrawn"
        t["standing_offers"].append(o)
        t["messages"].append({"sender": t["with"], "offer": o})
        t["ask"] = price

    def me(self):
        return {**ME, "cash": self.cash, "unlocked": ["abuela", "chato"]}

    def catalog(self):
        return CAT

    def dealers(self):
        return {"personas": list(DEALERS.values())}

    def dealer(self, d):
        return DEALERS[d]

    def value(self, card):
        return {"card": card, "your_value": VALUES[card]}

    def my_threads(self):
        return {"threads": list(self.threads.values())}

    def open_thread(self, with_, topic=None):
        with self.lock:
            return self._open_thread(with_, topic)

    def _open_thread(self, with_, topic):
        tid = self.next_id
        self.next_id += 1
        assert not any(t["with"] == with_ and t["status"] == "open" for t in self.threads.values()), f"BUG: two threads with {with_}"
        if "sell" in topic:
            aid = topic["sell"]["assets"][0]
            assert aid not in [x[1] for x in self.sold], f"BUG: asset {aid} sold twice"
            bid, ceiling = self.prices[with_]["buys"][ASSETS[aid]["rarity"]]
            t = {"id": tid, "with": with_, "topic": topic, "status": "open", "standing_offers": [], "messages": [], "rounds": 0,
                 "last_bid": None, "floor": ceiling, "item": aid, "sell": True}
            self.threads[tid] = t
            self._offer(t, bid)
            return t
        buy = topic["buy"]
        kind = "pack" if "pack" in buy else RARITY[buy["card"]]
        p = self.prices[with_]
        start, floor = p[kind]
        t = {"id": tid, "with": with_, "topic": topic, "status": "open", "standing_offers": [], "messages": [],
             "rounds": 0, "last_bid": None, "floor": floor, "item": buy.get("card") or buy.get("pack"), "sell": False}
        self.threads[tid] = t
        self._offer(t, start)
        return t

    def thread(self, tid):
        return self.threads[tid]

    def say(self, tid, text, price=None):
        with self.lock:
            self._say(tid, text, price)

    def _say(self, tid, text, price):
        t = self.threads[tid]
        if t["sell"]:
            self.sent.append((t["with"], text, price))
            t["rounds"] += 1
            assert price != t["last_bid"], f"BUG: repeated price {price}"
            assert t["last_bid"] is None or price < t["last_bid"], f"BUG: ask went UP {t['last_bid']} -> {price}"
            assert price >= ASSETS[t["item"]]["your_value"], f"BUG: asked {price} under the card's value"
            t["last_bid"] = price
            if price <= t["ask"]:
                self._settle(t, price)
            else:
                final = t["rounds"] >= self.prices[t["with"]]["patience"] + 2
                self._offer(t, min(t["floor"], t["ask"] + 1), final=final)
            return
        p = self.prices[t["with"]]
        t["rounds"] += 1
        self.sent.append((t["with"], text, price))
        assert price != t["last_bid"], f"BUG: repeated price {price}"
        assert t["last_bid"] is None or price > t["last_bid"], f"BUG: offer went DOWN {t['last_bid']} -> {price}"
        assert price <= self.cash, "BUG: offered more than our cash"
        t["last_bid"] = price
        if price >= t["ask"]:  # the dealer takes our offer
            self._settle(t, price)
            return
        if t["rounds"] >= p["patience"]:
            self._offer(t, max(t["floor"], t["ask"] - 1), final=True)
            return
        self._offer(t, max(t["floor"], t["ask"] - p["step"]))

    def _settle(self, t, price):
        t["status"] = "deal"
        if t["sell"]:
            self.cash += price
            self.sold.append((t["with"], t["item"], price))
            t["messages"].append({"sender": "t07", "offer": {"status": "settled", "want": {"cash": price}, "give": {"cash": 0}}})
            return
        self.cash -= price
        self.bought.append((t["with"], t["item"], price))
        t["messages"].append({"sender": "t07", "offer": {"status": "settled", "want": {"cash": 0}, "give": {"cash": price}}})

    def accept(self, oid):
        for t in self.threads.values():
            for o in t["standing_offers"]:
                if o["id"] == oid:
                    o["status"] = "settled"
                    self._settle(t, o["give"]["cash"] if t["sell"] else o["want"]["cash"])
                    t["messages"][-1]["offer"] = o
                    return

    def close_thread(self, tid):
        self.threads[tid]["status"] = "closed"

    def wait_tick(self):
        pass

    def clock(self):
        return {"tick": 1, "next_tick_in": 0}

    def open_pack(self, aid):
        return {"cards": []}

    def my_offers(self):
        return {"offers": [{"give": {"assets": [aid]}} for aid, _ in self.listed]}

    def list_offer(self, give, want, venue=None):
        assert venue == "rastro"
        aid = give["assets"][0]
        assert aid not in [x[1] for x in self.sold], f"BUG: listed {aid} after selling it"
        assert want["cash"] > ASSETS[aid]["your_value"], "BUG: listed under value"
        self.listed.append((aid, want["cash"]))


def run(name, cash, reserve, dealers=(), cards=(), max_deals=5, prices=PRICES, sell=False, parallel=False):
    print(f"\n=== {name} (cash {cash}, reserve {reserve}) ===")
    fb = FakeBazaar(cash, prices)
    s.b, s.CASH_RESERVE, s.DEALERS, s.CARDS, s.MAX_DEALS = fb, reserve, list(dealers), list(cards), max_deals
    s.SELL, s.PARALLEL, s.OPEN_VENUE, s.TICK_PAD = sell, parallel, False, 0
    s.log = lambda m: print("   ", m)
    s.main()
    for dealer in ("abuela", "chato"):
        texts = [t for d, t, _ in fb.sent if d == dealer]
        if texts:
            print(f"  -> {dealer}: {len(texts)} messages, e.g. {texts[0]!r}")
            other = "chato" if dealer == "abuela" else "Abuela"
            assert not any(other in t for t in texts), f"BUG: {dealer} was addressed as {other}"
    assert fb.cash >= reserve or cash < reserve, "BUG: spent the reserve"
    print(f"  -> bought {fb.bought}, sold {fb.sold}, listed {fb.listed}, cash left {fb.cash}")
    return fb


fb = run("1. Only LAV-10 from Chato", 235, 0, dealers=["chato"], cards=["LAV-10"])
assert [x[1] for x in fb.bought] == ["LAV-10"] and fb.bought[0][2] <= VALUES["LAV-10"]

fb = run("2. All unlocked dealers, Chato first", 235, 0)
assert fb.bought and fb.bought[0][0] == "chato", "BUG: Chato should go first"
assert not any(x[1] == "sobre_plata" for x in fb.bought), "BUG: bought a silver pack"
assert all(RARITY.get(x[1]) != "common" for x in fb.bought if x[0] == "chato"), "BUG: Chato does not sell commons"

fb = run("3. Reserve 270 > cash 235: buys nothing", 235, 270)
assert not fb.bought

stubborn = {**PRICES, "chato": {**PRICES["chato"], "rare": (200, 180)}}
fb = run("4. Chato asks 180+ for LAV-10 (above its 149.9 value): walks away", 235, 0, dealers=["chato"], cards=["LAV-10"], prices=stubborn)
assert not fb.bought

fb = run("5. Sell spares only (no cash to buy): highest-level buyer, then El Rastro", 235, 270, sell=True)
spares = s.spare_copies(ME)
assert fb.sold, "BUG: sold nothing"
assert {x[1] for x in fb.sold} | {x[0] for x in fb.listed} == {a["id"] for a in spares}, "BUG: a spare was neither sold nor listed"
assert all(x[0] == "chato" for x in fb.sold if ASSETS[x[1]]["rarity"] == "uncommon"), "BUG: uncommon spare not offered to Chato first"
assert not fb.bought

fb = run("6. Everything in parallel", 235, 0, sell=True, parallel=True)
assert fb.sold and fb.bought

stingy = {**PRICES, "abuela": {**PRICES["abuela"], "buys": {"common": (1, 2)}}}
fb = run("7. Abuela bids under what our spares are worth: keep the worthy ones for El Rastro", 235, 270, prices=stingy, sell=True)
assert all(ASSETS[x[1]]["your_value"] <= 2 for x in fb.sold), "BUG: sold a spare under its value"
assert {x[0] for x in fb.listed} == {a["id"] for a in spares} - {x[1] for x in fb.sold}, "BUG: unsold spare not listed"

print("\nALL CHECKS PASSED")
