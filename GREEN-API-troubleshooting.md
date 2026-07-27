# GREEN-API / WhatsApp Bot Troubleshooting

Lessons learned from a 2026-07-19 outage: the bot went silent for ~11 days (2026-07-08 to
2026-07-19) with no crash, no error, nothing in the logs — just quiet. Root causes turned out
to be layered. This doc exists so the next outage takes less than a full afternoon.

## Architecture (read this first, it's not self-chat)

- **The bot's own identity** is a dedicated prepaid SIM ("Aldi SIM", `+61494727931`), linked to
  a GREEN-API instance via QR scan on a spare Android phone. This is a two-party setup, not
  self-messaging.
- **`WHATSAPP_MY_NUMBER`** in `.env` is Shaun's personal number (`61410868612`) — it's the
  security filter for "who's allowed to message the bot," not the bot's own number. Don't
  confuse the two when debugging.
- The Aldi SIM phone does **not** need to stay powered on — WhatsApp Multi-Device means the
  linked GREEN-API session runs independently of the physical device once properly linked.

## Root causes of the 2026-07-19 outage (there were three, stacked)

1. **VPS `.env` had drifted from local.** `.env` is only `scp`'d to the VPS once during initial
   setup (`scripts/deploy.ps1` never re-syncs it). At some point the VPS ended up pointing at
   `WHATSAPP_INSTANCE_ID=7107660885` — the old Aldi-SIM instance, which had separately died and
   was gone from the GREEN-API console entirely (deleted or expired off the Developer tier).
   **Lesson: when the bot goes silent, verify the VPS's configured instance ID actually matches
   a live instance in the console before doing anything else.**
2. **The console's only visible instance (`7107649252`) was linked to the wrong WhatsApp
   account** (Shaun's personal number, left over from initial Phase 6 testing on 2026-06-15) —
   not the Aldi SIM. Relinking it required logging out the wrong session and re-scanning the QR
   with the correct device.
3. **WhatsApp's `lid` migration.** GREEN-API's release 5.44.36.19 (2026-07-09) added support for
   `@lid` chat identifiers, replacing phone-number JIDs (`@c.us`) as WhatsApp phases them out.
   The bot's security filter only matched on phone number, so once an account's messages started
   using `lid`, they were silently acknowledged and dropped — no error, no log line, nothing.
   Fixed in code (see below). **Separately**, GREEN-API's own `enableLidMode` instance setting
   must be turned on *and the instance must be logged out and re-authenticated with a fresh QR
   scan* — a `setSettings` + reboot alone does **not** fully apply it. This was the step that
   got missed on the first relink attempt and cost the most debugging time.

## Diagnostic playbook

- **Check the running config actually matches a live instance**, before trusting anything else:
  ```
  ssh secondbrain@137.184.102.104
  cd /home/secondbrain/second-brain
  .claude/scripts/.venv/bin/python -c "
  import sys; sys.path.insert(0, '.claude/scripts')
  from config import WHATSAPP_INSTANCE_ID
  print(WHATSAPP_INSTANCE_ID)"
  ```
  Compare against what's actually listed at console.green-api.com/instanceList.

- **Check instance health** (read-only, safe to run anytime):
  - `GET /waInstance{id}/getStateInstance/{token}` → should be `authorized`, not `starting`
    (`starting` = logged out / needs QR rescan, and doesn't self-heal)
  - `GET /waInstance{id}/getWaSettings/{token}` → check `phone`, `chatId`, `historySyncProgress`
    match what's expected

- **Don't trust WhatsApp tick marks as proof the bot saw the message.** A single tick means
  WhatsApp hasn't delivered it anywhere yet. Double ticks mean WhatsApp delivered it to the
  recipient's *device* — that's a different layer from GREEN-API's own relay actually capturing
  it. We saw double ticks for over an hour with zero trace on the GREEN-API side; the fault was
  entirely in GREEN-API's relay, invisible to the tick marks.

- **Use the read-only message journal to inspect real traffic without racing the live bot**:
  ```
  GET /waInstance{id}/lastIncomingMessages/{token}?minutes=10
  ```
  This doesn't dequeue anything (unlike `receiveNotification`, which the bot's own poll loop is
  actively consuming every second — calling that manually risks stealing a message from the bot).

- **Developer-tier accounts cap at 3 chats/month**, and the quota-exceeded signal only fires via
  webhook — which this project deliberately doesn't use (poll-only, no public URL). A
  quota-exceeded chat would be just as silent as everything else in this outage. Wasn't the
  cause this time (only ever 1 chat used), but it's a blind spot worth remembering.

## Relinking an instance to a different WhatsApp account, correctly

1. `GET /waInstance{id}/logout/{token}` — only unlinks that one companion device, doesn't touch
   normal WhatsApp usage on the account being logged out
2. If also toggling `enableLidMode`, set it now: `POST /waInstance{id}/setSettings/{token}`
   `{"enableLidMode": "yes"}`, then reboot — **but the reboot alone is not enough**, continue to
   step 3 regardless
3. Wait ~1-2 minutes
4. Refresh the console page for that instance, click **Get QR**
5. Scan within ~20 seconds (QR rotates) using WhatsApp → Settings → Linked Devices → Link a
   Device on the *correct* physical device
6. Confirm via `getWaSettings`: `phone`, `chatId`, `stateInstance: authorized`

## Code fix (2026-07-19, commit `4e95375`)

`.claude/chat/adapters/whatsapp.py` — the security filter used to only check
`my_number in sender`. It now also resolves the instance's own `lid` (via
`integrations/whatsapp.py:get_own_chat_id()`, called at `connect()`) and accepts a sender
matching either format. This only guards the adapter's own identity check — it does not change
anything about GREEN-API's server-side relay behavior, which was the actual blocker in this
outage.

## Automated detection (added 2026-07-27)

The bot going silent for days with nothing surfacing it (this outage, and the
2026-07-19 one) was the real problem, more than any single root cause.
`.claude/scripts/whatsapp_health.py` now runs on every heartbeat cycle
(every 30 min, regardless of active-hours gating) and scans the bot's own log
for a run of 3+ consecutive `WhatsApp poll error` lines since the last
successfully processed message. On a new degradation it alerts via the
existing WhatsApp/Toast notification channels (deduped so an ongoing outage
alerts once, not every cycle) — ~30min worst-case detection instead of days.

This catches the "poll loop quietly degrades" failure class (the
`receiveNotification` long-poll failing while quick one-shot calls like
`getStateInstance` keep working — the exact pattern diagnosed 2026-07-25/26).
It does **not** catch a total session outage that also breaks outbound
`sendMessage` — that class would still need the tick-marks-aren't-proof
lesson above and a manual check.

## Related

- Setup guide: [`GREEN-API (30 min).txt`](./GREEN-API%20(30%20min).txt)
- Adapter code: `.claude/chat/adapters/whatsapp.py`
- Integration helpers: `.claude/scripts/integrations/whatsapp.py`
- GREEN-API's own lid migration notes:
  https://green-api.com/en/docs/faq/lid-important-differences/
