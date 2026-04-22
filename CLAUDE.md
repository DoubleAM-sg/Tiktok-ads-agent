# CLAUDE.md

## Project

**TikTok Ads Agent** — Autonomous TikTok Ads agent for PickMeALoan (PMAL, Singapore personal loan platform). Sister project to meta-ads-agent; same operational model adapted for TikTok. Three cadences (daily/weekly/monthly) delivered via Telegram, persistent state under `.state/`.

**Core Value:** Autonomous monitoring and creative optimization on TikTok — surface what works, pause what doesn't, recommend next creative batch.

## Session Kick-off — Always Read First

Before suggesting any optimization, pause, creative launch, budget change, audience move, or workflow run:

1. Read `.state/optimization_log.json` — append-only audit of every decision we've made, with rationale. If you're about to propose pausing X, check whether X was already paused/reactivated recently and why.
2. Read the most recent `.state/weekly_snapshots/YYYY-WNN.json` (and the preceding one if it exists) — current performance baseline + WoW context.
3. Read the most recent `.state/daily_snapshots/YYYY-MM-DD.json` if a same-week delta matters.
4. Read `.state/creative_registry.json` if it exists — user-provided creative labels + angles.
5. Read the **Learnings Log** section at the bottom of this file — TikTok-account-specific patterns we've already proved out or ruled out.

If any of those are missing or stale, say so before proceeding — don't guess from memory, and don't re-litigate decisions already made. When you make a new significant decision (pause, creative add, budget shift, scope request), append it to `.state/optimization_log.json` in the same PR as the change.

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

- Python 3.11+, FastAPI, Click, Uvicorn, Pydantic v2, pydantic-settings, Rich, pytest, ruff, mypy (strict)
- Execution model: GitHub Actions workflows (scheduled + merge-triggered). No standalone chat UI / Anthropic SDK — strategic reasoning happens in Claude Code sessions; workflows run deterministic Python (data pulls, reports, pause/activate, Telegram posts).
- `tiktok-business-api-sdk` as the primary TikTok Marketing API client
- Entry point: `tiktok-ads` CLI → `src/tiktok_ads_agent/cli/main.py`

## Conventions

Same as meta-ads-agent: snake_case modules/functions/vars, PascalCase classes, ALL_CAPS enum values, PEP 604 unions (`str | None`), explicit type hints, f-strings, Rich `console.print` for output, module + public function docstrings, ruff `E/F/I/N/W/UP`, line length 100, mypy strict.

## Architecture

Mirrors meta-ads-agent. Layers: `core` (client + settings), `models` (pydantic schemas), `api` (FastAPI routers), `cli` (Click), `reports` (daily/weekly/monthly), `creative` (Corey Haines analysis), `notifications` (Telegram), `state` (JSON persistence). Workflows under `.github/workflows/` invoke the CLI on schedule and post results to Telegram.

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
- `/adgroup/get/` field gotchas — `external_action`/`external_type` are **not** valid fields there (they're only on /adgroup/create/); use `placements` (plural, not `placement`); custom pixel events like "Submit application" surface in `custom_conversion_id`, not `optimization_event`
- Smart+ / Upgraded Smart Plus campaigns reject `/adgroup/update/` mutations — TikTok owns placements / optimization there. Error message: "This API does not support Upgraded Smart Plus ads." Our `exclude_pangle` workflow detects this and marks the adgroup `skipped_smart_plus` rather than failing. Implication: Pangle exclusion must be done via Ads Manager UI for Smart+ campaigns, not via API

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

## Learnings Log

Append-only, dated. Add new entries **above** the earlier ones (reverse-chronological). Keep entries tight: what we observed, what we did, what to revisit. TikTok-native only — do not carry Meta inferences forward beyond the setup phase; TikTok audience behaviour, creative affinity, and optimization dynamics are distinct.

---

### 2026-W17 — Daily report hardened; ACO off; API/UI ad_id mismatch proven

**What broke / how we fixed it**

- **Scheduled cron skipped.** The 2026-04-21 21:00 UTC scheduled daily silently didn't execute (GH Actions peak-time skip). Workflow has a failure-notify step but it never reached that. Retrigger via path-filter push to `.github/workflows/daily-report.yml` works as a manual bootstrap; cron is best-effort, not guaranteed.
- **Telegram 400 on HTML parse_mode.** Our signals block emitted literal `(<3d):` which Telegram's HTML parser rejected as a malformed tag. Dropped `parse_mode` entirely — report is plain text + emojis, no HTML formatting needed, and ad captions containing `<` / `>` / `&` are now safe to forward unescaped.
- **`/ad/get/` default hides ads.** Default is `filtering.primary_status=STATUS_NOT_DELETE`, which hides deleted/appeal-review objects. Pass `STATUS_ALL` explicitly in every `list_ads()` call.
- **`/report/integrated/get/` silently drops deleted ads.** Even with `filtering.ad_ids=[...]` and `STATUS_ALL`, TikTok still excludes rows for ads whose `secondary_status=AD_STATUS_DELETE`. Historical conversion data disappears the moment an ad is deleted. Defense: `fetch_snapshot()` now merges with the on-disk snapshot for the same period — new rows win on collision, old rows with `spend > 0` are preserved for ad_ids missing from the new pull. Once metrics hit disk for a given day they stay.
- **Ad Performance filter was too strict.** `operation_status == "ENABLE"` excluded ads deleted mid-day even though they spent real money earlier in the reporting window. Relaxed to "had spend in the window" so yesterday's paused ads still show yesterday's data.

**API/UI ad_id mismatch — confirmed token-scope limitation**

- Ads Manager UI shows ad_ids our `/ad/get/` cannot see (direct lookup via `filtering.ad_ids` returns `(not returned)` for them). Our token is restricted to the **Spark-Ad shadow copies** TikTok creates when a direct-to-Ads-Manager ad references an organic post.
- Shadow copies share the organic post's caption as `ad_name`; direct ads (invisible to us) carry the short names the user typed ("PMAL UGC", "Cashback Launch", "Cashback - $50 Don't Know", "Cashback - Already Borrowing").
- Root cause: pending Creative / Audience / Pixel Management OAuth scopes from W16. Until those land, we label shadow ad_ids manually via `.state/creative_registry.json` to match what the user sees in Ads Manager.
- **Revisit once scopes land** — should unlock direct ad_ids and kill the registry mapping.

**ACO (Auto-add newly generated assets) disabled**

- When ON, TikTok auto-generates hook/CTA/music variant ad_ids under each user-facing ad, each with its own metrics row. Our 2026-04-17 roster had 11 such variants (`Auto-generated-CTA_*`, `New_Hook-*`, `Music_Refresh-*`, `auto carousel generation_*`).
- User turned it off in Ads Manager → new ads will map 1:1 to one ad_id each. Historical variants will churn out.
- Daily's Ad Performance aggregates by registry label so variant noise collapsed into the parent ad's row; Creative Variants section auto-hides once each label resolves to a single ad_id.

**Reporting structure settled**

- Sections: header → conversions headline → budget + CPA → Campaign Performance → Converting ad groups → Ad Performance (by label, nested under adgroup) → Creative Variants (only when a label has >1 delivering variant) → MTD Pacing (campaign-level aggregate, separate API call).
- **Signals section removed.** CTR-drop / fatigue thresholds are meaningless with <1 week of history; `new (<3d)` just repeated user actions. Helper `_detect_signals` gone. Revive if/when the account matures and the thresholds have something to say.
- `creative_registry.json` accepts `"ad_id": "label"` or `"ad_id": {"label": ..., "angle": ...}`. Current 9-entry map covers both the Lookalike-Rejected adgroup and the new `MS+SS Customer reject-Narrow` adgroup.

**Campaign state (end of 2026-04-22)**

- 1 campaign: `Leads-Manual`, $20/day dynamic daily budget
- 2 adgroups enabled: `Leads-Lookalike-before 1jan2025 rejected` (original) + `MS+SS Customer reject-Narrow` (new today, 4 ads pending TikTok review under `1863143710470449`)
- 3 delivering ads on 2026-04-21: PMAL UGC (POV variant + Bank-rejected variant = 6 conv combined) + Cashback Launch (1 conv). Total 7 conv at $3.57 blended CPA.
- POV (1862715093286945) deleted mid-2026-04-22; merge-with-existing preserves its yesterday metrics.

**Open / to revisit**

- **Creative / Audience / Pixel Management OAuth scopes** still pending TikTok review. Re-check ~Apr 26; re-auth and drop the shadow-copy workaround once granted.
- **Pending TikTok review** on the 4 new MS+SS ads. Once they deliver, verify registry label pairings (inferred from caption content — user to confirm/correct).
- **Signals reintroduction** — once there are 2-3 weeks of history, CTR-drop + fatigue thresholds become trustworthy. Revive the section (or a trimmed version) at that point.
- **Pangle exclusion** still blocked on Smart+ adgroups via API; keep doing it in Ads Manager UI for Smart+.

---

### 2026-W16 — Baseline established, first snapshot committed

**Setup state at end of week**

- OAuth scope granted: Ad Account Management, Ads Management, Reporting, Measurement, Custom Conversion, Ad Diagnosis, Automated Rules, Reach & Frequency, Lead Management, Mentions, TikTok Accounts, Ad Comments.
- OAuth scope pending TikTok manual review: **Audience Management, Creative Management, Pixel Management**. Without these: no programmatic audience discovery, limited creative metadata, no direct pixel-event query.
- GitHub Actions live: `verify-secrets`, `daily-report` (cron 05:00 SGT), `weekly-report` (cron Mon 05:00 SGT), `monthly-report` (cron 1st 05:00 SGT), `send-notification` (dispatch), `exclude-pangle` (idempotent on merge). All commit state back to `main` as `tiktok-ads-bot`.
- Pipeline validated end-to-end; `.state/weekly_snapshots/2026-W16.json`, `.state/monthly_snapshots/2026-03.json`, `.state/daily_snapshots/2026-04-20.json` all committed.

**Campaign state (end of W16)**

- 1 Smart+ campaign: `Leads-Lookalike-before 1jan2025 rejected`. $20/day dynamic. Objective `LEAD_GENERATION` with Location=Website. Pixel `7624420828901376018` ("PMAL TikTok Pixel") optimizing for custom event **"Submit application"** — this = SingPass form submit on the loan-matching-page = the real conversion.
- 3 ads active during W16: POV-acknowledge-redirect (new), Cashback-reward, Bank-rejected-storytime.

**W16 performance (Apr 13–19)**

- Totals: $53.63 spend · 7,634 impressions · 94 clicks · **1.21% CTR** · 16 SingPass submits · **$3.35 blended CPA**.
- Per-ad CPA ranking: POV $1.63 (6 conv, 2 days live), Cashback $3.50 (5 conv), Bank-rejected $5.27 (5 conv).
- Hook retention (2s-views / plays): Bank-rejected **32%**, POV 18%, Cashback 12%. Bank-rejected has the strongest stop-scroll hook but the weakest conversion rate (9.8%) — more research, less yield.
- **Budget underspend**: $53.63 actual on $140 planned (38%). Smart+ + narrow audience + tight conversion goal keeps delivery conservative at low volume. Diversifying audiences should lift utilisation.

**Decisions taken**

- **POV removed** post-W16 — TikTok flagged the creative for compliance. Historical snapshot retains its data; future ads sheets won't show it. Implication: re-audit any new acknowledge-redirect variant's language before publishing, especially rate mentions.
- **Pangle exclusion attempted via API** — failed on the Smart+ adgroup because `/adgroup/update/` rejects placement changes on Smart+ ("This API does not support Upgraded Smart Plus ads."). No loss; Smart+ manages placement internally and W16's $3.35 CPA suggests it's doing so reasonably. Manual Pangle toggle only possible via Ads Manager UI on Smart+. Our workflow now classifies this as `skipped_smart_plus` rather than `failed`, so re-runs are no-ops.
- **Ad group expansion deferred to 2026-04-22** — user will create LAL Narrow MS+SS and Custom Rejected-List adgroups in Ads Manager. Same 3 (now 2 remaining) existing ads + Spark Ad from scheduled organic post (lower CPM, higher trust).

**API findings (TikTok v1.3)**

- `/adgroup/get/` fields: the param is **`placements`** plural, not `placement`. Custom pixel events like "Submit application" live in **`custom_conversion_id`**, not `optimization_event` (which is null on LEAD_GEN/Website adgroups). `external_action` / `external_type` are create-only — requesting them on GET returns `40002`.
- Smart+ adgroups reject `/adgroup/update/` mutations entirely. Treat Smart+ as a black box for placement / optimization; only Manual adgroups are scriptable.
- Conversion-field reconciliation: campaign `objective_type: LEAD_GENERATION` does not mean TikTok in-app lead forms when **Location: Website** is set. The `conversion` metric in reports = actual pixel `SubmitForm` events. Verified via Ads Manager UI (ad group → Optimization and bidding → Event: "Submit application").

**Open / to revisit**

- Pixel Management + Audience Management + Creative Management scopes — check status ~Apr 26 and re-auth once granted.
- W17 first real baseline computation (needs 7 days of clean data with the new adgroups and the frequency/engagement metrics the pipeline now pulls). Auto-pause proposals unlock after two consecutive weeks.
- TikTok finance CTR benchmark of 5–8% (industry rumour) is well above our 1.21%. Not alarming given CPA is good — but if CPA creeps up it's the first lever to pull (creative refresh).

---

## Cross-Reference — meta-ads-agent

Read https://github.com/DoubleAM-sg/Meta-ads-agent CLAUDE.md for strategic depth not reproduced here:

- Full Corey Haines fatigue framework (3 signals, creative lifecycle stages Learning/Scaling/Mature/Fatigued)
- Message-Market Match audience psychology
- Learning engine (what to log from winners/losers, domain knowledge accumulation)
- W15/W16/W17 Meta execution history (useful as starting hypotheses)

Do NOT transfer: Meta API limits (CBO/ABO, dynamic creative, SGD $1.30 floor), specific Meta ad names/history, `adrules_library` syntax (TikTok has its own Automated Rules API).

## Developer Profile

> Profile not yet configured.
