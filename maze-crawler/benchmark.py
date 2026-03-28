"""Run local Crawl benchmark matches for the current agent."""

import argparse
import contextlib
import io

FACTORY = 0
DIRS = ("NORTH", "EAST", "WEST", "SOUTH")
OFFSETS = {"NORTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0), "SOUTH": (0, -1)}
WALL_BITS = {"NORTH": 1, "EAST": 2, "SOUTH": 4, "WEST": 8}


def load_make():
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        from kaggle_environments import make

    return make


def mapping_get(mapping, key, default=None):
    if hasattr(mapping, "get"):
        return mapping.get(key, default)
    try:
        return mapping[key]
    except (KeyError, TypeError):
        return default


def factory_state(obs, player):
    for uid, data in obs.robots.items():
        if data[0] == FACTORY and data[4] == player:
            return uid, data
    return None, None


def wall_bits_at(obs, width, col, row):
    global_row = mapping_get(getattr(obs, "globalWalls", {}), str(row))
    if global_row is not None and 0 <= col < len(global_row):
        return global_row[col]
    idx = (row - obs.southBound) * width + col
    if 0 <= idx < len(obs.walls) and obs.walls[idx] != -1:
        return obs.walls[idx]
    return None


def legal_exits(width, south, north, col, row, wall_bits):
    exits = []
    bits = wall_bits if wall_bits is not None else 0
    for direction in DIRS:
        dc, dr = OFFSETS[direction]
        nc, nr = col + dc, row + dr
        if 0 <= nc < width and south <= nr <= north and not (bits & WALL_BITS[direction]):
            exits.append(direction)
    return exits


def action_for_uid(action, uid):
    if not isinstance(action, dict) or uid is None:
        return None
    return action.get(uid)


def build_failure_report(env, agent_index):
    width = env.configuration.width
    player = agent_index
    last_seen = None
    first_missing = None

    for idx, states in enumerate(env.steps):
        state = states[agent_index]
        obs = state.observation
        public_obs = states[0].observation
        uid, data = factory_state(obs, player)
        if data is not None:
            last_seen = (idx, state, obs, public_obs, uid, data)
        elif last_seen is not None and first_missing is None:
            first_missing = (idx, state, obs, public_obs)
            break

    if last_seen is None:
        return {
            "factory_death_step": "unknown",
            "last_factory_action": None,
            "factory_gap": None,
            "wall_bits": None,
            "legal_exits": [],
            "jump_cd": None,
        }

    _, state, obs, public_obs, uid, data = last_seen
    col, row = data[1], data[2]
    wall_bits = wall_bits_at(public_obs, width, col, row)
    death_step = "survived"
    last_action = action_for_uid(state.action, uid)
    if first_missing is not None:
        _, missing_state, _, missing_public_obs = first_missing
        death_step = missing_public_obs.step
        last_action = action_for_uid(missing_state.action, uid) or last_action

    return {
        "factory_death_step": death_step,
        "last_factory_action": last_action,
        "factory_gap": row - public_obs.southBound,
        "wall_bits": wall_bits,
        "legal_exits": legal_exits(width, public_obs.southBound, public_obs.northBound, col, row, wall_bits),
        "jump_cd": data[6] if len(data) > 6 else None,
    }


def run_match(make, players, seed, agent_index, failure_report=False):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        env = make("crawl", configuration={"randomSeed": seed}, debug=True)
        env.run(players)

    rewards = [state.reward for state in env.steps[-1]]
    statuses = [state.status for state in env.steps[-1]]
    opponent_index = 1 - agent_index
    if rewards[agent_index] > rewards[opponent_index]:
        outcome = "win"
    elif rewards[agent_index] < rewards[opponent_index]:
        outcome = "loss"
    else:
        outcome = "draw"

    result = {
        "seed": seed,
        "side": agent_index,
        "outcome": outcome,
        "rewards": rewards,
        "agent_reward": rewards[agent_index],
        "opponent_reward": rewards[opponent_index],
        "margin": rewards[agent_index] - rewards[opponent_index],
        "statuses": statuses,
        "steps": len(env.steps),
    }
    if failure_report and outcome == "loss":
        result["failure_report"] = build_failure_report(env, agent_index)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default="main.py", help="Agent file or Kaggle agent name.")
    parser.add_argument("--opponent", default="baseline.py", help="Opponent file or Kaggle agent name.")
    parser.add_argument("--seeds", type=int, default=20, help="Number of random seeds to test.")
    parser.add_argument("--start-seed", type=int, default=0, help="First seed to test.")
    parser.add_argument("--duel", action="store_true", help="Play each seed from both starting sides.")
    parser.add_argument("--verbose", action="store_true", help="Print every match result.")
    parser.add_argument("--failure-report", action="store_true", help="Print factory death diagnostics for losses.")
    args = parser.parse_args()

    make = load_make()
    results = []
    for seed in range(args.start_seed, args.start_seed + args.seeds):
        results.append(run_match(make, [args.agent, args.opponent], seed, agent_index=0, failure_report=args.failure_report))
        if args.duel:
            results.append(run_match(make, [args.opponent, args.agent], seed, agent_index=1, failure_report=args.failure_report))

    wins = sum(result["outcome"] == "win" for result in results)
    losses = sum(result["outcome"] == "loss" for result in results)
    draws = sum(result["outcome"] == "draw" for result in results)
    avg_reward = sum(result["agent_reward"] for result in results) / len(results)
    avg_opponent_reward = sum(result["opponent_reward"] for result in results) / len(results)
    avg_margin = sum(result["margin"] for result in results) / len(results)
    avg_steps = sum(result["steps"] for result in results) / len(results)

    games = len(results)
    print(f"{games} games vs {args.opponent}: {wins}W {losses}L {draws}D")
    print(f"Average reward: {avg_reward:.3f} vs {avg_opponent_reward:.3f} ({avg_margin:+.3f})")
    print(f"Average steps: {avg_steps:.1f}")
    for side in (0, 1):
        side_results = [result for result in results if result["side"] == side]
        if not side_results:
            continue
        side_wins = sum(result["outcome"] == "win" for result in side_results)
        side_losses = sum(result["outcome"] == "loss" for result in side_results)
        side_draws = sum(result["outcome"] == "draw" for result in side_results)
        side_margin = sum(result["margin"] for result in side_results) / len(side_results)
        print(f"P{side}: {side_wins}W {side_losses}L {side_draws}D ({side_margin:+.3f})")

    if args.duel:
        paired_margins = []
        for seed in range(args.start_seed, args.start_seed + args.seeds):
            seed_results = [result for result in results if result["seed"] == seed]
            if len(seed_results) == 2:
                paired_margins.append(sum(result["margin"] for result in seed_results))
        if paired_margins:
            paired_wins = sum(margin > 0 for margin in paired_margins)
            paired_losses = sum(margin < 0 for margin in paired_margins)
            paired_draws = sum(margin == 0 for margin in paired_margins)
            paired_margin = sum(paired_margins) / len(paired_margins)
            print(
                f"Duel pairs: {paired_wins}W {paired_losses}L {paired_draws}D "
                f"({paired_margin:+.3f})"
            )

    if args.failure_report:
        for result in results:
            report = result.get("failure_report")
            if not report:
                continue
            exits = ",".join(report["legal_exits"]) or "none"
            print(
                f"failure seed={result['seed']:02d} "
                f"side=P{result['side']} "
                f"death_step={report['factory_death_step']} "
                f"last_action={report['last_factory_action']} "
                f"factory_gap={report['factory_gap']} "
                f"wall_bits={report['wall_bits']} "
                f"legal_exits={exits} "
                f"jump_cd={report['jump_cd']}"
            )

    if args.verbose:
        for result in results:
            print(
                f"seed={result['seed']:02d} "
                f"side=P{result['side']} "
                f"outcome={result['outcome']:4s} "
                f"rewards={result['rewards']} "
                f"steps={result['steps']} "
                f"statuses={result['statuses']}"
            )


if __name__ == "__main__":
    main()
