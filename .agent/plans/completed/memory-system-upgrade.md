# Feature: Memory System Upgrade — Structured Wiki, Profile, Ask Me Questions, External Wiki

The following plan should be complete, but validate codebase patterns and task sanity before implementing.

Pay special attention to:
- All Memory/ file paths must use constants from `config.py` (never hardcode strings)
- Reflection still uses structured output + Python applies changes — Codex backend cannot use named tools
- `file_lock` + `atomic_write` for all Memory/ file writes (from `shared.py`)
- New directories must be added to `ensure_directories()` in `config.py`
- Execute phases in order: A (foundation) → B (profile) → C (ask me questions) → D (wiki)

## Feature Description

Upgrades the Second Brain from a flat-file memory system to a structured wiki-based architecture.
Four interconnected systems:

1. **Structured Memory** — MEMORY.md becomes a lean index (<5KB) pointing to dedicated entity and
   topic pages. Reflection agent routes items intelligently instead of appending everything flat.
2. **Profile System** — `Memory/Profile/` stores deep personal context across 7 life areas,
   injected into every session.
3. **Ask Me Questions** — Coaching skill that builds the profile through one-question-at-a-time
   conversations. Works locally and via WhatsApp. Auto-ends after 10 min silence.
4. **External Knowledge Wiki** — Separate `wiki/` directory for ingesting articles and research.
   No database — compiled wiki IS the search index (Karpathy pattern).

## User Stories

As Shaun's Second Brain,
I want structured, navigable long-term memory about Shaun's businesses, projects, and personal life
So that every session starts with rich context and I can make wise, informed recommendations.

As Shaun,
I want to build a personal profile by answering questions one at a time (by voice while driving)
So that my AI advisor understands who I am, not just what I'm working on.

As Shaun,
I want an external knowledge wiki where I can ingest articles and research
So that business and investment knowledge compounds over time.

## Problem Statement

The current MEMORY.md is a flat append-only file that will grow unbounded. The reflection agent
appends everything to one file with no routing logic. There is no personal profile depth — the AI
knows business config but not Shaun as a person. External knowledge is not captured anywhere.

## Solution Statement

Restructure Memory/ into a wiki with entity pages, topic pages, decision archives, and a Profile
section. Upgrade reflection to route items to the right destination. Build a coaching skill to
populate Profile/ through conversations. Add a separate external wiki.

## Feature Metadata

**Feature Type**: Enhancement + New Capability
**Estimated Complexity**: High
**Primary Systems Affected**: `memory_reflect.py`, `session_context.py`, `config.py`,
  `Memory/` vault, `.claude/chat/engine.py`, `.claude/skills/`
**Dependencies**: No new external libraries — all existing (`shared.py`, `config.py`, `json`, `re`, `pathlib`)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ THESE BEFORE IMPLEMENTING

- `.claude/scripts/config.py` (full file)
  Key: `VAULT_DIR`, `ensure_directories()`, path constant patterns. All new Memory/ subdirs added here.

- `.claude/scripts/memory_reflect.py` (full file, 307 lines)
  Key: `parse_reflection_response()` (line 111), `apply_memory_additions()` (line 127),
  `apply_user_updates()` (line 138), `run_reflection()` (line 154), `reflection_prompt` (line 187).
  New routing functions mirror these patterns exactly.

- `.claude/scripts/shared.py` (full file)
  Key: `file_lock` (line 13), `atomic_write` (line 58), `load_state` (line 79), `save_state` (line 87).
  All file writes must use these.

- `.claude/scripts/session_context.py` (full file, 99 lines)
  Key: `build_context()` (line 54) — reads SOUL.md, USER.md, MEMORY.md, HEARTBEAT.md, recent logs.
  Must add core-memories.md and Profile/ injection here.

- `.claude/chat/engine.py` (full file)
  Key: `handle_message()` method, system prompt construction. Add "Ask Me Questions" detection here.

- `Memory/SOUL.md` — will receive new Memory Recall Protocol section.

- `Memory/MEMORY.md` — will be rewritten as lean index.

- `Memory/Projects/songbookdb.md`, `hosting-growth.md`, `karaoke-night-app.md`, `creative-work.md`
  — content to migrate to entities/ or topics/.

- `Memory/Wealth/portfolio.md` — content to migrate to `Memory/topics/investment-strategy.md`.

- `Memory/Businesses/Sole Trader/Hosting/venues_for_all_shows.md`
  — content to migrate to `Memory/entities/venues.md`.

- `.claude/scripts/tests/test_memory_reflect.py` — test pattern to mirror for new tests.
  Uses `tmp_path` + monkeypatch of module-level path constants.

- `O:\AI\Dynamous\Courses\workshops\second-brain-memory-deep-dive\internal-memory-system-prd.md`
  — Cole's reference PRD. Read architecture section: lean index, entity/topic routing,
  3-mention threshold, core-memories.md, lint checks.

- `O:\AI\Dynamous\Courses\workshops\second-brain-memory-deep-dive\llm-wiki-template\.claude\skills\llm-wiki\SKILL.md`
  — template skill to copy verbatim.

- `O:\AI\Dynamous\Courses\workshops\second-brain-memory-deep-dive\llm-wiki-template\.claude\skills\llm-wiki\scripts\wiki_ops.py`
  — copy verbatim, update only WIKI_DIR path.

- `O:\AI\Dynamous\Courses\workshops\second-brain-memory-deep-dive\llm-wiki-template\wiki\`
  — copy all files (index.md, log.md, overview.md, SCHEMA.md) verbatim.

### New Files to Create

**Memory vault:**
- `Memory/entities/` — directory with migrated + new entity pages
- `Memory/topics/` — directory with migrated + new topic pages
- `Memory/decisions/` — directory with 2026-Q2.md stub
- `Memory/Profile/` — directory with 7 seeded files
- `Memory/core-memories.md` — permanent user-initiated memories
- `Memory/GUIDE.md` — human-readable filing reference

**Scripts:**
- `.claude/scripts/memory_lint.py` — internal memory health check
- `.claude/scripts/tests/test_memory_lint.py` — lint tests

**Skills:**
- `.claude/skills/ask-me-questions/SKILL.md` — coaching skill

**External wiki (copy from Cole's template):**
- `wiki/` directory structure
- `.claude/skills/llm-wiki/` (with updated WIKI_DIR path in wiki_ops.py)

### Files to Modify

- `.claude/scripts/config.py` — add ENTITIES_DIR, TOPICS_DIR, DECISIONS_DIR, PROFILE_DIR,
  CORE_MEMORIES_FILE, GUIDE_FILE; update ensure_directories()
- `.claude/scripts/session_context.py` — inject core-memories.md + Profile/ files
- `.claude/scripts/memory_reflect.py` — expanded JSON schema + routing functions
- `Memory/SOUL.md` — add Memory Recall Protocol section
- `Memory/MEMORY.md` — rewrite as lean index
- `.claude/chat/engine.py` — add "Ask Me Questions" phrase detection + profile mode
- `CLAUDE.md` — add wiki/ to Key Paths

### Patterns to Follow

**Path constants** (all new dirs follow existing config.py pattern):
```python
ENTITIES_DIR = VAULT_DIR / "entities"
TOPICS_DIR = VAULT_DIR / "topics"
DECISIONS_DIR = VAULT_DIR / "decisions"
PROFILE_DIR = VAULT_DIR / "Profile"
CORE_MEMORIES_FILE = VAULT_DIR / "core-memories.md"
GUIDE_FILE = VAULT_DIR / "GUIDE.md"
```

**Entity/topic page frontmatter** (every entity/topic page must have this header):
```yaml
---
title: SongbookDB
type: entity
category: project
created: 2026-06-03
updated: 2026-06-17
related: []
tags: [project, software, karaoke]
---
```

**Atomic section update** (for MEMORY.md active items — mirrors apply_memory_additions pattern):
```python
def update_memory_active_items(items: list[str]) -> bool:
    if not items:
        return False
    with file_lock(MEMORY_FILE):
        current = MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else ""
        marker = "## Active Items"
        if marker in current:
            idx = current.index(marker)
            next_section = current.find("\n## ", idx + len(marker))
            footer_idx = current.rfind("\n---")
            insert_at = next_section if next_section != -1 else (footer_idx if footer_idx != -1 else len(current))
            new_items_str = "\n" + "\n".join(items)
            updated = current[:insert_at] + new_items_str + current[insert_at:]
        else:
            updated = current.rstrip() + "\n\n## Active Items\n\n" + "\n".join(items) + "\n"
        atomic_write(MEMORY_FILE, updated)
    return True
```

**Mention count pre-computation** (Python does this before LLM call in reflection):
```python
def count_file_mentions(name: str) -> int:
    """Count how many Memory/ files contain this name (case-insensitive)."""
    count = 0
    if not VAULT_DIR.exists():
        return 0
    for md_file in VAULT_DIR.rglob("*.md"):
        try:
            if name.lower() in md_file.read_text(encoding="utf-8").lower():
                count += 1
        except OSError:
            pass
    return count
```

**Test pattern** (from existing test_memory_reflect.py — monkeypatch module-level paths):
```python
def test_something(tmp_path, monkeypatch):
    import memory_reflect
    monkeypatch.setattr(memory_reflect, "MEMORY_FILE", tmp_path / "MEMORY.md")
    monkeypatch.setattr(memory_reflect, "ENTITIES_DIR", tmp_path / "entities")
    (tmp_path / "entities").mkdir()
    ...
```

---

## IMPLEMENTATION PLAN

### Phase A: Structured Memory Foundation
Config, directory structure, content migration, MEMORY.md restructure, SOUL.md update,
session context update, reflection routing upgrade, lint script.

### Phase B: Profile System
Depends on Phase A. Seed Memory/Profile/ files; update reflection permanence rule.

### Phase C: Ask Me Questions
Depends on Phase B (Profile/ files exist to write into).

### Phase D: External Knowledge Wiki
Independent of A/B/C — install after A is stable.

---

## STEP-BY-STEP TASKS

### TASK 1 — UPDATE `config.py`: Add new path constants

**File**: `.claude/scripts/config.py`

After the existing draft directory constants, add:
```python
# Structured memory directories
ENTITIES_DIR = VAULT_DIR / "entities"
TOPICS_DIR = VAULT_DIR / "topics"
DECISIONS_DIR = VAULT_DIR / "decisions"
PROFILE_DIR = VAULT_DIR / "Profile"
CORE_MEMORIES_FILE = VAULT_DIR / "core-memories.md"
GUIDE_FILE = VAULT_DIR / "GUIDE.md"
```

Also update `ensure_directories()` to include:
```python
ENTITIES_DIR, TOPICS_DIR, DECISIONS_DIR, PROFILE_DIR,
```
alongside the existing dirs list.

- **VALIDATE**: `cd .claude/scripts && python -c "from config import ENTITIES_DIR, TOPICS_DIR, DECISIONS_DIR, PROFILE_DIR, CORE_MEMORIES_FILE; print('ok')"`

---

### TASK 2 — CREATE: New Memory directory stubs

Create `.gitkeep` files in each new directory to ensure git tracks them:
- `Memory/entities/.gitkeep`
- `Memory/topics/.gitkeep`
- `Memory/decisions/.gitkeep`
- `Memory/Profile/.gitkeep`

- **VALIDATE**: `ls Memory/entities/ Memory/topics/ Memory/decisions/ Memory/Profile/`

---

### TASK 3 — MIGRATE: `Memory/Projects/` → `Memory/entities/`

Create each entity page with YAML frontmatter added before existing content.

**`Memory/entities/songbookdb.md`** — from `Memory/Projects/songbookdb.md`:
```yaml
---
title: SongbookDB
type: entity
category: project
created: 2026-06-03
updated: 2026-06-17
related: [[hosting-growth]]
tags: [project, software, karaoke, subscription]
---
```
Then existing content verbatim.

**`Memory/entities/karaoke-night-app.md`** — from `Memory/Projects/karaoke-night-app.md`:
Same frontmatter pattern: `title: Karaoke Night App`, `category: project`.

**`Memory/entities/creative-work.md`** — from `Memory/Projects/creative-work.md`:
`title: Creative Work`, `category: project`, `tags: [music, film, finn-twist]`.

**`Memory/entities/billy-goat-karaoke.md`** — new entity (was only in USER.md/MEMORY.md):
```yaml
---
title: Billy Goat Karaoke
type: entity
category: business
created: 2026-06-03
updated: 2026-06-17
related: [[venues]], [[host-masters-entertainment]]
tags: [business, karaoke, hosting]
---
# Billy Goat Karaoke
Hosted karaoke shows at venues across Sydney.

## Regular Shows
- Boyles Hotel Sutherland — every Thursday at 8pm

## Status
Active
```

**`Memory/entities/dingos-music-bingo.md`** — same pattern for Dingo's Music Bingo.

**`Memory/entities/thommos-trivia.md`** — same pattern for Thommo's Trivia.

**`Memory/entities/host-masters-entertainment.md`** — umbrella entity:
```yaml
---
title: Host Masters Entertainment
type: entity
category: business
created: 2026-06-03
updated: 2026-06-17
related: [[billy-goat-karaoke]], [[dingos-music-bingo]], [[thommos-trivia]]
tags: [business, entertainment, umbrella]
---
# Host Masters Entertainment
Umbrella entity covering all hosted live entertainment shows (karaoke, music bingo, trivia).

## Businesses
- [[billy-goat-karaoke]] — hosted karaoke
- [[dingos-music-bingo]] — hosted music bingo
- [[thommos-trivia]] — hosted trivia

## Status
Active — sole trader structure
```

- **GOTCHA**: Do NOT delete old Projects/ files yet — do that in Task 5 after verifying migration.
- **VALIDATE**: `ls Memory/entities/` should show 7+ .md files (not counting .gitkeep)

---

### TASK 4 — MIGRATE: `Memory/Wealth/` + `Memory/Projects/hosting-growth.md` → `Memory/topics/`

**`Memory/topics/investment-strategy.md`** — from `Memory/Wealth/portfolio.md`:
```yaml
---
title: Investment Strategy
type: topic
created: 2026-06-03
updated: 2026-06-17
related: [[hosting-growth]]
tags: [investment, wealth, portfolio, strategy]
---
```
Then existing portfolio.md content verbatim.

**`Memory/topics/hosting-growth.md`** — from `Memory/Projects/hosting-growth.md`:
```yaml
---
title: Hosting Growth Strategy
type: topic
created: 2026-06-03
updated: 2026-06-17
related: [[billy-goat-karaoke]], [[dingos-music-bingo]], [[thommos-trivia]]
tags: [hosting, growth, venues, shows]
---
```
Then existing hosting-growth.md content verbatim.

**`Memory/entities/venues.md`** — from `Memory/Businesses/Sole Trader/Hosting/venues_for_all_shows.md`:
```yaml
---
title: Venues
type: entity
category: reference
created: 2026-06-03
updated: 2026-06-17
related: [[billy-goat-karaoke]], [[dingos-music-bingo]], [[thommos-trivia]]
tags: [venues, hosting, shows]
---
```
Then venues content verbatim.

- **VALIDATE**: `ls Memory/topics/` shows investment-strategy.md and hosting-growth.md

---

### TASK 5 — REMOVE: Retire old folder structure

After verifying all content migrated in Tasks 3-4:

Use `git rm` (NOT `rm`) to remove old files so git tracks the deletions:
```powershell
git rm -r Memory/Projects/ Memory/Wealth/ "Memory/Businesses/"
git rm Memory/Content/.gitkeep Memory/Clients/.gitkeep Memory/Goals/.gitkeep Memory/Research/.gitkeep
```

- **GOTCHA**: `rm -rf` is blocked by command-guard.py hook. Must use `git rm`.
- **GOTCHA**: `Memory/Clients/`, `Memory/Goals/`, `Memory/Research/` directories themselves:
  after `git rm` of `.gitkeep` files, git removes the empty dirs automatically.
- **VALIDATE**: `git status` shows files as deleted. Old directories no longer present.

---

### TASK 6 — REWRITE: `Memory/MEMORY.md` as lean index

Replace the entire file with the following content (preserving existing active state):

```markdown
# Memory Index

_Active items and pointers to structured memory pages. Always loaded into sessions._

---

## Active Items

_Time-sensitive, unresolved, or needs follow-up. Reflection promotes items here; archive to decisions/ when done._

- (Jun 17) Second Brain nightly reflection running on VPS — structured output via Codex backend
- (Jun 17) VPS: secondbrain@137.184.102.104, dir /home/secondbrain/second-brain
- (Jun 17) Branch: post-creation-tweaks-20260617

## Entity Pages

- [[songbookdb]] — karaoke song list software, ~170 subscribers, code-signing blocker on desktop app
- [[billy-goat-karaoke]] — hosted karaoke, Boyles Hotel Sutherland Thursdays 8pm
- [[dingos-music-bingo]] — hosted music bingo
- [[thommos-trivia]] — hosted trivia nights
- [[host-masters-entertainment]] — umbrella entity for all live entertainment
- [[karaoke-night-app]] — low priority, ToS concerns, early build with Victor Northhead
- [[creative-work]] — FiNN TWiST music + Juno: Wonderdog film, on hold
- [[venues]] — all show venues and distances

## Topic Pages

- [[investment-strategy]] — portfolio, crash-prep strategy, watchlist
- [[hosting-growth]] — venue sales, show efficiency, ad creation bottleneck

## Decision Archives

- [[2026-Q2]] — Q2 2026 decisions (Apr–Jun 2026)

## Preferences

- Communication: brief bullets, no fluff, no end-of-turn recaps
- Deploy target: Windows local + DigitalOcean VPS (cloud sync via git)
- LLM backend: Codex (ChatGPT flat-rate) via codex_sdk_compat.py
- Never auto-send emails, messages, or social posts

---

_Resolve [[name]] → Memory/entities/name.md or Memory/topics/name.md or Memory/decisions/name.md_
_Profile: Memory/Profile/{values,goals,history,personality,health,relationships,finances}.md_
_Core permanent memories: Memory/core-memories.md_
```

- **GOTCHA**: Keep this file under 5KB. It is loaded into every session.
- **VALIDATE**: Size check — file should be under 5000 bytes.

---

### TASK 7 — CREATE: `Memory/core-memories.md`

```markdown
# Core Memories

_Things explicitly asked to remember permanently. Always loaded into every session._
_User-initiated only — say "add to core memories" or "remember this forever"._

---

_(Empty — no permanent memories added yet)_
```

- **VALIDATE**: File exists; readable.

---

### TASK 8 — CREATE: `Memory/GUIDE.md`

Human-readable reference for where things get filed:

```markdown
# Memory Filing Guide

_Quick reference: where does this information go?_

---

## Memory/MEMORY.md — Lean Index
The master table of contents. Always loaded into every session.
- **Active Items**: time-sensitive tasks, unresolved questions, things to follow up
- **Entity/Topic pointers**: [[wiki-links]] to dedicated pages
- **Preferences**: standing communication and system preferences
- Keep under 5KB. Never dump bulk content here.

## Memory/entities/ — People, Projects, Companies, Businesses
One page per noun that accumulates history.
- Each of Shaun's 5 businesses has a page
- Key venues, contractors, clients get pages when they have 3+ mentions
- Projects (SongbookDB features, new show ideas) get pages when active
- Format: YAML frontmatter + Status, Key Decisions, Related sections

## Memory/topics/ — Recurring Themes
One page per theme that spans multiple decisions or sessions.
- Investment strategy, hosting growth, tech architecture
- Think: "this topic keeps coming up" → topic page
- Format: YAML frontmatter + sections organized by theme, not chronology

## Memory/decisions/ — Completed Decision Archives
Quarterly archives of decisions that are done and shipped.
- "Chose X over Y" and it's done → here
- Ongoing decisions with future implications → topic page instead
- Named: 2026-Q2.md, 2026-Q3.md, etc.

## Memory/Profile/ — Personal Profile (Deep)
Long-form answers about who Shaun is as a person.
- values.md, goals.md, history.md, personality.md, health.md, relationships.md, finances.md
- Built via "Ask Me Questions" sessions
- Append with dates — history is valuable, never overwrite
- NEVER expires — always permanent

## Memory/core-memories.md — Permanent Explicit Memories
Small, high-value items explicitly asked to remember forever.
User-initiated only — say "add to core memories" or "remember this forever".

## Memory/daily/ — Raw Daily Logs
Append-only chronological record. One file per day.
Raw material that reflection reviews nightly. Never edit past entries.

## Memory/drafts/ — Email/Message Drafts
Active, sent, and expired draft replies. Never auto-sent.

## Memory/USER.md — Operational Config
Email accounts, business names, integration config, timezone.
NOT personal profile depth (that's Profile/).

## wiki/ — External Knowledge Base
Articles, research papers, investment theses you've ingested.
Completely separate from Memory/. Navigate via wiki/index.md.
Add sources by saying "ingest this article" and providing the text or URL.

---

_When in doubt: specific person/project/business → entities/. Recurring theme → topics/.
Personal depth → Profile/. Finished decision → decisions/. External reading → wiki/._
```

- **VALIDATE**: File exists; renders correctly in Obsidian.

---

### TASK 9 — UPDATE: `Memory/SOUL.md` — add Memory Recall Protocol

Append to the end of SOUL.md:

```markdown

## Memory Recall Protocol (Hard Rule)

When recalling information about Shaun's businesses, projects, people, or themes:

**Step 1** — Check MEMORY.md (always loaded at session start). It lists all entity and topic pages
via [[wiki-links]]. If the question maps to a known page, read it directly:
- Entity page: `Memory/entities/name.md`
- Topic page: `Memory/topics/name.md`
- Profile: `Memory/Profile/filename.md`
These pages are curated and authoritative — prefer them over search.

**Step 2** — For things without a dedicated page (events, conversations, one-off facts), use
`memory_search.py "query"` or read recent daily logs directly.

**Core Memories** — `Memory/core-memories.md` is always loaded at session start. Never modify
without explicit instruction from Shaun.

**Profile** — `Memory/Profile/` holds Shaun's personal depth. Always treat as sensitive and permanent.

**Examples:**
- "What's going on with SongbookDB?" → read `Memory/entities/songbookdb.md`
- "What's the investment strategy?" → read `Memory/topics/investment-strategy.md`
- "What happened last Tuesday?" → search daily logs
- "What are Shaun's core values?" → read `Memory/Profile/values.md`
```

- **VALIDATE**: `Select-String "Memory Recall Protocol" Memory/SOUL.md`

---

### TASK 10 — UPDATE: `session_context.py` — inject core-memories.md + Profile/

**File**: `.claude/scripts/session_context.py`

In `build_context()`, after the existing `memory` injection block, add:

```python
# Core memories — permanent file, always inject if non-empty
core_mem_path = MEMORY_DIR / "core-memories.md"
if core_mem_path.exists():
    core_mem = read_file_safe(core_mem_path)
    if core_mem and "_(Empty" not in core_mem:
        parts.append("## Core Memories\n" + core_mem.strip())

# Profile — inject non-placeholder files for key categories
profile_dir = MEMORY_DIR / "Profile"
if profile_dir.exists():
    profile_parts = []
    for fname in ["values.md", "goals.md", "personality.md", "health.md"]:
        fpath = profile_dir / fname
        if fpath.exists():
            content = read_file_safe(fpath)
            if content and "_(not yet" not in content:
                profile_parts.append(f"### {fname.replace('.md','').title()}\n{content.strip()}")
    if profile_parts:
        parts.append("## Profile\n" + "\n\n".join(profile_parts))
```

- **GOTCHA**: Only inject Profile/ files with real content. Check for `"_(not yet"` placeholder.
- **GOTCHA**: Only inject values, goals, personality, health by default. relationships.md and
  finances.md can be large and sensitive — available on-demand via direct read only.
- **GOTCHA**: Check `MEMORY_DIR` variable name in session_context.py — may be `VAULT_DIR` or
  a local variable. Match the naming used in the existing file exactly.
- **VALIDATE**: `python -c "import sys; sys.path.insert(0,'.claude/scripts'); from session_context import build_context; ctx = build_context(); print(len(ctx), 'chars')"`

---

### TASK 11 — CREATE: `Memory/decisions/2026-Q2.md`

```markdown
---
title: Q2 2026 Decisions
type: decisions
quarter: 2026-Q2
created: 2026-06-17
---

# Q2 2026 Decisions (Apr–Jun 2026)

_Completed decisions with no future action. Archived by daily reflection._

---

- (Jun 17) Chose Codex (ChatGPT flat-rate) as primary LLM backend — replaced Gemini due to quota limits
- (Jun 17) Deployed to DigitalOcean VPS (137.184.102.104) — heartbeat + reflection + WhatsApp bot run there permanently
- (Jun 17) VPS vault sync via git concat-both merge driver — no daily log conflicts
- (Jun 17) Structured output reflection — Codex cannot use named tools; Python applies file changes from JSON
- (Jun 17) PostgreSQL + pgvector on VPS for shared memory search and chat sessions
- (Jun 17) Second Brain memory system upgraded to structured wiki with entity/topic/profile pages
```

- **VALIDATE**: File exists with correct YAML frontmatter.

---

### TASK 12 — UPDATE: `memory_reflect.py` — expanded routing schema

This is the most complex task. Read the full file before editing.

**Step 1: Update imports** — add new path constants after existing config imports:
```python
from config import (
    DAILY_DIR,
    DECISIONS_DIR,   # NEW
    ENTITIES_DIR,    # NEW
    MEMORY_FILE,
    OWNER_NAME,
    PROFILE_DIR,     # NEW
    REFLECTION_STATE_FILE,
    TOPICS_DIR,      # NEW
    USER_FILE,
    VAULT_DIR,
    ensure_directories,
    get_today_log_path,
    now_local,
)
```

**Step 2: Add helper function `get_existing_pages()`** — after `trim_memory_if_needed()`:
```python
def get_existing_pages() -> dict[str, list[str]]:
    """Return stems of existing entity and topic pages for routing context."""
    entities = sorted(p.stem for p in ENTITIES_DIR.glob("*.md")) if ENTITIES_DIR.exists() else []
    topics = sorted(p.stem for p in TOPICS_DIR.glob("*.md")) if TOPICS_DIR.exists() else []
    return {"entities": entities, "topics": topics}
```

**Step 3: Add routing helper functions** — after `apply_user_updates()`, before `run_reflection()`:

```python
def count_file_mentions(name: str) -> int:
    """Count Memory/ files that mention this name (case-insensitive). Used for page creation threshold."""
    count = 0
    if not VAULT_DIR.exists():
        return 0
    for md_file in VAULT_DIR.rglob("*.md"):
        try:
            if name.lower() in md_file.read_text(encoding="utf-8").lower():
                count += 1
        except OSError:
            pass
    return count


def append_to_entity_page(page: str, content: str) -> bool:
    """Append dated bullet to existing entity page. Returns True if wrote."""
    page_path = ENTITIES_DIR / f"{page}.md"
    if not page_path.exists():
        return False
    with file_lock(page_path):
        current = page_path.read_text(encoding="utf-8")
        atomic_write(page_path, current.rstrip() + "\n" + content + "\n")
    return True


def append_to_topic_page(page: str, content: str) -> bool:
    """Append dated bullet to existing topic page. Returns True if wrote."""
    page_path = TOPICS_DIR / f"{page}.md"
    if not page_path.exists():
        return False
    with file_lock(page_path):
        current = page_path.read_text(encoding="utf-8")
        atomic_write(page_path, current.rstrip() + "\n" + content + "\n")
    return True


def append_to_profile_file(filename: str, content: str, date_str: str) -> bool:
    """Append dated section to Profile/ file. Returns True if wrote."""
    profile_path = PROFILE_DIR / f"{filename}.md"
    if not profile_path.exists():
        return False
    with file_lock(profile_path):
        current = profile_path.read_text(encoding="utf-8")
        section = f"\n\n## {date_str} Update\n{content}\n"
        atomic_write(profile_path, current.rstrip() + section)
    return True


def archive_decision(content: str, date_str: str) -> bool:
    """Append completed decision to current quarter archive."""
    month = int(date_str[5:7])
    quarter = f"{date_str[:4]}-Q{(month - 1) // 3 + 1}"
    archive_path = DECISIONS_DIR / f"{quarter}.md"
    DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
    if not archive_path.exists():
        archive_path.write_text(
            f"---\ntitle: {quarter} Decisions\ntype: decisions\nquarter: {quarter}\ncreated: {date_str}\n---\n\n# {quarter} Decisions\n\n",
            encoding="utf-8",
        )
    with file_lock(archive_path):
        current = archive_path.read_text(encoding="utf-8")
        atomic_write(archive_path, current.rstrip() + "\n" + content + "\n")
    return True


def update_memory_active_items(items: list[str]) -> bool:
    """Append items to MEMORY.md ## Active Items section."""
    if not items:
        return False
    with file_lock(MEMORY_FILE):
        current = MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else ""
        marker = "## Active Items"
        if marker in current:
            idx = current.index(marker)
            next_section = current.find("\n## ", idx + len(marker))
            footer_idx = current.rfind("\n---")
            if next_section != -1:
                insert_at = next_section
            elif footer_idx != -1:
                insert_at = footer_idx
            else:
                insert_at = len(current)
            new_items_str = "\n" + "\n".join(items)
            updated = current[:insert_at] + new_items_str + current[insert_at:]
        else:
            updated = current.rstrip() + "\n\n## Active Items\n\n" + "\n".join(items) + "\n"
        atomic_write(MEMORY_FILE, updated)
    return True


def update_memory_preferences(preferences: list[str]) -> bool:
    """Append items to MEMORY.md ## Preferences section."""
    if not preferences:
        return False
    with file_lock(MEMORY_FILE):
        current = MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else ""
        marker = "## Preferences"
        if marker in current:
            idx = current.index(marker)
            next_section = current.find("\n## ", idx + len(marker))
            footer_idx = current.rfind("\n---")
            insert_at = next_section if next_section != -1 else (footer_idx if footer_idx != -1 else len(current))
            updated = current[:insert_at] + "\n" + "\n".join(preferences) + current[insert_at:]
        else:
            updated = current.rstrip() + "\n\n## Preferences\n\n" + "\n".join(preferences) + "\n"
        atomic_write(MEMORY_FILE, updated)
    return True
```

**Step 4: Update `parse_reflection_response()`** — expand return dict to include new keys:
```python
return {
    # New routing keys
    "active_items": data.get("active_items") or [],
    "entity_updates": data.get("entity_updates") or [],
    "topic_updates": data.get("topic_updates") or [],
    "new_entity_pages": data.get("new_entity_pages") or [],
    "new_topic_pages": data.get("new_topic_pages") or [],
    "profile_updates": data.get("profile_updates") or [],
    "decision_archive": data.get("decision_archive") or [],
    "memory_preferences": data.get("memory_preferences") or [],
    # Backward-compat keys (still work, go to dated MEMORY.md section)
    "memory_additions": data.get("memory_additions") or [],
    "user_updates": data.get("user_updates") or [],
    "nothing_to_update": bool(data.get("nothing_to_update", False)),
}
```

**Step 5: Update `reflection_prompt`** — add existing pages context and new output format.

The updated prompt must include:
1. Pre-computed list of existing entity and topic pages (call `get_existing_pages()` before building the prompt in `run_reflection()`)
2. Updated JSON output schema showing all routing fields
3. Routing rules:
   - Content about a specific entity (business, project) matching an existing page → `entity_updates`
   - Recurring theme matching an existing topic page → `topic_updates`
   - Personal statements about values, goals, health, relationships, finances → `profile_updates`
   - Completed decisions (no future action needed) → `decision_archive`
   - Time-sensitive / unresolved items → `active_items`
   - Preference changes → `memory_preferences`
   - Fallback for items that don't fit above → `memory_additions` (dated MEMORY.md section)

Add to prompt:
```python
pages = get_existing_pages()
entity_list = ", ".join(pages["entities"]) or "none yet"
topic_list = ", ".join(pages["topics"]) or "none yet"

reflection_prompt = f"""Daily memory reflection for {owner}'s Second Brain.

Review yesterday's daily log and route items to the correct memory destination.
Respond with a single JSON block and nothing else.

## Existing Entity Pages
{entity_list}

## Existing Topic Pages
{topic_list}

## Current MEMORY.md
{current_memory}

## Current USER.md
{current_user}

## Yesterday's Daily Log ({date_str})
{wrap_external_data(log_content, "daily_logs")}

{TRUST_BOUNDARY_INSTRUCTION}

## Output Format

Respond with ONLY this JSON (no prose, no extra text):

```json
{{
  "active_items": ["- (Mon DD) time-sensitive or unresolved item"],
  "entity_updates": [
    {{"page": "songbookdb", "content": "- (Mon DD) note about SongbookDB"}}
  ],
  "topic_updates": [
    {{"page": "investment-strategy", "content": "- (Mon DD) note about investments"}}
  ],
  "new_entity_pages": [],
  "new_topic_pages": [],
  "profile_updates": [
    {{"file": "goals", "content": "- (Mon DD) goal-related observation"}}
  ],
  "decision_archive": ["- (Mon DD) completed decision — chose X, done"],
  "memory_preferences": ["- preference or standing instruction"],
  "memory_additions": ["- item that doesn't fit above categories"],
  "user_updates": ["- operational config change"],
  "nothing_to_update": false
}}
```

## Routing Rules

- entity_updates: "page" must be a stem from the Existing Entity Pages list above
- topic_updates: "page" must be a stem from the Existing Topic Pages list above
- new_entity_pages / new_topic_pages: only suggest if name appears in 3+ Memory/ files already
- profile_updates: personal statements about values, goals, health, relationships, finances
  "file" must be one of: values, goals, history, personality, health, relationships, finances
- decision_archive: only for COMPLETED decisions — no future action needed
- active_items: time-sensitive, unresolved, needs follow-up
- memory_preferences: standing communication or tool preferences
- memory_additions: fallback for items that don't fit other categories
- Do NOT add anything already present in Current MEMORY.md or Current USER.md
- NEVER include SOUL.md content or personality edits
- Profile/ updates are permanent — most important long-term memory in the system
- If nothing to add: set "nothing_to_update": true with all empty lists
- Keep each item under 120 chars
"""
```

**Step 6: Update the application block in `run_reflection()`** — after `asyncio.run(_run())`:

Replace the existing `wrote_memory = apply_memory_additions(...)` block with:
```python
parsed = parse_reflection_response(response_text)

if parsed.get("_parse_error"):
    print(f"[{now_local()}] Reflection: could not parse LLM response — skipping")
    append_to_daily_log(f"**[Reflection]** Parse error — raw: {response_text[:200]}")
    return

# Route to structured pages
wrote_entity = any(
    append_to_entity_page(u["page"], u["content"])
    for u in parsed["entity_updates"]
    if isinstance(u, dict) and "page" in u and "content" in u
)
wrote_topic = any(
    append_to_topic_page(u["page"], u["content"])
    for u in parsed["topic_updates"]
    if isinstance(u, dict) and "page" in u and "content" in u
)
wrote_profile = any(
    append_to_profile_file(u["file"], u["content"], date_str)
    for u in parsed["profile_updates"]
    if isinstance(u, dict) and "file" in u and "content" in u
)
wrote_decisions = any(archive_decision(d, date_str) for d in parsed["decision_archive"] if d)

# Handle new page creation (verify 3-mention threshold first)
for page_spec in parsed.get("new_entity_pages", []):
    if isinstance(page_spec, dict) and "name" in page_spec and "content" in page_spec:
        if count_file_mentions(page_spec["name"]) >= 3:
            page_path = ENTITIES_DIR / f"{page_spec['name']}.md"
            if not page_path.exists():
                atomic_write(page_path, page_spec["content"])

for page_spec in parsed.get("new_topic_pages", []):
    if isinstance(page_spec, dict) and "name" in page_spec and "content" in page_spec:
        if count_file_mentions(page_spec["name"]) >= 3:
            page_path = TOPICS_DIR / f"{page_spec['name']}.md"
            if not page_path.exists():
                atomic_write(page_path, page_spec["content"])

# MEMORY.md updates
wrote_active = update_memory_active_items(parsed["active_items"])
wrote_prefs = update_memory_preferences(parsed["memory_preferences"])

# Backward compat: old memory_additions still go to dated MEMORY.md section
wrote_memory = apply_memory_additions(parsed["memory_additions"], date_str)
wrote_user = apply_user_updates(parsed["user_updates"], date_str)

trim_memory_if_needed()

wrote_any = any([wrote_entity, wrote_topic, wrote_profile, wrote_decisions,
                 wrote_active, wrote_prefs, wrote_memory, wrote_user])
```

Also update `trim_memory_if_needed()`: the archive path currently uses `VAULT_DIR / "Research"` — change to `VAULT_DIR / "decisions"` to avoid recreating the retired Research/ folder.

- **GOTCHA**: `pages = get_existing_pages()` must be called before building `reflection_prompt` inside `run_reflection()`, not at module level.
- **GOTCHA**: The `allowed_tools=[]` setting stays — Codex backend constraint. Do not add tool calls.
- **VALIDATE**: `python -c "import ast, pathlib; ast.parse(pathlib.Path('memory_reflect.py').read_text()); print('syntax ok')"`
- **VALIDATE**: `python -c "import memory_reflect; print('imports ok')"`
- **VALIDATE**: `uv run pytest tests/test_memory_reflect.py -v`

---

### TASK 13 — UPDATE: `tests/test_memory_reflect.py` — add tests for new routing functions

Add tests covering (add to existing file, do not replace):

- `parse_reflection_response()` with full new schema — all keys present in result
- `append_to_entity_page()` — appends to existing page; returns False if page missing
- `append_to_topic_page()` — mirrors entity test
- `append_to_profile_file()` — appends dated section to existing profile file
- `archive_decision()` — creates quarter file if missing, appends to existing file
- `update_memory_active_items()` — finds `## Active Items` and inserts; creates section if absent
- `update_memory_preferences()` — finds `## Preferences` and inserts
- `count_file_mentions()` — returns correct count across tmp_path files

**All tests must use `tmp_path` + `monkeypatch`:**
```python
def test_append_to_entity_page(tmp_path, monkeypatch):
    import memory_reflect
    monkeypatch.setattr(memory_reflect, "ENTITIES_DIR", tmp_path / "entities")
    (tmp_path / "entities").mkdir()
    page = tmp_path / "entities" / "songbookdb.md"
    page.write_text("# SongbookDB\n")
    result = memory_reflect.append_to_entity_page("songbookdb", "- (Jun 17) test item")
    assert result is True
    assert "test item" in page.read_text()
```

- **VALIDATE**: `uv run pytest tests/test_memory_reflect.py -v` — all tests pass

---

### TASK 14 — CREATE: `.claude/scripts/memory_lint.py`

Standalone health-check script for internal Memory/ structure.

**CLI interface:**
```
python memory_lint.py          # Run all checks, print report
python memory_lint.py --stats  # Print page counts per directory
python memory_lint.py --fix    # Auto-fix: add missing MEMORY.md index entries
```

**Checks to implement:**
1. **Broken wiki-links**: scan all .md files in Memory/ for `[[name]]`; verify
   `entities/name.md` or `topics/name.md` or `decisions/name.md` exists
2. **Index orphans**: pages in entities/ or topics/ not listed in MEMORY.md
3. **Stale active items**: entries in MEMORY.md `## Active Items` with dates > 30 days old
4. **Missing frontmatter**: entity/topic pages without YAML `---` block
5. **Large pages**: pages > 5KB (warn, suggest splitting)

**Pattern**: Mirror `wiki_ops.py` from Cole's template exactly — same argparse structure,
same `cmd_stats()` / `cmd_lint()` functions, same issue-list reporting.
Key difference: resolve `[[name]]` against Memory/entities/, Memory/topics/, Memory/decisions/
(not wiki/entities/, wiki/concepts/).

**Imports**: `argparse`, `re`, `sys`, `pathlib.Path`; import from config:
`VAULT_DIR`, `ENTITIES_DIR`, `TOPICS_DIR`, `DECISIONS_DIR`, `MEMORY_FILE`

```python
# At top of file, after imports:
os.environ.setdefault("AGENT_INVOKED_BY", "memory_lint")

WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
DATE_RE = re.compile(r"\((\w{3})\s+(\d{1,2})\)")  # matches (Jun 17) format

PAGE_DIRS = {
    "entities": ENTITIES_DIR,
    "topics": TOPICS_DIR,
    "decisions": DECISIONS_DIR,
}
```

- **VALIDATE**: `cd .claude/scripts && python memory_lint.py --stats`
- **VALIDATE**: `python memory_lint.py` — runs without errors

---

### TASK 15 — CREATE: `.claude/scripts/tests/test_memory_lint.py`

Tests using `tmp_path` + `monkeypatch` for all check functions.

Cover:
- `check_broken_links()` — detects `[[missing-page]]` as broken; passes for `[[existing-page]]`
- `check_orphan_pages()` — detects page not listed in MEMORY.md index
- `check_stale_active_items()` — detects items with old dates (> 30 days)
- `check_missing_frontmatter()` — detects pages without `---` frontmatter

- **VALIDATE**: `uv run pytest tests/test_memory_lint.py -v`

---

### TASK 16 — CREATE: `Memory/Profile/` seeded files

Create all 7 files with structured headings and placeholder text.

**Template for each file:**
```yaml
---
title: {Title}
type: profile
category: {category}
created: 2026-06-17
updated: 2026-06-17
---
# {Title}

_Built through "Ask Me Questions" sessions. Append with dates — history matters._

## {Section 1}
_(not yet populated — run "ask me questions" to build this)_

## {Section 2}
_(not yet populated)_
```

**Files to create** with appropriate sections:

- `Memory/Profile/values.md` — sections: Core Values, Non-Negotiables, What Matters Most
- `Memory/Profile/goals.md` — sections: 12-Month Goals, 5-Year Vision, Business Goals, Wealth Goals, Lifestyle Goals
- `Memory/Profile/history.md` — sections: Background, Key Turning Points, How I Got Here
- `Memory/Profile/personality.md` — sections: How I Work Best, What Energises Me, What Drains Me, Decision Style
- `Memory/Profile/health.md` — sections: Energy Patterns, Sleep, Fitness, Lifestyle Habits
- `Memory/Profile/relationships.md` — sections: Family, Key People, Support Network
- `Memory/Profile/finances.md` — sections: Full Financial Picture, Income Sources, Financial Goals, Constraints

- **VALIDATE**: `ls Memory/Profile/` shows 7 .md files (not counting .gitkeep)

---

### TASK 17 — UPDATE: `memory_reflect.py` — Profile permanence rule in prompt

In the reflection prompt, the routing rules section must include:
```
- Profile/ updates are the most important long-term memory. Always append, NEVER overwrite.
- When yesterday's log contains any personal statements about values, goals, health, 
  relationships, or finances — route to profile_updates, not memory_additions.
- Treat Profile/ files as permanent. Never suggest archiving or summarising them.
```

This is part of Task 12 — ensure these rules are present in the final prompt text.

---

### TASK 18 — CREATE: `.claude/skills/ask-me-questions/SKILL.md`

```yaml
---
name: ask-me-questions
description: >
  Build Shaun's personal profile through a one-question-at-a-time coaching conversation.
  Trigger: "ask me questions", "ask me a question", "coaching session", "profile building".
  Works locally and via WhatsApp. One question at a time. Auto-ends after 10 min silence (WhatsApp).
---

# Ask Me Questions — Personal Profile Builder

## Purpose

Build a deep personal profile stored in Memory/Profile/ through a coaching-style conversation.
The richer this profile, the better every advisory session becomes.

## Trigger Phrases

- "ask me questions"
- "ask me a question"
- "coaching session"
- "profile building"
- "build my profile"

## Question Philosophy

Think: a skilled coach meeting an important client for the first time.
Start broad (life picture, what's working), move to values, then goals, then specifics.
Business and investment context is highest priority — ask about these first.

## Question Order

1. Current life picture — what's working well, what's frustrating you most right now
2. Business priorities — which of your 5 businesses deserves the most attention and why
3. Investment thinking — what's your plan for the next market cycle
4. Values — what are your absolute non-negotiables in life
5. Goals — where do you want to be in 5 years across business, wealth, and lifestyle
6. Personal history — key turning points that shaped who you are
7. Personality — how do you work best, what energises vs drains you
8. Relationships — who are the key people in your life
9. Health — energy patterns, sleep, fitness
10. Finances — full picture beyond the investment portfolio
11. Open gaps — anything that hasn't come up that I should know

## Behavior Rules

- Ask ONE question per message. Never ask multiple questions at once.
- Wait for the full answer before asking the next question.
- Acknowledge briefly before moving on ("Got it." / "Interesting." / "Good to know.").
- Keep questions open-ended — no yes/no questions.
- Choose which question to ask next based on what's already been covered.
- Session ends when Shaun says "stop", "that's enough", "done", or "end session".
- WhatsApp: session auto-ends after 10 minutes of silence.

## Filing Rules

After each answer:
- Identify the most appropriate Memory/Profile/ file
- Use the section headings in each file as a filing guide
- Append with today's date as a heading: `## YYYY-MM-DD Update`
- Never overwrite existing content
- File immediately — don't wait until end of session

Profile files: values.md, goals.md, history.md, personality.md, health.md,
relationships.md, finances.md

## Starting Message

When triggered, say exactly:
"Ready. I'll ask you one question at a time to build a picture of who you are and what
matters to you. I'll file your answers to your profile as we go. Here's the first question:"

Then ask Question 1.
```

- **VALIDATE**: File exists; YAML frontmatter is valid.

---

### TASK 19 — UPDATE: `.claude/chat/engine.py` — Ask Me Questions phrase detection

Read the full engine.py before editing.

In `handle_message()`, after the injection detection block and before building `system_prompt`,
add:

```python
# Ask Me Questions profile-building mode detection
_AQM_PHRASES = ["ask me questions", "ask me a question", "coaching session", "profile building", "build my profile"]
_is_profile_mode = any(phrase in message.text.lower() for phrase in _AQM_PHRASES)
```

After `system_prompt` is built (after the existing WhatsApp rules block), add:
```python
if _is_profile_mode:
    skill_path = self.project_root / ".claude" / "skills" / "ask-me-questions" / "SKILL.md"
    try:
        skill_text = skill_path.read_text(encoding="utf-8")
        system_prompt += f"\n\n# Profile Building Mode\n{skill_text}"
    except OSError:
        pass
    _save_profile_session_state(self.project_root, channel_id)
else:
    # Update last-message time if in active profile session
    _update_profile_session_timestamp(self.project_root, channel_id)

# Check for 10-min timeout on active profile session
if _check_and_clear_profile_timeout(self.project_root, channel_id):
    yield OutgoingMessage(
        text="Profile session ended (10 min timeout). I've saved everything we covered to your profile. Type 'ask me questions' any time to continue.",
        channel=message.channel,
        thread=message.thread,
    )
    return
```

**Add helper functions** at module level (before the class):

```python
def _profile_session_state_path(project_root: Path) -> Path:
    return project_root / ".claude" / "data" / "state" / "profile-session.json"


def _save_profile_session_state(project_root: Path, channel_id: str) -> None:
    from shared import load_state, save_state
    state_path = _profile_session_state_path(project_root)
    state = load_state(state_path)
    now_str = datetime.now().isoformat()
    state[channel_id] = {"started_at": now_str, "last_message_at": now_str}
    save_state(state_path, state)


def _update_profile_session_timestamp(project_root: Path, channel_id: str) -> None:
    from shared import load_state, save_state
    state_path = _profile_session_state_path(project_root)
    state = load_state(state_path)
    if channel_id in state:
        state[channel_id]["last_message_at"] = datetime.now().isoformat()
        save_state(state_path, state)


def _check_and_clear_profile_timeout(project_root: Path, channel_id: str, timeout_minutes: int = 10) -> bool:
    """Returns True if a profile session exists and has been silent for > timeout_minutes."""
    from shared import load_state, save_state
    state_path = _profile_session_state_path(project_root)
    state = load_state(state_path)
    if channel_id not in state:
        return False
    last = datetime.fromisoformat(state[channel_id]["last_message_at"])
    if (datetime.now() - last).total_seconds() > timeout_minutes * 60:
        del state[channel_id]
        save_state(state_path, state)
        return True
    return False
```

- **GOTCHA**: `datetime` is already imported at the top of engine.py (line 7). Do not re-import.
- **GOTCHA**: `load_state` / `save_state` are in `shared.py` — they're already imported in engine.py.
  Check the existing imports before adding new ones to avoid duplicates.
- **GOTCHA**: The timeout check MUST happen before the `query()` call, otherwise the closing message
  yields after the LLM call (too late).
- **VALIDATE**: `python -c "import sys; sys.path.insert(0,'.claude/chat'); sys.path.insert(0,'.claude/scripts'); from engine import ConversationEngine; print('engine imports ok')"`

---

### TASK 20 — CREATE: External wiki directory structure

1. **Copy skill** from Cole's template:
   Copy entire directory `O:\AI\Dynamous\Courses\workshops\second-brain-memory-deep-dive\llm-wiki-template\.claude\skills\llm-wiki\`
   to `.claude\skills\llm-wiki\`
   (includes: SKILL.md, references/page-templates.md, references/schema-guide.md, scripts/wiki_ops.py)

2. **Update WIKI_DIR path in `wiki_ops.py`** — change line 21:
   From:
   ```python
   WIKI_DIR = Path(__file__).parent.parent.parent.parent.parent / "wiki"
   ```
   To:
   ```python
   WIKI_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "wiki"
   ```
   Use `.resolve()` for absolute path safety — same pattern as all other scripts in this project.

3. **Create wiki/ directory structure** by copying from template:
   Copy all files from `O:\AI\Dynamous\Courses\workshops\second-brain-memory-deep-dive\llm-wiki-template\wiki\`
   to `wiki\` at project root. Expected structure:
   ```
   wiki/
   ├── SCHEMA.md
   ├── index.md
   ├── log.md
   ├── overview.md
   ├── raw/.gitkeep
   ├── entities/.gitkeep
   ├── concepts/.gitkeep
   ├── sources/.gitkeep
   └── comparisons/.gitkeep
   ```

- **GOTCHA**: `wiki/` lives at project root — same level as `Memory/`, NOT inside `Memory/`.
  Internal memory and external knowledge are kept separate by design.
- **VALIDATE**: `python .claude/skills/llm-wiki/scripts/wiki_ops.py stats` — prints stats with 0 pages.
- **VALIDATE**: `python .claude/skills/llm-wiki/scripts/wiki_ops.py lint` — no errors.

---

### TASK 21 — UPDATE: `CLAUDE.md` — add wiki/ references

In the `## Key Paths` section, add:
```markdown
- External knowledge wiki: wiki/
- Wiki skill: .claude/skills/llm-wiki/
```

After the `## Integrations (Phase 4)` section command list, add a new section:

```markdown
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
```

- **VALIDATE**: `Select-String "wiki/" CLAUDE.md` returns results.

---

### TASK 22 — RUN: Full test suite + memory lint

```powershell
cd .claude/scripts
uv run pytest tests/ -x -q --tb=short
python memory_lint.py --stats
python memory_lint.py
```

Fix any failures before proceeding to deploy.

- **VALIDATE**: All 155+ existing tests pass + new tests in Tasks 13 and 15 pass (target: 175+)

---

### TASK 23 — DEPLOY: Push to VPS

```powershell
powershell -File "O:\AI\Dynamous\Courses\second-brain-workshop\scripts\deploy.ps1"
```

After deploy, verify on VPS:
```bash
ssh secondbrain@137.184.102.104 "ls /home/secondbrain/second-brain/Memory/entities/"
ssh secondbrain@137.184.102.104 "ls /home/secondbrain/second-brain/Memory/Profile/"
ssh secondbrain@137.184.102.104 "cd /home/secondbrain/second-brain && .claude/scripts/.venv/bin/python .claude/scripts/memory_lint.py --stats"
```

Force reflection to test new routing:
```bash
ssh secondbrain@137.184.102.104 "cd /home/secondbrain/second-brain && .claude/scripts/.venv/bin/python .claude/scripts/memory_reflect.py --force 2>&1"
```

- **VALIDATE**: New Memory/ structure present on VPS. Reflection runs and routes without errors.

---

## TESTING STRATEGY

### Unit Tests

All new pure functions (routing helpers, lint checks) tested with `tmp_path` + `monkeypatch`.
Pattern: `monkeypatch.setattr(module, "ENTITIES_DIR", tmp_path / "entities")` before each test.
No live API calls in any unit test. Mirror patterns from `test_memory_reflect.py`.

### Integration Tests (Manual)

1. Start fresh Claude Code session — verify core-memories.md and Profile/ are in session context
2. Run `memory_reflect.py --force` — verify items route to entity/topic pages, not just MEMORY.md
3. Trigger "Ask Me Questions" locally — skill activates, one question at a time
4. Send "ask me questions" via WhatsApp — profile mode activates, answer saved to Profile/
5. Run `memory_lint.py` — clean bill of health after migration

### Edge Cases

- `append_to_entity_page()` with non-existent page → returns False, no exception
- `archive_decision()` when quarter file doesn't exist → creates file automatically
- `update_memory_active_items()` on MEMORY.md with no `## Active Items` → creates section
- Profile/ placeholder content must NOT be injected into session context (`"_(not yet"` guard)
- `count_file_mentions()` on a name with dots/parentheses → no crash (pure string `in` check, not regex)
- `parse_reflection_response()` with both old and new keys → both are processed without error
- WhatsApp profile timeout check runs BEFORE LLM call — no extra API spend for timed-out sessions

---

## VALIDATION COMMANDS

### Level 1: Syntax
```powershell
cd .claude/scripts
python -c "import ast, pathlib; [ast.parse(f.read_text()) for f in pathlib.Path('.').glob('*.py') if not f.name.startswith('test')]; print('syntax ok')"
```

### Level 2: Imports
```powershell
python -c "from config import ENTITIES_DIR, TOPICS_DIR, DECISIONS_DIR, PROFILE_DIR, CORE_MEMORIES_FILE; print('config ok')"
python -c "import memory_reflect; print('reflect ok')"
python -c "import memory_lint; print('lint ok')"
python -c "import sys; sys.path.insert(0,'../chat'); from engine import ConversationEngine; print('engine ok')"
```

### Level 3: Unit Tests
```powershell
uv run pytest tests/test_memory_reflect.py -v
uv run pytest tests/test_memory_lint.py -v
uv run pytest tests/ -x -q --tb=short
```

### Level 4: Memory Health
```powershell
python memory_lint.py --stats
python memory_lint.py
```

### Level 5: Session Context
```powershell
python -c "import sys; sys.path.insert(0,'.claude/scripts'); from session_context import build_context; ctx = build_context(); print(len(ctx), 'chars'); print('Core Memories' in ctx)"
```

### Level 6: Wiki Ops
```powershell
python .claude/skills/llm-wiki/scripts/wiki_ops.py stats
python .claude/skills/llm-wiki/scripts/wiki_ops.py lint
```

### Level 7: VPS Validation
```bash
ssh secondbrain@137.184.102.104 "cd /home/secondbrain/second-brain && .claude/scripts/.venv/bin/python .claude/scripts/memory_lint.py --stats"
ssh secondbrain@137.184.102.104 "cd /home/secondbrain/second-brain && .claude/scripts/.venv/bin/python .claude/scripts/memory_reflect.py --force 2>&1"
```

---

## ACCEPTANCE CRITERIA

- [ ] `Memory/entities/` contains pages for all 5 businesses + venues + projects (8+ pages)
- [ ] `Memory/topics/` contains investment-strategy.md and hosting-growth.md
- [ ] `Memory/decisions/2026-Q2.md` exists with historical decisions archived
- [ ] `Memory/Profile/` contains all 7 seeded files with correct section headings
- [ ] `Memory/MEMORY.md` is under 5KB and uses lean index format with [[wiki-links]]
- [ ] `Memory/core-memories.md` exists
- [ ] `Memory/GUIDE.md` exists with human-readable filing reference
- [ ] `Memory/SOUL.md` contains Memory Recall Protocol section
- [ ] Old folders removed: Projects/, Wealth/, Businesses/, Content/
- [ ] `session_context.py` injects core-memories.md and non-placeholder Profile/ files
- [ ] `memory_reflect.py` routes to entity/topic/profile/decisions pages (not only MEMORY.md)
- [ ] `memory_lint.py` runs clean on fresh vault
- [ ] `engine.py` detects "ask me questions" and activates profile mode
- [ ] `.claude/skills/ask-me-questions/SKILL.md` exists with full question framework
- [ ] WhatsApp profile sessions auto-end after 10 min silence
- [ ] `wiki/` directory structure exists at project root
- [ ] `.claude/skills/llm-wiki/` installed with updated WIKI_DIR path
- [ ] `wiki_ops.py stats` and `wiki_ops.py lint` run without errors
- [ ] CLAUDE.md references wiki/ in Key Paths
- [ ] All 155+ existing tests still pass + new tests added (target: 175+)
- [ ] VPS deploy successful — new Memory/ structure present on server
- [ ] Forced VPS reflection routes correctly after deploy

---

## COMPLETION CHECKLIST

- [ ] Phase A (Tasks 1–15): Structured memory foundation complete
- [ ] Phase B (Tasks 16–17): Profile system seeded + reflection permanence rule in prompt
- [ ] Phase C (Tasks 18–19): Ask Me Questions skill + engine.py integration
- [ ] Phase D (Tasks 20–21): External wiki installed + CLAUDE.md updated
- [ ] Phase E (Tasks 22–23): Tests pass + deployed to VPS
- [ ] `memory_lint.py` reports clean vault
- [ ] Fresh session confirms core-memories + Profile injection in context
- [ ] WhatsApp "ask me questions" tested end-to-end

---

## NOTES

### Why structured output for reflection (not tool calls)?
`memory_reflect.py` uses `allowed_tools=[]` and structured JSON output because the Codex backend
(current active backend) cannot reliably use named tools. Python applies all file changes from the
JSON. This constraint is preserved in the upgraded reflection — the LLM still outputs JSON, Python
routes to the right files.

### Why Python-driven mention count (not LLM)?
The 3-mention threshold for new page creation is computed by Python (`count_file_mentions()`)
before the LLM call. More reliable than asking the LLM to count, and avoids extra file system
access in the LLM call.

### MEMORY.md active items pruning
The lint script checks for stale active items (> 30 days). Removal is not automated — it happens
when reflection routes completed decisions to `decisions/`. Stale items surface in the lint report.

### Profile/ injection budget
Only values, goals, personality, and health are injected at session start. relationships.md and
finances.md are large and sensitive — available on-demand via direct read. This keeps context lean.

### wiki/ is NOT indexed by memory_index.py
The external wiki uses its own index.md navigation — no pgvector embeddings needed. If wiki/ grows
large, a separate `wiki_index.py` could be added later. memory_index.py indexes Memory/ only.

### Ask Me Questions — no session store schema change
Profile mode is detected per-message from the trigger phrase + conversation history (the LLM sees
prior Q&A in context via sdk_compat resume). The 10-min timeout uses a simple JSON state file —
no database schema migration required.

### trim_memory_if_needed() archive path
Currently archives to `VAULT_DIR / "Research"`. Update to `VAULT_DIR / "decisions"` in Task 12
to avoid recreating the retired Research/ directory.

**Confidence Score: 8/10**

High confidence: all patterns established in codebase, no new dependencies, structured-output
reflection proven (just rebuilt on this pattern in commit 9a103d8), wiki is copy-and-configure.

Main risks: (1) MEMORY.md section parsing in `update_memory_active_items()` — test thoroughly
with varied MEMORY.md shapes; (2) `count_file_mentions()` is a linear scan — acceptable for
nightly reflection cadence, not for hot path; (3) WhatsApp profile timeout relies on file state —
if the polling interval is slow, auto-end may lag by one poll cycle.
