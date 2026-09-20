---
title: "A Semantic Core Instead of a Phrasebook"
description: "What a rejected Caveman prompt rewrite taught us about keeping stable test taxonomy outside runtime context, annotating cases at evaluation time, and validating evidence before reporting it."
slug: "semantic-core-instead-of-phrasebooks"
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

The maintainer of Caveman
[closed our pull request with a precise objection](https://github.com/JuliusBrussee/caveman/pull/944#issuecomment-5510147754):
the skill body is the product, the rewrite needed the maintainer's own eval loop,
and identifiers such as `CAV-SEM-07` in runtime headings would reach the model in
every session as pure overhead. The original
[Caveman PR #944](https://github.com/JuliusBrussee/caveman/pull/944) had combined a
31% rewrite of the runtime skill with a semantic contract, model runs, reports,
generated mirrors, and raw snapshots. That review was correct. Stable IDs were
useful, and we had put them on the wrong side of the interface.

The mistake has a general shape. Style skills for language models have two
different audiences. The model needs a small set of behavioral rules on every
invocation. Engineers need identifiers, coverage matrices, fixtures, reports, and
historical comparisons. Mixing those audiences makes the runtime prompt pay for the
test system.

This article answers one question: where should the stable identifiers of a test
taxonomy live so that reports can use them while the runtime prompt never carries
them? It covers the three small Caveman follow-ups that replaced #944 and one
runtime-side example from Pohuy. It does not evaluate model behavior under any of
these skills.

An earlier version of this article described the candidate reductions from #944
as a delivered Caveman result. They were measurements of an unmerged branch. This
revision corrects the record and documents the smaller design that followed.

## Runtime rules and evaluation metadata are different planes

A semantic core defines behavior that the model must apply:

- compress form while preserving technical substance;
- preserve negation, limits, numbers, units, code, identifiers, APIs, commands,
  and quoted errors;
- retain the user's language and grammatical role markers;
- keep public and persisted artifacts in normal prose;
- suspend the compressed style when safety or an ordered recovery procedure
  requires full clarity.

These rules belong in runtime context because they can affect the answer.

Evaluation metadata serves a different purpose. A stable identifier lets a report
track one invariant across renamed cases, reordered fixtures, and skill revisions.
It supports joins, coverage matrices, trends, and failure clustering. The model
does not need to see the identifier to follow the rule.

The practical boundary is simple:

| Concern | Source form | Enters runtime prompt? |
| --- | --- | --- |
| Behavioral rule | Clear natural language | Yes |
| Calibration example | Minimal representative example | Sometimes |
| Stable contract ID | Eval taxonomy entry | No |
| Case-to-invariant mapping | Readable taxonomy keys | No |
| Coverage matrix and report | Generated eval output | No |

## Assign IDs when an evaluation starts

The rest of the Caveman example follows one invariant, exact preservation, from
its taxonomy entry through a source case to an annotated report row. The focused
replacement in
[Caveman PR #1061](https://github.com/JuliusBrussee/caveman/pull/1061)
keeps the stable ID in an eval-only taxonomy. Within this design the taxonomy
entry is the only place where `CAV-SEM-02` is written by hand; cases and the
runtime skill are checked for its absence:

```json
{
  "id": "CAV-SEM-02",
  "key": "exact-preservation",
  "description": "Preserve polarity, limits, numbers, units, code, identifiers, APIs, commands, and quoted errors."
}
```

A source case refers to that invariant by its readable key and never by its ID, so
a fixture can be reviewed without a lookup table:

```json
{
  "id": "polarity-and-limits",
  "taxonomy": ["exact-preservation"],
  "prompt": "Restate this retry policy without changing meaning: Do not retry more than 3 times. Retry only after 250 ms, except for HTTP 429."
}
```

When a run or report is prepared, an annotation step resolves the key. The
expected output is the same case with one added field:

```json
{
  "id": "polarity-and-limits",
  "taxonomy": ["exact-preservation"],
  "contract_ids": ["CAV-SEM-02"],
  "prompt": "Restate this retry policy without changing meaning: Do not retry more than 3 times. Retry only after 250 ms, except for HTTP 429."
}
```

The only thing that changed between the second and third sample is
`contract_ids`, and it appeared at evaluation time. This gives reports stable
machine identifiers while the runtime `SKILL.md` contains none of them. The test
suite checks that boundary directly.

The edge cases are where the resolver earns its place. It fails on duplicate
taxonomy IDs, duplicate case IDs, unknown keys, repeated keys, malformed entries,
and source cases that embed contract IDs. These checks matter because a misspelled
key should stop a run. Silently dropping the mapping would produce a clean report
with a hidden coverage hole.

Numbering requirements adds little by itself. The taxonomy becomes useful when
cases can map to several invariants and engineers can inspect the resulting matrix.
A Portuguese migration prompt can cover both `language-and-grammar` and
`exact-preservation`. A public security PR description can cover
`artifact-boundary` and `safety-clarity`. Looking at cases only gives a list of
prompts. Looking at the case-to-invariant matrix reveals which properties have
positive controls, negative controls, overlapping coverage, or no evidence.
Stable IDs make comparisons durable across revisions. Readable keys keep fixtures
reviewable. The annotation step connects the two representations at the point
where the extra metadata becomes useful.

## Complete evidence before attractive metrics

Taxonomy integrity does not prove that a run is complete. The original #944 review
also found that partial evidence could pass a structural gate. We separated that
problem into
[Caveman PR #1062](https://github.com/JuliusBrussee/caveman/pull/1062).

The validator runs before the existing token report and requires:

- snapshot metadata and a non-empty prompt list;
- both comparison controls;
- at least one skill arm;
- exactly one output per prompt in every arm;
- raw string outputs;
- an `n_prompts` value equal to the actual prompt count.

The evidence for this validator is a set of tests, and the tests are what make the
gate believable. They include the committed snapshot as a positive control, then
remove a control, truncate an arm, replace a raw output with an object, change
`n_prompts`, remove every skill arm, and corrupt the JSON. A checker is useful only
after a known violation demonstrates that it can fail for the intended reason.

## Isolate the generator from the operator

Even a complete matrix can measure the wrong thing when the runner inherits local
agent customization. The old Claude invocation inherited user and project settings
plus MCP configuration. Two engineers could run the same checked-in fixtures and
silently give the model different instructions or tools.

[Caveman PR #1063](https://github.com/JuliusBrussee/caveman/pull/1063)
adds `--setting-sources ""` and `--strict-mcp-config`, following an isolation
pattern already used by `caveman-compress`. Unit tests verify the exact user prompt,
system prompt, model, and isolation arguments without calling a model.

Taxonomy, matrix validation, and runner isolation are separate contracts. Each can
be reviewed and merged independently. This is why the replacement is three small
PRs instead of another combined harness and prompt rewrite.

## Pohuy shows the runtime side of the boundary

Pohuy is a separate sample rather than a continuation of the Caveman example,
because it shows what stays on the runtime side once the metadata has moved out.
The same separation applies to phrasebooks. The open
[Pohuy PR #21](https://github.com/smixs/pohuy/pull/21) proposes a 2,694-byte,
57-line runtime skill with zero mandatory reference loads. It keeps explicit
activation, three intensity levels, tone semantics, artifact boundaries, and clear
safety behavior. Glossaries and scenario collections remain optional material.

Those are exact file and contract measurements, not a universal token or quality
claim. The PR's deterministic harness mutation-tests the byte and line budgets,
activation boundaries, default level, reference loading, eval schema, and safety
thresholds. Model behavior still requires separate evaluation.

## What the current evidence supports

The three Caveman follow-ups are open contributions as of this revision. They prove
that the proposed taxonomy mapping, fail-closed matrix validation, and isolated
command construction execute under their tests. They do not prove semantic
equivalence across models. They do not establish that the rejected runtime rewrite
should be merged. They make no claim about token savings from the identifiers
themselves.

The narrow claim is stronger because it is testable: traceability metadata can be
added during evaluation, used in reports, and mechanically excluded from the
runtime prompt.

## A practical sequence

1. Write behavioral invariants in plain language.
2. Keep only rules that affect model behavior in runtime context.
3. Give each invariant a stable ID and readable key in an eval-only manifest.
4. Label cases with readable keys.
5. Resolve stable IDs when preparing a run or report.
6. Reject unknown keys, duplicates, malformed cases, and incomplete evidence.
7. Isolate model runners from user settings, project settings, and inherited tools.
8. Mutation-test every gate with a known violation.
9. Report model, inputs, repetitions, controls, limitations, and unresolved cases.

Prompt optimization and evaluation design share one engineering principle: put
information at the boundary where it is consumed. Behavioral instructions belong
with the model. Taxonomy and traceability belong with the test system. The
decision that follows is concrete: a contract ID found in a runtime file is a leak
from the test system, and the fix is moving it into the eval manifest. Keeping
that boundary explicit saves context and produces evidence that is easier to trust.
