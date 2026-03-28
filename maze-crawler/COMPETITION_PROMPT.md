# Maze Crawler Competition Prompt

Use this file as the durable starting prompt for future competition work.
Read it before changing code, then follow the referenced strategy notes.

## Objective

Maximize Kaggle Maze Crawler leaderboard rank, aiming for top 3. Optimize
for competitive score only. Do not optimize for tidy code, cleverness, broad
refactors, or copying visible replay style unless the change survives the
benchmark gates.

## Read Order

Read these files first, in order:

1. `AGENTS.md`
2. `CURRENT_STRATEGY.md`
3. `patchnotes.md`
4. `README.md`
5. `main.py`, `baseline.py`, and `benchmark.py`

`CURRENT_STRATEGY.md` is the steering wheel. `patchnotes.md` is the
append-only evidence log.

## Source Of Truth

- Submission candidate: `main.py`
- Control baseline: `baseline.py`
- Trusted local Python: `/Users/michaely/anaconda3/bin/python3`
- Default benchmark gate:

```bash
/Users/michaely/anaconda3/bin/python3 benchmark.py --agent main.py --opponent baseline.py --seeds 8 --duel --failure-report
```

The plain `python3` command may resolve to Xcode Python inside this folder
and fail to import `kaggle_environments`.

## Operating Loop

1. Confirm local evaluation works with the Anaconda Python path above.
2. Inspect `CURRENT_STRATEGY.md` and the latest entries in `patchnotes.md`.
3. Use benchmark failures or target replay evidence to identify the top three
   concrete failure modes.
4. Pick exactly one minimal hypothesis.
5. Modify only `main.py` unless benchmark tooling or logging needs a tiny
   support change.
6. Run the default benchmark gate.
7. If promising, prefer 32+ duel games before promotion.
8. Keep the change only if duel-pair margin is positive and P0/P1 margins do
   not show a new collapse.
9. If it regresses, revert the code and append a rejected row to
   `patchnotes.md`.
10. After 2-3 confirmed wins, copy `main.py` to `baseline.py` so the bar
    moves up.

## Strategy Priorities

- Factory survival beats economy polish.
- Mine economy is the core architecture.
- Keep one-live-miner discipline.
- Scouts are optional early vision and should not become late-game build
  poison.
- Workers should be late plows or emergency wall tools, not early economy.
- Jumps should usually buy northward progress.
- SOUTH is for scroll-trap backtracking or desperation, not normal routing.
- Do not bundle several strategy changes together.
- Do not retry known rejected ideas without new evidence.

## Current High-Value Areas

- Investigate and fix P0/P1 asymmetry.
- Test node/station tie-breaks by column locality.
- Improve worker plow quality without increasing early worker spam.
- Improve enemy-factory collision avoidance only as one isolated hypothesis.
- Improve late emergency jump timing only as one isolated hypothesis.

## Replay Discipline

- Use only the target replay bots named in `CURRENT_STRATEGY.md` unless the
  user changes the target set.
- Separate peak live units from replacement churn.
- For each loss or suspicious win, report factory death step, last 12 factory
  actions, factory gap, jump cooldown, legal exits, enemy factory distance,
  mine status, and whether we spent a build turn in the last 20 turns.
- Do not infer strategy from non-target bots unless explicitly asked.

## Session Deliverables

At the end of each strategy session, report:

- The failure mode targeted.
- The exact code change made.
- Benchmark command and result.
- Whether the change was kept or reverted.
- The `patchnotes.md` update.

