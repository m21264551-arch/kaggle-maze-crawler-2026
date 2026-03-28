# Maze Crawler — Patch Notes

Read `CURRENT_STRATEGY.md` first. This file is the append-only evidence log; older sections may be historical and superseded.

A running log of what changes have helped vs. regressed. Use `/Users/michaely/anaconda3/bin/python3 benchmark.py --agent main.py --opponent baseline.py --seeds 8 --duel`. "Duel pair" = same seed run from both sides (only fair comparison).

## Current ELO snapshot
- Public LB plateau: **~1300-1400**
- Target: **2200**
- Current target replay bots: bunterrrrr, Андрей Савельев, Takahiro Matsumoto

---

## Iteration timeline (chronological, oldest first)

### `submitted_600.py` — Iteration 1 (LB ~600)
- Basic worker-rush, no mine economy, no BFS jumps.
- Bench vs baseline.py: **0W-12L (-5407 avg margin)**. Floor.

### `submitted_v5.py` — V2 (LB ~600-900)
- Adds scout + crystal pathing + better north march.
- Bench vs baseline.py: **0W-11L-1D (-5172 avg margin)**. Still gets crushed by the mine-economy bots.
- Bench vs main.py: **0W-12L**. Decisively obsolete.

### `public_top2.py` — reference (LB ~1223)
- Jump-preferred BFS + mirror vision + emergency escape. No mine economy.
- This is the bone of every modern iteration. Beats anything without mines, loses to anything with mines.

### `caadfb1` "Add replay-inspired mine economy agent"
- **Big jump.** Adds: persistent wall memory with mirror inference, mining-node memory with E/W symmetry mirroring, `BUILD_MINER_<DIR>` to spawn miner directly onto a mining node, factory parks on its own mine for 50 e/turn passive income.
- This is the architecture every later iteration is patching, not replacing.

### `bf6209a` "Improve factory wall sweeping" + `4884a80` "Improve factory survival"
- Tightened the desperation jump and the SOUTH fallback. Probably a real gain.

### `a702d22` "fix logic for early mining"
- Tweaked `MINE_SAFE_GAP` / `MINE_ROUTE_DEPTH` for the factory's first mining-node hunt.

### `8fd8c91` "Update main.py" — adds `WORKER_CHARGE_BUFFER = 350`
- Factory now transfers excess energy to an adjacent low-energy worker (so worker can REMOVE walls). Solid micro-optimization.

### `264eb4f` "gus"
- `MINE_ROUTE_DEPTH 18 → 22` (longer mine-hunt range)
- Adds `SCOUT_DELAY_STEP = 40` (don't build scout in opening — saves 50 energy for the first miner)
- Adds `LOW_GAP_WORKER_ENERGY_BUFFER = 1300` (allows worker spawn even at low gap if factory is loaded)
- **Probably the strongest version of the agent.** Aggressive opening, doesn't waste 50e on a useless scout.

### `8be487f` "anti suicide patch"
- Adds `enemy_factory_escape_action` — runs away from adjacent enemy factory if our backup energy ≤ theirs.
- Adds `safer_factory_step` — vetoes SOUTH/JUMP_SOUTH unless gap > 3 + step < 430 OR factory is on a known one-way south-trap.
- ⚠️ **Suspect regressor.** The veto is too eager; see baseline.py vs main.py bench below.

### `b7f89fa` "Changes" (current `main.py`)
- Adds `SCROLL_TRAP_GAP = 14` + `is_scroll_trap` / `unsafe_scroll_trap` (cell whose only exit is SOUTH is treated as lethal when the boundary is within 14 rows and jump is on cooldown).
- Adds `WORKER_PLOW_STEP = 430` + `guard_factory_action` + worker-plow logic (after step 430, factory + 1 worker walk north in lockstep; worker REMOVEs walls).
- `factory_trap_backtrack` — allows SOUTH from a one-way trap even when jump is on cooldown.

---

## Head-to-head benchmark (8 seeds × 2 sides = 16 games)

| Agent A | Agent B | A wins | A losses | Avg margin |
|--------|--------|--------|----------|------------|
| `main.py` | `baseline.py` (= caadfb1-era) | **7** | **9** | **-477** |
| `main.py` | `submitted_v5.py` | 12 | 0 | +5348 |
| `submitted_v5.py` | `baseline.py` | 0 | 11 | -5172 |
| `submitted_600.py` | `baseline.py` | 0 | 12 | -5407 |

**Ordering: baseline.py (caadfb1) ≳ main.py >> submitted_v5.py >>> submitted_600.py.**

The "anti-suicide patch" + "worker plow" changes added in the last two commits are net-negative against the pre-patch version. They are not catastrophic — they win 7/16 — but they leak more than they save. The plausible regressor is `safer_factory_step` inverting the SOUTH-fallback logic:

- Old (baseline): `if factory_gap <= 3: SOUTH` (desperate escape when wedged at the south bound).
- New (main): `if factory_gap > 3 and step < 430: SOUTH` (only retreat when there's runway).

Combined effect: when our factory is wedged at gap ≤ 3 in mid-game with no jump and no north exit, baseline.py walks SOUTH and lives; main.py falls through to BUILD_WORKER or IDLE and dies.

---

## Target replay audit

User-ranked bots worth copying right now: **bunterrrrr**, **Андрей Савельев**, **Takahiro Matsumoto**. I parsed every local replay containing those names, not the full top-public folder.

| Bot | Local sample | Unit pattern | Factory movement | Mine pattern | Copy this |
|-----|--------------|--------------|------------------|--------------|-----------|
| bunterrrrr | 19 games, 17W-1L-1D | **0 scouts**, 3.7 miners built but peak live miner = 1, 1.3 workers built with peak live worker < 1 | 228/228 jumps were NORTH; only 146 SOUTH moves across 19 games | 1.5 peak mines, 119 factory-on-mine steps/game | Zero-scout default, one-live-miner discipline, directional miner spawns, north-only jump bias |
| Андрей Савельев | 4 games vs us, 2W-2L | **Factory only**: no scouts, miners, workers, mines, or transfers | 18 jumps/game, mostly NORTH with lateral jumps only to route/escape | none | Treat factory survival as the floor: do not spend build turns when collision/scroll pressure is active |
| Takahiro Matsumoto | 12 games vs us, 5W-7L | Scout/miner churn, but peak live scout ~= 1 and peak live miner ~= 1; workers mostly step 403+ | 15.6 jumps/game, 70% NORTH | 2.2 peak mines, 139 factory-on-mine steps/game | Replacement cycles and mine uptime; do **not** copy the raw scout/miner churn |

Replay-backed diagnosis of our bad losses:
1. **Adjacent enemy factory handling is too cute.** In several Takahiro/Андрей games our factory stayed adjacent or walked into an adjacent enemy factory because `enemy_factory_escape_action` skipped escape when our backup energy looked better. That turns a won economy game into a cheap factory collision.
2. **Late scout/build turns are poison.** Replays show our older submissions still building scouts near steps 330-480 while factory pressure was active. bunter and Андрей spend zero turns on scouts; Takahiro rebuilds scouts, but only wins when the factory still has runway.
3. **Emergency jumping fires too late.** Our old emergency jump at `gap <= 2` sometimes leaves only one move cycle before scroll. bunter jumps NORTH from step 1 and never banks; Андрей survives by keeping the factory moving.
4. **Mining route ties drag us sideways.** Target bots either avoid mines entirely (Андрей) or keep the mine cycle close and simple (bunter). Equal-distance station choices should prefer local columns before lateral wandering.

What to do now:
1. **Run from adjacent enemy factories unconditionally** if there is a safe move/jump. Do not assume mutual factory contact is good just because backup energy looks favorable.
2. **Cap scout builds to the early game only.** If we did not build a scout before the first mine route is established, skip it; do not let the first scout appear in late-game pressure.
3. **Raise emergency jump threshold in late game** so a NORTH jump happens before the factory is already at gap 1-2.
4. **Tie-break mine station goals by column locality** so replacement miners do not pull the factory across the board.
5. **Keep workers as late plows/replacements.** Do not copy scout/miner/worker churn as live-unit caps.

What not to do:
1. Do not copy AI TOP3/Hazy/ZERO for this round; user signal says these three are the comparison set.
2. Do not copy Takahiro's raw 8-20 scout build counts. His peak live scout is still one; the count is replacement churn.
3. Do not worker-rush or leave a safe mine early. Previous benches already punished both.
4. Do not treat SOUTH as normal routing. It remains scroll-trap backtrack/desperation only.

---

## Replay-derived queue at this checkpoint

Historical checkpoint: several of these were later shipped or rejected. The current queue is in the Iteration log below.

### High-impact, low-risk
- **Revert the `safer_factory_step` SOUTH veto** or rewrite it so it only blocks SOUTH when the SOUTH cell is itself a known scroll-trap. Status: shipped in the current baseline.
- **Build a second miner when current mine drops below ~400 energy** (mineMaxEnergy is 1000; mine generates 50/turn so you've got ~12 turns of warning). Status: shipped as `MINE_REFRESH_THRESHOLD = 400`, but do not make the factory leave a safe mine early.
- **Don't build a scout in the opening if a mining node is within 5 cells of the factory.** Status: shipped for visible early nodes; zero-scout opening still needs a clean A/B.

### Medium-impact
- **Bias factory jumps toward NORTH unless there's a known node to the side.** Status: shipped as a NORTH-first tiebreak; keep tightening lateral jumps only with replay evidence.
- **Pre-position the worker before step 430.** Status: partially shipped (`WORKER_PLOW_STEP = 420`, second worker after 380); next work is target quality, not earlier worker spam.
- **Cache `bfs_jump` results across turns** when the factory is parked on a mine — we recompute the same BFS every turn the factory IDLEs.

### Speculative
- **Wall-build to deny enemy scout vision.** Workers can BUILD walls, and the maze is mirrored — a strategically placed wall on our half projects to a mirrored cell the enemy will eventually need to cross.
- **Track enemy factory column via the mirror.** If we see their robot at column X, the enemy factory is probably at `width - 1 - X` ± a few. Could inform jump direction in late game.

### Known dead-ends (do not retry without new evidence)
- **Worker rushes early game** (`submitted_v5.py` style) — gets dominated by any mine-economy bot.
- **Keeping >1 live scout** — every extra live scout burns 50e and the marginal vision is tiny once we have wall memory. Replacement scouts after the old scout dies are a separate, still-plausible idea.
- **Bigger `MINE_SAFE_GAP`** in mid-game — top bots will happily spawn a miner at gap=5 and walk the factory onto the mine before the scroll catches up. Being conservative here gives up free energy.

---

## Cadence

This file should be updated after each new submission with:
1. The commit hash / submission ID
2. The diff against the previous version (one-line summary)
3. The 16-game bench vs `baseline.py`
4. The LB rank change

The bench vs `baseline.py` is the *only* fast signal that's worth trusting. LB ranks have 24-48h of noise.

---

## Current state (this commit)

- `baseline.py` rewritten: caadfb1-era mine economy + scroll-trap detection + worker-plow + three replay-derived fixes:
  - **Restored low-gap SOUTH desperation escape** (the regressor in the "anti-suicide patch" — `safer_factory_step` was vetoing SOUTH at gap ≤ 3, deleting the live-saving fallback).
  - **Skip opening scout when a mining node is visible** (`step_num < 80` + `nodes_mem`) — saves 50e for the first miner.
  - **Refresh-miner trigger** (`MINE_REFRESH_THRESHOLD = 400`) — start moving toward the next node when our current mine drops below 400e so production doesn't have a dead window.
  - Added a NORTH-first tiebreak in `bfs_jump` so equal-cost paths prefer northward progress.
  - `WORKER_PLOW_STEP` brought forward 430 → 420 (small bias toward earlier worker pre-positioning).

- `main.py` reset to the same code as `baseline.py`. Fresh starting point for iteration.

**Bench results:**

| Agent A | Agent B | A wins | A losses | A margin |
|---------|---------|--------|----------|----------|
| new `baseline.py` | old `main.py` (b7f89fa) | **10** | **4** (2 draws) | **+1929** |
| new `baseline.py` | `submitted_v5.py` | 12 | 0 | +5473 |
| new `main.py` | new `baseline.py` | 5 | 5 (6 draws) | ±0 (identical code) |

The +1929 margin vs the prior main.py is real signal — a full duel-pair win across 5 of 6 paired seeds.

## Workflow from here

1. Modify `main.py` with one focused change at a time.
2. `/Users/michaely/anaconda3/bin/python3 benchmark.py --agent main.py --opponent baseline.py --seeds 8 --duel`.
3. If `Duel pairs` margin is positive AND the per-side margins are both non-negative → keep, append a row to the timeline above with the seed-count and margin, and proceed.
4. If it regresses → revert, append a "tried and rejected" note explaining the failure mode so we don't try the same thing twice.
5. After accumulating 2-3 confirmed wins in `main.py`, copy main → baseline so the bar moves up.

---

## Iteration log (latest first)

### Iter 2 — confirmed wins promoted to `baseline.py`

After the first promotion, `main.py` was iterated; the following changes survived 32–48 seed benchmarks and were folded into the new `baseline.py`:

| Change | 32-game duel margin | 48-game duel margin | Status |
|--------|---------------------|---------------------|--------|
| **Multi-direction emergency jump** — when `factory_gap <= 2` and `f_jump_cd <= 0`, try every direction (NORTH→EAST→WEST) instead of falling through when the NORTH landing is occupied by a friendly. Fixed seed-1 P0 death at step 488 (factory at gap=1, mvCD=2, jCD=0, walked WEST instead of jumping). | ±0 (symmetric — both sides also fix in self-play) | n/a | shipped (correctness fix) |
| **Scout transfers to factory only when energy ≥ 60** (not 30) — at 30 the scout immediately dumps its 50e spawn energy back to the factory and dies. Threshold 60 only fires after a crystal pickup, so the scout retains exploration value. | +172 → wash | wash | shipped (paired with crystal pickup) |
| **Scout opportunistic crystal pickup** within Manhattan 6 — diverts scout from the escort row to grab nearby crystals, then ships the energy back when adjacent to factory. | folded into scout transfer | wash | shipped |
| **2nd worker after step 380** (`worker_cap = 2 if step_num >= 380 else 1`) — redundant wall plowing for the late-game scroll catch-up. | +630 (7-4-5) | **+415 (7-9-8)**; avg reward +207 | shipped — wins by big margin, loses tiebreakers narrowly |

### Current targeted replay-derived guidance

After narrowing the replay set to bunterrrrr / Андрей Савельев / Takahiro Matsumoto, the current patch should improve **factory survival under pressure** first and economy second:

What to do:
- Escape adjacent enemy factories every time a safe action exists. The old backup-energy gate caused avoidable factory contact against Андрей/Takahiro.
- Keep one-live-miner discipline, but route replacement miners locally: prefer nearby/straight-ahead station goals and directional spawns.
- Treat scouts as optional early vision only. bunter/Андрей use zero scouts; Takahiro's many scout builds are replacement churn with peak live scout ~= 1.
- Raise late emergency jump timing from "last-second" to "before the scroll is already touching us."
- Keep workers as late plows/replacements, not early economy units.

What not to do:
- Do not add more live scouts/miners/workers because Takahiro's raw build count is high.
- Do not copy factory-only Андрей completely; use him as the survival floor, then keep our mine economy once safe.
- Do not leave safe mines early or bank jumps. Both already produced catastrophic benches.

### Tried and rejected (do not retry without new evidence)

| Change | What broke | Margin |
|--------|-----------|--------|
| **Bundled target-bot mimic patch** — unconditional enemy-factory escape + scout cutoff at 120 + normal worker delay to 330 + late emergency jump gap 6 + local mine-station candidate cap | Too many coupled changes. Local benchmark regressed vs `baseline.py`, especially P0 (`1W-7L`, -1478 avg). Reverted code; keep the replay audit, but test one hypothesis at a time. | -720 duel-pair margin on 8 seeds |
| **`WORKER_PLOW_STEP = 380`** | Workers pre-positioned too early, blocked the factory's path during mine-hunt phase. | -79 |
| **Late-game jump banking** — pass `jump_cd=999` to `bfs_jump` when `step >= 380 and gap > 6` to save the CD for emergencies. | `bfs_jump` returned `None` when the only path was a jump-through-wall. Factory IDLEd into death. | -6240 catastrophic |
| **`on_safe_mine` skip when `needs_fresh_miner`** — let factory leave a depleting mine early to head for the next node. | Factory died in transit. The mine economy is sticky for a reason: the BFS path to the next node is usually longer than the scroll-tolerance budget. | -2607 |
| **`mine_almost_empty` (<150e) + sufficient energy** trigger to leave a mine | Same as above, different threshold. | -2562 |
| **Center-biased direction order** (P0 prefers EAST, P1 prefers WEST) intended to fix the persistent P0 (-1381) vs P1 (+1275) asymmetry | WEST-first for P1 was actively worse than EAST-first. The "toward center" intuition is wrong. | -1527 |
| **Zero-scout opening** — removed the entire `BUILD_SCOUT` elif branch (bunterrrrr/Андрей Савельев target replays use no scouts). 8-seed gate looked promising (+66.5 duel-pair margin, P0 lifted -2222 → -1450) but at 32 seeds the duel-pair margin flipped to **-93.34** (11W-12L-9D), avg margin -46.67. P1 regressed sharply +2222 → +704 — losing scout vision meant the factory walked into early-game collisions (seed 7 had both sides die at step 151). The zero-scout target-bot pattern doesn't transfer to our code without paired vision substitutes; do not retry without first adding factory-side exploration scaffolding. | -93.34 duel-pair margin on 32 seeds |
| **BUILD_WORKER while on safe mine (idle-turn reuse)** — modified the `on_safe_mine or adjacent_node_wait` branch to attempt `BUILD_WORKER` instead of IDLE when the factory is parked on a healthy mine with `f_build_cd==0`, `not needs_fresh_miner`, `step_num>=180`, `factory_gap > mine_gap + 3`, and worker cap not reached. 8-seed result was **exactly identical to baseline-vs-baseline** (0W-0L-8D, ±0 margin), meaning the conditions never triggered in 16 games. The existing post-elif `BUILD_WORKER` branch already consumes the same conditions during transit between mines, so by the time the factory parks the worker cap is already saturated. Insertion location was wrong — the wasted turns happen later, after the lone worker is built, but then unit caps prevent another build. Inert change, reverted. | 0.00 (no trigger) |

### Persistent open problem: P0/P1 asymmetry

Across every benchmark I ran on 16+ seeds:
- P0 (left-half factory) loses badly: **-1300 to -1500** avg margin
- P1 (right-half factory) wins big: **+1200 to +2200** avg margin

The agent and the baseline are mirror-symmetric code. The asymmetry is in the maze generation or the move-resolution order. I tried center-biased BFS to fix it — regressed. Worth investigating directly: instrument a P0-only loss vs the same-seed P1-side game and find where the divergence starts. Likely candidates:

- Default `DIRS = ("NORTH", "EAST", "WEST", "SOUTH")` favors EAST-then-WEST in every linear scan (`adjacent_own_mine_step`, `adjacent_node_build_action`, etc.). For P0 starting on the left, EAST is "into the maze"; for P1 starting on the right, EAST is "into a wall."
- `mining_station_goals` sort key `(distance, -row)` ignores column; equally distant stations on left vs right of the factory get arbitrary preference.

### What's worth trying next

Reordered by what's still plausible after the failed experiments:

**High-impact, low-risk:**
- **Node/station tie-break by column distance** — when choosing the next mining station, break ties by `abs(node[0] - factory_col)` and then northward progress so we don't drag the factory across the maze for an equal-distance node.
- **Worker target staggering** — with 2 workers, send worker-2 to `(factory_col, factory_row + 3)` so it pre-clears walls 2 rows ahead of the close plower. Replay caveat: top bots peak at one live worker, so this must benchmark as a plow-quality fix, not a unit-count fix.

**Medium-impact:**
- **Replacement scout after scout death** — top bots often build 4+ scouts over a game, but peak live scout is one. Rebuild only when the old scout is gone and we lack fresh forward vision; do not build a second live scout.
- ~~**Zero-scout opening A/B**~~ — tested and rejected (see Tried and rejected). Losing scout vision regresses P1 too much because the factory blunders into early collisions.
- **Wall pre-clearing via worker prediction** — when factory is on a mine, send the worker to remove the wall on the cell the factory will need to escape to. Currently the worker just escorts at `factory_row + 7`, not the actual planned escape cell.

**Speculative:**
- Track `globalCrystals` etc. — if the env exposes them, we could plan routes through known-good cells without relying on vision.
- Instrument a one-game diff between P0 and P1 plays of the same seed to root-cause the asymmetry before chasing more changes.
