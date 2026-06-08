/**
 * pi_safety - Pi extension replacing the Second Brain's Claude-Agent-SDK
 * PreToolUse hooks (shared.validate_bash_command + memory_reflect.protect_soul_file).
 *
 * Loaded explicitly via `-e` only for Second Brain tool-using calls, so it does
 * not affect any other Pi usage on this machine. Runs deterministically in
 * headless (--mode json) mode: it blocks without prompting (no UI available).
 *
 * Only `import type` is used, so jiti needs no runtime module resolution.
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

// Mirror of shared.DANGEROUS_BASH_PATTERNS (keep in sync).
const DANGEROUS_BASH_PATTERNS: string[] = [
  "rm -rf /",
  "rm -rf ~",
  "rm -rf /*",
  "rm -rf .",
  "rm -rf *",
  "> /dev/sda",
  "> /dev/hda",
  "dd if=/dev/zero",
  "dd if=/dev/random",
  "mkfs.",
  ":(){:|:&};:",
  ":(){ :|:& };:",
  "curl | sh",
  "curl | bash",
  "wget | sh",
  "wget | bash",
  "chmod -R 777 /",
  "chmod -R 000 /",
  "chown -R",
  "history -c",
  "> /dev/tcp",
  "truncate -s 0",
  "shred",
  "Remove-Item -Recurse -Force",
  "Format-Volume",
  "del /s",
  "del /q",
  "del /a",
  "Remove-Item *",
  "Set-ExecutionPolicy Unrestricted",
];

function dangerousMatch(command: string): string | null {
  const normalized = command.split(/\s+/).join(" ");
  const candidates = [normalized];
  for (const m of normalized.matchAll(/\$\(([^)]+)\)/g)) candidates.push(m[1]);
  for (const m of normalized.matchAll(/`([^`]+)`/g)) candidates.push(m[1]);
  for (const cmd of candidates) {
    const stripped = cmd.replace(/(?:\/usr)?\/s?bin\//g, "");
    for (const pat of DANGEROUS_BASH_PATTERNS) {
      if (stripped.includes(pat)) return pat;
    }
  }
  return null;
}

// Files protected from automated edits/writes (memory_reflect.protect_soul_file).
function isProtectedPath(p: string): boolean {
  return /(^|[\\/])SOUL\.md$/i.test(p);
}

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event) => {
    const name = event.toolName;
    const input = (event.input ?? {}) as Record<string, unknown>;

    if (name === "bash") {
      const command = String(input.command ?? "");
      const hit = dangerousMatch(command);
      if (hit) {
        return { block: true, reason: `Blocked dangerous command pattern: ${hit}` };
      }
    }

    if (name === "edit" || name === "write") {
      const path = String(input.path ?? input.file_path ?? "");
      if (isProtectedPath(path)) {
        return { block: true, reason: "SOUL.md is protected from automated edits" };
      }
    }

    return undefined;
  });
}
