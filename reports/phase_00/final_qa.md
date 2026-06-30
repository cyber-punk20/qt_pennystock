# Phase 0 Final QA

## Status

GO

## Phase goal

Build the project-wide trading-day source of truth:

```text
data/reference/trading_calendar_v0.parquet
```

Every later phase must use this artifact as its date driver and must not independently loop over raw calendar days.

## Outputs produced

- `data/reference/trading_calendar_v0.parquet`
- `reports/phase_00/trading_calendar_qa.md`
- `reports/phase_00/calendar_artifact_review.md`
- `reports/phase_00/final_qa.md`

Supporting Phase 0 implementation and validation files:

- `src/phase_00_trading_calendar.py`
- `tests/test_phase_00_trading_calendar.py`
- `configs/project_v0.yaml`
- `requirements.txt`

## QA checks run

1. Re-ran focused Phase 0 tests.
2. Read back `data/reference/trading_calendar_v0.parquet`.
3. Verified schema, row count, date range, split ranges, trading-day count, early-close count, session-boundary nullability, and weekend exclusion.
4. Verified Phase 0 reports exist and show `GO`.
5. Verified file scope contains no Phase 1+ outputs or implementation.

## Commands run

```bash
python -m pytest tests/test_phase_00_trading_calendar.py -q -p no:cacheprovider
python - <artifact read-back and invariant check>
rg --files data reports src tests | sort
git status --short
```

## Results

- Focused tests: `3 passed`
- Artifact exists: `true`
- Artifact path: `data/reference/trading_calendar_v0.parquet`
- Artifact size: `18764` bytes
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
- Date unique: `true`
- Date sorted: `true`
- Trading-day count: `2481`
- Early-close count: `21`
- Weekend trading-day count: `0`
- Non-trading rows with non-null `regular_open_et`: `0`
- Non-trading rows with non-null `regular_close_et`: `0`
- Trading rows with null `regular_open_et`: `0`
- Trading rows with null `regular_close_et`: `0`

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

## GO criteria evidence

1. `data/reference/trading_calendar_v0.parquet` exists: PASS.
2. Artifact covers `2016-08-14` through `2026-06-29` inclusive: PASS.
3. All required columns exist with valid values: PASS.
4. All trading days have valid split labels: PASS.
5. Weekend, holiday, normal-session, and early-close fixture QA passes: PASS.
6. Early-close days are retained and correctly marked: PASS.
7. Output was written only after QA passed: PASS, supported by `reports/phase_00/trading_calendar_qa.md`.
8. Phase 0 QA report records commands/checks run and results: PASS.

## Known risks

- Massive local file-date listings were unavailable, so vendor date alignment remains deferred until Massive files or manifests exist. This is acceptable under the Phase 0 spec because Massive dates are optional QA evidence, not the semantic source for `is_trading_day`.
- Dependency versions are not pinned in a lock file. The Phase 0 QA report records `exchange_calendars` version `4.13.2`, which is enough evidence for current Phase 0 reproducibility.

## Open issues

No blocking Phase 0 issues.

## Decision

Phase 0 is GO.

## Readiness for next phase

Phase 1 can use `data/reference/trading_calendar_v0.parquet` as the date driver. The next phase should not loop over raw calendar days and should process only rows where `is_trading_day == true`.
