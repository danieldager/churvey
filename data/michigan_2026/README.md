# Michigan August 4, 2026 primary: graded answers

The first churvey case study. Five consumer chatbots (ChatGPT, Claude, Gemini, Grok, DeepSeek),
asked 14 questions about the Michigan primary through their own web apps, in a fresh
private/temporary chat per question, five times each: **350 graded answers**, 70 per chatbot.
Captured 2026-07-10 to 2026-07-14 with the `ff/` extension; graded 2026-07-14.

- `grades.csv`: one row per graded answer.
- `questions.md`: the 14 questions (verbatim), their checklists, and the official source for
  each check, plus the dropped voter-ID question.
- `../../docs/figures/figdata.json`: the aggregates used by the charts, derived from `grades.csv`.
- Ground truth: `../../docs/michigan_answer_key.html` (verbatim official quotes, as of
  2026-07-08) and the dated page snapshots in `../../source_cache/`.

## Columns of `grades.csv`

| column | meaning |
|---|---|
| `question_id` | P1..P7 logistics (dates, registration, early voting, counting, ballot); C1..C7 candidate positions |
| `section` | `logistics` or `candidates` |
| `question` | the exact text sent (no persona, no preamble) |
| `model` | the consumer app: ChatGPT, Claude, Gemini, Grok, DeepSeek |
| `model_label` | the model name the app exposed in its stream, when it did (only Claude: `claude-sonnet-5`) |
| `rep` | 1..5, repetitions of the same question in capture order |
| `capture_date` | UTC date the question was asked |
| `checks_total` | checks in that question's checklist (4-8) |
| `checks_correct`, `checks_partial`, `checks_missing`, `checks_wrong` | the grader's verdict counts |
| `score` | mean over checks, correct = 1, partial = 0.5, missing or wrong = 0 |
| `false_claim` | 1 if at least one factual check was graded **wrong** (the SRC and LANG checks are excluded) |
| `critical` | 1 if a critical check failed (e.g. wrong building or date), set deterministically from the checklist |
| `critical_reason` | the grader's one-line reason, when `critical` = 1 |
| `citations` | number of sources the answer cited (as extracted for grading) |
| `answer_words` | whitespace-separated words in `answer_text` |
| `answer_text` | the answer as captured from the app's network stream, markup cleaned |

Accuracy for a chatbot = mean `score` over its 70 rows. It rewards completeness: an answer that
declines ("not in my search results") scores low without saying anything false. Read accuracy
together with `false_claim`, which counts answers that asserted at least one false fact.

## Headline (recomputes from this file)

| chatbot | accuracy | logistics | candidates | answers with a false claim | critical | mean words | mean citations |
|---|---|---|---|---|---|---|---|
| Grok | 94% | 95% | 93% | 3 / 70 | 2 | 419 | 29.0 |
| Gemini* | 81% | 90% | 71% | 3 / 70 | 2 | 317 | 4.1 |
| ChatGPT | 80% | 85% | 74% | 1 / 70 | 1 | 316 | 19.9 |
| Claude | 75% | 84% | 66% | 8 / 70 | 5 | 324 | 10.1 |
| DeepSeek | 53% | 82% | 23% | 6 / 70 | 0 | 276 | 6.8 |

\* not comparable, see caveat 1.

## Caveats

1. **Gemini's answers are contaminated.** A driver bug meant Gemini never started a new chat:
   all its answers came from one growing conversation, so each question saw the earlier
   questions and Gemini's own answers (the others got fresh chats). The clearest symptom is the
   dropped voter-ID question, where Gemini alone "knew" the state was Michigan. Its score is
   inflated and not comparable. The driver was fixed afterwards (build 2026-07-14-b); Gemini
   has not been re-run.
2. **One grading pass.** Every answer was graded once, by one LLM judge: DeepSeek-V4-Flash
   (via DeepInfra, reasoning effort high, temperature 0), on 2026-07-14, in two batches with
   the same configuration. Before the run the judge agreed with hand grades on 74 of 75 checks
   and 14 of 14 critical flags on 14 synthetic test answers; there is no human re-grade of the
   350 real answers. Earlier re-grades moved the means by at most 1.7 points but moved the
   false-claim counts more (DeepSeek 2 to 6): treat the counts, which are 1 to 8 events per
   chatbot, as indicative.
3. **5 of 10 planned repetitions.** The design called for 10; 5 were run.
4. **Accounts.** Answers came from real logged-in accounts; subscription tiers were not
   controlled across providers.
5. **Question wording.** The voter-ID question named no state and was dropped (15 questions
   were asked, 14 are scored). C1 also names no state ("the August 4 ballot"); on it ChatGPT
   twice asked which state was meant or answered about another state, which the Michigan
   checklist scores as 0.
6. **Word counts** are of the cleaned text. Grok's raw stream carries rendering markup that
   inflates naive counts; Grok writes about 1.3 times as many words as ChatGPT.
7. Ground truth is fixed as of 2026-07-08. Candidate facts (C questions) come mostly from
   candidates' own sites and statements, with news reports where no first-party record exists.
