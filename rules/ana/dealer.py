"""Baseline dealer rules: the haggling of starter_agent.py, unchanged.

    budget = 80 % of what the item is worth          (starter: int(pack["expected_book"] * 0.8))
    first offer = 60 % of the budget, then +2 P a round, never above the budget
    accept when her ask is within 1 P of our next offer, or when it is her final word and within budget

Your copy lives in rules/<your name>/dealer.py (created by `python3 -m bench.new_member <your name>`). Interface:

    cap(personal_value) -> int
        The most we will ever pay for an item worth `personal_value` primas to us.

    decide(s) -> ("accept",) | ("offer", price) | ("walk",)
        Called once per round while the dealer has a standing offer. `s` is a dict:
          ask        the dealer's current ask (primas)
          open_ask   the dealer's first ask in this conversation
          prev_ask   the dealer's ask last round, None in round 0
          asks       every ask the dealer has made, oldest first (asks[-1] == ask)
          final      True when this is the dealer's last word (take it or it walks)
          our_offer  our last offer, None before we have spoken
          our_offers every offer we have made, oldest first
          round      0, 1, 2, ...
          cap        cap(personal_value) for this item
        Game facts the rules should respect: the dealer only concedes after we move, repeating our
        price earns nothing, a deal at the dealer's opening price does not count for the ladder, and
        score is the share of the dealer's range we capture.
"""


class Rules:
    max_rounds = 30   # the starter haggles until the thread closes; the dealer's patience ends it first

    def cap(self, personal_value: float) -> int:
        return int(personal_value * 0.8)

    def decide(self, s: dict):
        budget, ask = s["cap"], s["ask"]
        offer = int(budget * 0.6) if s["our_offer"] is None else min(budget, s["our_offer"] + 2)
        if ask <= min(budget, offer + 1) or (s["final"] and ask <= budget):  # fine, or her last word
            return ("accept",)
        return ("offer", offer)  # a polite counter-offer, two primas higher each round
