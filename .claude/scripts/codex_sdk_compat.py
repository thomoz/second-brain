"""
codex_sdk_compat - a drop-in compatibility layer that lets Second Brain scripts
run on the OpenAI Codex CLI (`codex exec`) instead of the Claude Agent SDK,
without rewriting every call site.

This is the sibling of pi_sdk_compat.py. Both expose the exact same surface
(the small slice of the Claude Agent SDK the codebase uses), so a call site can
run on either backend with no code change. The selector module sdk_compat.py
picks between them via the SB_AGENT_BACKEND env var.

Why this exists
---------------
Starting June 15 2026, Claude Agent SDK / `claude -p` usage on a subscription is
metered against a separate credit at API rates. A lot of people would rather move
their agentic tooling onto Codex (which runs flat-rate on a ChatGPT subscription)
than onto Pi. This module drives the standalone Codex CLI headless so the Second
Brain can do exactly that:

    from codex_sdk_compat import (
        AssistantMessage, ClaudeAgentOptions, HookMatcher,
        ResultMessage, TextBlock, query,
    )

Each migrated file changes ONE line: the import source (or, via sdk_compat.py,
nothing at all). The call shape
(`async for msg in query(prompt=..., options=ClaudeAgentOptions(...))`,
isinstance checks on AssistantMessage/TextBlock/ResultMessage) is preserved.

How it maps onto Codex (and where it differs from Pi)
-----------------------------------------------------
* Transport: `codex exec --json -o <file>` one-shot. The prompt is streamed to
  the process's stdin (Codex exec reads stdin when the prompt arg is `-`), fed by
  a concurrent writer task so a large prompt cannot deadlock against stdout.
* Final text: read from the `--output-last-message` file. That file is the stable
  channel for the answer across Codex versions; the JSONL event stream is parsed
  in parallel only for the thread id (continuity), token usage, and errors.
* Models: Claude tier names (haiku/sonnet/opus) map to Codex models via env
  (see _resolve_model). Any unrecognized string is passed through as a literal
  Codex model ref (e.g. "gpt-5.4", "gpt-5.2-codex").
* Tools / safety: Codex exec has no per-tool allow-list and no tool_call hook
  (Pi's pi_safety.ts has no direct equivalent). Safety is enforced with the OS
  sandbox instead: a pure-reasoning call (allowed_tools=[]) runs `read-only`; a
  tool-using call runs `workspace-write`, which blocks writes outside the project
  root. Approval is forced to `never` (headless cannot prompt). This is coarser
  than Pi's pattern-level bash/SOUL.md blocking; see the PRD for the trade-off.
* Skills: Codex exec has no system-prompt flag, so skill descriptions and any
  appended system prompt are folded into the prompt text as a preamble. The model
  reads the named SKILL.md on its own, exactly as it did under the claude_code
  preset and under Pi.
* Sessions: stateless calls run `--ephemeral`. Multi-turn continuity (the Slack
  chat) cannot pin an arbitrary session id at creation the way Pi can, so this
  module keeps a deterministic-key -> Codex-thread-id map on disk
  (.claude/data/codex_sessions.json) and resumes via `codex exec resume <id>`.
  Call sites still pass the same deterministic key as `resume`, so no call site
  changes.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

# ---------------------------------------------------------------------------
# Locating the Codex binary
# ---------------------------------------------------------------------------

_DEFAULT_CLI_JS = Path(
    os.path.expandvars(r"%APPDATA%\npm\node_modules\@openai\codex\bin\codex.js")
)


def _codex_cmd_prefix() -> list[str]:
    """Return the argv prefix that launches Codex. Configurable via env.

    CODEX_BIN  - a native codex executable to call directly (highest priority)
    CODEX_NODE - node executable (default: 'node' on PATH)
    CODEX_CLI_JS - path to codex's bin/codex.js (default: npm global install)

    Defaults to `node <codex.js>` because the npm `codex` shim on Windows is a
    .cmd/.ps1 wrapper that asyncio.create_subprocess_exec cannot run directly.
    """
    native = os.getenv("CODEX_BIN")
    if native and Path(native).exists():
        return [native]

    node = os.getenv("CODEX_NODE") or shutil.which("node") or "node"
    cli = os.getenv("CODEX_CLI_JS") or str(_DEFAULT_CLI_JS)
    if not Path(cli).exists():
        raise FileNotFoundError(
            f"Codex CLI not found at {cli}. Install @openai/codex globally, or set "
            f"CODEX_BIN to a native codex executable or CODEX_CLI_JS to bin/codex.js."
        )
    return [node, cli]


_SCRIPTS_DIR = Path(__file__).resolve().parent
_DATA_DIR = _SCRIPTS_DIR.parent / "data"
_SESSIONS_FILE = _DATA_DIR / "codex_sessions.json"
_SKILLS_DIR = _SCRIPTS_DIR.parent / "skills"


# ---------------------------------------------------------------------------
# Model alias mapping (Claude tier name -> Codex model ref)
# ---------------------------------------------------------------------------

# Cole's Codex is a ChatGPT subscription. Cheap tier uses the mini for
# guardrail/scoring; strong tier uses the top model the installed Codex CLI
# exposes. On Codex CLI 0.117 the listed models are gpt-5.4 ("Strong model for
# everyday coding") and gpt-5.4-mini; gpt-5.5 requires a NEWER Codex CLI and is
# rejected with a 400 if requested. So strong defaults to gpt-5.4 here; when a
# newer CLI ships gpt-5.5, set CODEX_MODEL_STRONG=gpt-5.5. Override any tier to
# whatever your Codex plan/CLI exposes.
_MODEL_CHEAP = os.getenv("CODEX_MODEL_CHEAP", "gpt-5.4-mini")
_MODEL_MID = os.getenv("CODEX_MODEL_MID", "gpt-5.4")
_MODEL_STRONG = os.getenv("CODEX_MODEL_STRONG", "gpt-5.4")
_MODEL_DEFAULT = os.getenv("CODEX_MODEL_DEFAULT", _MODEL_MID)

_MODEL_ALIASES = {
    "haiku": _MODEL_CHEAP,
    "sonnet": _MODEL_MID,
    "opus": _MODEL_STRONG,
}


def _resolve_model(model: str | None) -> str:
    if not model:
        return _MODEL_DEFAULT
    return _MODEL_ALIASES.get(model.lower(), model)


# ---------------------------------------------------------------------------
# Tool interpretation
# ---------------------------------------------------------------------------

# Codex has no allow-list; we only need to know (a) whether this is a lean
# reasoning call and (b) whether web access should be enabled.
_WEB_TOOLS = {"WebSearch", "WebFetch"}


def _wants_web(tools: list[str] | None) -> bool:
    return bool(tools) and any(t in _WEB_TOOLS for t in (tools or []))


# ---------------------------------------------------------------------------
# Message types (mirror the claude_agent_sdk shapes the call sites use)
# ---------------------------------------------------------------------------


@dataclass
class TextBlock:
    text: str


@dataclass
class AssistantMessage:
    content: list[TextBlock]


@dataclass
class ResultMessage:
    subtype: str
    total_cost_usd: float | None
    session_id: str | None = None
    is_error: bool = False
    num_turns: int = 0


@dataclass
class HookMatcher:
    """No-op placeholder. Codex enforces safety via the OS sandbox instead.

    The Claude SDK accepted Python hook callbacks (bash-danger, SOUL.md
    protection). Codex exec has no tool_call hook; the equivalent guard here is
    the sandbox mode chosen per call (read-only for reasoning, workspace-write
    for tool use). Finer-grained command blocking would need a custom MCP shell
    wrapper - see the migration PRD.
    """

    matcher: str = ""
    hooks: list[Any] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Options (accepts the full kwarg surface the codebase passes)
# ---------------------------------------------------------------------------


class ClaudeAgentOptions:
    """Mirrors claude_agent_sdk.ClaudeAgentOptions for the kwargs we use.

    Unknown kwargs are accepted and ignored so call sites need no edits beyond
    the import swap.
    """

    def __init__(
        self,
        *,
        cwd: str | None = None,
        model: str | None = None,
        allowed_tools: list[str] | None = None,
        system_prompt: Any = None,
        setting_sources: list[str] | None = None,
        permission_mode: str | None = None,
        max_turns: int | None = None,
        hooks: Any = None,
        resume: str | None = None,
        max_budget_usd: float | None = None,
        **_ignored: Any,
    ) -> None:
        self.cwd = cwd
        self.model = model
        self.allowed_tools = allowed_tools
        self.system_prompt = system_prompt
        self.setting_sources = setting_sources
        self.permission_mode = permission_mode
        self.max_turns = max_turns
        self.hooks = hooks
        self.resume = resume
        self.max_budget_usd = max_budget_usd


# ---------------------------------------------------------------------------
# Session id mapping (deterministic key -> Codex thread id)
# ---------------------------------------------------------------------------


def _load_sessions() -> dict[str, str]:
    try:
        data = json.loads(_SESSIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items()}
    return {}


def _save_session(key: str, thread_id: str) -> None:
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        sessions = _load_sessions()
        sessions[key] = thread_id
        _SESSIONS_FILE.write_text(
            json.dumps(sessions, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def reset_session(resume_key: str) -> bool:
    """Remove a session mapping so the next call starts a fresh Codex thread.

    Returns True if the key was found and removed, False if it wasn't present.
    The vault (daily logs, MEMORY.md, entity pages) is unaffected.
    """
    sessions = _load_sessions()
    if resume_key not in sessions:
        return False
    del sessions[resume_key]
    try:
        _SESSIONS_FILE.write_text(json.dumps(sessions, indent=2), encoding="utf-8")
    except OSError:
        return False
    return True


# ---------------------------------------------------------------------------
# Prompt composition (Codex exec has no system-prompt flag)
# ---------------------------------------------------------------------------


def _extract_append_prompt(system_prompt: Any) -> str | None:
    """Pull the 'append' text out of a {'type':'preset',...,'append':...} dict."""
    if isinstance(system_prompt, dict):
        ap = system_prompt.get("append")
        if isinstance(ap, str) and ap.strip():
            return ap
    elif isinstance(system_prompt, str) and system_prompt.strip():
        return system_prompt
    return None


def _read_frontmatter_field(text: str, field_name: str) -> str:
    """Tiny YAML-frontmatter scalar reader (name/description only)."""
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end == -1:
        return ""
    for line in text[3:end].splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(f"{field_name}:"):
            return stripped.split(":", 1)[1].strip().strip("\"'")
    return ""


def _skills_preamble(cwd: str) -> str:
    """Enumerate available skills (name + description + path) for the prompt.

    Mirrors how the claude_code preset and Pi surfaced skill descriptions: the
    model sees what is available and reads the SKILL.md it needs on its own.
    """
    skills_root = Path(cwd) / ".claude" / "skills"
    if not skills_root.is_dir():
        skills_root = _SKILLS_DIR
    if not skills_root.is_dir():
        return ""
    lines: list[str] = []
    for skill_md in sorted(skills_root.glob("*/SKILL.md")):
        try:
            head = skill_md.read_text(encoding="utf-8")[:2000]
        except OSError:
            continue
        name = _read_frontmatter_field(head, "name") or skill_md.parent.name
        desc = _read_frontmatter_field(head, "description")
        lines.append(f"- {name}: {desc} (read: {skill_md})")
    if not lines:
        return ""
    return (
        "# Available Skills\n"
        "These project skills are available. To use one, read its SKILL.md at "
        "the path shown and follow its instructions. Do not invoke a slash "
        "command; just read the file and act on it.\n" + "\n".join(lines)
    )


def _compose_prompt(
    user_prompt: str, options: ClaudeAgentOptions, lean: bool
) -> str:
    parts: list[str] = []
    append = _extract_append_prompt(options.system_prompt)
    if append:
        parts.append("# Additional Instructions\n" + append)
    if not lean:
        preamble = _skills_preamble(options.cwd or os.getcwd())
        if preamble:
            parts.append(preamble)
    if lean:
        parts.append(
            "Answer directly. Do not run shell commands or use tools; "
            "respond with the requested output only."
        )
    parts.append(user_prompt)
    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Command construction
# ---------------------------------------------------------------------------


def _build_argv(
    options: ClaudeAgentOptions,
    *,
    resume_thread_id: str | None,
    ephemeral: bool,
    lean: bool,
    last_msg_file: Path,
    cwd: str,
) -> list[str]:
    argv = _codex_cmd_prefix() + ["exec"]
    if resume_thread_id:
        argv += ["resume", resume_thread_id]

    argv += ["-m", _resolve_model(options.model)]

    sandbox = "read-only" if lean else "workspace-write"
    argv += ["-c", f"sandbox_mode={sandbox}"]
    argv += ["-c", "approval_policy=never"]
    if _wants_web(options.allowed_tools):
        argv += ["-c", "tools.web_search=true"]
    # Tool-using calls need network: the Second Brain's bash runs hit Gmail,
    # Slack, Asana, and MCP servers. Codex's workspace-write sandbox blocks
    # network by default, so enable it (override with CODEX_NETWORK_ACCESS=0).
    if not lean and os.getenv("CODEX_NETWORK_ACCESS", "1") != "0":
        argv += ["-c", "sandbox_workspace_write.network_access=true"]

    # cwd / ephemeral only apply to a fresh session; resume reuses the
    # original session's working root and persistence.
    if not resume_thread_id:
        argv += ["-C", cwd]
        if ephemeral:
            argv += ["--ephemeral"]

    argv += [
        "--skip-git-repo-check",
        "--json",
        "-o",
        str(last_msg_file),
        "-",  # read the prompt from stdin
    ]
    return argv


# ---------------------------------------------------------------------------
# Event-stream parsing helpers
# ---------------------------------------------------------------------------


def _item_text(item: dict[str, Any]) -> str:
    """Extract assistant text from a Codex item object (defensive)."""
    itype = item.get("item_type") or item.get("type") or ""
    if itype in ("assistant_message", "agent_message", "message"):
        text = item.get("text")
        if isinstance(text, str):
            return text
        # Some shapes nest content blocks.
        parts: list[str] = []
        for block in item.get("content", []) or []:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "".join(parts)
    return ""


async def _feed_stdin(proc: asyncio.subprocess.Process, data: str) -> None:
    """Write the prompt to the process stdin concurrently (avoids deadlock)."""
    if proc.stdin is None:
        return
    try:
        proc.stdin.write(data.encode("utf-8"))
        await proc.stdin.drain()
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Codex tmp cleanup (workaround for --ephemeral not flushing .tmp on VPS)
# ---------------------------------------------------------------------------


def _clear_codex_tmp() -> None:
    """Delete ~/.codex/.tmp so Codex starts clean on every ephemeral call.

    Despite --ephemeral, the Codex CLI accumulates plugin/context state in its
    .tmp directory between runs on the VPS. Each run then inherits the previous
    run's full context, causing the input to double every 30 minutes. Clearing
    .tmp before each ephemeral call restores the intended stateless behaviour.
    Only ephemeral calls are cleaned; session (chat-bot) calls are unaffected.
    """
    codex_tmp = Path.home() / ".codex" / ".tmp"
    if not codex_tmp.is_dir():
        return
    try:
        import shutil
        shutil.rmtree(codex_tmp)
        codex_tmp.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# The query() entry point
# ---------------------------------------------------------------------------


async def query(
    prompt: str, options: ClaudeAgentOptions | None = None
) -> AsyncIterator[AssistantMessage | ResultMessage]:
    """Run Codex once and yield AssistantMessage(final text) then ResultMessage.

    Async generator, mirroring claude_agent_sdk.query(). Only the FINAL
    assistant turn's text is surfaced (matches how every call site consumes the
    stream - they want the final answer/JSON).
    """
    options = options or ClaudeAgentOptions()
    cwd = options.cwd or str(Path(__file__).resolve().parent.parent.parent)

    # A lean (pure-reasoning) call has allowed_tools explicitly empty.
    lean = options.allowed_tools is not None and len(options.allowed_tools) == 0

    # Resolve session continuity.
    resume_key = options.resume or ""
    resume_thread_id: str | None = None
    if resume_key:
        resume_thread_id = _load_sessions().get(resume_key)
    ephemeral = not resume_key  # truly stateless calls leave no session on disk
    if ephemeral:
        _clear_codex_tmp()

    # Wall-clock backstop: Codex exec has no turn cap, so a runaway tool loop
    # would otherwise never terminate. Scale a timeout off the original turn
    # budget (the Claude SDK's max_turns) and hard-kill the process if exceeded.
    env_timeout = os.getenv("CODEX_TIMEOUT_S")
    if env_timeout:
        timeout_s = float(env_timeout)
    else:
        mt = options.max_turns or 5
        timeout_s = min(1800.0, max(120.0, mt * 25.0))

    last_msg_file = Path(
        _DATA_DIR / f".codex_last_{os.getpid()}_{int(time.monotonic() * 1000)}.txt"
    )
    composed = _compose_prompt(prompt, options, lean)

    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    argv = _build_argv(
        options,
        resume_thread_id=resume_thread_id,
        ephemeral=ephemeral,
        lean=lean,
        last_msg_file=last_msg_file,
        cwd=cwd,
    )

    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=os.environ.copy(),
    )

    writer = asyncio.ensure_future(_feed_stdin(proc, composed))

    thread_id: str | None = resume_thread_id
    stream_text = ""
    had_error = False
    error_detail = ""
    turns = 0

    assert proc.stdout is not None
    buf = b""
    deadline = time.monotonic() + timeout_s
    try:
        while True:
            try:
                chunk = await asyncio.wait_for(
                    proc.stdout.read(65536),
                    timeout=max(1.0, deadline - time.monotonic()),
                )
            except TimeoutError:
                had_error = True
                error_detail = f"codex timed out after {timeout_s:.0f}s"
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                break
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = raw.rstrip(b"\r").decode("utf-8", "replace").strip()
                if not line or not line.startswith("{"):
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    continue
                etype = evt.get("type")
                if etype == "thread.started":
                    tid = evt.get("thread_id")
                    if isinstance(tid, str):
                        thread_id = tid
                elif etype in ("item.completed", "item.updated"):
                    item = evt.get("item")
                    if isinstance(item, dict):
                        text = _item_text(item)
                        if text.strip():
                            stream_text = text
                elif etype == "turn.completed":
                    turns += 1
                elif etype == "turn.failed":
                    had_error = True
                    err = evt.get("error")
                    if isinstance(err, dict):
                        error_detail = str(err.get("message", "")) or error_detail
                elif etype == "error":
                    had_error = True
                    msg = evt.get("message")
                    if isinstance(msg, str):
                        error_detail = msg or error_detail
    finally:
        if not writer.done():
            writer.cancel()

    stderr_bytes = await proc.stderr.read() if proc.stderr else b""
    await proc.wait()

    # Final text: prefer the --output-last-message file, fall back to the
    # text captured from the event stream.
    final_text = ""
    try:
        final_text = last_msg_file.read_text(encoding="utf-8").strip()
    except OSError:
        final_text = ""
    if not final_text:
        final_text = stream_text.strip()

    # Persist a newly created session id so the next turn can resume it.
    if resume_key and not resume_thread_id and thread_id:
        _save_session(resume_key, thread_id)

    try:
        last_msg_file.unlink()
    except OSError:
        pass

    if not final_text and (proc.returncode != 0 or had_error):
        stderr_txt = stderr_bytes.decode("utf-8", "replace").strip()
        detail = error_detail or stderr_txt[-500:] or f"codex exited {proc.returncode}"
        raise RuntimeError(f"codex failed (exit {proc.returncode}): {detail}")

    # Round-trip the caller's deterministic key as the session id when one was
    # supplied (so they keep resuming the same logical session); otherwise
    # surface Codex's own thread id.
    surfaced_session = resume_key if resume_key else thread_id

    yield AssistantMessage(content=[TextBlock(text=final_text)])
    yield ResultMessage(
        subtype="error" if had_error else "success",
        total_cost_usd=None,  # flat-rate on a ChatGPT subscription
        session_id=surfaced_session,
        is_error=had_error,
        num_turns=turns,
    )


# ---------------------------------------------------------------------------
# Convenience: synchronous one-shot text helper (handy for tests)
# ---------------------------------------------------------------------------


async def run_text(prompt: str, options: ClaudeAgentOptions | None = None) -> str:
    out = ""
    async for msg in query(prompt, options):
        if isinstance(msg, AssistantMessage):
            for b in msg.content:
                if isinstance(b, TextBlock):
                    out += b.text
    return out


# Re-export the parser for unit tests that feed canned events (see
# _codex_compat_tests.py). cast keeps mypy --strict happy on the dynamic dict.
def _parse_event_line(line: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(line))


if __name__ == "__main__":
    _prompt = sys.argv[1] if len(sys.argv) > 1 else "Respond with exactly: CODEX OK"
    _model = sys.argv[2] if len(sys.argv) > 2 else "haiku"
    print(asyncio.run(run_text(_prompt, ClaudeAgentOptions(model=_model, allowed_tools=[]))))
