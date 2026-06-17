# Wiki Schema

_Conventions and workflows governing the LLM Wiki. Read this before any wiki operation._

## Purpose and Scope

This wiki accumulates **external knowledge only** - articles, papers, research, industry developments, technical concepts.

## Three-Layer Architecture

1. **Raw sources** (`raw/`) - Immutable source documents. The LLM reads from them but never modifies them.
2. **Wiki pages** (subdirectories) - LLM-generated and maintained markdown pages organized by type.
3. **This schema** (`SCHEMA.md`) - Conventions governing structure, naming, and workflows.

## Page Types

| Type | Directory | Purpose | Example |
|------|-----------|---------|---------|
| **Entity** | `entities/` | People, companies, projects, tools | `entities/anthropic.md` |
| **Concept** | `concepts/` | Techniques, patterns, ideas | `concepts/context-engineering.md` |
| **Source** | `sources/` | Summary of an ingested source | `sources/2026-04-09-some-article.md` |
| **Comparison** | `comparisons/` | Side-by-side analysis | `comparisons/rag-vs-fine-tuning.md` |
| **Overview** | root | High-level synthesis | `overview.md` |

## Frontmatter Format

Every wiki page (except index.md, log.md, and SCHEMA.md) must have YAML frontmatter:

```yaml
---
title: Page Title
type: entity | concept | source | comparison | overview
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: [source-filename-1, source-filename-2]
related: [[concept-page]], [[entity-page]]
tags: [relevant, tags]
---
```

Source pages add: `source_url`, `author`, `publication_date`
Comparison pages add: `comparing: [[topic-a]], [[topic-b]]`

## Naming Conventions

- **Entity pages**: `entities/kebab-case-name.md`
- **Concept pages**: `concepts/kebab-case-name.md`
- **Source summaries**: `sources/YYYY-MM-DD-kebab-case-title.md`
- **Raw sources**: `raw/YYYY-MM-DD-kebab-case-title.md`
- **Comparisons**: `comparisons/topic-a-vs-topic-b.md`
- All lowercase kebab-case. No spaces, no underscores.

## Cross-Referencing Rules

- Use `[[wiki-link]]` Obsidian syntax for links between wiki pages
- Use standard markdown `[text](path)` for raw source references
- Cross-references should be bidirectional (if A links to B, B should link to A)
- Every claim should cite its source

## When to Create vs Update Pages

- **Create a new page** when an entity/concept has 3+ mentions across wiki pages
- **Update an existing page** when new information adds to what's already there
- When in doubt, update rather than create

## Ingest Order (Important)

Source ingestion must be **sequential, not parallel**:

1. Save raw source to `raw/`
2. Read the raw source fully
3. Write the source summary in `sources/` (with specific claims, quotes, data points)
4. THEN create/update entity and concept pages **by reading the source summary**

This keeps the citation chain intact.

## Quality Standards

- Every claim should cite a source
- Every page should have at least one inbound link (sources/ exempt - linked from index.md)
- Frontmatter must be complete
- The overview page should be updated when a source materially changes the big picture
