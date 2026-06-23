# Memory Index

_Active items and pointers to structured memory pages. Always loaded into sessions._

---

## Active Items

_Time-sensitive, unresolved, or needs follow-up. Reflection promotes items here; archive to decisions/ when done._

- (Jun 17) Second Brain nightly reflection running on VPS — structured output via Codex backend
- (Jun 17) VPS: secondbrain@137.184.102.104, dir /home/secondbrain/second-brain
- (Jun 17) Branch: post-creation-tweaks-20260617

- (Jun 17) Elanora Squash: send Nicky another banner colour option instead of yellow on red
- (Jun 17) Verify nightly reflection auto-writes to MEMORY.md with correct blank lines
- (Jun 18) Confirm July 15 trivia coverage with Nicky Haslam; first away-date cover is tentatively handled
- (Jun 18) Review unread SuperChoice tax invoice from 11:04am
- (Jun 18) Check tenancy invoice status; Alison Bennett said payment method is unchanged
- (Jun 19) Review Marilyn Dunn email about The Foundery First Floor Program opportunity
- (Jun 19) Confirm whether Briefs Media $499 charge went through and fix any billing issue
- (Jun 19) Review revised Apple Developer Program License Agreement before release work
- (Jun 20) Check Messenger and review Victor Northhead's message from 11:10
- (Jun 20) Reply to Nicky to clarify which venue the demo video relates to
- (Jun 22) Review SongbookDB admin password change and account lock alerts from 15:06-15:08
- (Jun 22) Handle Facebook user data deletion request for SongbookDB from 17:19 AEST
- (Jun 22) Check eBay message from rockstore2010 at 11:26 if tied to an active order or issue
- (Jun 22) Check Pawshake review from Vivien and respond if appropriate
- (Jun 22) Read laragon-setup-handoff.md before resuming SongbookDB PHP 8.0 upgrade
- (Jun 22) Choose display format before executing the Briefs Finance tool plan
- (Jun 22) Fix missing pre-compact hook target `.claude/hooks/pre-compact-flush.py`
## Entity Pages

- [[songbookdb/index]] — karaoke song list software, ~170 subscribers, code-signing blocker on desktop app, PHP upgrade in progress
- [[billy-goat-karaoke]] — hosted karaoke, Boyles Hotel Sutherland Thursdays 8pm
- [[dingos-music-bingo]] — hosted music bingo
- [[thommos-trivia]] — hosted trivia nights
- [[host-masters-entertainment]] — umbrella entity for all live entertainment
- [[karaoke-night-app]] — low priority, ToS concerns, early build with Victor Northhead
- [[creative-work]] — FiNN TWiST music + Juno: Wonderdog film, on hold
- [[juno-wonderdog/index]] — animated film project; characters, story, development log sub-pages
- [[venues]] — all show venues and distances

## Topic Pages

- [[investment-strategy]] — portfolio, crash-prep strategy, watchlist
- [[hosting-growth]] — venue sales, show efficiency, ad creation bottleneck

## Decision Archives

- [[2026-Q2]] — Q2 2026 decisions (Apr–Jun 2026)

## Preferences

- Communication: brief bullets, no fluff, no end-of-turn recaps
- Deploy target: Windows local + DigitalOcean VPS (cloud sync via git)
- LLM backend: Codex (ChatGPT flat-rate) via codex_sdk_compat.py
- Never auto-send emails, messages, or social posts

---

_Resolve `[[name]]` → Memory/entities/name.md or Memory/topics/name.md or Memory/decisions/name.md_
_Profile: Memory/Profile/{values,goals,history,personality,health,relationships,finances}.md_
_Core permanent memories: Memory/core-memories.md_

- In ask-me-questions sessions, ask exactly one open-ended question per message
- In ask-me-questions sessions, prioritise business and investment questions first
- Use full file paths in commands when path ambiguity is likely
## 2026-06-17 Reflection
- (Jun 17) SessionEnd hook now runs `memory_flush.py` detached so flush survives terminal close
- (Jun 17) Reflection fix deployed; Codex structured output now writes to `MEMORY.md`
- (Jun 17) Added reflection tests in `test_memory_reflect.py`
- (Jun 17) `wiki_ops.py` supports `stats`, `lint`, and `validate <page>` for the project wiki
- (Jun 17) Memory system upgrade plan saved with 23 tasks; each phase ends with VPS deploy
- (Jun 17) Deploy script stashes and restores local changes during VPS pull

## 2026-06-18 Reflection
- (Jun 18) Built WhatsApp thread reset so 'ask me questions' resets the conversation thread
- (Jun 18) Security hardening deployed to VPS in commit c74f256; added security_audit.log

## 2026-06-22 Reflection
- (Jun 22) Briefs Finance handoff plan file is `briefs-finance-investment-tool.md`
- (Jun 22) Run Briefs Finance from `investments/briefs-finance` in its own `uv` env
