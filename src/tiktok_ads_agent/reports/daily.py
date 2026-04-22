"""Daily early-warning report.

Pulls yesterday's per-ad metrics, commits a snapshot under
``.state/daily_snapshots/YYYY-MM-DD.json``, and returns a Telegram
summary formatted to match the Meta-ads-agent daily layout so the
two feeds read side-by-side. No auto-pause — daily is alert-only per
the handover.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from tiktok_ads_agent.core.settings import Settings
from tiktok_ads_agent.models.schemas import Snapshot
from typing import Any

from tiktok_ads_agent.reports.common import (
    aggregate_by_adgroup,
    aggregate_by_campaign,
    aggregate_by_creative,
    display_name_map,
    fetch_mtd_campaign_totals,
    fetch_snapshot,
    short_label,
    totals,
)
from tiktok_ads_agent.state.persistence import (
    load_creative_registry,
    load_snapshot,
    save_snapshot,
)

SGT = ZoneInfo("Asia/Singapore")
CREATIVE_LABEL_LEN = 32
AD_LABEL_LEN = 40

# Signal thresholds — benchmarked against the account's own history, not
# external industry figures.
FREQUENCY_FATIGUE = 3.0          # Corey Haines seen-and-ignored
CTR_DROP_RATIO = 0.5             # today < 50% of own N-day avg
CTR_DROP_MIN_HISTORY = 3         # need at least N prior days to trust the avg
NEW_AD_DAYS = 3                  # <3 days since create_time = "new"
THREE_TWO_ONE_TARGET = 3         # active ads per ad group


def yesterday_sgt() -> date:
    """Return 'yesterday' in Singapore — the advertiser's reporting timezone."""

    return datetime.now(SGT).date() - timedelta(days=1)


def _load_prior_snapshots(up_to: date, days: int = 7) -> list[Snapshot]:
    """Load the ``days`` daily snapshots preceding ``up_to`` (exclusive)."""

    loaded: list[Snapshot] = []
    for offset in range(1, days + 1):
        snap = load_snapshot("daily", (up_to - timedelta(days=offset)).isoformat())
        if snap is not None:
            loaded.append(snap)
    return loaded


def _fmt_short_date(d: date) -> str:
    """Format ``date(2026, 4, 22)`` as ``"22 Apr"``."""

    return f"{d.day} {d.strftime('%b')}"


def _pacing_icon(actual_pct: float, expected_pct: float) -> str:
    """✅ if within ±20pct of expected, ⚠️ otherwise."""

    return "✅" if abs(actual_pct - expected_pct) <= 20.0 else "⚠️"


def _campaign_daily_budget(
    campaign: object,
) -> float | None:
    """Return the campaign's daily budget if the mode is daily + positive."""

    budget = getattr(campaign, "budget", None) or 0.0
    mode = getattr(campaign, "budget_mode", "") or ""
    if budget > 0 and "DAILY" in mode:
        return float(budget)
    return None


def _parse_tiktok_ts(value: str | None) -> datetime | None:
    """Parse TikTok's ``create_time`` / ``modify_time`` strings.

    The API emits naive ``"YYYY-MM-DD HH:MM:SS"`` in the advertiser's
    timezone. Returns a tz-aware datetime in SGT, or ``None`` on any
    parse failure (we treat missing timestamps as unknown, not new).
    """

    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("T", " ").rstrip("Z"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SGT)
    return parsed


def _detect_signals(
    snapshot: Snapshot,
    *,
    prior_daily: list[Snapshot],
    today: datetime,
    display_names: dict[str, str],
) -> list[str]:
    """Flag fatigue, CTR drops, understaffed ad groups, and new ads.

    All thresholds compare against the account's own history — no
    external benchmarks. Requires ``CTR_DROP_MIN_HISTORY`` prior daily
    snapshots before it will call out a CTR drop.
    """

    flags: list[str] = []

    # Frequency ≥ 3 = Corey Haines fatigue signal.
    for m in snapshot.metrics:
        if m.frequency >= FREQUENCY_FATIGUE:
            label = display_names.get(m.ad_id) or m.ad_id
            flags.append(f"  · freq {m.frequency:.1f} on {label} (fatigue)")

    # Per-ad CTR drop vs own N-day avg.
    if len(prior_daily) >= CTR_DROP_MIN_HISTORY:
        history: dict[str, list[float]] = {}
        for snap in prior_daily:
            for m in snap.metrics:
                if m.impressions > 0:
                    history.setdefault(m.ad_id, []).append(m.ctr)
        for m in snapshot.metrics:
            hist = history.get(m.ad_id, [])
            if len(hist) < CTR_DROP_MIN_HISTORY or m.impressions == 0:
                continue
            avg = sum(hist) / len(hist)
            if avg > 0 and m.ctr < avg * CTR_DROP_RATIO:
                label = display_names.get(m.ad_id) or m.ad_id
                delta = (m.ctr - avg) / avg * 100.0
                flags.append(
                    f"  · CTR drop on {label}: "
                    f"{m.ctr:.2f}% vs {avg:.2f}% avg ({delta:+.0f}%)"
                )

    # 3-2-1 check and new-ad (<3d) annotation.
    active_by_group: dict[str, list] = {}
    for ad in snapshot.ads:
        if ad.operation_status == "ENABLE" and ad.adgroup_id:
            active_by_group.setdefault(ad.adgroup_id, []).append(ad)

    adgroups_by_id = {g.adgroup_id: g for g in snapshot.adgroups}
    understaffed = [
        (gid, len(ads))
        for gid, ads in active_by_group.items()
        if len(ads) < THREE_TWO_ONE_TARGET
    ]
    if understaffed:
        parts = []
        for gid, count in understaffed:
            group = adgroups_by_id.get(gid)
            gname = (group.adgroup_name if group else None) or gid
            parts.append(f"{gname} ({count}/{THREE_TWO_ONE_TARGET})")
        flags.append("  · 3-2-1 below target — " + ", ".join(parts))

    cutoff = today - timedelta(days=NEW_AD_DAYS)
    new_ads = []
    for ad in snapshot.ads:
        if ad.operation_status != "ENABLE":
            continue
        created = _parse_tiktok_ts(ad.create_time)
        if created and created >= cutoff:
            new_ads.append(ad)
    if new_ads:
        labels = ", ".join(
            (display_names.get(a.ad_id) or short_label(a.ad_name, 22))
            for a in new_ads[:3]
        )
        suffix = "" if len(new_ads) <= 3 else f" +{len(new_ads) - 3} more"
        flags.append(f"  · new (<{NEW_AD_DAYS}d): {len(new_ads)} — {labels}{suffix}")

    return flags


def build_telegram_summary(
    snapshot: Snapshot,
    *,
    prior_daily: list[Snapshot] | None = None,
    mtd: dict[str, dict[str, float]] | None = None,
    today: date | None = None,
    registry: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Format the daily Telegram message.

    ``prior_daily`` powers the "vs Nd avg" CPA delta; ``mtd`` populates
    the MTD Pacing section; ``registry`` maps ``ad_id`` to the short
    label shown in every section (falls back to truncated ``ad_name``
    when absent). All three are optional so the function stays pure and
    testable; :func:`run` wires up the real data.
    """

    prior_daily = prior_daily or []
    mtd = mtd or {}
    today = today or datetime.now(SGT).date()
    registry = registry or {}
    data_date = date.fromisoformat(snapshot.start_date)

    t = totals(snapshot)
    display_names = display_name_map(snapshot, registry=registry, max_len=AD_LABEL_LEN)
    by_campaign = aggregate_by_campaign(snapshot)
    by_adgroup = aggregate_by_adgroup(snapshot)
    by_creative = aggregate_by_creative(
        snapshot, registry=registry, label_len=CREATIVE_LABEL_LEN
    )

    campaigns_by_id = {c.campaign_id: c for c in snapshot.campaigns}
    adgroups_by_id = {g.adgroup_id: g for g in snapshot.adgroups}

    # ── Header ──────────────────────────────────────────────────────
    lines: list[str] = []
    lines.append(f"📊 TikTok Ads · Daily — {_fmt_short_date(today)} "
                 f"(data: {_fmt_short_date(data_date)})")
    lines.append("")

    # ── Conversions headline ────────────────────────────────────────
    conv_breakdown = ", ".join(
        f"{(campaigns_by_id.get(cid).campaign_name or cid) if campaigns_by_id.get(cid) else cid} "
        f"{int(row['conversion'])}"
        for cid, row in sorted(by_campaign.items(), key=lambda kv: kv[1]["conversion"], reverse=True)
        if row["conversion"] > 0
    )
    conv_total = int(t["conversion"])
    conv_line = f"✅ {conv_total} conversion{'s' if conv_total != 1 else ''}"
    if conv_breakdown:
        conv_line += f" — {conv_breakdown}"
    lines.append(conv_line)

    # ── Budget + blended CPA ────────────────────────────────────────
    daily_target = sum(
        v
        for c in snapshot.campaigns
        if (v := _campaign_daily_budget(c)) is not None
        and c.operation_status == "ENABLE"
    )
    budget_bits = [f"💰 Daily budget: ${t['spend']:.2f}"]
    if daily_target > 0:
        pct = t["spend"] / daily_target * 100.0
        budget_bits[0] += f" / ${daily_target:.2f} ({pct:.0f}%)"
    cpa_text = f"${t['cpa']:.2f} blended CPA" if t["conversion"] else "no conversions"
    budget_bits.append(cpa_text)

    if prior_daily:
        prior_cpas = [totals(s)["cpa"] for s in prior_daily if totals(s)["cpa"] > 0]
        if prior_cpas and t["cpa"] > 0:
            avg = sum(prior_cpas) / len(prior_cpas)
            delta = (t["cpa"] - avg) / avg * 100.0
            arrow = "📈" if delta >= 0 else "📉"
            budget_bits.append(f"({arrow} {delta:+.1f}% vs {len(prior_cpas)}d avg)")

    lines.append(" · ".join(budget_bits))

    # ── Signals (fatigue, CTR drop, 3-2-1, new ads) ─────────────────
    today_dt = datetime.combine(today, datetime.min.time(), tzinfo=SGT)
    signals = _detect_signals(
        snapshot,
        prior_daily=prior_daily,
        today=today_dt,
        display_names=display_names,
    )
    if signals:
        lines.append("")
        lines.append("⚠️ Signals")
        lines.extend(signals)

    # ── Campaign Performance ────────────────────────────────────────
    if by_campaign:
        lines.append("")
        lines.append("📋 Campaign Performance")
        for cid, row in sorted(by_campaign.items(), key=lambda kv: kv[1]["spend"], reverse=True):
            camp = campaigns_by_id.get(cid)
            name = (camp.campaign_name if camp else None) or cid
            budget = _campaign_daily_budget(camp) if camp else None
            budget_str = ""
            if budget:
                pct = row["spend"] / budget * 100.0
                budget_str = f" / ${budget:.2f} ({pct:.0f}%)"
            conv_str = (
                f" · {int(row['conversion'])} conv · ${row['cpa']:.2f} CPA"
                if row["conversion"]
                else f" · {int(row['conversion'])} conv"
            )
            lines.append(
                f"  {name}: ${row['spend']:.2f}{budget_str} · "
                f"{int(row['clicks'])} clicks{conv_str}"
            )

    # ── Converting ad groups ────────────────────────────────────────
    converting = [
        (gid, row) for gid, row in by_adgroup.items() if row["conversion"] > 0
    ]
    if converting:
        lines.append("")
        lines.append("🎯 Converting ad groups")
        for gid, row in sorted(converting, key=lambda kv: kv[1]["conversion"], reverse=True):
            group = adgroups_by_id.get(gid)
            name = (group.adgroup_name if group else None) or gid
            lines.append(
                f"  {name} — {int(row['conversion'])} conv, ${row['spend']:.2f}"
            )

    # ── Ad Performance (grouped by ad group) ────────────────────────
    active_ads = {ad.ad_id for ad in snapshot.ads if ad.operation_status == "ENABLE"}
    ad_to_group = {ad.ad_id: ad.adgroup_id for ad in snapshot.ads}
    group_rows: dict[str, list] = {}
    for m in snapshot.metrics:
        if m.ad_id not in active_ads:
            continue
        gid = ad_to_group.get(m.ad_id) or "(no adgroup)"
        group_rows.setdefault(gid, []).append(m)

    if group_rows:
        lines.append("")
        lines.append("📝 Ad Performance")
        # Sort ad groups by total spend descending
        ordered = sorted(
            group_rows.items(),
            key=lambda kv: sum(m.spend for m in kv[1]),
            reverse=True,
        )
        for gid, ms in ordered:
            group = adgroups_by_id.get(gid)
            gname = (group.adgroup_name if group else None) or gid
            lines.append(f"  {gname}")
            for m in sorted(ms, key=lambda x: x.spend, reverse=True):
                label = display_names.get(m.ad_id) or m.ad_id
                hook = (
                    f"hook {m.hook_retention * 100:.0f}%"
                    if m.hook_retention is not None
                    else "hook —"
                )
                conv_str = (
                    f" · {m.conversion} conv · ${m.cost_per_conversion:.2f} CPA"
                    if m.conversion and m.cost_per_conversion is not None
                    else f" · {m.conversion} conv"
                )
                lines.append(
                    f"    {label}: ${m.spend:.2f} · "
                    f"{m.clicks} clk · {m.ctr:.2f}% CTR · {hook}{conv_str}"
                )

    # ── Creative Performance ────────────────────────────────────────
    if by_creative:
        lines.append("")
        lines.append("🎨 Creative Performance")
        for label, row in sorted(
            by_creative.items(), key=lambda kv: kv[1]["spend"], reverse=True
        ):
            conv_str = (
                f" · {int(row['conversion'])} conv · ${row['cpa']:.2f} CPA"
                if row["conversion"]
                else f" · {int(row['conversion'])} conv"
            )
            lines.append(
                f"  {label}: ${row['spend']:.2f} · "
                f"{int(row['clicks'])} clicks{conv_str}"
            )

    # ── MTD Pacing ──────────────────────────────────────────────────
    if mtd:
        days_in_month = calendar.monthrange(today.year, today.month)[1]
        day_of_month = today.day
        expected_pct = day_of_month / days_in_month * 100.0

        mtd_spend = sum(row["spend"] for row in mtd.values())
        mtd_conv = sum(int(row["conversion"]) for row in mtd.values())
        mtd_cpa = mtd_spend / mtd_conv if mtd_conv else 0.0

        monthly_target = sum(
            (v * days_in_month)
            for c in snapshot.campaigns
            if (v := _campaign_daily_budget(c)) is not None
            and c.operation_status == "ENABLE"
        )

        lines.append("")
        lines.append(f"📅 MTD Pacing (day {day_of_month}/{days_in_month})")
        if monthly_target > 0:
            actual_pct = mtd_spend / monthly_target * 100.0
            icon = _pacing_icon(actual_pct, expected_pct)
            lines.append(
                f"  {icon} ${mtd_spend:.2f} / ${monthly_target:.2f} "
                f"({actual_pct:.0f}% spent, {expected_pct:.0f}% expected)"
            )
        else:
            lines.append(f"  ${mtd_spend:.2f} MTD (no monthly target set)")
        cpa_str = f"${mtd_cpa:.2f} blended CPA" if mtd_conv else "no conversions"
        lines.append(f"  {mtd_conv} conv MTD · {cpa_str}")
        for cid, row in sorted(mtd.items(), key=lambda kv: kv[1]["spend"], reverse=True):
            camp = campaigns_by_id.get(cid)
            name = (camp.campaign_name if camp else None) or cid
            budget = _campaign_daily_budget(camp) if camp else None
            if budget:
                monthly = budget * days_in_month
                pct = row["spend"] / monthly * 100.0
                budget_str = f" / ${monthly:.2f} ({pct:.0f}%)"
            else:
                budget_str = ""
            lines.append(
                f"  {name}: ${row['spend']:.2f}{budget_str} · "
                f"{int(row['conversion'])} conv"
            )

    return "\n".join(lines)


def run(settings: Settings) -> tuple[Snapshot, str]:
    """Fetch yesterday's data, persist snapshot, return (snapshot, message)."""

    today = datetime.now(SGT).date()
    target = today - timedelta(days=1)
    period_id = target.isoformat()
    snapshot = fetch_snapshot(
        settings,
        cadence="daily",
        period_id=period_id,
        start_date=period_id,
        end_date=period_id,
    )
    save_snapshot(snapshot)

    prior = _load_prior_snapshots(target, days=7)
    month_start = target.replace(day=1).isoformat()
    mtd = fetch_mtd_campaign_totals(settings, month_start=month_start, end_date=period_id)
    registry = load_creative_registry()

    message = build_telegram_summary(
        snapshot,
        prior_daily=prior,
        mtd=mtd,
        today=today,
        registry=registry,
    )
    return snapshot, message
