"""Pydantic schemas for metrics snapshots and supporting types.

All per-ad metrics + hierarchy data we commit to ``.state/`` flow
through these models so the shape stays consistent across daily,
weekly, and monthly cadences.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AdMetadata(BaseModel):
    """Hierarchy + naming data for an ad, pulled from ``/ad/get/``."""

    model_config = ConfigDict(extra="ignore")

    ad_id: str
    ad_name: str | None = None
    adgroup_id: str | None = None
    campaign_id: str | None = None
    operation_status: str | None = None
    create_time: str | None = None


class AdGroupMetadata(BaseModel):
    """Ad group config — notably ``optimization_event`` + ``pixel_id``.

    This is where we answer "what do our conversions refer to": the
    ``optimization_event`` field tells us which pixel event the group
    is optimizing for (e.g. ``ON_WEB_FORM`` ≈ SingPass form submit).
    """

    model_config = ConfigDict(extra="ignore")

    adgroup_id: str
    adgroup_name: str | None = None
    campaign_id: str | None = None
    operation_status: str | None = None
    optimization_goal: str | None = None
    optimization_event: str | None = None
    secondary_optimization_event: str | None = None
    billing_event: str | None = None
    pixel_id: str | None = None
    budget: float | None = None
    budget_mode: str | None = None
    placement_type: str | None = None


class CampaignMetadata(BaseModel):
    """Campaign-level config."""

    model_config = ConfigDict(extra="ignore")

    campaign_id: str
    campaign_name: str | None = None
    operation_status: str | None = None
    objective_type: str | None = None
    budget: float | None = None
    budget_mode: str | None = None


class AdMetrics(BaseModel):
    """Aggregated metrics for a single ad over a date range."""

    model_config = ConfigDict(extra="ignore")

    ad_id: str
    spend: float = 0.0
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    cpc: float = 0.0
    cpm: float = 0.0
    conversion: int = 0
    cost_per_conversion: float | None = None
    conversion_rate: float | None = None
    video_play_actions: int = 0
    video_watched_2s: int = 0
    video_watched_6s: int = 0
    video_views_p25: int = 0
    video_views_p50: int = 0
    video_views_p75: int = 0
    video_views_p100: int = 0

    @property
    def computed_cpa(self) -> float | None:
        """Derived CPA (spend / conversions). ``None`` if zero conversions."""

        if self.conversion <= 0:
            return None
        return round(self.spend / self.conversion, 4)


class Snapshot(BaseModel):
    """Top-level snapshot committed per cadence run.

    The ``cadence`` field is ``daily`` / ``weekly`` / ``monthly``; the
    ``period_id`` is the ISO-ish key (``2026-04-20`` / ``2026-W17`` /
    ``2026-04``). ``start_date`` / ``end_date`` are inclusive YYYY-MM-DD
    bounds passed to the reporting API.
    """

    model_config = ConfigDict(extra="ignore")

    cadence: str
    period_id: str
    start_date: str
    end_date: str
    generated_at: str
    advertiser_id: str
    campaigns: list[CampaignMetadata] = Field(default_factory=list)
    adgroups: list[AdGroupMetadata] = Field(default_factory=list)
    ads: list[AdMetadata] = Field(default_factory=list)
    metrics: list[AdMetrics] = Field(default_factory=list)
