# Coverage decay: when style prompts forget themselves

## Stabilising reasoning structure in long LLM outputs

**Author:** Nic Omolabi  
**Format:** Technical article / reproducibility protocol  
**Date:** May 2026

---

## Executive summary

Large language models do not always fail all at once. They often fail gradually.

The first paragraph follows your instructions. The second still resembles the structure you asked for. By the third, the answer begins to loosen. By the fifth, it has become competent, fluent, and generic.

This is not a knowledge problem. The model may know the answer. It may even know your preference. The failure is consistency: the reasoning structure you asked for does not survive the full response.

I call this **coverage decay**.

In this article, **coverage** refers to the presence of structural markers associated with reasoning patterns: causal explanation, edge-case identification, concretisation, decomposition, and operational reasoning. It is a practical proxy for structure persistence, not a direct measurement of reasoning itself.

Coverage decay matters because the most valuable AI outputs are rarely one-paragraph answers. They are reports, technical explanations, design documents, research notes, operational analyses, policy arguments, product plans, and long-form reasoning tasks. These are exactly the places where structure matters most — and exactly where style prompts start to leak.

**Cogito** is a lightweight control loop for reducing that drift. Instead of generating once and hoping the instruction sticks, it runs a simple cycle:

```text
generate -> evaluate -> critique -> refine
```

The goal is not to make the model “think like a human” in any grand philosophical sense. The goal is narrower and more useful: keep the requested reasoning structure present across the whole answer.

This article describes the failure mode, the Cogito mechanism, and a reproducible experiment designed to test whether iterative preference application stabilises reasoning structure better than a system prompt alone.

The central claim is precise rather than grand:

> This article introduces coverage decay as a measurable failure mode in long-form LLM output and presents Cogito as a practical prompting-layer method for reducing it.

The mechanism can be summarised in one line:

> System prompts describe preference. Cogito applies preference. Coverage tracking checks whether the preference survived.

---

## Contributions

This article makes three contributions:

1. It identifies **coverage decay** as a practical failure mode in long-form LLM outputs, where requested reasoning structure appears early but weakens across later paragraphs.
2. It introduces **Cogito**, a prompting-layer control loop designed to reduce that decay through generate -> evaluate -> critique -> refine iteration.
3. It defines a reproducible protocol for measuring **structure persistence** across paragraph positions and comparing Cogito against vanilla and system-prompt baselines.

---

## 1. The problem: long answers drift

Most prompt personalisation feels convincing at first contact.

You tell the model:

> Explain mechanisms before conclusions. Include edge cases. Be concrete. Avoid vague analogies. Show operational implications.

The model responds with a strong opening. It explains the mechanism. It names one or two failure modes. It seems to have understood the instruction.

But longer answers expose a different behaviour. The model often begins in the requested structure and then gradually relaxes back into the default register of fluent generality. The later paragraphs are still useful, but they no longer preserve the specific reasoning pattern requested at the start.

This is the gap between **initial compliance** and **structural persistence**.

A normal system prompt can encode a user preference. It does not, by itself, guarantee that the preference remains active throughout the answer. The problem is not simply whether the model can follow an instruction. The problem is whether it can sustain a structure across a multi-paragraph output.

That is the practical failure mode behind this project.

I built Cogito because I wanted an AI system to respond more like the way I reason: causal, edge-case aware, concrete, operational, decompositional, and willing to examine where an idea breaks. A system prompt could describe that preference. It could not reliably maintain it.

The experiment described later asks a simple question:

> Can we stabilise reasoning structure over long LLM outputs?

---

## 2. What Cogito is

Cogito is a prompting-layer control loop for long-form LLM outputs.

A normal system prompt describes the user’s preferred reasoning style once. Cogito makes that preference explicit, checks whether the generated answer still contains it, critiques the answer when the structure weakens, and asks the model to revise.

It does not require fine-tuning. It does not change model weights. It does not claim to measure reasoning directly. It uses a practical proxy: whether the structural markers of the user’s preferred reasoning patterns persist across the answer.

The mechanism is simple:

```text
1. Generate an initial answer.
2. Measure coverage of preferred reasoning patterns.
3. Critique the answer against the strongest preferences.
4. Refine the answer.
5. Repeat until coverage reaches a threshold or the iteration limit is reached.
```

The important difference is not that Cogito has a better system prompt. The difference is that Cogito does not treat generation as a one-shot event. It turns preference application into a loop.

The working hypothesis is that long-form personalisation needs three things:

1. **Encoding:** represent the user’s preferred reasoning patterns explicitly.
2. **Application:** force the model to revise when those patterns weaken.
3. **Verification:** measure whether the patterns persist across the response.

Most prompt-based personalisation stops at the first step. Cogito adds the second and third.

---

## 3. A concrete example

The example below is illustrative. It shows the behaviour this experiment is designed to test. In the final public version, this section should be replaced or supplemented with a logged output from the smoke test.

### Prompt preference

The user asks for an explanation of why build systems become slow as projects grow. The personalisation instruction says:

```text
Explain mechanisms before conclusions. Include edge cases. Be concrete. Show operational implications.
```

### Standard system-prompt behaviour

The opening paragraph often looks aligned:

> Build systems become slow because dependency graphs expand, cache invalidation becomes harder, and small changes begin triggering large rebuilds. The underlying mechanism is not just “more code”; it is the relationship between dependency resolution, file watching, compilation boundaries, and cache correctness.

That is a strong start. It explains mechanism before conclusion.

But by the later paragraphs, the answer may drift:

> To solve this, teams should improve tooling, review their build process, use caching where appropriate, and keep dependencies manageable. Regular maintenance and good engineering practices can help reduce friction and improve developer productivity.

That second paragraph is not wrong. It is just generic. The edge cases have disappeared. The operational implications are vague. The structure requested by the prompt has not survived.

### Cogito-style behaviour

A Cogito-refined answer should preserve structure deeper into the response:

> The failure mode is usually not that the compiler suddenly became slow. It is that the build graph stopped matching the way developers think changes are isolated. A one-line change in a shared module can invalidate dozens of downstream targets if the boundaries are too coarse. Caching helps only when the cache key is stable and the dependency graph is accurate. It fails when generated files, environment variables, timestamps, or implicit dependencies are not captured. The operational fix is therefore not “add caching” in general. It is to measure invalidation paths, split large targets, remove hidden dependencies, and track which files cause disproportionately large rebuilds.

The difference is not fluency. Both answers are fluent.

The difference is **structure persistence**. The second answer keeps the causal mechanism, edge cases, and operational consequences present across the paragraph instead of letting them fade.

In the baseline, edge-case and operational reasoning collapse into broad advice: improve tooling, use caching, maintain dependencies. In the Cogito-style answer, those patterns remain active: hidden dependencies, unstable cache keys, generated files, timestamps, invalidation paths, and measurement procedures all stay visible.

That is what Cogito is trying to stabilise.

---

## 4. Why this matters

Coverage decay is easy to miss in casual chat, but it becomes costly in long-form work.

If an AI assistant is drafting a technical report, the issue is not whether it can produce a plausible opening. The issue is whether it can maintain the requested structure through the middle and end of the document.

That matters in several real contexts:

- **Technical writing**, where mechanisms and edge cases must remain explicit.
- **Research assistance**, where argument structure matters more than fluency.
- **Operational analysis**, where recommendations need concrete failure modes.
- **Product planning**, where decisions depend on sustained trade-off reasoning.
- **Executive reporting**, where generic summaries hide the details decision-makers need.
- **Learning and tutoring**, where a student benefits from consistent explanatory structure rather than isolated good paragraphs.

The longer the output, the more valuable structure persistence becomes.

For short answers, a system prompt may be enough. For long answers, the model needs a way to check whether the requested structure is still present after generation has begun.

This is why the central question is not merely “can the model follow my style?”

The better question is:

> Can the model maintain the requested reasoning structure from the beginning of an answer to the end?

---

## 5. The mechanism in detail

Cogito represents a user’s reasoning preferences as a weighted cognitive profile.

The reconstructed engine uses ten reasoning-pattern operators:

| Operator | Meaning in this experiment |
|---|---|
| causal | Explain mechanisms, causes, consequences, and why something happens. |
| edge_cases | Name conditions where the answer breaks, fails, or becomes unreliable. |
| concretize | Use specific examples, quantities, scenarios, or implementation details. |
| operationalize | Translate ideas into tests, procedures, measurements, or actions. |
| counterfactual | Explore alternatives, “what if” branches, and changed assumptions. |
| generalize | Extract broader principles from a specific case. |
| analogy | Use comparison or metaphor to clarify a concept. |
| decompose | Break a problem into parts, components, or sub-problems. |
| ethical | Consider harm, fairness, responsibility, or moral trade-offs. |
| historical | Explain how something developed over time or what precedent matters. |

A sample profile might look like this:

```json
{
  "causal": 0.90,
  "edge_cases": 0.85,
  "concretize": 0.75,
  "operationalize": 0.70,
  "counterfactual": 0.60,
  "generalize": 0.65,
  "analogy": 0.20,
  "decompose": 0.75,
  "ethical": 0.35,
  "historical": 0.30
}
```

This profile does not claim to capture cognition in a full psychological sense. It is a practical representation of structural preferences in generated text.

### 5.1 Generation

Cogito first gives the model the full cognitive profile. This ensures that the model has the same preference information as the system-prompt baseline.

### 5.2 Coverage scoring

After the initial answer is generated, Cogito scores it against the profile. The current detector is regex-based. For example, the causal operator looks for lexical markers such as:

```python
r"\b(because|causes?|due to|results? in|leads? to|mechanism|why)\b"
r"\b(underlying|fundamental|root cause)\b"
```

This is intentionally simple and inspectable. It is also limited. It measures style-marker persistence, not reasoning itself.

### 5.3 Critique

If coverage is below the target threshold, the model is asked to critique the answer through the user’s strongest preferences:

```text
Where did causal reasoning weaken?
Which edge cases were named but not analysed?
Which preferred patterns are underrepresented?
```

The critique does not rewrite the answer. It identifies where the answer lost the requested structure.

### 5.4 Refinement

The model then revises the answer using the critique. The revised answer is rescored. If it improves coverage, it becomes the new working answer. If it regresses, the previous answer remains the working answer.

The loop continues until the answer reaches the target threshold or the maximum iteration count is reached.

In short:

```text
system prompt = preference description
Cogito = preference description + critique loop + coverage check
```

---

## 6. The experiment

The experiment tests whether Cogito can stabilise reasoning structure over long outputs more effectively than a system prompt alone.

It compares three conditions:

| Condition | Description |
|---|---|
| A — Vanilla | Claude answers with no personalisation prompt. |
| B — System prompt | Claude receives the full cognitive profile once, but no iteration. |
| C — Cogito | Claude receives the same profile, then runs evaluate -> critique -> refine. |

The critical comparison is B versus C.

Both conditions receive the same preference information. If C performs better, the explanation cannot simply be “the model was given a better description of the user.” The difference is the control loop.

### 6.1 Main question set

The main experiment uses 20 questions across four domains:

- technical explanation;
- philosophical exploration;
- applied problem-solving;
- creative ideation.

The main set deliberately avoids questions about personalisation, prompt decay, reasoning style, or AI preference modelling. This matters because those topics could prime the model toward the language the detector is looking for.

### 6.2 Appendix stress test

A second 10-question stress-test set deliberately includes prompts about personalisation, output drift, and reasoning-style consistency.

This is reported separately. It does not modify the main claim.

The clean set answers:

> Does Cogito help when the prompts do not telegraph the experiment?

The stress-test set answers:

> Does the same effect survive when the prompts are about the target domain itself?

### 6.3 Metrics

The experiment uses two metrics, reported separately.

#### Reasoning-pattern coverage

The regex detector is applied to all three conditions. It reports:

- weighted coverage across the full response;
- coverage by paragraph position;
- per-pattern coverage;
- marker hits per 500 words as a length-aware robustness check.

The paragraph-position breakdown is the most important part. Coverage decay is specifically a claim about structure weakening over the length of the answer.

#### Held-out alignment score

The second metric asks whether the answer resembles the author’s actual writing style.

Three held-out writing samples are used:

1. a physics/consciousness draft;
2. a Recursive Discovery Algorithm specification excerpt;
3. an Eleanor / LNER AI documentation extract.

The outputs are scored by:

- an LLM judge for all outputs;
- the author on a blind subsample.

The two scores are reported separately and never blended into a single false-precision metric.

### 6.4 Pre-registered prediction

Before running the experiment, the prediction is:

> Cogito will score higher than the system-prompt baseline on reasoning-pattern coverage by at least 15 percentage points, with the effect concentrated in paragraphs 3 and later. Alignment-score differences will be smaller, likely 0.3 to 0.5 points on a 5-point scale.

If the data disagrees, the article still gets published. A failed prediction is more informative than an overfitted success story.

---

## 7. What would count as evidence

The strongest positive result would look like this:

1. Vanilla outputs stay low on reasoning-pattern coverage.
2. System-prompt outputs start strong and decay across later paragraphs.
3. Cogito outputs maintain flatter coverage across paragraph positions.
4. Held-out alignment scores improve modestly but consistently.
5. The effect is strongest for patterns that require sustained scaffolding, such as causal reasoning, edge cases, decomposition, and operationalisation.

A weaker but still useful result would be:

- Cogito improves coverage, but mostly by increasing lexical markers rather than improving judged alignment.

That would suggest the loop can optimise the detector, but the detector is not yet good enough.

A negative result would be:

- System prompting performs as well as Cogito, or Cogito improves only the first paragraph and not the later ones.

That would challenge the core hypothesis and suggest that the loop is not adding enough value over ordinary prompting.

The most important rule is that the results section should tell the actual story the data tells.

---

## 8. Results status

The experiment has not yet been run at full scale.

This version of the article therefore does not report numerical results. It reports:

- the failure mode;
- the mechanism;
- the test design;
- the scoring plan;
- the limitations;
- the reproducibility structure.

The results section should be completed only after the smoke test and full generation run are logged.

The intended chart set is:

1. **Coverage by condition and paragraph position** — the core coverage-decay chart.
2. **Per-pattern breakdown** — which reasoning patterns improved most or least.
3. **Held-out alignment scores** — LLM judge and author blind subsample, shown separately.
4. **Clean set versus stress-test comparison** — whether topic priming changes the effect.

Until those charts exist, the article should be treated as a technical protocol and pitchable mechanism, not a completed empirical result.

---

## 9. Limitations

The limitations are real. They do not invalidate the project, but they constrain the claim.

### 9.1 This is not a benchmark

The experiment uses one user profile and a limited question set. It is a personal-tool experiment with quantified evaluation, not a general benchmark for LLM personalisation.

A benchmark would require more users, more profiles, more prompts, external raters, and statistical power analysis.

### 9.2 The detector is a proxy

The regex detector catches lexical markers associated with reasoning patterns. It does not measure reasoning directly.

A response can contain the word “because” without explaining a mechanism. A response can also be causal without using the detector’s marker list. This is why the article describes the metric as reasoning-pattern coverage or style-marker persistence.

### 9.3 The loop can game its own detector

Cogito’s critique step can push the model toward the same lexical markers the detector rewards. A coverage win could therefore partly reflect detector optimisation rather than better reasoning structure.

The held-out alignment score partly compensates for this, because an external judge does not care which regex markers were triggered. But it does not solve the issue completely.

A stronger future version would use a detector trained separately from the generator, ideally on held-out writing samples.

### 9.4 The engine is reconstructed

The current `PreferenceAwareCogito` engine is reconstructed from prior architectural notes, not recovered verbatim from the original October 2025 source file.

That needs to be disclosed. The experiment therefore tests the reconstructed engine as implemented, not a claimed historical original.

### 9.5 This does not compete with fine-tuning

A fine-tuned model or LoRA trained on a user’s writing would likely outperform Cogito on stylistic alignment.

Cogito’s advantage is different:

- no training data required;
- no fine-tuning infrastructure;
- immediate profile changes;
- standard API compatibility;
- interpretable control loop.

It is a lightweight prompting-layer intervention, not a model-layer solution.

---

## 10. Next steps

The immediate next step is the smoke test:

```bash
python scripts/run_experiment.py \
  --profile data/profile.json \
  --questions data/questions_smoke.json \
  --max-iterations 1 \
  --skip-judge \
  --output results/smoke_test/
```

The smoke test should confirm that:

1. all three conditions run successfully;
2. condition B and C receive the same full profile prompt;
3. condition C records iterations and critiques;
4. rejected refinements do not become the working answer;
5. each output logs word count, paragraph count, weighted coverage, paragraph coverage, and marker hits per 500 words;
6. raw outputs are saved even if scoring or judging fails later.

After the smoke test passes, the full generation run should be performed before any judging step. The raw outputs should be inspected first. Only then should the LLM-judge pass be run.

The future work path is clear:

- replace regex detection with embedding-based or classifier-based detection;
- test multiple user profiles;
- add external blind raters;
- run ablations of profile-only, critique-only, scoring-only, and full loop conditions;
- study whether user profiles drift over months of use;
- evaluate whether the effect appears across models, not just Claude.

---

## 11. Appendix: main question set

### Technical explanation

1. Explain how database indexing speeds up queries and when it can make writes slower.
2. Why do distributed systems become harder to reason about as they scale?
3. Explain the difference between caching, queueing, and batching in backend systems.
4. Why do build systems become slow as projects grow, and what can you do about it?
5. Explain how a transformer model uses attention to process context.

### Philosophical exploration

6. Is it possible to know whether you’ve made a free choice?
7. Can a person be responsible for an outcome they did not intend but could have predicted?
8. Is memory part of identity, or only evidence of identity?
9. Does progress usually require forgetting older ways of thinking?
10. Is consistency always a virtue?

### Applied problem-solving

11. Design a small system to detect when a Slack channel has gone quiet but shouldn’t have.
12. Design a process to review a friend’s CV without making them feel judged.
13. Create a lightweight checklist for deciding whether to automate a repetitive workplace task.
14. Propose a workflow for handling customer complaints when the root cause is outside your team’s control.
15. Design a simple incident-review process for a small operations team.

### Creative ideation

16. Generate a concept for a tool that helps amateur cooks adapt recipes when ingredients are missing.
17. Create a sci-fi premise about a city where all public clocks begin disagreeing by different amounts.
18. Imagine a future interface where users can edit their own memories. What goes wrong first?
19. Invent a product for people who want to learn a musical instrument but keep giving up after two weeks.
20. Develop a product idea for the gap between fitness trackers and physiotherapy.

---

## 12. Appendix: stress-test question set

1. How would you design a system to detect output drift in a multi-step AI workflow?
2. Explain why evaluation metrics for LLM personalisation are difficult to design.
3. What does it mean for an AI system to “understand” a user?
4. Can reasoning style be separated from personality?
5. What are the risks of making AI systems too aligned with an individual user’s cognitive preferences?
6. How would you evaluate whether an AI assistant is becoming more useful to a specific user over time?
7. Propose a workflow for reducing generic output in long-form AI-generated documents.
8. Propose a metaphor for prompt decay that would work in a technical blog post.
9. How would you debug a system prompt that works at the start of a response but fails later?
10. Design a feedback loop that lets an AI assistant improve its answer before showing it to the user.

---

## 13. Appendix: methodological credibility note

The question set was iteratively de-contaminated.

Earlier drafts of the experiment included questions about LLM behaviour, personalisation metrics, and reasoning-style consistency — topics that directly named the experiment’s target concepts. That would have primed the model toward style-relevant language and could have inflated the apparent effect.

The main result therefore uses a 20-question set that deliberately avoids those topics. The contaminated questions are not discarded; they are preserved as a separate stress-test set and reported separately.

This distinction matters. The clean set supports the primary claim. The stress-test set explores whether the same effect appears when the prompt topic itself is adjacent to the failure mode.

---

## 14. Appendix: implementation status

The current implementation includes:

- reconstructed `PreferenceAwareCogito` engine;
- canonical ten-operator profile;
- full-profile system prompt shared by conditions B and C;
- regex-based coverage scoring;
- paragraph-position coverage;
- marker-hits-per-500-words robustness logging;
- monotonic refinement acceptance;
- strict profile validation;
- raw JSONL output logging;
- separate generation and judging stages.

The implementation is sufficient for a smoke test and full pilot run. It should not yet be treated as a stable research library.

---

## 15. Closing position

Cogito is not presented here as a solved personalisation system.

It is presented as a practical response to a visible failure mode: long-form LLM outputs often start aligned and then drift.

The value of the project is not that it proves a universal law of model behaviour. It does not. The value is that it turns a vague complaint — “the model stops writing the way I asked” — into a testable mechanism:

```text
Does the requested reasoning structure persist across the full answer?
```

That question is measurable. It is reproducible. It can fail.

That is what makes the project worth testing.
