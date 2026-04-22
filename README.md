# TikTok Ads Agent

Autonomous TikTok Ads management for PickMeALoan (PMAL). Sister project to [meta-ads-agent](https://github.com/DoubleAM-sg/Meta-ads-agent). Daily pacing reports, weekly creative optimization with auto-pause, monthly strategic analysis, Telegram delivery.

**Status: setup phase.** Awaiting TikTok developer app approval, OAuth bootstrap, SG financial pre-qualification, pixel installation. See [CLAUDE.md](CLAUDE.md) for checklist and strategic context.

## Quickstart (once setup complete)

```bash
pip install -e ".[dev]"
cp .env.example .env  # then fill in credentials
tiktok-ads --help
```

## Interfaces

- **CLI:** `tiktok-ads` (Click)
- **API:** FastAPI app (`uvicorn tiktok_ads_agent.api.app:app`)
- **Chat:** Conversational agent powered by Claude with tool use

## Cadences

- **Daily** — pacing, early warnings, delivery issues (no auto-pause)
- **Weekly** — CPA ranking, auto-pause underperformers, next-batch recommendations
- **Monthly** — MoM comparison, audience shifts, strategic recommendations

## Related

- [meta-ads-agent](https://github.com/DoubleAM-sg/Meta-ads-agent) — sister project, Meta Ads version
