# Feature: investments.db — Single Source of Truth via VPS-Only Execution

The following plan should be complete, but validate documentation and codebase patterns
and task sanity before implementing. Pay special attention to the exact CLI invocation
strings in the skill files — they are read by the LLM at runtime, so they must stay
copy-pasteable and correct.

## Feature Description

`investments/briefs-finance/data/investments.db` is currently a live SQLite file that
exists as two independent physical copies: one on Shaun's Windows machine (written by
interactive `my-trader`/`briefs-finance` sessions in Claude Code) and one on the VPS
(written continuously by the `goat` and `fourteen-crash-signals-daily-check` systemd
timers). Both copies are nominally reconciled via git, but SQLite is a binary format
git cannot 3-way merge, so every time the two copies must actually be reconciled (a
`deploy.ps1` stash/pop, or a manual "unstick" commit), it jams and requires manual
row-count archaeology to resolve without losing data. This has now happened at least
twice (2026-08-22, 2026-08-23).

This plan removes the second copy entirely rather than getting better at merging it.
`investments.db` will physically exist in exactly one place — the VPS — and will never
again be opened by a process running on Shaun's Windows machine. Interactive
`my-trader`/`briefs-finance` commands, which currently run locally, will instead run
*on* the VPS over SSH, using the exact same access `scripts/deploy.ps1` already uses.
`goat`/`fourteen-crash-signals` need no change — they already run VPS-only. The one
genuine exception is IBKR holdings sync, which must run locally (it talks to IB Gateway
on `127.0.0.1`) — that gets split into a local fetch + a remote write over SSH.

No schema or SQL changes. No Postgres migration. The ~30 files across `goat`,
`my-trader`, `briefs-finance`, and `fourteen-crash-signals-daily-check` that call raw
`sqlite3`/`conn.execute` are untouched — they keep running exactly as they do today,
just always on the VPS.

## User Story

As Shaun, running `my-trader`/`briefs-finance` commands from a local Claude Code
session,
I want those commands to operate on the one real `investments.db` on the VPS instead
of a local copy,
So that the recurring "stuck binary merge conflict" incident (~twice in the last three
days) stops happening at all, without a large, risky rewrite of the database layer.

## Problem Statement

Two independently-writable physical copies of one SQLite file, synced through git,
which cannot merge binary content. `investments.db` is deliberately excluded from the
routine 2-minute vault-sync commit (`.claude/scripts/run_vault_sync.sh:15-21`,
`scripts/sync_vault.ps1:13-21` both scope `git add`/`git commit` to `Memory/` and the
`*.md` report files only) — so in normal operation the file just sits as an
ever-growing uncommitted diff on both machines. It only gets swept into a commit
during a manual "unstick" operation (a `deploy.ps1` `git stash pop` conflict, or an
ad-hoc fix commit), at which point git has no way to 3-way-merge the accumulated
independent binary changes from both sides.

## Solution Statement

Stop maintaining two copies. Make the VPS's copy the only one that exists:

1. Remove `investments.db` from git tracking entirely (`.gitignore` it) — no more
   binary blob in history to conflict on, ever.
2. Add a thin SSH-execution wrapper that runs a `my-trader`/`briefs-finance` CLI
   command on the VPS (same `$VPS`/`$REMOTE_DIR` constants `scripts/deploy.ps1`
   already uses) and streams its stdout/stderr back to the local Claude Code session,
   exactly as if it had run locally.
3. Update the two skills (`my-trader`, `investments`) that currently document local
   `uv run` invocations to use the wrapper instead.
4. Handle the two cases that don't fit the plain "run the same command remotely"
   shape: briefs-finance PDF ingestion (source PDF lives locally, must be copied up
   first) and IBKR holdings sync (must run locally against IB Gateway; only the
   database *write* moves to the VPS).
5. One-time cutover of the current live data (today's stuck divergence) onto the VPS
   copy, using the already-computed safe union merge from this session's diagnosis
   (21 local-only rows across 3 cache tables — see Task 0 below), before local writes
   stop happening.

## Feature Metadata

**Feature Type**: Refactor (execution boundary change, no schema/SQL changes)
**Estimated Complexity**: Medium — small code surface, but the design has real edge
cases (SSH availability, ingestion file transfer, IBKR's local-only constraint) that
must be handled correctly, not just "wrap everything in ssh".
**Primary Systems Affected**: `investments/my-trader`, `investments/briefs-finance`,
`.claude/skills/my-trader/`, `.claude/skills/investments/`, `scripts/` (VPS access
helpers), `.gitignore`
**Dependencies**: OpenSSH client on Windows (already used by `deploy.ps1` — confirms
key-based auth is already configured, no new credential needed)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `scripts/deploy.ps1` (whole file, esp. lines 1-5, 28-38) — `$VPS =
  "secondbrain@137.184.102.104"`, `$REMOTE_DIR = "/home/secondbrain/second-brain"`,
  and the `Invoke-Remote` function (`ssh $VPS $Command`, checks `$LASTEXITCODE`) —
  this is the exact pattern the new wrapper should mirror for consistency and because
  it's proven to already work against this VPS.
- `scripts/deploy.ps1:10-16` — existing comment explaining `investments/` is already
  checked out on the VPS and the shared venv already has `my-trader` +
  `briefs-finance` importable (goat-monitor imports both), but their own
  timers/ingestion were "deliberately never enabled" on VPS. This plan does **not**
  contradict that — it adds on-demand SSH-triggered runs, not new systemd timers.
  Do not add `second-brain-mytrader-monitor.timer` or an ingestion timer as part of
  this work.
- `scripts/systemd/second-brain-goat-monitor.service:8-9` — shows the exact working
  invocation shape already proven on the VPS: `WorkingDirectory=.../investments/goat`
  + `ExecStart=.../investments/.venv/bin/python -m goat.main monitor`. Mirror this
  shape (`cd <pkg dir> && <shared venv>/bin/python -m <pkg>.main <args>`) for the new
  wrapper rather than inventing a new invocation style.
- `.claude/scripts/run_vault_sync.sh:15-21` and `scripts/sync_vault.ps1:13-21` — proof
  that `investments.db` is already excluded from the routine auto-commit path on both
  sides; this confirms removing it from git entirely is a strict simplification, not
  a behavior change to the sync timers.
- `.claude/skills/my-trader/SKILL.md:26-63` — every current local invocation to
  convert, e.g. `uv run --directory investments/my-trader python -m mytrader.main
  find --ticker VRTX`. Convert each one to the SSH wrapper form.
- `.claude/skills/investments/SKILL.md:24-46` — same, for briefs-finance, e.g. `uv run
  python -m scripts.main ingest --path "..."`, `assess --ticker KGC --output
  markdown`.
- `investments/my-trader/mytrader/main.py:8-17` (`_open_conn`) — every my-trader CLI
  command opens its own connection via this helper; irrelevant to change (still runs
  fine once the whole process is on the VPS), but useful to confirm there's no
  local-machine-specific state assumed here beyond `DB_PATH`.
- `investments/briefs-finance/scripts/main.py:9-15` (`cmd_ingest`) — `args.path` is a
  local filesystem path to a PDF; this is the one command whose *input*, not just its
  execution, is local. Needs a file-transfer step before the remote call.
- `investments/briefs-finance/scripts/config.py:10-11` — `.env` is loaded from
  `investments/briefs-finance/.env` (`_HERE.parent / ".env"`) — confirm this same file
  (with `FRED_API_KEY` etc.) already exists on the VPS at
  `/home/secondbrain/second-brain/investments/briefs-finance/.env` (it must, since
  `goat`/`fourteen-crash-signals` already depend on the same macro/FRED config
  running on the VPS today — validate, don't assume).
- `investments/my-trader/mytrader/config.py:521-529` — `IBKR_HOST = "127.0.0.1"`,
  `IBKR_PORT = 4001`. Proves IBKR sync structurally cannot run on the VPS — IB
  Gateway only runs on Shaun's machine. This is the one workflow that must keep a
  local step.
- `investments/my-trader/mytrader/ibkr_sync.py:62-83` (`fetch_positions`) — already a
  pure local read with **no DB access inside it** — it returns
  `list[dict[str, Any]]`. This means the fetch/write split this plan needs is already
  half-done in the existing code; only the *write* side (wherever `main.py`'s
  ibkr-sync command currently calls `holdings_ops.add_or_update_holding` per fetched
  row) needs to move to a remote call. Find that call site in `main.py` before
  implementing Task 3.1 (it wasn't fully read during planning — locate via `grep -n
  "ibkr" investments/my-trader/mytrader/main.py`).
- `investments/my-trader/ibkr-sync-handoff.md:10-11` — explicit design constraint:
  "Local only — this will not run on the VPS or on any schedule." This plan doesn't
  violate that (the *sync trigger* stays local and on-demand) but changes where the
  resulting DB write physically lands.
- `CLAUDE.md` "Key Paths" section, the `Investments DB:` line — needs updating to
  note the file is VPS-only post-migration.
- Memory: `project_investments_db_git_conflict.md` — prior incident record; this plan
  is the structural fix that memory file explicitly says doesn't exist yet.

### New Files to Create

- `scripts/invoke_investments.ps1` — PowerShell wrapper, callable as
  `.\scripts\invoke_investments.ps1 -Package my-trader -Command "find --ticker VRTX"`
  (or a `-Package briefs-finance` equivalent). Runs the equivalent of
  `ssh $VPS "cd $REMOTE_DIR/investments/<pkg-dir> && $REMOTE_DIR/investments/.venv/bin/python -m <module>.main <args>"`,
  streams output live, and exits non-zero if the remote command failed (mirror
  `deploy.ps1`'s `Invoke-Remote` exit-code check). Package-to-module/dir mapping:
  `my-trader` → dir `investments/my-trader`, module `mytrader.main`;
  `briefs-finance` → dir `investments/briefs-finance`, module `scripts.main`.
- `investments/my-trader/mytrader/ibkr_remote_write.py` — small module with one
  function, e.g. `push_positions_remote(positions: list[dict]) -> None`, that
  JSON-serializes the already-fetched local `positions` list, sends it to the VPS
  over SSH (e.g. `ssh $VPS "cd $REMOTE_DIR/investments/my-trader && <venv>/bin/python -m mytrader.ibkr_remote_apply"`
  with the JSON piped via stdin), and surfaces the remote exit code/stderr locally.
- `investments/my-trader/mytrader/ibkr_remote_apply.py` — the remote-side
  counterpart: reads the JSON positions list from stdin, opens the (now genuinely
  local-to-the-VPS) `investments.db` via the existing `_open_conn()`/`holdings_ops`
  path, and applies `add_or_update_holding` per row exactly as the current local code
  path does today. This file only ever runs on the VPS.

### Files to Update

- `.gitignore` — add `investments/briefs-finance/data/investments.db` (mirrors the
  existing `investments/my-trader/monitor_runs.log` ignore entry already present at
  line 18).
- `.claude/skills/my-trader/SKILL.md` — replace every `uv run --directory
  investments/my-trader python -m mytrader.main ...` example (lines 26-60) with the
  `scripts/invoke_investments.ps1 -Package my-trader -Command "..."` equivalent.
- `.claude/skills/investments/SKILL.md` — replace every `uv run python -m
  scripts.main ...` example (lines 24-46) with the `-Package briefs-finance`
  equivalent; the `ingest --path` example additionally needs the scp-then-run note
  (see Task 2.3).
- `investments/my-trader/mytrader/main.py` — locate the ibkr-sync command's write
  step and swap the direct local `holdings_ops.add_or_update_holding` loop for a call
  to `ibkr_remote_write.push_positions_remote(...)`.
- `CLAUDE.md` — update the `Investments DB:` line under Key Paths.

### Patterns to Follow

**Remote invocation shape** (from `second-brain-goat-monitor.service:8-9` and
`deploy.ps1`'s `Invoke-Remote`):
```
ssh secondbrain@137.184.102.104 "cd /home/secondbrain/second-brain/investments/<pkg-dir> && /home/secondbrain/second-brain/investments/.venv/bin/python -m <module>.main <args>"
```

**Exit-code propagation** (from `deploy.ps1:28-38`):
```powershell
function Invoke-Remote {
    param([string]$Command, [switch]$IgnoreFailure)
    $output = ssh $VPS $Command
    $output | ForEach-Object { Write-Host $_ }
    if (-not $IgnoreFailure -and $LASTEXITCODE -ne 0) {
        Write-Host "ERROR: remote command failed (exit $LASTEXITCODE): $Command" -ForegroundColor Red
        exit 1
    }
    return $output
}
```
Reuse this shape in `invoke_investments.ps1` rather than inventing new error handling.

**Constants**: reuse `$VPS = "secondbrain@137.184.102.104"` and `$REMOTE_DIR =
"/home/secondbrain/second-brain"` literally as they appear in `deploy.ps1` — don't
introduce a second source of truth for these values; consider having
`invoke_investments.ps1` dot-source them from a shared constants file if one gets
introduced later, but a literal copy is acceptable for this plan's scope (matches
existing precedent — no shared constants file exists yet).

---

## IMPLEMENTATION PLAN

### Phase 0: Cutover of current live data (do this first, before anything else changes)

The current stuck divergence (analyzed live in this session) is purely additive on
both sides — no table was written by both machines. Origin (VPS) is ahead by 809 rows
across 7 `goat_*`/`signals_*` tables; local is ahead by 21 rows across 3 cache tables
(`holdings_price_history` +16, `news_events_cache` +2, `sec_filing_cache` +3).
`holdings`/`watchlist` (the manually-curated tables) are identical on both sides.

**Tasks:**
- Confirm with Shaun whether to preserve the 21 local-only cache rows (safe, already
  diffed) or just accept the VPS's current file as canonical and let those 3 cache
  tables repopulate naturally on the next local-triggered Monitor run (they're
  regenerable caches, not curated data — losing them costs nothing but a slightly
  cold cache). Recommend preserving them since the diff is already known — low
  effort, zero downside.
- Write the 21 rows into the VPS's live `investments.db` (SSH + a one-off script, or
  scp the 3 tables' rows as SQL `INSERT` statements and apply remotely) rather than
  overwriting the whole file.
- Once the VPS file is confirmed to hold the union of both sides, delete the local
  working-tree copy's git-tracked history association: this is folded into Phase 1's
  `git rm --cached`.

### Phase 1: Remove investments.db from git

**Tasks:**
- `git rm --cached investments/briefs-finance/data/investments.db` (keeps the local
  working-tree file on disk for now — it becomes irrelevant once Phase 2/3 land, but
  don't delete Shaun's data preemptively).
- Add `investments/briefs-finance/data/investments.db` to `.gitignore`.
- Commit this on its own (not bundled with the SSH-wrapper code) so the git-history
  cleanup is independently reviewable.

### Phase 2: SSH remote-execution wrapper + skill updates

**Tasks:**
- Create `scripts/invoke_investments.ps1` per the New Files section above.
- Update `.claude/skills/my-trader/SKILL.md` and `.claude/skills/investments/SKILL.md`
  to use it.
- Special-case briefs-finance `ingest --path <local-pdf>`: the skill instructions must
  say to `scp` the PDF to a scratch path on the VPS
  (`$REMOTE_DIR/investments/briefs-finance/reports/_incoming/`) before invoking
  `ingest --path` with the remote path — add this as an explicit two-command sequence
  in the skill doc, not something the wrapper script silently does (ingestion source
  folder structure — `pro-2025`/`pro-2026` subfolders per the existing skill examples
  — should stay a conscious placement choice, not automated).

### Phase 3: IBKR sync fetch/write split

**Tasks:**
- Locate the ibkr-sync command's current write loop in
  `investments/my-trader/mytrader/main.py` (grep for `ibkr` — not read during
  planning, confirm exact line numbers at implementation time).
- Create `ibkr_remote_apply.py` (VPS-side) and `ibkr_remote_write.py` (local-side) per
  the New Files section.
- Update the `main.py` ibkr-sync command to call `fetch_positions()` (unchanged,
  local) then `ibkr_remote_write.push_positions_remote(positions)` instead of writing
  directly.

### Phase 4: Validation + cleanup

**Tasks:**
- Confirm `/home/secondbrain/second-brain/investments/briefs-finance/.env` exists on
  the VPS with the needed keys (FRED_API_KEY etc.) — don't assume from `goat`
  working; briefs-finance's `.env` load path is its own file
  (`investments/briefs-finance/.env`), distinct from goat's.
- Run every converted skill example end-to-end once against the VPS and confirm
  output matches what the equivalent local run used to produce.
- Update `CLAUDE.md`'s Investments DB path note.
- Leave the stale local `investments.db` file in place (gitignored, untracked) rather
  than deleting it — it's Shaun's data and deleting files outside an explicit request
  is out of scope; mention it to him as safe to delete manually once he's confirmed
  the VPS-only flow works.

---

## STEP-BY-STEP TASKS

### Task 0.1: Diagnose and apply the union merge to the VPS's live file
- **IMPLEMENT**: SSH to the VPS, extract the 21 locally-only rows (already identified
  by ticker/table in this session — `holdings_price_history`, `news_events_cache`,
  `sec_filing_cache`) as INSERT statements from the local working-tree
  `investments.db`, and apply them to the VPS's live file via a one-off `sqlite3`
  call over SSH (`ssh $VPS "sqlite3 $REMOTE_DIR/investments/briefs-finance/data/investments.db < /tmp/merge.sql"`).
- **GOTCHA**: `holdings_price_history`/`news_events_cache`/`sec_filing_cache` may have
  autoincrement `id` primary keys — do NOT insert with the local `id` values (they'll
  collide with the VPS's own autoincrement sequence). Insert the non-id columns only
  and let the VPS's own `id` sequence assign new ids.
- **VALIDATE**: row counts per table on the VPS's file after the merge match
  `base_count + max(local_new, origin_new)` for tables touched by only one side, and
  match `origin_count` unchanged for the 7 VPS-only tables.

### Task 1.1: Untrack investments.db
- **IMPLEMENT**: `git rm --cached investments/briefs-finance/data/investments.db`;
  add the path to `.gitignore` near the existing
  `investments/my-trader/monitor_runs.log` entry.
- **PATTERN**: `.gitignore:18`
- **VALIDATE**: `git status` shows the file as untracked, not modified; `git log --
  investments/briefs-finance/data/investments.db` shows no new commits touching it
  going forward.

### Task 2.1: Create the SSH wrapper
- **IMPLEMENT**: `scripts/invoke_investments.ps1` with `-Package` (`my-trader` |
  `briefs-finance`) and `-Command` (the CLI args string) parameters; resolve
  package→(dir, module) via a small hashtable; build and run the `ssh $VPS "cd ... && .../python -m <module> <command>"`
  string; stream output; propagate exit code.
- **PATTERN**: `scripts/deploy.ps1`'s `Invoke-Remote` function and `$VPS`/`$REMOTE_DIR`
  constants.
- **GOTCHA**: quoting — the remote command string crosses two shells (local
  PowerShell → remote bash via ssh); arguments containing spaces (e.g. `--notes
  "some text"` in `watchlist-add`) must be quoted correctly for the *remote* bash, not
  just the local PowerShell call. Test with a command that has a quoted argument
  before considering this done.
- **VALIDATE**: `.\scripts\invoke_investments.ps1 -Package my-trader -Command "find --ticker VRTX"`
  produces the same assessment output structure as the current local
  `uv run --directory investments/my-trader python -m mytrader.main find --ticker VRTX`
  used to.

### Task 2.2: Update my-trader skill
- **UPDATE**: `.claude/skills/my-trader/SKILL.md` lines 26-60 — replace each `uv run
  --directory investments/my-trader python -m mytrader.main ...` line with
  `.\scripts\invoke_investments.ps1 -Package my-trader -Command "..."`.
- **VALIDATE**: every command in the updated skill file runs successfully via the
  wrapper (spot-check `find`, `watchlist-add`, `holding-buy`, `monitor`).

### Task 2.3: Update investments (briefs-finance) skill, including ingest's file-transfer step
- **UPDATE**: `.claude/skills/investments/SKILL.md` lines 24-46 — replace `uv run
  python -m scripts.main ...` with the `-Package briefs-finance` wrapper form; for
  `ingest --path`, document the preceding `scp` step explicitly
  (`scp <local-pdf> secondbrain@137.184.102.104:/home/secondbrain/second-brain/investments/briefs-finance/reports/<subfolder>/`).
- **VALIDATE**: `assess --ticker KGC`, `score --all`, and a real `ingest --path`
  (scp + remote ingest) round-trip all work.

### Task 3.1: Locate and split the IBKR sync write path
- **IMPLEMENT**: `grep -n "ibkr" investments/my-trader/mytrader/main.py` to find the
  exact command function; extract its current `holdings_ops.add_or_update_holding`
  loop into the new `ibkr_remote_apply.py` (VPS-side entry point), leaving the local
  command to only call `fetch_positions()` + `ibkr_remote_write.push_positions_remote(...)`.
- **PATTERN**: `investments/my-trader/mytrader/ibkr_sync.py:62-83` (`fetch_positions`,
  already local-only, already returns plain dicts — no change needed there).
- **GOTCHA**: `compute_diff` (whatever it currently diffs against — check whether it
  reads the *local* `investments.db`'s current holdings for comparison before
  applying; if so, that read must also move to the remote side, or `ibkr_remote_write`
  needs to fetch the current remote holdings first for the diff to stay meaningful).
- **VALIDATE**: a real (or dry-run, if one exists) IBKR sync produces the same
  `add/update/remove` summary as before, with the actual DB write landing only in the
  VPS's file (confirm via `ssh $VPS` row check pre/post).

### Task 4.1: Confirm VPS environment
- **VALIDATE**: `ssh secondbrain@137.184.102.104 "test -f /home/secondbrain/second-brain/investments/briefs-finance/.env && echo present"`
  prints `present`; `ssh secondbrain@137.184.102.104 "/home/secondbrain/second-brain/investments/.venv/bin/python -c 'import mytrader, scripts'"`
  exits 0 (confirms both packages are importable in the shared venv, as `deploy.ps1`'s
  comment claims).

### Task 4.2: Update CLAUDE.md
- **UPDATE**: `CLAUDE.md`'s `Investments DB:` line to note the file now lives only on
  the VPS and is accessed locally via `scripts/invoke_investments.ps1`.

---

## TESTING STRATEGY

### Unit Tests
No new unit-testable logic beyond `ibkr_remote_write`/`ibkr_remote_apply`'s
serialization boundary — add a small test that a `list[dict]` round-trips through
JSON serialize/deserialize without type loss (dates/Decimals if any appear in
`fetch_positions()`'s output — check its return shape first).

### Integration Tests
Manual, against the real VPS (this is infrastructure/ops work, not something to fake
with a test double — a mocked SSH call would validate nothing real). Every "VALIDATE"
line above IS the integration test for this feature.

### Edge Cases
- VPS unreachable (network down, VPS rebooting): the wrapper should fail loudly with
  a clear error, not hang — confirm `ssh`'s default connect timeout behavior is
  acceptable or set `-o ConnectTimeout=10` explicitly in the wrapper.
- A my-trader command that both reads and writes report `.md` files (e.g. `monitor`,
  `snapshot`) — confirm the resulting `holdings.md`/`watchlist.md`/`monitor-report.md`
  changes on the VPS still flow back to Shaun's local vault via the existing
  `investments/my-trader/*.md` vault-sync path (`run_vault_sync.sh:21` /
  `sync_vault.ps1`) — no new sync mechanism should be needed here, but confirm it
  actually fires within the next 2-minute sync window.
- Ingest with a PDF that needs manual placement into a dated subfolder
  (`pro-2025`/`pro-2026`) — the scp step must land it in the *same* subfolder
  convention the remote `ingest --folder` scan expects.

---

## VALIDATION COMMANDS

### Level 1: Syntax & Style
No new Python type/lint surface beyond the two small `ibkr_remote_*.py` files — run
whatever the `my-trader` package's existing check command is (confirm from
`investments/my-trader/pyproject.toml` at implementation time; likely `ruff`/`mypy`
via `uv run`).

### Level 2: Unit Tests
`uv run --directory investments/my-trader pytest mytrader/tests/` — confirm no
existing tests broke (none of this plan's changes touch `mytrader/tests/conftest.py`'s
tmp-path-backed test DB pattern).

### Level 3: Integration Tests
See "Integration Tests" above — real SSH round-trips, not mocked.

### Level 4: Manual Validation
- Run one command from each of `my-trader` and `briefs-finance` through the new
  wrapper and confirm output.
- Confirm `git status` no longer shows `investments.db` as modified after a VPS-side
  write (it shouldn't show at all — it's untracked).
- Wait one vault-sync cycle (≤2 min) after a remote `monitor` run and confirm the
  updated `.md` reports appear locally.

### Level 5: Additional Validation
None.

---

## ACCEPTANCE CRITERIA

- [ ] `investments.db` is untracked in git and in `.gitignore`
- [ ] Every command previously documented as a local `uv run` in
      `.claude/skills/my-trader/SKILL.md` and `.claude/skills/investments/SKILL.md`
      now runs via `scripts/invoke_investments.ps1` against the VPS and produces
      equivalent output
- [ ] Briefs-finance PDF ingestion works end-to-end (scp + remote ingest)
- [ ] IBKR sync fetch still runs locally (against IB Gateway); the resulting write
      lands only in the VPS's `investments.db`
- [ ] No new systemd timers added on the VPS (this stays on-demand/interactive, per
      `deploy.ps1`'s existing "deliberately never enabled" comment)
- [ ] `CLAUDE.md` and both skill files reflect the new invocation pattern
- [ ] The 21 locally-diagnosed rows from today's stuck divergence are preserved in
      the VPS's canonical file (per Shaun's confirmation in Task 0.1)
- [ ] No regressions in `goat`/`fourteen-crash-signals` (untouched by this plan —
      confirm their timers still run clean after Phase 1's git changes)

## COMPLETION CHECKLIST

- [ ] All tasks completed in order (Phase 0 before Phase 1 — don't untrack the file
      before the union merge is safely applied to the VPS's copy)
- [ ] Each task's validation passed immediately after that task
- [ ] Manual testing confirms every skill example works through the new wrapper
- [ ] Acceptance criteria all met
- [ ] Shaun has confirmed the cutover data-preservation decision (Task 0.1) before
      that step ran

---

## NOTES

- This plan deliberately does **not** migrate to Postgres. An earlier version of this
  investigation proposed that, but a live grep found raw SQLite-dialect SQL
  (`?` placeholders, `INSERT OR IGNORE`/`REPLACE`, `AUTOINCREMENT`) scattered across
  ~30 source files in all four `investments/` packages, not centralized behind one
  interface the way the memory-search database (`.claude/scripts/db.py`'s `MemoryDB`
  protocol) is. Rewriting that surface for Postgres would be a large, high-risk
  change to code that runs unattended against live trading/alert data. The
  SSH-execution approach gets the same "one physical database" outcome with zero SQL
  changes.
- IBKR sync is the one workflow that structurally cannot become "just run it on the
  VPS" — IB Gateway only runs where Shaun is logged in locally. The fetch/write split
  in Phase 3 is the minimum change that keeps it working under the new model.
- The exact line numbers for the IBKR sync command's write loop in `main.py` were not
  located during planning (the file is large; only its first 80 lines were read).
  Task 3.1 starts with a `grep` to find them — do not guess the line numbers.
- Confirm before Phase 4 that `briefs-finance`'s `.env` (distinct file from any other
  package's) actually exists on the VPS — it was inferred as "probably already there"
  from `goat`/`fourteen-crash-signals` needing similar macro config, not confirmed
  directly during planning.
