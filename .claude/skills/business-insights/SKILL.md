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
