# Feature: Phase 5 — Skills (Copy + Adapt from Cole's Reference)

The following plan should be complete, but validate file existence and paths before implementing.
Pay special attention to the two skills that need adaptation — they must NOT be copied verbatim.

## Feature Description

Copy all skills from Cole's reference Second Brain into Shaun's `.claude/skills/` directory.
14 skills copy verbatim. 2 skills require targeted adaptation:
- `vault-structure` (was `obsidian-vault-structure`) — rewrite for Shaun's Memory/ layout, not Dynamous'
- `direct-integrations` — rewrite SKILL.md to point to Shaun's query.py path, remove Asana/Slack/Sheets/Docs/Drive

## User Story

As Shaun's Second Brain,
I want a library of specialist skills available in every session,
So that I can immediately draft content, create documentation, query integrations, and navigate the memory vault without re-explaining conventions.

## Problem Statement

Without skills, every session starts cold — Claude has no procedural knowledge of vault conventions,
integration commands, content formats, or specialized workflows. Phase 5 solves this by bringing in
Cole's full skill library and adapting the two skills that are Dynamous-specific into Shaun-specific equivalents.

## Solution Statement

Batch-copy 14 generic skills verbatim. Hand-craft 2 adapted SKILL.md files with Shaun-specific
context. No new scripts, tests, or Python code required — this is almost entirely a file copy operation.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Low
**Primary Systems Affected**: `.claude/skills/`
**Dependencies**: None beyond what Phases 1–4 already delivered

---

## CONTEXT REFERENCES

### Source Directory

`O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\skills\`

### Destination Directory

`O:\AI\Dynamous\Courses\second-brain-workshop\.claude\skills\`

### Skills Already Present (DO NOT overwrite)

- `create-second-brain-prd/` — already exists, skip entirely

### Relevant Codebase Files — READ BEFORE IMPLEMENTING

- `.claude/scripts/integrations/query.py` — ENTIRE FILE — this is what `direct-integrations` SKILL.md must reference. The skill has NO `scripts/` subfolder of its own.
- `.claude/scripts/config.py` — lines 78–98 — GMAIL_ACCOUNTS and GOOGLE_CALENDAR_IDS dict structure (populated from env vars)
- `Memory/USER.md` — email accounts list, to populate account table in `direct-integrations` SKILL.md
- `Memory/MEMORY.md` — active projects list, for vault-structure SKILL.md
- `Memory/Clients/venues.md` — venue list, informs `Clients/` folder description
- `Memory/SOUL.md` — behavioral rules, for vault-structure SKILL.md agent constraints

### New Files to Create

**Verbatim copies (full directory trees):**
- `.claude/skills/skill-creator/` — all files
- `.claude/skills/sop-creator/` — all files
- `.claude/skills/pdf/` — all files
- `.claude/skills/pptx-generator/` — all files (large — ~30 cookbook scripts + brand folders)
- `.claude/skills/remotion/` — all files (~30 rules files)
- `.claude/skills/video-processor/` — all files
- `.claude/skills/excalidraw-diagram/` — all files
- `.claude/skills/mcp-client/` — all files
- `.claude/skills/instagram-post/` — all files
- `.claude/skills/linkedin-post/` — all files
- `.claude/skills/x-post/` — all files
- `.claude/skills/yt-script/` — all files
- `.claude/skills/yt-shorts/` — all files
- `.claude/skills/yt-livestream/` — all files

**Adapted (write new SKILL.md, no scripts subfolder):**
- `.claude/skills/vault-structure/SKILL.md` — NEW file, written from scratch for Shaun's Memory/
- `.claude/skills/direct-integrations/SKILL.md` — adapted from Cole's, updated paths + commands

**New custom skill (no Cole's equivalent):**
- `.claude/skills/business-insights/SKILL.md` — NEW file, written from scratch for Shaun's 5 businesses

### Patterns to Follow

**Skill frontmatter format** (from `skill-creator/SKILL.md`):
```yaml
---
name: skill-name
description: |
  What the skill does. When to use it. Specific trigger phrases.
---
```

**No extra files in adapted/custom skills** — `skill-creator` SKILL.md is clear: no README, INSTALLATION, CHANGELOG.
The `direct-integrations` skill has NO `scripts/` subfolder — query.py lives at `.claude/scripts/integrations/query.py`.
The `vault-structure` and `business-insights` skills have no subfolders either — all content fits in one SKILL.md each.

---

## IMPLEMENTATION PLAN

### Phase 1: Batch copy 14 verbatim skills

14 skills copied unchanged using xcopy/robocopy. No edits.

### Phase 2: Create vault-structure skill

Write `.claude/skills/vault-structure/SKILL.md` from scratch using Shaun's actual Memory/ structure.
Reference: Cole's `obsidian-vault-structure/SKILL.md` as a structural template only — content must
reflect Shaun's vault, not Dynamous'.

### Phase 3: Create direct-integrations skill

Write `.claude/skills/direct-integrations/SKILL.md` from scratch.
Reference: Cole's `direct-integrations/SKILL.md` for structure — adapt to Shaun's 8-account Gmail,
6-calendar setup, and correct script path. Remove Asana, Slack, Sheets, Docs, Drive entirely.
Do NOT create a `scripts/` subfolder inside this skill.

### Phase 4: Create business-insights skill

Write `.claude/skills/business-insights/SKILL.md` from scratch — no Cole's equivalent exists.
Must reflect Shaun's actual 5 businesses, real venue pay rates from `Memory/Clients/venues.md`,
real email account priorities, and how to cross-reference `Memory/Wealth/` for investment context.

### Phase 5: Validate

Confirm all 18 skill directories exist and each has a valid SKILL.md.

---

## STEP-BY-STEP TASKS

### Task 1: COPY 14 verbatim skills from reference

- **IMPLEMENT**: Use `xcopy /E /I /Y` (or Robocopy) to copy each skill directory
- **SOURCE**: `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\skills\`
- **DEST**: `O:\AI\Dynamous\Courses\second-brain-workshop\.claude\skills\`
- **SKIP**: `create-second-brain-prd` (already exists), `obsidian-vault-structure` (adapting it separately as `vault-structure`), `direct-integrations` (adapting separately)
- **GOTCHA**: `pptx-generator` has a binary `.pptx` file and `.png` — xcopy handles these fine, but verify they are included in the copy result
- **GOTCHA**: `remotion/rules/assets/` contains `.tsx` files — verify they copy correctly

```powershell
$src = "O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\skills"
$dst = "O:\AI\Dynamous\Courses\second-brain-workshop\.claude\skills"
$skills = @(
    "skill-creator", "sop-creator", "pdf", "pptx-generator", "remotion",
    "video-processor", "excalidraw-diagram", "mcp-client",
    "instagram-post", "linkedin-post", "x-post",
    "yt-script", "yt-shorts", "yt-livestream"
)
foreach ($s in $skills) {
    xcopy "$src\$s" "$dst\$s\" /E /I /Y /Q
}
```

- **VALIDATE**:
  ```powershell
  $dst = "O:\AI\Dynamous\Courses\second-brain-workshop\.claude\skills"
  $expected = @("skill-creator","sop-creator","pdf","pptx-generator","remotion","video-processor","excalidraw-diagram","mcp-client","instagram-post","linkedin-post","x-post","yt-script","yt-shorts","yt-livestream")
  foreach ($s in $expected) { if (Test-Path "$dst\$s\SKILL.md") { "OK: $s" } else { "MISSING: $s" } }
  ```
  Expected: 14 lines each starting with `OK:`

---

### Task 2: CREATE `.claude/skills/vault-structure/SKILL.md`

- **IMPLEMENT**: Write a new SKILL.md documenting Shaun's actual Memory/ vault structure
- **PATTERN**: Cole's `obsidian-vault-structure/SKILL.md` for layout and tone — all folder paths, naming conventions, and purposes MUST reflect Shaun's project, not Dynamous'
- **CONTENT**: See full content spec below

```markdown
---
name: vault-structure
description: |
  Reference for Shaun Thomson's Second Brain Memory vault organization and file conventions.
  Use when Claude needs to understand where content is stored, how files are organized, or
  where to save new content. Helpful for: (1) Finding existing notes, projects, or client info,
  (2) Understanding the append-only daily log format, (3) Knowing where to save new drafts,
  insights, or vault entries, (4) Understanding the draft lifecycle (active → sent/expired),
  (5) Navigating Memory/ subdirectories by business or topic.
---

# Second Brain Memory Vault Structure

**Location:** `Memory/` (relative to project root)

## Directory Overview

```
Memory/
├── SOUL.md           — Agent personality, behavioral rules, hard limits (never edit)
├── USER.md           — Shaun's profile, email accounts, businesses, preferences
├── MEMORY.md         — Key decisions, lessons, active projects (kept concise)
├── HEARTBEAT.md      — Monitoring checklist: email, calendar, WhatsApp, habits
├── HABITS.md         — Daily pillars: Shows, SongbookDB, Wealth, Health, Learning
├── daily/            — Append-only daily logs (YYYY-MM-DD.md)
├── Projects/         — Active work items per business
├── Clients/          — Venue details, contacts, show info
├── Research/         — External articles, learnings, reference notes
├── Goals/            — Personal goals, health tracking
├── Content/          — Social media drafts, marketing ideas
├── Wealth/           — Investment portfolio notes, financial research
└── drafts/
    ├── active/       — Email/message drafts pending Shaun's review
    ├── sent/         — Archived sent drafts (RAG voice-matching source)
    └── expired/      — Unactioned drafts after 24 hours
```

## Daily Logs

**Format:** `Memory/daily/YYYY-MM-DD.md`

Rules:
- Append-only — NEVER edit or delete past entries
- Each entry uses H2 timestamp heading: `## HH:MM`
- Entries written by: heartbeat agent, memory flush hook, manual notes
- Content includes: heartbeat summaries, draft notifications, show reminders

## Draft Files

All email/message drafts go to `Memory/drafts/active/`. YAML frontmatter is required:

```yaml
---
type: email_draft
source_id: <gmail_message_id>
recipient: venue@example.com.au
subject: Re: Booking inquiry — Saturday
account: karaoke
context: Venue asking about Dec 14 availability
created: 2026-06-09T14:30:00+10:00
status: active
---
```

**Draft lifecycle:**
- `active/` → created by heartbeat, awaiting Shaun's review
- `sent/` → moved after Shaun replies (heartbeat detects sent reply by thread ID match)
- `expired/` → moved if >24h old with no reply sent

**Naming convention:** `YYYY-MM-DD_email_<recipient-slug>.md`
Example: `2026-06-09_email_racquet-club-nicky.md`

**Voice-matching:** Past drafts in `drafts/sent/` are searched via `memory_search.py --path-prefix drafts/sent`
before generating new drafts, to match Shaun's writing tone.

## Projects/

One file per active initiative:

| File | Business | Purpose |
|------|----------|---------|
| `hosting-growth.md` | Host Masters | Show bookings, venue targets, revenue |
| `songbookdb.md` | SongbookDB | Feature queue, support patterns, churn notes |
| `karaoke-night-app.md` | BGK | App build with Victor Northhead |
| `creative-work.md` | Personal | FiNN TWiST music, Juno: Wonderdog film |

## Clients/

Venue and client details per business:

| File | Contents |
|------|---------|
| `venues.md` | All show venues — address, pay rate, schedule, contacts, status |

Add new venue or client files as needed using kebab-case naming.

## Folder Purposes

| Folder | Purpose | When to Write Here |
|--------|---------|-------------------|
| **Projects/** | Active initiatives — tasks, progress, decisions | New project milestone or decision |
| **Clients/** | Venue/client details, contact info | New venue booking or contact update |
| **Research/** | External articles, tool evaluations, learnings | Something worth preserving long-term |
| **Goals/** | Personal goals, health, habit tracking | Goal setting or progress notes |
| **Content/** | Social posts, marketing copy, show night ideas | Marketing drafts or ideas |
| **Wealth/** | Investment research, portfolio notes | Financial insights or opportunities |

## Key Conventions

1. **Daily logs:** `Memory/daily/YYYY-MM-DD.md` (append-only, H2 timestamp headings)
2. **Drafts:** `Memory/drafts/active/YYYY-MM-DD_email_<slug>.md` (YAML frontmatter required)
3. **No secrets or tokens** in any Memory/ file
4. **Checkbox syntax:** `- [ ]` incomplete / `- [x]` complete
5. **Timezone:** All timestamps use Australia/Sydney (AEST UTC+10 / AEDT UTC+11)

## Agent Constraints (SOUL.md Rules)

- Write to `Memory/drafts/active/` only — never send emails automatically
- Write to `Memory/daily/` for log entries — never delete or overwrite existing content
- Read any Memory/ file for context
- NEVER modify `SOUL.md`
- NEVER delete any file in Memory/
- NEVER access financial accounts or make purchases
```

- **VALIDATE**:
  ```powershell
  Test-Path "O:\AI\Dynamous\Courses\second-brain-workshop\.claude\skills\vault-structure\SKILL.md"
  ```
  Expected: `True`

---

### Task 3: CREATE `.claude/skills/direct-integrations/SKILL.md`

- **IMPLEMENT**: Write a new SKILL.md for Shaun's integration setup — correct script path, Shaun's 8 accounts/6 calendars, no Asana/Slack/Sheets/Docs/Drive
- **PATTERN**: Cole's `direct-integrations/SKILL.md` for structure
- **GOTCHA**: Do NOT create a `scripts/` subfolder inside this skill. Shaun's query.py lives at `.claude/scripts/integrations/query.py` — the skill just points to it
- **GOTCHA**: The 8 Gmail account names (personal, sbdb, karaoke, hosting, bingo, trivia, finntwist, hooklust) come from `Memory/USER.md` and `.claude/scripts/config.py`
- **CONTENT**: See full content spec below

```markdown
---
name: direct-integrations
description: |
  Query Gmail (8 accounts), Google Calendar (6 calendars), and Outlook directly via Python APIs.
  Use when the user asks to check email, view calendar events, or read Outlook messages.
  Triggers on requests like "check my email", "show calendar", "any urgent emails",
  "what's on my calendar today", "check unread", "check Outlook", or any email/calendar query
  across Shaun's accounts.
---

# Direct Platform Integrations

Query Gmail (8 accounts), Google Calendar (6 calendars), and Outlook — no Zapier or MCP needed.

## Script Path

`.claude/scripts/integrations/query.py`

## Running Commands

```bash
# Gmail — all 8 accounts (default) or single account
python .claude/scripts/integrations/query.py gmail list                           # All accounts unread (last 24h)
python .claude/scripts/integrations/query.py gmail list --account sbdb            # Single account
python .claude/scripts/integrations/query.py gmail list --account karaoke --hours 48
python .claude/scripts/integrations/query.py gmail urgent                         # Urgent across all accounts
python .claude/scripts/integrations/query.py gmail unread                         # Unread counts per account

# Calendar — all 6 calendars or single calendar
python .claude/scripts/integrations/query.py calendar all                         # All calendars next 24h
python .claude/scripts/integrations/query.py calendar today                       # Personal calendar today
python .claude/scripts/integrations/query.py calendar today --calendar bgk        # Specific calendar
python .claude/scripts/integrations/query.py calendar upcoming --hours 48         # Next 48 hours

# Outlook
python .claude/scripts/integrations/query.py outlook list                         # Outlook inbox
python .claude/scripts/integrations/query.py outlook unread                       # Unread count
python .claude/scripts/integrations/query.py outlook urgent                       # Unread last 2 hours
```

## Gmail Account Names

| Account | Email Address | Priority |
|---------|--------------|---------|
| `sbdb` | shaun_thomson@songbookdb.com | Highest — support tickets |
| `karaoke` | info@billygoatkaraoke.com.au | High — venue bookings |
| `hosting` | hostmastersentertainment@gmail.com | High — contract shows |
| `bingo` | dingosmusicbingo@gmail.com | Medium |
| `trivia` | thommostrivia@gmail.com | Medium |
| `personal` | shaunthommo10@gmail.com | Medium |
| `finntwist` | finntwistmusic@gmail.com | Low |
| `hooklust` | hooklustmusic@gmail.com | Low |

## Calendar Names

| Calendar | Purpose |
|----------|---------|
| `personal` | Primary Google Calendar — shaunthommo10@gmail.com |
| `bgk` | Billy Goat Karaoke shows |
| `bingo` | Dingo's Music Bingo shows |
| `trivia` | Thommo's Trivia shows |
| `dogdaycare` | Dog day care schedule |
| `hme` | Host Masters Entertainment |

## Auth Setup

Check current auth status:
```bash
cd .claude\scripts && python integrations\setup_auth.py --check
```

Re-authenticate when tokens expire (weekly — OAuth app is in Testing mode):
```bash
cd .claude\scripts && python integrations\setup_auth.py
```

**Token expiry:** OAuth app stays in Testing mode → tokens expire every 7 days. Re-run `setup_auth.py` weekly.

**Calendar sharing:** Non-personal calendars (bgk, bingo, trivia, dogdaycare, hme) must be shared
with `shaunthommo10@gmail.com` in Google Calendar settings for multi-calendar queries to work.

## Notes

- Gmail + Calendar share a single Google OAuth token (personal account)
- Outlook uses MSAL device code flow — token persists via `SerializableTokenCache` at `integrations/outlook_token.json`
- SongbookDB support (sbdb account) is highest priority for email drafts
- `query.py` handles errors gracefully — unauthenticated accounts are skipped with a warning
```

- **VALIDATE**:
  ```powershell
  Test-Path "O:\AI\Dynamous\Courses\second-brain-workshop\.claude\skills\direct-integrations\SKILL.md"
  ```
  Expected: `True`
  Confirm no `scripts/` folder was created inside the skill:
  ```powershell
  Test-Path "O:\AI\Dynamous\Courses\second-brain-workshop\.claude\skills\direct-integrations\scripts"
  ```
  Expected: `False`

---

### Task 4: CREATE `.claude/skills/business-insights/SKILL.md`

- **IMPLEMENT**: Write a new SKILL.md for multi-business insight generation — no Cole's equivalent
- **SOURCE DATA**: Read `Memory/Clients/venues.md` (venue pay rates), `Memory/MEMORY.md` (active projects), `Memory/USER.md` (email accounts) before writing
- **GOTCHA**: No `scripts/` or `references/` subfolder — all content fits in one SKILL.md
- **GOTCHA**: Venue pay rates and show schedules must come from `Memory/Clients/venues.md` — do NOT invent them
- **CONTENT**: See full content spec below

```markdown
---
name: business-insights
description: |
  Surface efficiency opportunities and investment insights across Shaun's 5 businesses
  (SongbookDB, Billy Goat Karaoke, Dingo's Music Bingo, Thommo's Trivia, Host Masters Entertainment).
  Use when the user asks about business performance, show efficiency, email load patterns, revenue
  insights, or investment opportunities. Triggers on requests like "how are my shows performing",
  "any efficiency wins", "what's taking up the most time", "check business insights",
  "surface investment notes", "which shows are worth keeping", or any multi-business analysis.
---

# Business Insights

Surface actionable efficiency and investment insights across Shaun's 5 businesses.

## Business Map

| Business | Core Activity | Email Account | Priority |
|----------|--------------|--------------|---------|
| SongbookDB | Karaoke song list software — support + dev | `sbdb` | Highest |
| Billy Goat Karaoke | Hosted karaoke shows | `karaoke` | High |
| Host Masters Entertainment | Umbrella — own + contract shows | `hosting` | High |
| Dingo's Music Bingo | Hosted music bingo shows | `bingo` | Medium |
| Thommo's Trivia | Hosted trivia nights | `trivia` | Medium |

## Insight Types

### 1. Show Efficiency

Pull calendar data and cross-reference `Memory/Clients/venues.md` for pay rates and status.

Key questions:
- Which shows have the best pay-to-effort ratio? (high pay + short drive = keep; low pay + long drive + struggling crowd = review)
- Any venue where crowd has been consistently low for 2+ months despite ad spend?
- How many shows this week vs. last week? (load tracking)
- Any gaps in the forward booking pipeline?

**Pay rate reference (from venues.md):**

| Venue | Show | Frequency | Pay |
|-------|------|-----------|-----|
| Moss Vale Services Club | Bingo + Karaoke | Monthly | $1,100 |
| Wests Illawarra Club | Karaoke | 2×/month | $770 + super |
| Katoomba Family Hotel | Karaoke | Monthly | $918–$1,083 |
| Boyles Sutherland Hotel | Karaoke | Weekly | $595 |
| Boyles Sutherland Hotel | Trivia (Jeff) | Weekly | $385 − costs − host |
| Kiama Bowling Club | Karaoke (Mel) | Weekly | $595–$694 − costs − host |
| The Friendly Inn KV | Karaoke (Mel) | Monthly | $824 − costs − host |
| The Racquet Club | Trivia | Weekly | $330 (ramp-up) |
| Surfboat Brewery | Karaoke | Fortnightly | ~$11/head |
| Surfboat Brewery | Bingo | Monthly | ~$11/head |

Flag Surfboat Brewery shows if head-count revenue is consistently below $200 — that's the review threshold.

### 2. Email Volume Patterns

Run `query.py gmail unread` to get per-account snapshot. Patterns worth surfacing:

- **sbdb spike** → SongbookDB support load up; check for recurring issues or new customer wave
- **karaoke/hosting spike** → booking inquiries or venue comms up; draft replies likely needed
- **Consistent zero-unread on sbdb** → either quiet period or auth issue (note it)
- **Any account at 10+ unread** → flag immediately; likely needs attention today

### 3. SongbookDB Support Patterns

When sbdb has multiple unread messages, look for recurring themes:

```bash
python .claude/scripts/integrations/query.py gmail list --account sbdb --hours 168
```

Recurring signals to log to `Memory/Projects/songbookdb.md`:
- Same error appearing across multiple tickets → potential product bug
- Onboarding questions clustering → docs or onboarding flow gap
- Churn risk language: "cancelling", "too expensive", "not working", "switching"

### 4. Investment and Wealth Insights

Always read `Memory/Wealth/` files before generating financial insights. Never speculate without that context.

What to surface:
- Active positions or theses being watched — cross-reference with anything relevant in email
- "Build cash buffer pre-crash" goal (MEMORY.md) → note when show revenue is strong or a new booking comes in
- Any investment opportunity mentioned in email → cross-reference existing Wealth/ notes before flagging

**Where notes belong:**

| Note type | Write to |
|-----------|---------|
| Ephemeral observation (today only) | `Memory/daily/YYYY-MM-DD.md` |
| Ongoing position or investment thesis | `Memory/Wealth/*.md` |
| Key business or financial decision | `Memory/MEMORY.md` |

### 5. Efficiency Signals

Patterns worth flagging proactively:

- **Ad spend vs. crowd**: Most venues run FB + IG ~$1.45/day. If a show has run ads for 3+ months with consistently poor attendance, surface it.
- **Contract host transitions**: Shows moving to gear-hire model reduce travel burden — track transition status in venues.md.
- **High-effort/low-return shows**: Surfboat Brewery karaoke — fortnightly, long drive to Warriewood, variable crowd. Flag if head-count revenue stays low.
- **High-value underutilised relationships**: Wests Illawarra Club ($770 + super, 2×/month) is a top performer — any expansion opportunity worth exploring?

## Workflow

1. Run `query.py gmail unread` → email volume snapshot
2. Run `query.py calendar all` → shows in next 24–48h
3. Read `Memory/Clients/venues.md` → venue context and pay rates
4. Read `Memory/Wealth/` → investment context
5. Synthesise into brief bullets: what's most actionable for Shaun today?

## Output Format

Surface as brief bullets — lead with the most actionable item:

```
**Shows:**
- [Venue]: show tonight [time] — $[pay]
- [Venue]: crowd low 3 weeks running — worth a call to [contact]?

**Email:**
- sbdb: [N] unread — check for recurring support themes
- karaoke: [N] booking inquiries — drafts in Memory/drafts/active/

**Wealth:**
- [Note from Memory/Wealth/ relevant to today]
```

Shaun runs 5 businesses. Keep it scannable — no walls of text.
```

- **VALIDATE**:
  ```powershell
  Test-Path "O:\AI\Dynamous\Courses\second-brain-workshop\.claude\skills\business-insights\SKILL.md"
  ```
  Expected: `True`

  Confirm venue pay rates are present:
  ```powershell
  Select-String -Path "O:\AI\Dynamous\Courses\second-brain-workshop\.claude\skills\business-insights\SKILL.md" -Pattern "Moss Vale|Wests Illawarra|Surfboat|sbdb"
  ```
  Expected: 4+ matches

---

### Task 5: VALIDATE all 18 skills present and well-formed

- **IMPLEMENT**: Check all 18 skill directories exist with a SKILL.md
- **VALIDATE**:
  ```powershell
  $skills = @("skill-creator","sop-creator","pdf","pptx-generator","remotion","video-processor",
    "excalidraw-diagram","mcp-client","instagram-post","linkedin-post","x-post",
    "yt-script","yt-shorts","yt-livestream","vault-structure","direct-integrations",
    "business-insights","create-second-brain-prd")
  $base = "O:\AI\Dynamous\Courses\second-brain-workshop\.claude\skills"
  $ok = $true
  foreach ($s in $skills) {
    $path = "$base\$s\SKILL.md"
    if (Test-Path $path) { "OK: $s" } else { "MISSING: $s"; $ok = $false }
  }
  if ($ok) { "All 18 skills verified." }
  ```
  Expected: 18 lines starting with `OK:` followed by `All 18 skills verified.`

---

## TESTING STRATEGY

### No unit tests for this phase

Skills are Markdown files. No Python, no APIs, no tests needed.

### Manual validation

1. Open `.claude/skills/vault-structure/SKILL.md` — confirm Memory/ paths match actual project structure
2. Open `.claude/skills/direct-integrations/SKILL.md` — confirm script path and account names are correct
3. Open `.claude/skills/business-insights/SKILL.md` — confirm venue pay rates and email account names match venues.md and USER.md
4. Open `.claude/skills/sop-creator/SKILL.md` — confirm verbatim copy (should match Cole's source)
5. Open `.claude/skills/pptx-generator/cookbook/` — confirm ~20 Python cookbook files copied
6. Open `.claude/skills/remotion/rules/` — confirm ~30 Markdown rules files copied

---

## VALIDATION COMMANDS

### Level 1: File existence
```powershell
$base = "O:\AI\Dynamous\Courses\second-brain-workshop\.claude\skills"
(Get-ChildItem $base -Directory).Name | Sort-Object
```
Expected: 18 directories listed (including create-second-brain-prd)

### Level 2: SKILL.md frontmatter check (all skills have name + description)
```powershell
$base = "O:\AI\Dynamous\Courses\second-brain-workshop\.claude\skills"
Get-ChildItem $base -Recurse -Filter "SKILL.md" | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $hasName = $content -match "^name:"
    $hasDesc = $content -match "^description:"
    "$($_.Directory.Name): name=$hasName desc=$hasDesc"
}
```
Expected: 18 lines, all showing `name=True desc=True`

### Level 3: Spot check adapted and custom skills

Vault structure — confirm Memory/ paths are correct:
```powershell
Select-String -Path "O:\AI\Dynamous\Courses\second-brain-workshop\.claude\skills\vault-structure\SKILL.md" -Pattern "Memory/daily|drafts/active|SOUL.md"
```
Expected: 3+ matches for Shaun's vault paths

Direct integrations — confirm NO Asana/Slack/Sheets references:
```powershell
Select-String -Path "O:\AI\Dynamous\Courses\second-brain-workshop\.claude\skills\direct-integrations\SKILL.md" -Pattern "asana|slack|sheets|docs|drive" -CaseSensitive:$false
```
Expected: No output (0 matches)

Confirm correct script path in direct-integrations:
```powershell
Select-String -Path "O:\AI\Dynamous\Courses\second-brain-workshop\.claude\skills\direct-integrations\SKILL.md" -Pattern "\.claude/scripts/integrations/query\.py"
```
Expected: 1+ match

Business insights — confirm venue names and account names are present:
```powershell
Select-String -Path "O:\AI\Dynamous\Courses\second-brain-workshop\.claude\skills\business-insights\SKILL.md" -Pattern "Moss Vale|Wests Illawarra|Surfboat|sbdb|songbookdb"
```
Expected: 4+ matches

---

## ACCEPTANCE CRITERIA

- [ ] 14 verbatim skills copied to `.claude/skills/` with all subdirectory files intact
- [ ] `.claude/skills/vault-structure/SKILL.md` documents Shaun's Memory/ vault (not Dynamous')
- [ ] `.claude/skills/direct-integrations/SKILL.md` points to `.claude/scripts/integrations/query.py`
- [ ] `direct-integrations` has no `scripts/` subfolder
- [ ] `direct-integrations` has NO Asana, Slack, Sheets, Docs, Drive content
- [ ] `direct-integrations` lists all 8 Gmail accounts and 6 calendar names correctly
- [ ] `vault-structure` correctly describes Memory/ folder structure, daily log format, draft lifecycle
- [ ] `.claude/skills/business-insights/SKILL.md` covers all 5 businesses with real venue pay rates
- [ ] `business-insights` shows and email patterns reference actual data from venues.md and USER.md
- [ ] All 18 skill SKILL.md files have valid YAML frontmatter (name + description)
- [ ] `create-second-brain-prd/` skill is untouched
- [ ] No new Python files, no new test files, no new config files created

---

## COMPLETION CHECKLIST

- [ ] Task 1: 14 skills batch-copied, all validated present
- [ ] Task 2: vault-structure/SKILL.md written and verified
- [ ] Task 3: direct-integrations/SKILL.md written and verified (no scripts/ subfolder)
- [ ] Task 4: business-insights/SKILL.md written with real venue data and verified
- [ ] Task 5: All 18 skills (including create-second-brain-prd) exist and have valid SKILL.md

---

## NOTES

**Content skills (linkedin-post, x-post, yt-script, yt-shorts, yt-livestream, instagram-post):**
These are written for Cole's AI/tech content business. The style guides reference
Cole's voice and YouTube channel. Shaun can use or ignore them. They are copied verbatim
because they have generic value and Shaun opted to bring all skills across.
The source attribution sections (referencing `DAILY_DIGEST.md` and `content-engine/output/topics/`)
will not apply to Shaun's vault — these sections are harmless but irrelevant.

**pptx-generator and remotion:**
These are large skill directories with many files. Verify the xcopy ran completely —
pptx-generator includes `.pptx` and `.png` binaries that must copy correctly.

**skill-creator is itself a skill:**
It lives in `.claude/skills/skill-creator/`. It gives Claude the knowledge to create
new skills in future sessions. Copy it verbatim — its `scripts/` subfolder contains
`init_skill.py`, `package_skill.py`, `quick_validate.py` which are useful utilities.

**business-insights is the only genuinely custom skill:**
It has no Cole's equivalent, so the execution agent must write it from scratch using real data from
`Memory/Clients/venues.md` and `Memory/USER.md`. The task spec includes the full SKILL.md content,
but the agent must verify venue pay rates and email account names against the actual source files
before writing — do not trust memory alone.

**Confidence Score: 9.5/10** — Pure file copy + three short Markdown files. No API calls,
no Python, no dependencies. The only risk is a data mismatch in the custom SKILL.md files,
which the validation commands will catch.
