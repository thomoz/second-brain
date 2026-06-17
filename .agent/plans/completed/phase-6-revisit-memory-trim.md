# Phase 6 Revisit: MEMORY.md Trim Behaviour

Review after Phase 7 is complete.

---

## What to Revisit

`memory_reflect.py` contains a `trim_memory_if_needed()` function added during the
Phase 6 build. It is NOT in Cole's reference implementation — and likely shouldn't be.

**What it does:**
- If `Memory/MEMORY.md` exceeds 200 lines, archives the oldest entries to
  `Memory/Research/memory-archive-YYYY-MM-DD.md` and keeps only the most recent 200 lines.

---

## Why It's Probably Wrong

The reflection LLM **is already the consolidation step**. The `memory_reflect.py` prompt
instructs the LLM to:
- Only promote key decisions, lessons, and important long-term facts
- Skip anything already present in MEMORY.md (no duplication)
- Keep entries concise

Cole trusts this selectivity to keep MEMORY.md manageable naturally. The trim function
is therefore redundant — a dumb line-count chop sitting on top of a process that's
already supposed to be selective.

Worse: if `trim_memory_if_needed()` ever fires, it silently discards entries the LLM
already decided were worth keeping permanently. That's the opposite of what we want.

---

## Recommended Fix

Remove `trim_memory_if_needed()` from `memory_reflect.py` entirely and delete the call
site at line ~237. Trust the reflection LLM to keep MEMORY.md lean.

If MEMORY.md genuinely starts bloating over time, that's a signal the reflection prompt
needs tightening — not that we need a line-count truncation.

---

## Relevant File

`.claude/scripts/memory_reflect.py` — `trim_memory_if_needed()` (lines 80–102) and
its call at approximately line 237.

---

## Bug: `protect_soul()` Wrong Signature

Discovered during reflection test run on 2026-06-12.

**Error:** `protect_soul() takes 1 positional argument but 3 were given`

The `protect_soul()` hook in `memory_reflect.py` is defined to accept 1 argument but the
SDK calls hook callbacks with 3. The function runs but throws errors on every invocation.
Reflection still completes successfully — the bug is noisy but not fatal.

**Fix:** Update the function signature to accept the arguments the SDK passes:
```python
async def protect_soul(event: Any, *args: Any) -> Any:
```
or match whatever the sdk_compat hook callback signature actually expects (check against
other hook implementations in the codebase).
