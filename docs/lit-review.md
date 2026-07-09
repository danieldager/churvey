# Literature Review: LLMs, Misinformation, and Evidence Validity — Grounding Principled Question Selection

*Compiled 2026-07-08. Sources fetched and every headline claim adversarially verified (3-vote; 24/25 confirmed, 1 refuted). Scope: academic + preprint + policy/think-tank + journalism + eval benchmarks, 2023 onward. Ideological-lean/political-bias measurement excluded by design; chatbot-accuracy-on-civic-questions precedents included as the core theme.*

---

## 0. Why this review exists

The project harvests LLM responses to the political, policy, and current-events questions ordinary users ask (US first, then France; timed before elections) to measure two things: **(1) the rate of misinformation** in responses, and **(2) the validity/relevance of the evidence** models cite. The harvesting tool exists; what's missing is a *principled way to select the questions*. This review pulls together the prior work that (a) establishes the phenomena we expect to measure and (b) gives us reusable templates for question design and scoring. The payoff is §8 (Synthesis), which converts the findings into a concrete question-selection recipe.

**One-line takeaway:** the literature strongly validates both goals and hands us two directly reusable design templates (AI Democracy Projects' expert rubric; Reuters/FreshQA's basic-fact / fast-changing / false-premise question typology sourced from fact-check databases), while showing that **evidence validity is a distinct capability from answer correctness and must be scored separately** — which is exactly what phase 2 needs.

---

## 1. LLM-generated misinformation in political/news contexts

The most directly relevant, large-scale evidence is the **EBU/BBC 2025 news-integrity study**: 22 public-service media organizations across 18 countries and 14 languages had professional journalists evaluate 3,000+ responses from ChatGPT, Copilot, Gemini, and Perplexity. **45% of answers had at least one significant issue; 20% had major accuracy issues** including hallucinated details and outdated information (sourcing failures covered in §3). Crucially, the distortion was **consistent across languages and territories** — not a quirk of one model or one language. This is the strongest single warrant that our measurement will find a non-trivial misinformation rate, and it ties factual error directly to both attribution failure and knowledge-cutoff failure in *real news QA* (not synthetic benchmarks).

> **Do not cite a "baseline 5–10% false-statement rate."** A plausible-sounding claim that GPT-4/LLaMA-2 produce false statements in 5–10% of general-knowledge responses was **refuted** in verification (0–3) — no reliable single baseline exists. Report measured rates against a described question set, not against an invented baseline.

---

## 2. Hallucination & factual accuracy — benchmarks and rates

- **Frontier models still hallucinate on a large share of short factual questions.** On Meta's **HalluLens / PreciseWikiQA**, GPT-4o hallucinated ~45% of *attempted* answers (~53% correct). Claude-3-sonnet's hallucination rate was ~56% **conditional on not refusing** — but it refused ~57%, so its share of *all* questions hallucinated is ~24%. *(Metric caveat to preserve: conditional-on-attempt rates are not whole-set rates.)*
- **Refusal on non-existent entities is unreliable and varies wildly.** On HalluLens's **NonExistentRefusal** task, false-acceptance (confidently answering about a made-up entity) ranged from ~7% (Llama-3.1-405B) to **42% (GPT-4o)** to **86% (Mistral-7B)**. This is a systematic weakness and a direct argument for including **false-premise** probes (§8).
- **Standard benchmarks to know:** TruthfulQA (~817 questions across 38 domains, designed to elicit *imitative* falsehoods), HaluEval, FActScore (atomic-fact support; human-eval FActScores for LLM-generated biographies ran ~42–71%, i.e. a large share of atomic facts unsupported). These are static and English-centric — useful for method, not for our current-events target.

---

## 3. Evidence & citation validity — the phase-2 core

This is the most important theme for phase 2, and the literature is unambiguous: **citation is a distinct capability that fails often, and answer correctness does not validate the evidence.**

- **Citation support is weak even when responses look authoritative.** Across four generative search engines (Bing Chat, NeevaAI, Perplexity.ai, YouChat), only **51.5% of generated sentences were fully supported by their citations** (citation recall) and only **74.5% of citations actually support the sentence they're attached to** (citation precision — i.e. ~1 in 4 citations doesn't substantiate its claim). Responses were fluent and informative-seeming while frequently containing unsupported statements and inaccurate citations. *(Liu, Zhang & Liang, EMNLP Findings 2023 — foundational, 2023-vintage systems.)*
- **Correctness ≠ faithfulness.** A citation can be factually correct (the cited document entails the claim, per NLI) yet **unfaithful** — "right for the wrong reason" — because the model never causally relied on it. In a RAG study with Cohere's Command-R+, up to **57% of citations were post-rationalized** (the model cited adversarial documents that merely shared a token). *(Wallat et al., "Correctness is not Faithfulness in RAG Attributions," SIGIR/ICTIR 2025.)* Unfaithful-but-correct attributions are the hardest to catch and "foster misguided trust."
- **Sourcing fails at scale in real news QA.** In the EBU study, **31% of responses had serious sourcing problems** — missing, misleading, or incorrect attributions.

**Implication:** phase 2 must score *evidence relevance and genuine support independently of whether the answer is right.* A correct answer with a fabricated, irrelevant, or post-rationalized citation is a distinct — and arguably more insidious — failure mode.

---

## 4. Current events & knowledge cutoff

- **FreshQA / FreshLLMs** is the validated template here: a dynamic benchmark deliberately mixing **fast-changing** knowledge questions with **false-premise** questions. Headline finding: **all models, regardless of size, struggle on both** — making these two categories reliable probes for current-events failure *and* misinformation. *(Vu et al., ACL Findings 2024.)*
- **Answer-only scoring overstates temporal reliability.** On **TDBench**, models often give a correct answer while hallucinating the associated *time reference* — a **21.7% average performance drop** from answer-only to answer-plus-time scoring. We should capture temporal grounding, not just the headline answer.
- **Benchmark aging is real and biases evaluation.** 24–64% of time-sensitive samples in widely-used benchmarks are outdated (Dataset Drift: BoolQ 63.8%, TriviaQA 37.1%, TruthfulQA 36.9%, NaturalQuestions 24.2%), and this actively *penalizes correct up-to-date answers* in up to ~24% of time-sensitive cases. **Consequence for us: ground truth for current-events items must be dated and re-verified at scoring time, not frozen at question-authoring time.**
- **Web-grounding helps but doesn't solve it.** The EBU 45% figure is for current, web-connected assistants. Separately, models frequently *refuse* live-news queries ("I'm unable to directly access…"), so refusal vs. answer behavior on fresh questions is itself worth logging.

---

## 5. How LLMs lead users astray

The mechanism that matters for a study framed around voters: fluent, confident, well-formatted answers that *appear* informative while being unsupported or wrong (documented directly in §3's generative-search study and §1's EBU study). Combined with citation post-rationalization (§3), the user-facing risk is **misplaced trust** — the answer looks sourced and authoritative, so the reader doesn't verify. This is the practical harm our study is positioned to quantify. *(Note: this theme is the least independently benchmarked of the seven; the strongest evidence is indirect, via the fluency-vs-support gap and the harm ratings in §6.)*

---

## 6. Methodological precedents (most important for question selection)

### 6a. AI Democracy Projects (Proof News + IAS, Jan 2024) — the central precedent
An **expert-driven, domain-specific, sociotechnical** evaluation of five frontier models (Claude, Gemini, GPT-4, Llama 2, Mixtral) on real voter/election queries.
- **Raters:** ~40 state/local election officials and AI/election experts (research, civil society, academia, journalism).
- **Rubric — four dimensions:** **bias, accuracy, completeness, harmfulness.**
- **Results:** ~half of ~130 responses rated inaccurate by a majority of expert testers; **40% harmful, 38% incomplete, 13% biased**; GPT-4 least-inaccurate but still wrong ~1 in 5; **no reliable model.** Harm/bias driven by wrong info on voter eligibility, polling locations, ID requirements.
- **Reusable for us:** the 4-dimension rubric and the expert-rater sourcing model. *(Gap: the public materials give dimensions + rater composition but not the full codebook or inter-rater reliability statistics — see Open Questions.)*

### 6b. Reuters Institute — 2024 European elections — the multilingual template
Tested ChatGPT-4o, Gemini, Perplexity.ai with **six questions per country** across **France, Germany, Italy, Spain**:
- **Three basic-information** questions (MEP count, voting dates, what voters decide) + **three debunked-claim (false-premise)** questions.
- **Debunked claims sourced from the EFCSN Elections24Check fact-checking database.**
- **Findings:** errors even on basic facts (GPT-4o gave outdated MEP count 705 vs. 720); **the same model answered correctly in one language and falsely in another** (correct in French/Spanish, wrong in Italian/German). This same-question cross-language divergence is *exactly* the failure mode a US/France study must control for.
- **Caveat:** authors call it "not systematic academic research," and only the debunked items are strictly from Elections24Check.

### 6c. Convergent recipe
FreshQA (§4) + Reuters (§6b) independently converge on the same question typology: **mix basic-fact, fast-changing, and false-premise items, sourced from fact-check databases.** That's the backbone of §8.

---

## 7. Limitations & gaps in the existing literature

- **French/multilingual political QA is thin.** Coverage exists via the Reuters EU study (includes France) and the EBU 14-language study, but **dedicated peer-reviewed French-language political/policy/current-events evaluation is essentially absent.** This is a genuine contribution opportunity for the France arm.
- **Evidence-validity is under-measured relative to answer-correctness.** Most benchmarks score whether the answer is right, not whether the *cited evidence* is real, relevant, and genuinely supporting. Our phase 2 targets exactly this gap.
- **Current-events evaluation is methodologically fragile** (benchmark aging, answer-only scoring) — solvable only with dated, re-verified ground truth.
- **Headline error rates are vintage.** AI Democracy Projects (Jan 2024), generative-search citations (2023), Reuters (June 2024) predate the newest web-grounded models. They establish *phenomena and methods*, not current per-model rates — which is precisely why a fresh 2025–2026 harvest has value.

---

## 8. Synthesis — what this implies for principled question selection

**A. Build questions from fact-checked claim databases, not from scratch.** Follow Reuters/EFCSN: source items (especially false-premise ones) from established fact-checking corpora. US: PolitiFact, FactCheck.org, Washington Post Fact Checker, state election-official FAQs. France: EFCSN/Elections24Check, AFP Factuel, Les Décodeurs, CrossCheck. This gives provenance, a dated ground truth, and defensible selection.

**B. Balance every topic across three difficulty/temporal types** (the FreshQA × Reuters convergence):
  1. **Basic civic/policy facts** — stable, checkable (voter eligibility, how/where to vote, what an office does, current officeholders). *Probes baseline accuracy + the "confident on easy things" assumption.*
  2. **Fast-changing / current-events** — post-cutoff, requires fresh knowledge (latest poll standings, a bill's current status, a candidate's most recent position). *Probes knowledge-cutoff and freshness failure.*
  3. **False-premise / debunked-claim** — embeds a known-false assumption the model should refuse or correct. *Probes the single most reliable model weakness (FreshQA, HalluLens NonExistentRefusal).*

**C. Ask every question in both English and French** (and, where relevant, the same question in both) — the same-question cross-language divergence (Reuters) is a first-class finding to measure, not a nuisance.

**D. Score on a two-track rubric — accuracy AND evidence, independently:**
  - *Track 1 (misinfo, phase 1):* adapt AI Democracy Projects' dimensions — **accuracy, completeness, harmfulness** (drop "bias" per project scope, or keep as factual-slant only). Log refusal separately.
  - *Track 2 (evidence, phase 2):* for each cited source, score **existence** (is it real?), **relevance** (does it address the claim?), and **support** (does it genuinely substantiate it — recall/precision in the Liu et al. sense), and flag likely **post-rationalization**. Never infer evidence quality from answer correctness.

**E. Date and re-verify ground truth at scoring time**, not at authoring time (benchmark-aging finding). For current-events items, record the as-of date and the model's own reported cutoff/grounding behavior.

**F. What makes a good probe:**
  - *For misinformation:* false-premise items and fast-changing items — highest and most reliable failure rates.
  - *For weak evidence:* questions plausible enough that a model will *volunteer citations* (so there's evidence to grade), on topics with a real but non-trivial documentary record — where fabrication and post-rationalization surface.

---

## Open questions the study itself should resolve
1. **Current-model (2025–2026) rates** on political/electoral QA — nearly all headline figures predate newest web-grounded models; the harvest may find materially different rates.
2. **Dedicated French-language political-QA evaluation** — does any peer-reviewed work exist beyond the EU-elections journalistic probes? Appears to be a genuine gap.
3. **The AI Democracy Projects' full codebook + inter-rater reliability** — public materials give the four dimensions and rater composition but not the detailed rubric or agreement statistics; we'd need to reconstruct or improve on these.
4. **An operational, reproducible evidence-validity rubric** for freely-harvested chatbot citations at scale — the correctness-vs-faithfulness distinction is established conceptually but not as a practical scoring protocol.

---

## Sources (primary unless noted)

**Methodological precedents**
- AI Democracy Projects — IAS press release: https://www.ias.edu/news/ai-chatbots-found-inaccurate-answering-voter-queries
- AI Democracy Projects — Proof News: https://www.proofnews.org/seeking-election-information-dont-trust-ai/
- Reuters Institute — 2024 European elections chatbot test: https://reutersinstitute.politics.ox.ac.uk/news/how-ai-chatbots-responded-basic-questions-about-2024-european-elections-right-vote
- Reuters Institute — "I'm unable to": chatbots on the latest news: https://reutersinstitute.politics.ox.ac.uk/im-unable-how-generative-ai-chatbots-respond-when-asked-latest-news

**Misinformation / news integrity**
- EBU/BBC — AI's systemic distortion of news (2025, 22 orgs / 18 countries / 14 languages): https://www.ebu.ch/news/2025/10/ai-s-systemic-distortion-of-news-is-consistent-across-languages-and-territories-international-study-by-public-service-broadcaste

**Hallucination & factual accuracy**
- HalluLens (Meta, 2025): https://arxiv.org/pdf/2504.17550
- Survey on Factuality in LLMs: https://arxiv.org/pdf/2310.07521

**Citation & evidence validity (phase-2 core)**
- Liu, Zhang & Liang — Evaluating Verifiability in Generative Search Engines (EMNLP Findings 2023): https://arxiv.org/pdf/2304.09848
- Wallat et al. — Correctness is not Faithfulness in RAG Attributions (SIGIR/ICTIR 2025): https://staff.fnwi.uva.nl/m.derijke/wp-content/papercite-data/pdf/wallat-2025-correctness.pdf
- Hallucination survey (Artificial Intelligence Review 2025): https://link.springer.com/article/10.1007/s10462-025-11454-w

**Current events & temporal**
- FreshLLMs / FreshQA (ACL Findings 2024): https://arxiv.org/abs/2310.03214
- TDBench (2025): https://arxiv.org/html/2508.02045
- Benchmark aging / Dataset Drift (2025): https://arxiv.org/pdf/2510.07238

**Multilingual / policy perspective**
- FDD — AI-amplified narratives / propaganda in LLM citations (2026): https://www.fdd.org/analysis/2026/03/03/ai-amplified-narratives-measuring-propaganda-in-llm-citations/

*Verification note: 24 of 25 tested claims confirmed 3–0; one refuted (the "5–10% baseline error rate" — do not use). Several headline rates are from 2023–2024-era models and establish phenomena/methods, not current per-model rates. Two metric caveats preserved above: HalluLens rates are conditional on non-refusal; drift/EMR scores are over time-sensitive subsets only.*
