"""Shared building blocks for daily / weekly / monthly reports.

All three cadences pull the same shape of data (campaign + adgroup +
ad metadata, plus per-ad aggregated metrics for a date range) and post
a Telegram summary. This module owns the fetching, joining, and
formatting so the per-cadence modules stay thin.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from tiktok_ads_agent.core.client import TikTokClient
from tiktok_ads_agent.core.settings import Settings
from tiktok_ads_agent.models.schemas import (
    AdGroupMetadata,
    AdMetadata,
    AdMetrics,
    CampaignMetadata,
    Snapshot,
)

# Metrics requested on every report. TikTok rejects unknown fields so
# keep this aligned with Marketing API v1.3 Reporting docs.
METRIC_FIELDS: list[str] = [
    "spend",
    "impressions",
    "clicks",
    "ctr",
    "cpc",
    "cpm",
    "conversion",
    "cost_per_conversion",
    "conversion_rate",
    "real_time_conversion",
    # Fatigue + audience sizing: frequency ≥ 3 is Corey Haines' seen-and-ignored
    "reach",
    "frequency",
    # Video retention
    "video_play_actions",
    "video_watched_2s",
    "video_watched_6s",
    "video_views_p25",
    "video_views_p50",
    "video_views_p75",
    "video_views_p100",
    # TikTok-specific engagement (virality + brand lift leading indicators)
    "likes",
    "comments",
    "shares",
    "follows",
    "profile_visits",
]


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _coerce_int(value: Any) -> int:
    return int(_coerce_float(value))


def _metric_from_row(row: dict[str, Any]) -> AdMetrics:
    """Build an :class:`AdMetrics` from a ``/report/integrated/get/`` row.

    TikTok returns each row as ``{"dimensions": {...}, "metrics": {...}}``.
    All numeric fields come back as strings — coerce explicitly.
    """

    dims = row.get("dimensions", {})
    mets = row.get("metrics", {})
    ad_id = str(dims.get("ad_id", ""))
    spend = _coerce_float(mets.get("spend"))
    conversion = _coerce_int(mets.get("conversion"))
    cpa_raw = mets.get("cost_per_conversion")
    cpa: float | None = _coerce_float(cpa_raw) if cpa_raw not in (None, "", "-") else None
    if cpa == 0.0 and conversion == 0:
        cpa = None
    conv_rate_raw = mets.get("conversion_rate")
    conv_rate: float | None = (
        _coerce_float(conv_rate_raw) if conv_rate_raw not in (None, "", "-") else None
    )
    return AdMetrics(
        ad_id=ad_id,
        spend=spend,
        impressions=_coerce_int(mets.get("impressions")),
        clicks=_coerce_int(mets.get("clicks")),
        ctr=_coerce_float(mets.get("ctr")),
        cpc=_coerce_float(mets.get("cpc")),
        cpm=_coerce_float(mets.get("cpm")),
        conversion=conversion,
        cost_per_conversion=cpa,
        conversion_rate=conv_rate,
        reach=_coerce_int(mets.get("reach")),
        frequency=_coerce_float(mets.get("frequency")),
        video_play_actions=_coerce_int(mets.get("video_play_actions")),
        video_watched_2s=_coerce_int(mets.get("video_watched_2s")),
        video_watched_6s=_coerce_int(mets.get("video_watched_6s")),
        video_views_p25=_coerce_int(mets.get("video_views_p25")),
        video_views_p50=_coerce_int(mets.get("video_views_p50")),
        video_views_p75=_coerce_int(mets.get("video_views_p75")),
        video_views_p100=_coerce_int(mets.get("video_views_p100")),
        likes=_coerce_int(mets.get("likes")),
        comments=_coerce_int(mets.get("comments")),
        shares=_coerce_int(mets.get("shares")),
        follows=_coerce_int(mets.get("follows")),
        profile_visits=_coerce_int(mets.get("profile_visits")),
    )


def fetch_snapshot(
    settings: Settings,
    *,
    cadence: str,
    period_id: str,
    start_date: str,
    end_date: str,
) -> Snapshot:
    """Pull hierarchy + metrics for the given window and build a Snapshot."""

    client = TikTokClient(settings)

    campaigns_payload = client.list_campaigns(page_size=200)
    campaigns = [CampaignMetadata.model_validate(row) for row in campaigns_payload.get("list", [])]

    adgroups_payload = client.list_adgroups(page_size=200)
    adgroups = [AdGroupMetadata.model_validate(row) for row in adgroups_payload.get("list", [])]

    ads = [AdMetadata.model_validate(row) for row in client.list_ads(page_size=200)]

    report_payload = client.get_basic_report(
        data_level="AUCTION_AD",
        dimensions=["ad_id"],
        metrics=METRIC_FIELDS,
        start_date=start_date,
        end_date=end_date,
        page_size=200,
    )
    metrics = [_metric_from_row(row) for row in report_payload.get("list", [])]

    return Snapshot(
        cadence=cadence,
        period_id=period_id,
        start_date=start_date,
        end_date=end_date,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        advertiser_id=settings.tiktok_advertiser_id,
        campaigns=campaigns,
        adgroups=adgroups,
        ads=ads,
        metrics=metrics,
    )


def totals(snapshot: Snapshot) -> dict[str, float]:
    """Aggregate metrics across all ads. CPA is derived, not summed."""

    spend = sum(m.spend for m in snapshot.metrics)
    impressions = sum(m.impressions for m in snapshot.metrics)
    clicks = sum(m.clicks for m in snapshot.metrics)
    conversion = sum(m.conversion for m in snapshot.metrics)
    ctr = (clicks / impressions * 100.0) if impressions else 0.0
    cpa = (spend / conversion) if conversion else 0.0
    return {
        "spend": round(spend, 2),
        "impressions": float(impressions),
        "clicks": float(clicks),
        "conversion": float(conversion),
        "ctr": round(ctr, 3),
        "cpa": round(cpa, 2),
    }


def ad_name_map(snapshot: Snapshot) -> dict[str, str]:
    """Map ``ad_id`` → ``ad_name`` for pretty-printing."""

    return {ad.ad_id: (ad.ad_name or ad.ad_id) for ad in snapshot.ads}


def short_label(name: str | None, max_len: int = 32) -> str:
    """Condense a verbose ad name into a table-friendly label.

    TikTok ad names in this account are the full caption (multi-line,
    emoji- and hashtag-heavy). For dense sections like Creative /
    Ad Performance we want something that fits in one column, so take
    the first line and hard-truncate with an ellipsis.
    """

    if not name:
        return "(unnamed)"
    first = name.splitlines()[0].strip()
    if len(first) <= max_len:
        return first
    return first[: max_len - 1].rstrip() + "…"


def display_name_map(
    snapshot: Snapshot,
    *,
    registry: dict[str, dict[str, Any]] | None = None,
    max_len: int = 32,
) -> dict[str, str]:
    """Map ``ad_id`` → user-facing label for reports.

    Consults the creative registry first (``.state/creative_registry.json``);
    falls back to a truncated ``ad_name``. Used by every table in the
    daily/weekly reports so relabelling an ad updates every section at once.
    """

    registry = registry or {}
    names: dict[str, str] = {}
    for ad in snapshot.ads:
        entry = registry.get(ad.ad_id)
        if entry and entry.get("label"):
            names[ad.ad_id] = str(entry["label"])
        else:
            names[ad.ad_id] = short_label(ad.ad_name, max_len)
    return names


def _blank_agg() -> dict[str, float]:
    return {"spend": 0.0, "impressions": 0, "clicks": 0, "conversion": 0}


def _finalise_agg(bucket: dict[str, dict[str, float]]) -> None:
    """Round spend and derive CPA in place for every row."""

    for row in bucket.values():
        conv = row["conversion"]
        row["cpa"] = round(row["spend"] / conv, 2) if conv else 0.0
        row["spend"] = round(row["spend"], 2)


def aggregate_by_campaign(snapshot: Snapshot) -> dict[str, dict[str, float]]:
    """Aggregate ad-level metrics up to campaign level."""

    parent = {ad.ad_id: ad.campaign_id for ad in snapshot.ads if ad.campaign_id}
    bucket: dict[str, dict[str, float]] = {}
    for m in snapshot.metrics:
        cid = parent.get(m.ad_id)
        if not cid:
            continue
        row = bucket.setdefault(cid, _blank_agg())
        row["spend"] += m.spend
        row["impressions"] += m.impressions
        row["clicks"] += m.clicks
        row["conversion"] += m.conversion
    _finalise_agg(bucket)
    return bucket


def aggregate_by_adgroup(snapshot: Snapshot) -> dict[str, dict[str, float]]:
    """Aggregate ad-level metrics up to ad group level."""

    parent = {ad.ad_id: ad.adgroup_id for ad in snapshot.ads if ad.adgroup_id}
    bucket: dict[str, dict[str, float]] = {}
    for m in snapshot.metrics:
        gid = parent.get(m.ad_id)
        if not gid:
            continue
        row = bucket.setdefault(gid, _blank_agg())
        row["spend"] += m.spend
        row["impressions"] += m.impressions
        row["clicks"] += m.clicks
        row["conversion"] += m.conversion
    _finalise_agg(bucket)
    return bucket


def aggregate_by_creative(
    snapshot: Snapshot,
    *,
    registry: dict[str, dict[str, Any]] | None = None,
    label_len: int = 32,
) -> dict[str, dict[str, float]]:
    """Aggregate by display label (registry-first, fallback to truncated name).

    Two ad_ids that share a registry label collapse into one row — which
    is the point: the creative-registry lets the user declare "these two
    ads are the same creative angle" even if TikTok sees them as
    separate ad objects.
    """

    labels = display_name_map(snapshot, registry=registry, max_len=label_len)
    bucket: dict[str, dict[str, float]] = {}
    for m in snapshot.metrics:
        lbl = labels.get(m.ad_id, m.ad_id)
        row = bucket.setdefault(lbl, _blank_agg())
        row["spend"] += m.spend
        row["impressions"] += m.impressions
        row["clicks"] += m.clicks
        row["conversion"] += m.conversion
    _finalise_agg(bucket)
    return bucket


def fetch_mtd_campaign_totals(
    settings: Settings, *, month_start: str, end_date: str
) -> dict[str, dict[str, float]]:
    """Pull month-to-date campaign totals via the reporting API.

    Used by the daily report's MTD Pacing section. A separate call
    rather than summing local daily snapshots because we usually only
    have a handful of prior snapshots on disk.
    """

    client = TikTokClient(settings)
    payload = client.get_basic_report(
        data_level="AUCTION_CAMPAIGN",
        dimensions=["campaign_id"],
        metrics=["spend", "clicks", "conversion"],
        start_date=month_start,
        end_date=end_date,
        page_size=200,
    )
    bucket: dict[str, dict[str, float]] = {}
    for row in payload.get("list", []):
        dims = row.get("dimensions", {})
        mets = row.get("metrics", {})
        cid = str(dims.get("campaign_id", ""))
        if not cid:
            continue
        bucket[cid] = {
            "spend": _coerce_float(mets.get("spend")),
            "clicks": _coerce_int(mets.get("clicks")),
            "conversion": _coerce_int(mets.get("conversion")),
        }
    _finalise_agg(bucket)
    return bucket
