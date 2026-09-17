# IBKR Holdings Sync — Setup Guide

First-time walkthrough for connecting `sync-ibkr` to your Interactive Brokers account.
You have never used IB Gateway or TWS before — this assumes zero familiarity. See
`ibkr-sync-handoff.md` for the design background and `.agent/plans/ibkr-holdings-sync.md`
for the implementation plan.

## What this does (and doesn't do)

`sync-ibkr` connects to a locally running IB Gateway process on your own machine and
reads your real account positions — read-only, on-demand only. It never places trades,
never moves money, never runs automatically (no VPS, no schedule). You trigger it
yourself, only when you want to check your tracked holdings against reality.

## 1. Install IB Gateway

- Download IB Gateway (not full TWS — Gateway is the lighter, API-only app) from
  Interactive Brokers: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php
- Install and launch it.
- Log in with your normal IBKR credentials. 2FA happens here, in the Gateway app itself
  — this tool never sees your IBKR password or 2FA code.
- Select **Live Trading** (not Paper Trading) when prompted — this syncs against your
  real account, matching `holdings.md`.

## 2. Enable API access

In IB Gateway:

1. Go to **Configure → Settings → API → Settings**.
2. Check **Enable ActiveX and Socket Clients**.
3. Confirm **Read-Only API** stays checked (it's on by default). This is IBKR's own
   account-level backstop against order placement via the API — a second layer of
   protection underneath this tool's own read-only design, not something you need to
   configure, just don't uncheck it.
4. Set the **Socket port** to **4001** (this is the standard live-trading port for IB
   Gateway; 4002 is paper, and TWS uses different ports again — 4001 is what this tool
   expects).
5. Under **Trusted IPs**, add `127.0.0.1` (or leave the trusted-IP list restricted to
   localhost-only, which is the safer default since nothing outside your own machine
   needs to reach this).
6. Click **OK** / **Apply**.

Leave IB Gateway running and logged in whenever you want to run `sync-ibkr`.

## 3. Run the sync

```powershell
uv run --directory investments/my-trader python -m mytrader.main sync-ibkr
```

This is a dry run — it prints your positions, account summary, and a diff against
`holdings.md`, with zero writes. Once you're happy with what it shows, run it again
with `sync-ibkr --apply` to commit qty/avg-price corrections for tickers you already
track, and add any brand-new position straight into `holdings.md` (bucket
`unassigned` — re-bucket it yourself later whenever you get around to it, same as any
other holding).

## Troubleshooting

**`sync-ibkr` fails to connect** — by far the most common cause is that IB Gateway
isn't open, or it logged itself out. This is normal, not a bug:

- IB Gateway requires periodic re-authentication — daily if auto-restart isn't
  configured, weekly (resets Sundays around 1am ET) if it is.
- Fix: reopen IB Gateway and log back in (2FA happens in the app, same as step 1),
  then re-run `sync-ibkr`.

**Connection refused / timeout** — double-check the socket port in Gateway's API
settings is still `4001` and that "Enable ActiveX and Socket Clients" is still checked
— these settings occasionally get reset by an IB Gateway update.

**A position looks wrong or missing** — `sync-ibkr` only reads what IB Gateway reports
at the moment you run it. If you traded very recently, give the account a minute to
settle before syncing.

## Quick Steps (super simple version)

This is the "just tell me what to click" version, for whenever you forget the details
above.

1. Open **IB Gateway** on your computer.
2. Log in like normal (your usual IBKR login + 2FA).
3. Make sure it says **Live Trading**, not Paper Trading.
4. Leave IB Gateway open — don't close it, just let it sit there running.
5. Open a terminal and type:
   ```
   uv run --directory investments/my-trader python -m mytrader.main sync-ibkr
   ```
6. Press Enter and read what it shows you. This step is just "looking" — it doesn't
   change anything yet.
7. If everything it found looks right, type this instead to actually save it:
   ```
   uv run --directory investments/my-trader python -m mytrader.main sync-ibkr --apply
   ```
   Any position you already track gets its qty/price corrected. Any brand-new
   position gets added straight in too — no extra step needed, it just shows up with
   bucket `unassigned` until you re-bucket it yourself.
8. Wait for it to finish — it'll print "Pulling latest holdings.md/watchlist.md from
   the VPS..." near the end. That's it automatically fetching the update for you, so
   just let it run to completion.
9. Done! Check `holdings.md` — it should now match your real account.

## Why there's a pull step at the end

IB Gateway only runs on your computer, but the real database only lives on the VPS
(a separate computer in the cloud) — so `sync-ibkr --apply` sends what it found to
the VPS over the internet, the VPS updates `holdings.md` there, and step 8 above
pulls that change back down to your computer automatically. You never need to run
`git pull` yourself for this.

If it doesn't work: IB Gateway probably logged itself out. Just reopen it, log back
in, and try again from step 5.
