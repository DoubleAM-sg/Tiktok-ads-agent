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

    def list_ads(self, page_size: int = 200) -> list[dict[str, Any]]:
        """List all ads (paged). Returns the flattened ``list`` array.

        Pages through ``/ad/get/`` until exhausted. Fields selected are
        what the cadence reports need for name + hierarchy mapping.

        ``filtering.primary_status=STATUS_ALL`` is passed explicitly
        because TikTok's default for ``/ad/get/`` is ``STATUS_NOT_DELETE``,
        which also hides some Spark-Ad / appeal-under-review objects we
        need to see in the snapshot to stay in sync with the Ads Manager
        UI. Callers can filter afterwards if they only want ENABLE ads.
        """

        fields = [
            "ad_id",
            "ad_name",
            "adgroup_id",
            "campaign_id",
            "operation_status",
            "secondary_status",
            "create_time",
            "modify_time",
        ]
        all_rows: list[dict[str, Any]] = []
        page = 1
        while True:
            params = {
                "advertiser_id": self.settings.tiktok_advertiser_id,
                "page": page,
                "page_size": page_size,
                "fields": json.dumps(fields),
                "filtering": json.dumps({"primary_status": "STATUS_ALL"}),
            }
            payload = self._request("GET", "/ad/get/", params=params)
            data = payload["data"]
            all_rows.extend(data.get("list", []))
            page_info = data.get("page_info", {})
            if page >= int(page_info.get("total_page", 1)):
                break
            page += 1
        return all_rows

    def get_ads_by_ids(self, ad_ids: list[str]) -> list[dict[str, Any]]:
        """Look up specific ads by id, bypassing the default listing scope.

        Distinct from :meth:`list_ads` because TikTok's listing endpoint
        silently drops some objects (Spark Ads authored under a different
        identity, appeal-under-review entries, cross-BC ads). Calling
        ``/ad/get/`` with ``filtering.ad_ids`` forces the API to tell us
        whether it recognises each id at all under the current token.
        """

        fields = [
            "ad_id",
            "ad_name",
            "adgroup_id",
            "campaign_id",
            "operation_status",
            "secondary_status",
            "create_time",
            "modify_time",
        ]
        params = {
            "advertiser_id": self.settings.tiktok_advertiser_id,
            "page": 1,
            "page_size": max(len(ad_ids), 1),
            "fields": json.dumps(fields),
            "filtering": json.dumps(
                {"primary_status": "STATUS_ALL", "ad_ids": ad_ids}
            ),
        }
        payload = self._request("GET", "/ad/get/", params=params)
        data = payload["data"]
        rows: list[dict[str, Any]] = data.get("list", [])
        return rows

    def list_adgroups(self, page_size: int = 50) -> dict[str, Any]:
        """List ad groups — exposes ``optimization_event`` + ``pixel_id``.

        This is where TikTok stores which pixel event a campaign is
        optimizing for, which is the cleanest way to answer "what do our
        conversions refer to".
        """

        params = {
            "advertiser_id": self.settings.tiktok_advertiser_id,
            "page": 1,
            "page_size": page_size,
            "fields": json.dumps(
                [
                    "adgroup_id",
                    "adgroup_name",
                    "campaign_id",
                    "operation_status",
                    "optimization_goal",
                    "optimization_event",
                    "secondary_optimization_event",
                    "conversion_id",
                    "custom_conversion_id",
                    "pixel_id",
                    "billing_event",
                    "budget",
                    "budget_mode",
                    "placement_type",
                    "placements",
                    "bid_type",
                    "bid_price",
                    "conversion_bid_price",
                ]
            ),
        }
        payload = self._request("GET", "/adgroup/get/", params=params)
        data: dict[str, Any] = payload["data"]
        return data

    def update_adgroup_placements(
        self,
        *,
        adgroup_id: str,
        placements: list[str],
    ) -> dict[str, Any]:
        """Switch an adgroup to manual placement and whitelist ``placements``.

        TikTok's default ``PLACEMENT_TYPE_AUTOMATIC`` includes Pangle
        (external app network) which typically spends cheap and converts
        poorly for finance. Setting ``PLACEMENT_TYPE_NORMAL`` + an explicit
        placement list turns Pangle off.
        """

        body = {
            "advertiser_id": self.settings.tiktok_advertiser_id,
            "adgroup_id": adgroup_id,
            "placement_type": "PLACEMENT_TYPE_NORMAL",
            "placements": placements,
        }
        payload = self._request("POST", "/adgroup/update/", json_body=body)
        data: dict[str, Any] = payload.get("data") or {}
        return data

    def list_custom_audiences(self, page_size: int = 100) -> list[dict[str, Any]]:
        """List custom audiences (for LAL/seed targeting of new adgroups).

        Requires "Audience Management" scope — not guaranteed to be in the
        current token grant. Raises :class:`TikTokAPIError` with code 40001
        if the scope is missing; callers should handle that gracefully.
        """

        all_rows: list[dict[str, Any]] = []
        page = 1
        while True:
            params = {
                "advertiser_id": self.settings.tiktok_advertiser_id,
                "page": page,
                "page_size": page_size,
            }
            payload = self._request("GET", "/dmp/custom_audience/list/", params=params)
            data = payload["data"]
            all_rows.extend(data.get("list", []))
            page_info = data.get("page_info", {})
            if page >= int(page_info.get("total_page", 1)):
                break
            page += 1
        return all_rows

    def get_basic_report(
        self,
        *,
        data_level: str,
        dimensions: list[str],
        metrics: list[str],
        start_date: str,
        end_date: str,
        page_size: int = 100,
        ad_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Pull an aggregated synchronous report.

        ``data_level`` is one of AUCTION_ADVERTISER | AUCTION_CAMPAIGN |
        AUCTION_ADGROUP | AUCTION_AD. Dates are YYYY-MM-DD in the
        advertiser's timezone.

        Pass ``ad_ids`` to force TikTok to return rows for a specific
        ad_id set, including deleted ads. The default behaviour of
        ``/report/integrated/get/`` is to hide ads whose
        ``secondary_status`` is ``AD_STATUS_DELETE`` — which drops
        historical conversion data for the reporting window the moment
        an ad gets removed. Passing the full known id list from
        :meth:`list_ads` with ``primary_status=STATUS_ALL`` preserves
        yesterday's truth regardless of today's status.
        """

        params = {
            "advertiser_id": self.settings.tiktok_advertiser_id,
            "report_type": "BASIC",
            "data_level": data_level,
            "dimensions": json.dumps(dimensions),
            "metrics": json.dumps(metrics),
            "start_date": start_date,
            "end_date": end_date,
            "page": 1,
            "page_size": page_size,
        }
        if ad_ids:
            params["filtering"] = json.dumps(
                [
                    {
                        "field_name": "ad_ids",
                        "filter_type": "IN",
                        "filter_value": json.dumps(ad_ids),
                    }
                ]
            )
        payload = self._request("GET", "/report/integrated/get/", params=params)
        data: dict[str, Any] = payload["data"]
        return data
