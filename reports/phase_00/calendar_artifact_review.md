# Phase 0.2 Calendar Artifact Review

## Status

GO

## Changed files

- `reports/phase_00/calendar_artifact_review.md`
- `TODO.md`

## Review scope

Reviewed Phase 0.1 against:

- `PROJECT.md`
- `CODEX.md`
- `TODO.md`
- `docs/phases/phase_00_trading_calendar.md`
- `reports/phase_00/trading_calendar_qa.md`
- `data/reference/trading_calendar_v0.parquet`
- Phase 0 implementation and tests under `src/` and `tests/`

No Phase 1+ code, data, or reports were reviewed or modified.

## Findings

No blocking or actionable findings.

The implementation stayed within the Phase 0 scope, uses `exchange_calendars.get_calendar("XNYS")`, writes the required calendar artifact, and records QA evidence. The generated artifact follows `PROJECT.md` date boundaries rather than stale `PLAN.md` dates.

## Commands run

```bash
python -m pytest tests/test_phase_00_trading_calendar.py -q -p no:cacheprovider
python - <artifact read-back check>
rg --files | sort
```

## Results

- Focused tests: `3 passed`
- Calendar artifact exists: `data/reference/trading_calendar_v0.parquet`
- Row count: `3607`
- Column count: `7`
- Columns:
  - `date`
  - `is_trading_day`
  - `is_early_close`
  - `regular_open_et`
  - `regular_close_et`
  - `dataset_split`
  - `research_split`
- Minimum date: `2016-08-14`
- Maximum date: `2026-06-29`
- Trading-day count: `2481`
- Early-close count: `21`
- Non-trading rows with non-null `regular_open_et`: `0`
- Non-trading rows with non-null `regular_close_et`: `0`

## Split verification

`dataset_split` ranges:

- `Train`: `2016-08-14` through `2021-12-31`
- `Val`: `2022-01-01` through `2023-12-31`
- `OOS`: `2024-01-01` through `2026-06-29`

`research_split` ranges:

- `Train`: `2016-08-14` through `2021-12-31`
- `Val-A`: `2022-01-01` through `2022-12-31`
- `Val-B`: `2023-01-01` through `2023-12-31`
- `OOS`: `2024-01-01` through `2026-06-29`

## QA evidence reviewed

The Phase 0.1 QA report is `GO` and includes:

- commands run
- calendar source and `exchange_calendars` version
- output path
- row count
- trading-day count
- early-close count
- split date ranges
- fixture check results
- Massive date cross-check status

Massive local file-date listings were unavailable. This is acceptable for Phase 0 because the spec treats Massive file dates as optional QA evidence, not the semantic source for `is_trading_day`.

## Scope check

Files present after Phase 0.1 are limited to expected Phase 0 surfaces:

- project/config/docs already in repo
- `data/reference/trading_calendar_v0.parquet`
- `reports/phase_00/trading_calendar_qa.md`
- `src/phase_00_trading_calendar.py`
- `tests/test_phase_00_trading_calendar.py`
- `requirements.txt`

No Phase 1+ outputs or implementation files were introduced.

## Risks / unknowns

- Dependency versions are not pinned in a lock file. The QA report records `exchange_calendars` version `4.13.2`, which is sufficient for current Phase 0 evidence, but future reproducibility would be stronger with pinned dependency management.
- Massive local file-date alignment remains untested until local Massive files or manifests exist.

## Suggested next task

Phase 0.3 Final Phase 0 QA.
