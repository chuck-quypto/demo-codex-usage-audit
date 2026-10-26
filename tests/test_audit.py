from pathlib import Path

from codex_usage_audit.audit import (
    Reading,
    collect_readings,
    find_cliffs,
    format_gap,
    run_audit,
)

FIXTURES = Path(__file__).parent / "fixtures" / "sessions"


def test_collect_readings_reads_both_windows_and_skips_other_events():
    readings = collect_readings(FIXTURES)
    windows = {r.window_minutes for r in readings}
    assert windows == {300, 10080}
    assert len(readings) == 6  # 3 token_count events x 2 windows


def test_cliff_is_flagged_and_small_drift_is_not():
    readings = collect_readings(FIXTURES)
    cliffs = find_cliffs(readings, threshold=5.0)
    assert len(cliffs) == 1
    cliff = cliffs[0]
    assert cliff.window_minutes == 10080
    assert cliff.delta == 12.0
    assert cliff.at == "2026-10-16T18:10:00Z"
    assert cliff.previous_at == "2026-10-16T17:30:00Z"


def test_empty_directory_gives_a_plain_message(tmp_path):
    report = run_audit(tmp_path, threshold=5.0)
    assert "No rate_limits events found" in report


def test_report_mentions_the_cliff(tmp_path):
    report = run_audit(FIXTURES, threshold=5.0)
    assert "+12.0" in report
    assert "18:10" in report
    assert "40m after the previous reading" in report
    assert "plan changed" not in report


def test_gap_is_readable():
    assert format_gap("2026-10-16T17:30:00Z", "2026-10-16T18:10:00Z") == "40m"
    assert format_gap("2026-10-16T01:00:00Z", "2026-10-16T04:05:00Z") == "3h 05m"
    assert format_gap("2026-10-14T01:00:00Z", "2026-10-16T05:00:00Z") == "2d 4h"
    assert format_gap("", "2026-10-16T05:00:00Z") == "unknown time"


def test_plan_change_is_called_out():
    readings = [
        Reading("2026-10-16T17:00:00Z", 10080, 10.0, "plus", "a"),
        Reading("2026-10-16T17:05:00Z", 10080, 50.0, "pro", "b"),
    ]
    report_line = find_cliffs(readings, threshold=5.0)[0]
    assert (report_line.plan_before, report_line.plan_after) == ("plus", "pro")


def test_reading_is_a_plain_value():
    r = Reading(
        at="t", window_minutes=300, used_percent=1.0, plan_type="plus", source="f"
    )
    assert r.used_percent == 1.0
