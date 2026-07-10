---
title: Assistant Commands
type: system
updated: 2026-06-23
---
# Personal Assistant Command Manifest

This file is loaded into every WhatsApp session. It defines how to handle save commands.
All writes must be to files inside `Memory/` only — never modify files outside `Memory/`.

---

## Save & Notes

### Trigger Phrases
- "save this" / "remember this" / "log this" / "note this"
- "save to [entity]" — e.g. "save to Juno characters", "save to Simone", "save to scratch"
- "remind me to [X]" → `Memory/scratch.md` Reminders section
- "add to [section]" — route as per routing table below

### Routing Table
| Phrase / keyword            | Target                                                   |
|-----------------------------|----------------------------------------------------------|
| "juno" / "wonderdog"        | `Memory/entities/juno-wonderdog/` — pick sub-file        |
| "simone" / "kensington"     | `Memory/entities/simone-kensington/` — pick sub-file     |
| "investment" / "stocks"     | `Memory/entities/investing/investment-ideas.md`          |
| "remind me"                 | `Memory/scratch.md` → under `## Reminders`                 |
| no entity named             | `Memory/scratch.md` → under `## Ideas`                     |

### Sub-File Routing (for entity folders)
Pick the sub-file based on content type — do not ask Shaun:
- Character descriptions, traits, backstory → `characters.md`
- Plot, narrative, scene ideas, story beats → `story.md`
- General notes, decisions, development log entries → `development.md`
- High-level overview or summary → `index.md`

### Save Format
Append content under a dated heading at the end of the target section:

```
## YYYY-MM-DD [WhatsApp save]
[content verbatim or lightly formatted]
```

Do not overwrite existing content. Always append.

### Confirmation
Always reply with a single short confirmation after saving:
- "Saved to Juno characters."
- "Reminder added to scratch."
- "Saved to investment strategy."

If the destination is genuinely ambiguous (two entities equally likely), ask one clarifying
question before writing. Do not ask if the context makes the destination clear.

### "Save this" — Infer from Context
If Shaun says "save this" with no explicit entity, infer the subject from the most recent
exchange in the conversation. If the last topic was Juno, route to Juno development.
If the conversation has no clear subject, route to `Memory/scratch.md` Ideas section, or if
in doubt, ask Shaun for clarification.

### New Entity Flow
If Shaun names an entity with no existing folder:
1. Suggest the file path (e.g. "I'll create `Memory/entities/new-entity/index.md` — confirm?")
2. Wait for confirmation before writing.
3. On confirm, create the file with a minimal stub and append the content.

---

## Reminders

_(Future section — remind me to X commands route via scratch.md Reminders for now.)_

---

## Email Drafting

_(Future section — drafts go to Memory/drafts/active/ with YAML frontmatter.)_

---

## Calendar

_(Future section — log-only for now.)_

---

## General Research

_(Future section — "look up X and save what you find".)_

---

## Entity Management

_(Future section — create/update entity pages from WhatsApp.)_
