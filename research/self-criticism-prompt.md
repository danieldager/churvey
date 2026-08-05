# Research prompt: getting LLMs to be genuinely self-critical

Paste into something with live web search. Written 2026-08-05, because this session's
WebSearch budget was already spent (see note at the bottom).

---

I'm designing prompting and workflow rules to make an LLM coding assistant genuinely
self-critical about its own work, and willing to push back on proposals from the user rather
than agreeing with them. I want evidence, not advice.

Find and summarise research from roughly 2023 to now on:

1. Whether an LLM critiquing its own output in the same context actually improves it. I know
   Huang et al. 2023 "Large Language Models Cannot Self-Correct Reasoning Yet" and Li et al.
   2024 "Confidence Matters: Revisiting Intrinsic Self-Correction Capabilities". What has
   replaced or contradicted those since?

2. Self-preference bias when a model evaluates its own generations, starting from Panickssery
   et al. 2024 "LLM Evaluators Recognize and Favor Their Own Generations", and whether a fresh
   context or a different model measurably reduces it. Effect sizes if reported.

3. Sycophancy toward a user's stated position: Sharma et al. 2023 "Towards Understanding
   Sycophancy in Language Models", Xie et al. 2024 "Ask Again, Then Fail", and anything newer.
   Specifically, how much does ordering matter, i.e. does asking for an opinion before the user
   reveals their preference measurably change the answer?

4. Prompt structures with measured effects on critique quality: falsification framing ("what
   would make this wrong") versus evaluation framing, adversarial or devil's-advocate roles,
   pre-mortems, forcing a quota of N distinct concerns, requiring a named test that would settle
   each claim.

5. Whether any of this differs for recent frontier reasoning models, or whether the 2023
   findings still hold.

For each: the claim, the evidence behind it, the effect size, and how strong the study is. Flag
anything that is practitioner folklore rather than measured.

Then, most importantly: give me the strongest evidence *against* the thesis that independence is
the key ingredient, and that same-context self-critique is near-worthless. I want to know if I'm
about to over-correct.

---

## One extra question, added after a session post-mortem

A separate question, because our own failure data does not match the literature's framing.

The two errors that mattered in a long working session were not bad reasoning about the result.
They were false claims about process: "I removed X" when the find-and-replace had silently
matched nothing and the file was unchanged, and "the rendering problem is only local" when only
the local file had ever been tested. Both produced **no diff at all**, which is why they slipped
past review.

So: is there work on detecting when a model asserts it performed an action it did not perform,
as distinct from reasoning errors? What should an automated critique step key on, given that the
highest-risk turns here produced zero or near-zero diff? Anything on verifying tool-use claims
against tool-use logs would be directly useful.

---

## Why this is a prompt and not a finished review

The session's WebSearch budget showed 200 of 200 used on the first call. Cause: `/clear` resets
the context window but not the session, and the search counter is per session. This session
(`5d2c8a04-…`) began 2026-08-04 at 21:19 and its transcript was already 11.4 MB when our
conversation started. Fix: relaunch `claude` rather than `/clear` for a genuinely fresh session,
and/or raise `CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION` in `~/.claude/settings.json`.
