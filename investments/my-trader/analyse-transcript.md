# Directive: Analyse Transcript

## Purpose

Analyse a single finance YouTube transcript in
`investments/my-trader/transcripts/lesson-extraction/` and surface anything genuinely new
and worth adding to `tool-preplan.md` — fact-checked, bias-assessed, and checked against
what's already been extracted. This directive is for durable, structural lessons (asset
classes, indicators, tickers, portfolio-building material) — not same-day tactical calls.
For daily trading-analyst videos about what to do in the market *today*, see
`analyse-daily-transcript.md` instead; that's a different job with a different output.

This directive is for **analysis only**. It never edits `tool-preplan.md` (or any other
file) on its own — findings are presented in chat, discussed with Shaun, and only added
to `tool-preplan.md` after he says what to keep.

## When to use

Shaun points at a transcript (by path, or asks to analyse "the next one") and asks for it
to be analysed as a strategy/lessons source. If he pastes new transcript content into an
existing file first, treat that as the target.

## Process

1. **Read the target transcript in full** —
   `investments/my-trader/transcripts/lesson-extraction/<file>.md`. Note the title and
   source URL from the top of the file.

2. **Read `tool-preplan.md` in full first.** This is the file everything gets aligned
   to — its Purpose section, Confirmed So Far table, Candidate Universe buckets, Parked
   Research Tasks, "What we know so far", and Deferred Hold/Sell Rules all define what
   counts as relevant. Build a working list of what's already there before touching the
   transcript's content.

3. **Also skim `investment-strategy.md`'s "Lessons" sections.** Three earlier transcripts
   were already vetted there (crash-assets, purchasing-power/inflation, late-cycle
   warning signals). A new transcript covering the same ground should be recognized as
   overlap, not re-extracted as new.

4. **Extract candidate claims from the transcript**: headline stats, the core thesis,
   named tickers/asset classes, and any "here's what to do" recommendations.

5. **Fact-check the headline claims via web search.** For each load-bearing stat or
   claim (inflation/rate figures, index levels, historical comparisons, "X happened for
   the first time since Y" claims, named data releases), search for it and note:
   confirmed / refuted / mixed-or-unclear, plus the source you checked it against.
   Prioritize claims the video's argument actually depends on — not every incidental
   number.

6. **Test the assumptions, not just the stats.** Identify the underlying premises the
   video's argument rests on (e.g. "this pattern always precedes a crash," "the current
   move is unprecedented," "this indicator is reliable on its own"). Search for
   counter-evidence or base rates, not just confirmation — e.g. how often has this
   signal fired before without the predicted outcome following, what do other sources
   say about the same data.

7. **Flag anything framed as "now" / "currently" / "as of [date]" for staleness.**
   Transcripts describe a snapshot at their publish/upload date, which may already be
   behind the current date by the time this is analysed (and drifts further every time
   it's re-read later). For any claim presented as a live/current condition (a rate
   level, an indicator reading, "the Fed is currently...", "X is happening right now"):
   - check whether it's still accurate as of today, not just whether it was accurate
     when the video was made
   - if it's stale or superseded, don't drop the claim — relabel it as a **historical
     data point / example** (what the indicator did that time) rather than an active
     signal, and say plainly that its current relevance is unclear or has changed
   - carry the transcript's own as-of date alongside the claim so this judgment can be
     re-made later without re-watching the source

8. **Assess the source's incentive/bias.** Same as the existing vetted lessons: is
   there a product pitch, paid-signal upsell, affiliate link, or "free video / get rich"
   framing mid-video? Note it explicitly — it doesn't invalidate correct data, but it
   explains why the framing is more alarming than the underlying facts warrant.

9. **Filter against what's already captured.** Drop anything that duplicates:
   - a row already in `tool-preplan.md`'s Confirmed So Far table or Candidate Universe
   - a bullet already in `tool-preplan.md`'s "What we know so far" / Parked Research
   - a lesson already written up in `investment-strategy.md`
   Only surface what's actually new — a new ticker, a new indicator, a new fact-checked
   number that sharpens something already there, or a genuine correction to something
   currently believed.

10. **Present findings in chat**, structured as:
   - **Source**: title, URL, one-line thesis
   - **Bias/incentive check**: what's being sold, if anything
   - **Fact-check results**: claim → verified/refuted/mixed, with what you checked it
     against
   - **Currency check**: any "as of now" claims that are stale as of today — relabeled
     as historical examples with the transcript's as-of date, plus a note on whether
     current relevance is unclear or has changed
   - **Assumptions tested**: what the argument depends on, and what the evidence
     actually supports vs. overstates
   - **New candidates for `tool-preplan.md`**: tickers, indicators, or lessons not
     already there — say exactly where they'd land (Candidate Universe bucket, Parked
     Research Tasks, etc.), marked `NOT DISCUSSED` per that file's convention, never
     pre-filled into the Confirmed So Far table
   - **Already covered — skipped**: brief list of what the transcript repeats that's
     already in `tool-preplan.md` or `investment-strategy.md`, so Shaun can see the
     dedupe worked without re-reading the transcript himself

11. **Stop there.** Wait for Shaun to discuss the findings. Only edit `tool-preplan.md`
    once he confirms what to add, and add it in the same raw/undiscussed form the file
    already uses for unvetted material — don't promote anything to "Confirmed" or
    "DISCUSSED" status from this analysis alone. That status is earned by the
    back-and-forth discussion, not by the fact-check.

## Notes

- This directive only ever targets `tool-preplan.md` as the write destination (once
  Shaun approves changes) — it does not add sections to `investment-strategy.md`. That
  file's existing "Lessons" sections were written before this directive existed; don't
  extend that pattern from here without Shaun saying so.
- Keep the chat presentation scannable — bullets, not prose paragraphs, matching the
  Second Brain's general communication style.
