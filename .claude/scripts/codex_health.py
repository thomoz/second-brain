"""Codex model-availability health check.

Built 2026-10-21 after the ChatGPT-account backend stopped accepting the
configured model (gpt-5.5) outright -- even the installed CLI's own bare
default (no -m override) got the same 400, because the CLI itself (0.139)
had fallen behind what the backend currently serves. Fixing it needed a
privileged `npm install -g @openai/codex` (0.139 -> 0.163), which picked up
a new default (gpt-6.1-sol) the backend does accept. See
GREEN-API-troubleshooting.md's "Two stacked bugs" entry and
codex_sdk_compat.py's model-default comment for the full incident.

Two distinct outcomes on a "model not supported" failure:
  - Self-healable: the CLI has already moved on to a new default (e.g.
    someone ran `codex update` for an unrelated reason) but .env/code still
    names the old one. Patch .env and restart the bot -- no privilege
    needed, matches exactly what was done by hand this time once the CLI
    update landed.
  - Not self-healable: the CLI's own bare default is ALSO rejected, meaning
    the CLI itself needs updating -- a `sudo npm install` this agent/script
    cannot run. Alert with the exact next command instead of failing silent.

Deliberately mirrors whatsapp_health.py's structure: same state-file dedup
pattern, same notification channels, same "alert once per new degradation"
behavior.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
from pathlib import Path

from config import BOT_LOCK_FILE, CODEX_HEALTH_STATE_FILE, SCRIPTS_DIR, now_local
from shared import load_state, save_state

ENV_PATH = SCRIPTS_DIR / ".env"

_NOT_SUPPORTED_RE = re.compile(r"'([^']+)' model is not supported")
_BANNER_MODEL_RE = re.compile(r"^model:\s*(\S+)", re.MULTILINE)
_MODEL_ENV_KEYS = ("CODEX_MODEL_CHEAP", "CODEX_MODEL_MID", "CODEX_MODEL_STRONG")


def _probe_configured_model() -> tuple[bool, str]:
    """Trivial Codex call using whatever's currently configured (CODEX_MODEL_MID).
    Returns (ok, error_detail) -- error_detail is "" on success."""
    import asyncio

    from codex_sdk_compat import ClaudeAgentOptions, run_text

    try:
        asyncio.run(run_text("ok", ClaudeAgentOptions(allowed_tools=[])))
        return True, ""
    except Exception as e:
        return False, str(e)


def _probe_cli_bare_default() -> tuple[str | None, bool]:
    """Bare `codex exec`, no -m override, read-only sandbox -- lets the CLI pick
    its own current default and reports it via the startup banner ("model: X"),
    regardless of whether the call then succeeds or fails. Bypasses
    codex_sdk_compat.py entirely: it always passes an explicit -m flag, so it
    can't be used to discover the CLI's own bare default.

    Returns (model_name_or_None, succeeded).
    """
    from codex_sdk_compat import _codex_cmd_prefix

    try:
        argv = _codex_cmd_prefix() + [
            "exec",
            "-c", "sandbox_mode=read-only",
            "-c", "approval_policy=never",
            "--skip-git-repo-check",
            "ok",
        ]
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    except Exception:
        return None, False

    m = _BANNER_MODEL_RE.search(result.stdout)
    model = m.group(1) if m else None
    succeeded = result.returncode == 0 and "ERROR:" not in result.stdout
    return model, succeeded


def _patch_env_model(new_model: str) -> bool:
    """Blind find-and-replace of the CODEX_MODEL_* lines in .env. Never reads
    or logs any other line -- only ever touches lines whose key is one of
    _MODEL_ENV_KEYS, so nothing else in the file (secrets included) is
    inspected or reported on."""
    if not ENV_PATH.exists():
        return False
    try:
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    kept = [ln for ln in lines if ln.split("=", 1)[0] not in _MODEL_ENV_KEYS]
    kept += [f"{key}={new_model}" for key in _MODEL_ENV_KEYS]
    try:
        ENV_PATH.write_text("\n".join(kept) + "\n", encoding="utf-8")
        return True
    except OSError:
        return False


def _restart_whatsapp_bot() -> bool:
    """Same-user SIGTERM to the bot's own PID (read from its lock file) so
    systemd's Restart=always relaunches it with the patched .env picked up
    fresh. No sudo involved -- same mechanism used to restart it by hand
    during today's fix."""
    if not BOT_LOCK_FILE.exists():
        return False
    try:
        pid = int(BOT_LOCK_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        return True
    except (OSError, ValueError):
        return False


def run_codex_model_check() -> str | None:
    """Probe the configured Codex model; self-heal or alert on a new
    degradation. Deduped via CODEX_HEALTH_STATE_FILE like whatsapp_health.py's
    checks -- fires once per new degradation, not every heartbeat cycle.
    Returns the message sent (self-heal note or alert), or None if healthy /
    already alerted / not this check's failure class.
    """
    from notifications import send_toast_notification, send_whatsapp_notification

    state = load_state(CODEX_HEALTH_STATE_FILE)
    was_alerted = state.get("alerted", False)

    ok, detail = _probe_configured_model()
    if ok:
        if was_alerted:
            state["alerted"] = False
            state["recovered_at"] = now_local().isoformat()
            save_state(CODEX_HEALTH_STATE_FILE, state)
        return None

    rejected_match = _NOT_SUPPORTED_RE.search(detail)
    if not rejected_match:
        return None  # a different failure class (network, auth, ...) -- not this check's job
    configured_model = rejected_match.group(1)

    bare_model, bare_ok = _probe_cli_bare_default()

    if bare_ok and bare_model and bare_model != configured_model:
        patched = _patch_env_model(bare_model)
        restarted = patched and _restart_whatsapp_bot()
        message = (
            f"Codex model auto-updated: '{configured_model}' was rejected, the "
            f"CLI's own default is now '{bare_model}'."
            + (" Patched config and restarted the bot." if restarted else
               " Could not patch config/restart automatically -- check manually.")
        )
        send_toast_notification("Second Brain: Codex model self-healed", message)
        send_whatsapp_notification(f"\U0001f527 {message}")
        state["alerted"] = False
        state["self_healed_at"] = now_local().isoformat()
        save_state(CODEX_HEALTH_STATE_FILE, state)
        return message

    if not was_alerted:
        message = (
            f"⚠️ Codex model '{configured_model}' was rejected, and the "
            f"CLI's own bare default ({bare_model or 'unknown'}) is rejected too -- "
            f"this needs a CLI update, not a config change. On the VPS: "
            f"`codex doctor` to confirm a newer version is available, then "
            f"`sudo npm install -g @openai/codex`. See GREEN-API-troubleshooting.md "
            f"(\"Two stacked bugs\") for the full fix sequence."
        )
        send_toast_notification("Second Brain: Codex model needs a CLI update", message)
        send_whatsapp_notification(message)
        state["alerted"] = True
        state["alerted_at"] = now_local().isoformat()
        save_state(CODEX_HEALTH_STATE_FILE, state)
        return message

    return None
