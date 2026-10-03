"""A smarter Bazaar agent, tuned on what the leaders do in the live feed:

- every dealer gets its own worker, so we haggle with all of them at once (one conversation each);
- each worker first SELLS our spare duplicates to its dealer (the dealer ladder scores the share of the
  dealer's price range we capture, and a deal with no counterpart scores zero), then BUYS the missing
  cards with the best expected surplus, then (Abuela) a pack;
- prices only ever move one way: a seller anchors high and comes down, a buyer anchors low and goes up,
  by a steady step and never the same number twice (dealers only move when we move, and Abuela scolds
  anyone who goes backwards); the dealer's `final` offer is taken whenever it is inside our limit;
- spares no dealer bought are listed on El Rastro;
- OPEN_VENUE=1 opens our own `board` venue (for the Market Test) and saves the broker key.

    BAZAAR_URL=https://bazaar.causaprima.ai BAZAAR_KEY=tk-xxxx-xxxx python3 dealers/smart_agent.py
    DEALER=chato CARDS=LAV-10 CASH_RESERVE=0 python3 dealers/smart_agent.py   # one dealer, one card, spend freely
    SELL=0 python3 dealers/smart_agent.py                                     # only buy
    OPEN_VENUE=1 python3 dealers/smart_agent.py                               # also open our board venue (250 P bond + 20 P)
"""
import collections
import math
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # bazaar_sdk.py lives at the repo root
from bazaar_sdk import Bazaar, BazaarError

b = Bazaar(os.environ.get("BAZAAR_URL", "https://bazaar.causaprima.ai"), os.environ["BAZAAR_KEY"])

DEALERS = [d for d in os.environ.get("DEALER", "").split(",") if d]  # e.g. DEALER=chato; empty = every unlocked dealer
CARDS = [c for c in os.environ.get("CARDS", "").split(",") if c]  # e.g. CARDS=LAV-10; empty = best targets
CASH_RESERVE = int(os.environ.get("CASH_RESERVE", "270"))  # keep the venue bond (250 P) + opening fee (20 P); 0 once we own a venue
MAX_DEALS = int(os.environ.get("MAX_DEALS", "5"))  # buys per dealer and run, inside each dealer's hourly quota
SELL = os.environ.get("SELL", "1") != "0"  # sell spare duplicates to the dealers that buy their rarity
LIST_ON_RASTRO = os.environ.get("LIST_ON_RASTRO", "1") != "0"  # list the spares no dealer bought
OPEN_VENUE = os.environ.get("OPEN_VENUE", "0") == "1"
PARALLEL = os.environ.get("PARALLEL", "1") != "0"  # one worker per dealer
BROKER_KEY_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".broker_key")

# How to talk to each dealer, from its traits in GET /api/dealers. Every message carries a new price:
# the same words without one count as spam to strict dealers. `step_frac` is the share of the first gap
# between the dealer's number and ours that we move each round: steady, small steps (Team 13 sold to
# Chato with 51 -> 49 -> 46 -> 43 -> 40 -> 37 and he came up from 13 to a final 15).
PROFILES = {
    # patience .85, generosity .80, shrewdness .20, chattiness .75; "Abuela likes kindness"
    "abuela": {
        "lines": [
            "Hola, Abuela! Would {p} P be all right? Thank you very much.",
            "Buenas tardes, Abuela! How are your grandchildren? {p} P?",
            "Your stall is the best in El Rastro, Abuela. {p} P, if you can?",
            "Muchas gracias por su paciencia, Abuela. {p} P.",
            "We are trying to finish a page of our album, Abuela. {p} P, por favor?",
            "You are very kind, Abuela. {p} P would make our day!",
        ],
        "max_rounds": 16, "start_frac": 0.45, "step_frac": 0.12, "buy_packs": True,
    },
    # patience .35, shrewdness .85, memory .90, strictness .85, chattiness .30: numbers only, no
    # theatre (Team 13 sends him bare structured prices), and skip his silver pack, whose expected
    # value to us (~157 P) is about his list price (150 P).
    "chato": {"lines": [""], "max_rounds": 10, "start_frac": 0.60, "step_frac": 0.10, "buy_packs": False},
}
# a dealer we have not profiled yet (new levels arrive during the weekend): numbers only
DEFAULT_PROFILE = {"lines": [""], "max_rounds": 10, "start_frac": 0.60, "step_frac": 0.10, "buy_packs": False}
MIN_VALUE_VS_LIST = 0.8  # skip cards worth less to us than 80 % of the dealer's list price: no deal to be had
SELL_ANCHOR_VS_LIST = 2.0  # a seller opens at twice what the dealer sells that rarity for (Team 13: 51 for an uncommon)
SELL_ANCHOR_VS_BID = 3.0  # ... and at least three times the dealer's first bid

_log_lock = threading.Lock()


def log(msg):
    with _log_lock:
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


TICK_PAD = 0.6  # seconds after the expected tick before we look again
_tick_lock, _tick_due = threading.Lock(), [0.0]


def wait_tick():
    """Sleep until just after the next tick. The SDK's wait_tick() polls the clock four times a second,
    which from several workers at once breaks the 5 requests/second limit; here every worker shares one
    clock read per tick."""
    with _tick_lock:
        if time.time() >= _tick_due[0]:
            _tick_due[0] = time.time() + max(0.0, float(b.clock().get("next_tick_in", 1.0)))
        due = _tick_due[0]
    time.sleep(max(0.05, due - time.time()) + TICK_PAD)


class Budget:
    """Cash the buyers may still commit, shared by the dealer workers: a negotiation reserves its cap up
    front, so two workers never both promise the same primas."""

    def __init__(self, spendable):
        self.lock, self.free, self.spent = threading.Lock(), spendable, 0

    def reserve(self, want):
        with self.lock:
            got = max(0, min(want, self.free))
            self.free -= got
            return got

    def release(self, reserved, paid=0):
        with self.lock:
            self.free += reserved - paid
            self.spent += paid

    def earn(self, primas):  # a sale tops the budget up, but never eats into the reserve
        with self.lock:
            self.free += primas


def clear_or_resume_thread(with_, topic):
    """A dealer allows only one open conversation per team at a time. An open one about the same topic is
    resumed (closing it would throw away every concession we already earned), any other one is closed.
    Returns (thread id, the last price we said in it) or (None, None)."""
    for t in b.my_threads()["threads"]:
        if t["with"] != with_ or t["status"] != "open":
            continue
        if t.get("topic") == topic:
            full = b.thread(t["id"])
            ours = [m["offer"] for m in full.get("messages", []) if m.get("offer") and m["offer"].get("maker") != with_]
            last = None
            if ours:
                last = ours[-1]["want"]["cash"] or ours[-1]["give"]["cash"]
            log(f"resuming open thread {t['id']} with {with_} (topic {topic}, we last said {last} P)")
            return t["id"], last
        log(f"closing stale open thread {t['id']} with {with_} (topic {t['topic']})")
        b.close_thread(t["id"])
    return None, None


def say_price(tid, text, price):
    """Send our price, waiting out the one-message-per-tick limit instead of giving the thread up."""
    for _ in range(4):
        try:
            return b.say(tid, text, price=price)
        except BazaarError as e:
            if e.code != "wait_for_tick":
                raise
            wait_tick()
    raise BazaarError("wait_for_tick", f"could not send {price} P to thread {tid} after 4 ticks")


def negotiate(with_, topic, limit, label, profile, sell=False, anchor=None):
    """Haggle `topic` with dealer `with_`. Buying, `limit` is the most we pay; selling, the least we take.

    Our price only ever moves towards the dealer (up when buying, down when selling) by a steady step,
    never past `limit` and never the same number twice. We take the dealer's offer when it meets ours or
    when it is `final` and inside our limit; stuck at our limit, we walk away. Returns the thread on a
    deal, else None."""
    sign = -1 if sell else 1  # buying our price rises, selling it falls

    def theirs_of(o):
        return o["give"]["cash"] if sell else o["want"]["cash"]

    def inside(p):
        return p >= limit if sell else p <= limit

    lines = profile["lines"]
    tid, ours = clear_or_resume_thread(with_, topic)
    if tid is None:
        tid = b.open_thread(with_, topic=topic)["id"]
    step, said, waited = None, 0, 0
    while said < profile["max_rounds"] and waited < 2 * profile["max_rounds"]:  # only our own prices use up rounds
        t = b.thread(tid)
        if t["status"] != "open":
            break
        offers = [o for o in t["standing_offers"] if o["maker"] == with_ and o["status"] == "open"]
        theirs = theirs_of(offers[-1]) if offers else None
        final = bool(offers and offers[-1].get("final"))

        if theirs is not None and ours is not None and (sign * (ours - theirs) >= 0 or final):
            if inside(theirs):
                log(f"{label}: accepting {theirs} P ({'final' if final else 'met our price'})")
                b.accept(offers[-1]["id"])
                wait_tick()  # accept() settles on the next tick
                return b.thread(tid)
            if final:
                log(f"{label}: final {theirs} P is outside our limit {limit} P, walking away")
                b.close_thread(tid)
                return None

        msgs = t.get("messages") or []
        if ours is not None and (theirs is None or (msgs and msgs[-1].get("sender") != with_)):
            wait_tick()  # the dealer has not answered our last price yet: conceding again would bid against ourselves
            waited += 1
            continue
        if ours is None:
            if theirs is None and not sell:  # a buyer waits for the dealer's opening ask
                wait_tick()
                waited += 1
                continue
            if sell:
                ours = max(anchor or 0, round(SELL_ANCHOR_VS_BID * (theirs or 0)), limit + 1)
            else:
                ours = min(limit, max(1, round(theirs * profile["start_frac"])))
        else:
            if step is None:
                gap = abs(theirs - ours) if theirs is not None else ours
                step = max(1, round(gap * profile["step_frac"]))
            nxt = ours + sign * step
            nxt = max(nxt, limit) if sell else min(nxt, limit)
            if theirs is not None:  # never cross the dealer's own number: that just gives primas away
                nxt = max(nxt, theirs) if sell else min(nxt, theirs)
            if nxt == ours:  # stuck at our limit: the same price twice earns nothing, so walk away
                log(f"{label}: can't go past our {limit} P limit and the dealer says {theirs} P, walking away")
                b.close_thread(tid)
                return None
            ours = nxt

        log(f"{label}: dealer {theirs} P (final={final}), we say {ours} P")
        say_price(tid, lines[said % len(lines)].format(p=ours), ours)
        said += 1
        wait_tick()

    t = b.thread(tid)
    if t["status"] == "deal":
        return t
    log(f"{label}: no deal after {profile['max_rounds']} rounds ({t['status']}), closing")
    if t["status"] == "open":
        b.close_thread(tid)
    return None


def settled_price(deal):
    settled = next((m["offer"] for m in deal["messages"] if m.get("offer") and m["offer"]["status"] == "settled"), None)
    return None if settled is None else settled["want"]["cash"] or settled["give"]["cash"]


def list_prices(dealers):
    """rarity -> the lowest price any dealer sells it for: what a buyer can always get it for."""
    prices = {}
    for d in dealers.values():
        for e in d["menu"]["sells"]:
            if "rarity" in e:
                prices[e["rarity"]] = min(prices.get(e["rarity"], e["list_price"]), e["list_price"])
    return prices


def spare_copies(me):
    """Our duplicate copies (we keep the copy worth most to us), least valuable first."""
    by_ref = collections.defaultdict(list)
    for a in me["assets"]:
        if a["kind"] == "card":
            by_ref[a["ref"]].append(a)
    spares = []
    for copies in by_ref.values():
        copies.sort(key=lambda a: -a.get("your_value", 0))
        spares += copies[1:]
    return sorted(spares, key=lambda a: a.get("your_value", 0))


def assign_spares(spares, order, dealers):
    """dealer id -> the spares it buys. Each spare goes to the highest-level dealer that buys its rarity,
    so no copy is offered to two dealers at once."""
    plan = {d: [] for d in order}
    for a in spares:
        buyer = next((d for d in order if any(e.get("rarity") == a["rarity"] for e in dealers[d]["menu"].get("buys", []))), None)
        if buyer:
            plan[buyer].append(a)
    return plan


def sell_spares(dealer_id, spares, profile, ref_price, budget, cur):
    """Sell our duplicates to one dealer, anchoring high and coming down steadily. Returns the unsold ones."""
    unsold = []
    for i, a in enumerate(spares):
        floor = max(1, math.ceil(a.get("your_value", 0)))  # below what the copy is worth to us we lose value
        anchor = round(SELL_ANCHOR_VS_LIST * ref_price.get(a["rarity"], floor))
        try:
            deal = negotiate(dealer_id, {"sell": {"assets": [a["id"]]}}, floor, f"{dealer_id}: sell {a['ref']} ({a['rarity']})",
                             profile, sell=True, anchor=anchor)
        except BazaarError as e:
            if e.code in ("persona_quota", "cooloff"):
                log(f"{dealer_id} won't deal now ({e}), keeping the rest of the spares for El Rastro")
                return unsold + spares[i:]
            if e.code in ("rate_limited", "wait_for_tick"):  # throttled, not refused: the open thread is resumed next time
                log(f"{dealer_id}: throttled selling {a['ref']} ({e.code}), retrying once")
                wait_tick()
                try:
                    deal = negotiate(dealer_id, {"sell": {"assets": [a["id"]]}}, floor, f"{dealer_id}: sell {a['ref']} ({a['rarity']})",
                                     profile, sell=True, anchor=anchor)
                except BazaarError as e2:
                    log(f"skipping sale of {a['ref']}: {e2}")
                    unsold.append(a)
                    continue
            else:
                log(f"skipping sale of {a['ref']}: {e}")
                unsold.append(a)
                continue
        paid = settled_price(deal) if deal else None
        if paid is None:
            unsold.append(a)
            continue
        budget.earn(paid)
        log(f"SOLD: {a['ref']} to {dealer_id} for {paid} {cur} (worth {a.get('your_value', 0):.1f} {cur} to us)")
    return unsold


def targets_for(dealer, me, cat):
    """Missing cards of the rarities this dealer sells, best expected surplus first. Uses the server's
    private value (it already includes the page bonus: a card that completes a page is worth much more)."""
    list_price = {e["rarity"]: e["list_price"] for e in dealer["menu"]["sells"] if "rarity" in e}
    owned = {a["ref"] for a in me["assets"] if a["kind"] == "card"}
    targets = []
    for s in cat["sets"]:
        if not s.get("released", True):  # dealers refuse cards from unreleased sets
            continue
        for c in s["cards"]:
            if c["rarity"] not in list_price or c["id"] in owned or c.get("hidden"):
                continue
            if CARDS and c["id"] not in CARDS:
                continue
            value = b.value(c["id"])["your_value"]
            if value >= MIN_VALUE_VS_LIST * list_price[c["rarity"]]:
                targets.append((value - list_price[c["rarity"]], value, c["id"], c["rarity"]))
    targets.sort(reverse=True)
    return targets


def buy_pack(dealer_id, dealer, profile, me, cat, budget, cur):
    pack_ids = [e["pack"] for e in dealer["menu"]["sells"] if "pack" in e]
    if not pack_ids:
        return
    pack = next(p for p in cat["packs"] if p["id"] == pack_ids[0])
    sets = [s["id"] for s in cat["sets"] if s.get("released", True)]
    avg_aff = sum(me["affinity"].get(s, 1.0) for s in sets) / len(sets)
    cap = budget.reserve(round(pack["expected_book"] * avg_aff * 1.05))
    paid = 0
    try:
        if cap < 5:
            return
        deal = negotiate(dealer_id, {"buy": {"pack": pack["id"]}}, cap, f"{dealer_id}: buy {pack['id']}", profile)
        if deal:
            paid = settled_price(deal) or 0
            sealed = next((a for a in b.me()["assets"] if a["kind"] == "pack" and a["ref"] == pack["id"]), None)
            if sealed is None:
                log(f"DEAL: {pack['name']} bought, not in our assets yet: open it later")
                return
            log(f"DEAL: {pack['name']}, worth {sealed['your_value']} {cur}")
            for c in b.open_pack(sealed["id"])["cards"]:
                log(f"  pulled {c['name']} · {c['rarity']} · #{c['serial']}/{c['print_run']}")
    except BazaarError as e:
        log(f"pack purchase skipped: {e}")
    finally:
        budget.release(cap, paid)


def shop_at(dealer_id, dealer, me, cat, budget, cur):
    """Buy the best missing cards (and, if the profile says so, a pack) from one dealer."""
    profile = PROFILES.get(dealer_id, DEFAULT_PROFILE)
    targets = targets_for(dealer, me, cat)
    log(f"--- {dealer['name']}: targets " + (", ".join(f"{t[2]}({t[1]:.0f}{cur})" for t in targets[:6]) or "none worth it"))
    deals = 0
    for _, value, card_id, rarity in targets:
        if deals >= MAX_DEALS:
            return
        value = b.value(card_id)["your_value"]  # refresh: an earlier buy may have changed it
        cap = budget.reserve(int(value))  # never pay above what the card is worth to us
        if cap < 5:
            budget.release(cap)
            log(f"{dealer_id}: no cash left above the {CASH_RESERVE} {cur} reserve (set CASH_RESERVE lower to spend more), stopping")
            return
        paid = 0
        try:
            deal = negotiate(dealer_id, {"buy": {"card": card_id}}, cap, f"{dealer_id}: buy {card_id} ({rarity})", profile)
            if deal:
                paid = settled_price(deal) or 0
                if paid:
                    deals += 1
                    log(f"DEAL: {card_id} for {paid} {cur} (worth {value:.1f} {cur} to us, surplus {value - paid:.1f} {cur})")
                else:
                    log(f"{card_id}: deal closed but no settled offer found yet (status={deal['status']})")
        except BazaarError as e:
            if e.code in ("persona_quota", "cooloff"):
                log(f"{dealer_id} won't sell now ({e})")
                return
            if e.code in ("sold_out", "locked"):
                log(f"skipping {card_id}: {e}")
                continue
            raise
        finally:
            budget.release(cap, paid)

    if profile["buy_packs"] and not CARDS and deals < MAX_DEALS:
        buy_pack(dealer_id, dealer, profile, me, cat, budget, cur)


def work_dealer(dealer_id, dealer, spares, me, cat, ref_price, budget, cur, unsold):
    """One dealer's worker: sell it our spares first, then buy from it."""
    profile = PROFILES.get(dealer_id, DEFAULT_PROFILE)
    try:
        open_sale = {aid for t in b.my_threads()["threads"] if t["with"] == dealer_id and t["status"] == "open"
                     for aid in (t.get("topic") or {}).get("sell", {}).get("assets", [])}
        spares = sorted(spares, key=lambda a: a["id"] not in open_sale)  # resume a sale in progress before starting another
        if spares:
            unsold += sell_spares(dealer_id, spares, profile, ref_price, budget, cur)
        shop_at(dealer_id, dealer, me, cat, budget, cur)
    except BazaarError as e:
        log(f"{dealer_id}: worker stopped ({e})")
        unsold += [a for a in spares if a not in unsold]


def list_on_rastro(spares, ref_price, cur):
    """Post the spares no dealer bought on El Rastro, a little under what a dealer sells them for, never
    under their value to us plus the house fee (5 % + 1 P)."""
    try:
        listed = {a["id"] for o in b.my_offers().get("offers", []) for a in o.get("give", {}).get("assets", [])}
    except BazaarError:
        listed = set()
    for a in spares:
        if a["id"] in listed:
            continue
        floor = math.ceil(a.get("your_value", 0) * 1.05) + 2
        price = max(floor, round(0.9 * ref_price.get(a["rarity"], floor)))
        try:
            b.list_offer({"assets": [a["id"]]}, {"cash": price}, venue="rastro")
            log(f"listed {a['ref']} on El Rastro for {price} {cur}")
        except BazaarError as e:
            log(f"could not list {a['ref']}: {e}")
            if e.code in ("wait_for_tick", "rate_limited"):
                return


def open_board_venue(me, cur):
    """Open our own board venue for the Market Test (30 % of the score) and keep the broker key, which the
    API returns once. Run starter_broker.py with it for the rest of the game."""
    if me.get("venue"):
        log(f"we already own venue {me['venue']}")
        return
    try:
        v = b.open_venue("Mercado Siete · 0.5% fee", fee_bps=50, rules={"mechanism": "board"},
                         description="Half a percent, no per-card charge, a broker that crosses the best pairs at the midpoint every tick. "
                                     "List your spares here and keep almost all of the price.")
    except BazaarError as e:
        log(f"could not open a venue: {e}")
        return
    with open(BROKER_KEY_FILE, "w") as f:
        f.write(v["broker_key"])
    log(f"VENUE {v.get('venue')} opened. Broker key saved to {BROKER_KEY_FILE}; start the broker now:")
    log(f"  BROKER_KEY=$(cat .broker_key) python3 market/starter_broker.py")


def main():
    me, cat = b.me(), b.catalog()
    cur = cat.get("currency_symbol", "P")
    log(f"{me['name']}: {me['cash']} {cur}, level {me['level']}, unlocked {me['unlocked']}, deals so far {me['score']['deals']}")
    if OPEN_VENUE:
        open_board_venue(me, cur)
        me = b.me()
    reserve = 0 if me.get("venue") else CASH_RESERVE  # the reserve only exists to pay for a venue
    personas = {d["id"]: d for d in b.dealers()["personas"]}
    # higher-level dealers first: they weigh more on the dealer ladder and pay the most for our spares
    order = []
    for d in DEALERS or sorted(me["unlocked"], key=lambda d: -(personas.get(d, {}).get("level") or 0)):
        if d in me["unlocked"]:
            order.append(d)
        else:
            log(f"{d} is not unlocked for us yet, skipping")
    dealers = {d: b.dealer(d) for d in order}
    ref_price = list_prices(dealers)
    plan = assign_spares(spare_copies(me) if SELL and not CARDS else [], order, dealers)
    log("spares: " + (", ".join(f"{d}<-{[a['ref'] for a in s]}" for d, s in plan.items() if s) or "none"))

    budget, unsold = Budget(me["cash"] - reserve), []
    args = [(d, dealers[d], plan[d], me, cat, ref_price, budget, cur, unsold) for d in order]
    if PARALLEL:
        workers = [threading.Thread(target=work_dealer, args=a, name=a[0]) for a in args]
        for w in workers:
            w.start()
        for w in workers:
            w.join()
    else:
        for a in args:
            work_dealer(*a)

    if LIST_ON_RASTRO and unsold:
        list_on_rastro(unsold, ref_price, cur)
    final_me = b.me()
    log(f"done. spent {budget.spent} {cur}, cash {final_me['cash']} {cur}, score {final_me['score']['score']} (rank {final_me['score']['rank']})")


if __name__ == "__main__":
    sys.exit(main())
