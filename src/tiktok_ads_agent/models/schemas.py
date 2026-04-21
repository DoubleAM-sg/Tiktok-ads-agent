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
    """Ad group config — notably ``optimization_event`` / ``external_action``.

    For Lead-Generation / Conversion-to-Website adgroups, the pixel event
    being optimized for usually surfaces in ``external_action`` (or the
    related ``conversion_id``), not ``optimization_event``. We pull both.
    """

    model_config = ConfigDict(extra="ignore")

    adgroup_id: str
    adgroup_name: str | None = None
    campaign_id: str | None = None
    operation_status: str | None = None
    optimization_goal: str | None = None
    optimization_event: str | None = None
    secondary_optimization_event: str | None = None
    external_action: str | None = None
    external_type: str | None = None
    conversion_id: str | None = None
    billing_event: str | None = None
    pixel_id: str | None = None
    budget: float | None = None
    budget_mode: str | None = None
    placement_type: str | None = None
    placement: list[str] = Field(default_factory=list)
    bid_type: str | None = None
    bid_price: float | None = None
    conversion_bid_price: float | None = None


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
    # Audience + fatigue signals (Corey Haines: frequency is fatigue signal #2)
    reach: int = 0
    frequency: float = 0.0
    # Video retention
    video_play_actions: int = 0
    video_watched_2s: int = 0
    video_watched_6s: int = 0
    video_views_p25: int = 0
    video_views_p50: int = 0
    video_views_p75: int = 0
    video_views_p100: int = 0
    # Engagement — TikTok-specific (virality + profile interest)
    likes: int = 0
    comments: int = 0
    shares: int = 0
    follows: int = 0
    profile_visits: int = 0

    @property
    def computed_cpa(self) -> float | None:
        """Derived CPA (spend / conversions). ``None`` if zero conversions."""

        if self.conversion <= 0:
            return None
        return round(self.spend / self.conversion, 4)

    @property
    def hook_retention(self) -> float | None:
        """Share of video plays that stayed past 2 seconds (0.0–1.0)."""

        if self.video_play_actions <= 0:
            return None
        return round(self.video_watched_2s / self.video_play_actions, 4)

    @property
    def is_fatigued(self) -> bool:
        """Corey Haines fatigue threshold — frequency ≥ 3 = seen-and-ignored."""

        return self.frequency >= 3.0


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
