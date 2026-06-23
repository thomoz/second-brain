# WhatsApp → Vault Pipeline — Discussion Handoff

**Status:** Partially complete — bitza.md created, entity pages done, save commands still to build
**Created:** 2026-06-23
**Updated:** 2026-06-23
**Next step:** Run `/core_piv_loop:plan-feature` to build WhatsApp save commands

---

## What's Working

1. Every WhatsApp exchange is written to `Memory/daily/YYYY-MM-DD.md` via `append_to_daily_log()`
2. Vault syncs every 2 min (VPS → GitHub → local)
3. `memory_reflect.py` runs 8am AEST, promotes daily log content to entity pages
4. Entity folders now exist for all creative projects

---

## What's Been Built This Session

- `Memory/entities/juno-wonderdog/` — index, characters, story, development log
- `Memory/entities/simone-kensington/` — same structure
- `Memory/bitza.md` — catch-all scratch file: Reminders, Ideas, Unsorted sections
- `core-memories.md` removed from session injection (not needed)

---

## What Still Needs Building

### WhatsApp Save Commands

Shaun wants to say "save this to Juno characters" or "remember this" mid-conversation
and have the content written directly to the right vault file immediately — not deferred
to 8am reflection.

**Trigger phrases:**
- "save this" / "remember this" / "log this"
- "save to [entity]" e.g. "save to Juno characters", "save to Simone", "save to bitza"
- "remind me to [X]" → bitza.md Reminders section

**Routing logic:**
| Phrase / keyword         | Target file                                        |
|--------------------------|-----------------------------------------------------|
| "juno" / "wonderdog"     | `Memory/entities/juno-wonderdog/` (right sub-file) |
| "simone" / "kensington"  | `Memory/entities/simone-kensington/` (right sub-file) |
| "investment" / "stocks"  | `Memory/topics/investment-strategy.md`             |
| "remind me"              | `Memory/bitza.md` → Reminders section              |
| no entity named          | `Memory/bitza.md` → Ideas or Unsorted section      |

**Implementation note:**
`engine.py` already has `Write` in `allowed_tools`. The LLM can write to vault files
directly. The bwrap issue on VPS affected Read (now fixed via pre-loading); Write tool
may work fine — test first before adding a Python fallback.

**Format for saves:**
Append under a dated heading so content is traceable:
```
## 2026-06-23 [WhatsApp save]
[content]
```

### Reflection Quality Check (low priority)
Check 8am reflection output to confirm it routes WhatsApp content to the right entity pages.
Tune `memory_reflect.py` prompt if it misses things.

---

## Architecture

```
WhatsApp message
    └─ engine.py
          ├─ save intent detected → Write tool → entity page / bitza.md  (immediate)
          └─ append_to_daily_log() → Memory/daily/YYYY-MM-DD.md
                    └─ vault sync (2 min) → local machine
                              └─ memory_reflect.py (8am) → entity pages / MEMORY.md
```

---

## How to Resume

1. Load this file: `.agent/plans/whatsapp-vault-pipeline-handoff.md`
2. Run `/core_piv_loop:plan-feature` — feed it this doc as context
3. Plan should cover: save intent detection, routing logic, file append format,
   bitza.md as fallback, Write tool test on VPS
