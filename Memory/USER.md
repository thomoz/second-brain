# User Profile

Name: Shaun Thomson
Timezone: Australia/Sydney (AEST UTC+10 / AEDT UTC+11)
Location: Sydney, Australia

## Businesses
- SongbookDB (SBDB Software Pty Ltd) — karaoke song list software, support + dev
- Billy Goat Karaoke — hosted karaoke shows at venues
- Dingo's Music Bingo — hosted music bingo shows
- Thommo's Trivia — hosted trivia nights
- Host Masters Entertainment — umbrella for live entertainment

## Email Accounts
- shaunthommo10@gmail.com — personal + marketing test emails
- info@billygoatkaraoke.com.au — Billy Goat Karaoke bookings/hosting
- hostmastersentertainment@gmail.com — umbrella hosting (own shows + contract hosts)
- dingosmusicbingo@gmail.com — Dingo's Music Bingo hosting
- shaun_thomson@songbookdb.com — SongbookDB (includes support@songbookdb.com and others)
- finntwistmusic@gmail.com — FiNN TWiST original music
- hooklustmusic@gmail.com — older original music account (lower priority)
- thommostrivia@gmail.com — Thommo's Trivia hosting
- thomoz@outlook.com — personal + some business (Outlook, not Gmail)

## Proactivity Level
Advisor — draft for review, never send or post

## Drafting Criteria
Draft replies to: SongbookDB support requests, venue booking inquiries, important business correspondence
Skip drafts for: Newsletters, automated notifications, spam

## Integration Config
- Gmail: 8 accounts (see Email Accounts above)
- Outlook: thomoz@outlook.com
- Calendar: Google Calendar (primary)
- WhatsApp: personal number (GREEN-API, Phase 4)

## 2026-06-16 Reflection
- Prefer no closing summary sentences in tool output; Shaun reads the output directly

## 2026-06-18 Reflection
- ask-me-questions should end on stop words or after 10 minutes of WhatsApp silence

## 2026-06-19 Reflection
- Next ask-me-questions session should resume at relationships
- ask-me-questions reflection flow now scans profile files before choosing the first question

## 2026-06-23 Reflection
- Daily logs sync to the vault every 2 minutes via git and a VPS timer
- `memory_reflect.py` runs at 8am AEST and currently ignores `chat.db` history

## 2026-06-24 Reflection
- (Jun 24) Next ask-me-questions session should resume at relationship patterns to improve

## 2026-06-27 Reflection
- WhatsApp message-end detection should wait longer before treating a pause as finished

## 2026-06-29 Reflection
- Daily logs now use `Memory/daily/YYYY/MM/YYYY-MM-DD.md` paths

## 2026-07-03 Reflection
- (Jul 03) Outlook retrieval uses Microsoft Graph app registration with tenant `consumers`

## 2026-07-05 Reflection
- SongbookDB Windows repo path: `O:\SBDB Software\SongbookDB\www\songbookdb-deep`

## 2026-07-09 Reflection
- Shaun handles SongbookDB production uploads via WinSCP

## 2026-07-19 Reflection
- (Jul 19) GREEN-API recovery may require full logout and fresh QR relink after LID issues

## 2026-08-16 Reflection
- (Aug 16) GOAT Phase 1 exit check is live on VPS via systemd timer
- (Aug 16) GOAT 150DMA daily check runs at 21:35 UTC / 07:35 AEST
- (Aug 16) GOAT interim intraday alert config uses pct 0.0 and min consecutive days 1

## 2026-08-17 Reflection
- (Aug 17) Goat handoff canonical file is `investments/goat/HANDOFF.md`
- (Aug 17) `second-brain-goat-live-check.timer` is enabled on the VPS
- (Aug 17) Goat S&P 500 heartbeat scanner is live on the VPS

## 2026-08-18 Reflection
- (Aug 18) Goat insider scanner is live on VPS; runs daily at 21:50 UTC / about 07:50 AEST
- (Aug 18) Goat insider sell alerts use 10% first-sale and 1% repeat-sale-in-90-days thresholds
- (Aug 18) Goat insider buy alerts require at least $25k
- (Aug 18) Fourteen Crash Signals Phases 1 and 2 are deployed on VPS; 8 markers are live

## 2026-08-19 Reflection
- (Aug 19) Fourteen Crash Signals Phase 3 is live on VPS; all 14 markers are now real
- (Aug 19) Goat Monitor now runs insider-selling checks on the broader watchlist

## 2026-08-20 Reflection
- (Aug 20) Recover broken Claude Code on Windows with PowerShell install script, then `claude --version`

## 2026-08-23 Reflection
- Local GREEN-API WhatsApp notifications work; no VPS relay needed
- Access VPS `investments.db` locally via `scripts/invoke_investments.ps1`

## 2026-08-26 Reflection
- (Aug 26) Wrapper strips literal `$` from command args; use `USD 6.19` style prices
- (Aug 26) `SecondBrain-MyTraderMonitor` 7:30am run should use VPS over SSH, not local DB

## 2026-08-29 Reflection
- (Aug 29) GOAT insider discovery excludes institutional bare `10%` Form 4 filers
- (Aug 29) `GOAT_INSIDER_DISCOVERY_EXCLUDE_INSTITUTIONAL_10PCT` is live on VPS

## 2026-09-02 Reflection
- (Sep 02) Codex backend replaced Gemini after quota issues
- (Sep 02) `/commit` now auto-pushes and deploys to VPS

## 2026-09-06 Reflection
- (Sep 06) Heartbeat Codex backend is configured to unsupported model gpt-5.4

## 2026-09-07 Reflection
- Codex backend was fixed from unsupported gpt-5.4 to gpt-5.5

## 2026-09-08 Reflection
- PowerShell Package: prompt means scripts/invoke_investments.ps1 is waiting for mandatory -Package

## 2026-09-09 Reflection
- (Sep 09) Repo convention uses .agent/plans, not .agents/plans
- (Sep 09) Superinvestor WhatsApp digests now use heading "Superinvestor filing:"

## 2026-09-10 Reflection
- (Sep 10) Superinvestor reports run 12:35pm and 10:30pm Sydney time during AEST
- (Sep 10) Heartbeat Codex backend gpt-5.5 returned 404 before later successful run

## 2026-09-12 Reflection
- (Sep 12) codex_sdk_compat.py retries transient Codex errors; CODEX_MAX_ATTEMPTS defaults to 3.

## 2026-09-15 Reflection
- (Sep 15) Moat scanner deployed; daily timer runs 23:30 UTC / about 09:30 AEST.
- (Sep 15) Moat scanner VPS is secondbrain@137.184.102.104.
- (Sep 15) Moat scan command uses local PowerShell to SSH remote bash via base64.

## 2026-09-16 Reflection
- (Sep 16) DMA breakout scanner plan created at .agent/plans/goat-dma-breakout-scanner.md.
- (Sep 16) Hated Industries Scanner plan created at .agent/plans/hated-industries-scanner.md.
- (Sep 16) Planned DMA scanner CLI subcommand is scan-dma-breakout.
- (Sep 16) Planned Hated Industries Scanner CLI subcommand is scan-hated-industries.
- (Sep 16) Suggested DMA timer is 22:55 UTC; suggested Hated Industries timer is 23:50 UTC.

## 2026-09-17 Reflection
- (Sep 17) DMA breakout scanner uses yfinance daily bars; poll cadence is not bar interval.
- (Sep 17) DMA breakout Exchange column should appear after next VPS scan.
- (Sep 17) Earnings Deterioration Watch handoff drafted; feature is not built yet.
- (Sep 17) Earnings Watch should scan my-trader holdings only, not full Monitor watchlist.
- (Sep 17) Earnings Watch needs estimate-history table and 8-K support in sec_filings.py.
- (Sep 17) Planned Earnings Watch CLI is scan-earnings-watch with report and systemd timer.
- (Sep 17) Oroco/OCO.V insider scan needs SEDI, not US Form 4/OpenInsider.

## 2026-09-20 Reflection
- (Sep 20) NEXG should use TSXV ticker NEXG.V, not bare NEXG.

## 2026-09-24 Reflection
- (Sep 24) DMA breakout ETF universe added and deployed.
- (Sep 24) IBKR sync auto-removal fixed and deployed.
- (Sep 24) WhatsApp alerts now include company name beside ticker.
- (Sep 24) VPS deploy included vault-sync resilience and staleness-alert fixes.
- (Sep 24) my-trader quote fetch 404s for BMS/BMS.AX fundamentals and some metals ETFs.

## 2026-09-25 Reflection
- (Sep 25) ROC triple signal handoff written at `investments/roc-triple-signal-handoff.md`; not built.
- (Sep 25) ROC triple v1 should be report-only until backtested against price ROC alone.
- (Sep 25) Cash-Value Scan gates are net cash >=50% market cap and positive TTM OCF.
- (Sep 25) Cash-Value Scan excludes financials/REIT-like sectors and defense hits.
- (Sep 25) Matt Damon check uses config prefix `MATT_DAMON_*`.
