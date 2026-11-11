# Feature: Outlook Junk Folder Deletion (Heartbeat-Detects, WhatsApp-Confirms)

The following plan should be complete, but it's important to validate documentation and
codebase patterns and task sanity before implementing. Pay special attention to naming of
existing utils/types/models — import from the right files.

## Feature Description

Wires up the final, deliberately-deferred step of the Outlook junk scanner: actually deleting
the matched spam messages. A daily heartbeat-driven scan surfaces keyword-matched Junk folder
messages via WhatsApp, Shaun replies with a bare `"yes"` / `"y"`, and that reply triggers a
soft delete (Graph API default, recoverable from Deleted Items) of every currently-staged
match. This is a narrow, explicit exception to `Memory/SOUL.md`'s "never delete anything,
anywhere" rule — the wording for that exception was approved by Shaun on 2026-11-11 and must
be used verbatim.

## User Story

As Shaun (Second Brain in Advisor mode)
I want the daily Outlook Junk folder scan to surface matches via WhatsApp and delete them the
moment I reply "yes"
So that recurring throwaway-domain spam gets cleaned up without manual Outlook triage, while
deletion still requires my explicit confirmation every single time — never fully autonomous.

## Problem Statement

A read-only scan (`scan_junk_folder()` in `.claude/scripts/integrations/outlook.py`, built
2026-07-05) already finds Junk folder messages matching 13 configured keyword rules with zero
false positives, but nothing acts on the matches — Shaun still deletes them by hand in Outlook.
Building deletion was deliberately stopped short of done because it runs straight into two
`Memory/SOUL.md` hard rules ("Never delete anything, anywhere" and "When in doubt, draft and
surface for review — never assume permission"). All four open questions blocking this
(soft vs. permanent delete, trigger model, SOUL.md wording, confirmation mechanism) were
resolved by Shaun across 2026-11-09 and 2026-11-11 — see "DECISIONS RESOLVED" below.

## Solution Statement

1. Add `delete_junk_message()` to `outlook.py` (Graph API `DELETE /me/messages/{id}`, soft
   delete) and bump `OUTLOOK_SCOPES` to `Mail.ReadWrite`.
2. Add a once-per-day, Python-deterministic junk scan inside `run_heartbeat()`
   (`.claude/scripts/heartbeat.py`) — day-gated the same way `reset_habits_if_new_day()`
   already day-gates the habits reset. On a match, it stages the matched message IDs to a new
   state file and sends a dedicated WhatsApp message (bypassing the LLM-composed heartbeat
   alert entirely, same separation of concerns as the existing `DRAFTS_JSON` handling).
3. Add a deterministic, LLM-bypassing check at the top of
   `ConversationEngine.handle_message()` (`.claude/chat/engine.py`) that mirrors the existing
   `"new conversation thread"` reset-phrase pattern: if the incoming WhatsApp text is an exact
   (not substring) `"yes"` or `"y"` AND a junk-delete batch is currently staged AND that batch
   hasn't expired, delete every staged message and reply with a count. Otherwise fall through
   to normal LLM chat untouched — so an ordinary "yes" in conversation never deletes anything.
4. Amend `Memory/SOUL.md`'s delete rule with the exact approved carve-out wording. This must be
   done in a normal interactive session — `soul-protect.py` blocks `AGENT_INVOKED_BY`-tagged
   (heartbeat/reflection) processes from touching SOUL.md, but an interactive `/execute` run has
   no such env var set, so it is unaffected.

## Feature Metadata

**Feature Type**: Enhancement (completes a deliberately-partial existing feature)
**Estimated Complexity**: Low-Medium — no new package, no new dependency, but touches three
existing hot files (`outlook.py`, `heartbeat.py`, `engine.py`) plus one config file and one
vault file, each requiring surgical precision.
**Primary Systems Affected**: `.claude/scripts/integrations/outlook.py`,
`.claude/scripts/heartbeat.py`, `.claude/chat/engine.py`, `.claude/scripts/config.py`,
`Memory/SOUL.md`
**Dependencies**: None new — `requests` (already used), `msal` (already used, scope change
only).

---

## DECISIONS RESOLVED (read first)

1. **Soft delete only.** Graph API default `DELETE /me/messages/{id}` → Deleted Items,
   recoverable. `?permanentDelete=true` is explicitly out of scope — do not implement it.
2. **Trigger model: heartbeat-detects, asks first.** The daily scan surfaces matches and waits;
   it never deletes on its own. Full autonomy (heartbeat deletes with no confirmation) is an
   explicitly deferred future idea — do not build it now, do not leave a flag for it either.
3. **SOUL.md carve-out wording — approved verbatim, 2026-11-11:**
   `Never delete anything, anywhere, except Outlook Junk folder messages matching configured
   keyword rules in outlook_junk_rules.json.`
   Use exactly this text. Do not paraphrase, expand, or add clauses.
4. **Confirmation mechanism — approved 2026-11-12: a bare `"yes"` or `"y"` WhatsApp reply.**
   Exact-match on the stripped/lowercased message text (trailing `.`/`!` stripped), not a
   substring match — "yes I think so" must NOT trigger a delete. This is a deliberate
   simplicity-over-precision tradeoff Shaun chose knowingly (see NOTES).
5. **A confirm reply deletes every currently-staged match as one batch** — not per-message,
   no message-ID referencing over WhatsApp. This was proposed during planning and not objected
   to.
6. **Scan cadence: piggyback on the existing heartbeat, day-gated — no new systemd timer.**
   Proposed during planning, not objected to. The junk scan runs once per calendar day
   (Sydney time) regardless of how many times heartbeat itself fires (default every 4h during
   active hours, see `HEARTBEAT_INTERVAL_MINUTES`).
7. **Pending-confirmation expiry: 24 hours**, mirroring the existing `DRAFT_EXPIRY_HOURS`
   convention (not reusing that exact constant — a new dedicated one, since the two concerns
   are unrelated and may need to diverge later). If Shaun doesn't reply within 24h, a stray
   late "yes" does nothing; the next day's scan simply re-finds and re-stages the same
   still-undeleted messages (they're still sitting in Junk) and sends a fresh WhatsApp alert.
   This is accepted, expected behavior — not a bug to fix.

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ BEFORE IMPLEMENTING

- `.claude/scripts/integrations/outlook.py` (whole file, 333 lines) — `list_folder_messages`,
  `load_junk_rules`, `find_rule_match`, `scan_junk_folder` (lines 189–259) are the existing
  read-only scan this feature extends. `with_retry` usage pattern (lines 178–186, 203–209,
  268–275) — every Graph API call wraps a `requests` call in `with_retry(lambda: ...)`. CLI
  arg-parsing block (lines 303–333) — mirror this shape for the new CLI validation command.
- `.claude/scripts/shared.py` (lines 55–63) — `with_retry(fn, max_retries=3, base_delay=1.0)`:
  retries, then **re-raises** on final failure — callers must catch, not assume a safe return.
  Lines 110–122 — `load_state(path) -> dict` / `save_state(path, state) -> None`: JSON state
  file helpers, used everywhere in this codebase for exactly this "stage something, read it
  back later" pattern.
- `.claude/scripts/heartbeat.py` (lines 478–519) — `reset_habits_if_new_day(state)`: the
  **day-gate pattern to mirror exactly**. Checks `state.get("last_habits_reset_date")` against
  today's date string, returns `False` (no-op) if already run today.
- `.claude/scripts/heartbeat.py` (lines 519–860) — `run_heartbeat()`: the call site. Note the
  `if dry_run: ...; return` block at lines 598–612 — **the new junk-scan call must go AFTER
  this block**, not before, so `--dry-run` never sends a real WhatsApp message (every other
  WhatsApp-sending call — `send_toast_notification`/`send_whatsapp_notification` at lines
  853–854 — is already past this point; deterministic file-mutating calls like
  `expire_old_drafts()` at line 585 are before it and DO run during dry-run, which is fine but
  is not the pattern we want here).
- `.claude/scripts/heartbeat.py` (lines 351–412) — `parse_and_write_drafts()`: shows the
  existing precedent for "Python handles a structured side-effect deterministically, outside
  the LLM's prose response" — the same shape the junk-scan alert will use (compose text in
  Python, call `send_whatsapp_notification` directly, don't route through the LLM's
  `heartbeat_prompt`).
- `.claude/scripts/notifications.py` (lines 38–45) — `send_whatsapp_notification(message, chat_id="")`:
  the function to call for the staged-matches alert.
- `.claude/chat/engine.py` (lines 203–296) — `handle_message()`: the full message-handling
  flow. Lines 227–231 (injection detection, log-only) and lines 233–243 (reset-phrase
  deterministic early-return) are the **two patterns to combine**: log-then-continue, and
  exact-phrase-match-then-early-return-without-calling-the-LLM.
- `.claude/chat/engine.py` (lines 108–121) — `_is_new_sydney_day()`: shows the existing
  tz-aware datetime comparison idiom to reuse for the 24h pending-expiry check.
- `.claude/scripts/config.py` (lines 100–106) — existing Outlook config block:
  `OUTLOOK_CLIENT_ID`, `OUTLOOK_TENANT_ID`, `OUTLOOK_TOKEN_FILE`, `OUTLOOK_SCOPES = ["Mail.Read"]`
  (**to change**), `OUTLOOK_JUNK_FOLDER`, `OUTLOOK_JUNK_RULES_FILE`.
- `.claude/scripts/config.py` (lines 138–144) — existing `STATE_DIR`-based state file constant
  block (`HEARTBEAT_STATE_FILE`, `REFLECTION_STATE_FILE`, `WHATSAPP_HEALTH_STATE_FILE`,
  `CODEX_HEALTH_STATE_FILE`, `HANDOFF_SURFACED_STATE_FILE`) — add the new state file constant
  here, same naming convention (kebab-case filename, `_STATE_FILE` suffix).
- `.claude/scripts/config.py` (lines 155–156) — `DRAFT_EXPIRY_HOURS = int(_os.getenv(...))`:
  the env-var-overridable-constant pattern to mirror for the new 24h expiry constant.
- `Memory/SOUL.md` (line 12) — `- Never delete anything, anywhere` — the exact line to replace
  with the approved carve-out wording (see Decision 3 above).
- `.claude/hooks/soul-protect.py` (lines 15–20, 46–53) — confirms SOUL.md is only
  write-protected when `AGENT_INVOKED_BY` env var is set (automated agents). A normal
  interactive edit during `/execute` is unaffected — no hook workaround needed.
- `.claude/data/outlook_junk_rules.json` — the live rules file (13 sender keywords, 0 subject
  keywords currently configured). Do not modify its schema.
- `.claude/scripts/tests/test_integrations.py` (lines 79–121) — `TestOutlookJunkRules`: the
  existing test class and its `_make_message()` helper — add new delete tests inside this
  class, reuse the helper.
- `.claude/scripts/tests/test_heartbeat.py` (lines 144–172) — `test_reset_habits_if_new_day_*`:
  the exact day-gate test pattern (monkeypatch a module-level file/constant, pass a `state`
  dict literal, assert the return value and/or state mutation) to mirror for the new junk-scan
  day-gate tests.
- `.claude/scripts/tests/test_chat_engine.py` (lines 83–131) — `test_reset_*`: the exact
  phrase-match test pattern to mirror (patch `engine.query`, assert `mock_query.assert_not_called()`
  on the deterministic-path tests, assert response text).

### New Files to Create

None — this is additive-within-existing-files only. No new modules, no new package.

### Patterns to Follow

**Graph API call pattern** (`outlook.py`, e.g. lines 262–275):
```python
def get_unread_count() -> int:
    import requests
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    result: dict[str, Any] = with_retry(
        lambda: requests.get(f"{GRAPH_BASE}/me/mailFolders/inbox", headers=headers, params={...}).json()
    )
    return int(result.get("unreadItemCount", 0))
```
A `DELETE` call returns `204 No Content` (no JSON body) — do not call `.json()` on the
response; call `.raise_for_status()` instead and let `with_retry` retry/raise on non-2xx.

**State file stage/read-back pattern** (used throughout `heartbeat.py`):
```python
state = load_state(SOME_STATE_FILE)
# ... mutate state ...
save_state(SOME_STATE_FILE, state)
```

**Deterministic early-return-before-LLM pattern** (`engine.py` lines 234–243):
```python
_reset_phrases = ["new conversation thread", "start new conversation"]
if any(phrase in message.text.lower() for phrase in _reset_phrases):
    if existing and not force_new_thread:
        reset_session(existing.agent_session_id)
    yield OutgoingMessage(text="...", channel=message.channel, thread=message.thread)
    return
```
The new junk-confirm check follows this exact shape: check condition, do the side effect
in Python, `yield` one `OutgoingMessage`, `return` — the LLM (`query()`) is never invoked for
this path, matching `mock_query.assert_not_called()` in the existing reset tests.

**Day-gate pattern** (`heartbeat.py` lines 478–486):
```python
def reset_habits_if_new_day(state: dict) -> bool:
    if not HABITS_FILE.exists():
        return False
    today_str = now_local().strftime("%Y-%m-%d")
    last_reset = state.get("last_habits_reset_date", "")
    if last_reset == today_str:
        return False
    # ... do the work, mutate state["last_habits_reset_date"] = today_str ...
```

---

## IMPLEMENTATION PLAN

### Phase 1: Foundation — config + delete primitive

**Tasks:**
- Bump `OUTLOOK_SCOPES` to `["Mail.ReadWrite"]` in `config.py`.
- Add `OUTLOOK_JUNK_PENDING_STATE_FILE` constant to `config.py`.
- Add `OUTLOOK_JUNK_CONFIRM_EXPIRY_HOURS` constant to `config.py`.
- Add `delete_junk_message(message_id: str) -> bool` to `outlook.py`.
- Re-auth: run `setup_auth.py` (or `outlook.py auth`) so the cached token picks up the new
  scope.

### Phase 2: Core Implementation — heartbeat staging

**Tasks:**
- Add `run_outlook_junk_scan(state: dict) -> None` to `heartbeat.py`: day-gate, scan, stage to
  the pending state file, compose and send the WhatsApp alert, log to the daily log.
- Wire the call into `run_heartbeat()` after the `dry_run` early-return block.

### Phase 3: Integration — WhatsApp confirm flow

**Tasks:**
- Add `_check_junk_confirm(project_root, text) -> str | None` to `.claude/chat/engine.py`.
- Wire it into `handle_message()` as a deterministic early-return branch, before the LLM call.

### Phase 4: SOUL.md carve-out

**Tasks:**
- Replace the `- Never delete anything, anywhere` line in `Memory/SOUL.md` with the exact
  approved wording (Decision 3). Do this as a normal interactive edit, not via any
  `AGENT_INVOKED_BY`-tagged process.

### Phase 5: Testing & Validation

**Tasks:**
- Unit tests for `delete_junk_message` (success + failure).
- Unit tests for `run_outlook_junk_scan` day-gating and staging.
- Unit tests for `_check_junk_confirm` (pending+exact-match deletes, no-pending falls through,
  expired falls through, non-exact-match falls through, case-insensitivity).
- Full suite regression run.
- Manual live validation per "VALIDATION COMMANDS" below.

---

## STEP-BY-STEP TASKS

### Task 1: UPDATE `config.py` — scope bump + new constants

- **IMPLEMENT**: Change `OUTLOOK_SCOPES = ["Mail.Read"]` → `OUTLOOK_SCOPES = ["Mail.ReadWrite"]`
  (line 104). Add two new constants near the existing state-file block (after line 144,
  `HANDOFF_SURFACED_STATE_FILE`):
  ```python
  OUTLOOK_JUNK_PENDING_STATE_FILE = STATE_DIR / "outlook-junk-pending-state.json"
  ```
  And near `DRAFT_EXPIRY_HOURS` (after line 156):
  ```python
  OUTLOOK_JUNK_CONFIRM_EXPIRY_HOURS = int(_os.getenv("OUTLOOK_JUNK_CONFIRM_EXPIRY_HOURS", "24"))
  ```
- **PATTERN**: `config.py:138-144` (state file constants), `config.py:155-156` (expiry
  constant).
- **GOTCHA**: `Mail.ReadWrite` is a superset permission grant on the Azure app registration —
  confirm the app registration itself has this scope available (it should, since `Mail.Read`
  was already granted and `Mail.ReadWrite` is the natural escalation within the same Microsoft
  Graph permission family) before re-authing.
- **VALIDATE**: `python -c "import sys; sys.path.insert(0,'.claude/scripts'); from config import OUTLOOK_SCOPES, OUTLOOK_JUNK_PENDING_STATE_FILE, OUTLOOK_JUNK_CONFIRM_EXPIRY_HOURS; print(OUTLOOK_SCOPES, OUTLOOK_JUNK_PENDING_STATE_FILE, OUTLOOK_JUNK_CONFIRM_EXPIRY_HOURS)"`

---

### Task 2: ADD `delete_junk_message()` to `outlook.py`

- **IMPLEMENT**: Add after `scan_junk_folder()` (after line 259):
  ```python
  def delete_junk_message(message_id: str) -> bool:
      """Soft-delete one message via Graph API (moves to Deleted Items, recoverable).

      Returns False on any failure instead of raising, so a caller deleting a batch
      can count partial success instead of aborting on the first error.
      """
      import requests

      token = get_access_token()
      headers = {"Authorization": f"Bearer {token}"}

      def _do() -> None:
          resp = requests.delete(f"{GRAPH_BASE}/me/messages/{message_id}", headers=headers)
          resp.raise_for_status()

      try:
          with_retry(_do)
          return True
      except Exception:
          return False
  ```
- **PATTERN**: `outlook.py:178-186` for the `with_retry(lambda: ...)` shape; note this one
  wraps a `def _do()` instead of a `lambda` because `raise_for_status()` returns `None`, not a
  JSON-able response — keep it as a named inner function for readability, not a lambda with a
  trailing expression.
- **IMPORTS**: `requests` (local import, matching every other function in this file).
- **GOTCHA**: `with_retry` **re-raises** on final failure (`shared.py:61-62`) — the `try/except`
  around `with_retry(_do)` is required, otherwise a persistent failure crashes the whole batch
  deletion instead of just counting that one message as failed.
- **GOTCHA**: Do NOT add `?permanentDelete=true` anywhere — soft delete only (Decision 1).
- **VALIDATE**: `uv run --directory .claude/scripts python -m pytest .claude/scripts/tests/test_integrations.py -k delete_junk -v` (after Task 6 adds the tests)

---

### Task 3: ADD CLI escape hatch to `outlook.py` (manual testing path)

- **IMPLEMENT**: Extend the `__main__` block's `choices` list (line 307) to add
  `"junk-delete-pending"`, and handle it by reading the pending state file directly and
  deleting each staged ID — a manual, pre-WhatsApp way to validate the delete primitive
  end-to-end before wiring the live confirm flow.
  ```python
  elif args.command == "junk-delete-pending":
      from config import OUTLOOK_JUNK_PENDING_STATE_FILE
      from shared import load_state, save_state

      state = load_state(OUTLOOK_JUNK_PENDING_STATE_FILE)
      message_ids = state.get("message_ids", [])
      if not message_ids:
          print("No pending junk messages staged.")
      else:
          deleted = sum(1 for mid in message_ids if delete_junk_message(mid))
          print(f"Deleted {deleted}/{len(message_ids)} staged junk message(s).")
          state["pending"] = False
          state["message_ids"] = []
          save_state(OUTLOOK_JUNK_PENDING_STATE_FILE, state)
  ```
  Also add `"junk-delete-pending"` to the `argparse` `choices` tuple at line 307.
- **WHY**: Lets Shaun (or this implementation's own manual validation step) exercise the real
  delete call against a real staged batch without needing a live WhatsApp round-trip, closing
  the loop the handoff's own "Validation (once built)" section asked for
  (`uv run python -m integrations.outlook junk-clean`-equivalent).
- **GOTCHA**: This CLI path and the WhatsApp confirm path (Task 5) both clear the same pending
  state file the same way — if both exist, a message staged and then manually cleared via CLI
  will correctly report "no pending" if confirmed again via WhatsApp afterward. No special
  coordination needed, `load_state`/`save_state` is the single source of truth either way.
- **VALIDATE**: `uv run --directory .claude/scripts python -m integrations.outlook junk-delete-pending`

---

### Task 4: ADD `run_outlook_junk_scan()` to `heartbeat.py`

- **IMPLEMENT**: Add a new function near `reset_habits_if_new_day` (after it, or immediately
  before `run_heartbeat`):
  ```python
  def run_outlook_junk_scan(state: dict) -> None:
      """Once-per-day Outlook Junk folder scan: stage matches and alert via WhatsApp.

      Deterministic — never deletes. Deletion only happens when Shaun replies "yes"
      on WhatsApp (see engine.py:_check_junk_confirm).
      """
      today_str = now_local().strftime("%Y-%m-%d")
      if state.get("last_junk_scan_date") == today_str:
          return
      state["last_junk_scan_date"] = today_str

      from config import OUTLOOK_JUNK_PENDING_STATE_FILE, OUTLOOK_JUNK_RULES_FILE
      from integrations.outlook import scan_junk_folder

      try:
          matches = scan_junk_folder()
      except Exception as e:
          print(f"[{now_local()}] Outlook junk scan failed (non-fatal): {e}")
          return

      if not matches:
          return

      message_ids = [msg.id for msg, _keyword in matches]
      lines = [f"- [{keyword}] {msg.subject} — {msg.sender}" for msg, keyword in matches]
      body = (
          f"Outlook Junk: {len(matches)} message(s) matched your cleanup rules:\n"
          + "\n".join(lines)
          + f'\n\nReply "yes" to delete all {len(matches)} (soft delete, recoverable '
          "from Deleted Items)."
      )

      pending_state = {
          "pending": True,
          "message_ids": message_ids,
          "staged_at": now_local().isoformat(),
      }
      save_state(OUTLOOK_JUNK_PENDING_STATE_FILE, pending_state)

      send_whatsapp_notification(body)
      append_to_daily_log(f"**[Outlook Junk]** Staged {len(matches)} match(es) for WhatsApp confirmation.")
  ```
- **PATTERN**: `heartbeat.py:478-519` for the day-gate shape (mutate `state[...]` in place, the
  caller's existing `save_state(HEARTBEAT_STATE_FILE, state)` at line 839 persists it — no
  separate save call needed for `last_junk_scan_date` itself).
- **IMPORTS**: `OUTLOOK_JUNK_PENDING_STATE_FILE` from `config` (new, Task 1);
  `scan_junk_folder` from `integrations.outlook` (existing); `save_state` and
  `append_to_daily_log` are already imported at module level in `heartbeat.py` (confirm via
  the existing `from shared import ... save_state` and
  `from shared import append_to_daily_log` imports near the top of the file — if
  `append_to_daily_log` isn't already imported there, add it to the existing `shared` import
  line rather than a fresh one).
- **GOTCHA**: `OUTLOOK_JUNK_RULES_FILE` is imported above but unused directly in this function —
  `scan_junk_folder()` already reads it internally via `load_junk_rules()`. Remove that import
  from the snippet above if you don't end up referencing it (avoid an unused-import lint
  failure).
- **GOTCHA**: `message.id` for Outlook messages (Graph API) can be a long base64-ish string
  containing `/` and `+` — fine for JSON string storage, fine for the Graph `DELETE` URL path,
  no escaping needed because `requests` handles URL-encoding.
- **GOTCHA**: Zero matches → return silently, no WhatsApp alert, no daily log entry — matches
  the "zero-candidate days silent" convention already used by every other scanner in this
  codebase (per project memory on the investments scanners).
- **VALIDATE**: `uv run --directory .claude/scripts python -m pytest .claude/scripts/tests/test_heartbeat.py -k junk_scan -v` (after Task 6)

---

### Task 5: WIRE `run_outlook_junk_scan()` into `run_heartbeat()`

- **IMPLEMENT**: In `run_heartbeat()`, immediately after the `if dry_run: ...; return` block
  ends (after line 612, before the `# Build system context for LLM` comment at line 614), add:
  ```python
  try:
      run_outlook_junk_scan(state)
  except Exception as e:
      print(f"[{now_local()}] Outlook junk scan error (non-fatal): {e}")
  ```
- **LOCATION**: `heartbeat.py`, inside `run_heartbeat()`, right after line 612.
- **GOTCHA**: Must be placed AFTER the `dry_run` return, not before — unlike
  `expire_old_drafts()`/`reset_habits_if_new_day()` (which run before the dry_run check and are
  therefore exercised even during `--dry-run`), this function can send a real WhatsApp message
  and must never fire during a dry run.
- **GOTCHA**: Wrap in try/except so a transient Graph API failure (expired token, network
  blip) never takes down the rest of the heartbeat cycle — same non-fatal error-swallowing
  style already used for the WhatsApp health check and Codex health check at the top of this
  same function (lines 530–547).
- **VALIDATE**: `uv run --directory .claude/scripts python heartbeat.py --dry-run` — confirm no
  WhatsApp send is attempted (check console output / mock in a test) and the dry-run snapshot
  still prints correctly.

---

### Task 6: ADD `_check_junk_confirm()` to `.claude/chat/engine.py`

- **IMPLEMENT**: Add a new module-level function, placed near `_is_new_sydney_day` (after it,
  before the profile-session helpers) since it shares the tz-aware-datetime-comparison idiom:
  ```python
  def _check_junk_confirm(project_root: Path, text: str) -> str | None:
      """If an Outlook junk-delete batch is pending and `text` is a bare yes/y confirmation,
      delete the staged batch and return the confirmation reply text.

      Returns None if nothing should happen here (falls through to normal LLM chat) — no
      pending batch, the batch expired, or the text isn't an exact yes/y match. Exact-match
      only (not substring) so an ordinary conversational "yes" never triggers a delete.
      """
      stripped = text.strip().lower().rstrip(".!")
      if stripped not in ("yes", "y"):
          return None

      from config import OUTLOOK_JUNK_CONFIRM_EXPIRY_HOURS, OUTLOOK_JUNK_PENDING_STATE_FILE, now_local
      from shared import append_to_daily_log, load_state, save_state

      state = load_state(OUTLOOK_JUNK_PENDING_STATE_FILE)
      if not state.get("pending"):
          return None

      staged_at = datetime.fromisoformat(state["staged_at"])
      now = now_local()
      if staged_at.tzinfo is None:
          staged_at = staged_at.replace(tzinfo=now.tzinfo)
      if (now - staged_at).total_seconds() > OUTLOOK_JUNK_CONFIRM_EXPIRY_HOURS * 3600:
          state["pending"] = False
          save_state(OUTLOOK_JUNK_PENDING_STATE_FILE, state)
          return None

      sys.path.insert(0, str(project_root / ".claude" / "scripts"))
      from integrations.outlook import delete_junk_message

      message_ids = state.get("message_ids", [])
      deleted = sum(1 for mid in message_ids if delete_junk_message(mid))

      state["pending"] = False
      state["message_ids"] = []
      save_state(OUTLOOK_JUNK_PENDING_STATE_FILE, state)
      append_to_daily_log(
          f"**[Outlook Junk]** Confirmed via WhatsApp — deleted {deleted}/{len(message_ids)} message(s)."
      )

      if deleted == len(message_ids):
          return f"Deleted {deleted} junk message(s)."
      return f"Deleted {deleted}/{len(message_ids)} junk message(s) — some failed, check the logs."
  ```
- **PATTERN**: `engine.py:234-243` for the deterministic-early-return shape;
  `engine.py:108-121` (`_is_new_sydney_day`) for the tz-aware datetime comparison idiom —
  note that unlike that function, `staged_at` here was always written by `now_local()` in
  Python (Task 4), so it should always be timezone-aware already; the `if staged_at.tzinfo is
  None` guard is defensive only, matching the same defensive style `_is_new_sydney_day` uses
  for "old rows written before this check existed."
- **IMPORTS**: `datetime` is already imported at module level in `engine.py` (line 7,
  `from datetime import datetime`) — no new top-level import needed, only the function-local
  `from config import ...` / `from shared import ...` / `from integrations.outlook import ...`
  imports shown above (matching this file's existing style of local imports inside functions
  rather than heavy module-level imports, e.g. `_save_profile_session_state` does the same).
- **GOTCHA**: `sys` is already imported at module level (line 5) and `_SCRIPTS_DIR` is already
  on `sys.path` (lines 159-162) by the time `handle_message` runs — the
  `sys.path.insert(0, str(project_root / ".claude" / "scripts"))` line in the snippet above is
  actually redundant given `_SCRIPTS_DIR` is computed from `__file__`, not `project_root`, and
  is already inserted at import time. Prefer just `from integrations.outlook import
  delete_junk_message` directly without the extra `sys.path.insert` — only add path
  manipulation if the import actually fails in testing (it shouldn't, since
  `integrations/` lives under `.claude/scripts/`, already on the path).
- **GOTCHA**: `message_ids` could be empty if staging and clearing raced oddly — `sum(...)` over
  an empty list is `0`, and `deleted == len(message_ids)` (`0 == 0`) is `True`, so the "Deleted 0
  junk message(s)." reply is technically correct if slightly odd; not worth special-casing.
- **VALIDATE**: `python -c "import sys; sys.path.insert(0,'.claude/chat'); sys.path.insert(0,'.claude/scripts'); import engine; print('engine ok')"`

---

### Task 7: WIRE `_check_junk_confirm()` into `handle_message()`

- **IMPLEMENT**: In `handle_message()`, immediately after the injection-detection block (after
  line 231, before the `# Conversation thread reset` comment at line 233), add:
  ```python
  # Outlook junk-delete confirmation (deterministic, no LLM call)
  _junk_confirm_reply = _check_junk_confirm(self.project_root, message.text)
  if _junk_confirm_reply is not None:
      yield OutgoingMessage(
          text=_junk_confirm_reply,
          channel=message.channel,
          thread=message.thread,
      )
      return
  ```
- **LOCATION**: `.claude/chat/engine.py`, inside `handle_message()`, between lines 231 and 233.
- **GOTCHA**: Must run BEFORE the `_reset_phrases` check and BEFORE the profile-mode check —
  order doesn't functionally matter here since `"yes"`/`"y"` can't collide with those other
  phrase sets, but placing it first keeps all three deterministic-bypass checks grouped
  together at the top of the function, before any session/LLM setup work begins.
- **GOTCHA**: This path does NOT call `append_to_daily_log` for the raw WhatsApp turn the way
  the normal LLM-response path does at lines 371-376 — `_check_junk_confirm` already logs its
  own daily-log entry (Task 6), so logging again here would double-log. Confirm no duplicate
  log entry after wiring.
- **VALIDATE**: `uv run --directory .claude/scripts python -m pytest .claude/scripts/tests/test_chat_engine.py -k junk_confirm -v` (after Task 8)

---

### Task 8: ADD unit tests — `outlook.py` delete primitive

- **IMPLEMENT**: Add to `TestOutlookJunkRules` in `test_integrations.py` (after line 121):
  ```python
  def test_delete_junk_message_success(self, monkeypatch) -> None:
      import integrations.outlook as outlook

      monkeypatch.setattr(outlook, "get_access_token", lambda: "fake-token")

      class _FakeResponse:
          def raise_for_status(self) -> None:
              return None

      monkeypatch.setattr(outlook.requests, "delete", lambda *a, **k: _FakeResponse())
      assert outlook.delete_junk_message("msg-id-1") is True

  def test_delete_junk_message_failure_returns_false(self, monkeypatch) -> None:
      import integrations.outlook as outlook

      monkeypatch.setattr(outlook, "get_access_token", lambda: "fake-token")

      class _FakeResponse:
          def raise_for_status(self) -> None:
              raise RuntimeError("500 server error")

      monkeypatch.setattr(outlook.requests, "delete", lambda *a, **k: _FakeResponse())
      monkeypatch.setattr(outlook, "with_retry", lambda fn, **k: fn())  # skip real retry/sleep
      assert outlook.delete_junk_message("msg-id-1") is False
  ```
- **GOTCHA**: `outlook.py` does `import requests` **inside** the function body (local import,
  not module-level) — `monkeypatch.setattr(outlook.requests, "delete", ...)` only works if
  `requests` has already been imported into the `outlook` module namespace by the time the test
  patches it. Since Python caches imported modules, `import requests` inside
  `delete_junk_message` binds the already-imported `sys.modules["requests"]` object — patch it
  via `monkeypatch.setattr("requests.delete", ...)` (patching the `requests` module directly,
  not `outlook.requests`) if `outlook.requests` isn't a valid attribute path. Verify which form
  works against this codebase's actual import style before finalizing — check how existing
  tests in `test_integrations.py` already patch `requests.get` for `list_messages`/
  `get_unread_count` tests (if any exist) and mirror that exact form.
- **VALIDATE**: `uv run --directory .claude/scripts python -m pytest .claude/scripts/tests/test_integrations.py -k delete_junk -v`

---

### Task 9: ADD unit tests — `heartbeat.py` junk scan staging

- **IMPLEMENT**: Add to `test_heartbeat.py`, mirroring `test_reset_habits_if_new_day_*`:
  ```python
  def test_run_outlook_junk_scan_skips_same_day(monkeypatch):
      import heartbeat
      from config import now_local

      today = now_local().strftime("%Y-%m-%d")
      state = {"last_junk_scan_date": today}
      called = {"scan": False}
      monkeypatch.setattr(
          "integrations.outlook.scan_junk_folder",
          lambda: called.update(scan=True) or [],
      )
      heartbeat.run_outlook_junk_scan(state)
      assert called["scan"] is False

  def test_run_outlook_junk_scan_no_matches_stays_silent(monkeypatch, tmp_path):
      import heartbeat

      monkeypatch.setattr("integrations.outlook.scan_junk_folder", lambda: [])
      state_file = tmp_path / "pending.json"
      monkeypatch.setattr(heartbeat, "OUTLOOK_JUNK_PENDING_STATE_FILE", state_file)
      sent = {"called": False}
      monkeypatch.setattr(heartbeat, "send_whatsapp_notification", lambda *a, **k: sent.update(called=True))
      heartbeat.run_outlook_junk_scan({})
      assert sent["called"] is False
      assert not state_file.exists()

  def test_run_outlook_junk_scan_stages_and_alerts_on_matches(monkeypatch, tmp_path):
      import heartbeat
      from integrations.outlook import OutlookMessage
      from datetime import datetime, timezone

      msg = OutlookMessage(
          id="msg-1", subject="Claim your prize", sender="AARP Offer",
          sender_email="x@spam.example.com", date=datetime.now(timezone.utc),
          snippet="", is_unread=False, thread_id="t1",
      )
      monkeypatch.setattr("integrations.outlook.scan_junk_folder", lambda: [(msg, "AARP")])
      state_file = tmp_path / "pending.json"
      monkeypatch.setattr(heartbeat, "OUTLOOK_JUNK_PENDING_STATE_FILE", state_file)
      sent = {}
      monkeypatch.setattr(
          heartbeat, "send_whatsapp_notification",
          lambda body, **k: sent.update(body=body) or True,
      )
      heartbeat.run_outlook_junk_scan({})
      assert "msg-1" in state_file.read_text()
      assert "AARP" in sent["body"]
      assert 'Reply "yes"' in sent["body"]
  ```
- **GOTCHA**: `run_outlook_junk_scan` imports `scan_junk_folder` via
  `from integrations.outlook import scan_junk_folder` **inside the function body** — patch the
  target at `integrations.outlook.scan_junk_folder` (the source), not
  `heartbeat.scan_junk_folder` (never bound there), since the import happens fresh on every
  call.
- **GOTCHA**: `OUTLOOK_JUNK_PENDING_STATE_FILE` is imported inside the function too
  (`from config import OUTLOOK_JUNK_PENDING_STATE_FILE`) — monkeypatching
  `heartbeat.OUTLOOK_JUNK_PENDING_STATE_FILE` only works if the function reads it as a
  module-level name resolved at call time via `heartbeat.OUTLOOK_JUNK_PENDING_STATE_FILE`
  rather than a fresh local import shadowing it. **Resolve this before writing the real
  implementation**: prefer importing `OUTLOOK_JUNK_PENDING_STATE_FILE` at module level in
  `heartbeat.py` (alongside its other existing `from config import ...` block near the top of
  the file, e.g. line 51's `HEARTBEAT_STATE_FILE` import) rather than function-locally, so
  tests can `monkeypatch.setattr(heartbeat, "OUTLOOK_JUNK_PENDING_STATE_FILE", ...)` the same
  way other heartbeat tests already patch `heartbeat.HABITS_FILE` etc. Update Task 4's snippet
  accordingly — move that import to the top-level `from config import (...)` block in
  `heartbeat.py` instead of inside `run_outlook_junk_scan()`.
- **VALIDATE**: `uv run --directory .claude/scripts python -m pytest .claude/scripts/tests/test_heartbeat.py -k junk_scan -v`

---

### Task 10: ADD unit tests — `engine.py` confirm flow

- **IMPLEMENT**: Add to `test_chat_engine.py`, mirroring `test_reset_*`:
  ```python
  @pytest.mark.asyncio
  async def test_junk_confirm_no_pending_falls_through_to_llm(engine, store, tmp_path, monkeypatch):
      """Bare 'yes' with no pending batch falls through to normal LLM chat."""
      import engine as engine_module
      from config import OUTLOOK_JUNK_PENDING_STATE_FILE
      monkeypatch.setattr(
          engine_module, "_check_junk_confirm",
          lambda root, text: None,
      )
      with patch("engine.query") as mock_query:
          async for _ in engine.handle_message(_make_incoming("yes")):
              pass
      mock_query.assert_called()  # fell through, LLM was invoked

  @pytest.mark.asyncio
  async def test_junk_confirm_deletes_when_pending(engine, store, tmp_path, monkeypatch):
      """Bare 'yes' with a pending batch deletes it and short-circuits before the LLM."""
      with patch("engine._check_junk_confirm", return_value="Deleted 3 junk message(s)."):
          with patch("engine.query") as mock_query:
              responses = []
              async for msg in engine.handle_message(_make_incoming("yes")):
                  responses.append(msg)
      assert len(responses) == 1
      assert "Deleted 3" in responses[0].text
      mock_query.assert_not_called()

  @pytest.mark.asyncio
  async def test_junk_confirm_non_exact_match_falls_through(engine, store, monkeypatch):
      """'yes I think so' is not an exact match — must not trigger a delete."""
      with patch("engine._check_junk_confirm", wraps=engine._check_junk_confirm) as spy:
          with patch("engine.query") as mock_query:
              async for _ in engine.handle_message(_make_incoming("yes I think so")):
                  pass
      result = spy.spy_return
      assert result is None
      mock_query.assert_called()
  ```
  Plus direct unit tests of `_check_junk_confirm` itself (not through `handle_message`), using
  `tmp_path` + `monkeypatch.setattr("config.OUTLOOK_JUNK_PENDING_STATE_FILE", ...)` to cover:
  pending+not-expired+exact-"yes" deletes; pending+expired falls through and clears `pending`;
  `"y"` (single letter) also matches; `"Yes."` (trailing punctuation, mixed case) also matches;
  `"yes please"` does NOT match.
- **GOTCHA**: `_check_junk_confirm` does its own `from config import OUTLOOK_JUNK_PENDING_STATE_FILE`
  inside the function body (Task 6) — the same monkeypatch-target gotcha as Task 9 applies.
  Either monkeypatch `config.OUTLOOK_JUNK_PENDING_STATE_FILE` directly (works regardless of
  where it's imported from, since the function always does a fresh `from config import ...`
  read), or restructure to import at module level in `engine.py` for easier
  `monkeypatch.setattr(engine_module, ...)`-style patching — **pick one approach and apply it
  consistently to both Task 6 and this task's tests**; patching the source module
  (`config.OUTLOOK_JUNK_PENDING_STATE_FILE`) is simpler here since `_check_junk_confirm`
  deliberately uses function-local imports matching this file's existing style (see Task 6's
  IMPORTS note).
- **VALIDATE**: `uv run --directory .claude/scripts python -m pytest .claude/scripts/tests/test_chat_engine.py -k junk_confirm -v`

---

### Task 11: UPDATE `Memory/SOUL.md`

- **IMPLEMENT**: Replace line 12:
  ```
  - Never delete anything, anywhere
  ```
  with:
  ```
  - Never delete anything, anywhere, except Outlook Junk folder messages matching
    configured keyword rules in outlook_junk_rules.json.
  ```
- **GOTCHA**: Do this edit directly in the current interactive session (not via any script or
  automated agent invocation) — `soul-protect.py` only blocks writes when `AGENT_INVOKED_BY` is
  set in the environment, which it isn't here, but the point stands regardless: this specific
  line is the one Shaun explicitly approved, word for word — do not editorialize it.
- **VALIDATE**: `python -c "from pathlib import Path; t = Path('Memory/SOUL.md').read_text(); assert 'except Outlook Junk folder messages' in t; print('ok')"`

---

## TESTING STRATEGY

### Unit Tests

Follow this codebase's existing `pytest` + `monkeypatch` conventions throughout (no new test
framework, no new fixtures beyond what `test_chat_engine.py`'s `engine`/`store` fixtures
already provide). Every new function gets both a "happy path" and at least one "doesn't fire"
test — the "doesn't fire" cases matter more here than usual, since the whole point of this
feature is a narrow, controlled exception to a blanket safety rule.

### Integration Tests

Run the full suite after each phase to confirm zero regressions in the existing Outlook
read-only scan tests, heartbeat day-gating tests, and chat-engine reset/profile-mode tests —
all three files are being edited, not just extended.

### Edge Cases

- Zero junk matches on a given day → silent, no WhatsApp, no state file write.
- Matches exist but Shaun never replies → next day's scan re-stages and re-alerts (expected).
- Shaun replies "yes" more than 24h after staging → falls through to normal LLM chat, no
  delete, pending flag silently cleared.
- Shaun replies "yes" with no batch ever staged → falls through to normal LLM chat (existing
  behavior, totally unaffected).
- Shaun says "yes" conversationally mid-chat while unrelated to junk (e.g. answering an
  unrelated question) while a batch happens to be pending and not yet expired → **this will
  delete the batch**. This is an accepted, explicitly-chosen tradeoff (Decision 4) — document
  it, do not attempt to silently "fix" it with extra heuristics not requested.
- One message in a staged batch fails to delete (already moved/deleted manually, token
  expired mid-batch, etc.) → partial-success reply ("Deleted 2/3...") rather than an all-or-
  nothing failure; `delete_junk_message` returning `False` for a `404` (already gone) counts as
  a failure under this design, which is acceptable — Shaun sees "2/3" and can shrug it off.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style

```powershell
python -c "import sys; sys.path.insert(0,'.claude/scripts'); import config, heartbeat; print('ok')"
python -c "import sys; sys.path.insert(0,'.claude/chat'); sys.path.insert(0,'.claude/scripts'); import engine; print('ok')"
```

### Level 2: Unit Tests

```powershell
uv run --directory .claude/scripts python -m pytest .claude/scripts/tests/test_integrations.py -k delete_junk -v
uv run --directory .claude/scripts python -m pytest .claude/scripts/tests/test_heartbeat.py -k junk_scan -v
uv run --directory .claude/scripts python -m pytest .claude/scripts/tests/test_chat_engine.py -k junk_confirm -v
```

### Level 3: Full Regression

```powershell
uv run --directory .claude/scripts python -m pytest .claude/scripts/tests -q
```

### Level 4: Manual Validation (live mailbox — run in this order)

```powershell
# 1. Re-auth with the new Mail.ReadWrite scope
uv run --directory .claude/scripts python -m integrations.outlook auth

# 2. Confirm the read-only scan still shows the same matches as before (no behavior change yet)
uv run --directory .claude/scripts python -m integrations.outlook junk-scan

# 3. Dry-run the heartbeat — confirm NO WhatsApp message is sent
uv run --directory .claude/scripts python heartbeat.py --dry-run

# 4. Force a real heartbeat run (first time today) — confirm a WhatsApp alert arrives listing
#    today's junk matches, with "Reply yes to delete all N" wording
uv run --directory .claude/scripts python heartbeat.py --force

# 5. On WhatsApp, reply exactly: yes
#    Confirm: a confirmation reply arrives ("Deleted N junk message(s)."), and the messages
#    have moved from Junk to Deleted Items in Outlook (soft delete, check Deleted Items folder)

# 6. Re-run the scan — confirm the deleted messages no longer match (they're gone from Junk)
uv run --directory .claude/scripts python -m integrations.outlook junk-scan
```

### Level 5: Additional Validation

```powershell
# Confirm the CLI escape hatch works independent of the WhatsApp flow (use on a fresh
# staged batch before testing the live WhatsApp reply, to validate the delete primitive
# in isolation first)
uv run --directory .claude/scripts python -m integrations.outlook junk-delete-pending
```

---

## ACCEPTANCE CRITERIA

- [ ] `OUTLOOK_SCOPES` is `["Mail.ReadWrite"]`; re-auth completed successfully.
- [ ] `delete_junk_message()` soft-deletes via Graph API, returns `bool`, never raises.
- [ ] Heartbeat stages junk matches to a dedicated state file once per calendar day, sends a
  WhatsApp alert listing matches + a "reply yes" instruction, and does NOT do this during
  `--dry-run`.
- [ ] Zero-match days produce no WhatsApp alert and no state-file write.
- [ ] A bare, exact WhatsApp reply of `"yes"` or `"y"` (case-insensitive, trailing `.`/`!`
  tolerated) deletes every currently-staged message and replies with a count — without
  invoking the LLM.
- [ ] A non-exact reply (e.g. `"yes I think so"`) does NOT delete anything and falls through to
  normal LLM chat.
- [ ] A `"yes"`/`"y"` reply more than 24h after staging does NOT delete anything.
- [ ] `Memory/SOUL.md` contains the exact approved carve-out wording, verbatim.
- [ ] All new and existing unit tests pass; full suite shows zero regressions.
- [ ] Live manual validation (Level 4 above) confirms the end-to-end flow against the real
  mailbox: scan → stage → WhatsApp alert → "yes" reply → soft delete → re-scan shows it's gone.

---

## COMPLETION CHECKLIST

- [x] Task 1: `config.py` scope bump + new constants
- [x] Task 2: `delete_junk_message()` added to `outlook.py`
- [x] Task 3: `junk-delete-pending` CLI command added
- [x] Task 4: `run_outlook_junk_scan()` added to `heartbeat.py`
- [x] Task 5: wired into `run_heartbeat()` after the dry-run gate
- [x] Task 6: `_check_junk_confirm()` added to `engine.py`
- [x] Task 7: wired into `handle_message()`
- [x] Task 8: `outlook.py` delete tests
- [x] Task 9: `heartbeat.py` junk-scan tests
- [x] Task 10: `engine.py` confirm-flow tests
- [x] Task 11: `Memory/SOUL.md` carve-out wording applied
- [x] Full test suite passes (315 passed, 6 pre-existing skips, zero regressions)
- [ ] Live manual validation complete — **blocked, requires Shaun**: re-auth with the new
  `Mail.ReadWrite` scope (device code flow needs interactive browser/code entry) and a real
  WhatsApp round-trip against the live mailbox. See VALIDATION COMMANDS Level 4 above.
- [x] Original handoff file (`outlook-junk-deletion-handoff.md`) moved to `.agent/plans/completed/`

---

## NOTES

**Why a bare "yes"/"y" instead of a more specific phrase.** Shaun explicitly asked for a
confirmation that "just needs me to reply yes or y" (2026-11-12) — optimized for a quick
CarPlay/WhatsApp reply over precision. The accepted tradeoff is that any ordinary
conversational "yes" sent while a batch happens to be pending and unexpired will also trigger
the delete. The 24h expiry window bounds how long this risk window stays open, but does not
eliminate it. This was a deliberate, informed choice — do not add extra disambiguation
(e.g. requiring "yes delete junk") without Shaun asking for it first.

**Why heartbeat (day-gated) over a new systemd timer.** This repo already has a working,
tested day-gate pattern (`reset_habits_if_new_day`) and an existing WhatsApp-sending
heartbeat process. A brand-new systemd timer (the pattern other `investments/` scanners use)
would mean a second cron-like process hitting the same Outlook mailbox and the same
WhatsApp-sending path, for no benefit — this feature has no need for sub-daily cadence or
independent scheduling.

**Why the LLM never sees the junk-delete decision.** Every other heartbeat alert is
LLM-composed prose (`heartbeat_prompt` → `response_text`). Deletion is different: it is a
security-sensitive, irreversible-enough (soft delete, but still) action gated by an explicit
SOUL.md carve-out. Keeping the trigger-detection and the delete call fully deterministic
Python — never asking an LLM to decide "should I delete this" — is consistent with how this
codebase already treats `DRAFTS_JSON` (Python parses and writes, LLM only proposes) and with
the Security Phase 8 philosophy of deterministic guards over LLM judgment for anything
irreversible.

**Confidence Score: 7/10.** The three integration points (`outlook.py`, `heartbeat.py`,
`engine.py`) each have clean, well-established patterns to mirror, and the hardest design
question (how does a WhatsApp reply trigger a Python-side action without LLM involvement) has
a direct, already-working precedent in `engine.py`'s existing reset-phrase check. The points
docked: (1) Task 8/9/10's GOTCHA notes flag real uncertainty about exactly how `monkeypatch`
needs to target function-local imports in this codebase's style (needs confirming against
existing test patterns during implementation, not just assumed); (2) the live Graph API
`DELETE` call path (soft delete semantics, exact response shape) is specified from documentation
and existing GET-call patterns in this file but has not been live-tested against Shaun's actual
mailbox during this planning pass, unlike the Finviz-scrape-style plans elsewhere in this
repo which validated their external call live before writing the plan.
