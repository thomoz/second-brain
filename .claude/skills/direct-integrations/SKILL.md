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
