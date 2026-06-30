from __future__ import annotations

from datetime import date

import pandas as pd

from src.phase_00_trading_calendar import (
    REQUIRED_COLUMNS,
    QAResult,
    build_trading_calendar,
    load_config,
    validate_calendar,
    write_calendar_if_qa_passes,
)


def test_build_trading_calendar_core_contract():
    config = load_config_path()
    calendar = build_trading_calendar(config)

    assert list(calendar.columns) == REQUIRED_COLUMNS
    assert calendar["date"].min() == date(2016, 8, 14)
    assert calendar["date"].max() == date(2026, 6, 29)
    assert len(calendar) == (date(2026, 6, 29) - date(2016, 8, 14)).days + 1
    assert calendar["date"].is_unique
    assert calendar["date"].is_monotonic_increasing


def test_fixture_dates_and_splits_pass_qa():
    config = load_config_path()
    calendar = build_trading_calendar(config)
    qa = validate_calendar(calendar, config, root=pd_path())

    assert qa.status == "GO"
    assert all(check["passed"] for check in qa.checks)
    assert qa.summary["dataset_split_ranges"] == {
        "OOS": {"start": "2024-01-01", "end": "2026-06-29"},
        "Train": {"start": "2016-08-14", "end": "2021-12-31"},
        "Val": {"start": "2022-01-01", "end": "2023-12-31"},
    }
    assert qa.summary["research_split_ranges"] == {
        "OOS": {"start": "2024-01-01", "end": "2026-06-29"},
        "Train": {"start": "2016-08-14", "end": "2021-12-31"},
        "Val-A": {"start": "2022-01-01", "end": "2022-12-31"},
        "Val-B": {"start": "2023-01-01", "end": "2023-12-31"},
    }

    early_close = calendar.loc[calendar["date"] == date(2024, 11, 29)].iloc[0]
    assert bool(early_close["is_trading_day"])
    assert bool(early_close["is_early_close"])
    assert early_close["regular_close_et"] == "13:00"

    holiday = calendar.loc[calendar["date"] == date(2024, 1, 1)].iloc[0]
    assert not bool(holiday["is_trading_day"])
    assert pd.isna(holiday["regular_open_et"])
    assert pd.isna(holiday["regular_close_et"])


def test_write_calendar_if_qa_passes_does_not_overwrite_on_failure():
    tmp_dir = pd_path() / "tests" / ".tmp_phase_00"
    tmp_dir.mkdir(exist_ok=True)
    output = tmp_dir / "calendar.parquet"
    output.write_text("previous-valid-output", encoding="utf-8")
    calendar = pd.DataFrame(columns=REQUIRED_COLUMNS)
    qa = QAResult(status="NO-GO", checks=[], summary={}, massive_cross_check={"status": "unavailable"})

    wrote = write_calendar_if_qa_passes(calendar, qa, output)

    assert not wrote
    assert output.read_text(encoding="utf-8") == "previous-valid-output"
    output.unlink()
    tmp_dir.rmdir()


def load_config_path():
    return load_config(pd_path() / "configs" / "project_v0.yaml")


def pd_path():
    from pathlib import Path

    return Path(__file__).resolve().parents[1]
