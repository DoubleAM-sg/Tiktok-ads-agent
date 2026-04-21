"""One-shot mutation: exclude Pangle from ad group placements.

Pangle is TikTok's third-party app network. On finance accounts it
can burn budget on low-quality impressions, so the default
``PLACEMENT_TYPE_AUTOMATIC`` (which includes Pangle) can waste spend.
Switching the ad group to ``PLACEMENT_TYPE_NORMAL`` with an explicit
placement list removes Pangle from eligibility.

Smart+ / Upgraded Smart Plus ad groups reject this update via the
Marketing API (TikTok manages placements automatically there). We
detect that response and record it as a ``skipped_smart_plus`` result
instead of treating it as a failure.

This module is idempotent — it skips ad groups already on a manual
placement that doesn't include ``PLACEMENT_PANGLE``.
"""

from __future__ import annotations

from typing import NamedTuple

from tiktok_ads_agent.core.client import TikTokAPIError, TikTokClient
from tiktok_ads_agent.core.settings import Settings
from tiktok_ads_agent.models.schemas import AdGroupMetadata

# The placements we keep. TIKTOK covers For-You + Search + Lemon8 inside
# the TikTok app and is what we actually want for a finance audience.
KEEP_PLACEMENTS = ["PLACEMENT_TIKTOK"]

SMART_PLUS_MARKERS = ("smart plus", "smart+", "upgraded smart")


class PlacementUpdateResult(NamedTuple):
    adgroup_id: str
    adgroup_name: str
    # "updated" | "already_correct" | "skipped_smart_plus" | "failed"
    action: str
    detail: str


def _needs_update(adgroup: AdGroupMetadata) -> bool:
    """True if the adgroup is on AUTOMATIC or its manual list still allows Pangle."""

    if (adgroup.placement_type or "") != "PLACEMENT_TYPE_NORMAL":
        return True
    if "PLACEMENT_PANGLE" in (adgroup.placements or []):
        return True
    # Normal + non-Pangle list already — leave alone regardless of which
    # placements are in it (user may have intentionally added more).
    return False


def exclude_pangle(
    settings: Settings, *, adgroup_id: str | None = None
) -> list[PlacementUpdateResult]:
    """Apply Pangle exclusion to one or all active ad groups.

    Parameters
    ----------
    adgroup_id:
        If given, update just that ad group. Otherwise iterate every ad
        group with ``operation_status == "ENABLE"``.
    """

    client = TikTokClient(settings)
    payload = client.list_adgroups(page_size=200)
    adgroups_raw = payload.get("list", [])
    adgroups = [AdGroupMetadata.model_validate(row) for row in adgroups_raw]

    if adgroup_id is not None:
        adgroups = [g for g in adgroups if g.adgroup_id == adgroup_id]
    else:
        adgroups = [g for g in adgroups if g.operation_status == "ENABLE"]

    results: list[PlacementUpdateResult] = []
    for group in adgroups:
        name = group.adgroup_name or group.adgroup_id
        if not _needs_update(group):
            results.append(
                PlacementUpdateResult(
                    adgroup_id=group.adgroup_id,
                    adgroup_name=name,
                    action="already_correct",
                    detail=(f"placement_type={group.placement_type} placements={group.placements}"),
                )
            )
            continue
        try:
            client.update_adgroup_placements(
                adgroup_id=group.adgroup_id,
                placements=KEEP_PLACEMENTS,
            )
        except TikTokAPIError as err:
            lowered = err.message.lower()
            is_smart_plus = any(marker in lowered for marker in SMART_PLUS_MARKERS)
            results.append(
                PlacementUpdateResult(
                    adgroup_id=group.adgroup_id,
                    adgroup_name=name,
                    action="skipped_smart_plus" if is_smart_plus else "failed",
                    detail=str(err),
                )
            )
            continue
        results.append(
            PlacementUpdateResult(
                adgroup_id=group.adgroup_id,
                adgroup_name=name,
                action="updated",
                detail=f"placement → {KEEP_PLACEMENTS}",
            )
        )
    return results


def format_telegram_summary(results: list[PlacementUpdateResult]) -> str:
    """Build the Telegram message for a Pangle-exclusion run."""

    if not results:
        return "🛠 Pangle exclusion — no active ad groups found."

    updated = [r for r in results if r.action == "updated"]
    skipped = [r for r in results if r.action == "already_correct"]
    smart_plus = [r for r in results if r.action == "skipped_smart_plus"]
    failed = [r for r in results if r.action == "failed"]

    lines = [
        f"🛠 Pangle exclusion run — {len(results)} ad group(s) checked",
        f"  ✓ updated: {len(updated)}",
        f"  ⏭ already correct: {len(skipped)}",
        f"  🤖 Smart+ (placement managed by TikTok): {len(smart_plus)}",
        f"  ✗ failed: {len(failed)}",
    ]
    for r in updated:
        lines.append(f"    · {r.adgroup_name} → TikTok-only")
    for r in smart_plus:
        lines.append(f"    · {r.adgroup_name} — Smart+, no manual placement")
    for r in failed:
        lines.append(f"    · {r.adgroup_name} FAILED: {r.detail}")
    return "\n".join(lines)
