"""CLI entry point for the TikTok Ads Agent."""

from __future__ import annotations

import sys

import click
from rich.console import Console

from tiktok_ads_agent.core.client import TikTokAPIError, TikTokClient
from tiktok_ads_agent.core.settings import load_settings
from tiktok_ads_agent.notifications.telegram import send_message
from tiktok_ads_agent.reports import daily as daily_report
from tiktok_ads_agent.reports import monthly as monthly_report
from tiktok_ads_agent.reports import weekly as weekly_report
from tiktok_ads_agent.state.persistence import init_state

console = Console()


@click.group()
@click.version_option()
def cli() -> None:
    """Autonomous TikTok Ads management for PickMeALoan."""


@cli.command()
def status() -> None:
    """Print scaffold status and setup checklist progress."""

    console.print("TikTok Ads Agent — scaffold. See CLAUDE.md for setup checklist.")


@cli.command()
def health() -> None:
    """Probe the TikTok access token by listing campaigns.

    Uses ``/campaign/get/`` (Ads Management scope) rather than
    ``/advertiser/info/`` (Ad Account Management) because the former is
    granted by the default OAuth consent and also exercises the scope
    the weekly CPA ranking will depend on.

    Prints ``healthy: ...`` and exits 0 on success, ``expired: ...`` and
    exits 1 if the API rejects the token, or ``error: ...`` and exits 1
    on any other failure. Workflows can grep the output for the literal
    word ``expired`` to decide whether to short-circuit gracefully.
    """

    settings = load_settings()
    client = TikTokClient(settings)
    try:
        data = client.list_campaigns(page_size=1)
    except TikTokAPIError as err:
        label = "expired" if err.is_expired_token else "error"
        console.print(f"{label}: {err}")
        sys.exit(1)
    page_info = data.get("page_info", {})
    total = page_info.get("total_number", 0)
    first = (data.get("list") or [{}])[0]
    console.print(
        f"healthy: advertiser {settings.tiktok_advertiser_id} has {total} campaigns "
        f"(first: {first.get('campaign_name') or '<none>'} "
        f"status={first.get('operation_status') or '-'})"
    )


@cli.command()
@click.argument("message")
def notify(message: str) -> None:
    """Send a plain-text message to the configured Telegram chat/topic."""

    send_message(message)
    console.print("sent")


@cli.group()
def state() -> None:
    """Persistent state helpers."""


@state.command("init")
def state_init() -> None:
    """Create ``.state/`` directory tree + empty cumulative JSON files."""

    created = init_state()
    if created:
        for path in created:
            console.print(f"created {path}")
    else:
        console.print("state already initialised")


@cli.group()
def report() -> None:
    """Daily, weekly, monthly cadence reports."""


def _run_and_notify(cadence: str) -> None:
    settings = load_settings()
    runner = {
        "daily": daily_report.run,
        "weekly": weekly_report.run,
        "monthly": monthly_report.run,
    }[cadence]
    try:
        snapshot, message = runner(settings)
    except TikTokAPIError as err:
        label = "expired" if err.is_expired_token else "error"
        console.print(f"{label}: {err}")
        sys.exit(1)
    send_message(message)
    console.print(f"{cadence} report sent — snapshot {snapshot.period_id}")


@report.command("daily")
def report_daily() -> None:
    """Run yesterday's daily report and post to Telegram."""

    _run_and_notify("daily")


@report.command("weekly")
def report_weekly() -> None:
    """Run last complete ISO week's report and post to Telegram."""

    _run_and_notify("weekly")


@report.command("monthly")
def report_monthly() -> None:
    """Run previous calendar month's report and post to Telegram."""

    _run_and_notify("monthly")


if __name__ == "__main__":
    cli()
