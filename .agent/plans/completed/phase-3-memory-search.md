# Phase 3: Memory Search (Hybrid RAG)

The following plan is complete and self-contained. Validate patterns against the
reference implementation before writing each file. All content is specified inline.

## Before You Start

- `/prime` has already been run — full project context is loaded.
- The Python venv at `.claude/scripts/.venv` already exists.
- Phase 3 requires three new pip installs (see Task 1).
- Cole's reference files are at:
  `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\scripts\`
  Read them before implementing Tasks 3, 4, 5, 6, 7.
- Our `config.py` is at `.claude/scripts/config.py` — Task 2 adds Phase 3 constants to it.

## Feature Description

Build a local hybrid search index over the entire `Memory/` vault. Markdown files
are chunked into ~400-token overlapping segments, embedded with FastEmbed
(all-MiniLM-L6-v2, 384-dim), and stored in SQLite with both a vector table
(sqlite-vec) and a full-text table (FTS5). A search CLI combines vector similarity
and BM25 keyword ranking via weighted fusion, with a `--path-prefix` flag for
voice-matching against past sent drafts in Phase 6.

## User Story

As Shaun Thomson (multi-business founder),
I want to search my entire Memory vault by meaning — not just keyword match —
So that the heartbeat (Phase 6) can find relevant email tone examples and context
regardless of exact wording, and I can ask questions across all my business notes.

## Problem Statement

Without Phase 3, every phase that needs context from Memory/ must do exact keyword
search or inject entire files. The heartbeat cannot match Shaun's email tone against
past drafts. The chat interface cannot retrieve relevant context by meaning.

## Solution Statement

SQLite + sqlite-vec + FTS5 gives a zero-infrastructure local RAG system. Incremental
indexing (content-hash change detection) keeps it fast on repeat runs. Hybrid search
(vector + keyword, weighted) outperforms either alone. The `--path-prefix` filter
makes it the voice-matching engine for Phase 6 draft generation.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `.claude/scripts/`, `.claude/data/`
**Dependencies**: fastembed, sqlite-vec, numpy (new installs)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ BEFORE IMPLEMENTING

- `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\scripts\embeddings.py`
  Why: Copy verbatim. numpy serialization pattern (`embedding.tobytes()`), lazy model
  singleton, generator-wrapping fix (`list(model.embed(...))`).

- `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\scripts\db.py`
  Why: Copy verbatim (paths come from our config). Full SQLite + Postgres abstraction,
  FTS5 trigger pattern, sqlite-vec load sequence, score normalization formulas,
  path_prefix over-fetch workaround.

- `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\scripts\memory_index.py`
  Why: Copy verbatim (paths come from our config). Content-hash change detection,
  chunk_markdown() overlap logic, model-change rebuild, ensure_directories() call.

- `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\scripts\memory_search.py`
  Why: Copy verbatim (paths come from our config). Three search modes, hybrid merge
  key, weighted fusion, sanitize_external_text() call, Windows Unicode handling.

- `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\scripts\sanitize.py`
  Why: Copy verbatim. memory_search.py imports sanitize_external_text() from this.
  Phase 8 wires it as a hook; Phase 3 just needs the module present.

- `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\scripts\config.py`
  Why: Read to verify constant values — especially SEARCH_CHUNK_OVERLAP_TOKENS=80
  (PRD says 50, actual code uses 80), SEARCH_MIN_SCORE=0.2, SEARCH_DEFAULT_LIMIT=10.

- `.claude/scripts/config.py` (our current file)
  Why: Task 2 appends to this — need to see existing constants before adding new ones.

### New Files to Create

```
.claude/scripts/embeddings.py          — FastEmbed wrapper (copy from reference)
.claude/scripts/db.py                  — SQLite + Postgres abstraction (copy from reference)
.claude/scripts/sanitize.py            — Sanitization utils (copy from reference)
.claude/scripts/memory_index.py        — Incremental indexer (copy from reference)
.claude/scripts/memory_search.py       — Hybrid search CLI (copy from reference)
.claude/data/models/                   — Embedding model cache dir (create via gitkeep)
```

### Existing Files to Update

```
.claude/scripts/config.py              — Add Phase 3 constants + ensure_directories()
.gitignore                             — Add memory.db and models/ cache
CLAUDE.md                              — Add Phase 3 build commands + completed phase
```

### Patterns to Follow

**Vector serialization (db.py:58-60):**
```python
def _embedding_to_bytes(embedding: NDArray[np.float32]) -> bytes:
    return embedding.tobytes()   # numpy method — NOT struct.pack()
```

**Generator fix (embeddings.py:42-43):**
```python
results = list(model.embed([text]))   # embed() returns generator — must list()
embedding = np.array(results[0], dtype=np.float32)
```

**sqlite-vec load sequence (db.py:87-90):**
```python
self._conn.enable_load_extension(True)
sqlite_vec.load(self._conn)
self._conn.enable_load_extension(False)   # always disable after load
```

**FTS5 content table + triggers (db.py:121-141):**
FTS5 uses `content='chunks', content_rowid='id'` — do NOT insert directly into
chunks_fts. Three triggers (AFTER INSERT, AFTER DELETE, AFTER UPDATE on chunks)
keep it in sync automatically.

**path_prefix vector search workaround (db.py:292-310):**
sqlite-vec cannot use WHERE in its MATCH queries. When path_prefix is set,
over-fetch `limit * 5` and filter results in Python:
```python
fetch_limit = limit * 5 if path_prefix else limit
# then: if path_prefix and not row["file_path"].startswith(path_prefix): continue
```

**Score normalization (db.py:276-277, 311-312):**
```python
# Keyword: BM25 rank is negative — normalize to 0-1
score = 1.0 / (1.0 + abs(bm25_rank))
# Vector: L2 distance — normalize to 0-1
score = 1.0 / (1.0 + distance)
```

**Hybrid merge key (memory_search.py:132-133):**
```python
key = f"{r['file_path']}:{r['start_line']}-{r['end_line']}"
```
NOT chunk rowid — this string key is safe across both keyword and semantic result sets.

**FTS query quoting (db.py:63-69):**
```python
def _quote_fts_query(query: str) -> str:
    terms = query.strip().split()
    quoted = [f'"{term}"' for term in terms]
    return " AND ".join(quoted)
```
Handles multi-word queries correctly. Falls back to raw query on OperationalError.

**Content-hash change detection (memory_index.py:248-252):**
```python
content_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
if not force_rebuild and db.get_file_hash(rel_path) == content_hash:
    files_skipped += 1
    continue
```
Uses SHA-256 content hash, NOT mtime — more reliable for detecting real changes.

**Model change → force rebuild (memory_index.py:230-234):**
```python
stored_model = db.get_meta("embedding_model")
if stored_model and stored_model != EMBEDDING_MODEL:
    print(f"Model changed ({stored_model} -> {EMBEDDING_MODEL}), forcing rebuild...")
    force_rebuild = True
```

**Windows console safety (memory_search.py:258-261):**
```python
try:
    print(output)
except UnicodeEncodeError:
    print(output.encode("ascii", errors="replace").decode("ascii"))
```

---

## CRITICAL GOTCHAS (PRD vs ACTUAL CODE)

| Item | PRD says | Actual code | Impact |
|------|----------|-------------|--------|
| Chunk overlap | 50 tokens | **80 tokens** | Wrong overlap if not corrected |
| Fusion algorithm | RRF (rank-based) | **Weighted sum of normalized scores** | Different results |
| Vector serialization | (not specified) | `embedding.tobytes()` (numpy) | TypeError if struct.pack used |
| FTS table name | `fts_chunks` | **`chunks_fts`** | SQL errors if wrong name |
| Cache dir | (not specified) | `.claude/data/models/` | Model re-downloads on reboot if in /tmp |
| `embed()` return | (not specified) | Generator — must `list()` | TypeError on index |
| Score formula | (not specified) | `1/(1+abs(bm25))`, `1/(1+dist)` | Wrong result ordering |
| `sanitize.py` dep | Phase 8 only | **Required by memory_search now** | ImportError without stub |
| Table structure | 3 tables | **5 tables** (meta, files, chunks, chunks_fts, vec_chunks) | Missing file change tracking |
| FTS insert method | (not specified) | Triggers only — never insert directly | Duplicate FTS entries |
| path_prefix (vec) | (not specified) | Over-fetch 5x + Python filter | Missing results without workaround |

---

## IMPLEMENTATION PLAN

### Stage 1: Dependencies + config
Install packages and extend config.py with Phase 3 constants.

### Stage 2: Core modules
Create embeddings.py, db.py, sanitize.py — the foundation everything else imports.

### Stage 3: Index + search
Create memory_index.py and memory_search.py from Cole's reference.

### Stage 4: Wire up
Update .gitignore, create model cache dir stub, update CLAUDE.md.

---

## STEP-BY-STEP TASKS

Execute every task in order. Each task is independently verifiable.

---

### TASK 1 — INSTALL Phase 3 dependencies

**IMPLEMENT:**
```powershell
.claude\scripts\.venv\Scripts\pip.exe install "fastembed>=0.4.0" "sqlite-vec>=0.1.6" "numpy>=1.26.0"
```

Note: psycopg and pgvector are NOT needed — Postgres backend is deferred to Phase 9.
The Postgres backend code in db.py imports them lazily (inside methods), so they are
not required at import time.

**VALIDATE:**
```powershell
.claude\scripts\.venv\Scripts\python.exe -c "import fastembed; import sqlite_vec; import numpy; print('deps OK')"
```
Expected: `deps OK`

---

### TASK 2 — UPDATE `.claude/scripts/config.py`

Append Phase 3 constants to the existing file. Do NOT rewrite it — add after the
existing `now_local()` function.

**IMPLEMENT — add these lines at the end of config.py:**
```python
# ---------------------------------------------------------------------------
# Phase 3: Memory Search
# ---------------------------------------------------------------------------
import os as _os
from dotenv import load_dotenv as _load_dotenv
_load_dotenv()

# Database
DATABASE_PATH = DATA_DIR / "memory.db"
DATABASE_URL = _os.getenv("DATABASE_URL", "")

# Embedding model
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384
EMBEDDING_CACHE_DIR = DATA_DIR / "models"

# Search tuning (match Cole's reference exactly)
SEARCH_CHUNK_MAX_TOKENS = 400
SEARCH_CHUNK_OVERLAP_TOKENS = 80    # NOTE: PRD says 50 — actual code uses 80
SEARCH_VECTOR_WEIGHT = 0.7
SEARCH_KEYWORD_WEIGHT = 0.3
SEARCH_DEFAULT_LIMIT = 10
SEARCH_MIN_SCORE = 0.2


def ensure_directories() -> None:
    """Ensure all Phase 1-3 runtime directories exist."""
    for d in [DAILY_DIR, STATE_DIR, DATA_DIR, EMBEDDING_CACHE_DIR,
              ACTIVE_DRAFTS_DIR, DRAFTS_DIR / "sent", DRAFTS_DIR / "expired"]:
        d.mkdir(parents=True, exist_ok=True)
```

**GOTCHA:** Use aliased imports (`import os as _os`) to avoid polluting the module
namespace with `os` — other scripts that do `from config import *` won't get `os`.

**VALIDATE:**
```powershell
.claude\scripts\.venv\Scripts\python.exe -c "
import sys; sys.path.insert(0, '.claude/scripts')
from config import (DATABASE_PATH, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS,
                    EMBEDDING_CACHE_DIR, SEARCH_CHUNK_OVERLAP_TOKENS,
                    SEARCH_VECTOR_WEIGHT, SEARCH_MIN_SCORE, ensure_directories)
print('DATABASE_PATH:', DATABASE_PATH)
print('EMBEDDING_CACHE_DIR:', EMBEDDING_CACHE_DIR)
print('SEARCH_CHUNK_OVERLAP_TOKENS:', SEARCH_CHUNK_OVERLAP_TOKENS)
ensure_directories()
print('ensure_directories OK')
"
```
Expected: paths printed, `ensure_directories OK`, no errors.
Check that `.claude/data/models/` directory was created.

---

### TASK 3 — CREATE `.claude/scripts/embeddings.py`

COPY VERBATIM from Cole's reference. The only difference is that our config.py
already exports `EMBEDDING_CACHE_DIR` and `EMBEDDING_MODEL` with the correct values.

Source: `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\scripts\embeddings.py`

**GOTCHA:** `embed()` returns a generator. Cole's code wraps it: `list(model.embed([text]))`.
Do NOT change this — it's the fix for a common FastEmbed gotcha.

**GOTCHA:** Serialization uses `embedding.tobytes()` (numpy NDArray method), NOT
`struct.pack()`. Do not substitute.

**GOTCHA:** Cache dir is set via `EMBEDDING_CACHE_DIR` (`.claude/data/models/`).
This survives reboots. If omitted, FastEmbed defaults to system tmp and re-downloads
the 80MB model on every reboot.

**VALIDATE:**
```powershell
.claude\scripts\.venv\Scripts\python.exe -c "
import sys; sys.path.insert(0, '.claude/scripts')
from embeddings import embed_text, embed_batch, embedding_to_bytes, text_hash
import numpy as np
print('embeddings import OK')
# Verify serialization roundtrip (no model download needed for this)
arr = np.array([0.1, 0.2, 0.3], dtype=np.float32)
b = arr.tobytes()
arr2 = np.frombuffer(b, dtype=np.float32).copy()
assert list(arr) == list(arr2), 'serialization roundtrip failed'
print('serialization roundtrip OK')
print('text_hash test:', text_hash('hello'))
"
```
Expected: imports OK, roundtrip OK, 16-char hex hash printed.

Note: do NOT trigger `embed_text()` or `embed_batch()` in validation — this downloads
the 80MB model. First real download happens in Task 6 (memory_index.py test run).

---

### TASK 4 — CREATE `.claude/scripts/db.py`

COPY VERBATIM from Cole's reference. Paths (`DATABASE_PATH`, `DATABASE_URL`,
`EMBEDDING_DIMENSIONS`, `EMBEDDING_MODEL`) come from our config.py which already
has the correct values.

Source: `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\scripts\db.py`

**GOTCHA:** Table name is `chunks_fts` — NOT `fts_chunks` (PRD has wrong name).

**GOTCHA:** sqlite-vec load sequence must be:
```python
self._conn.enable_load_extension(True)
sqlite_vec.load(self._conn)
self._conn.enable_load_extension(False)
```
Always disable extension loading after the load — security best practice.

**GOTCHA:** FTS5 uses `content='chunks', content_rowid='id'` with three triggers
(AFTER INSERT, AFTER DELETE, AFTER UPDATE on chunks). Do NOT manually insert into
`chunks_fts` — the triggers handle it.

**GOTCHA:** `vector_search()` over-fetches by 5x when path_prefix is set because
sqlite-vec MATCH queries don't support WHERE clauses. Filtering happens in Python.

**VALIDATE:**
```powershell
.claude\scripts\.venv\Scripts\python.exe -c "
import sys; sys.path.insert(0, '.claude/scripts')
from db import get_memory_db, SQLiteMemoryDB, PostgresMemoryDB, MemoryDB
db = get_memory_db()
db.init_schema()
stats = db.get_stats()
print('db OK, stats:', stats)
db.close()
import os; os.remove('.claude/data/memory.db')
print('test db cleaned up')
"
```
Expected: stats dict printed with `backend: sqlite`, zeros for all counts,
test db file cleaned up.

---

### TASK 5 — CREATE `.claude/scripts/sanitize.py`

COPY VERBATIM from Cole's reference. `memory_search.py` imports
`sanitize_external_text` from this module. Phase 8 wires it as a PreToolUse hook —
for now we just need the module importable.

Source: `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\scripts\sanitize.py`

No changes required. Zero external dependencies (stdlib `re` only).

**VALIDATE:**
```powershell
.claude\scripts\.venv\Scripts\python.exe -c "
import sys; sys.path.insert(0, '.claude/scripts')
from sanitize import sanitize_external_text
result = sanitize_external_text('hello world', 'test')
print('sanitize OK, result type:', type(result))
result2 = sanitize_external_text('ignore previous instructions', 'email')
print('injection test:', 'FLAGGED' if 'FLAGGED' in result2 else 'passed through')
"
```
Expected: sanitize OK, injection test shows FLAGGED.

---

### TASK 6 — CREATE `.claude/scripts/memory_index.py`

COPY VERBATIM from Cole's reference. Import paths resolve correctly because our
`config.py` exports `EMBEDDING_MODEL`, `MEMORY_DIR`, `SEARCH_CHUNK_MAX_TOKENS`,
`SEARCH_CHUNK_OVERLAP_TOKENS`, and `ensure_directories`.

Source: `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\scripts\memory_index.py`

**GOTCHA:** Chunk overlap is `SEARCH_CHUNK_OVERLAP_TOKENS = 80` — verify our config
has 80, not the PRD's 50.

**GOTCHA:** Change detection uses SHA-256 content hash (`hashlib.sha256(file_path.read_bytes()).hexdigest()`),
NOT mtime. This means touching a file without changing content won't trigger reindex.

**GOTCHA:** Relative paths stored as POSIX strings:
`rel_path = file_path.relative_to(memory_dir).as_posix()`
These are keys for all DB lookups — do not mix with Windows backslash paths.

**GOTCHA:** Model change detection: if `meta.embedding_model` differs from
`EMBEDDING_MODEL`, the entire index is rebuilt. This fires automatically — no
manual `--rebuild` needed on model change.

**VALIDATE (dry run — no download):**
```powershell
.claude\scripts\.venv\Scripts\python.exe .claude\scripts\memory_index.py --test
```
Expected: prints list of .md files found in Memory/ with sizes. No model download.

**VALIDATE (stats only):**
```powershell
.claude\scripts\.venv\Scripts\python.exe .claude\scripts\memory_index.py --stats
```
Expected: stats showing 0 files (empty index).

**VALIDATE (full index — triggers 80MB download on first run):**
```powershell
.claude\scripts\.venv\Scripts\python.exe .claude\scripts\memory_index.py
```
Expected: "Syncing memory index...", downloads model to `.claude/data/models/`,
indexes all Memory/ .md files, prints "Done!" with file/chunk counts.

---

### TASK 7 — CREATE `.claude/scripts/memory_search.py`

COPY VERBATIM from Cole's reference.

Source: `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\.claude\scripts\memory_search.py`

**GOTCHA:** Imports `sanitize_external_text` from `sanitize` — Task 5 must be
done first or this will fail with ImportError.

**GOTCHA:** Hybrid merge key is the string `"{file_path}:{start_line}-{end_line}"`,
not a rowid. This correctly joins keyword and vector results even when they come
from different SQL queries.

**GOTCHA:** Hybrid mode fetches `limit * 2` from each source before merging, then
takes top `limit` after weighted fusion. Results below `SEARCH_MIN_SCORE` (0.2)
are filtered before returning.

**GOTCHA:** Windows UnicodeEncodeError — Cole's code wraps `print(output)` in
try/except with ASCII fallback. Keep this — Windows terminal encoding breaks on
some Memory/ content.

**VALIDATE (requires Task 6 full index to have run):**
```powershell
.claude\scripts\.venv\Scripts\python.exe .claude\scripts\memory_search.py "SongbookDB"
.claude\scripts\.venv\Scripts\python.exe .claude\scripts\memory_search.py --mode keyword "karaoke"
.claude\scripts\.venv\Scripts\python.exe .claude\scripts\memory_search.py --mode semantic "business operations"
.claude\scripts\.venv\Scripts\python.exe .claude\scripts\memory_search.py --path-prefix drafts/sent "email reply"
.claude\scripts\.venv\Scripts\python.exe .claude\scripts\memory_search.py --test
```
Expected: results printed for first three queries, empty/no-results for path-prefix
(no drafts/sent yet), test queries run across all three modes.

---

### TASK 8 — UPDATE `.gitignore`

Add the database and model cache to gitignore so they are never committed.

**IMPLEMENT — append to existing `.gitignore`:**
```
# Phase 3: Memory Search
.claude/data/memory.db
.claude/data/memory.db-shm
.claude/data/memory.db-wal
.claude/data/models/
```

**VALIDATE:**
```powershell
git check-ignore -v .claude/data/memory.db
git check-ignore -v ".claude/data/models/"
```
Expected: both lines show the gitignore rule that matches them.

---

### TASK 9 — CREATE model cache dir stub

Create a `.gitkeep` so the `models/` directory is tracked by git but its contents
are not.

**IMPLEMENT:**
Create `.claude/data/models/.gitkeep` (empty file).

**VALIDATE:**
```powershell
Test-Path ".claude\data\models\.gitkeep"
```
Expected: True

---

### TASK 10 — UPDATE `CLAUDE.md`

Add Phase 3 build commands and mark phase complete.

**ADD to `## Build Commands` section:**
```markdown
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

**ADD to `## Completed Phases` section:**
```markdown
### Phase 3: Memory Search — Hybrid RAG (DATE)
SQLite + sqlite-vec + FTS5 hybrid search index over Memory/ vault.
embeddings.py (FastEmbed/all-MiniLM-L6-v2, 384-dim), db.py (SQLite + Postgres
abstraction, MemoryDB protocol), memory_index.py (incremental, content-hash
change detection, 400-token chunks/80-token overlap), memory_search.py
(keyword/semantic/hybrid modes, weighted fusion, --path-prefix for voice-matching).
```

**VALIDATE:**
```powershell
Select-String "Phase 3" CLAUDE.md
```
Expected: match on the completed phase entry.

---

## TESTING STRATEGY

### Unit Tests (manual — no pytest framework configured yet)

1. **config.py additions**: all new constants import cleanly; `ensure_directories()` creates dirs
2. **embeddings.py**: imports without triggering download; serialization roundtrip correct
3. **db.py**: `get_memory_db()` returns SQLiteMemoryDB; `init_schema()` creates all 5 tables
4. **sanitize.py**: `sanitize_external_text()` returns string; flags injection patterns
5. **memory_index.py**: `--test` lists files; `chunk_markdown()` produces overlapping chunks
6. **memory_search.py**: `--test` runs all three modes; `--path-prefix` accepted without error

### Integration Test

After Task 6 full index run:
- `memory_search.py "SongbookDB"` returns results from Memory/Projects/ or USER.md
- `memory_search.py --mode keyword "karaoke"` returns BM25 results
- `memory_search.py --mode semantic "music entertainment business"` returns semantic results
- All three modes return the same SearchResult fields (path, score, text, section_title)

### Edge Cases

- Empty vault (no daily logs yet): indexer runs without error, returns 0 files
- Query with no results: `format_results([])` returns "No results found."
- `--path-prefix` with no matching files: returns empty, no error
- Model name mismatch in meta table: forced rebuild triggered automatically
- File deleted from Memory/: `remove_stale_files()` cleans its index entries
- Multi-word FTS query: `_quote_fts_query()` wraps each term, uses AND

---

## VALIDATION COMMANDS

### Level 1: All imports resolve

```powershell
.claude\scripts\.venv\Scripts\python.exe -c "
import sys; sys.path.insert(0, '.claude/scripts')
from config import (DATABASE_PATH, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS,
                    EMBEDDING_CACHE_DIR, SEARCH_CHUNK_MAX_TOKENS,
                    SEARCH_CHUNK_OVERLAP_TOKENS, SEARCH_VECTOR_WEIGHT,
                    SEARCH_KEYWORD_WEIGHT, SEARCH_DEFAULT_LIMIT,
                    SEARCH_MIN_SCORE, ensure_directories)
from embeddings import embed_text, embed_batch, embedding_to_bytes
from db import get_memory_db, SQLiteMemoryDB, MemoryDB
from sanitize import sanitize_external_text
from memory_index import chunk_markdown, sync_index, ChunkRecord
from memory_search import search, format_results, SearchResult
print('All Phase 3 imports OK')
print('OVERLAP TOKENS (must be 80):', SEARCH_CHUNK_OVERLAP_TOKENS)
"
```
Expected: `All Phase 3 imports OK`, `OVERLAP TOKENS (must be 80): 80`

### Level 2: DB schema

```powershell
.claude\scripts\.venv\Scripts\python.exe -c "
import sys, sqlite3; sys.path.insert(0, '.claude/scripts')
from db import get_memory_db
db = get_memory_db()
db.init_schema()
conn = db._get_conn()
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' OR type='shadow'\").fetchall()]
print('Tables:', sorted(tables))
db.close()
import os; os.remove('.claude/data/memory.db')
"
```
Expected: tables list includes `meta`, `files`, `chunks`, `chunks_fts`, `vec_chunks`

### Level 3: Chunk logic

```powershell
.claude\scripts\.venv\Scripts\python.exe -c "
import sys; sys.path.insert(0, '.claude/scripts')
from memory_index import chunk_markdown
content = '\n'.join([f'Line {i}: ' + 'word ' * 20 for i in range(50)])
chunks = chunk_markdown(content)
print(f'Chunks produced: {len(chunks)}')
print(f'First chunk lines: {chunks[0].start_line}-{chunks[0].end_line}')
if len(chunks) > 1:
    print(f'Second chunk starts at: {chunks[1].start_line}')
    overlap_lines = chunks[0].end_line - chunks[1].start_line + 1
    print(f'Overlap (should be ~20 lines): {overlap_lines}')
"
```
Expected: multiple chunks produced, overlap of ~15-25 lines visible.

### Level 4: Search end-to-end (requires full index from Task 6)

```powershell
.claude\scripts\.venv\Scripts\python.exe .claude\scripts\memory_search.py "SongbookDB" --mode hybrid
.claude\scripts\.venv\Scripts\python.exe .claude\scripts\memory_search.py "karaoke show" --mode keyword
.claude\scripts\.venv\Scripts\python.exe .claude\scripts\memory_search.py "business operations Sydney" --mode semantic
```
Expected: results with file paths, scores, and 200-char snippets.

### Level 5: File tree check

```powershell
@(
  ".claude\scripts\embeddings.py",
  ".claude\scripts\db.py",
  ".claude\scripts\sanitize.py",
  ".claude\scripts\memory_index.py",
  ".claude\scripts\memory_search.py",
  ".claude\data\models\.gitkeep"
) | ForEach-Object { "$_ : $(Test-Path $_)" }
```
Expected: all 6 lines end with `: True`

---

## ACCEPTANCE CRITERIA

- [ ] All 10 tasks completed in order
- [ ] Level 1-5 validation commands pass with zero errors
- [ ] `SEARCH_CHUNK_OVERLAP_TOKENS` is 80 in config.py (not 50)
- [ ] `chunk_markdown()` produces overlapping chunks with correct section_title tracking
- [ ] `db.init_schema()` creates all 5 tables (meta, files, chunks, chunks_fts, vec_chunks)
- [ ] FTS5 table is `chunks_fts` (not `fts_chunks`)
- [ ] Vector serialization uses `embedding.tobytes()` (numpy), not struct.pack
- [ ] sqlite-vec extension disabled immediately after load
- [ ] `memory_index.py --test` lists all Memory/ .md files without error
- [ ] `memory_index.py` full run indexes all files and reports chunk counts
- [ ] `memory_search.py` returns results in keyword, semantic, and hybrid modes
- [ ] `--path-prefix` flag accepted and filters correctly
- [ ] `sanitize_external_text()` importable from sanitize.py
- [ ] `memory.db` and `models/` added to .gitignore
- [ ] CLAUDE.md updated with Phase 3 commands and completed phase entry

---

## COMPLETION CHECKLIST

- [ ] Tasks 1-10 completed in order
- [ ] Each task's VALIDATE command executed and passed
- [ ] Level 1-5 validation suite all green
- [ ] CLAUDE.md updated
- [ ] No regressions: existing Memory/ vault files and Phase 2 hooks untouched

---

## NOTES

**Why sanitize.py is created in Phase 3 (not Phase 8):**
`memory_search.py` imports `sanitize_external_text` at the top level, not lazily.
Without `sanitize.py` present, `memory_search.py` fails to import entirely. Phase 8
adds `block-secrets.py` and `command-guard.py` hooks — it does NOT recreate `sanitize.py`.

**Why Postgres is not installed in Phase 3:**
`psycopg` and `pgvector` are imported lazily inside `PostgresMemoryDB` methods, not
at module level. `get_memory_db()` only returns `PostgresMemoryDB` when `DATABASE_URL`
is set. Leave the Postgres code in db.py (it's copied verbatim) but don't install
the packages until Phase 9 (VPS deployment).

**Why overlap is 80 tokens, not 50:**
The PRD was written from the architecture spec, not the code. Cole's config.py has
`SEARCH_CHUNK_OVERLAP_TOKENS = 80`. This gives better context continuity across chunk
boundaries. Using 50 would produce valid results but worse retrieval quality.

**What comes next (Phase 4):**
Gmail, Outlook, Calendar, and WhatsApp integration modules. They return structured
data objects that the heartbeat (Phase 6) passes to the search layer for voice-matching.
The `--path-prefix drafts/sent` search mode built in Phase 3 is the voice-matching
entry point.
