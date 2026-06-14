# Handoff: Heartbeat State Not Persisting on VPS

## Problem
Every heartbeat run on the VPS shows `is_first_run=True` and `Diff: new_emails=11, new_events=11`.
This means the heartbeat state file is not being saved or found between runs.

## Expected Behaviour
After the first run, `heartbeat-state.json` should persist so subsequent runs only diff
against the previous state. `is_first_run` should be `False` after the first successful run.

## State File Location (per CLAUDE.md)
`.claude/data/state/heartbeat-state.json` (relative to project root)
Full VPS path: `/home/secondbrain/second-brain/.claude/data/state/heartbeat-state.json`

## What to Check First
1. Does the file exist on VPS?
   ```bash
   ls -la ~/second-brain/.claude/data/state/
   ```
2. Does it have correct permissions (secondbrain user should own it)?
3. Is it being written at all after a heartbeat run?
   ```bash
   cat ~/second-brain/.claude/data/state/heartbeat-state.json
   ```
4. Check heartbeat.py to see how it reads/writes state — look for the state file path logic

## Likely Causes
- Directory doesn't exist (setup_vps.sh created it but double-check)
- Permissions wrong (systemd runs as `secondbrain` user — file must be writable by that user)
- Path resolution issue — heartbeat.py may resolve the state path relative to `__file__`
  location or CWD; confirm it resolves to the correct absolute path on VPS

## Context
- VPS: `secondbrain@137.184.102.104`
- Project root: `/home/secondbrain/second-brain`
- Systemd service user: `secondbrain`
- Heartbeat timer fires every 30 min; check log at:
  `/home/secondbrain/second-brain/.claude/scripts/heartbeat_runs.log`
- Rate limit note: Gemini free tier daily quota was exhausted on 2026-06-14 from testing.
  Resets at midnight UTC (10am AEST). First clean LLM run expected 2026-06-15 morning.
