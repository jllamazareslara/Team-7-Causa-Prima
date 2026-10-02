"""Baseline duel rules. The kit has no duel starter, so this is starter_agent.py's haggle applied to a duel:

    a buyer opens at 60 % of its value and raises 2 P a round, never above its value
    a seller opens at its cost / 0.6 and lowers 2 P a round, never below its cost
    accept when the rival's offer is inside our limit and within 1 P of our next offer, or in the last round

Your copy lives in rules/<your name>/duel.py (created by `python3 -m bench.new_member <your name>`). Interface:

    decide(s) -> ("accept",) | ("offer", price) | ("walk",)
        Called once per round. `s` is a dict:
          role           "buyer" or "seller"
          limit          our private limit (a seller's cost, a buyer's value): a deal beyond it loses points
          rival_offer    the rival's standing price, None if it has not offered yet
          rival_offers   every price the rival has offered, oldest first
          our_offers     every price we have offered, oldest first
          round          0, 1, 2, ...
          max_rounds     the session ends with no deal (score 0) after this many rounds
          discount       the pie shrinks by this factor every round (e.g. 0.95)
        Score: our share of the pie (buyer value - seller cost) the deal gives us, times discount**round.
        The two-issue sessions (delivery days) are not modelled yet.
"""


class Rules:
    def decide(self, s: dict):
        limit, rival, ours = s["limit"], s["rival_offer"], s["our_offers"]
        if s["role"] == "buyer":
            offer = int(limit * 0.6) if not ours else min(limit, ours[-1] + 2)
            fine = rival is not None and rival <= limit and (rival <= offer + 1 or s["round"] >= s["max_rounds"] - 1)
        else:
            offer = int(limit / 0.6) if not ours else max(limit, ours[-1] - 2)
            fine = rival is not None and rival >= limit and (rival >= offer - 1 or s["round"] >= s["max_rounds"] - 1)
        return ("accept",) if fine else ("offer", max(1, offer))
