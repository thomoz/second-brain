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
