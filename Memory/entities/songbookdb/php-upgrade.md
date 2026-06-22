---
title: SongbookDB PHP Upgrade
type: topic
parent: [[index]]
created: 2026-06-21
updated: 2026-06-21
tags: [php, upgrade, songbookdb]
---
# PHP Upgrade: 7.4 → 8.5

Strategy: one major version at a time. Current target: **PHP 8.0**.

## Status: In progress — hard breaks fixed, environment set up, testing underway

---

## PHP 8.0 Hard Breaks (must fix before upgrading)

### 1. `money_format()` — removed in PHP 8.0
Replace with `number_format()`.

- [x] `public_html/dashboard/getInvoices/index.php` — was already fixed
- [x] `public_html/account/admin/receipt/index.php` — fixed 2026-06-22
- [x] `public_html/affiliate/receipt/index.php` — was already fixed

### 2. Required params after optional — `lib/logError.php:43`
```php
function logDatabaseError($scriptErrorCode, $mysqli, $stmt, $sql, $params = [], $mode, $logToFile, $emailSupport)
```
`$params = []` is optional but required params follow it. Deprecation warning in PHP 8.0; fatal compile error in PHP 8.1.
- [x] Removed `= []` default from `$params` — fixed 2026-06-22 (all call sites already pass it explicitly)

---

## PHP 8.0 Risks (need testing, not confirmed breaks)

### 3. `facebook/graph-sdk 5.7.0` — declared PHP ^5.4|^7.0 only
Live login paths load this via `public_html/vendor/autoload.php`:
- `mobilePWA/loginFacebookV5.php`
- `mobile/loginFacebookV5.php`
- `mobilePWA/appleSignIn.php`
- `mobile/appleSignIn.php`

mcrypt path in the SDK is **safe** — factory checks `function_exists('random_bytes')` first and never reaches mcrypt on PHP 7+. But broader PHP 8 compatibility is untested. Facebook login must be manually tested after upgrade.

---

## Silent Behavior Changes to Watch

### 4. `0 == "somestring"` → now `false` (was `true` in PHP 7.x)
Loose integer/string comparisons throughout the codebase may silently change behavior. Only catchable via testing.

### 5. `count(null)` → TypeError (was warning in PHP 7.x)
- `public_html/affiliate/reconcile/index.php` — two `count()` calls on DB result variables

---

## Confirmed Clean (not an issue)

| Check | Result |
|---|---|
| `create_function()` | Not found |
| `preg_replace /e` modifier | Not found |
| `get_magic_quotes_*` | Not found |
| `__autoload()` | Not found — uses `spl_autoload_register` |
| `$HTTP_RAW_POST_DATA` | Not found |
| `(real)` cast | Not found |
| `match` keyword conflict in first-party code | Not found |
| PDO in first-party code | Not found — MySQLi throughout |
| `strftime()` in first-party code | Not found |
| `each()` PHP built-in | Not found — vendor only defines own namespaced `each()` |

---

## Dead Code Removed

- `dir/getTokenBU.php` — had `mcrypt_create_iv()`; deleted 2026-06-21
- `facebookV4/` — orphaned legacy FB SDK folder; deleted locally 2026-06-21, **pending production delete**
- `public_html/jwtTest.php` + `public_html/jwtTest/` — 2021 Apple Sign In JWT scratch test; deleted locally 2026-06-21, **pending production delete**

---

## Next Steps

1. ~~Fix `money_format()` in the 3 receipt/invoice files~~ — done
2. ~~Fix `logDatabaseError()` param ordering in `lib/logError.php`~~ — done
3. Delete `facebookV4/` and `jwtTest/` from production
4. Test login, payment, and requests flows on local PHP 8.0
5. Test Facebook login and Apple Sign In on PHP 8.0
6. Fix `count(null)` in `public_html/affiliate/reconcile/index.php`
7. After PHP 8.0 stable → repeat scan for 8.1 → 8.2 → ... → 8.5

---


