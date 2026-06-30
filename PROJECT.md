# Active Minute Encoder Discovery

## Goal

Build a reproducible research pipeline to test whether self-supervised intraday morphology embeddings can improve active-minute trade selection out of sample, after costs, compared with simple baselines.

This is not a live trading project yet. The goal is a leak-free OOS research result.

## Current status

Project status: not started.

Current objective:

Set up the repository operating system, project config, and Phase 0 foundation.

## Core question

Can a self-supervised intraday encoder discover active-minute morphology patterns that improve online trade selection compared with simpler baselines?

## Global invariants

These rules apply to the whole project.

1. Every phase uses `trading_calendar_v0` as the date driver.
2. No phase independently loops over raw calendar days.
3. Only trading days are processed.
4. Minute data assumes OHLCV only.
5. No required VWAP, transactions, bid, ask, spread, or order book data.
6. Massive REST must be used only for all-market retrieval.
7. No per-ticker REST loop for all-market metadata.
8. Active-minute features use only `signal_bar_start_et` and earlier bars.
9. Entry price is next-bar open proxy for labels/PnL only.
10. Labels and PnL may use future bars, but labels must never enter encoder inputs.
11. Train fits models, scalers, transforms, UMAP, HDBSCAN, or any learned component.
12. Val selects configs, thresholds, and online rules.
13. OOS is chronological replay only.
14. No OOS tuning.
15. Date-level tasks may run concurrently.
16. Within a single trading day, online replay must be chronological.
17. Every phase must define QA and GO / NO-GO criteria.
18. Failed QA must not silently overwrite previous valid outputs.

## Dataset split

Train:

- 2016-08-14 to 2021-12-31

Val:

- 2022-01-01 to 2023-12-31

OOS:

- 2024-01-01 to 2026-06-29

## Current pipeline

Phase 0: Build trading calendar  
Phase 1: Download / ingest Massive data  
Phase 2: Build daily universe  
Phase 3: Build base active-minute universe  
Phase 4: Add labels  
Phase 5: Build encoder windows  
Phase 6: Train self-supervised encoder  
Phase 7: Generate embeddings  
Phase 8: Fit UMAP / HDBSCAN  
Phase 9: Cluster attribution  
Phase 10: Val-only online selection  
Phase 11: Baselines  
Phase 12: OOS encoder replay and benchmark  

## AI / Codex rules

- The repository is the source of truth.
- Chat history is not source of truth.
- Codex output is not source of truth until it is written into the repo and committed.
- Codex must read `PROJECT.md`, `PLAN.md`, `WORKFLOW.md`, `CODEX.md`, and `TODO.md` before making changes.
- Codex must implement only the Active task in `TODO.md`.
- Codex must not skip ahead to later phases.
- Codex must not redesign the whole project unless the Active task is blocked by a hard contradiction.
- Codex must report contradictions instead of guessing.
- Codex should prefer small, reviewable changes.
- Codex should add or update tests and validation checks whenever practical.