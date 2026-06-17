# Memory

Active as of: 2026-06-03

## Key Facts
- Five businesses: SongbookDB (SBDB Software Pty Ltd), Billy Goat Karaoke, Dingo's Music Bingo, Thommo's Trivia, Host Masters Entertainment
- Show days: travel to venues to host karaoke/bingo/trivia nights
- Proactivity: Advisor mode — draft for review, never act autonomously

## Venues & Show Schedule
- Billy Goat Karaoke — Boyles Hotel Sutherland — every Thursday at 8pm

## Active Projects
- **Hosting growth** — increase shows + find higher-paying venues; build cash buffer pre-crash
- **SongbookDB** — reduce churn (AI onboarding idea); desktop app blocked by code signing issue; Mac AIR deprecation looming
- **Karaoke Night app** — low priority; ToS concerns; early build with Victor Northhead
- **Creative work** — FiNN TWiST music + Juno: Wonderdog film — on hold until income stable

## Key Decisions
- Second Brain build started 2026-06-03
- Memory vault root: Memory/
- Deployment target: Windows local + VPS (cloud sync)

## 2026-06-16 Reflection
- Second Brain now uses `codex` as the primary backend; Gemini was replaced due to quota limits
- `/commit` now auto-pushes and deploys to VPS via `scripts/deploy.ps1`
- VPS must track the same git branch as local; rerun `deploy.ps1` after any branch switch
- Path handling is anchored to `__file__` to avoid wrong CWD writes from Task Scheduler
