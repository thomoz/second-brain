# Directive: Analyse Daily Transcript

## Purpose

Analyse a daily trading-analyst video transcript — the kind different analysts post
every day with a same-day read on the market — to help Shaun decide how to move in the
market *today*. This is a different job from `analyse-transcript.md`: that directive
extracts durable, structural lessons for `tool-preplan.md` (asset classes, indicators,
tickers). This one is tactical and ephemeral — a read on today's conditions, tied to
Shaun's actual holdings, that will be stale tomorrow. Don't conflate the two: a daily
video's take on "what to do today" doesn't get added to `tool-preplan.md`.

**Advisor mode applies here same as everywhere** (per `SOUL.md`): this directive never
recommends a trade or drafts an action. It presents what the analyst says, fact-checks
it, and flags what it would mean for Shaun's actual positions if true — the decision is
always his.

## When to use

Shaun points at a transcript in `investments/my-trader/transcripts/daily/` (or pastes
new transcript content into a file there) and asks for a daily/tactical read.

## Process

1. **Read the target transcript in full** —
   `investments/my-trader/transcripts/daily/<file>.md`. Note the analyst/channel name,
   title, source URL, and the video's own stated as-of date (daily content is time
   -sensitive by definition — the as-of date matters more here than for lesson
   transcripts).

2. **Read the actual portfolio.** Pull current holdings from `investment-strategy.md`'s
   "Current Holdings" table and confirmed/candidate positions from `tool-preplan.md`'s
   Confirmed So Far table and Candidate Universe. This is what the analyst's call gets
   checked against — the whole point of this directive is relevance to Shaun's actual
   positions, not a generic market summary.

3. **Extract the analyst's core call(s)**: what they're saying to buy/sell/hold/watch
   today, which indicators or events they're citing as justification, and what timeframe
   is implied (today, this week, "the next few months").

4. **Fact-check the headline claims via web search.** Same standard as
   `analyse-transcript.md` — verify load-bearing stats and claims, note
   confirmed/refuted/mixed with what you checked against. Daily analyst content is
   often noisier and more promotional than the longer strategy videos already vetted —
   don't relax the bar just because it's shorter or more casual.

5. **Assess the source's incentive/bias.** Same pattern as the existing vetted
   transcripts — paid-signal upsells, "free video" pitches, affiliate links. Daily
   analysts have a structural incentive to sound urgent every single day regardless of
   whether anything actually changed — note this explicitly, it's the main distortion
   to watch for in this genre.

6. **Tie the call to Shaun's actual positions.** For each ticker/asset class the
   analyst mentions, check it against the portfolio pulled in step 2:
   - If it matches a current holding or confirmed position, say plainly what the call
     would imply for that specific position if true (e.g. "analyst says gold is
     topping → relevant to PMGOLD specifically").
   - If it matches something in the Candidate Universe (not yet held), note it as
     context for that candidate, not an action.
   - If it doesn't touch anything Shaun holds or is considering, say so — that's a
     useful signal on its own (this call isn't relevant to him today).

7. **Present findings in chat**, structured as:
   - **Source**: analyst/channel, title, URL, as-of date
   - **Core call**: what they're saying to do and why, in one or two lines
   - **Bias/incentive check**: what's being sold, if anything
   - **Fact-check results**: claim → verified/refuted/mixed
   - **Portfolio relevance**: per-holding/candidate breakdown from step 6
   - **Bottom line**: a one-line, non-prescriptive summary of what this means for
     Shaun's specific positions today — never "you should buy/sell X," always framed
     as what the claim implies if it holds up

8. **Append a one-line entry to the daily reads log** —
   `investments/my-trader/transcripts/daily/daily-market-reads.md`. Create the file
   with a header row if it doesn't exist yet. One line per analysis, not a copy of the
   full chat writeup — this log exists so an analyst's calls (or a theme's persistence
   day to day) can be checked for track record later, not to duplicate the discussion.
   Format: `- YYYY-MM-DD | analyst/source | one-line thesis | fact-check: confirmed/
   mixed/refuted | touches: TICKER, TICKER or "none"`

9. **If a daily video surfaces something genuinely durable** (not just today's take,
   but a structural lesson or indicator worth keeping long-term), don't fold it into
   `tool-preplan.md` from here — flag it in chat and suggest running
   `analyse-transcript.md` on it separately. Keep the two directives' outputs distinct.

## Notes

- This directive writes exactly one thing automatically: the one-line log entry in
  step 8. Everything else is chat discussion only, same as `analyse-transcript.md`.
- Never treat a daily call as a reason to act — this directive informs Shaun's own
  judgment, it doesn't produce a recommendation to execute.
- Keep the chat presentation scannable — bullets, not prose paragraphs, matching the
  Second Brain's general communication style.
