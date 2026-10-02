"""Ana's dealer rules: the haggling of her smart_agent.py (branch ana/smart-agent), ported to the rules interface.

R1  Never pay above what the item is worth to us (cap = personal value).
R2  Anchor low: first offer at 45 % of the dealer's ask.
R3  Concede 35 % of the remaining gap to her ask each round, at least 1 P, never above the cap.
R4  Accept her offer when it meets ours, or when it is her final word, as long as it is within the cap;
    walk away from a final offer above the cap.
R5  If she holds the same ask two rounds in a row, treat it as her floor: take it if within the cap,
    else move up by 1 P.

The interface is documented in rules/baseline/dealer.py.
"""


class Rules:
    max_rounds = 14
    start_frac = 0.45
    concession = 0.35

    def cap(self, personal_value: float) -> int:
        return round(personal_value)

    def decide(self, s: dict):
        ask, cap, ours = s["ask"], s["cap"], s["our_offer"]
        if ours is not None and (ask <= ours or s["final"]):
            if ask <= cap:
                return ("accept",)
            if s["final"]:
                return ("walk",)
        if ours is None:
            return ("offer", max(1, round(ask * self.start_frac)))
        if ask == s["prev_ask"]:  # she held her price: likely near her floor
            if ask <= cap:
                return ("accept",)
            return ("offer", min(cap, ours + 1))
        return ("offer", min(cap, ours + max(1, round((ask - ours) * self.concession))))
