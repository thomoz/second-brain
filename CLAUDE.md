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
/prime           → load context
/plan-feature    → read PRD + reference code → create .agent/plans/phase-N-name.md
/execute         → build from the detailed plan (never from the PRD directly)
```

Cole's reference code (Phases 3–9): `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\`

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
```

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
