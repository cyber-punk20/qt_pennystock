from __future__ import annotations

import argparse
import os
import platform
from dataclasses import dataclass
from datetime import date, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

import exchange_calendars as xcals
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml


REQUIRED_COLUMNS = [
    "date",
    "is_trading_day",
    "is_early_close",
    "regular_open_et",
    "regular_close_et",
    "dataset_split",
    "research_split",
]

ET_TZ = "America/New_York"
CALENDAR_NAME = "XNYS"


@dataclass(frozen=True)
class QAResult:
    status: str
    checks: list[dict[str, Any]]
    summary: dict[str, Any]
    massive_cross_check: dict[str, Any]

    @property
    def passed(self) -> bool:
        return self.status == "GO"


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _split_for_date(day: date, config: dict[str, Any]) -> str:
    splits = config["splits"]
    if _parse_date(splits["train"]["start"]) <= day <= _parse_date(splits["train"]["end"]):
        return "Train"
    if _parse_date(splits["val"]["start"]) <= day <= _parse_date(splits["val"]["end"]):
        return "Val"
    if _parse_date(splits["oos"]["start"]) <= day <= _parse_date(splits["oos"]["end"]):
        return "OOS"
    raise ValueError(f"Date {day} is outside configured dataset splits")


def _research_split_for_date(day: date, config: dict[str, Any]) -> str:
    train = config["splits"]["train"]
    val = config["splits"]["val"]
    oos = config["splits"]["oos"]
    if _parse_date(train["start"]) <= day <= _parse_date(train["end"]):
        return "Train"
    if _parse_date(val["start"]) <= day <= date(2022, 12, 31):
        return "Val-A"
    if date(2023, 1, 1) <= day <= _parse_date(val["end"]):
        return "Val-B"
    if _parse_date(oos["start"]) <= day <= _parse_date(oos["end"]):
        return "OOS"
    raise ValueError(f"Date {day} is outside configured research splits")


def _et_time_string(ts: pd.Timestamp) -> str:
    return ts.tz_convert(ET_TZ).strftime("%H:%M")


def build_trading_calendar(config: dict[str, Any]) -> pd.DataFrame:
    start = _parse_date(config["dates"]["start_date"])
    end = _parse_date(config["dates"]["end_date"])

    all_days = pd.date_range(start=start, end=end, freq="D")
    cal = xcals.get_calendar(CALENDAR_NAME)
    sessions = cal.sessions_in_range(pd.Timestamp(start), pd.Timestamp(end))
    session_dates = {session.date() for session in sessions}
    early_close_dates = {session.date() for session in cal.early_closes if start <= session.date() <= end}
    schedule = cal.schedule.loc[sessions]

    session_times: dict[date, tuple[str, str]] = {}
    for session, row in schedule.iterrows():
        session_times[session.date()] = (_et_time_string(row["open"]), _et_time_string(row["close"]))

    rows: list[dict[str, Any]] = []
    for day_ts in all_days:
        day = day_ts.date()
        is_trading_day = day in session_dates
        open_et: str | None = None
        close_et: str | None = None
        if is_trading_day:
            open_et, close_et = session_times[day]
        rows.append(
            {
                "date": day,
                "is_trading_day": is_trading_day,
                "is_early_close": is_trading_day and day in early_close_dates,
                "regular_open_et": open_et,
                "regular_close_et": close_et,
                "dataset_split": _split_for_date(day, config),
                "research_split": _research_split_for_date(day, config),
            }
        )

    return pd.DataFrame(rows, columns=REQUIRED_COLUMNS)


def _check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str = "") -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def _row_for(calendar: pd.DataFrame, day: str) -> pd.Series:
    rows = calendar.loc[calendar["date"] == date.fromisoformat(day)]
    if rows.empty:
        raise AssertionError(f"Fixture date {day} not present")
    return rows.iloc[0]


def discover_local_massive_date_listings(root: Path) -> dict[str, Any]:
    data_root = root / "data"
    if not data_root.exists():
        return {"status": "unavailable", "detail": "data/ directory does not exist"}

    patterns = {
        "daily": ["**/daily*/**/*", "**/*daily*/**/*"],
        "minute": ["**/minute*/**/*", "**/*minute*/**/*"],
    }
    found: dict[str, list[str]] = {}
    for key, globs in patterns.items():
        dates: set[str] = set()
        for glob in globs:
            for path in data_root.glob(glob):
                for part in path.parts:
                    token = part.removeprefix("date=")
                    if _looks_like_date(token):
                        dates.add(token)
        if dates:
            found[key] = sorted(dates)

    if not found:
        return {"status": "unavailable", "detail": "no local Massive daily/minute date listings found"}
    return {"status": "available", "dates": found}


def _looks_like_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return len(value) == 10


def validate_calendar(calendar: pd.DataFrame, config: dict[str, Any], root: Path) -> QAResult:
    checks: list[dict[str, Any]] = []
    start = _parse_date(config["dates"]["start_date"])
    end = _parse_date(config["dates"]["end_date"])
    expected_days = (end - start).days + 1

    _check(checks, "required_columns", list(calendar.columns) == REQUIRED_COLUMNS, str(list(calendar.columns)))
    _check(checks, "date_unique", calendar["date"].is_unique)
    _check(checks, "date_sorted", calendar["date"].is_monotonic_increasing)
    _check(checks, "min_date", calendar["date"].min() == start, str(calendar["date"].min()))
    _check(checks, "max_date", calendar["date"].max() == end, str(calendar["date"].max()))
    _check(checks, "row_count", len(calendar) == expected_days, f"actual={len(calendar)} expected={expected_days}")

    weekends = calendar[pd.to_datetime(calendar["date"]).dt.dayofweek >= 5]
    _check(checks, "no_weekends_marked_trading", not weekends["is_trading_day"].any())

    trading = calendar[calendar["is_trading_day"]]
    non_trading = calendar[~calendar["is_trading_day"]]
    _check(checks, "trading_open_not_null", trading["regular_open_et"].notna().all())
    _check(checks, "trading_close_not_null", trading["regular_close_et"].notna().all())
    _check(checks, "non_trading_open_null", non_trading["regular_open_et"].isna().all())
    _check(checks, "non_trading_close_null", non_trading["regular_close_et"].isna().all())
    _check(checks, "trading_open_0930", (trading["regular_open_et"] == "09:30").all())
    normal = trading[~trading["is_early_close"]]
    _check(checks, "normal_close_1600", (normal["regular_close_et"] == "16:00").all())
    early = trading[trading["is_early_close"]]
    _check(checks, "early_close_not_before_1300", all(str(value) >= "13:00" for value in early["regular_close_et"]))

    _check(checks, "dataset_split_not_null", calendar["dataset_split"].notna().all())
    _check(checks, "research_split_not_null", calendar["research_split"].notna().all())
    _check(checks, "dataset_split_allowed", set(calendar["dataset_split"].unique()) <= {"Train", "Val", "OOS"})
    _check(checks, "research_split_allowed", set(calendar["research_split"].unique()) <= {"Train", "Val-A", "Val-B", "OOS"})
    _check_split_ranges(checks, calendar)
    _check_fixture_dates(checks, calendar)

    massive_cross_check = _massive_cross_check(calendar, discover_local_massive_date_listings(root))

    summary = {
        "row_count": int(len(calendar)),
        "trading_day_count": int(calendar["is_trading_day"].sum()),
        "early_close_count": int(calendar["is_early_close"].sum()),
        "start_date": str(start),
        "end_date": str(end),
        "dataset_split_ranges": _ranges(calendar, "dataset_split"),
        "research_split_ranges": _ranges(calendar, "research_split"),
        "calendar_source": CALENDAR_NAME,
        "exchange_calendars_version": metadata.version("exchange_calendars"),
        "python_version": platform.python_version(),
    }

    status = "GO" if all(check["passed"] for check in checks) else "NO-GO"
    return QAResult(status=status, checks=checks, summary=summary, massive_cross_check=massive_cross_check)


def _check_split_ranges(checks: list[dict[str, Any]], calendar: pd.DataFrame) -> None:
    expected = {
        ("dataset_split", "Train"): ("2016-08-14", "2021-12-31"),
        ("dataset_split", "Val"): ("2022-01-01", "2023-12-31"),
        ("dataset_split", "OOS"): ("2024-01-01", "2026-06-29"),
        ("research_split", "Train"): ("2016-08-14", "2021-12-31"),
        ("research_split", "Val-A"): ("2022-01-01", "2022-12-31"),
        ("research_split", "Val-B"): ("2023-01-01", "2023-12-31"),
        ("research_split", "OOS"): ("2024-01-01", "2026-06-29"),
    }
    for (column, value), (expected_min, expected_max) in expected.items():
        rows = calendar[calendar[column] == value]
        actual = (str(rows["date"].min()), str(rows["date"].max()))
        _check(
            checks,
            f"{column}_{value}_range",
            actual == (expected_min, expected_max),
            f"actual={actual} expected={(expected_min, expected_max)}",
        )


def _check_fixture_dates(checks: list[dict[str, Any]], calendar: pd.DataFrame) -> None:
    fixtures = {
        "weekend_2024_01_06": ("2024-01-06", False, None, None, False),
        "holiday_2024_01_01": ("2024-01-01", False, None, None, False),
        "normal_2024_01_02": ("2024-01-02", True, "09:30", "16:00", False),
        "early_close_2024_11_29": ("2024-11-29", True, "09:30", "13:00", True),
        "train_start_2016_08_14": ("2016-08-14", False, None, None, False),
        "train_last_2021_12_31": ("2021-12-31", True, "09:30", "16:00", False),
        "val_a_start_2022_01_01": ("2022-01-01", False, None, None, False),
        "val_a_last_2022_12_31": ("2022-12-31", False, None, None, False),
        "val_b_start_2023_01_01": ("2023-01-01", False, None, None, False),
        "val_b_last_2023_12_31": ("2023-12-31", False, None, None, False),
        "oos_start_2024_01_01": ("2024-01-01", False, None, None, False),
        "oos_last_2026_06_29": ("2026-06-29", True, "09:30", "16:00", False),
    }
    for name, (day, is_trading, open_et, close_et, is_early_close) in fixtures.items():
        try:
            row = _row_for(calendar, day)
            passed = (
                bool(row["is_trading_day"]) == is_trading
                and _nullable_equal(row["regular_open_et"], open_et)
                and _nullable_equal(row["regular_close_et"], close_et)
                and bool(row["is_early_close"]) == is_early_close
            )
            detail = (
                f"is_trading_day={row['is_trading_day']} open={row['regular_open_et']} "
                f"close={row['regular_close_et']} is_early_close={row['is_early_close']}"
            )
        except AssertionError as exc:
            passed = False
            detail = str(exc)
        _check(checks, f"fixture_{name}", passed, detail)


def _nullable_equal(actual: Any, expected: str | None) -> bool:
    if expected is None:
        return pd.isna(actual)
    return actual == expected


def _ranges(calendar: pd.DataFrame, column: str) -> dict[str, dict[str, str]]:
    ranges: dict[str, dict[str, str]] = {}
    for value in sorted(calendar[column].unique()):
        rows = calendar[calendar[column] == value]
        ranges[value] = {"start": str(rows["date"].min()), "end": str(rows["date"].max())}
    return ranges


def _massive_cross_check(calendar: pd.DataFrame, listing: dict[str, Any]) -> dict[str, Any]:
    if listing["status"] != "available":
        return listing

    trading_dates = {str(day) for day in calendar.loc[calendar["is_trading_day"], "date"]}
    result: dict[str, Any] = {"status": "available", "comparisons": {}}
    for key, values in listing["dates"].items():
        vendor_dates = set(values)
        result["comparisons"][key] = {
            "vendor_date_count": len(vendor_dates),
            "missing_from_vendor": sorted(trading_dates - vendor_dates),
            "extra_in_vendor": sorted(vendor_dates - trading_dates),
        }
    return result


def write_calendar_if_qa_passes(calendar: pd.DataFrame, qa: QAResult, output_path: Path) -> bool:
    if not qa.passed:
        return False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name(f"{output_path.name}.tmp")
    table = pa.Table.from_pandas(calendar, preserve_index=False)
    pq.write_table(table, tmp_path, compression="zstd")
    os.replace(tmp_path, output_path)
    return True


def write_qa_report(report_path: Path, output_path: Path, qa: QAResult, commands_run: list[str], wrote_output: bool) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "# Phase 0.1 Trading Calendar QA Report",
        "",
        "## Status",
        "",
        qa.status,
        "",
        "## Changed files",
        "",
        "- `configs/project_v0.yaml`",
        "- `src/phase_00_trading_calendar.py`",
        "- `tests/test_phase_00_trading_calendar.py`",
        "- `requirements.txt`",
        f"- `{output_path.as_posix()}`",
        f"- `{report_path.as_posix()}`",
        "- `TODO.md`",
        "",
        "## What was implemented",
        "",
        "- Built `trading_calendar_v0` from `exchange_calendars.get_calendar(\"XNYS\")`.",
        "- Assigned `dataset_split` and `research_split` from `PROJECT.md` canonical dates.",
        "- Added schema, fixture, split, session-boundary, and reproducibility QA.",
        "- Wrote the calendar only after QA passed.",
        "",
        "## Commands run",
        "",
        "```bash",
        *commands_run,
        "```",
        "",
        "## Results",
        "",
        f"- Output written: `{wrote_output}`",
        f"- Output path: `{output_path.as_posix()}`",
        f"- Row count: `{qa.summary['row_count']}`",
        f"- Trading-day count: `{qa.summary['trading_day_count']}`",
        f"- Early-close count: `{qa.summary['early_close_count']}`",
        f"- Calendar source: `{qa.summary['calendar_source']}`",
        f"- exchange_calendars version: `{qa.summary['exchange_calendars_version']}`",
        f"- Python version: `{qa.summary['python_version']}`",
        "",
        "## Split ranges",
        "",
        "### dataset_split",
        "",
    ]
    for split, values in qa.summary["dataset_split_ranges"].items():
        lines.append(f"- `{split}`: `{values['start']}` through `{values['end']}`")
    lines.extend(["", "### research_split", ""])
    for split, values in qa.summary["research_split_ranges"].items():
        lines.append(f"- `{split}`: `{values['start']}` through `{values['end']}`")
    lines.extend(["", "## QA summary", ""])
    for check in qa.checks:
        status = "PASS" if check["passed"] else "FAIL"
        detail = f" - {check['detail']}" if check["detail"] else ""
        lines.append(f"- `{status}` `{check['name']}`{detail}")
    lines.extend(["", "## Massive date cross-check", ""])
    if qa.massive_cross_check["status"] == "unavailable":
        lines.append(f"- Status: `unavailable`")
        lines.append(f"- Detail: {qa.massive_cross_check['detail']}")
    else:
        lines.append("- Status: `available`")
        for key, comparison in qa.massive_cross_check["comparisons"].items():
            lines.append(f"- `{key}` vendor date count: `{comparison['vendor_date_count']}`")
            lines.append(f"- `{key}` missing from vendor count: `{len(comparison['missing_from_vendor'])}`")
            lines.append(f"- `{key}` extra in vendor count: `{len(comparison['extra_in_vendor'])}`")
    lines.extend(
        [
            "",
            "## Risks / unknowns",
            "",
            "- Massive local file-date listings are optional for Phase 0 and may be unavailable before Phase 1 data exists.",
            "- Calendar-source behavior depends on the recorded `exchange_calendars` version.",
            "",
            "## Suggested next task",
            "",
            "- Phase 0.2 Review Calendar Artifact",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")


def read_back_calendar(output_path: Path) -> pd.DataFrame:
    return pd.read_parquet(output_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Phase 0 trading calendar.")
    parser.add_argument("--config", default="configs/project_v0.yaml")
    parser.add_argument("--output", default="data/reference/trading_calendar_v0.parquet")
    parser.add_argument("--report", default="reports/phase_00/trading_calendar_qa.md")
    parser.add_argument("--command", action="append", default=[])
    args = parser.parse_args(argv)

    root = Path.cwd()
    config_path = root / args.config
    output_path = root / args.output
    report_path = root / args.report
    config = load_config(config_path)
    calendar = build_trading_calendar(config)
    qa = validate_calendar(calendar, config, root)
    wrote_output = write_calendar_if_qa_passes(calendar, qa, output_path)
    if wrote_output:
        read_back = read_back_calendar(output_path)
        if len(read_back) != len(calendar):
            qa.checks.append(
                {
                    "name": "read_back_row_count",
                    "passed": False,
                    "detail": f"read_back={len(read_back)} expected={len(calendar)}",
                }
            )
            qa = QAResult(status="NO-GO", checks=qa.checks, summary=qa.summary, massive_cross_check=qa.massive_cross_check)

    commands = args.command or [
        "python -m src.phase_00_trading_calendar",
    ]
    write_qa_report(report_path, output_path, qa, commands, wrote_output)
    return 0 if qa.passed and wrote_output else 1


if __name__ == "__main__":
    raise SystemExit(main())
