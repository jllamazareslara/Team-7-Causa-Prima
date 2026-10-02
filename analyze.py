import collections
import json
import os

from bazaar_sdk import Bazaar

b = Bazaar(os.environ["BAZAAR_URL"], os.environ["BAZAAR_KEY"])
me = b.me()
cat = b.catalog()
aff = me["affinity"]
owned = collections.defaultdict(set)
for a in me["assets"]:
    if a["kind"] == "card":
        owned[a["ref"][:3]].add(a["ref"])

print(f"cash={me['cash']} level={me['level']} score={me['score']}")
for s in cat["sets"]:
    sid = s["id"]
    missing_common = [c["id"] for c in s["cards"] if c["rarity"] == "common" and c["id"] not in owned[sid]]
    missing_unc = [c["id"] for c in s["cards"] if c["rarity"] == "uncommon" and c["id"] not in owned[sid]]
    missing_rare = [c["id"] for c in s["cards"] if c["rarity"] == "rare" and c["id"] not in owned[sid]]
    print(f"{sid} (affinity {aff.get(sid)}): missing commons={missing_common} uncommons={missing_unc} rares={missing_rare}")
