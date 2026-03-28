"""Crawl agent: scout early, path to crystals, march north."""

from collections import deque


FACTORY = 0
SCOUT = 1
WORKER = 2
MINER = 3

NORTH = 1
EAST = 2
SOUTH = 4
WEST = 8

DIRECTION_BITS = {
    "NORTH": NORTH,
    "EAST": EAST,
    "SOUTH": SOUTH,
    "WEST": WEST,
}

DIRECTION_DELTAS = {
    "NORTH": (0, 1),
    "EAST": (1, 0),
    "SOUTH": (0, -1),
    "WEST": (-1, 0),
}


def cell_walls(obs, width, col, row):
    idx = (row - obs.southBound) * width + col
    if 0 <= idx < len(obs.walls) and obs.walls[idx] != -1:
        return obs.walls[idx]
    return 0


def known_cell_walls(obs, width, col, row):
    idx = (row - obs.southBound) * width + col
    if 0 <= idx < len(obs.walls) and obs.walls[idx] != -1:
        return obs.walls[idx]
    return None


def in_bounds(obs, width, col, row):
    return 0 <= col < width and obs.southBound <= row <= obs.northBound


def parse_pos(key):
    col, row = key.split(",", 1)
    return int(col), int(row)


def adjacent_crystal_dirs(obs, col, row):
    targets = []
    for direction, (dc, dr) in DIRECTION_DELTAS.items():
        key = f"{col + dc},{row + dr}"
        if key in obs.crystals:
            targets.append((obs.crystals[key], direction))
    return [direction for _, direction in sorted(targets, reverse=True)]


def build_choice(counts, energy, config):
    if counts.get(SCOUT, 0) < 2 and energy >= config.scoutCost:
        return "BUILD_SCOUT"
    if counts.get(WORKER, 0) < 1 and energy >= config.workerCost:
        return "BUILD_WORKER"
    if counts.get(SCOUT, 0) < 5 and energy >= config.scoutCost:
        return "BUILD_SCOUT"
    if counts.get(WORKER, 0) < 2 and energy >= config.workerCost:
        return "BUILD_WORKER"
    if energy >= config.scoutCost:
        return "BUILD_SCOUT"
    return None


def preferred_directions(width, col):
    toward_center = "EAST" if col < width // 2 else "WEST"
    away_from_center = "WEST" if toward_center == "EAST" else "EAST"
    return ["NORTH", toward_center, away_from_center, "SOUTH"]


def crystal_path_dir(obs, width, col, row, occupied, reserved):
    targets = {}
    for key, energy in obs.crystals.items():
        target = parse_pos(key)
        if target != (col, row) and in_bounds(obs, width, target[0], target[1]):
            targets[target] = energy

    if not targets:
        return None

    queue = deque([(col, row, None, 0)])
    seen = {(col, row)}
    best = None

    while queue:
        cur_col, cur_row, first_dir, distance = queue.popleft()
        if (cur_col, cur_row) in targets and first_dir is not None:
            energy = targets[(cur_col, cur_row)]
            candidate = (energy * 100 - distance, -distance, energy, first_dir)
            if best is None or candidate[:3] > best[:3]:
                best = candidate

        walls = known_cell_walls(obs, width, cur_col, cur_row)
        if walls is None:
            continue

        for direction in preferred_directions(width, cur_col):
            if walls & DIRECTION_BITS[direction]:
                continue
            dc, dr = DIRECTION_DELTAS[direction]
            next_cell = (cur_col + dc, cur_row + dr)
            if next_cell in seen or not in_bounds(obs, width, next_cell[0], next_cell[1]):
                continue
            if next_cell in occupied or next_cell in reserved:
                continue
            if known_cell_walls(obs, width, next_cell[0], next_cell[1]) is None and next_cell not in targets:
                continue
            seen.add(next_cell)
            queue.append((next_cell[0], next_cell[1], first_dir or direction, distance + 1))

    return best[3] if best else None


def choose_move(obs, width, col, row, walls, occupied, reserved, chase_crystals=True):
    path_dir = crystal_path_dir(obs, width, col, row, occupied, reserved) if chase_crystals else None
    preferred = adjacent_crystal_dirs(obs, col, row)
    if path_dir:
        preferred.append(path_dir)
    preferred += preferred_directions(width, col)

    seen = set()
    for direction in preferred:
        if direction in seen or walls & DIRECTION_BITS[direction]:
            continue
        seen.add(direction)
        dc, dr = DIRECTION_DELTAS[direction]
        target = (col + dc, row + dr)
        if not in_bounds(obs, width, target[0], target[1]):
            continue
        if target in occupied or target in reserved:
            continue
        reserved.add(target)
        return direction

    return "IDLE"


def agent(obs, config):
    actions = {}
    width = config.width
    my_robots = {
        uid: data for uid, data in obs.robots.items()
        if data[4] == obs.player
    }
    counts = {}
    occupied = {}
    for uid, data in my_robots.items():
        counts[data[0]] = counts.get(data[0], 0) + 1
        occupied[(data[1], data[2])] = uid

    reserved = set()

    for uid, data in my_robots.items():
        rtype, col, row, energy = data[0], data[1], data[2], data[3]
        jump_cd = data[6] if len(data) > 6 else 0
        build_cd = data[7] if len(data) > 7 else 0
        walls = cell_walls(obs, width, col, row)

        if rtype == FACTORY:
            spawn = (col, row + 1)
            if walls & NORTH:
                if jump_cd == 0 and in_bounds(obs, width, col, row + 2):
                    actions[uid] = "JUMP_NORTH"
                else:
                    actions[uid] = "IDLE"
            elif build_cd == 0 and in_bounds(obs, width, spawn[0], spawn[1]) and spawn not in occupied:
                action = build_choice(counts, energy, config)
                if action:
                    actions[uid] = action
                else:
                    actions[uid] = choose_move(obs, width, col, row, walls, occupied, reserved, chase_crystals=False)
            else:
                actions[uid] = choose_move(obs, width, col, row, walls, occupied, reserved, chase_crystals=False)
        elif rtype == WORKER and (walls & NORTH) and energy >= config.wallRemoveCost:
            actions[uid] = "REMOVE_NORTH"
        elif rtype == MINER and f"{col},{row}" in obs.miningNodes and energy >= config.transformCost:
            actions[uid] = "TRANSFORM"
        else:
            actions[uid] = choose_move(
                obs,
                width,
                col,
                row,
                walls,
                occupied,
                reserved,
                chase_crystals=(rtype == SCOUT),
            )

    return actions
