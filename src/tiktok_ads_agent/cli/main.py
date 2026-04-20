"""CLI entry point for the TikTok Ads Agent."""

import click


@click.group()
@click.version_option()
def cli() -> None:
    """Autonomous TikTok Ads management for PickMeALoan."""


@cli.command()
def status() -> None:
    """Print scaffold status and setup checklist progress."""
    click.echo("TikTok Ads Agent — scaffold only. See CLAUDE.md for setup checklist.")


if __name__ == "__main__":
    cli()
