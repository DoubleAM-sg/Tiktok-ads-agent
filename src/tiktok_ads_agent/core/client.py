"""Thin TikTok Marketing API v1.3 client.

Only covers what's needed to verify secrets + power health checks for now.
Richer coverage (insights, pause/activate, creative) will land as we build
out the cadence reports.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from tiktok_ads_agent.core.settings import Settings

EXPIRED_TOKEN_CODES = {40100, 40101, 40105}


class TikTokAPIError(Exception):
    """Raised when the TikTok API returns a non-zero ``code`` field."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"TikTok API error {code}: {message}")
        self.code = code
        self.message = message

    @property
    def is_expired_token(self) -> bool:
        return self.code in EXPIRED_TOKEN_CODES


class TikTokClient:
    """Minimal REST wrapper; uses ``Access-Token`` header auth."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _headers(self) -> dict[str, str]:
        return {
            "Access-Token": self.settings.tiktok_access_token,
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.settings.tiktok_base_url}{path}"
        with httpx.Client(timeout=30.0) as client:
            resp = client.request(
                method,
                url,
                headers=self._headers(),
                params=params,
                json=json_body,
            )
        resp.raise_for_status()
        payload: dict[str, Any] = resp.json()
        if payload.get("code") != 0:
            raise TikTokAPIError(
                code=int(payload.get("code", -1)),
                message=str(payload.get("message", "unknown")),
            )
        return payload

    def get_advertiser_info(self) -> dict[str, Any]:
        """Fetch advertiser metadata for the configured advertiser ID.

        Requires "Ad Account Management" scope. If the token lacks it,
        prefer :meth:`list_campaigns` for a health probe.
        """

        params = {
            "advertiser_ids": json.dumps([self.settings.tiktok_advertiser_id]),
            "fields": json.dumps(
                ["advertiser_id", "name", "status", "currency", "timezone", "country"]
            ),
        }
        payload = self._request("GET", "/advertiser/info/", params=params)
        rows: list[dict[str, Any]] = payload["data"]["list"]
        if not rows:
            raise TikTokAPIError(
                code=-1,
                message=f"no advertiser found for id {self.settings.tiktok_advertiser_id}",
            )
        return rows[0]

    def list_campaigns(self, page_size: int = 1) -> dict[str, Any]:
        """List campaigns under the configured advertiser.

        Used as the health probe since "Ads Management" scope is granted
        by the default OAuth consent and also covers the endpoints weekly
        CPA ranking will call.
        """

        params = {
            "advertiser_id": self.settings.tiktok_advertiser_id,
            "page": 1,
            "page_size": page_size,
            "fields": json.dumps(
                [
                    "campaign_id",
                    "campaign_name",
                    "operation_status",
                    "objective_type",
                    "budget",
                    "budget_mode",
                ]
            ),
        }
        payload = self._request("GET", "/campaign/get/", params=params)
        data: dict[str, Any] = payload["data"]
        return data
