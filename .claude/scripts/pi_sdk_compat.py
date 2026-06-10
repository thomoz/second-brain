"""
pi_sdk_compat - a drop-in compatibility layer that lets Second Brain scripts
run on the Pi coding agent (@earendil-works/pi-coding-agent) instead of the
Claude Agent SDK, without rewriting every call site.

Why this exists
---------------
Starting June 15 2026, Claude Agent SDK / `claude -p` usage on a subscription
is metered against a separate credit at API rates. To stay provider-independent
the Second Brain drives Pi in headless mode instead. Pi has no Python SDK, so
this module spawns `pi --mode json` as a subprocess, parses its JSONL event
stream, and re-exposes the small slice of the Claude Agent SDK API the codebase
actually uses:

    from pi_sdk_compat import (
        AssistantMessage, ClaudeAgentOptions, HookMatcher,
        ResultMessage, TextBlock, query,
    )

Each migrated file changes ONE line: the import source. The call shape
(`async for msg in query(prompt=..., options=ClaudeAgentOptions(...))`,
isinstance checks on AssistantMessage/TextBlock/ResultMessage) is preserved.

Design notes
------------
* Transport: `pi --mode json --print` one-shot. Prompt is passed via an
  `@<tempfile>` argument to avoid Windows argv length limits (the reflection
  prompt embeds the whole memory index).
* History: Pi sessions persist to disk keyed by cwd. Multi-turn continuity
  (the Slack chat) is achieved by reusing a deterministic `--session-id`; the
  on-disk session tree carries full history across separate one-shot calls.
  Stateless calls use `--no-session`.
* Models: Claude tier names (haiku/sonnet/opus) map to Codex models via env
  (see _resolve_model). Any string containing "/" is treated as a literal Pi
  model ref and passed through.
* Tools: Claude tool names map to Pi tool names (Read->read, Glob->find, ...).
  `allowed_tools=[]` -> `--no-tools`. Tools with no Pi builtin (WebSearch,
  WebFetch) are provided by a TS extension (pi_web.ts); PreToolUse hooks
  (bash-danger / SOUL.md protection) are provided by pi_safety.ts.
* Skills: the repo's existing `.claude/skills` are wired into Pi via
  `.pi/settings.json` (created at the worktree root), so skill descriptions
  load headlessly exactly like the claude_code preset did.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Locating the Pi binary
# ---------------------------------------------------------------------------

_DEFAULT_CLI_JS = Path(
    os.path.expandvars(r"%APPDATA%\npm\node_modules\@earendil-works\pi-coding-agent\dist\cli.js")
)


def _find_pi() -> tuple[str, str]:
    """Return (node_executable, cli_js_path). Configurable via env.

    PI_NODE   - node executable (default: 'node' on PATH)
    PI_CLI_JS - path to pi's dist/cli.js (default: npm global install)
    """
    node = os.getenv("PI_NODE") or shutil.which("node") or "node"
    cli = os.getenv("PI_CLI_JS") or str(_DEFAULT_CLI_JS)
    if not Path(cli).exists():
        raise FileNotFoundError(
            f"Pi CLI not found at {cli}. Set PI_CLI_JS to dist/cli.js of "
            f"@earendil-works/pi-coding-agent."
        )
    return node, cli


# Extension files (created alongside this module). Loaded only when relevant.
# Web tools (web_search/fetch_content) come from the globally-installed
# pi-web-access extension already on this machine - no local web extension needed.
_SCRIPTS_DIR = Path(__file__).resolve().parent
PI_SAFETY_EXT = str(_SCRIPTS_DIR / "pi_ext" / "pi_safety.ts")
# PreCompact + SessionEnd hooks (loaded only for multi-turn chat sessions).
PI_MEMORY_EXT = str(_SCRIPTS_DIR / "pi_ext" / "pi_memory_hooks.ts")


def _venv_python() -> str:
    """Path to the scripts venv python, used by the memory-hooks flush spawn."""
    if os.name == "nt":
        p = _SCRIPTS_DIR / ".venv" / "Scripts" / "python.exe"
    else:
        p = _SCRIPTS_DIR / ".venv" / "bin" / "python"
    return str(p) if p.exists() else (shutil.which("python") or "python")


# ---------------------------------------------------------------------------
# Model alias mapping (Claude tier name -> Pi model ref)
# ---------------------------------------------------------------------------

# Cole's Pi is authed with a Codex (ChatGPT) subscription. Cheap tier uses the
# mini for guardrail/scoring; strong tier uses gpt-5.5 for reasoning-heavy work.
_MODEL_CHEAP = os.getenv("PI_MODEL_CHEAP", "openai-codex/gpt-5.4-mini")
_MODEL_MID = os.getenv("PI_MODEL_MID", "openai-codex/gpt-5.4")
_MODEL_STRONG = os.getenv("PI_MODEL_STRONG", "openai-codex/gpt-5.5")
_MODEL_DEFAULT = os.getenv("PI_MODEL_DEFAULT", _MODEL_MID)

_MODEL_ALIASES = {
    "haiku": _MODEL_CHEAP,
    "sonnet": _MODEL_MID,
    "opus": _MODEL_STRONG,
}


def _resolve_model(model: str | None) -> str:
    if not model:
        return _MODEL_DEFAULT
    if "/" in model:  # already a Pi model ref (e.g. openai-codex/gpt-5.5)
        return model
    return _MODEL_ALIASES.get(model.lower(), _MODEL_DEFAULT)


# ---------------------------------------------------------------------------
# Tool name mapping (Claude tool name -> Pi tool name)
# ---------------------------------------------------------------------------

# Pi builtins: read, bash, edit, write, grep, find, ls.
_TOOL_MAP = {
    "Read": "read",
    "Write": "write",
    "Edit": "edit",
    "Bash": "bash",
    "Grep": "grep",
    "Glob": "find",
    "LS": "ls",
    # Provided by the globally-installed pi-web-access extension:
    "WebSearch": "web_search",
    "WebFetch": "fetch_content",
}
# Claude tools with no Pi equivalent and no extension - silently dropped.
# (Skill = skills are auto-loaded and invoked via /skill:name, not a tool.
#  Task = sub-agent spawning is handled by the Python orchestrator instead.
#  NotebookEdit = unused in practice.)
_TOOL_DROP = {"Skill", "Task", "NotebookEdit", "TodoWrite"}


def _map_tools(tools: list[str]) -> list[str]:
    """Map Claude tool names to Pi tool names (drops unsupported ones)."""
    mapped: list[str] = []
    for t in tools:
        if t in _TOOL_DROP:
            continue
        pi_name = _TOOL_MAP.get(t)
        if pi_name and pi_name not in mapped:
            mapped.append(pi_name)
    return mapped


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
    """No-op placeholder. Real enforcement lives in pi_safety.ts.

    The Claude SDK accepted Python hook callbacks; Pi enforces equivalent
    guards (bash-danger, SOUL.md protection) inside a TS extension that the
    query() driver loads automatically when bash/edit tools are enabled.
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
# Command construction
# ---------------------------------------------------------------------------


def _extract_append_prompt(system_prompt: Any) -> str | None:
    """Pull the 'append' text out of a {'type':'preset',...,'append':...} dict.

    The claude_code preset itself maps to Pi's default coding prompt (no flag);
    only the appended custom rules need to be forwarded.
    """
    if isinstance(system_prompt, dict):
        ap = system_prompt.get("append")
        if isinstance(ap, str) and ap.strip():
            return ap
    elif isinstance(system_prompt, str) and system_prompt.strip():
        return system_prompt
    return None


def _build_cmd(prompt_file: Path, options: ClaudeAgentOptions) -> list[str]:
    node, cli = _find_pi()
    cmd: list[str] = [node, cli, "--mode", "json", "--print"]
    if os.getenv("PI_OFFLINE"):
        cmd.append("--offline")

    cmd += ["--model", _resolve_model(options.model)]

    # --- Session continuity ---
    if options.resume:
        # Deterministic, caller-supplied id: created if missing, resumed if present.
        cmd += ["--session-id", str(options.resume)]
    else:
        cmd += ["--no-session"]

    # --- Tools / skills / extensions ---
    tools = options.allowed_tools
    if tools is not None and len(tools) == 0:
        # Pure reasoning call (scoring, mining, guardrail). Keep it lean and
        # deterministic: no tools, no skills, no auto-loaded context files.
        cmd += ["--no-tools", "--no-skills", "--no-context-files"]
    else:
        mapped = _map_tools(tools or [])
        if mapped:
            cmd += ["--tools", ",".join(mapped)]
        # Safety extension whenever the model can touch the filesystem/shell.
        if any(t in mapped for t in ("bash", "edit", "write")) and Path(PI_SAFETY_EXT).exists():
            cmd += ["-e", PI_SAFETY_EXT]
        # PreCompact + SessionEnd memory hooks: only for multi-turn chat sessions
        # (those that resume a session id). One-shot agents (pipeline, heartbeat,
        # reflection) pass no resume id, so they never load these.
        if options.resume and Path(PI_MEMORY_EXT).exists():
            cmd += ["-e", PI_MEMORY_EXT]
        # Web tools (web_search / fetch_content) come from the global
        # pi-web-access extension. Skills + context files stay enabled
        # (the claude_code preset analog).

    # --- Appended system prompt (chat interface rules, etc.) ---
    append = _extract_append_prompt(options.system_prompt)
    if append:
        cmd += ["--append-system-prompt", append]

    # --- Prompt (via @file to dodge argv length limits) ---
    cmd += ["@" + str(prompt_file)]
    return cmd


# ---------------------------------------------------------------------------
# Event-stream parsing
# ---------------------------------------------------------------------------


def _assistant_text_from_message(msg: dict[str, Any]) -> str:
    """Concatenate text content blocks from a Pi message object."""
    parts: list[str] = []
    for block in msg.get("content", []) or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts)


# ---------------------------------------------------------------------------
# The query() entry point
# ---------------------------------------------------------------------------


async def query(
    prompt: str, options: ClaudeAgentOptions | None = None
) -> AsyncIterator[AssistantMessage | ResultMessage]:
    """Run Pi once and yield AssistantMessage(final text) then ResultMessage.

    Async generator, mirroring claude_agent_sdk.query(). Only the FINAL
    assistant turn's text is surfaced (matches how every call site consumes the
    stream - they want the final answer/JSON).
    """
    options = options or ClaudeAgentOptions()

    # Wall-clock backstop: Pi has no --max-turns flag, so a runaway tool loop
    # would otherwise never terminate. Scale a timeout off the original turn
    # budget (the Claude SDK's max_turns) and hard-kill the process if exceeded.
    env_timeout = os.getenv("PI_TIMEOUT_S")
    if env_timeout:
        timeout_s = float(env_timeout)
    else:
        mt = options.max_turns or 5
        timeout_s = min(1800.0, max(120.0, mt * 25.0))

    # Write prompt to a temp file for @file inclusion.
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", prefix="pi_prompt_", delete=False, encoding="utf-8"
    )
    try:
        tmp.write(prompt)
        tmp.close()
        prompt_file = Path(tmp.name)

        cmd = _build_cmd(prompt_file, options)
        cwd = options.cwd or os.getcwd()

        env = os.environ.copy()
        env.setdefault("PI_OFFLINE", env.get("PI_OFFLINE", ""))  # respect external setting
        # For the memory-hooks extension (PreCompact/SessionEnd) to spawn the flush.
        env["SB_FLUSH_SCRIPTS"] = str(_SCRIPTS_DIR)
        env["SB_FLUSH_PYTHON"] = _venv_python()

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        last_assistant_text = ""
        total_cost: float | None = None
        # When the caller supplies a stable session id, round-trip it unchanged
        # so they keep resuming the same session. Only surface Pi's generated id
        # for ephemeral (no-resume) calls.
        resume_provided = bool(options.resume)
        session_id: str | None = options.resume
        had_error = False
        error_detail = ""
        turns = 0

        assert proc.stdout is not None
        # Pi RPC/JSON framing is strict LF; split on b"\n" only.
        buf = b""
        deadline = time.monotonic() + timeout_s
        while True:
            try:
                chunk = await asyncio.wait_for(
                    proc.stdout.read(65536),
                    timeout=max(1.0, deadline - time.monotonic()),
                )
            except TimeoutError:
                had_error = True
                error_detail = f"pi timed out after {timeout_s:.0f}s"
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
                if etype == "session":
                    if not resume_provided:
                        session_id = evt.get("id", session_id)
                elif etype == "message_end":
                    msg = evt.get("message", {})
                    if msg.get("role") == "assistant":
                        text = _assistant_text_from_message(msg)
                        if text.strip():
                            last_assistant_text = text
                        usage = msg.get("usage", {}) or {}
                        cost = (usage.get("cost", {}) or {}).get("total")
                        if isinstance(cost, (int, float)):
                            total_cost = (total_cost or 0.0) + float(cost)
                        if msg.get("stopReason") == "error":
                            had_error = True
                            error_detail = msg.get("errorMessage", "") or error_detail
                elif etype == "turn_end":
                    turns += 1
                elif etype == "message_update":
                    ev = evt.get("assistantMessageEvent", {}) or {}
                    if ev.get("type") == "error":
                        had_error = True
                        error_detail = ev.get("reason", "") or error_detail
                elif etype == "agent_end":
                    # Fallback: if we never captured assistant text, pull it
                    # from the final transcript.
                    if not last_assistant_text:
                        for m in reversed(evt.get("messages", []) or []):
                            if m.get("role") == "assistant":
                                last_assistant_text = _assistant_text_from_message(m)
                                if last_assistant_text:
                                    break

        stderr_bytes = await proc.stderr.read() if proc.stderr else b""
        await proc.wait()

        # Surface a hard failure to the caller's try/except when there's no
        # usable answer AND something went wrong (nonzero exit, an error event,
        # or a timeout). If we got partial text, prefer returning it.
        if not last_assistant_text and (proc.returncode != 0 or had_error):
            stderr_txt = stderr_bytes.decode("utf-8", "replace").strip()
            detail = error_detail or stderr_txt[-500:] or f"pi exited {proc.returncode}"
            raise RuntimeError(f"pi failed (exit {proc.returncode}): {detail}")

        yield AssistantMessage(content=[TextBlock(text=last_assistant_text)])
        yield ResultMessage(
            subtype="error" if had_error else "success",
            total_cost_usd=total_cost,
            session_id=session_id,
            is_error=had_error,
            num_turns=turns,
        )
    finally:
        try:
            Path(tmp.name).unlink()
        except OSError:
            pass


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


if __name__ == "__main__":
    # Tiny smoke test: python pi_sdk_compat.py "Respond with exactly: PI OK"
    _prompt = sys.argv[1] if len(sys.argv) > 1 else "Respond with exactly: PI OK"
    _model = sys.argv[2] if len(sys.argv) > 2 else "haiku"
    print(asyncio.run(run_text(_prompt, ClaudeAgentOptions(model=_model, allowed_tools=[]))))
