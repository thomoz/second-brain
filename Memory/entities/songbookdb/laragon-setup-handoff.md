---
title: Laragon Setup Handoff
type: handoff
parent: [[index]]
created: 2026-06-21
updated: 2026-06-22
tags: [laragon, php, setup, handoff]
---
# Laragon Setup Handoff

## How to resume
Say: **"Continue the SongbookDB PHP 8.0 upgrade — read the handoff doc first."**
Then read [[php-upgrade]] for the fix checklist.

---

## Status (2026-06-22)
Laragon environment fully configured. HTTPS working at `https://songbookdb.test`. Login, Favs tested and working locally. PHP 8.0 fixes in progress — see [[php-upgrade]] for full checklist.

---

## Local environment
- Repo: `O:\SBDB Software\SongbookDB\www\songbookdb-deep`
- Laragon: Apache 2.4.66, MySQL 8.4.3, PHP 8.0.30
- Site: `https://songbookdb.test` (HTTPS required — cookies won't work on HTTP)
- Symlink: `C:\laragon\www\songbookdb` → `O:\SBDB Software\SongbookDB\www\songbookdb-deep\public_html`

## Do NOT upload these files to production via WinSCP
- `getin/mysqliCon.php` — local DB credentials
- `getin/mysqliCon-mod.php` — local DB credentials
- `public_html/.htaccess` — local IP allowlist + SSL redirects commented out
- `public_html/.htaccess.backup-2026-06-22` — local backup
- `public_html/js/js01.js` — www variable set to https://songbookdb.test/
- `public_html/js/pwa/js01.js` — www variable set to https://songbookdb.test/
- `base/base.php` — domain detection for local cookies

---

## What's been fixed and uploaded to production

| File | Fix | Commit |
|---|---|---|
| `public_html/account/admin/receipt/index.php` | `money_format()` → `number_format()` | earlier |
| `lib/logError.php` | Removed `= []` default from `$params` | earlier |
| `public_html/account/admin/index.php` | Undefined variables `$results_message`, `$errorMessage` | earlier |
| `funcs_lib/authenticate/djAdmin.php` | Lockout reset bug — DELETE instead of INSERT/UPDATE | earlier |
| `funcs_lib/cryptomania.php` | Key path uses `dirname(__FILE__)` not `DOCUMENT_ROOT` | earlier |
| `mobilePWA/login.php` | Removed dead code `$arr['djData'] = $row` | 41e37ea |
| `mobilePWA/getToken.php` | Null guards, `?? ''` on cookie, `town_city` column fix | 94e5237 |

---

## Next steps (resume here)

1. **Fix `count(null)`** in `public_html/affiliate/reconcile/index.php` — two `count()` calls on DB result variables; PHP 8.0 throws TypeError (was warning in 7.4)
2. **Test requests flow** at `https://songbookdb.test`
3. **Delete `facebookV4/` and `jwtTest/`** from production (already deleted locally 2026-06-21)
4. **Test Facebook login and Apple Sign In** on local PHP 8.0
5. **Test payment flows** locally

---

## Local config notes

### Start Laragon each session
- Open Laragon from Start menu → right-click tray → Start All
- Confirm PHP 8.0.30: tray → PHP → Version
- Site at `https://songbookdb.test` (accept cert warning or install `C:\laragon\etc\ssl\laragon.crt`)

### MySQL local config
- `C:\laragon\bin\mysql\mysql-8.4.3-winx64\my.ini` — `sql_mode=""` (strict mode off for import)
- `C:\laragon\usr\laragon.ini` — `DataDir=O:\laragon\data` (moved from C: due to disk space)

### Cookies / HTTPS
- `base/base.php` detects `songbookdb.test` and sets `$base = ''` (empty domain) so cookies work locally
- Must use `https://` not `http://` — `secure=1` flag on cookies requires HTTPS
- `mobilePWA/getToken.php` still has hardcoded `'songbookdb.com'` in two `setcookie()` calls (lines ~88 and ~139) — not yet fixed, low priority since login via `login.php` sets the initial cookie correctly
