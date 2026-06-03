# Project: SongbookDB

## Goal
Increase revenue. ~170 DJs on monthly/yearly subscriptions. Reduce churn.

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

### PHP Backend
- Currently on PHP 7.4
- Future refactor to current PHP version needed (not urgent)

## Status
Active — desktop app blocker is highest priority technical issue
