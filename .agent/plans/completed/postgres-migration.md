# Feature: Migrate from SQLite to PostgreSQL (Shared DB — Local + VPS)

The following plan should be complete, but validate documentation and codebase patterns before implementing.

Pay special attention to the `psycopg` v3 API (`%s` params, `autocommit`, cursor usage) — it differs from psycopg2.

## Feature Description

Replace the two SQLite databases (`memory.db` for memory search, `chat.db` for WhatsApp sessions)
with a single shared PostgreSQL database on the VPS. Local machine connects via SSH tunnel.
Both environments then read/write the same data — consistent memory search results and session
continuity regardless of where a query originates.

## User Story

As Shaun's Second Brain running on both a local Windows machine and a DigitalOcean VPS,
I want both environments to share a single PostgreSQL database,
So that memory search results and WhatsApp session history are consistent everywhere.

## Problem Statement

- `memory.db` and `chat.db` are machine-local SQLite files that diverge between local and VPS
- Memory search locally returns stale results vs VPS (different indexes)
- WhatsApp sessions exist only on VPS; local can never resume them
- Cole's intended architecture explicitly uses Postgres + SSH tunnel for a unified data layer

## Solution Statement

- Install Postgres + pgvector on VPS, create `secondbrain` database
- Add `PostgresSessionStore` to `session.py` (mirroring `PostgresMemoryDB` pattern in `db.py`)
- Update `get_session_store()` factory to check `DATABASE_URL` (same as `get_memory_db()`)
- Set `DATABASE_URL` in `.env` on VPS (direct) and local (via SSH tunnel on localhost:5432)
- Create a persistent Windows Task Scheduler SSH tunnel task for local access
- Re-run `memory_index.py --rebuild` against Postgres to populate memory index

## Feature Metadata

**Feature Type**: Refactor / Infrastructure  
**Estimated Complexity**: Medium  
**Primary Systems Affected**: `db.py`, `session.py`, `config.py`, `main.py`, VPS setup, local tunnel  
**Dependencies**: Postgres 14+, pgvector extension, psycopg[binary]>=3.1.0, pgvector>=0.3.0 (already in pyproject.toml)

---

## CONTEXT REFERENCES

### Relevant Codebase Files — READ BEFORE IMPLEMENTING

- `.claude/scripts/db.py` (lines 375–678) — `PostgresMemoryDB` is the exact pattern to mirror for `PostgresSessionStore`. Uses `psycopg` v3, `%s` params, `_get_conn()`, `autocommit=False`.
- `.claude/scripts/db.py` (lines 669–678) — `get_memory_db()` factory: checks `DATABASE_URL`, returns Postgres or SQLite. Mirror this in `get_session_store()`.
- `.claude/chat/session.py` (full file) — `SQLiteSessionStore` is what we're extending. `get_session_store()` factory needs updating.
- `.claude/chat/main.py` (lines 26–36, 115–116) — imports `CHAT_DB_PATH` and calls `get_session_store(CHAT_DB_PATH)`. Will need update when Postgres is active.
- `.claude/scripts/config.py` (lines 36–41, 164) — `DATABASE_URL` already loaded from `.env`; `CHAT_DB_PATH` stays for SQLite fallback.
- `.claude/scripts/pyproject.toml` — `psycopg[binary]>=3.1.0` and `pgvector>=0.3.0` already listed. No new deps needed.
- `.claude/scripts/tests/test_chat_session.py` (full file) — existing SQLite session tests; Postgres tests must cover the same interface.
- `scripts/deploy.ps1` — VPS connection: `secondbrain@137.184.102.104`, remote dir `/home/secondbrain/second-brain`
- Cole's reference CLAUDE.md (at `O:\AI\Dynamous\Courses\workshops\claude-code-second-brain\CLAUDE.md`, lines 213–254) — SSH tunnel Task Scheduler PowerShell template

### New Files to Create

- `.claude/scripts/tests/test_postgres_session.py` — Postgres session store tests (skipped if no `TEST_DATABASE_URL`)
- `.agent/plans/postgres-migration.md` — this file

### Files to Modify

- `.claude/chat/session.py` — add `PostgresSessionStore`, update `get_session_store()` return type + factory logic
- `.claude/chat/main.py` — update `get_session_store()` call to pass `None` when Postgres is active (or let factory decide)

### Patterns to Follow

**psycopg v3 connection pattern** (from `db.py` lines 382–387):
```python
import psycopg
self._conn = psycopg.connect(self._url, autocommit=False)
```

**psycopg v3 cursor + params** — use `%s` not `?`; cursor is separate from connection:
```python
cur = self._get_conn().cursor()
cur.execute("SELECT ... WHERE key = %s", (key,))
row = cur.fetchone()
```

**Factory pattern** (mirror `get_memory_db()` in `db.py` lines 669–678):
```python
def get_session_store(chat_db_path=None):
    url = DATABASE_URL  # from config
    if url:
        return PostgresSessionStore(url)
    if chat_db_path is None:
        chat_db_path = CHAT_DB_PATH
    return SQLiteSessionStore(chat_db_path)
```

**ON CONFLICT upsert** (Postgres, from `db.py` line 477–483):
```python
cur.execute(
    "INSERT INTO ... VALUES (%s, ...) ON CONFLICT (key) DO UPDATE SET ...",
    (val, ...)
)
```

**SERIAL primary key** — Postgres equivalent of SQLite `INTEGER PRIMARY KEY AUTOINCREMENT`:
```sql
id SERIAL PRIMARY KEY
```

**RETURNING id** — Postgres way to get inserted row id (from `db.py` line 527):
```python
cur.execute("INSERT INTO ... RETURNING id", (...))
row = cur.fetchone()
return row[0]
```

**Test skip pattern** — skip Postgres tests when no test DB available:
```python
import pytest
TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not TEST_DB_URL, reason="TEST_DATABASE_URL not set")
```

---

## IMPLEMENTATION PLAN

### Phase 1: VPS — Install Postgres + pgvector

Install Postgres and pgvector on VPS. Create database and user.

### Phase 2: Code — PostgresSessionStore

Add `PostgresSessionStore` to `session.py`. Update factory.  
Update `main.py` call site.

### Phase 3: Configuration

Set `DATABASE_URL` in `.env` on VPS and local. Create SSH tunnel Task Scheduler task on Windows.

### Phase 4: Initialise Databases

Run `memory_index.py --rebuild` on VPS to populate Postgres memory index.  
Session table created automatically by `PostgresSessionStore.init_schema()`.

### Phase 5: Tests + Validation

Unit tests for `PostgresSessionStore`. Run full suite. Manual end-to-end check.

---

## STEP-BY-STEP TASKS

### TASK 1 — VPS: Install PostgreSQL

SSH into VPS and run:

```bash
ssh secondbrain@137.184.102.104
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

- **VALIDATE**: `sudo systemctl status postgresql | grep Active`  
  Expected: `Active: active (running)`

- **VALIDATE**: `pg_lsclusters`  
  Note the Postgres **version number** (e.g. `14` or `16`) — needed for pgvector package name.

---

### TASK 2 — VPS: Install pgvector

Still on VPS. Two approaches — try apt first, fall back to source:

**Approach A — apt (Ubuntu 22.04+ with PGDG repo):**
```bash
PG_VER=$(pg_lsclusters | grep online | awk '{print $1}')
sudo apt install -y postgresql-${PG_VER}-pgvector
```

If `postgresql-XX-pgvector` is not found in apt, use Approach B.

**Approach B — build from source (always works):**
```bash
sudo apt install -y build-essential postgresql-server-dev-all git
cd /tmp
git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

- **VALIDATE**: `sudo -u postgres psql -c "CREATE EXTENSION IF NOT EXISTS vector; SELECT extname FROM pg_extension WHERE extname = 'vector';"`  
  Expected: returns `vector`

---

### TASK 3 — VPS: Create Database and User

Still on VPS:

```bash
# Generate a strong password — save it, you'll need it for DATABASE_URL
openssl rand -base64 24
```

Save the generated password. Then:

```bash
sudo -u postgres psql <<'SQL'
CREATE USER secondbrain WITH PASSWORD 'PASTE_PASSWORD_HERE';
CREATE DATABASE secondbrain_brain OWNER secondbrain;
\c secondbrain_brain
CREATE EXTENSION IF NOT EXISTS vector;
GRANT ALL PRIVILEGES ON DATABASE secondbrain_brain TO secondbrain;
SQL
```

- **VALIDATE**: `sudo -u postgres psql -d secondbrain_brain -c "\dx"` — should list `vector` extension  
- **VALIDATE**: `psql -U secondbrain -d secondbrain_brain -h localhost -c "\conninfo"` — should connect without error

---

### TASK 4 — VPS: Configure pg_hba.conf for local password auth

By default Ubuntu Postgres uses `peer` auth for local connections. The app connects as `secondbrain` (not the OS user), so we need `md5` or `scram-sha-256`:

```bash
PG_VER=$(pg_lsclusters | grep online | awk '{print $1}')
sudo nano /etc/postgresql/${PG_VER}/main/pg_hba.conf
```

Find the line:
```
local   all             all                                     peer
```
Change to:
```
local   all             all                                     md5
```
Also ensure this line exists (for localhost TCP connections from SSH tunnel):
```
host    all             all             127.0.0.1/32            md5
```

Then restart:
```bash
sudo systemctl restart postgresql
```

- **VALIDATE**: `psql -U secondbrain -d secondbrain_brain -h 127.0.0.1 -W` — enter password, should connect

---

### TASK 5 — VPS: Set DATABASE_URL in .env

On VPS, edit `.claude/scripts/.env`:

```bash
nano /home/secondbrain/second-brain/.claude/scripts/.env
```

Add:
```
DATABASE_URL=postgresql://secondbrain:PASTE_PASSWORD_HERE@localhost:5432/secondbrain_brain
```

- **VALIDATE**: `cd /home/secondbrain/second-brain && grep DATABASE_URL .claude/scripts/.env`  
  Should show the URL (non-empty).

---

### TASK 6 — CODE: Add `PostgresSessionStore` to `session.py`

**File**: `.claude/chat/session.py`

After the `SQLiteSessionStore` class (after line ~148), add:

```python
class PostgresSessionStore:
    """Persistent session storage backed by PostgreSQL (psycopg v3)."""

    def __init__(self, database_url: str) -> None:
        self._url = database_url
        self._conn: Any = None
        self._init_db()

    def _get_conn(self) -> Any:
        import psycopg
        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(self._url, autocommit=False)
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL UNIQUE,
                agent_session_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                message_count INTEGER DEFAULT 0,
                total_cost_usd REAL DEFAULT 0.0,
                status TEXT DEFAULT 'active'
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_platform_thread
                ON chat_sessions(platform, channel_id, thread_id)
        """)
        conn.commit()

    def _row_to_session(self, row: tuple) -> Session:
        return Session(
            session_id=row[0],
            agent_session_id=row[1],
            platform=row[2],
            channel_id=row[3],
            thread_id=row[4],
            user_id=row[5],
            created_at=datetime.fromisoformat(row[6]),
            updated_at=datetime.fromisoformat(row[7]),
            message_count=row[8],
            total_cost_usd=row[9],
            status=row[10],
        )

    def get(self, platform: str, channel_id: str, thread_id: str) -> Session | None:
        session_id = f"{platform}:{channel_id}:{thread_id}"
        cur = self._get_conn().cursor()
        cur.execute(
            """SELECT session_id, agent_session_id, platform, channel_id, thread_id,
                      user_id, created_at, updated_at, message_count, total_cost_usd, status
               FROM chat_sessions WHERE session_id = %s""",
            (session_id,),
        )
        row = cur.fetchone()
        return self._row_to_session(row) if row else None

    def create(self, session: Session) -> None:
        conn = self._get_conn()
        conn.cursor().execute(
            """INSERT INTO chat_sessions
               (session_id, agent_session_id, platform, channel_id, thread_id,
                user_id, created_at, updated_at, message_count, total_cost_usd, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                session.session_id,
                session.agent_session_id,
                session.platform,
                session.channel_id,
                session.thread_id,
                session.user_id,
                session.created_at.isoformat(),
                session.updated_at.isoformat(),
                session.message_count,
                session.total_cost_usd,
                session.status,
            ),
        )
        conn.commit()

    def update(self, session: Session) -> None:
        conn = self._get_conn()
        conn.cursor().execute(
            """UPDATE chat_sessions
               SET agent_session_id = %s, updated_at = %s, message_count = %s,
                   total_cost_usd = %s, status = %s
               WHERE session_id = %s""",
            (
                session.agent_session_id,
                datetime.now().isoformat(),
                session.message_count,
                session.total_cost_usd,
                session.status,
                session.session_id,
            ),
        )
        conn.commit()

    def list_active(self, platform: str | None = None) -> list[Session]:
        cur = self._get_conn().cursor()
        if platform:
            cur.execute(
                """SELECT session_id, agent_session_id, platform, channel_id, thread_id,
                          user_id, created_at, updated_at, message_count, total_cost_usd, status
                   FROM chat_sessions WHERE status = 'active' AND platform = %s
                   ORDER BY updated_at DESC""",
                (platform,),
            )
        else:
            cur.execute(
                """SELECT session_id, agent_session_id, platform, channel_id, thread_id,
                          user_id, created_at, updated_at, message_count, total_cost_usd, status
                   FROM chat_sessions WHERE status = 'active'
                   ORDER BY updated_at DESC"""
            )
        return [self._row_to_session(row) for row in cur.fetchall()]
```

- **IMPORTS**: Add `from typing import Any` at top of file (if not already present)
- **PATTERN**: Mirrors `PostgresMemoryDB` in `.claude/scripts/db.py` lines 375–660
- **GOTCHA**: psycopg v3 `Row` objects from `cursor()` are plain tuples (not sqlite3.Row dicts) — index by position, not name. Use `row[0]`, `row[1]`, etc.
- **GOTCHA**: `self._conn.closed` is an int in psycopg v3 (0 = open, non-zero = closed)

---

### TASK 7 — CODE: Update `get_session_store()` factory in `session.py`

**File**: `.claude/chat/session.py`

Replace the existing `get_session_store()` function:

```python
def get_session_store(chat_db_path: Path | None = None) -> SQLiteSessionStore | PostgresSessionStore:
    """Return Postgres session store if DATABASE_URL is set, else SQLite."""
    from config import CHAT_DB_PATH, DATABASE_URL
    if DATABASE_URL:
        return PostgresSessionStore(DATABASE_URL)
    if chat_db_path is None:
        chat_db_path = CHAT_DB_PATH
    return SQLiteSessionStore(chat_db_path)
```

- **PATTERN**: Mirrors `get_memory_db()` in `.claude/scripts/db.py` lines 669–678
- **GOTCHA**: `DATABASE_URL` must be imported from `config`, not re-read from `os.environ`, so the `.env` load in `config.py` takes effect first.

---

### TASK 8 — CODE: Update `main.py` call site

**File**: `.claude/chat/main.py`

The existing call `get_session_store(CHAT_DB_PATH)` still works — the factory ignores the path when `DATABASE_URL` is set. No change required unless you want to tidy the import.

- **VALIDATE**: Confirm `CHAT_DB_PATH` is still imported (it is — line 29). No action needed.

---

### TASK 9 — CODE: Add unit tests for `PostgresSessionStore`

**File**: `.claude/scripts/tests/test_postgres_session.py` (CREATE NEW)

```python
"""Tests for PostgresSessionStore — skipped unless TEST_DATABASE_URL is set."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "chat"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not TEST_DB_URL, reason="TEST_DATABASE_URL not set")

from session import PostgresSessionStore, Session


@pytest.fixture
def store():
    s = PostgresSessionStore(TEST_DB_URL)
    # Clean slate for each test
    conn = s._get_conn()
    conn.cursor().execute("DELETE FROM chat_sessions")
    conn.commit()
    yield s
    conn = s._get_conn()
    conn.cursor().execute("DELETE FROM chat_sessions")
    conn.commit()


def _make_session(session_id: str = "whatsapp:61410868612@c.us:") -> Session:
    now = datetime.now()
    return Session(
        session_id=session_id,
        agent_session_id="sdk-abc123",
        platform="whatsapp",
        channel_id="61410868612@c.us",
        thread_id="",
        user_id="61410868612@c.us",
        created_at=now,
        updated_at=now,
        message_count=1,
        total_cost_usd=0.01,
    )


def test_create_and_get(store):
    s = _make_session()
    store.create(s)
    result = store.get("whatsapp", "61410868612@c.us", "")
    assert result is not None
    assert result.agent_session_id == "sdk-abc123"


def test_get_nonexistent(store):
    result = store.get("whatsapp", "unknown@c.us", "")
    assert result is None


def test_update(store):
    s = _make_session()
    store.create(s)
    s.agent_session_id = "sdk-updated"
    s.message_count = 5
    store.update(s)
    result = store.get("whatsapp", "61410868612@c.us", "")
    assert result.agent_session_id == "sdk-updated"
    assert result.message_count == 5


def test_list_active(store):
    store.create(_make_session("whatsapp:a@c.us:"))
    store.create(_make_session("whatsapp:b@c.us:"))
    active = store.list_active()
    assert len(active) == 2


def test_list_active_by_platform(store):
    store.create(_make_session("whatsapp:a@c.us:"))
    active = store.list_active(platform="whatsapp")
    assert len(active) == 1
    none = store.list_active(platform="slack")
    assert len(none) == 0


def test_get_session_store_returns_postgres():
    from session import get_session_store
    store = get_session_store()
    assert isinstance(store, PostgresSessionStore)
```

- **GOTCHA**: Tests clean up their own rows — no DROP TABLE (other tests may rely on schema existing)
- **PATTERN**: Mirrors structure of `test_chat_session.py` exactly

---

### TASK 10 — LOCAL: Create SSH Tunnel Task Scheduler Task (Windows)

Run this in PowerShell as **Administrator** (or standard user if your account can register tasks):

```powershell
$sshExe = "C:\Windows\System32\OpenSSH\ssh.exe"
$keyPath = "$env:USERPROFILE\.ssh\id_ed25519"   # adjust if your key has a different name
$vpsUser = "secondbrain"
$vpsIp = "137.184.102.104"

$action = New-ScheduledTaskAction `
    -Execute $sshExe `
    -Argument "-N -i `"$keyPath`" -L 5432:localhost:5432 ${vpsUser}@${vpsIp}"

$trigger = New-ScheduledTaskTrigger -AtLogOn

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName "SecondBrain-SSH-Tunnel" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "SSH tunnel: localhost:5432 -> VPS Postgres"
```

Start it immediately after registering:
```powershell
Start-ScheduledTask -TaskName "SecondBrain-SSH-Tunnel"
```

- **GOTCHA**: Tunnel only works if your SSH key is **passphrase-free** OR loaded in `ssh-agent`. If key has a passphrase, run `ssh-add $keyPath` first, and ensure the Windows OpenSSH Authentication Agent service is running (`Set-Service ssh-agent -StartupType Automatic; Start-Service ssh-agent`).
- **GOTCHA**: Use `C:\Windows\System32\OpenSSH\ssh.exe` (Windows native), not Git's `/usr/bin/ssh`. The Task Scheduler can't access the Git SSH agent.

- **VALIDATE**: After starting task, from PowerShell:  
  `ssh secondbrain@137.184.102.104 -L 5432:localhost:5432 -N &`  
  Then: `psql -U secondbrain -d secondbrain_brain -h 127.0.0.1 -p 5432 -W`  
  Should connect.

---

### TASK 11 — LOCAL: Set DATABASE_URL in local .env

**File**: `.claude/scripts/.env`

Add:
```
DATABASE_URL=postgresql://secondbrain:PASTE_PASSWORD_HERE@localhost:5432/secondbrain_brain
```

Note: `localhost:5432` here resolves through the SSH tunnel to the VPS Postgres.

- **VALIDATE**: With tunnel running:  
  `cd .claude/scripts && uv run python -c "from db import get_memory_db; db = get_memory_db(); print(db.get_stats())"`  
  Should print stats with `"backend": "postgres"`

---

### TASK 12 — VPS: Initialise Memory Index in Postgres

SSH into VPS and rebuild the memory index:

```bash
ssh secondbrain@137.184.102.104
cd /home/secondbrain/second-brain/.claude/scripts
uv run python memory_index.py --rebuild
```

This creates the `meta`, `files`, `chunks` tables in Postgres and re-indexes all `Memory/` markdown files.

- **VALIDATE**: `uv run python memory_index.py --stats`  
  Should show file count, chunk count, vector count with `backend: postgres`

- **VALIDATE**: `uv run python memory_search.py "SongbookDB"`  
  Should return results.

---

### TASK 13 — VPS: Validate Session Store Uses Postgres

On VPS, confirm the chat bot would use Postgres:

```bash
cd /home/secondbrain/second-brain/.claude/scripts
uv run python -c "
import sys; sys.path.insert(0,'../chat')
from session import get_session_store, PostgresSessionStore
s = get_session_store()
print(type(s).__name__)
print(s.list_active())
"
```

Expected output:
```
PostgresSessionStore
[]
```

---

### TASK 14 — VPS: Restart WhatsApp Bot Service

If the WhatsApp bot service is running, restart it to pick up the new session store:

```bash
sudo systemctl restart second-brain-whatsapp.service
sudo systemctl status second-brain-whatsapp.service
```

- **VALIDATE**: `sudo journalctl -u second-brain-whatsapp.service -n 20`  
  Should show bot started, no Postgres connection errors.

---

### TASK 15 — LOCAL: Run Full Test Suite

```powershell
cd .claude/scripts
uv run pytest tests/ -v
```

The existing SQLite tests should still pass (they don't set `DATABASE_URL`).

To also run Postgres tests (requires tunnel active):

```powershell
$env:TEST_DATABASE_URL = "postgresql://secondbrain:PASSWORD@localhost:5432/secondbrain_brain"
uv run pytest tests/ -v
```

- **VALIDATE**: All 155+ existing tests pass  
- **VALIDATE**: `test_postgres_session.py` tests pass (5 new tests)

---

### TASK 16 — LOCAL: Validate Local Memory Search via Tunnel

With tunnel running:

```powershell
cd .claude/scripts
uv run python memory_search.py "SongbookDB churn"
```

Should return results from the shared Postgres index (same data as VPS).

---

## TESTING STRATEGY

### Unit Tests

- `test_chat_session.py` — existing 5 SQLite tests unchanged (SQLite path not affected)
- `test_postgres_session.py` — 5 new tests covering same interface via `TEST_DATABASE_URL`
- Both store implementations must pass identical behavioural tests

### Integration Tests

- VPS: memory search returns results after `--rebuild`
- VPS: chat bot creates a session record in Postgres on first message
- Local: memory search via SSH tunnel returns same results as VPS

### Edge Cases

- Factory returns SQLite when `DATABASE_URL` not set (existing behaviour preserved)
- Factory returns Postgres when `DATABASE_URL` is set (new behaviour)
- Tunnel down: `memory_search.py` fails with connection error (expected — not a bug)
- pgvector extension not installed: `init_schema()` fails with clear error on `CREATE EXTENSION vector`

---

## VALIDATION COMMANDS

### Level 1: VPS Postgres Health

```bash
# On VPS
sudo systemctl status postgresql
sudo -u postgres psql -d secondbrain_brain -c "SELECT extname FROM pg_extension WHERE extname='vector';"
psql -U secondbrain -d secondbrain_brain -h 127.0.0.1 -W -c "\dt"
```

### Level 2: Memory Index (VPS)

```bash
# On VPS
cd /home/secondbrain/second-brain/.claude/scripts
uv run python memory_index.py --stats
uv run python memory_search.py "Billy Goat Karaoke"
```

### Level 3: Session Store (VPS)

```bash
# On VPS
cd /home/secondbrain/second-brain/.claude/scripts
uv run python -c "import sys; sys.path.insert(0,'../chat'); from session import get_session_store, PostgresSessionStore; s=get_session_store(); assert isinstance(s, PostgresSessionStore); print('OK')"
```

### Level 4: SSH Tunnel + Local Access

```powershell
# On local (with tunnel running)
cd .claude/scripts
uv run python -c "from db import get_memory_db; db=get_memory_db(); s=db.get_stats(); assert s['backend']=='postgres'; print(s)"
uv run python memory_search.py "SongbookDB"
```

### Level 5: Full Test Suite

```powershell
# SQLite tests (no tunnel needed)
cd .claude/scripts && uv run pytest tests/ -v

# Including Postgres tests (tunnel required)
$env:TEST_DATABASE_URL="postgresql://secondbrain:PASSWORD@localhost:5432/secondbrain_brain"
uv run pytest tests/ -v
```

### Level 6: End-to-End WhatsApp Session

Send a WhatsApp message to the brain, then check session was written to Postgres:

```bash
# On VPS
psql -U secondbrain -d secondbrain_brain -h 127.0.0.1 -W -c "SELECT session_id, message_count, updated_at FROM chat_sessions ORDER BY updated_at DESC LIMIT 5;"
```

---

## ACCEPTANCE CRITERIA

- [ ] `psql --version` works on VPS, Postgres running
- [ ] `SELECT extname FROM pg_extension WHERE extname='vector'` returns `vector` in `secondbrain_brain` DB
- [ ] `DATABASE_URL` set in VPS `.env` and local `.env`
- [ ] `get_memory_db()` returns `PostgresMemoryDB` on both machines when `DATABASE_URL` set
- [ ] `get_session_store()` returns `PostgresSessionStore` when `DATABASE_URL` set
- [ ] `memory_index.py --stats` shows files/chunks/vectors in Postgres backend on VPS
- [ ] `memory_search.py "test"` returns results on both VPS and local (via tunnel)
- [ ] WhatsApp bot writes sessions to Postgres `chat_sessions` table
- [ ] All 155+ existing tests pass
- [ ] 5 new `test_postgres_session.py` tests pass with `TEST_DATABASE_URL` set
- [ ] SQLite fallback still works (no `DATABASE_URL` → SQLite)
- [ ] SSH tunnel Task Scheduler task runs at logon and auto-restarts

---

## COMPLETION CHECKLIST

- [ ] Phase 1 (VPS Postgres): Tasks 1–5 complete
- [ ] Phase 2 (Code): Tasks 6–9 complete, committed
- [ ] Phase 3 (Config): Tasks 10–11 complete
- [ ] Phase 4 (Init DB): Tasks 12–13 complete
- [ ] Phase 5 (Restart + Validate): Tasks 14–16 complete
- [ ] Full validation commands run with zero errors
- [ ] Committed and deployed via `/commit`

---

## NOTES

### Why one shared database (not two)?

`memory.db` and `chat.db` use different tables. Sharing a single Postgres database (`secondbrain_brain`) is simpler to manage — one connection string, one backup target, one set of credentials.

### SSH key requirement

The Task Scheduler SSH tunnel task runs as your Windows user. If your SSH key is passphrase-protected, the task will fail silently after a reboot until `ssh-agent` loads the key. Options:
- Use a passphrase-free key dedicated to this tunnel
- Or manually run `ssh-add` after each boot and `Start-ScheduledTask -TaskName "SecondBrain-SSH-Tunnel"`

### Data migration

`chat.db` likely has minimal/no real sessions (bot was just set up). Fresh tables in Postgres is fine — no migration script needed. If sessions do exist and matter, they can be manually copied row-by-row, but this is almost certainly not worth the effort.

### Fallback preserved

Setting `DATABASE_URL=""` (empty or unset) in `.env` returns both factories to SQLite. The migration is fully reversible.

### pgvector version pinned

Plan uses pgvector `v0.8.0` (source build). If apt has a newer version, prefer apt — it gets security updates automatically.

### Confidence Score: 8/10

The code path is straightforward — `PostgresMemoryDB` is already proven and `PostgresSessionStore` is a direct mirror. The main risk is the VPS setup (pg_hba.conf auth, pgvector install) which depends on Ubuntu version and Postgres version encountered. The plan handles both apt and source-build paths for pgvector.
