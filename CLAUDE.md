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

### Phase 1: Memory Foundation (2026-06-03)
Memory vault created at Memory/ with SOUL.md, USER.md, MEMORY.md, BOOTSTRAP.md,
HEARTBEAT.md, HABITS.md. All subdirectory stubs created. BOOTSTRAP.md will run
onboarding on first session to populate email accounts and active projects.
