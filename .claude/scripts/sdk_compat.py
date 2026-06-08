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
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        HookMatcher,
        ResultMessage,
        TextBlock,
        query,
    )


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
