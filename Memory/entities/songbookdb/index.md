---
title: SongbookDB
type: entity
category: project
created: 2026-06-03
updated: 2026-06-21
related: [[hosting-growth]]
tags: [project, software, karaoke, subscription]
---
# SongbookDB

Karaoke DJ songbook platform. ~170 DJs on monthly/yearly subscriptions.
Company: SBDB Software Pty Ltd.
Website: https://www.songbookdb.com

## Goal
Increase revenue. Reduce churn.

## Active Issues

### Onboarding Churn
- DJs find onboarding difficult → high churn
- Exploring AI-assisted onboarding to help DJs learn the software

### SongbookDB Pal Desktop App (Blocked)
- New version triggers virus alerts; browsers block download
- Root cause: missing code signing certificate (e.g. DigiCert — expensive, uncertain fix)
- Result: no bug fixes released for ~2 years
- Impending: Apple Mac will soon block AIR-based desktop apps → need to recode desktop apps
- Built in AS3 + Harman AIR, with some Python for file handling
- (Jun 19) Apple Developer sent revised Program License Agreement; review before macOS/iOS release work

### PHP Backend Upgrade
- See [[php-upgrade]] for full tracking
- Currently on PHP 7.4; target PHP 8.5 one major version at a time

## Repo
`O:\SBDB Software\SongbookDB\www\songbookdb-deep`
Public web root: `public_html/`

## Sub-pages
- [[php-upgrade]] — PHP 7.4 → 8.5 upgrade tracking
