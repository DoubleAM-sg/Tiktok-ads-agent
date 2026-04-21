# CLAUDE.md

## Project

**TikTok Ads Agent** — Autonomous TikTok Ads agent for PickMeALoan (PMAL, Singapore personal loan platform). Sister project to meta-ads-agent; same operational model adapted for TikTok. Three cadences (daily/weekly/monthly) delivered via Telegram, persistent state under `.state/`.

**Core Value:** Autonomous monitoring and creative optimization on TikTok — surface what works, pause what doesn't, recommend next creative batch.

## Setup Status

Scaffolded from meta-ads-agent patterns. Before live operation:

- [ ] TikTok for Business account (business.tiktok.com)
- [ ] TikTok Ads Manager account — Singapore region, SGD, Asia/Singapore timezone
- [ ] Self-service developer app approved at https://business-api.tiktok.com/portal (1-2 business day approval)
- [ ] App ID + Secret copied to `.env`
- [ ] OAuth bootstrap: visit `https://business-api.tiktok.com/portal/auth?app_id=YOUR_APP_ID&state=pmal&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fauth%2Fcallback` → grab `auth_code` from redirect → exchange for long-lived token (`scripts/tiktok-auth-bootstrap.py`, TBD)
- [ ] Singapore financial services pre-qualification in Business Center (5-10 business days, manual TikTok review)
- [ ] TikTok Pixel installed on PMAL site; `SubmitForm` event fires on loan-matching-page
- [ ] `.env` populated from `.env.example`
- [ ] `pip install -e ".[dev]"` run

## Technology Stack

- Python 3.11+, FastAPI, Click, Uvicorn, Pydantic v2, pydantic-settings, Anthropic SDK, Rich, pytest, ruff, mypy (strict)
- `tiktok-business-api-sdk` as the primary TikTok Marketing API client
- Entry point: `tiktok-ads` CLI → `src/tiktok_ads_agent/cli/main.py`

## Conventions

Same as meta-ads-agent: snake_case modules/functions/vars, PascalCase classes, ALL_CAPS enum values, PEP 604 unions (`str | None`), explicit type hints, f-strings, Rich `console.print` for output, module + public function docstrings, ruff `E/F/I/N/W/UP`, line length 100, mypy strict.

## Architecture

Mirrors meta-ads-agent. Layers: `core` (client + settings), `models` (pydantic schemas), `api` (FastAPI routers), `cli` (Click), `agent` (Anthropic chat + tools), `reports` (daily/weekly/monthly), `creative` (Corey Haines analysis), `notifications` (Telegram), `state` (JSON persistence).

### TikTok vs Meta Terminology Map

| Meta | TikTok |
|---|---|
| Ad Set | Ad Group |
| Campaign | Campaign |
| Ad | Ad |
| `daily_budget` (cents) | `budget` (micro-units, 1M = $1) — different unit, watch writes |
| `last_7d` time_range | `TIME_RANGE` preset or custom date range |
| Advantage+ Creative | Automated Creative Optimization (ACO) / Smart Creative |
| AdCreative object | Ad holds creative fields directly |
| `regional_regulated_categories` | Industry category + manual pre-qualification |

## Known Limitations & Learnings

**TikTok API — to verify as we build:**

- Metrics expected reliable: spend, impressions, clicks, CTR, CPC, CPM, conversions, video views (3s/6s/15s/completion), engagement
- Creative text readability: UNKNOWN for Spark Ads / Smart Creative flows. On Meta this returned empty; fall back to manual CSV upload via `creative-reports/manual-upload/` if same issue surfaces
- Frequency granularity and conversion attribution windows: TBD

**Conversion counting (PMAL-specific):**

- Real conversion = SingPass form submit → fires TikTok Pixel `SubmitForm` event on loan-matching-page
- NOT conversions: video views, engagement, profile visits, messaging, link clicks
- Filter aggregations to `SubmitForm` only

**Agent can do:** pacing reports, WoW/MoM comparisons, baseline tracking, underperformer detection, ad lifecycle (pause/activate/CRUD), copy analysis with user-provided copy, next-batch recommendations.

**Agent cannot do:** watch videos / view images (visual feedback out of scope), autonomously create new ads end-to-end (user produces in CapCut/Canva), read ad text if TikTok API blocks it (TBD).

## Optimization by Cadence

### Daily — Early Warning

1. Pacing vs daily budget
2. Flag ads burning budget with 0 SingPass submits (>1x ad group baseline CPA today, 0 conv)
3. Flag delivery stoppage (disapproval, rejection, sudden drop)
4. Flag CTR drop >50% vs 7-day average (fatigue signal)
5. NO auto-pause daily — too noisy
6. 3-2-1 check: 3 active creatives per ad group, note newly launched (<3 days)

### Weekly — Main Optimization

1. Rank ads by CPA (SingPass submits only)
2. Auto-pause:
   - >2x ad group baseline CPA over 7 days with 0 SingPass = PAUSE
   - 7+ days with CTR below benchmark (establish W1-W2 first) = PAUSE
   - CPA >1.5x baseline WITH conversions = FLAG only
   - <3 days old = NEVER pause
   - Last active ad in ad group = NEVER pause
3. Surface winners (best CPA, winning angles)
4. Ask user for creative context if API can't expose it: caption text, video hook (first 3s), format (UGC talking-head, green-screen, product demo), music/sound, CTA
5. Corey Haines analysis when copy provided
6. Recommend next batch — angles to test based on gaps + winners
7. Pipeline 3-2-1: 3 active, 2 in development, 1 proven winner (control; never pause until truly fatigued)

### Monthly — Strategic

1. MoM comparison (spend, conversions, CPA, CTR)
2. Audience performance — shift budget between Smart Targeting / Custom / Retargeting
3. 30-day angle retrospective (which angles consistently won)
4. Budget reallocation recommendations
5. Creative fatigue check (month-1 winners declining?)
6. Funnel diagnosis — high CTR + low conv = post-click (landing page, SingPass friction); low CTR = creative
7. Strategic recommendations via Claude

## Pausing Rules

| Signal | Daily | Weekly |
|---|---|---|
| Spent >1x baseline CPA, 0 conv today | Flag Telegram | — |
| Spent >2x baseline CPA, 0 conv over 7d | — | Auto-pause |
| CTR below benchmark 7+ days | — | Auto-pause |
| CTR dropped >50% vs 7d avg | Flag Telegram | Review |
| CPA >1.5x baseline but has conv | — | Flag only |
| Ad <3 days old | Never | Never |
| Last active ad in group | Never | Never |
| Disapproved / stopped delivering | Alert | — |

## Ad Account Context

- **Product:** PMAL (Singapore personal loan comparison platform)
- **Real conversion:** SingPass form submit, TikTok Pixel `SubmitForm` event on loan-matching-page
- **NOT a conversion:** video views, engagement, profile visits, messaging, link clicks
- **Audiences plan** (TikTok starts fresh, no Meta carry-over): Smart Targeting / broad interest first (TikTok algo works best broad), Custom Audience from Singsaver/Moneysmart rejected-applicant lists → Lookalike, Retargeting once Pixel has 2-4 weeks of traffic
- **Baselines:** None yet. Build from W1 onward. Do NOT import Meta baselines (TikTok audience behavior / CTR norms / CPA differ materially)
- **Expected deltas vs Meta** (hypotheses to validate): CTR higher on TikTok (5-8% finance benchmark vs Meta's 3.86%); CPA possibly higher initially; video completion rate is a primary leading indicator; creative fatigue cycles shorter (2-4 weeks vs 4-6)

## Compliance & Creative Framing Rules

### Bank vs moneylender rates — never compare

1.88% per month ≠ 1.88% per year. Bank APR and moneylender per-month flat rates are different categories. Comparing them is misleading AND guaranteed TikTok rejection. Value prop: "licensed lenders that approve when banks reject" — not "cheaper than banks". Always anchor rate mentions with "per month".

### TikTok-safe vocabulary (mandatory — TikTok is stricter than Meta on finance)

| Avoid | Use |
|---|---|
| "loan", "borrow", "cash advance" | "match", "lender match", "see your offers" |
| "Get money fast" / "Need money?" | "See what matches your profile" |
| Rate as product feature ("get 1.88%") | Rate as matching outcome ("some matched at 1.88% per month") |
| "Approval" / "approved" | "match", "offer", "see your options" |
| Bank-style comparison | Same-category framing only |
| "Guaranteed" anything | "May be eligible", "could qualify" |

### "Licensed lenders" is standard

MAS-regulated moneylenders are legally licensed. Use the word — regulatory-accurate AND trust signal. "lenders on our panel" → "licensed lenders on our panel".

### Rate as outcome, not promise

- ❌ "Match rates from 1.88%" (promise, compliance risk)
- ✅ "Some matches come back as low as 1.88% per month" (outcome, safer + honest)

Always follow with eligibility honesty: "yours depends on your profile".

## Copy Writing — Humanizer Rule

Any ad-facing text (captions, hooks, headlines, video scripts, brainstorm drafts shared with user) MUST be run through the humanizer skill before presenting. Scope excludes code/commits/internal analysis/dev docs. See `.claude/skills/humanizer/SKILL.md`.

## Superpowers Workflow Enforcement

Invoke relevant skills from `.claude/skills/` before acting — see `using-superpowers` skill for the invocation rules. Key process skills:

- `brainstorming` — before any creative/design work (features, components, behavior changes)
- `writing-plans` — when a spec exists and needs a multi-step plan
- `test-driven-development` — before writing implementation code
- `systematic-debugging` — any bug, test failure, or unexpected behavior
- `verification-before-completion` — before claiming work done, committing, or opening a PR
- `executing-plans` / `subagent-driven-development` — when running a written plan
- `finishing-a-development-branch` — when implementation is complete and ready to integrate

## Cross-Reference — meta-ads-agent

Read https://github.com/DoubleAM-sg/Meta-ads-agent CLAUDE.md for strategic depth not reproduced here:

- Full Corey Haines fatigue framework (3 signals, creative lifecycle stages Learning/Scaling/Mature/Fatigued)
- Message-Market Match audience psychology
- Learning engine (what to log from winners/losers, domain knowledge accumulation)
- W15/W16/W17 Meta execution history (useful as starting hypotheses)

Do NOT transfer: Meta API limits (CBO/ABO, dynamic creative, SGD $1.30 floor), specific Meta ad names/history, `adrules_library` syntax (TikTok has its own Automated Rules API).

## Developer Profile

> Profile not yet configured.
