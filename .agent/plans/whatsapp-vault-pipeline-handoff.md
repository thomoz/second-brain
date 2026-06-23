# WhatsApp → Vault Pipeline — Discussion Handoff

**Status:** Scoped — previous premise was incorrect; see below
**Created:** 2026-06-23
**Updated:** 2026-06-23
**Next step:** Decide which of the remaining gaps are worth building

---

## What We Thought Was Wrong (Previous Session)

The previous session concluded that `chat.db → vault` was "completely unwired" and that
WhatsApp conversations never reached the vault. This was incorrect.

## What's Actually Happening

The pipeline already exists and works:

1. **WhatsApp message received** → `engine.py` calls `append_to_daily_log()` after every exchange
2. **Daily log** (`Memory/daily/YYYY-MM-DD.md`) is written on the VPS immediately
3. **Vault sync** runs every 2 min on both VPS and Windows → git push/pull via GitHub
4. **Local machine** has the full conversation within ~4 minutes of it happening
5. **Reflection** (`memory_reflect.py`) runs at 8am AEST, reads yesterday's daily log,
   and promotes relevant content to entity pages, MEMORY.md, and profile files

Confirmed: full WhatsApp conversation content appeared in local daily logs on 2026-06-23.

---

## What's Genuinely Still Missing (Smaller Scope)

### 1. Explicit in-conversation save commands
The daily log → reflection pipeline has a lag: content from today's WhatsApp session
won't be promoted to entity pages until 8am tomorrow. For high-value content dictated
from the car (novel ideas, project concepts, investment thoughts), Shaun wants to be able
to say "save this" or "remember this" and have the content written directly to the
appropriate vault file immediately — not deferred to reflection.

**Possible trigger phrases:**
- "save this" / "remember this" / "log this"
- "log to [entity]" / "tag: juno" / "tag: billy goat"

**Routing:**
- Named entity → `Memory/entities/[entity].md`
- Investment → `Memory/topics/investment-strategy.md`
- Personal/creative → appropriate profile or entity page
- Unspecified → `Memory/daily/` with a prominent `## [SAVED]` heading

### 2. Entity pages that don't exist yet
- **Juno Wonder Dog** — animation/creative project Shaun is developing; needs a vault page
  at `Memory/entities/creative-work.md` or a dedicated `Memory/entities/juno-wonder-dog.md`

### 3. Reflection quality check (not a build task)
Worth checking tomorrow's reflection output to confirm it correctly routes today's
WhatsApp conversations to the right entity pages. If reflection is missing things,
the prompt in `memory_reflect.py` may need tuning — but this is a tune, not a build.

---

## Current Architecture (confirmed correct)

```
WhatsApp message
    └─ engine.py → append_to_daily_log()
                        └─ Memory/daily/YYYY-MM-DD.md  (VPS)
                                └─ vault sync (git, every 2 min)
                                        └─ Memory/daily/YYYY-MM-DD.md  (local)
                                                └─ memory_reflect.py (8am AEST)
                                                        └─ entity pages / MEMORY.md
```

`chat.db` stores full session state for conversation continuity (resuming threads).
It does not need to be separately piped to the vault — the daily log already captures
the human-readable content.

---

## How to Resume

1. Load this file: `.agent/plans/whatsapp-vault-pipeline-handoff.md`
2. Decide whether to build the in-conversation save commands (Gap #1)
3. Create the Juno Wonder Dog entity page (Gap #2 — can be done any session)
4. If building save commands: run `/core_piv_loop:plan-feature` with this doc as context
