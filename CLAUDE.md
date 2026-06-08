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
- Use the Pi migration PRD as the runtime adaptation reference: `O:\AI\Dynamous\Courses\workshops\off-claudes-leash\pi-migration-prd.md`.
- Use the worked shim examples here: `O:\AI\Dynamous\Courses\workshops\off-claudes-leash\reference-implementation\`.
- Preserve these behaviors across backends: context injection, memory flush, daily logs, tool safety, chat continuity, heartbeat, reflection, memory search, and deployment scripts.
- Claude-specific names such as `CLAUDE.md` and `.claude/` may remain for workshop compatibility, but they must not imply a hard Claude runtime dependency.
- When the diagram refers to Claude Code or Claude Agent SDK, implement the equivalent through `sdk_compat` and Pi unless explicitly building Claude compatibility.

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
