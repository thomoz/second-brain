---
name: llm-wiki
description: |
  Build and maintain an LLM-powered external knowledge wiki that accumulates and synthesizes
  knowledge from articles, papers, and research. Use when the user wants to ingest a source
  into the wiki, query the knowledge base, run a health check, or manage wiki pages.
  Triggers on: "ingest this article", "add to wiki", "wiki query", "query the wiki",
  "what does the wiki say", "lint the wiki", "wiki health check", "knowledge base",
  "add this to the knowledge base", "research wiki", "wiki ingest".
---

# LLM Wiki - External Knowledge Base

An LLM-maintained wiki for accumulating and synthesizing external knowledge. Based on Andrej Karpathy's LLM Wiki pattern.

**What it is**: A persistent, compounding knowledge base. Knowledge is compiled once into structured pages and kept current - not re-derived on every query.

## Architecture

Three layers:
1. **Raw sources** (`wiki/raw/`) - Immutable source documents. Never modified after ingestion.
2. **Wiki pages** (`wiki/entities/`, `concepts/`, `sources/`, `comparisons/`) - LLM-generated and maintained.
3. **Schema** (`wiki/SCHEMA.md`) - Conventions governing structure.

Navigation: Read `wiki/index.md` to find pages, then read them directly. No database, no RAG.

---

## Operations

### Operation 1: Ingest

**Trigger**: User provides a source (URL, article text, file path) and asks to add it to the wiki.

**Workflow**:

1. **Acquire the source**
   - If URL: fetch and convert to markdown, save to `wiki/raw/YYYY-MM-DD-kebab-title.md`
   - If text/file: save or copy to `raw/` with the same naming convention
   - Raw files are immutable - never modify them after this step

2. **Read and discuss**
   - Read the source completely
   - Discuss key takeaways with the user
   - This is interactive - don't silently process

3. **Read wiki context**
   - Read `wiki/SCHEMA.md` for conventions
   - Read `wiki/index.md` to understand existing pages
   - Skim relevant existing pages that may need updating

4. **Create source summary page**
   - Write to `wiki/sources/YYYY-MM-DD-kebab-title.md`
   - Use the source page template from `references/page-templates.md`
   - Include specific claims, data points, and quotes (not just themes)

5. **Create or update entity pages** (by reading the source summary you just wrote)
   - For each person, company, project mentioned significantly
   - If entity page exists: update with new info, add source citation
   - If entity has 3+ mentions across wiki: create new page in `entities/`

6. **Create or update concept pages** (by reading the source summary you just wrote)
   - For each technique, pattern, or idea covered substantively
   - If concept page exists: update, add source citation
   - If concept is significant and new: create new page in `concepts/`

7. **Check for contradictions**
   - Search existing wiki for conflicting claims
   - If found: add `contradicted_by` frontmatter to both pages, note inline
   - Don't resolve automatically - flag for human review

8. **Update navigation files**
   - Update `wiki/index.md` with entries for all new pages
   - Update `wiki/overview.md` if the source changes the big picture
   - Append entry to `wiki/log.md`

9. **Report** what was created/updated

### Operation 2: Query

**Trigger**: User asks a question about wiki knowledge.

**Workflow**:

1. Read `wiki/index.md` to find relevant pages
2. Use Grep/Glob if index isn't sufficient
3. Read relevant wiki pages directly
4. Synthesize answer with citations to specific pages
5. If valuable, offer to file as a new wiki page

### Operation 3: Lint

**Trigger**: User asks to health-check the wiki.

**Workflow**:

1. Run `python .claude/skills/llm-wiki/scripts/wiki_ops.py lint`
2. Review output: broken links, orphan pages, missing frontmatter, unprocessed sources
3. Fix what can be fixed directly
4. Append lint entry to `wiki/log.md`

---

## Important Rules

1. **Never modify files in `raw/`** - sources are immutable
2. **Always update `index.md` and `log.md`** after any operation
3. **Every wiki page must have YAML frontmatter**
4. **Use `[[wiki-links]]`** for cross-references between wiki pages
5. **Sequential ingest** - write source summary FIRST, then create entity/concept pages by reading it
6. **Cite sources** for every claim
7. **Interactive ingest** - discuss sources with the user, don't silently process
8. **Flag contradictions** - don't silently resolve them
