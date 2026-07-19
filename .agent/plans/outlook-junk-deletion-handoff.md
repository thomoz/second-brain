# Handoff: Wire Up Outlook Junk Folder Deletion

## Status: Not started — scan-only tool is live, deletion is intentionally not built yet

## Context

Shaun's Outlook spam filter routes obvious spam to the Junk folder correctly, but a
recurring category of spam (rotating throwaway sender domains, but consistent sender
display names — e.g. "AARP Offer", "Blissy Associate", "CarShield Partner") sits in
Junk indefinitely and needs manual cleanup.

A read-only scan tool was built to find these by keyword (2026-07-05):

- **Rules file**: `.claude/data/outlook_junk_rules.json` — `subject_contains` and
  `sender_contains` keyword arrays, case-insensitive substring match. Already has 13
  working sender-name keywords configured and validated against the live mailbox
  (13/13 matched real spam, zero false positives).
- **Code**: `.claude/scripts/integrations/outlook.py`
  - `list_folder_messages(folder="junkemail")` — reads a specific mail folder via Graph API
  - `load_junk_rules()` / `find_rule_match(msg, rules)` — pure functions, unit tested
  - `scan_junk_folder()` — combines the above, returns `(message, matched_keyword)` pairs
  - CLI: `uv run python -m integrations.outlook junk-scan` — prints matches, deletes nothing
- **Tests**: `.claude/scripts/tests/test_integrations.py::TestOutlookJunkRules`

This has been deliberately stopped short of deletion because `Memory/SOUL.md` has two
hard rules that a deletion feature runs straight into:

```
- Never delete anything, anywhere
- When in doubt, draft and surface for review — never assume permission
```

Building deletion means consciously carving out a narrow, explicit exception to that
rule — not something to do as a side effect of a scan-tool task.

## Remaining Steps

### 1. Add a delete/move function to `outlook.py`
- Graph API: `DELETE /me/messages/{id}` moves to Deleted Items (soft delete, recoverable —
  NOT a permanent purge). Confirm this is the desired behavior vs. permanent delete
  (`?permanentDelete=true` requires separate handling and is not recoverable).
- Add `delete_junk_message(message_id: str) -> bool` alongside the existing read functions.
- Extend `scan_junk_folder()` or add a sibling function that actually acts, e.g.
  `purge_junk_folder(dry_run: bool = True)`.

### 2. Bump OAuth scope and re-auth
- `OUTLOOK_SCOPES` in `.claude/scripts/config.py` is currently `["Mail.Read"]`.
- Change to `["Mail.ReadWrite"]` (or add alongside Read).
- Re-run `python .claude/scripts/integrations/setup_auth.py` (or `outlook.py auth`) to
  get a new token with the expanded scope — the existing cached token won't have it.
- Note: OAuth app is in Testing mode — tokens expire every 7 days regardless
  (see CLAUDE.md), so this will need periodic re-auth either way.

### 3. Decide the trigger model — ASK SHAUN, don't assume
Options discussed but not decided:
- **On-demand only**: Shaun runs a command (e.g. `junk-scan --delete` or a new
  `junk-clean` command) whenever he wants a pass done. Safest, most consistent with
  Advisor mode.
- **Heartbeat-automatic**: runs on the existing heartbeat schedule, deletes matches
  with no confirmation step. Fastest, but fully autonomous — the biggest departure
  from current behavior.
- **Heartbeat-detects, asks first**: heartbeat scans and surfaces matches (e.g. via
  WhatsApp notification or daily log entry), Shaun confirms, then a follow-up command
  or reply triggers the actual deletion. Matches "draft and surface for review" most
  closely but requires wiring a confirmation round-trip (chat bot or next-session review).

### 4. Amend `Memory/SOUL.md`
- Current rule: `- Never delete anything, anywhere`
- Needs a narrow, explicit carve-out, e.g.:
  `- Never delete anything, anywhere, except Outlook Junk folder messages matching
  configured keyword rules in outlook_junk_rules.json`
- This is a deliberate, explicit edit Shaun should approve the exact wording of —
  don't quietly reinterpret the existing rule.
- `soul-protect.py` hook blocks automated agents from editing SOUL.md — this edit
  needs to happen in a normal interactive session, not from heartbeat/reflection.

## Validation (once built)

```powershell
# Confirm scope upgrade took effect
uv run python -m integrations.outlook auth

# Dry run first — must show the same output as today's junk-scan
uv run python -m integrations.outlook junk-scan

# Then the real thing, once trigger model is decided and SOUL.md is amended
uv run python -m integrations.outlook junk-clean   # or whatever the final command is named
```

Re-run the full test suite before considering this done:
```powershell
uv run --project .claude/scripts pytest .claude/scripts/tests -q
```

## Open Questions for Shaun (resolve before implementing)

1. Soft delete (Deleted Items, recoverable) or permanent delete?
2. On-demand command, full heartbeat automation, or heartbeat-detects-then-confirms?
3. Exact SOUL.md wording for the carve-out.
