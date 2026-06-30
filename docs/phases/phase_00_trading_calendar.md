# Phase 0: Trading Calendar

## Goal

Build the project-wide trading-day source of truth:

```text
data/reference/trading_calendar_v0.parquet
```

Every later phase must use this artifact as its date driver. No later phase may independently loop over raw calendar days.

This phase is small in data volume. Correctness and reproducibility matter more than compute performance.

## Source Priority

`PROJECT.md` is the source of truth.

Where `PLAN.md` conflicts with `PROJECT.md`, this spec follows `PROJECT.md`.

Known `PLAN.md` conflicts resolved by this spec:

- `PLAN.md` uses Train start `2016-08-02`; this spec uses `PROJECT.md` Train start `2016-08-14`.
- `PLAN.md` uses OOS end `2026-06-18`; this spec uses `PROJECT.md` OOS end `2026-06-29`.

## Inputs

Required inputs:

- `exchange_calendars` Python package, using calendar `XNYS`.
- `PROJECT.md` dataset split boundaries.

Optional QA inputs:

- Local Massive daily file dates, if available.
- Local Massive minute file dates, if available.

`XNYS` is the authoritative Phase 0 trading-session source. Massive file dates are reliable QA evidence, but they must not redefine exchange trading-day truth. If a Massive date listing disagrees with `XNYS`, record the mismatch in QA output and do not silently change `is_trading_day`.

## Output

Required output:

```text
data/reference/trading_calendar_v0.parquet
```

Recommended QA report:

```text
reports/phase_00/trading_calendar_qa.md
```

Phase 0 does not require a partition manifest because it produces one small reference artifact, not a set of date or date-plus-bucket tasks. Later phases may add manifests for partitioned outputs.

## Date Range

Generate one row per calendar date, inclusive:

```text
2016-08-14 through 2026-06-29
```

The table includes both trading and non-trading calendar dates. Downstream phases must filter:

```text
is_trading_day == true
```

## Split Contract

`dataset_split`:

```text
Train: 2016-08-14 through 2021-12-31
Val:   2022-01-01 through 2023-12-31
OOS:   2024-01-01 through 2026-06-29
```

`research_split`:

```text
Train: 2016-08-14 through 2021-12-31
Val-A: 2022-01-01 through 2022-12-31
Val-B: 2023-01-01 through 2023-12-31
OOS:   2024-01-01 through 2026-06-29
```

All rows in the date range should receive `dataset_split` and `research_split`, including non-trading days. Later phases still process only rows where `is_trading_day == true`.

## Schema

Required columns:

| Column | Type | Required | Contract |
|---|---:|---:|---|
| `date` | date | yes | Calendar date in ET session convention. Unique and sorted ascending. |
| `is_trading_day` | bool | yes | True only for US equity exchange trading days. |
| `is_early_close` | bool | yes | True only for trading days with regular close earlier than normal close. False for non-trading days. |
| `regular_open_et` | string or time | conditional | Regular session open in ET. Required for trading days, null for non-trading days. |
| `regular_close_et` | string or time | conditional | Regular session close in ET. Required for trading days, null for non-trading days. |
| `dataset_split` | string | yes | One of `Train`, `Val`, `OOS`. |
| `research_split` | string | yes | One of `Train`, `Val-A`, `Val-B`, `OOS`. |

Allowed `regular_open_et` value for trading days:

```text
09:30
```

Expected `regular_close_et` values:

```text
16:00 for normal trading days
13:00 for standard early-close days
```

If `XNYS` returns a different valid early close time for a historical special session, preserve the `XNYS` value and report it in QA.

Time fields may be stored as strings such as `09:30` and `16:00` to avoid cross-engine timezone ambiguity in Parquet. Later phases can combine `date` plus these local ET times when timestamp comparisons are needed.

## Session Semantics

Downstream phases must interpret sessions as:

```text
premarket:
  04:00 <= bar_start_et < 09:30

RTH:
  09:30 <= bar_start_et < regular_close_et
```

For early-close days, `regular_close_et` is the early close. Do not use a fixed 16:00 RTH close.

## Implementation Constraints

1. Use `exchange_calendars.get_calendar("XNYS")`, not a generic weekday or federal holiday calendar.
2. Generate the full calendar date range exactly once.
3. Assign splits from `PROJECT.md`, not from stale `PLAN.md` date ranges.
4. Keep early-close trading days.
5. Do not introduce look-ahead risk by allowing later phases to infer dates outside this calendar.
6. Do not require network access for the final calendar build unless explicitly added by a later task.
7. Write to a temporary path first, run QA, then replace the final output only after QA passes.
8. Failed QA must not overwrite a previous valid `trading_calendar_v0.parquet`.

## Performance and Parallelism

Do not parallelize Phase 0.

Reason:

- The full date range is only a few thousand rows.
- Parallel workers would add overhead, ordering risk, and unnecessary complexity.
- The algorithm is O(number of calendar days), with negligible memory use.

Expected memory use is tiny: one in-memory table with one row per calendar date. No large DataFrame copies, serialization, or I/O-heavy processing are needed.

## QA Checks

Required QA:

1. Schema and row integrity:
   - Required columns exist.
   - `date` is unique.
   - `date` is sorted ascending.
   - Minimum date is `2016-08-14`.
   - Maximum date is `2026-06-29`.
   - Row count equals the inclusive calendar-day count.

2. Trading-day correctness:
   - No Saturday or Sunday has `is_trading_day == true`.
   - Known US equity market holidays are not marked as trading days.
   - Known normal trading days are marked as trading days.
   - No non-trading day has non-null `regular_open_et` or `regular_close_et`.

3. Session-boundary correctness:
   - All trading days have non-null `regular_open_et`.
   - All trading days have non-null `regular_close_et`.
   - All trading days have `regular_open_et == 09:30`.
   - Normal trading days have `regular_close_et == 16:00`.
   - Early-close days are marked `is_early_close == true`.
   - Early-close trading days have `regular_close_et >= 13:00`.

4. Split correctness:
   - Every row has `dataset_split`.
   - Every row has `research_split`.
   - `dataset_split` values are only `Train`, `Val`, `OOS`.
   - `research_split` values are only `Train`, `Val-A`, `Val-B`, `OOS`.
   - Split min/max dates exactly match the split contract.
   - Splits are chronological and non-overlapping.

5. Fixture dates:
   - Include at least one weekend check.
   - Include at least one known market holiday check.
   - Include at least one normal trading-day check.
   - Include at least one known early-close check.
   - Include first and last dates of each dataset split.
   - Include first and last dates of each research split.

6. Massive date cross-check, if local file-date listings are available:
   - Compare generated trading dates to available Massive daily dates.
   - Compare generated trading dates to available Massive minute dates.
   - Report missing or extra dates.
   - Do not mutate `is_trading_day` based only on vendor file availability.

7. Reproducibility:
   - Regenerating the calendar with the same inputs produces identical rows.
   - QA report records the `exchange_calendars` package version and `XNYS` calendar name.

## GO Criteria

Phase 0 is GO if:

1. `data/reference/trading_calendar_v0.parquet` exists.
2. The artifact covers `2016-08-14` through `2026-06-29` inclusive.
3. All required columns exist with valid values.
4. All trading days have valid split labels.
5. Weekend, holiday, normal-session, and early-close fixture QA passes.
6. Early-close days are retained and correctly marked.
7. The output was written only after QA passed.
8. The Phase 0 QA report records commands/checks run and results.

## NO-GO Criteria

Phase 0 is NO-GO if:

1. The output uses stale `PLAN.md` date ranges instead of `PROJECT.md`.
2. Any weekend is marked as a trading day.
3. Any known market holiday fixture is marked as a trading day.
4. Any known early close fixture is missing or incorrectly marked.
5. Any trading day has null `dataset_split` or `research_split`.
6. Session boundaries are null for trading days.
7. Session boundaries are filled for non-trading days.
8. QA fails and the implementation overwrites a previous valid output.
9. The implementation requires later phases to infer dates from raw calendar loops.

## Known Risks

1. Calendar-source drift:
   - Different versions of a calendar library may produce different ad hoc closure or early-close outputs.
   - Mitigation: record the `exchange_calendars` package version and `XNYS` calendar name in the QA report.

2. Time representation ambiguity:
   - Timezone-aware Parquet columns can behave differently across readers.
   - Mitigation: store local ET session boundary times as simple time strings unless implementation has a clear typed-time convention.

3. PLAN.md date drift:
   - `PLAN.md` still contains stale Phase 0 date ranges.
   - Mitigation: this spec and implementation must use `PROJECT.md` dates.

4. Vendor availability mismatch:
   - Massive file listings may have missing or extra dates.
   - Mitigation: report mismatches as QA evidence; do not redefine exchange trading days from file presence alone.

## Provisional Choices

1. Time columns may be stored as strings in `HH:MM` ET format.
2. Phase 0 does not require a per-partition manifest because it has one small reference output.
3. Massive date availability is a QA cross-check, not a required semantic input.

These provisional choices can be tightened in the implementation task or final QA if the repository establishes a stronger shared convention.
