# TikTok Ads Agent

Autonomous TikTok Ads management for **PickMeALoan (PMAL)**, a Singapore personal-loan matching platform. Sister project to [meta-ads-agent](https://github.com/DoubleAM-sg/Meta-ads-agent); same operational model, adapted for TikTok's API, terminology, and creative norms.

## Status — scaffold only, not yet operational

This repo is in the setup phase. The package layout, CLI entry point, and conventions are in place, but the report, notification, and API logic has not been implemented yet. **Running the agent will not produce daily, weekly, or monthly updates until the items below are done.**

### What exists today

- Package scaffold under `src/tiktok_ads_agent/` (`core`, `models`, `api`, `cli`, `agent`, `reports`, `creative`, `notifications`, `state`) — each module is an empty stub awaiting implementation
- `tiktok-ads` CLI entry point with a single `status` command
- `.env.example` listing the credentials the agent will eventually need
- `.state/` and `creative-reports/manual-upload/` directories for persistence and manual creative fallback
- Strategic context, terminology map, pausing rules, and compliance guardrails in [CLAUDE.md](CLAUDE.md)

### What is blocked on external setup

- [ ] TikTok for Business account (business.tiktok.com)
- [ ] TikTok Ads Manager account — Singapore region, SGD, Asia/Singapore timezone
- [ ] Self-service developer app approved at https://business-api.tiktok.com/portal (1–2 business days)
- [ ] OAuth bootstrap → long-lived access + refresh tokens in `.env` (`scripts/tiktok-auth-bootstrap.py` — currently a placeholder)
- [ ] Singapore financial services pre-qualification in Business Center (5–10 business days, manual TikTok review)
- [ ] TikTok Pixel installed on PMAL site with `SubmitForm` event firing on the loan-matching page

### What still needs to be built in this repo

- `core/` — TikTok Marketing API client wrapper, pydantic-settings config loader
- `models/` — schemas for campaigns, ad groups, ads, metrics
- `reports/daily.py`, `reports/weekly.py`, `reports/monthly.py` — report generators implementing the rules in [CLAUDE.md](CLAUDE.md#optimization-by-cadence)
- `notifications/telegram.py` — Telegram delivery
- `agent/` — Claude-powered chat with tool use
- `api/app.py` — FastAPI app (referenced by docs but not present yet)
- `cli/main.py` — commands for `daily`, `weekly`, `monthly`, `chat`
- A scheduler (cron, systemd timer, or APScheduler) to actually trigger the cadences

Until these land, nothing runs automatically. If you expected a daily Telegram update, that's the reason it didn't arrive.

## Quickstart (once the above is complete)

```bash
pip install -e ".[dev]"
cp .env.example .env  # fill in TikTok, Anthropic, Telegram credentials
tiktok-ads --help
```

## Planned interfaces

- **CLI** — `tiktok-ads daily | weekly | monthly | chat` (Click)
- **API** — FastAPI app at `uvicorn tiktok_ads_agent.api.app:app`
- **Chat** — conversational agent powered by Claude with tool use
- **Scheduler** — cron or equivalent, driving the three cadences on Asia/Singapore time

## Cadences (design; not yet implemented)

- **Daily** — pacing vs budget, delivery issues, CTR-drop flags; no auto-pause
- **Weekly** — CPA ranking, auto-pause rules, next-batch recommendations, 3-2-1 creative pipeline
- **Monthly** — MoM comparison, audience shifts, angle retrospective, strategic recommendations

Full rules, pausing thresholds, compliance vocabulary, and the TikTok↔Meta terminology map live in [CLAUDE.md](CLAUDE.md).

## Related

- [meta-ads-agent](https://github.com/DoubleAM-sg/Meta-ads-agent) — sister project, Meta Ads version. Read its CLAUDE.md for the full Corey Haines fatigue framework, message-market-match playbook, and learning-engine design that are not reproduced here.
