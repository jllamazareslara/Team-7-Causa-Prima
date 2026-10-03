"""Run one author's rules live against the Bazaar, and log every decision to runs/<author>/<agent>.jsonl.

    python3 play.py dealer --rules ana               # buy our best missing cards from Abuela with ana's rules
    python3 play.py dealer --rules baseline --deals 3
    BROKER_KEY=bk_... python3 play.py broker --rules ana   # runs until stopped
    python3 play.py duel --rules ana                 # plays our live duels until none are left

Needs BAZAAR_KEY (and BROKER_KEY for the broker); BAZAAR_URL defaults to the game server.
The rule files are the same ones bench/ scores, so live results and benchmark results are comparable.

`dealer` and `duel` take the same candado (cadena/t7/candado.py) as rastro.py and duelos.py, so this never runs
live at the same time as the chain for the same accept quota (the game allows one trading accept and, separately,
one duel accept per tick for the whole team; two programs accepting with the same key step on each other). `broker`
trades through BROKER_KEY, not the team key, so it never competes for that quota and does not take a candado.
"""
import argparse
import json
import os
import subprocess
import sys
import time

import rules
from bazaar_sdk import Bazaar, BazaarError, Broker

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "cadena"))
from t7 import candado  # noqa: E402

URL = os.environ.get("BAZAAR_URL", "https://bazaar.causaprima.ai")


def load_rules(agent, author):
    """`author`'s rules for `agent`: from this checkout's rules/<author>/, else straight from their pushed branch
    origin/rules/<author> (so the live runner can play anyone's rules without switching branches), else baseline."""
    if author == "baseline" or os.path.isdir(os.path.join(rules.ROOT, author)):
        return rules.load(agent, author)
    subprocess.run(["git", "fetch", "-q", "origin", f"rules/{author}"], check=False)
    src = subprocess.run(["git", "show", f"origin/rules/{author}:rules/{author}/{agent}.py"], capture_output=True, text=True, encoding="utf-8")
    if src.returncode:
        print(f"no rules/{author}/{agent}.py here or on origin/rules/{author}: using baseline", flush=True)
        return rules.load(agent, "baseline")
    os.makedirs(os.path.join("runs", ".rules", author), exist_ok=True)
    f = os.path.join("runs", ".rules", author, f"{agent}.py")
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(src.stdout)
    return rules.load_file(f, author)


class Log:
    def __init__(self, author, agent):
        os.makedirs(os.path.join("runs", author), exist_ok=True)
        self.path = os.path.join("runs", author, f"{agent}.jsonl")

    def __call__(self, event, **kw):
        rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, **kw}
        print(json.dumps(rec, ensure_ascii=False), flush=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------------------------- dealer

def haggle(b, r, log, dealer, topic, value):
    for t in b.my_threads()["threads"]:  # one open conversation per dealer
        if t["with"] == dealer and t["status"] == "open":
            b.close_thread(t["id"])
    tid = b.open_thread(dealer, topic=topic)["id"]
    cap, asks, ours, open_ask = r.cap(value), [], [], None
    for rnd in range(getattr(r, "max_rounds", 14)):
        t = b.thread(tid)
        if t["status"] != "open":
            break
        hers = [o for o in t["standing_offers"] if o["maker"] == dealer and o["status"] == "open"]
        if not hers:
            b.wait_tick()
            continue
        offer = hers[-1]
        ask = offer["want"]["cash"]
        open_ask = open_ask or ask
        asks.append(ask)
        s = {"ask": ask, "open_ask": open_ask, "prev_ask": asks[-2] if len(asks) > 1 else None, "asks": list(asks),
             "final": bool(offer.get("final")), "our_offer": ours[-1] if ours else None, "our_offers": list(ours),
             "round": rnd, "cap": cap}
        d = r.decide(s)
        log("decision", dealer=dealer, topic=topic, state=s, decision=list(d))
        if d[0] == "accept":
            b.accept(offer["id"])
            b.wait_tick()
            log("deal", dealer=dealer, topic=topic, paid=ask, open_ask=open_ask, value=value, rounds=rnd + 1)
            return ask
        if d[0] == "walk":
            break
        ours.append(int(d[1]))
        b.say(tid, f"{ours[-1]} P, por favor?", price=ours[-1])
        b.wait_tick()
    t = b.thread(tid)
    if t["status"] == "deal":
        settled = next((m["offer"] for m in t["messages"] if (m.get("offer") or {}).get("status") == "settled"), {})
        paid = (settled.get("want") or {}).get("cash") or (settled.get("give") or {}).get("cash")
        log("deal", dealer=dealer, topic=topic, paid=paid, open_ask=open_ask, value=value, rounds=len(ours))
        return paid
    if t["status"] == "open":
        b.close_thread(tid)
    log("no_deal", dealer=dealer, topic=topic, status=t["status"], reason=t.get("closed_reason"), open_ask=open_ask)
    return None


def play_dealer(author, a):
    b, r, log = Bazaar(URL, os.environ["BAZAAR_KEY"]), load_rules("dealer", author), Log(author, "dealer")
    me, cat = b.me(), b.catalog()
    owned = {x["ref"] for x in me["assets"] if x["kind"] == "card"}
    targets = sorted(((c["book"] * me["affinity"].get(s["id"], 1.0), c["id"]) for s in cat["sets"] for c in s["cards"]
                      if c["rarity"] in ("common", "uncommon") and c["id"] not in owned), reverse=True)
    log("start", rules=author, cash=me["cash"], score=me["score"])
    deals = 0
    for value, card in targets:
        if deals >= a.deals:
            break
        try:
            if haggle(b, r, log, a.dealer, {"buy": {"card": card}}, value) is not None:
                deals += 1
        except BazaarError as e:
            log("error", card=card, code=e.code, message=e.message)
            if e.code in ("persona_quota", "insufficient_cash"):
                break
    me = b.me()
    log("end", rules=author, cash=me["cash"], score=me["score"])


# ---------------------------------------------------------------------------------------------- broker

def play_broker(author, a):
    broker, r, log, seen = Broker(URL, os.environ["BROKER_KEY"]), load_rules("broker", author), Log(author, "broker"), None
    while True:
        try:
            tick, book = broker.clock()["tick"], broker.book()
            book["tick"] = tick
            now = (tick, [o["id"] for o in book.get("bench_offers") or []])
            if now != seen:
                seen = now
                for sell, buy, price in r.plan(book):
                    try:
                        broker.match(sell, buy, price)
                        log("match", tick=tick, sell=sell, buy=buy, price=price)
                    except BazaarError as e:
                        log("refused", tick=tick, sell=sell, buy=buy, price=price, code=e.code)
        except BazaarError as e:
            log("error", code=e.code, message=e.message)
        time.sleep(1.0)


# ---------------------------------------------------------------------------------------------- duels

def play_duel(author, a):
    """V1 of the live duel runner. Field names below were wrong against the real server (found by reading a
    live /api/duels payload on 2026-10-03) and are fixed here: the duel's id is "duel", not "id"; the round
    counter is "rounds", not "round"; there is no "max_rounds" — the real limit is "deadline_tick" (an
    absolute tick) plus "decay_per_round" (the pie's per-round shrink, e.g. 0.06). Our own and the rival's
    price history come straight from "messages" (from == "you" or not) instead of being tracked locally, so a
    restart picks up offers already on the table instead of re-opening from scratch. The outer loop also
    survives a paused clock or a dropped connection (both happened in the first live run, right as a session's
    trading hours opened/closed) instead of crashing the whole process."""
    b, r, log = Bazaar(URL, os.environ["BAZAAR_KEY"]), load_rules("duel", author), Log(author, "duel")
    while True:
        try:
            live = b.duels().get("duels") or []
            if not live:
                log("idle")
                break
            tick = b.clock()["tick"]
            for d in live:
                msgs = d.get("messages") or []
                ours = [m["price"] for m in msgs if m.get("from") == "you" and m.get("price") is not None]
                theirs = [m["price"] for m in msgs if m.get("from") != "you" and m.get("price") is not None]
                rival = d.get("rival_offer")
                rival = rival.get("price") if isinstance(rival, dict) else rival
                if rival is None and theirs:
                    rival = theirs[-1]
                rnd = d.get("rounds", len(ours))
                remaining = max(0, d.get("deadline_tick", tick) - tick)
                s = {"role": d["role"], "limit": d["your_limit"], "rival_offer": rival, "rival_offers": list(theirs),
                     "our_offers": list(ours), "round": rnd, "max_rounds": rnd + max(1, remaining),
                     "discount": max(0.01, 1 - d.get("decay_per_round", 0.05))}
                if "days" in (d.get("issues") or []):
                    log("skipped", duel=d["duel"], reason="two-issue duels (price + days) are not in the rules interface yet")
                    continue
                dec = r.decide(s)
                log("decision", duel=d["duel"], state=s, decision=list(dec))
                try:
                    if dec[0] == "accept" and rival is not None:
                        b.duel_accept(d["duel"])
                    elif dec[0] == "offer":
                        b.duel_say(d["duel"], f"{dec[1]}?", price=dec[1])
                except BazaarError as e:
                    log("error", duel=d["duel"], code=e.code, message=e.message)
            b.wait_tick()
        except BazaarError as e:  # the clock paused between sessions, or a dropped connection: keep watching
            log("retry", code=e.code, message=e.message)
            time.sleep(2.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("agent", choices=rules.AGENTS)
    ap.add_argument("--rules", default="baseline", help="author whose rules to use (rules/<author>/<agent>.py, baseline when missing)")
    ap.add_argument("--dealer", default="abuela")
    ap.add_argument("--deals", type=int, default=5, help="dealer: stop after this many deals")
    a = ap.parse_args()
    ruta = {"dealer": candado.RUTA, "duel": candado.RUTA_DUELOS}.get(a.agent)
    if ruta:
        ok, motivo = candado.tomar(ruta, f"play.py {a.agent} --rules {a.rules}")
        if not ok:
            sys.exit("NO SE LANZA   " + motivo)
    try:
        {"dealer": play_dealer, "broker": play_broker, "duel": play_duel}[a.agent](a.rules, a)
    finally:
        if ruta:
            candado.soltar(ruta)


if __name__ == "__main__":
    main()
