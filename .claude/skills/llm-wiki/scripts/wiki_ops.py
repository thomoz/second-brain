"""
CLI for deterministic wiki operations: stats, lint, validate.

Usage:
    python wiki_ops.py stats
    python wiki_ops.py lint
    python wiki_ops.py validate <page-path>

Expects wiki/ directory at the project root (same level as .claude/).
Adjust WIKI_DIR below if your wiki lives elsewhere.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Wiki root - resolved absolute path (.claude/skills/llm-wiki/scripts → .claude/skills/llm-wiki → .claude/skills → .claude → project root)
WIKI_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "wiki"

PAGE_DIRS = {
    "entities": WIKI_DIR / "entities",
    "concepts": WIKI_DIR / "concepts",
    "sources": WIKI_DIR / "sources",
    "comparisons": WIKI_DIR / "comparisons",
}

WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)

REQUIRED_FRONTMATTER = {"title", "type", "created", "updated"}


def get_all_pages() -> list[Path]:
    """Return all .md wiki pages (excluding raw/, SCHEMA.md, index.md, log.md)."""
    pages: list[Path] = []
    for d in PAGE_DIRS.values():
        if d.exists():
            pages.extend(d.glob("*.md"))
    overview = WIKI_DIR / "overview.md"
    if overview.exists():
        pages.append(overview)
    return pages


def get_all_page_stems() -> set[str]:
    """Return stems of all wiki pages for link resolution."""
    stems: set[str] = set()
    for page in get_all_pages():
        stems.add(page.stem)
    return stems


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


def extract_wiki_links(text: str) -> list[str]:
    """Extract all [[wiki-link]] targets from text."""
    return WIKI_LINK_RE.findall(text)


def cmd_stats() -> None:
    """Print wiki statistics."""
    print("=== Wiki Stats ===\n")

    for name, d in PAGE_DIRS.items():
        count = len(list(d.glob("*.md"))) if d.exists() else 0
        print(f"  {name}: {count} pages")

    raw_dir = WIKI_DIR / "raw"
    raw_count = len([f for f in raw_dir.glob("*.md") if f.name != ".gitkeep"]) if raw_dir.exists() else 0
    print(f"  raw sources: {raw_count}")

    total = sum(len(list(d.glob("*.md"))) for d in PAGE_DIRS.values() if d.exists())
    overview = WIKI_DIR / "overview.md"
    if overview.exists():
        total += 1
    print(f"\n  Total wiki pages: {total}")

    # Last ingest from log
    log_file = WIKI_DIR / "log.md"
    if log_file.exists():
        log_text = log_file.read_text(encoding="utf-8")
        ingest_dates = re.findall(r"## \[(\d{4}-\d{2}-\d{2})\] ingest", log_text)
        if ingest_dates:
            print(f"  Last ingest: {ingest_dates[-1]}")
        else:
            print("  Last ingest: none")

    print()


def cmd_lint() -> None:
    """Run automated wiki health checks."""
    issues: list[str] = []
    pages = get_all_pages()
    page_stems = get_all_page_stems()

    # 1. Check for broken wiki links
    for page in pages:
        text = page.read_text(encoding="utf-8")
        links = extract_wiki_links(text)
        for link in links:
            target = link.split("|")[0].strip()
            if target not in page_stems:
                issues.append(f"BROKEN LINK: [[{target}]] in {page.relative_to(WIKI_DIR)}")

    # 2. Check for missing frontmatter
    for page in pages:
        text = page.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if not fm:
            issues.append(f"MISSING FRONTMATTER: {page.relative_to(WIKI_DIR)}")
        else:
            missing = REQUIRED_FRONTMATTER - set(fm.keys())
            if missing:
                issues.append(f"INCOMPLETE FRONTMATTER: {page.relative_to(WIKI_DIR)} missing {missing}")

    # 3. Find orphan pages (no inbound links except from index.md)
    inbound: dict[str, int] = {p.stem: 0 for p in pages}
    index_file = WIKI_DIR / "index.md"
    index_links: set[str] = set()
    if index_file.exists():
        index_links = set(extract_wiki_links(index_file.read_text(encoding="utf-8")))

    for page in pages:
        text = page.read_text(encoding="utf-8")
        for link in extract_wiki_links(text):
            target = link.split("|")[0].strip()
            if target in inbound:
                inbound[target] += 1

    for stem, count in inbound.items():
        if count == 0 and stem not in index_links and stem != "overview":
            issues.append(f"ORPHAN PAGE: {stem} (no inbound links from other wiki pages)")

    # 4. Find raw sources without summaries
    raw_dir = WIKI_DIR / "raw"
    sources_dir = WIKI_DIR / "sources"
    if raw_dir.exists() and sources_dir.exists():
        raw_files = {f.stem for f in raw_dir.glob("*.md")}
        summary_files = {f.stem for f in sources_dir.glob("*.md")}
        for raw_stem in raw_files:
            if raw_stem not in summary_files:
                issues.append(f"UNPROCESSED SOURCE: raw/{raw_stem}.md has no summary in sources/")

    # Report
    print("=== Wiki Lint ===\n")
    if issues:
        for issue in issues:
            print(f"  {issue}")
        print(f"\n  Total issues: {len(issues)}")
    else:
        print("  No issues found. Wiki is healthy.")
    print()


def cmd_validate(page_path: str) -> None:
    """Validate a specific wiki page."""
    full_path = WIKI_DIR / page_path
    if not full_path.exists():
        print(f"ERROR: Page not found: {full_path}")
        sys.exit(1)

    text = full_path.read_text(encoding="utf-8")
    page_stems = get_all_page_stems()
    issues: list[str] = []

    # Check frontmatter
    fm = parse_frontmatter(text)
    if not fm:
        issues.append("Missing YAML frontmatter")
    else:
        missing = REQUIRED_FRONTMATTER - set(fm.keys())
        if missing:
            issues.append(f"Missing frontmatter fields: {missing}")

    # Check wiki links
    links = extract_wiki_links(text)
    for link in links:
        target = link.split("|")[0].strip()
        if target not in page_stems:
            issues.append(f"Broken link: [[{target}]]")

    # Report
    print(f"=== Validate: {page_path} ===\n")
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  Page is valid.")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Wiki operations CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("stats", help="Show wiki statistics")
    sub.add_parser("lint", help="Run wiki health checks")

    validate_parser = sub.add_parser("validate", help="Validate a specific page")
    validate_parser.add_argument("page", help="Path to page relative to wiki/ dir")

    args = parser.parse_args()

    if args.command == "stats":
        cmd_stats()
    elif args.command == "lint":
        cmd_lint()
    elif args.command == "validate":
        cmd_validate(args.page)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
