# WhatsApp → Vault Pipeline — Discussion Handoff

**Status:** Design phase — requirements captured, no plan yet
**Created:** 2026-06-23
**Next step:** Discuss requirements, then `/core_piv_loop:plan-feature`

---

## The Problem

WhatsApp chat sessions between Shaun and the VPS bot live in `chat.db` on the VPS and **never reach the vault**. The heartbeat and reflection scripts don't read `chat.db`. So:

- Nothing said via WhatsApp filters into entity pages (businesses, investments, SongbookDB, etc.)
- Nothing said via WhatsApp appears in daily logs or MEMORY.md
- The whole point of having WhatsApp access to the Second Brain — that it learns about Shaun over time — isn't being fulfilled

---

## Shaun's Requirements

### 1. Fast sync (≤30 min)
Shaun may have a conversation via WhatsApp while driving (CarPlay), then be home 30 minutes later wanting to access what was discussed. The current vault sync is every 2 minutes, but chat sessions never enter the vault at all. The pipeline needs to be fast enough that a conversation from the car is accessible in the local Claude Code session when he gets home.

### 2. Full fidelity recording option (not just summaries)
Shaun wants the ability to have whole ideas fully recorded — not just summarised — when he wants that. Examples:
- Working on a novel idea
- **Juno Wonder Dog** — an animation story idea Shaun is developing (a character/project he wants tracked in the vault)
- Business ideas, show concepts, investment thoughts
- Anything important he might dictate while driving

The system should distinguish between:
- Routine Q&A (summarise only)
- "I want to remember this fully" (full fidelity capture to vault)

### 3. Filtering to correct vault entities
Content from WhatsApp should route to the right places:
- Business discussions → relevant entity page (billy-goat-karaoke.md, songbookdb/, etc.)
- Investment ideas → Memory/topics/investment-strategy.md or similar
- Personal/creative → new entity or topic page (e.g. Memory/entities/creative-work.md)
- General notes → daily log

### 4. Trigger mechanism
Shaun should be able to signal intent during a WhatsApp conversation:
- Possibly a keyword or command like "save this" or "remember this" or "log to [entity]"
- Or the bot should auto-detect important content and offer to save it

---

## Current Architecture (what exists)

- `chat.db` — SQLite on VPS, stores full conversation sessions per user/channel
- `whatsapp_runs.log` — bot activity log, VPS only
- `Memory/daily/*.md` — vault daily logs, synced every 2 min via git
- `memory_reflect.py` — runs 8am AEST, reads yesterday's daily log → promotes to MEMORY.md/entities
- Heartbeat reads Gmail/Calendar/WhatsApp (unread messages only) → writes to daily log
- Vault sync: `scripts/sync_vault.ps1` (Windows) + systemd timer (VPS) every 2 min

## The Gap

`chat.db` → vault is completely unwired. Reflection only reads daily logs, not chat history.

---

## Ideas to Discuss in Next Session

1. **Chat flush script** — after each WhatsApp session ends (or on a timer), extract the session from `chat.db`, run it through an LLM to classify and route content, write to appropriate vault files
2. **In-conversation save command** — bot detects "save this" / "log this" / "remember this" and immediately writes full content to a vault file, committed and synced within minutes
3. **Session tagging** — user can say "tag: juno" or "tag: billy goat" and the session gets routed to that entity's page
4. **Near-realtime sync** — flush to vault at end of each bot response (not just end of session) so 30-min car trip content is available immediately on arrival home
5. **Creative project pages** — Juno Wonder Dog needs its own entity page; others like it should be easy to create via WhatsApp ("start a new project called X")

---

## New Entity Noted

**Juno Wonder Dog** — animation story/creative project Shaun is developing. Needs a vault page at `Memory/entities/creative-work.md` or a dedicated page. Capture this in the next session.

---

## How to Resume

1. Load this file: `.agent/plans/whatsapp-vault-pipeline-handoff.md`
2. Discuss the requirements and approach with Shaun
3. Agree on the design before running `/core_piv_loop:plan-feature`
4. Plan should cover: flush trigger, routing logic, full-fidelity vs summary mode, in-conversation save command, vault entity creation flow
