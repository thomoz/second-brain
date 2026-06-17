"""
Memory health check for Second Brain structured vault.

Usage:
    python memory_lint.py          # Run all checks, print report
    python memory_lint.py --stats  # Print page counts per directory
    python memory_lint.py --fix    # Auto-fix: add missing MEMORY.md index entries
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("AGENT_INVOKED_BY", "memory_lint")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DECISIONS_DIR, ENTITIES_DIR, MEMORY_FILE, TOPICS_DIR, VAULT_DIR

WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
DATE_RE = re.compile(r"\((\w{3})\s+(\d{1,2})\)")  # matches (Jun 17) format

PAGE_DIRS = {
    "entities": ENTITIES_DIR,
    "topics": TOPICS_DIR,
    "decisions": DECISIONS_DIR,
}

MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def get_all_page_stems() -> set[str]:
    """Return stems of all entity/topic/decision pages."""
    stems: set[str] = set()
    for d in PAGE_DIRS.values():
        if d.exists():
            for p in d.glob("*.md"):
                stems.add(p.stem)
    return stems


def get_all_pages() -> list[Path]:
    """Return all entity/topic/decision .md pages."""
    pages: list[Path] = []
    for d in PAGE_DIRS.values():
        if d.exists():
            pages.extend(d.glob("*.md"))
    return pages


def extract_wiki_links(text: str) -> list[str]:
    """Extract all [[wiki-link]] targets from text, ignoring backtick-escaped links."""
    # Strip `[[...]]` patterns (documentation examples, not actual links)
    cleaned = re.sub(r"`\[\[[^\]]+\]\]`", "", text)
    return WIKI_LINK_RE.findall(cleaned)


def parse_frontmatter(text: str) -> dict[str, str]:
    """Extract frontmatter fields as a simple key-value dict."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def check_broken_links() -> list[str]:
    """Check structured .md files in Memory/ for [[name]] — verify entity/topic/decision page exists.
    Skips daily/ logs and drafts/ — those are raw text and may contain any [[...]] patterns.
    """
    issues: list[str] = []
    page_stems = get_all_page_stems()
    skip_dirs = {"daily", "drafts"}
    for md_file in VAULT_DIR.rglob("*.md"):
        # Skip raw daily logs and drafts — natural language may contain [[...]] patterns
        parts = md_file.relative_to(VAULT_DIR).parts
        if parts and parts[0] in skip_dirs:
            continue
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for link in extract_wiki_links(text):
            target = link.split("|")[0].strip()
            if target not in page_stems:
                rel = md_file.relative_to(VAULT_DIR)
                issues.append(f"BROKEN LINK: [[{target}]] in {rel}")
    return issues


def check_orphan_pages() -> list[str]:
    """Check pages in entities/ or topics/ that are not listed in MEMORY.md."""
    issues: list[str] = []
    if not MEMORY_FILE.exists():
        return issues
    memory_text = MEMORY_FILE.read_text(encoding="utf-8")
    memory_links = set(extract_wiki_links(memory_text))
    for dir_name in ("entities", "topics"):
        d = PAGE_DIRS[dir_name]
        if not d.exists():
            continue
        for page in d.glob("*.md"):
            if page.stem not in memory_links:
                issues.append(f"ORPHAN PAGE: {dir_name}/{page.name} (not listed in MEMORY.md)")
    return issues


def check_stale_active_items() -> list[str]:
    """Check MEMORY.md ## Active Items for entries with dates > 30 days old."""
    issues: list[str] = []
    if not MEMORY_FILE.exists():
        return issues
    text = MEMORY_FILE.read_text(encoding="utf-8")
    marker = "## Active Items"
    if marker not in text:
        return issues
    idx = text.index(marker)
    next_section = text.find("\n## ", idx + len(marker))
    section = text[idx:next_section] if next_section != -1 else text[idx:]

    today = datetime.now()
    for line in section.splitlines():
        m = DATE_RE.search(line)
        if not m:
            continue
        month_abbr, day_str = m.group(1), m.group(2)
        month = MONTH_MAP.get(month_abbr)
        if not month:
            continue
        year = today.year
        try:
            item_date = datetime(year, month, int(day_str))
            # If that date is in the future, assume it was last year
            if item_date > today:
                item_date = item_date.replace(year=year - 1)
            if (today - item_date).days > 30:
                issues.append(f"STALE ACTIVE ITEM (>{30}d): {line.strip()}")
        except ValueError:
            continue
    return issues


def check_missing_frontmatter() -> list[str]:
    """Check entity/topic pages that lack a YAML frontmatter block."""
    issues: list[str] = []
    for page in get_all_pages():
        try:
            text = page.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = parse_frontmatter(text)
        if not fm:
            rel = page.relative_to(VAULT_DIR)
            issues.append(f"MISSING FRONTMATTER: {rel}")
    return issues


def check_large_pages(max_bytes: int = 5000) -> list[str]:
    """Warn about entity/topic pages > max_bytes (suggest splitting)."""
    issues: list[str] = []
    for page in get_all_pages():
        try:
            size = page.stat().st_size
        except OSError:
            continue
        if size > max_bytes:
            rel = page.relative_to(VAULT_DIR)
            issues.append(f"LARGE PAGE ({size}B > {max_bytes}B): {rel} — consider splitting")
    return issues


def cmd_stats() -> None:
    """Print page counts per directory."""
    print("=== Memory Vault Stats ===\n")
    for name, d in PAGE_DIRS.items():
        count = len([p for p in d.glob("*.md") if p.name != ".gitkeep"]) if d.exists() else 0
        print(f"  {name}: {count} pages")

    profile_dir = VAULT_DIR / "Profile"
    profile_count = len(list(profile_dir.glob("*.md"))) if profile_dir.exists() else 0
    print(f"  Profile: {profile_count} files")

    daily_dir = VAULT_DIR / "daily"
    daily_count = len(list(daily_dir.glob("*.md"))) if daily_dir.exists() else 0
    print(f"  daily logs: {daily_count} files")

    if MEMORY_FILE.exists():
        size = MEMORY_FILE.stat().st_size
        print(f"\n  MEMORY.md size: {size}B (limit: 5000B)")
        if size > 5000:
            print("  WARNING: MEMORY.md exceeds 5KB target")

    print()


def cmd_lint() -> None:
    """Run all health checks and report issues."""
    all_issues: list[str] = []

    all_issues.extend(check_broken_links())
    all_issues.extend(check_orphan_pages())
    all_issues.extend(check_stale_active_items())
    all_issues.extend(check_missing_frontmatter())
    all_issues.extend(check_large_pages())

    print("=== Memory Lint ===\n")
    if all_issues:
        for issue in all_issues:
            print(f"  {issue}")
        print(f"\n  Total issues: {len(all_issues)}")
    else:
        print("  No issues found. Vault is healthy.")
    print()


def cmd_fix() -> None:
    """Auto-fix: add missing index entries to MEMORY.md Entity Pages section."""
    if not MEMORY_FILE.exists():
        print("MEMORY.md not found — nothing to fix.")
        return

    memory_text = MEMORY_FILE.read_text(encoding="utf-8")
    memory_links = set(extract_wiki_links(memory_text))

    new_entries: list[str] = []
    for dir_name in ("entities", "topics"):
        d = PAGE_DIRS[dir_name]
        if not d.exists():
            continue
        for page in sorted(d.glob("*.md")):
            if page.name == ".gitkeep":
                continue
            if page.stem not in memory_links:
                new_entries.append(f"- [[{page.stem}]] — (auto-added by memory_lint --fix)")

    if not new_entries:
        print("No missing index entries found — nothing to fix.")
        return

    # Append to Entity Pages section if present, otherwise append at end
    marker = "## Entity Pages"
    if marker in memory_text:
        idx = memory_text.index(marker)
        next_section = memory_text.find("\n## ", idx + len(marker))
        insert_at = next_section if next_section != -1 else len(memory_text)
        updated = memory_text[:insert_at] + "\n" + "\n".join(new_entries) + memory_text[insert_at:]
    else:
        updated = memory_text.rstrip() + "\n\n## Entity Pages\n\n" + "\n".join(new_entries) + "\n"

    MEMORY_FILE.write_text(updated, encoding="utf-8")
    print(f"Fixed: added {len(new_entries)} missing index entries to MEMORY.md.")
    for entry in new_entries:
        print(f"  {entry}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Memory vault health check")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--stats", action="store_true", help="Print page counts per directory")
    group.add_argument("--fix", action="store_true", help="Auto-fix missing MEMORY.md index entries")
    args = parser.parse_args()

    if args.stats:
        cmd_stats()
    elif args.fix:
        cmd_fix()
    else:
        cmd_lint()


if __name__ == "__main__":
    main()
