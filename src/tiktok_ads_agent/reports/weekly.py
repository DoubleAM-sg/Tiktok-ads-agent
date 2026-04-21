"""Weekly optimization report.

Pulls last-completed-ISO-week's per-ad metrics, ranks ads by CPA, and
commits a snapshot under ``.state/weekly_snapshots/YYYY-WNN.json``.
Auto-pause proposals are skipped until W1–W2 baselines exist — for
now this is a ranking + visibility report.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from tiktok_ads_agent.core.settings import Settings
from tiktok_ads_agent.models.schemas import Snapshot
from tiktok_ads_agent.reports.common import ad_name_map, fetch_snapshot, totals
from tiktok_ads_agent.state.persistence import save_snapshot

SGT = ZoneInfo("Asia/Singapore")


def last_iso_week() -> tuple[str, date, date]:
    """Return (period_id, Mon date, Sun date) for the most recent complete ISO week.

    Example: if today is Tue 2026-04-21, the previous complete week is
    2026-W16, Mon 2026-04-13 to Sun 2026-04-19.
    """

    today = datetime.now(SGT).date()
    # Most recent Sunday on or before yesterday
    days_since_sunday = (today.weekday() + 1) % 7  # Monday=0 ... Sunday=6
    this_sunday = today - timedelta(days=days_since_sunday)
    if this_sunday >= today:
        this_sunday -= timedelta(days=7)
    last_sunday = this_sunday
    last_monday = last_sunday - timedelta(days=6)
    iso_year, iso_week, _ = last_monday.isocalendar()
    period_id = f"{iso_year}-W{iso_week:02d}"
    return period_id, last_monday, last_sunday


def build_telegram_summary(snapshot: Snapshot) -> str:
    """Format a plain-text Telegram message for a weekly snapshot."""

    t = totals(snapshot)
    names = ad_name_map(snapshot)
    active_ad_ids = {ad.ad_id for ad in snapshot.ads if ad.operation_status == "ENABLE"}

    rows = [m for m in snapshot.metrics if m.ad_id in active_ad_ids and m.spend > 0]
    with_conv = [m for m in rows if m.conversion > 0]
    no_conv = sorted(
        [m for m in rows if m.conversion == 0],
        key=lambda m: m.spend,
        reverse=True,
    )
    with_conv.sort(key=lambda m: m.cost_per_conversion if m.cost_per_conversion else float("inf"))

    lines: list[str] = []
    lines.append(
        f"📈 Weekly report — {snapshot.period_id} "
        f"({snapshot.start_date} → {snapshot.end_date}, SGT)"
    )
    lines.append(f"advertiser {snapshot.advertiser_id}")
    lines.append("")
    lines.append(
        f"Totals: spend {t['spend']:.2f} · "
        f"impr {int(t['impressions']):,} · "
        f"clk {int(t['clicks']):,} · "
        f"CTR {t['ctr']:.2f}% · "
        f"conv {int(t['conversion'])} · "
        f"CPA {t['cpa']:.2f}"
    )

    if with_conv:
        lines.append("")
        lines.append("Winners (lowest CPA):")
        for m in with_conv[:5]:
            name = (names.get(m.ad_id) or m.ad_id)[:45]
            cpa = f"{m.cost_per_conversion:.2f}" if m.cost_per_conversion else "—"
            lines.append(f"  · {name} — CPA {cpa} · conv {m.conversion} · spend {m.spend:.2f}")

    if no_conv:
        lines.append("")
        lines.append("Zero-conv spenders (7d):")
        for m in no_conv[:5]:
            name = (names.get(m.ad_id) or m.ad_id)[:45]
            lines.append(f"  · {name} — spend {m.spend:.2f} · clk {m.clicks} · 0 conv")

    lines.append("")
    lines.append(f"Snapshot: .state/weekly_snapshots/{snapshot.period_id}.json")
    lines.append("No auto-pause proposals yet — baselines will build from W1–W2 data.")
    return "\n".join(lines)


def run(settings: Settings) -> tuple[Snapshot, str]:
    """Fetch last complete ISO week's data, persist snapshot, return (snapshot, msg)."""

    period_id, start, end = last_iso_week()
    snapshot = fetch_snapshot(
        settings,
        cadence="weekly",
        period_id=period_id,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
    )
    save_snapshot(snapshot)
    return snapshot, build_telegram_summary(snapshot)
