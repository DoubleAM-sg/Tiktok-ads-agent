"""Monthly strategic report.

Pulls the previous calendar month's per-ad metrics, commits a snapshot
under ``.state/monthly_snapshots/YYYY-MM.json``, and computes MoM deltas
against the month before that if its snapshot exists.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from zoneinfo import ZoneInfo

from tiktok_ads_agent.core.settings import Settings
from tiktok_ads_agent.models.schemas import Snapshot
from tiktok_ads_agent.reports.common import fetch_snapshot, totals
from tiktok_ads_agent.state.persistence import load_snapshot, save_snapshot

SGT = ZoneInfo("Asia/Singapore")


def last_calendar_month() -> tuple[str, date, date]:
    """Return (period_id 'YYYY-MM', first, last) for the previous month."""

    today = datetime.now(SGT).date()
    if today.month == 1:
        year, month = today.year - 1, 12
    else:
        year, month = today.year, today.month - 1
    last_day = monthrange(year, month)[1]
    return (
        f"{year:04d}-{month:02d}",
        date(year, month, 1),
        date(year, month, last_day),
    )


def _prev_period_id(period_id: str) -> str:
    year_s, month_s = period_id.split("-")
    year, month = int(year_s), int(month_s)
    if month == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{month - 1:02d}"


def _delta_line(label: str, curr: float, prev: float | None, *, as_int: bool = False) -> str:
    if prev is None:
        curr_s = f"{int(curr)}" if as_int else f"{curr:.2f}"
        return f"{label}: {curr_s} (no prior month)"
    if prev == 0:
        pct = "n/a"
    else:
        pct = f"{(curr - prev) / prev * 100:+.1f}%"
    if as_int:
        return f"{label}: {int(curr)} vs {int(prev)} ({pct})"
    return f"{label}: {curr:.2f} vs {prev:.2f} ({pct})"


def _fatigue_summary(snapshot: Snapshot) -> tuple[int, float, int]:
    """Return (fatigued_ad_count, avg_weighted_frequency, total_reach)."""

    rows = [m for m in snapshot.metrics if m.spend > 0]
    fatigued = sum(1 for m in rows if m.is_fatigued)
    total_reach = sum(m.reach for m in rows)
    weighted_freq = sum(m.frequency * m.reach for m in rows) / total_reach if total_reach else 0.0
    return fatigued, round(weighted_freq, 2), total_reach


def build_telegram_summary(current: Snapshot, previous: Snapshot | None) -> str:
    """Format a plain-text Telegram message for a monthly snapshot + MoM."""

    c = totals(current)
    p = totals(previous) if previous else None
    c_fatigued, c_freq, c_reach = _fatigue_summary(current)

    lines: list[str] = []
    lines.append(
        f"📅 Monthly report — {current.period_id} ({current.start_date} → {current.end_date}, SGT)"
    )
    lines.append(f"advertiser {current.advertiser_id}")
    lines.append("")
    lines.append(_delta_line("Spend", c["spend"], p["spend"] if p else None))
    lines.append(
        _delta_line(
            "Conversions",
            c["conversion"],
            p["conversion"] if p else None,
            as_int=True,
        )
    )
    lines.append(_delta_line("CPA", c["cpa"], p["cpa"] if p else None))
    lines.append(_delta_line("CTR %", c["ctr"], p["ctr"] if p else None))

    if previous is not None:
        _, p_freq, _ = _fatigue_summary(previous)
        lines.append(_delta_line("Avg frequency", c_freq, p_freq))
    else:
        lines.append(f"Avg frequency: {c_freq:.2f} (no prior month)")

    lines.append(f"Unique reach: {c_reach:,} · fatigued ads (freq ≥ 3): {c_fatigued}")

    lines.append("")
    lines.append(f"Snapshot: .state/monthly_snapshots/{current.period_id}.json")
    if previous is None:
        lines.append("First month on record — MoM kicks in once two months are captured.")
    return "\n".join(lines)


def run(settings: Settings) -> tuple[Snapshot, str]:
    """Fetch previous calendar month's data, persist snapshot, return (snapshot, msg)."""

    period_id, start, end = last_calendar_month()
    snapshot = fetch_snapshot(
        settings,
        cadence="monthly",
        period_id=period_id,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
    )
    save_snapshot(snapshot)
    previous = load_snapshot("monthly", _prev_period_id(period_id))
    return snapshot, build_telegram_summary(snapshot, previous)
