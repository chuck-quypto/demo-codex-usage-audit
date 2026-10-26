import json
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
    assert "Other rises" not in report


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


def _line(at, used, plan="pro"):
    event = {
        "type": "event_msg",
        "timestamp": at,
        "payload": {
            "type": "token_count",
            "rate_limits": {
                "plan_type": plan,
                "secondary": {"used_percent": used, "window_minutes": 10080},
            },
        },
    }
    return json.dumps(event)


def _write(tmp_path, lines):
    path = tmp_path / "2026" / "10" / "26" / "rollout.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(lines) + "\n")
    return tmp_path


def test_rise_after_long_gap_is_not_sudden(tmp_path):
    sessions = _write(
        tmp_path,
        [_line("2026-10-16T22:00:00Z", 19.0), _line("2026-10-18T15:00:00Z", 60.0)],
    )
    report = run_audit(sessions, threshold=5.0)
    sudden, other = report.split("Other rises, not counted as sudden:")
    assert "None." in sudden
    assert "+41.0" in other and "long gap with no readings" in other


def test_reading_with_no_plan_is_left_out(tmp_path):
    sessions = _write(
        tmp_path,
        [
            _line("2026-10-26T06:08:23Z", 30.0),
            _line("2026-10-26T06:08:23Z", 0.0, plan=None),
            _line("2026-10-26T06:08:24Z", 33.0),
        ],
    )
    report = run_audit(sessions, threshold=5.0)
    assert "Left out 1 readings that reported no plan." in report
    assert "None." in report
    assert "Other rises" not in report


def test_plan_change_is_not_sudden(tmp_path):
    sessions = _write(
        tmp_path,
        [
            _line("2026-10-09T13:00:00Z", 19.0, plan="prolite"),
            _line("2026-10-09T13:10:00Z", 54.0),
        ],
    )
    report = run_audit(sessions, threshold=5.0)
    assert "plan changed prolite -> pro" in report.split("Other rises")[1]
