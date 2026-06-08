/**
 * pi_memory_hooks - PreCompact + SessionEnd equivalents for the Second Brain chat.
 *
 * Claude Code's PreCompact and SessionEnd hooks do not exist on Pi/Codex. This
 * extension restores them using Pi's native lifecycle events:
 *   - session_before_compact  -> PreCompact  (flush before context is compacted away)
 *   - session_shutdown        -> SessionEnd  (flush when the session is torn down)
 *
 * "Flush" = dump the conversation transcript to a temp file and run memory_flush.py
 * (LLM-summarize important items -> daily log), exactly like the original hooks did.
 *
 * The flush is spawned DETACHED (fire-and-forget) so it never delays the user's
 * reply or blocks compaction/exit. The chat shim loads this extension only for
 * multi-turn chat calls (those that pass --session-id), so one-shot agents
 * (cofounder pipeline, heartbeat, reflection) are never affected.
 *
 * In --print mode every turn is a one-shot process, so session_shutdown fires on
 * EVERY turn. To avoid flushing on every message, shutdown flushes are debounced
 * by conversation growth: only flush when >= MIN_NEW_MESSAGES new messages have
 * accrued since the last flush for this session id. Compaction always flushes.
 *
 * Only `import type` is used, so jiti needs no runtime module resolution.
 */
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { spawn } from "node:child_process";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

const SCRIPTS_DIR = process.env.SB_FLUSH_SCRIPTS ?? "";
const FLUSH_PYTHON = process.env.SB_FLUSH_PYTHON ?? "python";
const MIN_NEW_MESSAGES = Number(process.env.SB_FLUSH_MIN_MESSAGES ?? "6");
const STATE_FILE = SCRIPTS_DIR
  ? path.join(SCRIPTS_DIR, "..", "data", "pi_flush_state.json")
  : path.join(os.tmpdir(), "pi_flush_state.json");

function sessionId(): string {
  const i = process.argv.indexOf("--session-id");
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : "default";
}

function transcript(ctx: ExtensionContext): { text: string; count: number } {
  const lines: string[] = [];
  let count = 0;
  try {
    const sm = ctx.sessionManager as unknown as { getEntries?: () => unknown[] };
    const entries = sm.getEntries ? sm.getEntries() : [];
    for (const e of entries) {
      const entry = e as { type?: string; message?: { role?: string; content?: unknown } };
      if (entry.type !== "message" || !entry.message) continue;
      const role = entry.message.role;
      if (role !== "user" && role !== "assistant") continue;
      const c = entry.message.content;
      let txt = "";
      if (typeof c === "string") {
        txt = c;
      } else if (Array.isArray(c)) {
        txt = c
          .map((b) => (b && typeof (b as { text?: string }).text === "string" ? (b as { text: string }).text : ""))
          .join("");
      }
      if (txt.trim()) {
        lines.push(`### ${role}\n${txt.trim()}`);
        count++;
      }
    }
  } catch {
    /* ignore */
  }
  return { text: lines.join("\n\n"), count };
}

function loadState(): Record<string, number> {
  try {
    return JSON.parse(fs.readFileSync(STATE_FILE, "utf-8")) as Record<string, number>;
  } catch {
    return {};
  }
}

function saveState(state: Record<string, number>): void {
  try {
    fs.mkdirSync(path.dirname(STATE_FILE), { recursive: true });
    fs.writeFileSync(STATE_FILE, JSON.stringify(state), "utf-8");
  } catch {
    /* ignore */
  }
}

function spawnFlush(text: string, reason: string): void {
  if (!SCRIPTS_DIR || !text.trim()) return;
  try {
    const tmp = path.join(os.tmpdir(), `sb_flush_${reason}_${Date.now()}_${process.pid}.md`);
    fs.writeFileSync(tmp, `# Chat conversation (${reason} flush)\n\n${text}\n`, "utf-8");
    // Detached + unref so it survives this (about-to-exit) pi process and never
    // blocks the reply. memory_flush.py reads + deletes the context file itself.
    const child = spawn(FLUSH_PYTHON, ["memory_flush.py", "--context-file", tmp], {
      cwd: SCRIPTS_DIR,
      detached: true,
      stdio: "ignore",
    });
    child.unref();
  } catch {
    /* ignore */
  }
}

export default function (pi: ExtensionAPI): void {
  // PreCompact: always flush before context is compacted away.
  pi.on("session_before_compact", (_event, ctx) => {
    const { text, count } = transcript(ctx);
    spawnFlush(text, "precompact");
    const state = loadState();
    state[sessionId()] = count;
    saveState(state);
  });

  // SessionEnd: fires every --print turn, so debounce by conversation growth.
  pi.on("session_shutdown", (_event, ctx) => {
    const { text, count } = transcript(ctx);
    const sid = sessionId();
    const state = loadState();
    const last = state[sid] ?? 0;
    if (count - last >= MIN_NEW_MESSAGES) {
      spawnFlush(text, "sessionend");
      state[sid] = count;
      saveState(state);
    }
  });
}
