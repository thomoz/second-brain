# Phase 1: Memory Foundation

The following plan is complete and self-contained. All file contents are specified inline — no additional reading required before implementing.

## Feature Description

Create the `Memory/` vault — a folder of Markdown files that becomes the agent's long-term memory — and `CLAUDE.md` at the repo root so every future Claude Code session has full project context loaded automatically. This is the foundation all subsequent phases build on.

## User Story

As Shaun Thomson (multi-business founder),
I want a structured memory vault pre-seeded with my business context and a CLAUDE.md that loads automatically,
So that every Claude Code session immediately knows who I am, what I run, and how to behave — without me re-explaining it.

## Problem Statement

Without a persistent memory layer, every Claude Code session starts cold with no knowledge of Shaun's 5 businesses, communication preferences, or behavioral rules. The agent cannot draft emails, surface insights, or operate in Advisor mode without this foundation.

## Solution Statement

Create a folder of Markdown files at `Memory/` seeded with Shaun's profile, agent personality rules, monitoring checklist, daily habits, and first-run onboarding script. Create `CLAUDE.md` at the repo root that Claude Code auto-loads into every session. Create all required subdirectory stubs for future phases.

## Feature Metadata

**Feature Type**: New Capability  
**Estimated Complexity**: Low  
**Primary Systems Affected**: Memory vault, Claude Code session context  
**Dependencies**: None — this is the foundation everything else builds on

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ BEFORE IMPLEMENTING

- `.agent/plans/second-brain-prd.md` (lines 1–223) — Phase 1 section: exact file contents for SOUL.md, USER.md, BOOTSTRAP.md, HEARTBEAT.md, CLAUDE.md. **NOTE: Plan below contains all content inline — reading PRD is optional but useful for broader context.**

### New Files to Create

```
Memory/
├── SOUL.md
├── USER.md
├── MEMORY.md
├── BOOTSTRAP.md
├── HEARTBEAT.md
├── HABITS.md
├── daily/.gitkeep
├── Projects/.gitkeep
├── Clients/.gitkeep
├── Research/.gitkeep
├── Goals/.gitkeep
├── Content/.gitkeep
├── Wealth/.gitkeep
└── drafts/
    ├── active/.gitkeep
    ├── sent/.gitkeep
    └── expired/.gitkeep
CLAUDE.md                      ← repo root, not inside Memory/
```

### Patterns to Follow

**Markdown conventions:**
- Checkbox syntax: `- [ ]` incomplete, `- [x]` complete
- H2 headings (`##`) for sections within files
- No trailing whitespace
- Files are UTF-8, no BOM

**Directory stubs:**
- Empty directories use `.gitkeep` (a zero-byte file) so git tracks them
- Git does not track empty directories — `.gitkeep` is required for `daily/`, `Projects/`, `Clients/`, `Research/`, `Goals/`, `Content/`, `Wealth/`, `drafts/active/`, `drafts/sent/`, `drafts/expired/`

**CLAUDE.md placement:**
- Must be at repo root (`O:\AI\Dynamous\Courses\second-brain-workshop\CLAUDE.md`), NOT inside `Memory/`
- Claude Code auto-loads this file into every session

---

## STEP-BY-STEP TASKS

Execute in order. Each task is independently verifiable.

---

### TASK 1 — CREATE `Memory/SOUL.md`

Agent personality, behavioral rules, communication style, and business context.

**EXACT CONTENT:**

```markdown
# Second Brain — Soul

You are Shaun's Second Brain — an AI advisor supporting a multi-business founder in Sydney, Australia.

## Operating Mode
Advisor: You draft things for review. You never send, post, or act autonomously.

## Behavioral Rules
- Never send emails, messages, or social media posts
- Never modify files outside Memory/
- Never access financial systems or make purchases
- Never delete anything, anywhere
- When in doubt, draft and surface for review — never assume permission

## Communication Style
Direct and practical. No fluff. Shaun is a busy operator managing 5 businesses and hosting live shows. Be concise, actionable, and businesslike.

## Business Context
- SongbookDB (SBDB Software Pty Ltd) — karaoke song list software, support + dev
- Billy Goat Karaoke — hosted karaoke shows at venues
- Dingo's Music Bingo — hosted music bingo shows
- Thommo's Trivia — hosted trivia nights
- Host Masters Entertainment — umbrella for live entertainment
Show days involve travel to venues to host events.
```

**VALIDATE:** File exists at `Memory/SOUL.md` and contains "Advisor" and "Business Context"

---

### TASK 2 — CREATE `Memory/USER.md`

User profile. Email accounts intentionally left for BOOTSTRAP onboarding.

**EXACT CONTENT:**

```markdown
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
(Populated during BOOTSTRAP.md onboarding)

## Proactivity Level
Advisor — draft for review, never send or post

## Drafting Criteria
Draft replies to: SongbookDB support requests, venue booking inquiries, important business correspondence
Skip drafts for: Newsletters, automated notifications, spam

## Integration Config
(Populated during BOOTSTRAP.md onboarding)
```

**VALIDATE:** File exists at `Memory/USER.md` and contains "Shaun Thomson" and "BOOTSTRAP"

---

### TASK 3 — CREATE `Memory/MEMORY.md`

Long-term memory store. Seeded with known key facts; active projects left for BOOTSTRAP.

**EXACT CONTENT:**

```markdown
# Memory

Active as of: 2026-06-03

## Key Facts
- Five businesses: SongbookDB (SBDB Software Pty Ltd), Billy Goat Karaoke, Dingo's Music Bingo, Thommo's Trivia, Host Masters Entertainment
- Show days: travel to venues to host karaoke/bingo/trivia nights
- Proactivity: Advisor mode — draft for review, never act autonomously

## Active Projects
(Populated during BOOTSTRAP.md onboarding)

## Key Decisions
- Second Brain build started 2026-06-03
- Memory vault root: Memory/
- Deployment target: Windows local + VPS (cloud sync)
```

**VALIDATE:** File exists at `Memory/MEMORY.md` and contains "Key Facts"

---

### TASK 4 — CREATE `Memory/BOOTSTRAP.md`

First-run interactive onboarding script. SessionStart hook (Phase 2) will detect this file and inject it into context on the first session. File deletes itself after onboarding completes.

**EXACT CONTENT:**

```markdown
# BOOTSTRAP — First-Run Onboarding

This file drives your initial setup conversation. The agent will ask you questions one at a time to personalize your Second Brain. This file deletes itself when done.

## Onboarding Questions (Ask One at a Time)

1. "I can see you run 5 businesses. What are the most active projects or initiatives right now that I should track in Memory/Projects/?"

2. "What Gmail addresses should I monitor? Please list each one and what it's used for (e.g., personal, SongbookDB support, karaoke bookings). Include your Outlook address too."

3. "Are there specific venues, clients, or contacts I should know about upfront? (I can add more later, but let's capture the key ones now)"

4. "For your investment portfolio — what are you currently tracking? Stocks, crypto, property? I'll set up Memory/Wealth/ to match your categories."

5. "What habit pillars matter most to you right now? Current defaults: SongbookDB progress, Shows hosted, Wealth review, Health, Learning. Adjust freely."

6. "How do you prefer I communicate — formal or casual? Brief bullets or fuller context?"

## After Onboarding
Write answers to USER.md, SOUL.md (communication style), and HEARTBEAT.md.
Then delete this file.
```

**VALIDATE:** File exists at `Memory/BOOTSTRAP.md` and contains 6 numbered questions

---

### TASK 5 — CREATE `Memory/HEARTBEAT.md`

Monitoring checklist. Heartbeat script (Phase 6) reads this to know what to check each run.

**EXACT CONTENT:**

```markdown
# Heartbeat Monitoring Checklist

## Email (All Accounts)
- [ ] Unread Gmail messages across all accounts (SongbookDB support priority)
- [ ] Unread Outlook messages
- [ ] Draft email replies for important threads

## Calendar
- [ ] Show days in next 48 hours (karaoke/bingo/trivia venues)
- [ ] Pre-show reminders (24h and 2h before each show)
- [ ] Upcoming booking or business meetings

## WhatsApp
- [ ] Unread messages from known contacts
- [ ] Venue or client messages needing a response

## Business Insights
- [ ] Efficiency patterns in email volume/type
- [ ] Recurring support issues in SongbookDB tickets
- [ ] Investment/wealth notes to surface

## Habits
- [ ] Update today's HABITS.md checklist
- [ ] Auto-detect show completions from Calendar
- [ ] Late-day nudge for unchecked pillars
```

**VALIDATE:** File exists at `Memory/HEARTBEAT.md` and contains "Show days"

---

### TASK 6 — CREATE `Memory/HABITS.md`

Daily improvement pillars. Shows pillar is auto-detected by the heartbeat (Phase 6); all others are self-reported.

**EXACT CONTENT:**

```markdown
# Daily Habits

## Today's Pillars
- [ ] **SongbookDB** — Made progress on a feature, bug fix, or support ticket
- [ ] **Shows** — Prepared or hosted a show (karaoke/bingo/trivia)
- [ ] **Wealth** — Reviewed investments, researched opportunity, or updated portfolio notes
- [ ] **Health** — Exercise, sleep hygiene, or deliberate health action
- [ ] **Learning** — Read, watched, or practiced something new

## Auto-Detection Rules
- **Shows**: Heartbeat auto-checks if Google Calendar has show-day event today ✓
- All others: Self-report only (Advisor mode)

## History
(Heartbeat appends yesterday's checklist here each morning with a timestamp)
```

**VALIDATE:** File exists at `Memory/HABITS.md` and contains 5 pillars

---

### TASK 7 — CREATE directory stubs

Create `.gitkeep` files in all empty directories so git tracks them.

**Files to create (all zero bytes):**

```
Memory/daily/.gitkeep
Memory/Projects/.gitkeep
Memory/Clients/.gitkeep
Memory/Research/.gitkeep
Memory/Goals/.gitkeep
Memory/Content/.gitkeep
Memory/Wealth/.gitkeep
Memory/drafts/active/.gitkeep
Memory/drafts/sent/.gitkeep
Memory/drafts/expired/.gitkeep
```

**GOTCHA:** Do not put any content in `.gitkeep` files. They must be zero-byte. Use `Write` tool with empty string content, or the equivalent.

**VALIDATE:** All 10 `.gitkeep` files exist. Run: `Get-ChildItem -Recurse -Filter .gitkeep Memory\ | Measure-Object` — should output Count: 10

---

### TASK 8 — CREATE `CLAUDE.md` (repo root)

Project instruction file auto-loaded by Claude Code into every session. Must be at repo root, NOT inside `Memory/`.

**EXACT CONTENT:**

```markdown
# Shaun Thomson's Second Brain

## Project Description
AI Second Brain for a multi-business founder (SongbookDB, karaoke, music bingo, trivia).
Monitors Gmail (multiple accounts), Outlook, Google Calendar, and WhatsApp.
Drafts email replies and surfaces efficiency/investment insights. Advisor mode only —
all action requires Shaun's explicit review.

## Key Paths
- Memory vault: Memory/
- Daily logs: Memory/daily/
- Active drafts: Memory/drafts/active/
- Sent drafts: Memory/drafts/sent/
- Expired drafts: Memory/drafts/expired/
- Projects: Memory/Projects/
- Clients: Memory/Clients/
- Research: Memory/Research/
- Goals: Memory/Goals/
- Content: Memory/Content/
- Wealth: Memory/Wealth/
- Scripts: .claude/scripts/
- Hooks: .claude/hooks/
- Skills: .claude/skills/
- Integrations: .claude/scripts/integrations/
- Data/state: .claude/data/
- State file: .claude/data/state/heartbeat-state.json
- Chat sessions: .claude/data/chat.db

## Project Conventions
- Timezone: Australia/Sydney (AEST UTC+10 / AEDT UTC+11)
- Proactivity: Advisor mode — draft for review, never send or act autonomously
- No secrets, API keys, or tokens in Memory/ vault
- Daily logs: Memory/daily/YYYY-MM-DD.md (append-only, never edit past entries)
- Draft files: YAML frontmatter required (type, source_id, recipient, subject, created, status)
- Checkbox syntax: - [ ] incomplete / - [x] complete
- All email/message drafts go to Memory/drafts/active/ — never sent automatically

## Build Commands
(Populated as phases complete)

## Completed Phases
(Updated after each phase is built)
```

**VALIDATE:** File exists at `CLAUDE.md` (repo root, not `Memory/CLAUDE.md`) and contains "Key Paths"

---

### TASK 9 — UPDATE `CLAUDE.md`: mark Phase 1 complete

After all files are created, update the "Completed Phases" section in `CLAUDE.md`.

**UPDATE** the `## Completed Phases` section to:

```markdown
## Completed Phases

### Phase 1: Memory Foundation (2026-06-03)
Memory vault created at Memory/ with SOUL.md, USER.md, MEMORY.md, BOOTSTRAP.md,
HEARTBEAT.md, HABITS.md. All subdirectory stubs created. BOOTSTRAP.md will run
onboarding on first session to populate email accounts and active projects.
```

**VALIDATE:** `CLAUDE.md` contains "Phase 1: Memory Foundation"

---

## VALIDATION COMMANDS

### Level 1: File existence check

```powershell
Get-ChildItem Memory\ -Recurse | Select-Object FullName
```
Expected: SOUL.md, USER.md, MEMORY.md, BOOTSTRAP.md, HEARTBEAT.md, HABITS.md, plus 10 .gitkeep files across subdirs.

```powershell
Test-Path CLAUDE.md
```
Expected: `True`

### Level 2: Content spot-checks

```powershell
Select-String "Advisor" Memory\SOUL.md
```
Expected: match on Operating Mode line

```powershell
Select-String "SongbookDB" Memory\USER.md
```
Expected: match

```powershell
Select-String "Key Paths" CLAUDE.md
```
Expected: match

### Level 3: Directory structure

```powershell
Get-ChildItem -Recurse -Filter .gitkeep Memory\ | Measure-Object
```
Expected: Count = 10

### Level 4: Manual review

Open `Memory/SOUL.md` and confirm:
- [ ] "Advisor" appears in Operating Mode
- [ ] All 5 businesses listed in Business Context
- [ ] Communication style is "Direct and practical. No fluff."

Open `CLAUDE.md` and confirm:
- [ ] It is at repo root (not inside Memory/)
- [ ] All 12+ key paths are listed
- [ ] Completed Phases section mentions Phase 1

---

## ACCEPTANCE CRITERIA

- [ ] `Memory/SOUL.md` exists with correct agent personality and all 5 businesses
- [ ] `Memory/USER.md` exists with Shaun's profile; email accounts section says "(Populated during BOOTSTRAP.md onboarding)"
- [ ] `Memory/MEMORY.md` exists with Key Facts seeded
- [ ] `Memory/BOOTSTRAP.md` exists with 6 numbered onboarding questions
- [ ] `Memory/HEARTBEAT.md` exists with all monitoring categories
- [ ] `Memory/HABITS.md` exists with 5 pillars (SongbookDB, Shows, Wealth, Health, Learning)
- [ ] All 10 directory stubs created with `.gitkeep` files
- [ ] `CLAUDE.md` exists at repo root (not inside Memory/)
- [ ] `CLAUDE.md` contains Key Paths section with all Memory/ subdirs listed
- [ ] `CLAUDE.md` Completed Phases section updated for Phase 1
- [ ] No secrets, email addresses, or API keys appear in any file

---

## COMPLETION CHECKLIST

- [ ] Tasks 1–9 completed in order
- [ ] All Level 1–4 validation steps passed
- [ ] CLAUDE.md is at repo root, not Memory/CLAUDE.md
- [ ] BOOTSTRAP.md is present (will trigger onboarding on next session)
- [ ] No .gitkeep files are missing

---

## NOTES

**Why BOOTSTRAP.md is left intact after Phase 1:**
The SessionStart hook (built in Phase 2) detects `Memory/BOOTSTRAP.md` and injects it as onboarding context. Until Phase 2 is built, the file just sits there harmlessly. Do not delete it.

**Why email accounts are not pre-filled:**
Shaun has multiple Gmail accounts. Pre-filling them without the auth token names risks creating registry config that doesn't match the Phase 4 token file names. BOOTSTRAP onboarding captures both the addresses and the account slugs together.

**Why Projects/Clients/etc are left empty:**
BOOTSTRAP onboarding will ask about active projects and key contacts. Pre-seeding with assumptions creates files that need to be corrected. Empty stubs are cleaner.

**CLAUDE.md is a living document:**
Every subsequent phase (2–9) will add to the Build Commands and Completed Phases sections. The skeleton created here is intentionally sparse.
