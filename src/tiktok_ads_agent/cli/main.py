"""CLI entry point for the TikTok Ads Agent."""

from __future__ import annotations

import sys

import click
from rich.console import Console

from tiktok_ads_agent.core.client import TikTokAPIError, TikTokClient
from tiktok_ads_agent.core.settings import load_settings
from tiktok_ads_agent.notifications.telegram import send_message

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
    """Probe the TikTok access token by fetching advertiser info.

    Prints ``healthy: ...`` and exits 0 on success, ``expired: ...`` and
    exits 1 if the API rejects the token, or ``error: ...`` and exits 1
    on any other failure. Workflows can grep the output for the literal
    word ``expired`` to decide whether to short-circuit gracefully.
    """

    settings = load_settings()
    client = TikTokClient(settings)
    try:
        info = client.get_advertiser_info()
    except TikTokAPIError as err:
        label = "expired" if err.is_expired_token else "error"
        console.print(f"{label}: {err}")
        sys.exit(1)
    console.print(
        f"healthy: advertiser {info.get('advertiser_id')} '{info.get('name')}' "
        f"status={info.get('status')} currency={info.get('currency')} "
        f"timezone={info.get('timezone')} country={info.get('country')}"
    )


@cli.command()
@click.argument("message")
def notify(message: str) -> None:
    """Send a plain-text message to the configured Telegram chat/topic."""

    send_message(message)
    console.print("sent")


if __name__ == "__main__":
    cli()
