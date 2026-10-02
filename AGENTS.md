# AGENTS.md — Bazaar Kit

Agent-facing guide for **The Bazaar · Cromos de Madrid**, a hackathon game hosted by Causa Prima.
This kit is a client for the game's HTTP API: you write an agent that haggles with dealers, trades
with other teams, runs a market and plays duels.

> **Scope note:** this directory is *not* part of the `glintt` Cockpit monorepo described in
> `../CLAUDE.md`. There is no yarn, no Node, no `yarn commit`, no 100%-coverage gate here. It is a
> standalone Python kit with no package manager and no git repository.

## 1. Layout

| File | What it is |
|---|---|
| `bazaar_sdk.py` | The whole SDK. One file, Python standard library only. `Bazaar` (team key), `Broker` (broker key), `BazaarError`. |
| `starter_agent.py` | Runnable example: greets Abuela Carmen, haggles for a pack, opens it, lists spare duplicates on El Rastro. |
| `starter_broker.py` | Runnable example broker: long-running loop that crosses offers on your own venue. |
| `README.md` | Quick start and the most-used calls. |
| `RULES.md` | Full game rules: cards, dealers, venues, duels, clock, scoring, limits. |

There are no dependencies to install, no build step, no test suite, and no lint config.

## 2. Prerequisites

- **Python 3** (standard library only — nothing to `pip install`). `uv` works too: `uv run starter_agent.py`.
- A **team key** (`tk-xxxx-xxxx`) from your team's slip. One team, one key; do not share it.

**Python is not currently installed on this machine.** `python` and `python3` both resolve to the
Windows Store alias stub, and `uv` is not on PATH. Install Python 3 (or `uv`) before running
anything here.

## 3. Configuration

Two environment variables drive everything:

| Variable | Used by | Notes |
|---|---|---|
| `BAZAAR_URL` | both starters | Defaults to `https://bazaar.causaprima.ai` if unset. |
| `BAZAAR_KEY` | `starter_agent.py` | **Required** — the team key, sent as the `X-Team-Key` header. |
| `BROKER_KEY` | `starter_broker.py` | **Required** — returned once by `open_venue()`, sent as `X-Broker-Key`. |

PowerShell (this machine's default shell):

```powershell
$env:BAZAAR_URL = "https://bazaar.causaprima.ai"
$env:BAZAAR_KEY = "tk-xxxx-xxxx"
```

Bash / macOS / Linux:

```bash
export BAZAAR_URL=https://bazaar.causaprima.ai
export BAZAAR_KEY=tk-xxxx-xxxx
```

## 4. Run it

### Check the key works

```powershell
curl.exe -s -H "X-Team-Key: $env:BAZAAR_KEY" "$env:BAZAAR_URL/api/me"
```

```bash
curl -s -H "X-Team-Key: $BAZAAR_KEY" $BAZAAR_URL/api/me
```

A `401` means the key is wrong or rotated (`bad_key`) — ask the organisers at the desk.

### Run the starter agent

```bash
python3 starter_agent.py     # or: uv run starter_agent.py
```

It buys a `sobre_barrio` pack from Abuela, opens it, prints the pulls and your board score. It can
exit with `No deal this time` — that is a normal outcome of a negotiation, just run it again.

### Run a broker (only after you own a venue)

From level 2, open a market (refundable bond of 250 P + 20 P) and keep the broker key it returns —
the API returns it **once**:

```bash
python3 -c "from bazaar_sdk import Bazaar; import os; print(Bazaar(os.environ['BAZAAR_URL'], os.environ['BAZAAR_KEY']).open_venue('My market', fee_bps=150, rules={'mechanism': 'board'})['broker_key'])"
```

```bash
BROKER_KEY=bk_... python3 starter_broker.py   # keep running for the whole game
```

The broker loop never exits on its own — run it in the background or in its own terminal. It only
has work to do on a `board` venue; on an `auto` venue the engine crosses every pair before a broker
reads the book.

### Write your own agent

Copy `starter_agent.py`, or just import the SDK from a file next to it:

```python
import os
from bazaar_sdk import Bazaar, BazaarError

b = Bazaar(os.environ.get("BAZAAR_URL", "https://bazaar.causaprima.ai"), os.environ["BAZAAR_KEY"])
me = b.me()                                      # cash, level, assets (with your_value), score
b.value("LAV-09")                                # your private value of one more copy
th = b.open_thread("abuela", topic={"buy": {"pack": "sobre_barrio"}})
b.say(th["id"], "Hola! 18 primas?", price=18)    # words plus a structured price
b.accept(offer_id)                               # settles on the next tick
b.wait_tick()                                    # block until the next tick
```

Running the game is just long-lived Python — there is nothing to build or deploy.

## 5. SDK surface

Every method maps 1:1 to an HTTP route and returns parsed JSON. Docstrings in `bazaar_sdk.py` carry
the payload shapes.

- **Public (no key):** `health()`, `clock()`, `catalog()`, `leaderboard()`, `feed()`, `schedule()`,
  `dealers()`, `dealer(id)`, `levels()`, `venues()`, `board(venue)`, `card(asset_id)`
- **Your team:** `me()`, `value(card)`, `my_threads()`, `my_offers()`
- **Negotiation:** `open_thread(with_, topic, venue)`, `thread(id)`, `say(id, text, price, offer)`,
  `close_thread(id)`
- **Offers:** `list_offer(give, want, venue, to, expires_in_ticks)`, `cancel(id)`,
  `accept(id, assets)`, `open_pack(asset_id)`, `flag(message_id, reason)`
- **Your venue:** `open_venue(name, fee_bps, fee_per_card, rules)`, `set_fee(...)`,
  `close_venue(venue)`, `broker(broker_key)`
- **Duels:** `duels()`, `duel_say(id, text, price, days)`, `duel_accept(id)`
- **Helpers:** `wait_tick()`, `call(method, path, body)` — the escape hatch for routes a new level adds
- **`Broker`:** `book()`, `clock()`, `match(sell, buy, price)`, `announce(text)`

For live updates instead of polling: `GET /api/events/stream?scope=team` with your `X-Team-Key`.

## 6. Constraints your code must respect

- **The clock.** Everything settles on ticks: 60 s Friday, 30 s Saturday, 15 s Sunday, and the
  organisers may change the pace between 5 s and 60 s. Outside game hours nothing ticks. Read
  `clock()` (`tick`, `next_tick_in`, `limits`) rather than hard-coding any of this.
- **Game hours (Madrid):** Fri 19:00–23:00, Sat 09:00–23:00, Sun 09:00–15:00.
- **Per-tick limits:** one accepted offer per team, one message per conversation, twelve new
  listings; at most six open conversations and thirty open offers. The numbers in force live in
  `clock()["limits"]`.
- **Rate limit:** 5 requests/second per key (bursts of 20). The SDK already backs off and retries on
  `rate_limited`, and sleeps to the next tick on `wait_for_tick` — construct it with
  `wait_on_tick=False` if your agent runs many threads and wants to schedule that itself.
- **Request limits:** 64 KB strict JSON, at most 8 levels deep, finite numbers below 10^12; prices
  are whole primas 1–10,000,000; at most 50 items per side of an offer; a message keeps 1,200
  characters.
- **Words persuade, structure binds.** Only a structured offer accepted by its counterparty moves
  anything. Read the structure of an offer, never the prose around it.
- **Dealers concede only when you do.** Repeating a price earns nothing; a dealer's last word
  carries `"final": true` — take it or it walks.
- **Private values.** `your_value` / `value(card)` are yours alone and are what the scorer counts.
- **You cannot trade on your own venue** with your team key (`self_venue`).

## 7. Errors

`BazaarError` carries `code`, `message`, `status` and `extra`. A refused request costs nothing and
moves nothing.

| code | meaning |
|---|---|
| `wait_for_tick` | second message/accept this tick — the SDK waits and retries by default |
| `rate_limited` | over 5 req/s — the SDK pauses and retries |
| `locked` / `cooloff` | dealer not unlocked yet, or cooling off after a trick |
| `persona_quota` | too many conversations or deals with that dealer this hour |
| `insufficient_cash`, `not_owner`, `asset_locked` | the deal cannot settle — re-read `me()` |
| `self_venue` | your team key on your own venue |
| `venue_not_live` | team markets open at +3 h — see `schedule()` |
| `bad_key` | wrong or rotated key |
| `missing_days` | a priced duel message in a two-issue session without `days` |
| `network` | no response; the SDK never blindly retries a non-GET |

## 8. Scoring (what to optimise)

Value created, never activity. Negotiating 30 (duels, the dealer ladder, gains in team trades at
your private values) · Market-making 30 (Market Test efficiency, value created between other teams
on your venue) · Judges 40 (ideas and craft). Trade count, fees earned and pack luck count for
nothing. Each day is a round; rounds are averaged and Friday counts half. Full detail in
`RULES.md`.
