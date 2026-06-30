# TODO: Phase 0 Trading Calendar

Source of truth:

- `PROJECT.md`
- `docs/phases/phase_00_trading_calendar.md`

Scope guard:

- Only Phase 0 work is in scope.
- Do not implement Phase 1 ingestion, Massive download logic, universe construction, labels, active-minute features, models, clustering, baselines, or replay.
- Do not modify `PROJECT.md` or `PLAN.md`.
- Treat `PROJECT.md` dates as canonical where existing config or plan text disagrees.

## Suggested Next Active Task

Phase 0.2 Review Calendar Artifact

## Active Task: Phase 0.1 Implement Trading Calendar Artifact

Status: GO

### Goal

Implement the Phase 0 trading calendar build and QA flow that produces:

```text
data/reference/trading_calendar_v0.parquet
reports/phase_00/trading_calendar_qa.md
```

The calendar must use `exchange_calendars.get_calendar("XNYS")` as the authoritative US equity session source and must follow the Phase 0 spec.

### Allowed Files

- `TODO.md`
- `configs/project_v0.yaml`
- Phase 0 implementation code under:
  - `src/`
- Phase 0 tests or validation code under:
  - `tests/`
- Dependency declaration files, only if needed:
  - `requirements.txt`
  - `pyproject.toml`
- Phase 0 outputs:
  - `data/reference/trading_calendar_v0.parquet`
  - temporary files under `data/reference/`
  - `reports/phase_00/trading_calendar_qa.md`

### Disallowed Files Or Areas

- `PROJECT.md`
- `PLAN.md`
- `docs/phases/phase_00_trading_calendar.md`
- `docs/reviews/`
- Any Phase 1+ implementation, data, reports, configs, or tests.
- Any Massive REST/S3 ingestion implementation.
- Any model, label, universe, embedding, clustering, baseline, or replay code.

### Acceptance Criteria

1. `configs/project_v0.yaml` uses the canonical `PROJECT.md` date range:
   - start date `2016-08-14`
   - end date `2026-06-29`
   - Train `2016-08-14` through `2021-12-31`
   - Val `2022-01-01` through `2023-12-31`
   - OOS `2024-01-01` through `2026-06-29`
2. The implementation uses `exchange_calendars.get_calendar("XNYS")`.
3. The implementation is single-process and does not parallelize Phase 0.
4. The output file `data/reference/trading_calendar_v0.parquet` is created only after QA passes.
5. The output schema includes exactly the required Phase 0 columns unless additional metadata columns are explicitly justified in the QA report:
   - `date`
   - `is_trading_day`
   - `is_early_close`
   - `regular_open_et`
   - `regular_close_et`
   - `dataset_split`
   - `research_split`
6. The output covers every calendar date from `2016-08-14` through `2026-06-29`, inclusive.
7. All rows have `dataset_split` and `research_split`.
8. Trading-day rows have non-null `regular_open_et` and `regular_close_et`.
9. Non-trading rows have null `regular_open_et` and `regular_close_et`.
10. Weekend, known holiday, normal trading day, split boundary, and early-close fixture checks pass.
11. Early-close trading days are retained and marked with `is_early_close == true`.
12. If local Massive file-date listings are available, they are cross-checked in QA; if unavailable, the QA report explicitly says they were not available and does not fail solely for that reason.
13. Failed QA must not overwrite a previous valid `data/reference/trading_calendar_v0.parquet`.
14. A Phase 0 QA report is written to `reports/phase_00/trading_calendar_qa.md`.
15. The QA report includes:
    - commands run
    - calendar source and package version
    - output path
    - row count
    - trading-day count
    - early-close count
    - split date ranges
    - fixture check results
    - Massive date cross-check result or unavailable note
    - GO / NO-GO status
16. The smallest relevant tests or validation checks are run and documented in the QA report.
17. `TODO.md` is updated only to mark this Active task status and propose the next Phase 0 task.

### Required Report Path

```text
reports/phase_00/trading_calendar_qa.md
```

## Backlog

### Task: Phase 0.2 Review Calendar Artifact

Status: Proposed Active

Acceptance criteria:

- Read `PROJECT.md`, `CODEX.md`, `TODO.md`, `docs/phases/phase_00_trading_calendar.md`, and `reports/phase_00/trading_calendar_qa.md`.
- Inspect `data/reference/trading_calendar_v0.parquet`.
- Verify the implementation stayed within Phase 0 scope.
- Verify the output obeys `PROJECT.md` invariants.
- Verify the QA evidence is sufficient for GO / NO-GO.
- Write a review report under `reports/phase_00/`.

### Task: Phase 0.3 Final Phase 0 QA

Status: Backlog

Acceptance criteria:

- Run final Phase 0 QA against the generated calendar artifact.
- Confirm all Phase 0 GO criteria in `docs/phases/phase_00_trading_calendar.md`.
- Confirm no later-phase files or outputs were introduced.
- Produce `reports/phase_00/final_qa.md`.
- Mark Phase 0 as GO, NO-GO, PARTIAL, or BLOCKED with evidence.
