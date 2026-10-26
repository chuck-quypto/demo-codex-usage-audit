"""Read Codex CLI session logs and flag sudden jumps in rate-limit usage.

Read-only. Nothing is sent over the network and nothing is written to the logs.
The log format is not documented by OpenAI; field names are matched defensively.
"""

import itertools
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Reading:
    at: str
    window_minutes: int
    used_percent: float
    plan_type: str
    source: str


@dataclass(frozen=True)
class Cliff:
    at: str
    window_minutes: int
    before: float
    after: float
    previous_at: str = ""
    plan_before: str = "unknown"
    plan_after: str = "unknown"

    @property
    def delta(self) -> float:
        return round(self.after - self.before, 1)


def _find_rate_limits(node):
    """Return the first dict under a 'rate_limits' key, searching nested objects."""
    if isinstance(node, dict):
        if isinstance(node.get("rate_limits"), dict):
            return node["rate_limits"]
        for value in node.values():
            found = _find_rate_limits(value)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_rate_limits(value)
            if found is not None:
                return found
    return None


def _readings_from_line(line: str, source: str, at_default: str) -> list[Reading]:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return []
    limits = _find_rate_limits(event)
    if limits is None:
        return []
    at = event.get("timestamp", at_default)
    plan = str(limits.get("plan_type", "unknown"))
    out = []
    for key in ("primary", "secondary"):
        window = limits.get(key)
        if not isinstance(window, dict):
            continue
        if "used_percent" not in window or "window_minutes" not in window:
            continue
        out.append(
            Reading(
                at=at,
                window_minutes=int(window["window_minutes"]),
                used_percent=float(window["used_percent"]),
                plan_type=plan,
                source=source,
            )
        )
    return out


def collect_readings(sessions_dir: Path) -> list[Reading]:
    """Collect every rate-limit reading under sessions_dir, sorted by time per window."""
    readings: list[Reading] = []
    for path in sorted(Path(sessions_dir).rglob("*.jsonl")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            readings.extend(_readings_from_line(line, str(path), at_default=""))
    readings.sort(key=lambda r: (r.window_minutes, _parse_time(r.at)))
    return readings


def _parse_time(value: str) -> datetime:
    if not value:
        return datetime.min
    return datetime.fromisoformat(value)


def find_cliffs(readings: list[Reading], threshold: float) -> list[Cliff]:
    """Flag consecutive readings in the same window that rise by more than threshold points."""
    cliffs: list[Cliff] = []
    for prev, cur in itertools.pairwise(readings):
        if prev.window_minutes != cur.window_minutes:
            continue
        if cur.used_percent - prev.used_percent > threshold:
            cliffs.append(
                Cliff(
                    at=cur.at,
                    window_minutes=cur.window_minutes,
                    before=prev.used_percent,
                    after=cur.used_percent,
                    previous_at=prev.at,
                    plan_before=prev.plan_type,
                    plan_after=cur.plan_type,
                )
            )
    return cliffs


def format_gap(previous_at: str, at: str) -> str:
    """Describe the time between two readings, such as '40m' or '3h 05m'."""
    if not previous_at or not at:
        return "unknown time"
    minutes = int((_parse_time(at) - _parse_time(previous_at)).total_seconds() // 60)
    days, rest = divmod(minutes, 24 * 60)
    hours, mins = divmod(rest, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {mins:02d}m"
    return f"{mins}m"


def run_audit(sessions_dir: Path, threshold: float) -> str:
    readings = collect_readings(sessions_dir)
    if not readings:
        return (
            f"No rate_limits events found under {sessions_dir}. "
            "Run Codex CLI once, or pass --sessions to point at your logs."
        )
    cliffs = find_cliffs(readings, threshold)
    lines = [f"Read {len(readings)} rate-limit readings."]
    if not cliffs:
        lines.append(f"No jumps above {threshold} points.")
    for c in cliffs:
        hours = c.window_minutes // 60
        line = (
            f"  {c.at}  {hours}h window  {c.before:.1f}% -> {c.after:.1f}%  "
            f"(+{c.after - c.before:.1f})  "
            f"{format_gap(c.previous_at, c.at)} after the previous reading"
        )
        if c.plan_before != c.plan_after:
            line += f", plan changed {c.plan_before} -> {c.plan_after}"
        lines.append(line)
    return "\n".join(lines)
