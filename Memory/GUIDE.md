# Memory Filing Guide

_Quick reference: where does this information go?_

---

## Memory/MEMORY.md — Lean Index
The master table of contents. Always loaded into every session.
- **Active Items**: time-sensitive tasks, unresolved questions, things to follow up
- **Entity/Topic pointers**: `[[wiki-links]]` to dedicated pages
- **Preferences**: standing communication and system preferences
- Keep under 5KB. Never dump bulk content here.

## Memory/entities/ — People, Projects, Companies, Businesses
One page per noun that accumulates history.
- Each of Shaun's 5 businesses has a page
- Key venues, contractors, clients get pages when they have 3+ mentions
- Projects (SongbookDB features, new show ideas) get pages when active
- Format: YAML frontmatter + Status, Key Decisions, Related sections

## Memory/topics/ — Recurring Themes
One page per theme that spans multiple decisions or sessions.
- Investment strategy, hosting growth, tech architecture
- Think: "this topic keeps coming up" → topic page
- Format: YAML frontmatter + sections organized by theme, not chronology

## Memory/decisions/ — Completed Decision Archives
Quarterly archives of decisions that are done and shipped.
- "Chose X over Y" and it's done → here
- Ongoing decisions with future implications → topic page instead
- Named: 2026-Q2.md, 2026-Q3.md, etc.

## Memory/Profile/ — Personal Profile (Deep)
Long-form answers about who Shaun is as a person.
- values.md, goals.md, history.md, personality.md, health.md, relationships.md, finances.md
- Built via "Ask Me Questions" sessions
- Append with dates — history is valuable, never overwrite
- NEVER expires — always permanent

## Memory/core-memories.md — Permanent Explicit Memories
Small, high-value items explicitly asked to remember forever.
User-initiated only — say "add to core memories" or "remember this forever".

## Memory/daily/ — Raw Daily Logs
Append-only chronological record. One file per day.
Raw material that reflection reviews nightly. Never edit past entries.

## Memory/drafts/ — Email/Message Drafts
Active, sent, and expired draft replies. Never auto-sent.

## Memory/USER.md — Operational Config
Email accounts, business names, integration config, timezone.
NOT personal profile depth (that's Profile/).

## wiki/ — External Knowledge Base
Articles, research papers, investment theses you've ingested.
Completely separate from Memory/. Navigate via wiki/index.md.
Add sources by saying "ingest this article" and providing the text or URL.

---

_When in doubt: specific person/project/business → entities/. Recurring theme → topics/.
Personal depth → Profile/. Finished decision → decisions/. External reading → wiki/._
