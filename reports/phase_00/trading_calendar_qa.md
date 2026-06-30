# Phase 0.1 Trading Calendar QA Report

## Status

GO

## Changed files

- `configs/project_v0.yaml`
- `src/phase_00_trading_calendar.py`
- `tests/test_phase_00_trading_calendar.py`
- `requirements.txt`
- `C:/Users/elisa/Documents/qt_pennystock/data/reference/trading_calendar_v0.parquet`
- `C:/Users/elisa/Documents/qt_pennystock/reports/phase_00/trading_calendar_qa.md`
- `TODO.md`

## What was implemented

- Built `trading_calendar_v0` from `exchange_calendars.get_calendar("XNYS")`.
- Assigned `dataset_split` and `research_split` from `PROJECT.md` canonical dates.
- Added schema, fixture, split, session-boundary, and reproducibility QA.
- Wrote the calendar only after QA passed.

## Commands run

```bash
python -m pytest tests/test_phase_00_trading_calendar.py -q -p no:cacheprovider
python -m src.phase_00_trading_calendar
```

## Results

- Output written: `True`
- Output path: `C:/Users/elisa/Documents/qt_pennystock/data/reference/trading_calendar_v0.parquet`
- Row count: `3607`
- Trading-day count: `2481`
- Early-close count: `21`
- Calendar source: `XNYS`
- exchange_calendars version: `4.13.2`
- Python version: `3.13.12`

## Split ranges

### dataset_split

- `OOS`: `2024-01-01` through `2026-06-29`
- `Train`: `2016-08-14` through `2021-12-31`
- `Val`: `2022-01-01` through `2023-12-31`

### research_split

- `OOS`: `2024-01-01` through `2026-06-29`
- `Train`: `2016-08-14` through `2021-12-31`
- `Val-A`: `2022-01-01` through `2022-12-31`
- `Val-B`: `2023-01-01` through `2023-12-31`

## QA summary

- `PASS` `required_columns` - ['date', 'is_trading_day', 'is_early_close', 'regular_open_et', 'regular_close_et', 'dataset_split', 'research_split']
- `PASS` `date_unique`
- `PASS` `date_sorted`
- `PASS` `min_date` - 2016-08-14
- `PASS` `max_date` - 2026-06-29
- `PASS` `row_count` - actual=3607 expected=3607
- `PASS` `no_weekends_marked_trading`
- `PASS` `trading_open_not_null`
- `PASS` `trading_close_not_null`
- `PASS` `non_trading_open_null`
- `PASS` `non_trading_close_null`
- `PASS` `trading_open_0930`
- `PASS` `normal_close_1600`
- `PASS` `early_close_not_before_1300`
- `PASS` `dataset_split_not_null`
- `PASS` `research_split_not_null`
- `PASS` `dataset_split_allowed`
- `PASS` `research_split_allowed`
- `PASS` `dataset_split_Train_range` - actual=('2016-08-14', '2021-12-31') expected=('2016-08-14', '2021-12-31')
- `PASS` `dataset_split_Val_range` - actual=('2022-01-01', '2023-12-31') expected=('2022-01-01', '2023-12-31')
- `PASS` `dataset_split_OOS_range` - actual=('2024-01-01', '2026-06-29') expected=('2024-01-01', '2026-06-29')
- `PASS` `research_split_Train_range` - actual=('2016-08-14', '2021-12-31') expected=('2016-08-14', '2021-12-31')
- `PASS` `research_split_Val-A_range` - actual=('2022-01-01', '2022-12-31') expected=('2022-01-01', '2022-12-31')
- `PASS` `research_split_Val-B_range` - actual=('2023-01-01', '2023-12-31') expected=('2023-01-01', '2023-12-31')
- `PASS` `research_split_OOS_range` - actual=('2024-01-01', '2026-06-29') expected=('2024-01-01', '2026-06-29')
- `PASS` `fixture_weekend_2024_01_06` - is_trading_day=False open=nan close=nan is_early_close=False
- `PASS` `fixture_holiday_2024_01_01` - is_trading_day=False open=nan close=nan is_early_close=False
- `PASS` `fixture_normal_2024_01_02` - is_trading_day=True open=09:30 close=16:00 is_early_close=False
- `PASS` `fixture_early_close_2024_11_29` - is_trading_day=True open=09:30 close=13:00 is_early_close=True
- `PASS` `fixture_train_start_2016_08_14` - is_trading_day=False open=nan close=nan is_early_close=False
- `PASS` `fixture_train_last_2021_12_31` - is_trading_day=True open=09:30 close=16:00 is_early_close=False
- `PASS` `fixture_val_a_start_2022_01_01` - is_trading_day=False open=nan close=nan is_early_close=False
- `PASS` `fixture_val_a_last_2022_12_31` - is_trading_day=False open=nan close=nan is_early_close=False
- `PASS` `fixture_val_b_start_2023_01_01` - is_trading_day=False open=nan close=nan is_early_close=False
- `PASS` `fixture_val_b_last_2023_12_31` - is_trading_day=False open=nan close=nan is_early_close=False
- `PASS` `fixture_oos_start_2024_01_01` - is_trading_day=False open=nan close=nan is_early_close=False
- `PASS` `fixture_oos_last_2026_06_29` - is_trading_day=True open=09:30 close=16:00 is_early_close=False

## Massive date cross-check

- Status: `unavailable`
- Detail: no local Massive daily/minute date listings found

## Risks / unknowns

- Massive local file-date listings are optional for Phase 0 and may be unavailable before Phase 1 data exists.
- Calendar-source behavior depends on the recorded `exchange_calendars` version.

## Suggested next task

- Phase 0.2 Review Calendar Artifact
