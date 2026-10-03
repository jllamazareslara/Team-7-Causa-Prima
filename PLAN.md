# Plan: Team 7 agent — duels + dealer agent fixes (from the Kickoff deck and DUELOS-RULES)

## Context

Two documents drive this:
- **The Bazaar – Kickoff.pdf**: the game. Score = 30 Negotiating (duels + dealer ladder + trades) + 30 Market-making + 40 judges. One accepted offer per tick per team, 1 msg/conversation/tick, 5 req/s per key. Saturday ticks are 30 s, Sunday 15 s.
- **DUELOS-RULES.PDF**: really a Spanish Markdown file, not a PDF. It holds a duel strategy and a ready-made `duel_agent.py`. Scoring duels start **Saturday 11:30**. A duel with no deal scores 0, and a deal outside our limit subtracts points.

Current state: `smart_agent.py` handles dealers, but its last run crashed with `rate_limited` at startup (`agent_run.log`). The duel agent exists only inside the misnamed file. There's no `.env`, and `.env` isn't gitignored yet. The goal is to get a working, safe duel agent ready before 11:30, keep the dealer agent running without crashing, and save this plan in the repo.

## Repo layout

Each agent lives in the folder of its action. Run everything from the repo root; every script finds the shared SDK one folder up.

```
bazaar_sdk.py   shared SDK              .env / .broker_key   secrets (root, gitignored)
dealers/        smart_agent.py, sim_test.py, test_data/   haggling with dealers
duels/          DUELOS-RULES.md, duel_agent.py, duel_sim_test.py   1v1 duels
market/         starter_broker.py       our venue's broker (Market Test)
starter/        starter_agent.py        kit example
tools/          analyze.py              collection report
```

## Steps

### 1. Save the plan in the repo
- Write this plan to `PLAN.md` in the project root.
- Rename `DUELOS-RULES.PDF` → `duels/DUELOS-RULES.md` (it is Markdown). ✅ done

### 2. Secrets setup
- Add `.env` and the runtime outputs `duelos-log.jsonl`, `duelos-limites.json` and `agent_run.log` to `.gitignore`.
- Ask the user to create `.env` with `BAZAAR_URL=` and `BAZAAR_KEY=`. I won't write the key.

### 3. Create `duels/duel_agent.py` (code taken from DUELOS-RULES, with fixes)
Copy the code block from the duel doc verbatim, then make these small changes:
- **Optional `.env`:** load it from the repo root, and only if it exists (`if os.path.exists(...)`). Otherwise fall back to environment variables, the same way `dealers/smart_agent.py:27` does, so the agent doesn't crash with no file.
- **Rate-limit-safe loop:** replace `b.wait_tick()` (polls `/api/clock` 4×/s) with a single `clock()` read plus a sleep on `next_tick_in`. Reuse the pattern of `smart_agent.wait_tick` (`dealers/smart_agent.py`), and reuse that tick value instead of calling `b.clock()` again at the top of the loop.
- **Robust field reads:** log the raw duel shape once (`first_duel_raw`, already present). Keep the `skip` behaviour when `role`/`your_limit` are missing. Leave `SCENARIO_KEYS` as is.
- **Days duels (Saturday 18:00 and Sunday):** add minimal support instead of skipping.
  - When `"days" in issues`, send `days=` in `b.duel_say` (the SDK already supports it, `bazaar_sdk.py:286`).
  - Pick the day value from `your_days_weight`: if extra days are good for us, ask 10, otherwise 0. Price logic stays unchanged.
  - Log the decision. Keep the change small and guarded so a missing weight falls back to the existing skip.
- Keep the strategy constants (`OPEN_SELL`, `GAP_STEPS`, `ROUND_COST`, `MAX_ROUNDS`, `PANIC_TICKS`, `OPEN_SHARE`, `HOLD_SHARE`) exactly as the doc sets them.

### 4. Offline test for the duel agent: `duels/duel_sim_test.py`
- Follow the style of `dealers/sim_test.py`: a fake `Bazaar` with `clock`, `duels`, `duel_say` and `duel_accept`, and rival bots (stubborn, generous, extreme anchor, shrinking steps).
- Run the duel logic against the fake and check two things:
  - (a) we never offer or accept outside our limit;
  - (b) every duel closes before the deadline.
- To make this possible, refactor `duel_agent.py` lightly: put the loop under `main()` / `if __name__ == "__main__":` so `decide()` is importable, and move the `Bazaar(...)` construction into `main()`.

### 5. Fix the `dealers/smart_agent.py` startup crash
- In `main()` (`dealers/smart_agent.py`), `me`, `catalog`, `me`, `dealers` and N× `dealer()` all fire back-to-back. The SDK only retries `rate_limited` 3× with 0.25–0.75 s sleeps (`bazaar_sdk.py:79`), and other team processes using the same key make it worse.
- Fix: add a small throttle helper (`time.sleep(0.25)`) between the startup calls. Also build the client with `Bazaar(..., retries=6)` so throttles back off longer.
- `targets_for` calls `b.value()` for every candidate card in a tight loop (`dealers/smart_agent.py`). Throttle it the same way.

### 6. Operating rule (documented in PLAN.md and README)
- Only one machine runs the agents.
- **Stop `smart_agent.py` while duels are live** (only one accept per tick per team). Run `duel_agent.py` dry-run first, check `first_duel_raw`, then `--live`.

## Critical files
- New: `duels/duel_agent.py`, `duels/duel_sim_test.py`, `PLAN.md`
- Edit: `dealers/smart_agent.py` (startup throttling, retries), `.gitignore`
- Rename: `DUELOS-RULES.PDF` → `duels/DUELOS-RULES.md`
- Reuse: `bazaar_sdk.Bazaar.duels/duel_say/duel_accept`, the `smart_agent.wait_tick` pattern, and the `sim_test.py` fake-client style

## Verification
1. `python dealers/sim_test.py`: the existing dealer sim still passes after the `smart_agent.py` changes.
2. `python duels/duel_sim_test.py`: all fake rivals; assert no out-of-limit offers or accepts and no duel ending without a deal.
3. `python duels/duel_agent.py` (dry run, real key): check `duelos-log.jsonl` → `first_duel_raw` against the field names `role`, `your_limit`, `rival_offer`, `deadline` and the scenario id. Fix the names if they differ.
4. A practice duel with `--live` before 11:30 Saturday: look at the rounds to close and the distance from our limit, then tune constants.
5. `python dealers/smart_agent.py` with `DEALER=abuela`: no `rate_limited` crash at startup.
