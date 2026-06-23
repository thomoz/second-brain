# WhatsApp → Vault Pipeline — Discussion Handoff

**Status:** Decisions locked — ready for `/prime` then `/plan-feature` in a fresh session
**Created:** 2026-06-23
**Updated:** 2026-06-23
**Next step:** Fresh session → `/prime` → `/core_piv_loop:plan-feature` with this doc as context

---

## What's Working

1. Every WhatsApp exchange is written to `Memory/daily/YYYY-MM-DD.md` via `append_to_daily_log()`
2. Vault syncs every 2 min (VPS → GitHub → local)
3. `memory_reflect.py` runs 8am AEST, promotes daily log content to entity pages
4. Entity folders exist for all creative projects

---

## What's Been Built This Session

- `Memory/entities/juno-wonderdog/` — index, characters, story, development log
- `Memory/entities/simone-kensington/` — same structure
- `Memory/bitza.md` — catch-all scratch file: Reminders, Ideas, Unsorted sections
- `core-memories.md` removed from session injection (not needed)

---

## Architecture Decision: Personal Assistant Command Manifest

This feature is the first piece of a larger **personal assistant command center** — the
same way someone calls a PA to take notes, set reminders, draft emails, add to calendar.
Shaun drives from WhatsApp (often via CarPlay while driving 12–15 hrs/week).

**Where save commands live: `Memory/ASSISTANT.md`**

A new markdown file loaded into the system prompt alongside `SOUL.md` in `engine.py`.
Vault-editable — new commands added without touching Python code. Structured as sections
per command category so it grows naturally:

```
## Save & Notes       ← building now
## Reminders          ← next natural add (already overlaps with bitza Reminders)
## Email Drafting     ← Memory/drafts/active/ already wired
## Calendar           ← log-only for now, action later
## General Research   ← "look up X and save what you find"
## Entity Management  ← create/update entity pages
```

**engine.py change:** one new `_load_assistant_commands()` loader + one line appending to
`system_prompt`, identical pattern to `_load_vault_context()`.

---

## What Needs Building

### 1. Enable WebSearch (one-line fix)
`engine.py:222` `allowed_tools` is missing `"WebSearch"`.
`codex_sdk_compat.py` already handles it: `_WEB_TOOLS = {"WebSearch", "WebFetch"}` at line 145,
passes `tools.web_search=true` to Codex at line 377. Network access is already enabled for
tool-using calls (line 382). Just add `"WebSearch"` to `allowed_tools`.
**Discovery task:** test from VPS that the sandbox doesn't block it.

### 2. Create `Memory/ASSISTANT.md` — Personal Assistant Command Manifest
The system prompt injection file. Defines all save command routing rules and format.

### 3. WhatsApp Save Commands
Shaun says "save this to Juno characters" or "remind me to X" mid-conversation.
Content is written directly to the right vault file immediately — not deferred to 8am reflection.

**Trigger phrases:**
- "save this" / "remember this" / "log this"
- "save to [entity]" e.g. "save to Juno characters", "save to Simone", "save to bitza"
- "remind me to [X]" → bitza.md Reminders section

**Routing logic:**
| Phrase / keyword        | Target file                                           |
|-------------------------|-------------------------------------------------------|
| "juno" / "wonderdog"    | `Memory/entities/juno-wonderdog/` (LLM picks sub-file) |
| "simone" / "kensington" | `Memory/entities/simone-kensington/` (LLM picks sub-file) |
| "investment" / "stocks" | `Memory/topics/investment-strategy.md`                |
| "remind me"             | `Memory/bitza.md` → Reminders section                 |
| no entity named         | `Memory/bitza.md` → Ideas section                     |

**Sub-file routing:** LLM picks based on content type (character description → characters.md,
plot/narrative → story.md, general/development notes → development-log.md, etc.)

**Intent detection:** LLM-driven via Write tool. If unsure of destination, ask for
clarification. If unsure of content scope ("this" with no obvious referent), infer from
conversation context — Codex is expected to handle this naturally.

**New entity flow:** If Shaun names an entity that has no folder:
1. LLM suggests file path and location
2. Waits for Shaun's confirmation
3. Creates the file/folder on confirm

**Confirmation:** Always reply with a short confirmation after saving (e.g. "Saved to Juno
characters"). Ask a clarifying question if destination is ambiguous.

**Save format — append under a dated heading:**
```markdown
## 2026-06-23 [WhatsApp save]
[content]
```

### 4. Clean up `Memory/bitza.md`
Remove the `## Unsorted` section — only Reminders + Ideas needed.

### 5. Write tool VPS test (discovery task)
The handoff noted Write is already in `allowed_tools` but untested from the bot on VPS.
Test a Write call from a live WhatsApp message. If it fails (bwrap), add a Python
direct-write fallback in `engine.py` (similar to how `_load_vault_context` pre-loads
files to work around Read bwrap failures).

### 6. Reflection Quality Check (low priority)
Check 8am reflection output to confirm it routes WhatsApp content to the right entity pages.
Tune `memory_reflect.py` prompt if it misses things.

---

## Key Files to Read Before Planning

- `.claude/chat/engine.py` — system prompt construction (line 193), allowed_tools (line 222),
  vault context loader pattern (`_load_vault_context`)
- `.claude/scripts/codex_sdk_compat.py` — WebSearch support (lines 145–149, 377–383)
- `Memory/bitza.md` — current structure (Reminders, Ideas, Unsorted — remove Unsorted)
- `Memory/entities/juno-wonderdog/` — existing sub-files to understand routing targets
- `Memory/entities/simone-kensington/` — same
- `.agent/plans/second-brain-prd.md` — for context on overall direction

---

## Architecture (updated)

```
WhatsApp message
    └─ engine.py
          ├─ ASSISTANT.md injected into system_prompt (always-on)
          ├─ save intent detected → Write tool → entity page / bitza.md  (immediate)
          │       └─ confirmation reply to Shaun
          └─ append_to_daily_log() → Memory/daily/YYYY-MM-DD.md
                    └─ vault sync (2 min) → local machine
                              └─ memory_reflect.py (8am) → entity pages / MEMORY.md
```

---

## Q&A Decisions Log (from design conversation 2026-06-23)

| Question | Decision |
|----------|----------|
| Sub-file routing when no sub-file named | LLM picks based on content type |
| Intent detection — Python or LLM | LLM via Write tool; ask for clarification if confused |
| "Save this" — inline or previous message | LLM infers from conversation context |
| Confirmation reply | Always; or ask if destination ambiguous |
| bitza.md sections | Reminders + Ideas only — remove Unsorted |
| Write tool VPS test | Discovery task within this plan |
| Unknown entities | LLM suggests path → confirm → create |
| Save command instruction location | `Memory/ASSISTANT.md`, loaded into system prompt |
| WebSearch | Add to allowed_tools (one-line fix); test VPS sandbox |
| Bigger vision | Personal assistant command center — ASSISTANT.md grows by section over time |
