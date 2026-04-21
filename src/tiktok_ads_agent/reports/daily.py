"""Daily early-warning report.

Pulls yesterday's per-ad metrics, commits a snapshot under
``.state/daily_snapshots/YYYY-MM-DD.json``, and returns a Telegram
summary. No auto-pause — daily is alert-only per the handover.

Flag logic (pacing, zero-conv burn, CTR crash) will layer in once we
have W1–W2 baselines. For now the report focuses on structure: totals
+ per-ad table, plus adgroup ``optimization_event`` context so we can
verify what conversions refer to.
"""

from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from tiktok_ads_agent.core.settings import Settings
from tiktok_ads_agent.models.schemas import Snapshot
from tiktok_ads_agent.reports.common import ad_name_map, fetch_snapshot, totals
from tiktok_ads_agent.state.persistence import save_snapshot

SGT = ZoneInfo("Asia/Singapore")


def yesterday_sgt() -> date:
    """Return 'yesterday' in Singapore — the advertiser's reporting timezone."""

    from datetime import datetime as _dt

    return (_dt.now(SGT).date()) - timedelta(days=1)


def build_telegram_summary(snapshot: Snapshot) -> str:
    """Format a plain-text Telegram message for a daily snapshot."""

    t = totals(snapshot)
    names = ad_name_map(snapshot)

    active_ads = {ad.ad_id for ad in snapshot.ads if ad.operation_status == "ENABLE"}
    active_metric_rows = sorted(
        (m for m in snapshot.metrics if m.ad_id in active_ads),
        key=lambda m: m.spend,
        reverse=True,
    )

    lines: list[str] = []
    lines.append(f"📊 Daily report — {snapshot.start_date} (SGT)")
    lines.append(f"advertiser {snapshot.advertiser_id}")
    lines.append(
        f"{len(snapshot.campaigns)} campaigns · "
        f"{len(snapshot.adgroups)} adgroups · "
        f"{len(active_ads)} active ads (of {len(snapshot.ads)})"
    )
    lines.append("")
    lines.append(
        f"Spend: {t['spend']:.2f} · "
        f"Impr: {int(t['impressions']):,} · "
        f"Clk: {int(t['clicks']):,} · "
        f"CTR: {t['ctr']:.2f}% · "
        f"Conv: {int(t['conversion'])} · "
        f"CPA: {t['cpa']:.2f}"
    )

    if active_metric_rows:
        lines.append("")
        lines.append("Active ads (by spend):")
        for m in active_metric_rows[:10]:
            name = (names.get(m.ad_id) or m.ad_id)[:45]
            cpa = f"{m.cost_per_conversion:.2f}" if m.cost_per_conversion else "—"
            lines.append(
                f"  · {name} — spend {m.spend:.2f} · "
                f"clk {m.clicks} · conv {m.conversion} · CPA {cpa}"
            )

    # Surface optimization events so we can verify what 'conversion' means
    active_groups = [g for g in snapshot.adgroups if g.operation_status == "ENABLE"]
    if active_groups:
        lines.append("")
        lines.append("Optimization events (active adgroups):")
        for g in active_groups[:5]:
            lines.append(
                f"  · {g.adgroup_name or g.adgroup_id}: "
                f"goal={g.optimization_goal or '-'} · "
                f"event={g.optimization_event or '-'} · "
                f"pixel={g.pixel_id or '-'}"
            )

    return "\n".join(lines)


def run(settings: Settings) -> tuple[Snapshot, str]:
    """Fetch yesterday's data, persist snapshot, return (snapshot, message)."""

    target = yesterday_sgt()
    period_id = target.isoformat()
    snapshot = fetch_snapshot(
        settings,
        cadence="daily",
        period_id=period_id,
        start_date=period_id,
        end_date=period_id,
    )
    save_snapshot(snapshot)
    return snapshot, build_telegram_summary(snapshot)
