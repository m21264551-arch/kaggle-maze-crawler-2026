# Maze Crawler Current Strategy

This is the steering wheel for future context windows. Read this before `patchnotes.md`; use `patchnotes.md` as the append-only evidence log.

## Objective

Maximize Kaggle Maze Crawler leaderboard rank, aiming for top 3. Do not optimize for tidy code, cleverness, or copying visible replay style unless it survives benchmark gates.

## Current Source Of Truth

- Submission candidate: `main.py`
- Control baseline: `baseline.py`
- Current status: `main.py` is intentionally identical to `baseline.py` after reverting a bundled target-bot mimic patch that regressed local benchmark margin.
- Trusted local Python: `/Users/michaely/anaconda3/bin/python3`
- Default benchmark gate:

```bash
/Users/michaely/anaconda3/bin/python3 benchmark.py --agent main.py --opponent baseline.py --seeds 8 --duel --failure-report
```

The plain `python3` command may resolve to Xcode Python inside this folder and fail to import `kaggle_environments`.

## Target Replay Set

Only copy from these bots unless the user changes the target set:

- `bunterrrrr`
- `Андрей Савельев`
- `Takahiro Matsumoto`

Important interpretation rule: raw build counts are misleading. Separate **peak live units** from **replacement churn**.

## Workflow Prompt

Use this operating loop for strategy work:

1. Confirm local evaluation works with the Anaconda Python path above.
2. Parse target-bot replays only; do not infer from Hazy, AI TOP3, or ZERO unless explicitly asked.
3. For each loss or suspicious win, report factory death step, last 12 factory actions, factory gap, jump cooldown, legal exits, enemy factory distance, mine status, and whether we spent a build turn in the last 20 turns.
4. Identify the top three concrete failure modes with replay episode IDs.
5. Convert exactly one failure mode into one minimal code hypothesis.
6. Implement only that hypothesis.
7. Run the benchmark gate. Prefer 32+ duel games before promotion when time allows.
8. Keep the change only if duel-pair margin is positive and P0/P1 margins do not show a new collapse.
9. If it regresses, revert the code and append a rejected row to `patchnotes.md`.
10. After 2-3 confirmed wins, copy `main.py` to `baseline.py` so the bar moves up.

## Current Tactical Beliefs

- Factory survival beats economy polish. A rich dead factory is still dead.
- Mine economy remains the core architecture.
- Keep one-live-miner discipline; replacement miners are good, miner swarms are not.
- Scouts are optional and expensive. bunterrrrr and Андрей use zero scouts; Takahiro's scout count is mostly replacement churn.
- Workers should be late plows or emergency wall tools, not early economy.
- Jumps should usually buy northward progress. Jump banking was catastrophic in prior tests.
- SOUTH is for scroll-trap backtracking or desperation, not normal routing.

## Known Rejected Ideas

- Worker rush / early worker economy.
- Leaving a safe mine early because it is almost empty.
- Banking factory jumps late.
- Center-biased direction order.
- Bundled target-bot mimic patch: unconditional enemy-factory escape + late scout cap + delayed worker + wider late emergency jump + local mine station cap. It regressed `main.py` vs `baseline.py` by `-720` duel-pair margin on 8 seeds.

## Patchnotes Discipline

For every strategy change, append:

- Hypothesis
- Code change
- Replay evidence
- Benchmark command and result
- Keep/revert decision

Keep old notes, but mark stale sections as historical. The top of this file is the current truth.
