# Future work

Status as of 2026-06-14: all 5 providers capture complete responses in private/
incognito chats, saved as JSONL + summary. Conductor is serial (one focused
provider at a time). Below is the planned work, roughly prioritized.

## Robustness / correctness
- [ ] **Confirm it works in all cases.** Run repeatedly across sessions/days; verify
      every provider stays at 100% capture. Watch for: provider UI/endpoint changes,
      cookie-consent variations, login/expiry, and selector drift (use **Capture DOM**
      to refix).
- [ ] **Per-provider stream-format regression checks.** A tiny harness that re-runs
      each parser against saved `raw-completions` samples, so a provider format change
      is caught fast.
- [ ] **DeepSeek delete-all durability.** The bearer-token localStorage key and
      `x-app-version` may change between deploys; the UI fallback may also drift.
      Re-record with the recorder if it breaks.
- [ ] **Truncation/echo guards already exist** — keep auditing endings (we caught
      ChatGPT truncation via "odd-end"); consider an automated end-of-run audit.

## Premium accounts
- [ ] **Test with premium accounts** (ChatGPT Plus, Grok premium, Claude Max [have],
      Gemini Advanced, DeepSeek). Goals: remove Grok "Too many requests" free-tier
      limits, confirm model routing/labels, and check whether paid tiers change
      answers vs free.
- [ ] **Dedicated research accounts** with memory/custom-instructions OFF for clean persona runs.

## Scale & parallelism
- [ ] **Scale up** repetitions (within-model variance) and the question set.
- [ ] **Multiple tabs per provider / re-parallelize.** Currently serial because some
      providers abort their stream when backgrounded. Selectively parallelize the
      providers that *don't* abort (Claude/DeepSeek/Grok appear to keep streaming);
      keep ChatGPT/Gemini focused. Possibly multiple tabs per provider for throughput
      (needs a work-claim queue so tabs don't duplicate items).

## The key open research/engineering question
- [ ] **Characterize how focus/visibility affects each provider — including the
      *content*, not just capture.** We know ChatGPT/Gemini abort their request when
      backgrounded. Open questions: does running backgrounded/throttled change the
      *answer itself* (model routing, truncated generation, "lite" responses)? Does
      being on another macOS Space change behavior? Build a controlled test
      (same question, foreground vs background, N reps) per provider and compare
      outputs. This determines how much we can safely parallelize without biasing data.

## Research phase (the actual study)
- [ ] **Persona priming.** Infra is wired (`personas.json` / Personas box; records
      store `personaId` + `promptSent`). Design the persona set (interview-style /
      name-based framings work better than "You are…"), run neutral vs persona, and
      analyze whether/how responses shift. Note validity caveats (in-context priming
      ≠ account-level personalization; effects can be shallow/caricatured).
- [ ] **Analysis tooling.** Scripts to dedup across runs, aggregate by
      provider/question/persona, and score/compare responses.

## Polish
- [ ] **Model-label extraction for all providers** (only Claude is captured now).
- [ ] **Auto-save / streaming export** so long unattended runs persist without manual Export.
- [ ] **Cross-browser**: the build targets Firefox (needs `filterResponseData`). Document that Chrome can't do network capture.
