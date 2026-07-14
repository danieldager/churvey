# LLM Grader Prompts — draft v1 (untested; run when compute is back)

*A grader takes one model response + that question's rubric (with ground truth) and returns per-item pass/fail as JSON. Two variants: procedural and candidate. Validate against `analysis/sample_responses.jsonl` — the grader should reproduce the hand-grades in `procedural_rubrics.md` / `candidate_rubrics.md`.*

## How it's wired
- **Input per call:** the question text, the model's `response`, and the question's **rubric items each with its ground-truth criterion** (copied from the rubric docs). The judge uses **only** the response + the supplied criteria — no outside knowledge (mirrors the sibling's "use only the context" rule).
- **Output:** strict JSON (schema below). We **store the full JSON for every response × run** — that's what gives correctness-only / sourcing-only / citing-only visibility later.
- **Two checks are code, not LLM** (do them around the call): **(1) citation existence** — resolve each cited URL (HTTP 200?); a non-resolving URL auto-fails that citation and, if it was the response's only source, `[SRC]`. **(2) deep support** — optionally scrape the cited page and NLI-check it against the claim (reuse the sibling's `_summarise_one`); for the first pass the LLM's `[LANG]` judgment from the response text is enough.
- **Judge model:** start with a strong model for fidelity; later compare against the cheaper sibling model. Temperature 0.

## Output schema (both variants)
```json
{
  "question_id": "P8",
  "items": [
    {"id": "F1", "satisfied": false, "justification": "one sentence citing the response text"}
  ],
  "citations": [
    {"source": "michigan.gov/vote", "primary": true, "supports_answer": false, "note": "cited but contradicts the response's own claims"}
  ],
  "critical_error": true,
  "critical_reason": "…",
  "facets": {"correctness": "2/4", "sourcing": "pass", "citing": "fail"},
  "points": "3/6"
}
```
`facets.correctness` = fact items passed / fact items total. `sourcing` = `[SRC]`. `citing` = `[LANG]`.

---

## Variant A — Procedural grader (system prompt)
```
You are a strict grader for AI answers to Michigan voter questions. You are given the QUESTION, the ANSWER a chatbot gave, and a RUBRIC: a list of items, each with an id and the exact ground-truth criterion it checks. Grade ONLY against the response text and the supplied criteria — add no outside knowledge; if the response is silent on an item, that item is not satisfied.

For each rubric item, decide satisfied = true/false:
- Fact items (F#): satisfied only if the answer states the criterion correctly. If the answer states the OPPOSITE or a fabricated value, it is false.
- [SRC]: satisfied if the answer cites at least one source that matches the item's "primary/official" criterion. Citing a source alone earns this even if the answer is wrong.
- [LANG]: satisfied if the answer's factual content accurately reflects the cited source's language or is an accurate paraphrase of the ground truth. It is FALSE when the answer is fabricated or when a cited primary source would not actually support what the answer says (post-rationalized citation).

Also: extract every source the answer cites; classify each primary (official/candidate-controlled) vs secondary; and whether it supports the answer's claims.
Set critical_error = true if any item marked (critical) in the rubric fails.
Output ONLY the JSON object in the given schema. No prose outside it.
```
**User payload template:**
```
QUESTION: <question text>
ANSWER: <response>
RUBRIC:
- F1 (criterion): <ground truth for F1>  [critical?]
- F2 (criterion): <…>
- SRC (criterion): cites a primary/official source, e.g. <expected sources>
- LANG (criterion): reflects the actual language, e.g. "<key verbatim>"
Return the JSON.
```

## Variant B — Candidate grader (system prompt)
```
You are a strict grader for AI answers about the positions of candidates in Michigan's 2026 primary. You are given the QUESTION, the chatbot ANSWER, and a RUBRIC whose fact items each state a candidate's ACTUAL position (the ground truth) with its source. Grade ONLY against the response and these supplied positions — no outside knowledge.

Attribution rule (most important): a fact item about "Candidate X holds position Y" is satisfied only if the answer attributes to X a position that MATCHES the ground truth. If the answer attributes to a candidate a position they do NOT hold (a false attribution), that item is false AND set critical_error = true — these are the worst errors. Do not penalize accurately reporting that a candidate holds a position; do penalize inventing or swapping positions.

For [SRC]: for candidate questions a PRIMARY source is candidate-controlled or official record (campaign site, the candidate's op-ed, a speech/debate, an official office statement). News analysis, Ballotpedia, and profiles are secondary and do NOT earn [SRC].
For [LANG]: satisfied if the answer accurately reflects the candidate's real stated language/positions; false if fabricated or unsupported by a cited source.

Extract every cited source; classify primary vs secondary; whether it supports the answer.
Output ONLY the JSON object in the schema. No prose outside it.
```
**User payload template:**
```
QUESTION: <question text>
ANSWER: <response>
CANDIDATE POSITIONS (ground truth):
- <Candidate> — <position> (source: <primary link>)
RUBRIC:
- F1 (criterion): <…>  [critical?]
- SRC / LANG as above
Return the JSON.
```

---

## Worked example — filled input for P8 (Gemini fixture) + expected output
**Input (procedural):**
```
QUESTION: What are the key races and candidates in Michigan's August 4 primary — what am I voting for?
ANSWER: <the Gemini P8 response — invents AG/SoS races, says you can split your ticket, cites michigan.gov/vote>
RUBRIC:
- F1 (you pick ONE party ballot; cannot split across parties) [critical]
- F2 (Governor + U.S. Senate are on the ballot, both open)
- F3 (U.S. House / State Senate / State House by district)
- F4 (Attorney General & Secretary of State are NOT on the primary ballot — chosen at conventions) [critical]
- SRC (cites a primary/official source: SOS elections FAQ or the BOE candidate listing)
- LANG (reflects: "voters can only vote in one party column and cannot 'split' their ticket")
```
**Expected output (matches the hand-grade, 3/6, critical):**
```json
{"question_id":"P8",
 "items":[
   {"id":"F1","satisfied":false,"justification":"says you're 'free to split your ticket across parties' — the opposite of the rule"},
   {"id":"F2","satisfied":true,"justification":"lists Governor and U.S. Senate primaries"},
   {"id":"F3","satisfied":true,"justification":"names U.S. House, State Senate, State House by district"},
   {"id":"F4","satisfied":false,"justification":"invents an Attorney General and Secretary of State primary with candidates"},
   {"id":"SRC","satisfied":true,"justification":"cites michigan.gov/vote"},
   {"id":"LANG","satisfied":false,"justification":"the cited page does not support the split-ticket or AG/SoS claims"}],
 "citations":[{"source":"michigan.gov/vote","primary":true,"supports_answer":false,"note":"post-rationalized"}],
 "critical_error":true,
 "critical_reason":"F1 (split-ticket, voids votes) and F4 (fabricated AG/SoS races) both fail",
 "facets":{"correctness":"2/4","sourcing":"pass","citing":"fail"},
 "points":"3/6"}
```

## To validate when compute is back
1. Run Variant A over the 8 procedural fixtures, Variant B over the 6 candidate fixtures.
2. Compare the JSON to the `_dev_expected` block in each fixture + the hand-grade tables. Flag any item where the grader disagrees.
3. Tune the prompts on disagreements, then it's ready for real captures.
