# Phase 0 Trading Calendar Technical Ownership Review

Scope: Phase 0 only, `Build trading calendar`.

Source files reviewed:

- `PROJECT.md`
- `PLAN.md`
- `WORKFLOW.md`
- `CODEX.md`

`TODO.md` is missing. This is acceptable for a planning artifact because the user explicitly requested this review, and no code implementation is being performed.

## Executive Summary

Phase 0 is small in row count but high in ownership impact. It defines the only allowed date driver for all later phases, so the main engineering risk is not compute performance; it is correctness, reproducibility, and removing ambiguity before downstream data ingestion starts.

The implementation should remain single-process. A 2016-2026 daily calendar is only a few thousand rows, so parallelization would add coordination and reproducibility risk without measurable benefit. The performance work belongs in later phases that consume this table at date or date-plus-bucket granularity.

The prior date-range ambiguity is resolved by treating `PROJECT.md` as the source of truth. Phase 0 should use the split boundaries in `PROJECT.md` even where `PLAN.md` differs. No separate spike is required before writing the phase spec; the spec can require normal QA fixture checks for holidays/early closes and straightforward cross-checks against Massive available daily/minute file dates.

## Technical Choices

### 1. Use `trading_calendar_v0` as the sole date driver

1. Problem it solves: Prevents every downstream phase from independently deciding which dates exist, which dates are trading days, and where splits begin/end.
2. Why it may be reasonable: The project has strict leak-free OOS requirements and many date-partitioned phases. A single date table makes date filtering auditable and reproducible.
3. Pros:
   - Eliminates duplicated calendar logic.
   - Makes reruns deterministic.
   - Provides one place to audit holidays, early closes, and split assignment.
   - Supports date-level parallelism later without raw calendar-day loops.
4. Cons:
   - A calendar bug propagates to every phase.
   - Later phases become blocked if the calendar contract is incomplete.
   - Requires strong QA before any data ingestion.
5. Common failure modes:
   - Downstream code loops over `pd.date_range` instead of reading the table.
   - Non-trading days get silently processed because `is_trading_day` is ignored.
   - Calendar is regenerated with a different source or version and breaks reproducibility.
6. Simpler alternative: Each phase computes NYSE trading days locally from a calendar library.
7. Validation:
   - Add QA that verifies all later phase specs/tasks require `trading_calendar_v0`.
   - In Phase 0, validate row coverage, trading-day count, known holidays, and early closes.
   - In Phase 1+, add checks that processed dates are a subset of `is_trading_day == true`.
8. Classification: BLOCKER

### 2. Calendar source of truth for US equity sessions

1. Problem it solves: Determines weekends, market holidays, ad hoc closures, and early closes.
2. Why it may be reasonable: A library-backed US equity calendar avoids hand-maintained holiday lists and captures historical exchange-specific behavior.
3. Pros:
   - Less error-prone than hardcoded holiday lists.
   - Can expose early-close times.
   - Easy to regenerate reproducibly if the package version is pinned.
4. Cons:
   - Calendar libraries may differ on exchange definitions and ad hoc closures.
   - Dependency/version drift can change outputs.
   - Massive data availability is reliable, but it is still vendor coverage rather than exchange-rule definition.
5. Common failure modes:
   - Using a generic federal holiday calendar instead of an exchange calendar.
   - Missing ad hoc closures, such as extraordinary market closure days.
   - Incorrect early closes around holidays.
   - Timezone-naive timestamps that look correct but compare incorrectly later.
6. Simpler alternative: Maintain a small explicit override file for holidays and early closes over the project date range.
7. Validation:
   - Compare the selected calendar source against a short known-date fixture.
   - Spot check years with common early closes: day after Thanksgiving, Christmas Eve when applicable, July 3 when applicable.
   - Cross-check trading-day dates against Massive available daily/minute file dates for missing or extra dates.
8. Classification: RISK

### 3. Use Massive available daily/minute file dates as a reliability cross-check

1. Problem it solves: Confirms the generated calendar aligns with the file dates the project will actually ingest.
2. Why it may be reasonable: Massive available daily/minute file dates are reliable enough to use as a practical sanity check for expected trading sessions.
3. Pros:
   - Simple, cheap validation against the actual data source.
   - Catches obvious missing/extra date mistakes before Phase 1.
   - Keeps the Phase 0 calendar grounded in the available dataset.
4. Cons:
   - Should not require live network access inside Phase 0 if local file-date information is available later.
   - Vendor dates should validate the calendar, not redefine `is_trading_day`.
   - Backfilled files can change availability reports over time.
5. Common failure modes:
   - Treating a missing vendor file as proof that the exchange was closed.
   - Letting vendor extras override exchange-calendar logic.
   - Blocking Phase 0 on remote file listing instead of using local or deferred checks.
6. Simpler alternative: Build the exchange calendar in Phase 0 and leave the full Massive availability audit to Phase 1.
7. Validation:
   - In normal Phase 0 QA, compare generated trading dates with available Massive file dates if local date listings exist.
   - Record mismatches in a QA report, not by changing `is_trading_day`.
   - Keep availability columns out of `trading_calendar_v0` unless the phase spec explicitly requires them.
8. Classification: NICE-TO-HAVE

### 4. Output full daily calendar rows, including non-trading days

1. Problem it solves: Preserves a complete date range with explicit `is_trading_day` rather than only storing trading sessions.
2. Why it may be reasonable: QA can assert weekends and holidays are present and marked false, and downstream code has no excuse to infer missing dates.
3. Pros:
   - Makes non-trading-day exclusions explicit.
   - Supports QA checks such as "no weekends marked trading day".
   - Helps detect raw calendar-day loops in downstream tests.
4. Cons:
   - Downstream code must always filter to `is_trading_day == true`.
   - `dataset_split` and `research_split` semantics for non-trading days must be specified.
   - Null open/close fields for non-trading rows need a clear contract.
5. Common failure modes:
   - Later phases forget the trading-day filter and process all rows.
   - Non-trading rows get split labels, misleading row counts.
   - Non-trading rows have fake 09:30-16:00 times filled in.
6. Simpler alternative: Store only trading days in `trading_calendar_v0`.
7. Validation:
   - QA counts all calendar days and trading days separately.
   - Assert all non-trading rows have null session times.
   - Assert all phase specs require `where is_trading_day == true`.
8. Classification: RISK

### 5. Store regular session boundaries in ET

1. Problem it solves: Downstream session logic needs correct premarket/RTH boundaries and early-close cutoffs.
2. Why it may be reasonable: The project's signal definitions use `bar_start_et`, `regular_open_et`, and `regular_close_et`; storing ET boundaries avoids repeated timezone conversion.
3. Pros:
   - Clear alignment with Phase 3 session rules.
   - Early-close RTH end can be joined directly.
   - Reduces repeated timestamp logic in later phases.
4. Cons:
   - Timezone representation must be explicit: date plus local time string, timezone-aware timestamp, or both.
   - Ambiguous handling of DST if stored as naive timestamps.
   - Parquet consumers may interpret timezone metadata differently.
5. Common failure modes:
   - Storing naive datetimes that are assumed UTC by one reader and ET by another.
   - Using fixed 16:00 close for early closes.
   - Off-by-one minute comparisons at `regular_close_et`.
6. Simpler alternative: Store `regular_open_time_et` and `regular_close_time_et` as strings such as `09:30` and `13:00`, plus `date`; construct timestamps later.
7. Validation:
   - QA exact open/close values for normal and early-close dates.
   - Test DST-period dates and confirm ET times remain 09:30/16:00 in local time.
   - Confirm downstream comparison convention is half-open: `bar_start_et < regular_close_et`.
8. Classification: RISK

### 6. Keep early-close trading days

1. Problem it solves: Avoids deleting valid trading sessions while allowing downstream RTH logic to use shorter session boundaries.
2. Why it may be reasonable: The plan says half-days are retained and use that day's `regular_close_et`, not a fixed 16:00 close.
3. Pros:
   - Maximizes usable historical data.
   - Keeps research behavior consistent across real market sessions.
   - Supports later QA for half-day candidate generation.
4. Cons:
   - Later labels with 30-minute holding windows may have fewer valid RTH candidates.
   - Lower liquidity and shorter sessions can behave differently.
   - Early-close list must be correct.
5. Common failure modes:
   - Half-days incorrectly marked as full days.
   - Treating post-13:00 bars as RTH on early-close days.
   - Dropping half-days in some phases but not others.
6. Simpler alternative: Exclude early-close days from v0 research.
7. Validation:
   - Fixture of known early-close dates with expected `regular_close_et == 13:00`.
   - Later Phase 3 QA that `decision_time_et <= regular_close_et - 30min` on half-days.
   - Report early-close count by year.
8. Classification: RISK

### 7. Dataset split and research split assignment in the calendar

1. Problem it solves: Prevents Train/Val/OOS boundaries from being recomputed or accidentally changed by later phases.
2. Why it may be reasonable: The whole project depends on chronological separation. Storing split labels in the calendar makes split membership auditable at the date level.
3. Pros:
   - Reduces leakage risk.
   - Gives every downstream partition an inherited split.
   - Makes OOS-only replay enforceable by date.
4. Cons:
   - Split boundary errors become global.
   - Non-trading-day split labels need clear handling.
   - `PLAN.md` contains stale split dates relative to `PROJECT.md`, so implementation must not copy them blindly.
5. Common failure modes:
   - Using `PLAN.md` dates even though `PROJECT.md` is the source of truth.
   - Assigning OOS through an old end date and silently dropping newer OOS days.
   - Boundary inclusivity errors on start/end dates.
6. Simpler alternative: Store only `date` and `is_trading_day`; define splits in a separate config.
7. Validation:
   - QA exact min/max date by split.
   - QA no null split on trading days.
   - QA split labels are chronological and non-overlapping.
8. Classification: RISK

### 8. Phase 0 date range

1. Problem it solves: Defines the complete historical coverage for Train, Val, and OOS.
2. Why it may be reasonable: A fixed closed range makes the research result reproducible and prevents later accidental OOS extension.
3. Pros:
   - Deterministic row count and split coverage.
   - Easy to audit and compare across runs.
   - Prevents accidental inclusion of future dates.
4. Cons:
   - Needs explicit update when the project endpoint changes.
   - `PLAN.md` has stale date ranges that conflict with `PROJECT.md`.
   - OOS ending date is especially sensitive because it defines the final test horizon.
5. Common failure modes:
   - Implementing `PLAN.md` range `2016-08-02` to `2026-06-18` while `PROJECT.md` says Train starts `2016-08-14` and OOS ends `2026-06-29`.
   - Inclusive/exclusive end-date mismatch.
   - Calendar generated through today's date instead of the project-defined OOS end.
6. Simpler alternative: Use `PROJECT.md` dates exactly and document that `PLAN.md` Phase 0 dates are stale.
7. Validation:
   - Before spec, make one explicit decision on the canonical range.
   - QA calendar min/max date and split boundaries against the chosen source.
   - Add a test fixture for the first and last date in each split.
8. Classification: RISK

### 9. Parquet output at `data/reference/trading_calendar_v0.parquet`

1. Problem it solves: Provides a compact, typed, queryable artifact for all phases.
2. Why it may be reasonable: The rest of the plan uses Parquet for large tables. Even though this table is small, using Parquet keeps read paths consistent.
3. Pros:
   - Preserves typed columns better than CSV.
   - Works with pyarrow, polars, duckdb, and pandas.
   - Easy for downstream joins and filters.
4. Cons:
   - Less human-readable than CSV.
   - Requires the environment to have a Parquet reader.
   - Timezone columns can be tricky across engines.
5. Common failure modes:
   - Schema changes without versioning.
   - Time columns written as object/string accidentally when downstream expects timestamps.
   - Overwriting a valid prior calendar after failed QA.
6. Simpler alternative: Write CSV plus a small schema JSON.
7. Validation:
   - Read the Parquet back with the intended engine and assert schema.
   - Add a small exported QA report with row counts and known-date checks.
   - Use temp-write then validate then atomic replace, consistent with project write rules.
8. Classification: RISK

### 10. Single-process generation with no parallelism

1. Problem it solves: Avoids unnecessary concurrency and serialization overhead for a tiny deterministic artifact.
2. Why it may be reasonable: The full daily date range is only thousands of rows. Calendar generation is CPU- and I/O-trivial.
3. Pros:
   - Simpler, deterministic implementation.
   - No worker startup, IPC, or serialization overhead.
   - Easier QA and debugging.
4. Cons:
   - None meaningful for this phase.
   - Does not exercise later date-level parallel infrastructure.
5. Common failure modes:
   - Overengineering Phase 0 with unnecessary workers.
   - Hiding nondeterministic ordering bugs behind parallel output.
6. Simpler alternative: Not applicable; single-process is already the simpler alternative.
7. Validation:
   - Runtime should be near-instant locally.
   - QA confirms stable row order and repeated-run identical output.
8. Classification: NICE-TO-HAVE

### 11. Versioning and immutability of `trading_calendar_v0`

1. Problem it solves: Keeps a stable dependency contract for all downstream phases.
2. Why it may be reasonable: The artifact name includes `v0`, implying future incompatible changes should get a new version.
3. Pros:
   - Prevents silent downstream changes.
   - Makes reports traceable to a calendar version.
   - Supports reproducibility if output metadata includes generation inputs.
4. Cons:
   - Requires discipline to avoid overwriting.
   - Needs a small metadata policy even though the table is small.
5. Common failure modes:
   - Regenerating `v0` after a dependency update and changing early-close rows.
   - Not recording calendar library/version or manual overrides.
   - Failed QA overwrites a prior valid calendar.
6. Simpler alternative: Treat the calendar as disposable and regenerate whenever needed.
7. Validation:
   - Include code/config version and calendar source/version in a QA report or metadata sidecar.
   - Compare checksum or row hash across repeated generation.
   - Enforce temp-write plus QA before replacing the output.
8. Classification: RISK

## Choices To Understand Before Implementation

1. Canonical date range and split boundaries. This is resolved: use `PROJECT.md` exactly. Train is `2016-08-14` to `2021-12-31`, Val is `2022-01-01` to `2023-12-31`, and OOS is `2024-01-01` to `2026-06-29`.
2. Calendar source. Use a US equity exchange calendar source, with fixture QA for holidays and early closes.
3. Massive file availability should be used as a practical QA cross-check, not as the semantic definition of `is_trading_day`.
4. Schema semantics for non-trading rows:
   - Should `dataset_split` and `research_split` be assigned to all calendar days or only trading days?
   - Should session boundary fields be null for non-trading days?
5. Time representation for `regular_open_et` and `regular_close_et`: timezone-aware timestamp versus date plus local time string.
6. Early-close handling policy: retain all half-days as planned, or explicitly exclude them from v0 if the owner decides simplicity is more important.
7. Atomic write and metadata policy for `data/reference/trading_calendar_v0.parquet`.

## Smallest Spike Before Phase Spec

No spike is required before writing the Phase 0 spec.

The phase spec should include normal QA checks for:

- A normal trading day.
- A weekend.
- A known market holiday.
- A known early close.
- The first and last date of each split.
- Massive available daily/minute file-date alignment where local date listings are available.

## Contradictions With `PROJECT.md`

These are contradictions in `PLAN.md` relative to the higher-priority `PROJECT.md`. They are not open decisions after the owner directive to treat `PROJECT.md` as source of truth.

1. Dataset split start date:
   - `PROJECT.md`: Train starts `2016-08-14`.
   - `PLAN.md`: Train starts `2016-08-02`.
   - Impact: `PLAN.md` Phase 0 dates are stale for implementation.
   - Resolution: Use `PROJECT.md`.
   - Classification: RISK

2. OOS end date:
   - `PROJECT.md`: OOS ends `2026-06-29`.
   - `PLAN.md`: OOS ends `2026-06-18`.
   - Impact: `PLAN.md` Phase 0 dates are stale for implementation.
   - Resolution: Use `PROJECT.md`.
   - Classification: RISK

3. Phase count mismatch:
   - `PROJECT.md` lists Phase 12 as `OOS encoder replay and benchmark`.
   - `PLAN.md` includes Phase 12 `Baselines_v0` and Phase 13 `OOS encoder replay and benchmark_v0`.
   - Impact: Not a Phase 0 implementation blocker, but it confirms `PLAN.md` contains stale or superseded structure relative to the higher-priority project constitution.
   - Classification: RISK

4. Plan version inconsistency:
   - `PLAN.md` header says `active_minute_encoder_discovery_v0_4`, while the embedded original plan says `v0_5`.
   - Impact: Not a Phase 0 blocker by itself, but reinforces the need to treat `PLAN.md` Phase 0 details as provisional where they conflict with `PROJECT.md`.
   - Classification: RISK

## Ownership Recommendation

Use `PROJECT.md` dates exactly in the Phase 0 spec and explicitly note that `PLAN.md` Phase 0 date ranges are stale where they conflict.

Proceed to the executable Phase 0 spec. Keep the spec simple: generate the calendar from a US equity session source, assign splits from `PROJECT.md`, retain early closes, write the Parquet output, and require direct QA checks including Massive file-date alignment where available.

READY_TO_SPEC
