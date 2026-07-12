# Memory Index

_Active items and pointers to structured memory pages. Always loaded into sessions._

---

## Active Items

_Time-sensitive, unresolved, or needs follow-up. Reflection promotes items here; archive to decisions/ when done._

- (Jun 17) VPS: secondbrain@137.184.102.104, dir /home/secondbrain/second-brain

- (Jun 25) Ask Nick to ask her dad for investor introductions
- (Jun 26) Create SongbookDB First Win Onboarding v1 plan around first live request
## Entity Pages

- [[songbookdb/index]] — karaoke song list software, ~170 subscribers, code-signing blocker on desktop app, PHP upgrade in progress
- [[billy-goat-karaoke]] — hosted karaoke, Boyles Hotel Sutherland Thursdays 8pm
- [[dingos-music-bingo]] — hosted music bingo
- [[thommos-trivia]] — hosted trivia nights
- [[host-masters-entertainment]] — umbrella entity for all live entertainment
- [[karaoke-night-app]] — low priority, ToS concerns, early build with Victor Northhead
- [[creative-work]] — FiNN TWiST music + Juno: Wonderdog film, on hold
- [[juno-wonderdog/index]] — animated film project; characters, story, development log sub-pages
- [[simone-kensington/index]] — story project; characters, story, development log sub-pages
- [[venues]] — all show venues and distances
- [[investing/investment-ideas]] — WhatsApp-captured investment ideas inbox (feeds into investments/ tools)
- my-trader notes (portfolio, strategy, transcripts) live at `investments/my-trader/` — outside the vault, not auto-synced by VPS

## Topic Pages

- [[hosting-growth]] — venue sales, show efficiency, ad creation bottleneck

## Decision Archives

- [[2026-Q2]] — Q2 2026 decisions (Apr–Jun 2026)

## Preferences

- Communication: brief bullets, no fluff, no end-of-turn recaps
- Deploy target: Windows local + DigitalOcean VPS (cloud sync via git)
- LLM backend: Codex (ChatGPT flat-rate) via codex_sdk_compat.py
- Never auto-send emails, messages, or social posts

- For SongbookDB upgrade work, make and test changes one by one; avoid bulk uploads or commits
- No em dashes in drafted content
- For SongbookDB PHP upgrade work, read the file, propose the fix, wait for approval, then commit
---

_Resolve `[[name]]` → Memory/entities/name.md or Memory/topics/name.md or Memory/decisions/name.md_
_Profile: Memory/Profile/{values,goals,history,personality,health,relationships,finances}.md_

- In ask-me-questions sessions, ask exactly one open-ended question per message
- In ask-me-questions sessions, prioritise business and investment questions first
- Use full file paths in commands when path ambiguity is likely
- Use `Push-Location`/`Pop-Location`; leaving CWD changed breaks `.claude` hooks
- In ask-me-questions sessions, keep replies short and plain text
