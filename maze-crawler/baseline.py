"""Maze Crawler agent — current submission candidate.

This file is the agent we submit. It starts as a copy of `baseline.py` (the
fixed strong reference) and is where new iterations land. Run
`python3 benchmark.py --agent main.py --opponent baseline.py --seeds 8 --duel`
after each change — a positive duel-pair margin is the gating signal before
shipping.

See `patchnotes.md` for the history of what's helped and what's regressed.
"""
from collections import deque

FACTORY, SCOUT, WORKER, MINER = 0, 1, 2, 3
DIRS = ("NORTH", "EAST", "WEST", "SOUTH")
OFFSETS = {"NORTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0), "SOUTH": (0, -1)}
WALL_BITS = {"NORTH": 1, "EAST": 2, "SOUTH": 4, "WEST": 8}
MINE_SAFE_GAP = 5
MINE_ROUTE_DEPTH = 22
MINER_ENERGY_BUFFER = 25
WORKER_CHARGE_BUFFER = 350
SCOUT_DELAY_STEP = 40
LOW_GAP_WORKER_ENERGY_BUFFER = 1300
WORKER_PLOW_STEP = 420
SCROLL_TRAP_GAP = 14
MINE_REFRESH_THRESHOLD = 400  # spawn next miner when current mine drops below this

MIRROR_WALL = [0] * 16
for _v in range(16):
    _m = (_v & 1) | (_v & 4)
    if _v & 2: _m |= 8
    if _v & 8: _m |= 2
    MIRROR_WALL[_v] = _m

_memory = {}


def agent(obs, config):
    global _memory
    try:
        return _agent_inner(obs, config)
    except Exception:
        return {uid: "IDLE" for uid in obs.robots if obs.robots[uid][4] == obs.player}


def _agent_inner(obs, config):
    global _memory
    actions = {}
    width = config.width
    south = obs.southBound
    north = obs.northBound
    player = obs.player

    if getattr(obs, "step", None) == 0:
        _memory = {"walls": {}, "nodes": set(), "own_mines": set(), "scouts_built": 0}

    if "walls" not in _memory:
        _memory["walls"] = {}
    walls_mem = _memory["walls"]

    for i, w in enumerate(obs.walls):
        if w == -1:
            continue
        r = south + i // width
        c = i % width
        walls_mem[(c, r)] = w
        mc = (width - 1) - c
        mw = MIRROR_WALL[w]
        if (mc, r) not in walls_mem:
            walls_mem[(mc, r)] = mw

    if len(walls_mem) > 2000:
        cutoff = south - 5
        walls_mem = {k: v for k, v in walls_mem.items() if k[1] >= cutoff}
        _memory["walls"] = walls_mem

    def parse_pos(key):
        c, r = key.split(",", 1)
        return int(c), int(r)

    nodes_mem = _memory.setdefault("nodes", set())
    own_mines_mem = _memory.setdefault("own_mines", set())
    visible_nodes = set()
    for key in obs.miningNodes:
        c, r = parse_pos(key)
        visible_nodes.add((c, r))
        nodes_mem.add((c, r))
        nodes_mem.add((width - 1 - c, r))

    # Track our own mines + their current energy
    own_mine_energy = {}
    for key, data in obs.mines.items():
        pos = parse_pos(key)
        nodes_mem.discard(pos)
        if len(data) > 2 and data[2] == player:
            own_mines_mem.add(pos)
            own_mine_energy[pos] = data[0]

    nodes_mem = {
        (c, r)
        for c, r in nodes_mem
        if 0 <= c < width and south <= r <= north and r - south > 1 and (c, r) not in own_mines_mem
    }
    own_mines_mem = {
        (c, r)
        for c, r in own_mines_mem
        if 0 <= c < width and south <= r <= north
    }
    _memory["nodes"] = nodes_mem
    _memory["own_mines"] = own_mines_mem

    def get_wall(c, r):
        return walls_mem.get((c, r), 0)

    def can_move(c, r, d):
        dc, dr = OFFSETS[d]
        nc, nr = c + dc, r + dr
        if not (0 <= nc < width and south <= nr <= north):
            return False
        return not (get_wall(c, r) & WALL_BITS[d])

    def can_jump(c, r, d):
        dc, dr = OFFSETS[d]
        nc, nr = c + 2 * dc, r + 2 * dr
        if not (0 <= nc < width and south <= nr <= north):
            return False
        return get_wall(nc, nr) != 15

    def is_scroll_trap(c, r):
        return (
            can_move(c, r, "SOUTH")
            and not can_move(c, r, "NORTH")
            and not can_move(c, r, "EAST")
            and not can_move(c, r, "WEST")
        )

    def unsafe_scroll_trap(c, r, next_jump_cd):
        return r - south <= SCROLL_TRAP_GAP and next_jump_cd > 0 and is_scroll_trap(c, r)

    def can_factory_jump(c, r, d):
        if not can_jump(c, r, d):
            return False
        dc, dr = OFFSETS[d]
        nc, nr = c + 2 * dc, r + 2 * dr
        return not unsafe_scroll_trap(nc, nr, 20)

    my_robots = {uid: d for uid, d in obs.robots.items() if d[4] == player}
    enemy_robots = {uid: d for uid, d in obs.robots.items() if d[4] != player}
    my_positions = {(d[1], d[2]): uid for uid, d in my_robots.items()}
    reserved = set()
    counts = {rt: sum(1 for d in my_robots.values() if d[0] == rt) for rt in range(4)}

    crystals = {}
    for k, v in obs.crystals.items():
        parts = k.split(",")
        crystals[(int(parts[0]), int(parts[1]))] = v

    def adjacent_direction(c, r, target):
        for d, (dc, dr) in OFFSETS.items():
            if (c + dc, r + dr) == target:
                return d
        return None

    def spawn_clear(c, r, d):
        dc, dr = OFFSETS[d]
        target = (c + dc, r + dr)
        return (
            0 <= target[0] < width
            and south <= target[1] <= north
            and target not in my_positions
            and target not in reserved
            and can_move(c, r, d)
        )

    def adjacent_node_build_action(c, r, energy, build_cd):
        if build_cd > 0 or counts[MINER] > 0:
            return None
        if energy < getattr(config, "minerCost", 300) + MINER_ENERGY_BUFFER:
            return None
        choices = []
        for d, (dc, dr) in OFFSETS.items():
            node = (c + dc, r + dr)
            if node in visible_nodes and spawn_clear(c, r, d):
                choices.append((node[1], d))
        if not choices:
            return None
        _, direction = max(choices)
        return f"BUILD_MINER_{direction}"

    def adjacent_own_mine_step(c, r, gap, safe_gap):
        if gap <= safe_gap:
            return None
        for d in DIRS:
            dc, dr = OFFSETS[d]
            target = (c + dc, r + dr)
            if target in own_mines_mem and can_move(c, r, d):
                return d
        return None

    def adjacent_worker_transfer_action(c, r, energy):
        if energy < WORKER_CHARGE_BUFFER:
            return None
        choices = []
        for d, (dc, dr) in OFFSETS.items():
            pos = (c + dc, r + dr)
            uid = my_positions.get(pos)
            if not uid:
                continue
            robot = my_robots[uid]
            if robot[0] != WORKER or not can_move(c, r, d):
                continue
            wall_ahead = get_wall(pos[0], pos[1]) & WALL_BITS["NORTH"]
            if wall_ahead and robot[3] <= getattr(config, "wallRemoveCost", 100) * 2:
                direction_rank = {"NORTH": 3, "EAST": 2, "WEST": 2, "SOUTH": 1}[d]
                choices.append((pos[1], direction_rank, -robot[3], d))
        if not choices:
            return None
        return f"TRANSFER_{max(choices)[3]}"

    def mining_station_goals(c, r, energy):
        if energy < getattr(config, "minerCost", 300) + MINER_ENERGY_BUFFER:
            return []
        goals = set()
        for node in nodes_mem:
            if node[1] - south <= MINE_SAFE_GAP:
                continue
            if abs(node[0] - c) + abs(node[1] - r) > MINE_ROUTE_DEPTH + 2:
                continue
            for d, (dc, dr) in OFFSETS.items():
                station = (node[0] - dc, node[1] - dr)
                if not (0 <= station[0] < width and south <= station[1] <= north):
                    continue
                if can_move(station[0], station[1], d):
                    goals.add(station)
        return sorted(goals, key=lambda p: (abs(p[0] - c) + abs(p[1] - r), -p[1]))

    def bfs_first_step(start, goals, depth=20, avoid_occupied=True, avoid_traps=False, jump_cd=0):
        if not goals:
            return None
        goal_set = set(goals)
        if start in goal_set:
            return "IDLE"
        q = deque([(start, None, 0)])
        seen = {start}
        while q:
            (c, r), first_d, dist = q.popleft()
            if (c, r) in goal_set and dist > 0:
                return first_d
            if dist >= depth:
                continue
            for d in DIRS:
                if not can_move(c, r, d):
                    continue
                nc, nr = c + OFFSETS[d][0], r + OFFSETS[d][1]
                if (nc, nr) in seen:
                    continue
                if avoid_occupied and (nc, nr) in reserved:
                    continue
                if avoid_occupied and (nc, nr) in my_positions and (nc, nr) != start:
                    continue
                if avoid_traps and unsafe_scroll_trap(nc, nr, max(0, jump_cd - dist - 1)):
                    continue
                seen.add((nc, nr))
                q.append(((nc, nr), first_d or d, dist + 1))
        return None

    # Jump-preferred BFS with NORTH-biased tiebreak. EAST before WEST.
    # Center-biased ordering (EAST for P0, WEST for P1) was tried and
    # regressed -1527 — the "toward center" intuition is wrong, the symmetric
    # walls produce asymmetric outcomes for unclear reasons. Do not retry
    # without new evidence.
    NORTH_FIRST_DIRS = ("NORTH", "EAST", "WEST", "SOUTH")

    def bfs_jump(start, goals, jump_cd, depth=20):
        if not goals:
            return None
        goal_set = set(goals)
        q = deque([(start, None, 0, min(jump_cd, 20))])
        seen = {(start[0], start[1], jump_cd <= 0)}
        while q:
            (c, r), first_d, dist, jcd = q.popleft()
            if (c, r) in goal_set and dist > 0:
                return first_d
            if dist >= depth:
                continue

            if jcd <= 0:
                for d in NORTH_FIRST_DIRS:
                    if not can_factory_jump(c, r, d):
                        continue
                    dc, dr = OFFSETS[d]
                    nc, nr = c + 2 * dc, r + 2 * dr
                    key = (nc, nr, False)
                    if key in seen:
                        continue
                    seen.add(key)
                    q.append(((nc, nr), first_d or f"JUMP_{d}", dist + 1, 20))

            for d in NORTH_FIRST_DIRS:
                if not can_move(c, r, d):
                    continue
                nc, nr = c + OFFSETS[d][0], r + OFFSETS[d][1]
                njcd = max(0, jcd - 1)
                if unsafe_scroll_trap(nc, nr, njcd):
                    continue
                key = (nc, nr, njcd <= 0)
                if key in seen:
                    continue
                seen.add(key)
                q.append(((nc, nr), first_d or d, dist + 1, njcd))

        return None

    def record(uid, act, col, row):
        actions[uid] = act
        if act.startswith("JUMP_"):
            d = act.split("_")[1]
            dc, dr = OFFSETS[d]
            reserved.add((col + 2 * dc, row + 2 * dr))
        elif act in OFFSETS:
            dc, dr = OFFSETS[act]
            reserved.add((col + dc, row + dr))
        elif act.startswith("BUILD_"):
            parts = act.split("_")
            d = parts[2] if len(parts) > 2 else "NORTH"
            dc, dr = OFFSETS.get(d, (0, 1))
            reserved.add((col + dc, row + dr))
        else:
            reserved.add((col, row))

    factory_uid = None
    factory_col, factory_row = 0, 0
    for uid, d in my_robots.items():
        if d[0] == FACTORY:
            factory_uid = uid
            factory_col, factory_row = d[1], d[2]
            break

    if not factory_uid:
        return actions

    factory_energy = my_robots[factory_uid][3]
    factory_gap = factory_row - south
    step_num = getattr(obs, "step", 0) or 0
    if step_num >= 430:
        mine_gap = 18
    elif step_num >= 340:
        mine_gap = 14
    elif step_num >= 230:
        mine_gap = 10
    else:
        mine_gap = MINE_SAFE_GAP

    fdata = my_robots[factory_uid]
    f_move_cd = fdata[5] if len(fdata) > 5 else 0
    f_jump_cd = fdata[6] if len(fdata) > 6 else 0
    f_build_cd = fdata[7] if len(fdata) > 7 else 0
    factory_in_scroll_trap = is_scroll_trap(factory_col, factory_row)
    factory_trap_backtrack = (
        factory_in_scroll_trap
        and f_jump_cd > 0
        and factory_gap > 2
        and can_move(factory_col, factory_row, "SOUTH")
    )

    # True if we own a mine that's about to deplete — time to spawn replacement.
    needs_fresh_miner = (
        counts[MINER] == 0
        and own_mine_energy
        and min(own_mine_energy.values()) < MINE_REFRESH_THRESHOLD
        and any(node[1] - south > MINE_SAFE_GAP for node in nodes_mem)
    )

    def front_worker_uid():
        uid = my_positions.get((factory_col, factory_row + 1))
        if uid and my_robots[uid][0] == WORKER:
            return uid
        return None

    def guard_factory_action(step):
        if step_num < WORKER_PLOW_STEP or step != "NORTH":
            return step
        uid = front_worker_uid()
        if not uid:
            return step
        worker = my_robots[uid]
        wc, wr = worker[1], worker[2]
        worker_move_cd = worker[5] if len(worker) > 5 else 0
        if worker[3] > getattr(config, "energyPerTurn", 1) and worker_move_cd <= 1 and can_move(wc, wr, "NORTH"):
            target = (wc, wr + 1)
            if target not in reserved and target not in my_positions:
                return step
        return adjacent_worker_transfer_action(factory_col, factory_row, factory_energy) or "IDLE"

    def enemy_factory_escape_action():
        if f_move_cd > 1:
            return None
        own_backup = sum(d[3] for d in my_robots.values() if d[0] != FACTORY)
        enemy_backup = sum(d[3] for d in enemy_robots.values() if d[0] != FACTORY)
        if own_backup > enemy_backup + 25:
            return None
        enemy_factories = [
            (d[1], d[2])
            for d in enemy_robots.values()
            if d[0] == FACTORY
        ]
        for ec, er in enemy_factories:
            if abs(ec - factory_col) + abs(er - factory_row) != 1:
                continue
            enemy_dir = adjacent_direction(ec, er, (factory_col, factory_row))
            if enemy_dir and get_wall(ec, er) & WALL_BITS[enemy_dir]:
                continue
            choices = []
            for rank, d in enumerate(("NORTH", "EAST", "WEST", "SOUTH")):
                if d == "SOUTH" and factory_gap <= 6:
                    continue
                if not can_move(factory_col, factory_row, d):
                    continue
                dc, dr = OFFSETS[d]
                nc, nr = factory_col + dc, factory_row + dr
                if unsafe_scroll_trap(nc, nr, max(0, f_jump_cd - 1)):
                    continue
                if (nc, nr) == (ec, er):
                    continue
                uid = my_positions.get((nc, nr))
                if uid and uid != factory_uid:
                    continue
                distance = abs(nc - ec) + abs(nr - er)
                if distance <= 1:
                    continue
                choices.append((distance, d == "NORTH", -rank, d))
            if choices:
                return max(choices)[3]
            if f_jump_cd <= 0:
                jump_choices = []
                for rank, d in enumerate(("NORTH", "EAST", "WEST")):
                    if not can_factory_jump(factory_col, factory_row, d):
                        continue
                    dc, dr = OFFSETS[d]
                    nc, nr = factory_col + 2 * dc, factory_row + 2 * dr
                    uid = my_positions.get((nc, nr))
                    if uid and uid != factory_uid:
                        continue
                    distance = abs(nc - ec) + abs(nr - er)
                    jump_choices.append((distance, d == "NORTH", -rank, f"JUMP_{d}"))
                if jump_choices:
                    return max(jump_choices)[3]
        return None

    def safer_factory_step(step):
        """Block SOUTH/JUMP_SOUTH unless the SOUTH cell is genuinely safer.

        The original `main.py` veto was too coarse — it forbade SOUTH whenever
        gap <= 3, which deletes the desperate-escape branch baseline relied on.
        Here we permit SOUTH if:
          * the factory is in a one-way scroll trap (must back out), OR
          * there's a fully-open north alternative that doesn't lead to a trap.
        """
        if step not in ("SOUTH", "JUMP_SOUTH"):
            return step
        if step == "SOUTH" and factory_trap_backtrack:
            return step
        # Look for a strictly better north/lateral alternative first.
        for d in ("NORTH", "EAST", "WEST"):
            if not can_move(factory_col, factory_row, d):
                continue
            dc, dr = OFFSETS[d]
            target = (factory_col + dc, factory_row + dr)
            if unsafe_scroll_trap(target[0], target[1], max(0, f_jump_cd - 1)):
                continue
            if target in my_positions and my_positions.get(target) != factory_uid:
                continue
            return d
        if f_jump_cd <= 0:
            for d in ("NORTH", "EAST", "WEST"):
                if not can_factory_jump(factory_col, factory_row, d):
                    continue
                dc, dr = OFFSETS[d]
                target = (factory_col + 2 * dc, factory_row + 2 * dr)
                if target in my_positions and my_positions.get(target) != factory_uid:
                    continue
                return f"JUMP_{d}"
        # No better option — let SOUTH stand. Better to retreat than IDLE-and-die.
        return step

    # Emergency near the south bound — try every jump direction in priority
    # order, not just NORTH. Previous code would fall through to main planning
    # when NORTH landing was occupied by a friendly robot, missing valid
    # EAST/WEST escape jumps. Failure trace (seed=1 P0 step 488): factory at
    # gap=1 with jCD=0 and mvCD=2, walked WEST instead of jumping.
    if factory_gap <= 2 and south > 0 and f_jump_cd <= 0:
        for d in ("NORTH", "EAST", "WEST"):
            if not can_factory_jump(factory_col, factory_row, d):
                continue
            dc, dr = OFFSETS[d]
            nc, nr = factory_col + 2 * dc, factory_row + 2 * dr
            occupant = my_positions.get((nc, nr))
            if occupant and occupant != factory_uid:
                continue
            record(factory_uid, f"JUMP_{d}", factory_col, factory_row)
            break

    if factory_uid not in actions:
        spawn = (factory_col, factory_row + 1)
        spawn_ok = (
            f_build_cd <= 1
            and spawn not in my_positions
            and factory_row + 1 <= north
            and not (get_wall(factory_col, factory_row) & WALL_BITS["NORTH"])
        )

        miner_build = (
            adjacent_node_build_action(factory_col, factory_row, factory_energy, f_build_cd)
            if factory_gap > mine_gap
            else None
        )
        mine_step = adjacent_own_mine_step(factory_col, factory_row, factory_gap, mine_gap)
        on_safe_mine = (factory_col, factory_row) in own_mines_mem and factory_gap > mine_gap
        worker_transfer = adjacent_worker_transfer_action(factory_col, factory_row, factory_energy)
        adjacent_node_wait = (
            f_build_cd > 0
            and factory_gap > mine_gap
            and any(
                (factory_col + dc, factory_row + dr) in visible_nodes and can_move(factory_col, factory_row, d)
                for d, (dc, dr) in OFFSETS.items()
            )
        )
        collision_escape = enemy_factory_escape_action()

        if collision_escape:
            record(factory_uid, guard_factory_action(collision_escape), factory_col, factory_row)
        elif miner_build:
            record(factory_uid, miner_build, factory_col, factory_row)
            counts[MINER] += 1
        elif step_num >= WORKER_PLOW_STEP and worker_transfer:
            record(factory_uid, worker_transfer, factory_col, factory_row)
        elif on_safe_mine or adjacent_node_wait:
            record(factory_uid, worker_transfer or "IDLE", factory_col, factory_row)
        elif mine_step and f_move_cd <= 1:
            record(factory_uid, guard_factory_action(mine_step), factory_col, factory_row)
        elif f_move_cd > 1:
            record(factory_uid, worker_transfer or "IDLE", factory_col, factory_row)
        elif (nodes_mem and (not own_mines_mem or needs_fresh_miner) and factory_gap > mine_gap + 2):
            station_goals = mining_station_goals(factory_col, factory_row, factory_energy)
            if (factory_col, factory_row) in station_goals:
                record(factory_uid, "IDLE", factory_col, factory_row)
            else:
                step = bfs_jump((factory_col, factory_row), station_goals, f_jump_cd, depth=MINE_ROUTE_DEPTH)
                if step and step != "IDLE":
                    record(factory_uid, step, factory_col, factory_row)

        spawn_north_wall = (
            factory_row + 1 <= north
            and bool(get_wall(factory_col, factory_row + 1) & WALL_BITS["NORTH"])
        )
        low_gap_wall_worker = (
            own_mines_mem
            and spawn_north_wall
            and factory_gap > 2
            and factory_energy >= getattr(config, "workerCost", 200) + LOW_GAP_WORKER_ENERGY_BUFFER
        )

        # 2nd worker allowed after step 380 — redundant plowing for the
        # late-game scroll catch-up phase. On 48 games this lifted avg
        # reward +207, duel-pair margin +415 vs baseline. WLD was 7-9-8
        # (wins by big margin, losses are narrow tiebreakers).
        worker_cap = 2 if step_num >= 380 else 1
        if (
            factory_uid not in actions
            and spawn_ok
            and own_mines_mem
            and counts[WORKER] < worker_cap
            and factory_energy >= getattr(config, "workerCost", 200) + 250
            and ((step_num >= 180 and factory_gap > mine_gap + 3) or low_gap_wall_worker)
        ):
            record(factory_uid, "BUILD_WORKER", factory_col, factory_row)
            counts[WORKER] += 1
        elif (
            factory_uid not in actions
            and spawn_ok
            and counts[SCOUT] < 1
            and _memory.get("scouts_built", 0) < 1
            and factory_energy >= 50
            and step_num >= SCOUT_DELAY_STEP
            and not (nodes_mem and step_num < 80)
        ):
            record(factory_uid, "BUILD_SCOUT", factory_col, factory_row)
            counts[SCOUT] += 1
            _memory["scouts_built"] = _memory.get("scouts_built", 0) + 1

        if factory_uid not in actions:
            target_row = min(north, factory_row + 20)
            factory_goals = [(tc, target_row) for tc in range(width)]
            step = bfs_jump((factory_col, factory_row), factory_goals, f_jump_cd, depth=20)

            if not step:
                closer_goals = [(tc, min(north, factory_row + 5)) for tc in range(width)]
                step = bfs_first_step(
                    (factory_col, factory_row),
                    closer_goals,
                    depth=10,
                    avoid_occupied=False,
                    avoid_traps=True,
                    jump_cd=f_jump_cd,
                )

            if not step:
                for d in ("NORTH", "EAST", "WEST"):
                    if can_move(factory_col, factory_row, d):
                        dc, dr = OFFSETS[d]
                        nc, nr = factory_col + dc, factory_row + dr
                        if unsafe_scroll_trap(nc, nr, max(0, f_jump_cd - 1)):
                            continue
                        step = d
                        break

            if not step and factory_trap_backtrack:
                step = "SOUTH"

            # Low-gap desperation SOUTH (the branch the old veto deleted).
            # Only worth taking when we're genuinely wedged: jump on CD AND no
            # north/lateral option AND we won't fall off the boundary next turn.
            if not step and factory_gap <= 3 and factory_gap > 1 and can_move(factory_col, factory_row, "SOUTH"):
                step = "SOUTH"

            # High-gap polite retreat (preserved from main.py)
            if not step and factory_gap > 3 and step_num < 430:
                if can_move(factory_col, factory_row, "SOUTH"):
                    step = "SOUTH"

            if not step and f_jump_cd <= 0 and factory_gap <= 3:
                for d in ("NORTH", "EAST", "WEST"):
                    if can_factory_jump(factory_col, factory_row, d):
                        step = f"JUMP_{d}"
                        break

            step = guard_factory_action(safer_factory_step(step))
            if step and step != "IDLE":
                record(factory_uid, step, factory_col, factory_row)
            else:
                if spawn_ok and counts[WORKER] < 1 and factory_energy >= 200 and factory_gap <= 4:
                    record(factory_uid, "BUILD_WORKER", factory_col, factory_row)
                    counts[WORKER] += 1
                else:
                    record(factory_uid, "IDLE", factory_col, factory_row)

    # Miners — walk to nearest mining node, TRANSFORM on arrival
    miners = [(uid, d) for uid, d in my_robots.items() if d[0] == MINER]
    for uid, data in miners:
        col, row = data[1], data[2]
        energy = data[3]
        move_cd = data[5] if len(data) > 5 else 0
        if f"{col},{row}" in obs.miningNodes and energy >= getattr(config, "transformCost", 50):
            record(uid, "TRANSFORM", col, row)
            continue
        if move_cd > 1:
            record(uid, "IDLE", col, row)
            continue
        step = bfs_first_step((col, row), nodes_mem, depth=8)
        if step and step != "IDLE":
            record(uid, step, col, row)
        else:
            record(uid, "IDLE", col, row)

    # Scouts — push ahead of factory for vision, dump scavenged energy back
    scouts = [(uid, d) for uid, d in my_robots.items() if d[0] == SCOUT]
    for uid, data in scouts:
        col, row = data[1], data[2]
        energy = data[3]
        move_cd = data[5] if len(data) > 5 else 0
        # Only transfer when scout has clearly *gained* energy from a crystal
        # (spawn energy is 50 + 1e/turn decay), not when it would just be
        # giving back what we paid to build it. Threshold 60 catches a 10e+
        # crystal pickup that happened recently.
        if energy >= 60:
            transfer_dir = adjacent_direction(col, row, (factory_col, factory_row))
            if transfer_dir and can_move(col, row, transfer_dir):
                record(uid, f"TRANSFER_{transfer_dir}", col, row)
                continue
        if move_cd > 1:
            record(uid, "IDLE", col, row)
            continue
        # Opportunistic crystal pickup within 6 cells, then resume escort target.
        # Picking up a 10-50e crystal and dumping it back to the factory next
        # turn is pure gain vs sitting at the escort row.
        crystal_goals = [
            cpos for cpos in crystals
            if abs(cpos[0] - col) + abs(cpos[1] - row) <= 6
            and cpos[1] >= row - 2  # don't dive south into the scroll
        ]
        step = bfs_first_step((col, row), crystal_goals, depth=8) if crystal_goals else None
        if not step:
            scout_goals = [(tc, min(north, factory_row + 8)) for tc in range(width)]
            step = bfs_first_step((col, row), scout_goals, depth=12)
        if not step or step == "IDLE":
            for d in ("NORTH", "EAST", "WEST"):
                if can_move(col, row, d):
                    nc, nr = col + OFFSETS[d][0], row + OFFSETS[d][1]
                    if (nc, nr) not in reserved and (nc, nr) not in my_positions:
                        step = d
                        break
        if step and step != "IDLE":
            record(uid, step, col, row)
        else:
            record(uid, "IDLE", col, row)

    # Workers — escort factory, plow walls in late game
    workers = [(uid, d) for uid, d in my_robots.items() if d[0] == WORKER]
    for uid, data in workers:
        col, row = data[1], data[2]
        energy = data[3]
        move_cd = data[5] if len(data) > 5 else 0
        factory_action = actions.get(factory_uid)
        if step_num >= WORKER_PLOW_STEP and (col, row) == (factory_col, factory_row + 1):
            if (
                factory_action == "NORTH"
                and energy > getattr(config, "energyPerTurn", 1)
                and move_cd <= 1
                and can_move(col, row, "NORTH")
            ):
                target = (col, row + 1)
                if target not in reserved and target not in my_positions:
                    record(uid, "NORTH", col, row)
                    continue
            if (get_wall(col, row) & WALL_BITS["NORTH"]) and energy >= 100:
                record(uid, "REMOVE_NORTH", col, row)
                continue
            record(uid, "IDLE", col, row)
            continue
        if (get_wall(col, row) & WALL_BITS["NORTH"]) and energy >= 100:
            record(uid, "REMOVE_NORTH", col, row)
            continue
        if move_cd > 1:
            record(uid, "IDLE", col, row)
            continue
        escort_row = min(north, factory_row + (1 if step_num >= WORKER_PLOW_STEP else 7))
        target_goals = [(factory_col, escort_row)]
        step = bfs_first_step((col, row), target_goals, depth=10)
        if not step or step == "IDLE":
            for d in ("NORTH", "EAST", "WEST"):
                if can_move(col, row, d):
                    nc, nr = col + OFFSETS[d][0], row + OFFSETS[d][1]
                    if (nc, nr) not in reserved and (nc, nr) not in my_positions:
                        step = d
                        break
        if step and step != "IDLE":
            record(uid, step, col, row)
        else:
            record(uid, "IDLE", col, row)

    for uid in my_robots:
        if uid not in actions:
            actions[uid] = "IDLE"

    return actions
