"""
sdk_compat - backend selector for the Second Brain agent layer.

Every Second Brain script imports the agent surface from HERE, not from a
specific backend. One environment variable picks which backend actually runs:

    SB_AGENT_BACKEND=claude  (default) -> claude_agent_sdk   (native Claude SDK)
    SB_AGENT_BACKEND=pi                -> pi_sdk_compat       (Pi, multi-provider)
    SB_AGENT_BACKEND=codex             -> codex_sdk_compat    (OpenAI Codex CLI)

All three expose an identical slice of the Claude Agent SDK API
(`query`, `ClaudeAgentOptions`, `AssistantMessage`, `TextBlock`,
`ResultMessage`, `HookMatcher`), so switching the entire system between Claude,
Pi, and Codex is a single env var - no code change at any call site.

    from sdk_compat import AssistantMessage, ClaudeAgentOptions, query

`run_text` is a convenience helper defined here (the native Claude SDK does not
ship one), so it works the same across all three backends.

To switch: set SB_AGENT_BACKEND in the environment (or .env), e.g.
    setx SB_AGENT_BACKEND codex     # Windows, persists for new shells
The default is Claude, so unset behavior is the original native SDK.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

_BACKEND = os.getenv("SB_AGENT_BACKEND", "claude").strip().lower()
if _BACKEND not in ("claude", "pi", "codex"):
    _BACKEND = "claude"
BACKEND = _BACKEND

# For static analysis, the three backends are drop-in equivalents, so we type
# against the native Claude SDK. At runtime the elif/else chain picks the real
# backend. (mypy treats `if TYPE_CHECKING` as True, so it never sees the
# same-named-but-distinct types of the other backends and stays clean.)
if TYPE_CHECKING:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        HookMatcher,
        ResultMessage,
        TextBlock,
        query,
    )
elif _BACKEND == "pi":
    from pi_sdk_compat import (
        AssistantMessage,
        ClaudeAgentOptions,
        HookMatcher,
        ResultMessage,
        TextBlock,
        query,
    )
elif _BACKEND == "codex":
    from codex_sdk_compat import (
        AssistantMessage,
        ClaudeAgentOptions,
        HookMatcher,
        ResultMessage,
        TextBlock,
        query,
    )
else:
    try:
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            HookMatcher,
            ResultMessage,
            TextBlock,
            query,
        )
    except ModuleNotFoundError:
        # claude-code-sdk (PyPI) uses ClaudeCodeOptions; alias to keep call sites unchanged
        from claude_code_sdk import (  # type: ignore[no-redef]
            AssistantMessage,
            HookMatcher,
            ResultMessage,
            TextBlock,
            query as _raw_query,
        )
        from claude_code_sdk import ClaudeCodeOptions as ClaudeAgentOptions  # type: ignore[no-redef]
        from claude_code_sdk._errors import MessageParseError as _MessageParseError  # type: ignore

        def _patch_claude_sdk_message_parser() -> None:
            """Monkeypatch the parse_message reference in client.py so unknown message
            types (e.g. rate_limit_event) return None instead of raising.

            client.py imports parse_message at module level (`from .message_parser
            import parse_message`), so we must patch the name in the client module
            namespace — not in message_parser — to intercept calls from process_query.

            This lets the stream continue past the unknown event so that
            AssistantMessage and ResultMessage still arrive. None values are filtered
            out in query() below before being yielded to callers.

            claude_code_sdk 0.0.25 crashes on rate_limit_event because the Claude CLI
            started emitting it but the SDK doesn't yet know how to parse it.
            """
            try:
                import claude_code_sdk._internal.client as _client
                import claude_code_sdk._internal.message_parser as _mp
                _orig = _mp.parse_message

                def _safe_parse(data):  # type: ignore[no-untyped-def]
                    try:
                        return _orig(data)
                    except _MessageParseError as exc:
                        if "Unknown message type" in str(exc):
                            return None  # skip; stream continues
                        raise

                # Patch in both places: the definition module AND the client's
                # local import reference (the latter is what process_query actually calls).
                _mp.parse_message = _safe_parse
                _client.parse_message = _safe_parse  # type: ignore[attr-defined]
            except Exception:
                pass  # best-effort; original behaviour resumes if patching fails

        def _patch_claude_cmd_windows() -> None:
            """On Windows, rewire SubprocessCLITransport._find_cli to return the
            claude.exe binary path instead of claude.CMD.

            When the SDK invokes claude.CMD, Python subprocess wraps it with
            `cmd.exe /C` which has an 8192-character command line limit. The
            heartbeat prompt (~10K chars) exceeds this limit, causing
            "Command failed with exit code 1" on every heartbeat run.

            Calling claude.exe directly uses CreateProcess (32767-char limit)
            and bypasses cmd.exe entirely.
            """
            import os
            if os.name != "nt":
                return
            try:
                import re
                import shutil
                from pathlib import Path as _Path
                import claude_code_sdk._internal.transport.subprocess_cli as _cli_mod

                _orig_find = _cli_mod.SubprocessCLITransport._find_cli

                def _patched_find_cli(self_obj):  # type: ignore[no-untyped-def]
                    result = _orig_find(self_obj)
                    if result.lower().endswith((".cmd", ".bat")):
                        try:
                            content = _Path(result).read_text(encoding="utf-8", errors="replace")
                            # Match: "...\claude.exe"   %* or "%dp0%\node_modules\...\claude.exe"
                            m = re.search(
                                r'"?%dp0%\\([^"\r\n%]+\.exe)"?\s*%\*', content
                            )
                            if m:
                                rel = m.group(1).replace("/", "\\")
                                dp0 = str(_Path(result).parent)
                                exe = str(_Path(dp0) / rel)
                                if _Path(exe).exists():
                                    return exe
                        except Exception:
                            pass
                    return result

                _cli_mod.SubprocessCLITransport._find_cli = _patched_find_cli
            except Exception:
                pass

        _patch_claude_sdk_message_parser()
        _patch_claude_cmd_windows()

        async def query(prompt: str, options: "ClaudeAgentOptions | None" = None):  # type: ignore[no-redef]
            """Pass-through wrapper that filters None values emitted by the patched parser."""
            async for msg in _raw_query(prompt=prompt, options=options):
                if msg is not None:
                    yield msg


async def run_text(prompt: str, options: ClaudeAgentOptions | None = None) -> str:
    """Concatenate the assistant text from a query() run. Backend-agnostic."""
    out = ""
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for b in msg.content:
                if isinstance(b, TextBlock):
                    out += b.text
    return out


# Alias so callers can use AgentOptions as well as ClaudeAgentOptions
AgentOptions = ClaudeAgentOptions

__all__ = [
    "BACKEND",
    "AgentOptions",
    "AssistantMessage",
    "ClaudeAgentOptions",
    "HookMatcher",
    "ResultMessage",
    "TextBlock",
    "query",
    "run_text",
]
