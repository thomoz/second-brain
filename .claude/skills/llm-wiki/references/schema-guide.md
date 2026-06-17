# Wiki Schema Guide

Detailed reference for page formats and conventions. See `wiki/SCHEMA.md` for the authoritative rules.

## Frontmatter by Page Type

### Source: Required fields
`title`, `type`, `created`, `updated`, `source_url`, `author`, `publication_date`, `tags`

### Entity: Required fields
`title`, `type`, `created`, `updated`, `sources`, `related`, `tags`

### Concept: Required fields
`title`, `type`, `created`, `updated`, `sources`, `related`, `tags`

### Comparison: Required fields
`title`, `type`, `created`, `updated`, `comparing`, `sources`, `tags`

## Naming Rules

| Type | Pattern | Example |
|------|---------|---------|
| Entity | `entities/kebab-case.md` | `entities/openai.md` |
| Concept | `concepts/kebab-case.md` | `concepts/rag.md` |
| Source | `sources/YYYY-MM-DD-kebab-case.md` | `sources/2026-04-09-some-article.md` |
| Raw | `raw/YYYY-MM-DD-kebab-case.md` | `raw/2026-04-09-some-article.md` |
| Comparison | `comparisons/a-vs-b.md` | `comparisons/rag-vs-fine-tuning.md` |

## Contradiction Handling

When pages conflict, add to both:
```yaml
contradicted_by: [[other-page]]
contradiction_note: "Brief description"
```

## Log Entry Format

```markdown
## [YYYY-MM-DD] ingest | Source Title
- Source: raw/filename.md
- Pages created: list
- Pages updated: list
- Index updated: +N entries

## [YYYY-MM-DD] query | "Question"
- Pages referenced: list

## [YYYY-MM-DD] lint | Health check
- Issues found/fixed/flagged: N
```
