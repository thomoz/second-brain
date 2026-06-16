# Handoff: "Ask Me Questions" — Personal Profile System

## What This Is

A system for building a deep personal knowledge base about Shaun through on-demand coaching conversations. The premise: the more I know Shaun as a person — not just his businesses — the better I can coach, advise, and assist him across all areas of his life.

Analogy: a human coach or personal assistant becomes more valuable the more they know their client. This system is how I accumulate that depth over time.

---

## Design Decisions Already Made

### Trigger phrase
`Ask Me Questions` — typed locally or said via WhatsApp while driving.
- Simple, literal, impossible to forget
- Works in both contexts without ambiguity

### Storage location
New directory: `Memory/Profile/`
Suggested files (starting point — open to revision):
- `values.md` — what matters to Shaun, non-negotiables
- `goals.md` — short/medium/long term across all life areas
- `history.md` — how he got here, key turning points, lessons learned
- `personality.md` — how he works, what energises/drains him
- `health.md` — energy patterns, sleep, fitness, lifestyle
- `relationships.md` — family, key people in his life
- `finances.md` — full financial picture beyond business cash buffer

### Question delivery
- One question at a time — wait for answer before asking next
- Complex questions are fine (Shaun confirmed driving context handles depth)
- I choose question order — professional/coaching logic applies
  (broad context → values/goals → history → present situation → specifics)

### Question ordering philosophy
Think: a skilled coach meeting a new client for the first time.
They'd start with big picture (who are you, what do you want, what's life like?)
before drilling into specifics (health, finances, relationships).
Suggested order:
1. Current life picture — what's working, what's not
2. Values and non-negotiables
3. Goals across all life areas (not just business)
4. Personal history and key turning points
5. Relationships and support network
6. Health, energy, lifestyle
7. Financial picture (holistic, not just business)
8. Specific deep dives as gaps emerge

### Data handling
- Answers flushed to daily log and reflected into `Memory/Profile/` files
- Flush and reflection pipelines must capture "Ask Me Questions" session content
- I file information in the most appropriate `Memory/Profile/` file, not just dump it in daily log
- Over time, profile files grow richer as answers accumulate

---

## Open Questions / Things to Finalise in Next Session

1. **WhatsApp trigger**: when Shaun types "Ask Me Questions" via WhatsApp, how does the bot know to enter this mode vs. a normal query? Does it need a special handler in the chat engine, or is the phrase enough for the LLM to recognise and act on?

2. **Session length**: how many questions per "Ask Me Questions" session? Open-ended until Shaun says stop, or a suggested number (e.g. 5)?

3. **Profile file seeding**: do we pre-populate `Memory/Profile/` files with headings/structure, or let them grow organically from answers?

4. **Existing data migration**: `USER.md` has some relevant info (businesses, email accounts). Does `USER.md` stay as-is (operational quick-reference) while `Profile/` holds the depth? Or do we merge/refactor?

5. **Skill or hook?**: should "Ask Me Questions" be implemented as a skill (`.claude/skills/ask-me-questions/`) that I invoke, or handled purely by prompt recognition? A skill would give it consistent behaviour across local + WhatsApp.

6. **Reflection integration**: when `memory_reflect.py` runs, should it specifically look for `Memory/Profile/` updates and treat them differently (e.g. never expire, always promote)?

---

## How to Load This in a New Session

1. Run `/prime` first (loads codebase context)
2. Read this file: `O:\AI\Dynamous\Courses\second-brain-workshop\.agent\plans\ask-me-questions-handoff.md`
3. Brief discussion to close the open questions above
4. Run `/plan-feature` to generate the full implementation plan

---

## Context: Where This Fits in the Architecture

- **Local**: triggered in Claude Code chat, same as all other sessions
- **WhatsApp**: triggered via the WhatsApp bot (`.claude/chat/`) — needs the chat engine to recognise the phrase and enter profile-building mode
- **Storage**: `Memory/Profile/` (new directory, to be created)
- **Flush**: session-end and pre-compact hooks already capture conversation — profile answers must be extracted and filed by `memory_flush.py` or `memory_reflect.py`
- **Search**: once indexed, profile content will be available via `memory_search.py` hybrid RAG — I can pull relevant profile context automatically during any conversation

---

## One-Line Summary

Build a system where Shaun says "Ask Me Questions", I ask one question at a time to build a deep personal profile stored in `Memory/Profile/`, usable across local and WhatsApp sessions to make every coaching/advisory conversation smarter.
