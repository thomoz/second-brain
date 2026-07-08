---
title: SongbookDB PHP Upgrade
type: topic
parent: [[index]]
created: 2026-06-21
updated: 2026-06-23
tags: [php, upgrade, songbookdb, laragon]
---
# PHP Upgrade: 7.4 → 8.5

Strategy: one major version at a time. Current target: **PHP 8.0**.

## Process Rule
**Do NOT auto-apply fixes.** For each folder: read all files, list the next issue found, then wait. Shaun reviews the issue and we work through fixes one at a time together.

**Open files in VS Code.** When discussing a specific file, open it in VS Code with `code <path>` so Shaun can follow along.

**Check production before editing.** When moving to each new file, remind Shaun: "Before we edit this — does your local copy match production? You sometimes tweak files locally without uploading them. If the local version has unrelated local changes, you may want to download the production version first and use that as the base for this PHP 8.0 fix."

**To resume:** Say "Continue the SongbookDB PHP 8.0 upgrade — read the php-upgrade doc first."

## Status (2026-06-26)
Hard breaks fixed. Facebook login confirmed working on production (mobilePWA + mobile). Next: test Apple Sign In locally on PHP 8.0.

---

## Local Environment

- Repo: `O:\SBDB Software\SongbookDB\www\songbookdb-deep`
- Laragon: Apache 2.4.66, MySQL 8.4.3, PHP 8.0.30
- Site: `http://songbookdb.test` or `https://songbookdb.test` — both work now that `www="/"` is used in `js/pwa/js01.js`
- Symlink: `C:\laragon\www\songbookdb` → `O:\SBDB Software\SongbookDB\www\songbookdb-deep\public_html`

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
- `mobilePWA/getToken.php` has hardcoded `'songbookdb.com'` in two `setcookie()` calls (lines ~88 and ~139) — not yet fixed, low priority since login via `login.php` sets the initial cookie correctly

### Do NOT upload these files to production via WinSCP
- `getin/mysqliCon.php` — local DB credentials
- `getin/mysqliCon-mod.php` — local DB credentials
- `public_html/.htaccess` — local IP allowlist + SSL redirects commented out
- `public_html/.htaccess.backup-2026-06-22` — local backup
- `public_html/js/js01.js` — www variable (check before uploading; may still have local URL)
- `base/base.php` — domain detection for local cookies

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

### 5. `fgetcsv()` EOF bug → `strpos(null)` TypeError (was silent in PHP 7.x)
- [x] `public_html/affiliate/reconcile/index.php` — `while(!feof())` loop pushed `false` into `$arrResult`; replaced with `while(($linearr = fgetcsv(...)) !== false)` — fixed and uploaded 2026-06-23
- Note: the two `count()` calls in this file (lines 20/52) are on arrays from `explode()` and `[]` init — not a PHP 8.0 issue

### 6. Undefined `$_FILES` key warning on page load
- [x] `public_html/affiliate/reconcile/index.php` line 15 — added `isset($_FILES['csvfile']['type'])` guard — fixed and uploaded 2026-06-23

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

- `dir/getTokenBU.php` — had `mcrypt_create_iv()`; deleted locally 2026-06-21
- `facebookV4/` — orphaned legacy FB SDK folder; deleted locally 2026-06-21, deleted from production 2026-06-23
- `public_html/jwtTest.php` + `public_html/jwtTest/` — 2021 Apple Sign In JWT scratch test; deleted locally 2026-06-21, deleted from production 2026-06-23

---

## All Fixes (uploaded to production unless noted)

| File | Fix | Commit |
|---|---|---|
| `public_html/account/admin/receipt/index.php` | `money_format()` → `number_format()` | earlier |
| `lib/logError.php` | Removed `= []` default from `$params` | earlier |
| `public_html/account/admin/index.php` | Undefined variables `$results_message`, `$errorMessage` | earlier |
| `funcs_lib/authenticate/djAdmin.php` | Lockout reset bug — DELETE instead of INSERT/UPDATE | earlier |
| `funcs_lib/cryptomania.php` | Key path uses `dirname(__FILE__)` not `DOCUMENT_ROOT` | earlier |
| `mobilePWA/login.php` | Removed dead code `$arr['djData'] = $row` | 41e37ea |
| `mobilePWA/getToken.php` | Null guards, `?? ''` on cookie, `town_city` column fix | 94e5237 |
| `public_html/affiliate/reconcile/index.php` | fgetcsv EOF bug — `while(!feof())` → `while(fgetcsv() !== false)` | bd77314 — uploaded 2026-06-23 |
| `public_html/affiliate/reconcile/index.php` | `isset($_FILES['csvfile']['type'])` guard on line 15 | bd77314 — uploaded 2026-06-23 |
| `mobilePWA/com.php` + 4 others | `antiXSS()` — added `?? ''` null coalescing on `$_POST['r']` and `$_SESSION['wipit']` | bd77314 |
| `public_html/js/pwa/js01.js` | `www="/"` (relative) — fixes session cookie loss when page loaded over HTTP while AJAX called HTTPS origin | bd77314 |
| `mobilePWA/login.php` | `townCity` key mismatch — `checkPublicLoginToken()` returns `town_city`, `logUserIn()` read `townCity`; fixed with `?? $user_details['town_city'] ?? ''` on lines 605 and 666 | bd77314 — uploaded 2026-06-23 |
| `paypal/tipTheDJ/tipTheDJPay3.php` | `$_POST` undefined key guards — added `?? ''` on `$_POST['a']`, `djID`, `venue`, `rigID` | bd77314 — uploaded 2026-06-23 |
| `mobilePWA/loginFacebookV5.php` | CA bundle, SDK shims, curl fallback, token extractor — full PHP 8.0 rework | bd77314 — uploaded + tested 2026-06-23 ✓ |
| `mobile/loginFacebookV5.php` | `$row !== null` null guard in `authenticate_facebook_user()` | bd77314 — uploaded + tested 2026-06-26 ✓ |
| `mobilePWA/appleSignIn.php` | `HTTP_MOBILE` undefined key guard, `$_POST['sub'] ?? ''`, null guard on `$row` | 8fd9f18 — uploaded + tested 2026-06-26 ✓ |
| `mobile/appleSignIn.php` | Same + `isset($postData['user']['name'])` guard in `createNewUser()` | 8fd9f18 — uploaded + tested 2026-06-26 ✓ |
| `public_html/js/pwa/signInWithApple.js` | Add `r: RN` to POST data — `antiXSS()` was always blocking Apple Sign In on PWA | 8fd9f18 — uploaded + tested 2026-06-26 ✓ |
| `dashboard/getMessages.php` | Removed debug file-logging code (debug artifact, not a PHP 8.0 fix) | 3ce21ec |

---

## Folder Audit Log

### `mobile/` — audit COMPLETE 2026-07-03

76 PHP files. All files audited.

**Fixes this session:**

| File | Issue | Commit |
|---|---|---|
| `getTokenAdmin.php` | Unguarded `$result->fetch_assoc()` on venueAdmin query (lines 33-34) | `c186a39` |
| `accountSettings.php` | Unguarded `mysqli_result($t, 0)` — added `if (!$t) return false` | `341d08f` |
| `registerDJ.php` | Same in both branches of `exists()` | `1dc1897` |
| `registerVenue.php` | Same in `exists()` | `5520b8c` |
| `djAdmin/updateAccount.php` | Same in `exists()` + removed debug `$_POST` file logger | `27cd85d` |
| `venueAdmin/updateVenue.php` | Same in `exists()` | `d54b5bf` |
| `registerPublic.php` | `emailExists()` unguarded `$total` + honeypot `?? ''` guards | `2960b53` |
| `searchV2.php` | `$_POST['tags']` unguarded — `?? '[]'` null coalescing | `b7ab5f4` |
| `activateEmail.php` | `err()` inject `$mysqli` param instead of undefined global | `b7ab5f4` |
| `sendLockoutEmail.php`, `sendLockoutVenueEmail.php`, `djAdmin/sendLockoutEmail.php` | `- 9995` typo → `= -9995`; djAdmin version also had active debug file-logger removed | `bd0ab6f` |
| `logout.php`, `logoutAdmin.php`, `djAdmin/logout.php` | `$_SESSION['wipit']` unguarded — added `?? ''` | `bd0ab6f` |
| `updatePushCredentials.php` | `$_POST['subscribeOrUnsubscribe']` and `$_POST['r']` unguarded — added `?? ''` | `bd0ab6f` |
| `djAdmin/activateEmail.php`, `venueAdmin/activateVenueEmail.php` | `err()` inject `$mysqli` param | `bd0ab6f` |

**Files confirmed clean (guarded):** `favAdd.php`, `favNoteAdd.php`, `deleteAccount.php`, `searchDuets.php`, `searchLetter.php`, `searchRequests.php`, `searchKeyword.php`, `searchFavsV3-1.php`, `djSearch.php`, `search.php`, `searchFavs.php`, `poll.php`, `adImageUploader.php`, `deleteAccountPasswordCheck.php`, `noSongHit.php`, `getKioskVenues.php`, `djAdmin/getVenues.php`, `setKioskVenue.php`, `setVenue.php`, `getDJ.php`, `getToken.php`, `searchJustAdded.php`, `gigGuide.php`, `showRot.php`, `checkIfDJHasThisSong.php`, `reqAdd.php`, `login.php`, `loginVenue.php`, `djAdmin/getStats.php`, `registerVenue.php` (line 269 inside else), `reqDel.php`, `venueAdmin/updateAd.php`, `venueAdmin/updateVenue.php` (line 115).

**All files checked.** `venueAdmin/deleteAd.php` confirmed clean.

---

### `mobilePWA/` — audit IN PROGRESS (2026-07-03)

~83 PHP files total. Full scan complete. Working through fixes in order.

**Files skipped (debug-logger-only, live on production):**
`login.php` (user fixed loggers themselves), `convertToFullAccount*.php`, `getMessages.php`, `loginFacebookV5chat.php`

**Fixes applied (commits `5fd87e4`, `5f169e7`):**

| File | Fix |
|---|---|
| `activateEmail.php` | `err()` — inject `$mysqli` as param instead of undefined global |
| `updatePushCredentials.php` | `$_POST['subscribeOrUnsubscribe'] ?? ''` |
| `accountSettings.php` | Honeypot `?? ''`; `$_SESSION['usxerxid'] ?? ''`; `$_SESSION['userEmail_S'] ?? ''`; `if (!$t) return false` in `exists()` |
| `registerPublic.php` | Honeypot `?? ''`; `if (!$total) return false` in `emailExists()` |
| `registerDJ.php` | Honeypot `?? ''`; `if (!$total) return false` in `exists()` |
| `registerVenue.php` | Honeypot `?? ''`; `$_POST['businessName'] ?? ''`; `$_POST['address2'] ?? ''`; email body uses `$firstName` (was wrong `$_POST['djName']`); `if (!$total) return false` in `exists()` |
| `loginVenue.php` | `$_POST['accountType'] ?? ''`; `$venueID` → `$userID` in `checkPublicLoginToken()` ads query (ads were never loading on cookie login) |
| `searchV2.php` | `$_POST['tags'] ?? '[]'` — fixed & committed `e65e70e` 2026-07-08, uploaded to production 2026-07-08 |
| `searchRequests.php` | `$_SESSION['usxerxid'] ?? ''` — fixed & committed `e65e70e` 2026-07-08, uploaded to production 2026-07-08 |
| `favAdd.php` | `$_SESSION['usxerxid'] ?? ''` — fixed & committed `9185317` 2026-07-08, uploaded to production 2026-07-08 |
| `favDel.php` | `$_SESSION['usxerxid'] ?? ''` — fixed & committed `9185317` 2026-07-08, uploaded to production 2026-07-08 |
| `deleteAccount.php` | `$_SESSION['usxerxid'] ?? ''` + replaced undefined-function `back('error', ...)` calls with the file's own ROLLBACK+send() pattern (was a pre-existing fatal-error bug, unrelated to PHP 8) — fixed & committed `1c2d1f0` 2026-07-08, uploaded to production 2026-07-08 |
| `deleteAccountPasswordCheck.php` | `$_SESSION['usxerxid'] ?? ''` + `fetch_assoc()` guard — fixed & committed `9185317` 2026-07-08, uploaded to production 2026-07-08 |
| `adImageUploader.php` | `$_SESSION['userIDAdmin'] ?? ''`; `$linkTo = ''` init; `getimagesize()` false guard — fixed & committed `9185317` 2026-07-08, uploaded to production 2026-07-08 |
| `comUserObjectReload.php` | `$_POST['r'] ?? ''` + `fetch_assoc()` guard — fixed & committed `9185317` 2026-07-08, uploaded to production 2026-07-08 |
| `deleteMessage.php` | `$_POST['messageID'] ?? ''`; `$_SESSION['usxerxid'] ?? ''` — fixed & committed `9185317` 2026-07-08, uploaded to production 2026-07-08 |
| `contact.php` | Honeypot `?? ''`; `$_POST['n']`/`$_POST['e']`/`$_POST['m']` unguarded — fixed & committed `9185317` 2026-07-08, uploaded to production 2026-07-08 |
| `getTokenAdmin.php` (mobilePWA copy — missed in original scan) | `fetch_assoc()` guard + `?? ''` on several `$_SESSION` DJ-account keys — fixed & committed `1c2d1f0` 2026-07-08, uploaded to production 2026-07-08 |
| `reqAddLogoutFix.php` (fixed out of queue order — user asked about it directly) | `$_SESSION['usxerxid'] ?? ''`; `$_SESSION['venueID_S'] ?? ''`; also `$_POST['kiosk'] ?? ''` guard on an earlier unguarded read (not in original scan) — fixed & committed `0c8c1a6` 2026-07-08, uploaded to production 2026-07-08. Note: a second copy exists at `public_html/pwa/reqAddLogoutFix.php`, outside mobilePWA scope, not yet audited |

| `noSongHit.php` | `$_SESSION['venueName_S'] ?? ''`; `$_SESSION['rig_id_S'] ?? ''`; also added `fetch_assoc()` guard on DJ email lookup (not in original scan) — fixed & committed `0745b1b` 2026-07-08, uploaded to production 2026-07-08 |

| `setKioskVenue.php` | `$_POST['venueObj']['rig']` (x2); `$_SESSION['kioskDJID_S']`; `$_POST['rig']` unguarded — fixed & committed `b59ccbe` 2026-07-08, uploaded to production 2026-07-08, tested working |

| `setVenue.php` | `$_SESSION['djID_S']`; `$_POST['rig']`; `$_POST['vName']` unguarded; also `fetch_assoc()` guard on venue lookup (not in original scan) — fixed & committed `aec9034` 2026-07-08, uploaded to production 2026-07-08 |

| `reqAdd.php` | `$_SESSION['usxerxid'] ?? ''`; `$_SESSION['venueID_S'] ?? ''`; also `fetch_assoc()` guard on cookie-relogin lookup (not in original scan). Note: local copy was re-downloaded from production mid-session — had a stray `TO DO` comment block removed that wasn't in our git history, so git was slightly behind production for this file (now caught up) — fixed & committed `aec9034` 2026-07-08, uploaded to production 2026-07-08 |

| `reqDel.php` | `$_SESSION['usxerxid'] ?? ''` (2 places) — fixed & committed `bdf6b03` 2026-07-08, uploaded to production 2026-07-08 |

**Order note (2026-07-08):** staying in `mobilePWA/` root alphabetically before moving into `venueAdmin/` subfolder. Order now: `search.php` → `setUpGuestAccount.php` → `updateMessageStatus.php`, then circle back to `mailOptIn.php` and `venueAdmin/toggleAd.php` + `venueAdmin/contact.php`.

| `search.php` | `$_POST['tags'] ?? '[]'`; `$_SESSION['_actualVenueID'] ?? ''` — fixed locally 2026-07-08, not yet committed/uploaded. (Checked `searchBU.php`: stale unreferenced backup, one 'Charts' case older, not part of scope) |

**Remaining files with fixes needed — next up: `setUpGuestAccount.php`:**

| File | Issue |
|---|---|
| `setUpGuestAccount.php` | `$_POST['editOrSetup'] ?? ''` |
| `updateMessageStatus.php` | `$_POST['messageID'] ?? ''`; `$_SESSION['usxerxid'] ?? ''` |
| `mailOptIn.php` | Remove no-op `$_SESSION['djEmail_S'];` bare statement |
| `venueAdmin/toggleAd.php` | `$_SESSION['userIDAdmin'] ?? ''` |
| `venueAdmin/contact.php` | Same as `contact.php` |

---

### `emailAdmin/` — audited 2026-06-27 ✓
5 PHP files. 2 fixes applied (commit `d5fb618`).

| File | Issue | Fix |
|---|---|---|
| `emailCampaigns_CheckAndProcessEmailQueue_DJs_CronJob.php` | `mysqli_num_rows()` on potentially-false result → TypeError in PHP 8.0 | Added `!$result \|\|` guard |
| `emailCampaigns_PopulateEmailQueue_DJs_CronJob.php` | Undefined `$stmt`/`$params` passed to `logDatabaseError()` in error branch | Replaced with `null` |
| `webhookSendgrid.php` | Clean | — |
| `populate_email_campaign_recipients_with_active_djs.php` | Clean (one-off admin script, TESTING=true intentional) | — |
| `webhookSendgridGetsIndividual.php` | Dev diagnostic tool, not a production endpoint. Has hardcoded Sendgrid API key (pre-existing, not a PHP 8 issue) | — |
| `webhookSendgridBU.php` | Backup file, not in production path | — |

---

## Remaining Folders — PHP 8.0 Audit Not Yet Started

These are entire areas of the codebase that haven't been scanned or tested yet.
Shaun will specify which folders to work through in order.

### Desktop App Backends (3 apps)
- [ ] **To be specified** — 3 desktop apps each have a backend; folders TBD by Shaun

### Mobile Request Hoster
- [ ] **Web app backend** — folder TBD by Shaun
- [ ] **iOS/Android app backend** — folder TBD by Shaun

### Other Root Folders
- [ ] Full audit of remaining repo root folders not yet touched

---

## Next Steps (public_html area — in progress)

1. ~~Fix `money_format()` in receipt/invoice files~~ — done
2. ~~Fix `logDatabaseError()` param ordering in `lib/logError.php`~~ — done
3. ~~Fix fgetcsv EOF bug in `reconcile/index.php`~~ — done 2026-06-23
4. ~~Fix `$_FILES` isset guard in `reconcile/index.php`~~ — done 2026-06-23
5. ~~**Upload `reconcile/index.php`** fixes to production via WinSCP~~ — done 2026-06-23
6. ~~**Delete `facebookV4/` and `jwtTest/`** from production~~ — done 2026-06-23
7. ~~**Test requests flow** at `https://songbookdb.test`~~ — done 2026-06-23 (patron search → request → received in hoster)
8. ~~**Test login and payment flows** locally~~ — done 2026-06-23
9. ~~**Test Facebook login** on local PHP 8.0~~ — mobilePWA + mobile both uploaded and confirmed working in production 2026-06-26 ✓
10. ~~**Test Apple Sign In** on local PHP 8.0~~ — fixed and confirmed working 2026-06-26 ✓
11. Work through remaining folders (see "Remaining Folders" section above) — not started
