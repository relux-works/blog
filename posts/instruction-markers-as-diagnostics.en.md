---
title: "Instruction Markers as Diagnostics"
description: "A bounded experiment with tagged evaluation copies shows how instruction IDs can support observable diagnostics without entering production prompts or becoming claims of causal provenance."
slug: "instruction-markers-as-diagnostics"
lang: "en"
authors:
  - name: "Alexis Grigoryev"
    title: "CTO / Founding Engineer, Relux Works"
    links:
      - "https://www.linkedin.com/in/alexis-grigoryev-22bab159/"
  - name: "Ivan Oparin"
    title: "CEO / Founding Engineer, Relux Works"
    links:
      - "https://github.com/ivanopcode"
      - "https://www.linkedin.com/in/ivanoparin/"
aiSystems:
  - "OpenAI Codex"
  - "Claude Opus 5"
---

In the first version of this experiment, a model returned an answer and then
separately quoted the spans of that answer it claimed to have derived from specific
instructions. Two of those quoted spans did not exist in the answer. Exact checking
caught both, but the response shape had allowed a claim about text that was never
returned. The second version of the experiment, and the limits on what it can
show, follow from that defect.

The question this article answers is narrow: can temporary markers on a disposable
copy of the instructions make an evaluation easier to inspect, and what does the
resulting evidence support? Our [previous article](https://relux.works/en/blog/semantic-core-instead-of-phrasebooks/)
placed stable taxonomy IDs outside production prompts. That boundary still holds.
The runtime instructions used by a product remain ordinary, untagged text, and
everything described here happens inside evaluation fixtures.

The design is a matched pair. A disposable copy of the instructions receives IDs,
and the model sees those IDs only inside a tagged experimental arm. A matched clean
arm uses the same response envelope without markers or links. The marker and the
envelope can themselves alter behavior, so this pairing is part of the design and
serves as an integral experimental control.

The result is a [bounded diagnostic prototype](https://github.com/relux-works/taxonomy-research/blob/aae4e2af69d9f71de1b19fcf3fbe6591ea0003ea/evals/instruction_diagnostics.md).
It creates inspectable claims between answer segments and supplied instructions. It
does not reveal chain of thought or prove which instruction caused an answer.

## Taxonomy IDs and experimental markers have different jobs

A stable test taxonomy names requirements across revisions. An experimental marker
is an intervention inserted into one frozen evaluation fixture and exposed to the
model. They may share an identifier scheme, but their operational roles differ, and
the rest of this article is about the marker.

The marker method generalizes beyond a word-replacement matrix. Candidate units can
be examples, requirements, prose rules, semantic-core units, safety instructions,
or boundary rules. These are possible units for the method. The study has not tested
every domain in that list.

An LLM may propose semantic units when prose has no convenient headings or bullets.
That proposal still needs review. After review, a script should generate and insert
IDs using pinned source hashes, unique anchors, and a reversible transformation.
Missing or ambiguous anchors should stop the run. The current Caveman study used an
explicit, reviewed, frozen map; it did not prove automatic semantic segmentation.
An LLM is therefore optional during unit selection and unnecessary for each ID.

The study uses [Caveman](https://github.com/JuliusBrussee/caveman) as a concrete
source. The public research repository freezes the evaluated inputs and explains
their provenance without turning either fixture into a production skill.

## What changed from v1 to v2

V1 requested an answer plus separately quoted spans and rule IDs. Its 80 completed
calls emitted 14 claims. Two semantic claims quoted source text that never appeared
in the answer. Exact checking caught the defect, but the response shape allowed it.
Under that shape, nothing stopped a response from citing a span such as
`17 × 19 = 323` (borrowed from the v2 cases for illustration) as derived from a
rule while the returned answer contained no such string. The [v1 report](https://github.com/relux-works/taxonomy-research/blob/aae4e2af69d9f71de1b19fcf3fbe6591ea0003ea/docs/v1-report.md)
therefore treated the result as promising and inconclusive.

V2 made the answer a concatenation of returned segments. Each segment carries its
own links, and an empty link list is legitimate. A link is now structurally attached
to text that actually exists: the segment holding `17 × 19 = 323` either carries a
link or it does not, and there is no separate quote to drift. This makes the
relationship addressable. Its semantic truth still requires a separate judgment.

| Study | Scheduled responses | Design | Observable result |
| --- | ---: | --- | --- |
| V1 | 80 | 1 model, 5 arms, 8 cases, 2 repetitions | 14 emitted claims; quoted spans could be absent from the answer |
| V2 | 120 | 2 pinned models, 5 arms, 6 cases, 2 repetitions | 27 emitted links attached to returned segments |

The five v2 arms were terse control, current-original clean and tagged, and
historical-semantic clean and tagged. This arm set limits what the numbers can
say. The current original and historical candidate are different versions and
contracts. Their differences mix version, wording, granularity, and
instrumentation, so they cannot establish word-matrix versus semantic-core
superiority. Clean and tagged arms also share a segmented envelope, so their
comparison estimates incremental marker and link overhead within that protocol.
Total overhead against an unstructured production answer remains outside this
comparison. The full
[v2 report](https://github.com/relux-works/taxonomy-research/blob/aae4e2af69d9f71de1b19fcf3fbe6591ea0003ea/docs/v2-report.md)
records these limits.

## Three layers of evidence

V2 separates checks that are easy to blur together:

1. Structural checks validate the envelope, known arm-specific IDs, and exact source
   quotes.
2. Answer checks validate declared artifacts, polarity, language, and joining
   invariants independently of link validity.
3. Independent semantic review inspects the segment, full source fragment, and task
   context, preserving compatible, contradicted, and insufficient-evidence labels.

The third layer is a model judgment, and its output is a set of counts rather than
a rate. Across 27 emitted links, an independent MODEL review judged 18 compatible, 7
contradicted, and 2 insufficient. It also identified 17 observable omissions. These
denominators matter. The 18 compatible links are not "18/27 accuracy" or precision.
The 17 omissions are not causal false negatives, and they are unrelated to the
separate total of 17 tagged responses with independently checkable answer or segment
joining violations. The complete negative candidate universe was not independently
labeled, so live precision and recall remain undefined. The frozen
[aggregate](https://github.com/relux-works/taxonomy-research/blob/aae4e2af69d9f71de1b19fcf3fbe6591ea0003ea/artifacts/v2/aggregate.json)
and [independent review](https://github.com/relux-works/taxonomy-research/blob/aae4e2af69d9f71de1b19fcf3fbe6591ea0003ea/artifacts/v2/independent-link-review.json)
preserve those distinctions.

The arithmetic answer `17 × 19 = 323` shows what a compatible label does and does
not mean. One tagged response linked it to a broad rule about preserving exact
technical substance. The independent model review called that relationship
compatible because the required string was preserved. The same review noted that
the match was generic and non-discriminative. Correct arithmetic plus a compatible
broad rule does not show that the source rule influenced the answer. An empty link
list for the same answer was also a valid abstention, which is why the format keeps
abstention legitimate.

## Calibrate the checker against declared facts

False-positive and false-negative controls become meaningful only after declaring
the unit, observable contract, and candidate universe. Useful offline fixtures
include wrong and cross-arm IDs, incorrect quotes, unrelated copied rules,
polarity or language counterexamples, and a corrupted matrix. Nearby positive
controls prevent a checker that rejects everything from winning. Always-positive
and always-empty baselines should fail, and a zero denominator stays undefined.

The v2 report includes a small planted-fixture confusion matrix. Its numbers describe
that declared offline fixture set only. They are not live model rates. This is the
right role for deterministic controls: demonstrate that the measurement rejects a
known violation for the intended reason.

## What the prototype supports

The evidence supports a useful, bounded source-aware output diagnostic. It supports
reversible eval fixtures, structurally attached links, explicit abstention, separate
answer checks, and reviewable disagreement. It does not support claims of causal
provenance, chain-of-thought access, a benchmark win, pure compression superiority,
or global validation. Two models and two repetitions leave substantial uncertainty,
and broad matching can be non-discriminative, as the arithmetic link showed.

The proposed next step is [synthetic robustness work](https://github.com/relux-works/taxonomy-research/blob/aae4e2af69d9f71de1b19fcf3fbe6591ea0003ea/docs/roadmap/synthetic-robustness-proposal.md),
which has not been executed. It would script decidable examples, use review-assisted
semantic proposals, freeze grouped development and holdout splits plus primary
metrics, keep paraphrase families together, and distinguish repeated executions from
independent families. A holdout should not change after its scores are visible. More
rows alone do not remove statistical uncertainty, and the proposal makes no power or
success promise.

## A reproducible diagnostic workflow

1. Freeze source units, task contracts, versions, hashes, and unique anchors.
2. Review any model-assisted semantic-unit proposal.
3. Generate reversible markers deterministically in disposable eval copies.
4. Run matched clean and tagged arms with the same model, case, repetition, envelope,
   and settings.
5. Reconstruct answers from segments, then check IDs, quotes, artifacts, polarity,
   language, and joins as separate layers.
6. Review emitted links and link-free segments independently, preserving abstention
   and insufficient evidence.
7. Publish denominators, costs, confounds, corrections, and the boundary of every
   claim.

The [public repository README](https://github.com/relux-works/taxonomy-research/blob/aae4e2af69d9f71de1b19fcf3fbe6591ea0003ea/README.md)
contains the current offline reproduction commands. Its 48 tests are deterministic
software controls. Counting them as 48 independent experimental confirmations would
be incorrect.

The practical consequence is a rule for reporting. Keep markers in disposable eval
copies, publish every count with its denominator, and treat a compatible link as
evidence that a relationship is inspectable rather than evidence that it is causal.
That modest distinction is the core of the method: make claims easier to inspect
without making them larger than the evidence.
