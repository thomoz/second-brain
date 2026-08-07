# Gold Outlook — How to Use It

## What it is

A daily read on gold, written to `gold-outlook.md` in this folder. It gives you a
plain-English guess at what gold's price might do **today/tomorrow**, **this week**,
and **this month** — and backs every guess with real historical data, not just
opinion.

## Where to find it

`investments/my-trader/gold-outlook.md`

Open it any time. It's a plain markdown file — readable in Obsidian, VS Code, or any
text editor.

## How it updates

Automatically. Every time Monitor runs (daily, on schedule — no action needed from
you), this file gets overwritten with a fresh read. You never need to run anything
yourself.

If you want to force a fresh recalculation right now (e.g. after a big market move),
run:

```powershell
uv run --directory investments/my-trader python -m mytrader.main monitor
```

## How to read it

Each of the three sections (Today/Tomorrow, This Week, This Month) shows:

- **A lean** — "bullish", "bearish", or "mixed" — based on today's actual signals
- **A confidence label** — how much history backs that lean. Today/Tomorrow is
  always the least confident (shortest track record); This Month is always the
  most confident (longest, deepest track record).
- **A list of notes** — each signal currently active (e.g. "RSI elevated", "real
  yields negative"), with `N=` showing how many historical instances that read is
  based on. Bigger N = more trustworthy. Small N (under ~20) means take it with a
  grain of salt.

## What it is NOT

- **Not a buy/sell instruction.** It never tells you to trade — it's a guided guess
  for your own judgment call, same as everything else this tool produces.
- **Not guaranteed.** Small sample sizes are common, especially for
  Today/Tomorrow. Read it directionally, not as proof.

## One-line summary

Check `gold-outlook.md` whenever you want a gold read — it's always current as of
the last Monitor run, and every number in it is backed by real history, not
invented rationale.
