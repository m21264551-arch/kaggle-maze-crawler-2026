# Kaggle Maze Crawler 2026

This repo contains my Maze Crawler competition agent, benchmark harness, and working strategy notes.

Maze Crawler is a two-player fog-of-war game where factories build robots, mine energy, manage walls, and move north before the scrolling map destroys anything left behind.

## What is included

- `maze-crawler/main.py` as the current submission candidate
- `maze-crawler/baseline.py` as the local control agent
- `maze-crawler/benchmark.py` for duel testing across seeds
- `maze-crawler/submitted_600.py` as a preserved submission snapshot
- `maze-crawler/CURRENT_STRATEGY.md` and `patchnotes.md` for experiment history
- `maze-crawler/README.md` with the game rules and observation format

## Strategy summary

The current agent is built around factory survival and mine economy. It prioritizes keeping the factory ahead of the scroll, using miners carefully, avoiding early worker spam, and promoting only changes that beat the baseline in local duels.

## Run a local benchmark

```bash
cd maze-crawler
python benchmark.py --agent main.py --opponent baseline.py --seeds 8 --duel --failure-report
```

On my machine, the Kaggle environment was installed under Anaconda, so some notes reference a full Python path. Use whichever Python environment has `kaggle_environments` installed.

## Submission shape

Kaggle expects an `agent(obs, config)` function. The active one lives in `maze-crawler/main.py`.

## Notes

The repository is public for portfolio review. It keeps code and notes, not private Kaggle credentials.
