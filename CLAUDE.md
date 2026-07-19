# Shaun Thomson's Second Brain

## Project Description
AI Second Brain for a multi-business founder (SongbookDB, karaoke, music bingo, trivia).
Monitors Gmail (multiple accounts), Outlook, Google Calendar, and WhatsApp.
Drafts email replies and surfaces efficiency/investment insights. Advisor mode only —
all action requires Shaun's explicit review.

## Key Paths
- Memory vault: Memory/
- Entity pages: Memory/entities/
- Topic pages: Memory/topics/
- Decision archives: Memory/decisions/
- Personal profile: Memory/Profile/
- Core memories: Memory/core-memories.md
- Daily logs: Memory/daily/
- Active drafts: Memory/drafts/active/
- Sent drafts: Memory/drafts/sent/
- Expired drafts: Memory/drafts/expired/
- External knowledge wiki: wiki/
- Wiki skill: .claude/skills/llm-wiki/
- Scripts: .claude/scripts/
- Hooks: .claude/hooks/
- Skills: .claude/skills/
- Integrations: .claude/scripts/integrations/
- Data/state: .claude/data/
- State file: .claude/data/state/heartbeat-state.json
- Chat sessions: .claude/data/chat.db
- Phase plans: .agent/plans/
- Project PRD: .agent/plans/second-brain-prd.md

## Project Conventions
- Timezone: Australia/Sydney (AEST UTC+10 / AEDT UTC+11)
- Proactivity: Advisor mode — draft for review, never send or act autonomously
- No secrets, API keys, or tokens in Memory/ vault
- Daily logs: Memory/daily/YYYY-MM-DD.md (append-only, never edit past entries)
- Draft files: YAML frontmatter required (type, source_id, recipient, subject, created, status)
- Checkbox syntax: - [ ] incomplete / - [x] complete
- All email/message drafts go to Memory/drafts/active/ — never sent automatically

## Architecture Rule: Model-Agnostic Runtime
- The Second Brain must not be built as a Claude-only system.
- Use Pi as the primary model-agnostic backend so model/provider choice can change by configuration.
- Any script that needs an LLM must import through `.claude/scripts/sdk_compat.py`, not directly from `claude_agent_sdk`.
- Build the complete Second Brain feature set from the original workshop, but adapt Claude-specific runtime pieces as they are built.
- Use Cole's original repo as the feature reference: `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain`.
- Use Cole's architecture diagram as the visual component/data-flow reference: `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\SecondBrainArchitecture.excalidraw`.
- Phase 2 complete — shim files are in `.claude/scripts/`, no further reference to off-claudes-leash needed.
- Preserve these behaviors across backends: context injection, memory flush, daily logs, tool safety, chat continuity, heartbeat, reflection, memory search, and deployment scripts.
- Claude-specific names such as `CLAUDE.md` and `.claude/` may remain for workshop compatibility, but they must not imply a hard Claude runtime dependency.
- When the diagram refers to Claude Code or Claude Agent SDK, implement the equivalent through `sdk_compat` and Pi unless explicitly building Claude compatibility.

## Build Workflow (PIV Loop — Do Not Skip Steps)

The PRD describes WHAT to build. It is not an implementation guide.
Before implementing any phase, `/core_piv_loop:plan-feature` must be run first —
it reads the PRD + Cole's reference code and produces a detailed plan with gotchas,
validation commands, and per-task acceptance criteria.

```
/prime           â†’ load context
/plan-feature    â†’ read PRD + reference code â†’ create .agent/plans/phase-N-name.md
/execute         â†’ build from the detailed plan (never from the PRD directly)
```

Cole's reference code (Phases 3â€“9): `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\`

## Build Commands

```powershell
# Test hooks (pipe empty JSON to stdin via subprocess)
python -c "import subprocess; subprocess.run(['python','.claude/hooks/session-start-context.py'],input=b'{}')"
python -c "import subprocess; subprocess.run(['python','.claude/hooks/session-end-flush.py'],input=b'{}')"
python -c "import subprocess; subprocess.run(['python','.claude/hooks/pre-compact-flush.py'],input=b'{}')"

# Test context injection
python -c "import sys; sys.path.insert(0,'.claude/scripts'); from session_context import build_context; print(build_context()[:500])"

# Manual memory flush (replace paths as needed)
python .claude/scripts/memory_flush.py <transcript_path> <session_id>

# Memory search (Phase 3)
python .claude/scripts/memory_index.py              # Incremental re-index
python .claude/scripts/memory_index.py --rebuild    # Force full reindex
python .claude/scripts/memory_index.py --stats      # Show index statistics
python .claude/scripts/memory_index.py --test       # Dry run (list files only)
python .claude/scripts/memory_search.py "query"                           # Hybrid search (default)
python .claude/scripts/memory_search.py "query" --mode keyword            # BM25 only
python .claude/scripts/memory_search.py "query" --mode semantic           # Vector only
python .claude/scripts/memory_search.py --path-prefix drafts/sent "query" # Voice-match search
python .claude/scripts/memory_search.py --test                            # Run test queries

# Windows Task Scheduler (run as Administrator once)
powershell -ExecutionPolicy Bypass -File scripts\setup_scheduler_windows.ps1

# Register vault merge driver (run once per machine)
git config merge.concat-both.driver "scripts/git-merge-concat %O %A %B"

# Check Windows scheduled tasks
Get-ScheduledTask | Where-Object TaskName -like "SecondBrain-*" | Select-Object TaskName, State

# After VPS live — disable Windows automation tasks
Disable-ScheduledTask -TaskName "SecondBrain-Heartbeat"
Disable-ScheduledTask -TaskName "SecondBrain-Reflection"
Disable-ScheduledTask -TaskName "SecondBrain-WhatsAppBot"

# VPS management (SSH in first)
sudo systemctl status second-brain-heartbeat.timer
sudo systemctl status second-brain-whatsapp.service
tail -f .claude/scripts/heartbeat_runs.log
tail -f .claude/scripts/vault_sync_runs.log
```

## Security (Phase 8)

Three PreToolUse hooks protect every tool call:
- `block-secrets.py` — blocks Read/Bash/Grep/Edit/Write/Glob on credential files + env-dumping
  bash commands + write-time exfiltration scripts. Uses sys.exit(2).
- `command-guard.py` — blocks destructive Bash commands (rm -rf, git push --force,
  social media POSTs, package installs). Uses sys.exit(2).
- `soul-protect.py` — blocks automated agents from editing SOUL.md. Uses JSON deny.

All external data (Gmail, Calendar, Outlook, WhatsApp) is sanitized via
`sanitize_external_text()` at the integration formatter level before reaching the LLM.
Incoming WhatsApp bot messages are logged if injection patterns are detected.

### Security Test Commands
```powershell
# Test block-secrets (expect exit 2 = blocked)
echo '{"tool_name":"Read","tool_input":{"file_path":".env"}}' | python .claude/hooks/block-secrets.py

# Test command-guard (expect exit 2 = blocked)
echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf Memory/"}}' | python .claude/hooks/command-guard.py

# Test soul-protect (expect JSON deny output)
$env:AGENT_INVOKED_BY="heartbeat"; echo '{"tool_name":"Write","tool_input":{"file_path":"Memory/SOUL.md","content":"x"}}' | python .claude/hooks/soul-protect.py
```

## Integrations (Phase 4)
```powershell
# Auth setup (run once per account, then weekly due to Testing-mode token expiry)
python .claude/scripts/integrations/setup_auth.py --check         # Check auth status
python .claude/scripts/integrations/setup_auth.py                 # Run all auth flows

# Gmail
python .claude/scripts/integrations/query.py gmail list           # All accounts unread (last 24h)
python .claude/scripts/integrations/query.py gmail list --account sbdb --hours 48  # Single account
python .claude/scripts/integrations/query.py gmail unread         # Unread counts per account
python .claude/scripts/integrations/query.py gmail urgent         # Urgent across all accounts

# Calendar
python .claude/scripts/integrations/query.py calendar all         # All 6 calendars (next 24h)
python .claude/scripts/integrations/query.py calendar today       # Personal calendar today
python .claude/scripts/integrations/query.py calendar today --calendar bgk  # Specific calendar

# Outlook
python .claude/scripts/integrations/query.py outlook list         # Outlook inbox
python .claude/scripts/integrations/query.py outlook unread       # Unread count
python .claude/scripts/integrations/query.py outlook urgent       # Unread last 2h
```

WhatsApp bot setup: `GREEN-API (30 min).txt`. If it goes quiet with no errors, see
`GREEN-API-troubleshooting.md` before re-doing setup from scratch.

## External Knowledge Wiki

Navigate via `wiki/index.md`. Use the `llm-wiki` skill to ingest, query, and lint the wiki.

```powershell
# Wiki operations
python .claude/skills/llm-wiki/scripts/wiki_ops.py stats    # Page counts + last ingest
python .claude/skills/llm-wiki/scripts/wiki_ops.py lint     # Health check (broken links, orphans)
python .claude/skills/llm-wiki/scripts/wiki_ops.py validate entities/page-name.md  # Validate single page
```

To ingest new content: drop the source text or URL into the conversation and say "ingest this article".
Raw sources go in `wiki/raw/` — the llm-wiki skill processes them into structured pages.

## Completed Phases

### Phase 1: Memory Foundation (2026-06-03)
Memory vault created at Memory/ with SOUL.md, USER.md, MEMORY.md, BOOTSTRAP.md,
HEARTBEAT.md, HABITS.md. All subdirectory stubs created. BOOTSTRAP.md will run
onboarding on first session to populate email accounts and active projects.

### Phase 2: Model-Agnostic Hooks and Context Persistence (2026-06-08)
Lifecycle hooks (SessionStart, SessionEnd, PreCompact, PreToolUse/soul-protect)
wired via .claude/settings.json. Backend-agnostic shim layer: sdk_compat.py
(selector) + pi_sdk_compat.py (Pi subprocess driver). Shared utilities in
shared.py. Context builder in session_context.py. Background summarizer in
memory_flush.py. Pi safety + memory-hooks TypeScript extensions in pi_ext/.

### Phase 3: Memory Search — Hybrid RAG (2026-06-08)
SQLite + sqlite-vec + FTS5 hybrid search index over Memory/ vault.
embeddings.py (FastEmbed/all-MiniLM-L6-v2, 384-dim), db.py (SQLite + Postgres
abstraction, MemoryDB protocol), memory_index.py (incremental, content-hash
change detection, 400-token chunks/80-token overlap), memory_search.py
(keyword/semantic/hybrid modes, weighted fusion, --path-prefix for voice-matching).

### Phase 8: Security Hardening (2026-06-13)
Two new PreToolUse hooks (`block-secrets.py`, `command-guard.py`) wired into settings.json
alongside soul-protect.py. block-secrets.py: credential file protection + bash exfiltration
patterns + write-time two-step attack defense + Windows PowerShell additions + per-account
Gmail/Outlook token patterns. command-guard.py: imports DANGEROUS_BASH_PATTERNS from shared.py,
blocks rm -rf, package installs, git push --force, social media POST. shared.py extended with
6 new patterns (social media POST, git push force, system dir writes). whatsapp.py
format_messages_for_context() sanitizes text and sender via sanitize_external_text(). engine.py
logs injection detections on incoming WhatsApp messages (never blocks). Tests: 41 new tests
(test_block_secrets.py + test_command_guard.py), 155 total passing.

### Phase 4: Integrations — Gmail + Calendar + Outlook (2026-06-09)
Multi-account Gmail (8 accounts, per-account token_gmail_{name}.json), 6 Google Calendars
(single personal-account OAuth, calendar sharing required for non-personal), Outlook
(MSAL device code flow, outlook_token.json). config.py: LOCAL_TZ alias, GMAIL_ACCOUNTS dict,
GOOGLE_CALENDAR_IDS dict, google_token_file(), OUTLOOK_CLIENT_ID/TENANT_ID constants.
auth.py: account_name param. gmail.py: list_all_accounts(). calendar_api.py:
get_all_calendars_events() + format_all_calendars_for_context(). New: outlook.py,
setup_auth.py, query.py (unified CLI), pyproject.toml, test_integrations.py.
NOTE: OAuth app in Testing mode — tokens expire every 7 days, re-run setup_auth.py weekly.
Calendar sharing (manual step): share non-personal calendars with shaunthommo10@gmail.com.

### Phase 9: Deployment (Windows + VPS + Vault Sync) (2026-06-14)
Windows Task Scheduler (4 tasks) + DigitalOcean VPS systemd (5 units) + git vault sync
with concat-both merge driver for daily logs. Secrets copied via scp; Gmail tokens
auto-refresh headlessly; Outlook MSAL SerializableTokenCache is headless-safe after
initial copy. GREEN-API polling mutex via BOT_LOCK_FILE (machine-local, gitignored).
After VPS live: disable Heartbeat, Reflection, WhatsAppBot Windows tasks; keep VaultSync.
