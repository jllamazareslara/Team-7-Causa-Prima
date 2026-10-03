"""A smarter Bazaar agent: haggles with slow, shrinking concessions instead of the starter's fixed
+2-per-round pattern, and spends this hour's deal quota on the highest personal-value targets first
(missing cards in our best-affinity set) before spending it on more packs.

    BAZAAR_URL=https://bazaar.causaprima.ai BAZAAR_KEY=tk-xxxx-xxxx python3 smart_agent.py
"""
import collections
import os
import sys
import time

from bazaar_sdk import Bazaar, BazaarError

b = Bazaar(os.environ.get("BAZAAR_URL", "https://bazaar.causaprima.ai"), os.environ["BAZAAR_KEY"])


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def ensure_clear_thread(with_):
    """Abuela allows only one open conversation at a time: close any stale one first."""
    for t in b.my_threads()["threads"]:
        if t["with"] == with_ and t["status"] == "open":
            log(f"closing stale open thread {t['id']} with {with_} (topic {t['topic']})")
            b.close_thread(t["id"])


def negotiate(with_, topic, hard_cap, label, max_rounds=14, start_frac=0.45, concession=0.35):
    """Haggle `topic` with dealer `with_` up to `hard_cap` primas. Anchors low, then closes the gap
    to the dealer's latest ask by `concession` of the remaining distance each round (never above
    hard_cap), so we always keep at least as much of the range as the dealer gives up. Accepts on a
    `final` offer, when the dealer's offer meets our own, or when two consecutive dealer asks don't
    move (a floor signal) and the price is within cap. Returns the settled deal info or None."""
    ensure_clear_thread(with_)
    th = b.open_thread(with_, topic=topic)
    tid = th["id"]
    our_offer, prev_ask, status = None, None, "open"
    for rnd in range(max_rounds):
        t = b.thread(tid)
        status = t["status"]
        if status != "open":
            break
        hers = [o for o in t["standing_offers"] if o["maker"] == with_ and o["status"] == "open"]
        if not hers:
            b.wait_tick()
            continue
        offer = hers[-1]
        ask = offer["want"]["cash"]
        final = bool(offer.get("final"))

        if our_offer is not None and (ask <= our_offer or final):
            if ask <= hard_cap:
                log(f"{label}: accepting {ask} P ({'final' if final else 'met our offer'})")
                b.accept(offer["id"])
                b.wait_tick()  # accept() settles on the next tick
                return b.thread(tid)
            if final:
                log(f"{label}: her final {ask} P is above our cap {hard_cap} P, walking away")
                b.close_thread(tid)
                return None

        if our_offer is None:
            our_offer = max(1, round(ask * start_frac))
        elif ask == prev_ask:  # she held her price: likely near her floor
            if ask <= hard_cap:
                log(f"{label}: she held at {ask} P twice, taking it (within our {hard_cap} P cap)")
                b.accept(offer["id"])
                b.wait_tick()  # accept() settles on the next tick
                return b.thread(tid)
            our_offer = min(hard_cap, our_offer + 1)
        else:
            gap = ask - our_offer
            our_offer = min(hard_cap, our_offer + max(1, round(gap * concession)))
        prev_ask = ask

        log(f"{label}: round {rnd}, her ask {ask} P (final={final}), we offer {our_offer} P")
        b.say(tid, f"{our_offer} P, por favor?", price=our_offer)
        b.wait_tick()

    t = b.thread(tid)
    if t["status"] == "deal":
        return t
    log(f"{label}: no deal after {max_rounds} rounds ({t['status']}), closing")
    if t["status"] == "open":
        b.close_thread(tid)
    return None


def missing_cards_by_affinity(b):
    me, cat = b.me(), b.catalog()
    aff = me["affinity"]
    owned = collections.defaultdict(set)
    for a in me["assets"]:
        if a["kind"] == "card":
            owned[a["ref"][:3]].add(a["ref"])
    targets = []
    for s in cat["sets"]:
        sid = s["id"]
        for c in s["cards"]:
            if c["rarity"] in ("common", "uncommon") and c["id"] not in owned[sid]:
                personal_value = c["book"] * aff.get(sid, 1.0)
                targets.append((personal_value, c["id"], c["rarity"], sid))
    targets.sort(reverse=True)  # best personal value first
    return targets


def main():
    me = b.me()
    cur = b.catalog().get("currency_symbol", "P")
    log(f"{me['name']}: {me['cash']} {cur}, level {me['level']}, deals so far {me['score']['deals']}")

    targets = missing_cards_by_affinity(b)
    log("best missing cards by personal value: " + ", ".join(f"{t[1]}({t[0]:.0f}{cur})" for t in targets[:6]))

    budget_spent, deals_done = 0, 0
    MAX_DEALS_THIS_RUN = 5  # stay well inside abuela's 8-deals/hour quota (we may have used some already)

    for personal_value, card_id, rarity, set_id in targets:
        if deals_done >= MAX_DEALS_THIS_RUN:
            break
        if me["cash"] - budget_spent < 5:
            log("low on cash, stopping")
            break
        cap = round(personal_value)  # never pay above what the card is worth to us
        try:
            deal = negotiate("abuela", {"buy": {"card": card_id}}, cap, f"buy {card_id} ({rarity}, {set_id})")
        except BazaarError as e:
            if e.code == "persona_quota":
                log(f"abuela's quota is spent for this hour ({e}); stopping purchases")
                break
            if e.code in ("sold_out", "locked", "cooloff"):
                log(f"skipping {card_id}: {e}")
                continue
            raise
        if deal:
            settled = next((m["offer"] for m in deal["messages"] if m["offer"]["status"] == "settled"), None)
            if settled is None:
                log(f"{card_id}: deal closed but no settled offer found yet (status={deal['status']}), skipping accounting")
                continue
            paid = settled["want"]["cash"] or settled["give"]["cash"]
            budget_spent += paid
            deals_done += 1
            log(f"DEAL: {card_id} for {paid} {cur} (worth {personal_value:.1f} {cur} to us, surplus {personal_value - paid:.1f} {cur})")

    # Spend any remaining quota on a pack too (check hourly pack cap via the dealer menu)
    if deals_done < MAX_DEALS_THIS_RUN:
        catalog = b.catalog()
        pack = next(p for p in catalog["packs"] if p["id"] == "sobre_barrio")
        avg_aff = sum(me["affinity"][s] for s in ("LAV", "MAL", "LAT", "SAL")) / 4
        cap = round(pack["expected_book"] * avg_aff * 1.05)
        try:
            deal = negotiate("abuela", {"buy": {"pack": "sobre_barrio"}}, cap, "buy sobre_barrio pack")
            if deal:
                now = b.me()
                sealed = next(a for a in now["assets"] if a["kind"] == "pack" and a["ref"] == "sobre_barrio")
                paid = me["cash"] - budget_spent - now["cash"]
                log(f"DEAL: pack for {paid} {cur}, worth {sealed['your_value']} {cur}")
                for c in b.open_pack(sealed["id"])["cards"]:
                    log(f"  pulled {c['name']} · {c['rarity']} · #{c['serial']}/{c['print_run']}")
        except BazaarError as e:
            log(f"pack purchase skipped: {e}")

    final_me = b.me()
    log(f"done. cash {final_me['cash']} {cur}, score {final_me['score']}")


if __name__ == "__main__":
    sys.exit(main())
