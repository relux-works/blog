---
title: "A Semantic Core Instead of a Phrasebook"
description: "How Pohuy and Caveman replaced prompt repetition with tested semantic invariants, reduced runtime context, and kept the limits of their evidence explicit."
slug: "semantic-core-instead-of-phrasebooks"
lang: "en"
authors:
  - name: "Alexis Grigoryev"
    title: "CTO / Founding Engineer, Relux Works"
    links:
      - "https://www.linkedin.com/in/alexis-grigoryev-22bab159/"
aiSystems:
  - "OpenAI Codex"
---

Style skills for LLMs often begin with a harmless list of examples. Then come a glossary, scenarios, exceptions, and several more examples for every intensity level. Eventually, the model receives tens of kilobytes of text before it ever sees the user's task.

We encountered this in two open-source projects: the Russian profane chat mode [Pohuy](https://github.com/relux-works/pohuy) and the ultra-concise response mode [Caveman](https://github.com/JuliusBrussee/caveman). The scale of the problem differed, but the solution was the same: separate semantic invariants from a collection of ready-made phrases, lock those invariants down with tests, and only then reduce the runtime prompt.

## What Counts as a Semantic Core

A semantic core is not a shorter summary of the old prompt or a new list of "correct" phrases. It is the smallest set of rules that defines behavior independently of the wording of any particular response.

For a style skill, the core usually answers five questions:

1. When is the mode activated and deactivated?
2. Which properties of the response change?
3. Which facts, constraints, and exact literals must never be lost?
4. In which situations must style yield to clarity and safety?
5. Which artifacts must not inherit the conversational style at all?

Examples are useful for calibration, but they are poor contracts. They anchor the model to wording from the example, inflate context, and prove nothing about behavior on new tasks. One or two calibration examples are enough at runtime; complete scenarios belong in an eval suite.

Deterministic command phrase maps form a separate layer. Commands such as `/caveman ultra` and `stop caveman` should be parsed by ordinary code and tested as exact state transitions. They are neither a generative phrasebook nor part of the model's style calibration.

## Pohuy: From a Mandatory Phrasebook to a Compact Contract

The original Pohuy runtime required loading the main `SKILL.md` plus three reference documents: a glossary, a scenario catalog, and an ontology. In the historical snapshot used for the A/B evaluation, this amounted to 42,603 bytes and 477 lines of mandatory instructions.

The compact version reduced the runtime to 2,694 bytes and 57 lines. Instead of a phrasebook, it defines:

- explicit opt-in only, with no activation from incidental profanity or frustration;
- three intensity levels;
- the semantic role of profanity: status, severity, or surprise rather than decoration on a schedule;
- normal professional language for code, documentation, and public artifacts;
- complete, clear prose for safety, data loss, and irreversible actions;
- one calibration example.

Mandatory instructions shrank by 39,909 bytes, or 93.68%. This compares the skill-only runtime bytes, not the full system prompt.

A paired historical run on July 31, 2026 produced these results:

| Metric | Old runtime | Semantic core | Change |
| --- | ---: | ---: | ---: |
| Mandatory instructions | 42,603 B | 2,694 B | -93.68% |
| Prompt-cache creation | 14,625 tokens | 4,059 tokens | -72.25% |
| Model output | 1,334 tokens | 284 tokens | -78.71% |
| Run cost | $0.1146277 | $0.0354977 | -69.03% |
| Blind semantic score | 21.2/25 | 24.2/25 | +3.0 |

Claude Sonnet 5 generated the responses, and `gpt-5.6-sol` performed the blind evaluation. The rubric covered factual accuracy, required actions, tone, severity calibration, and safety. The old response invented a clean Git worktree and permission to push, and it misstated the possible data-loss interval. The compact response received no material factual errors.

These numbers apply only to that preserved historical run. The current repository contains the rubric and scenarios, but it does not yet include a fully reproducible model runner with immutable raw snapshots. The result therefore cannot be generalized automatically to a new model or a future revision of the skill.

## Caveman: A Smaller Problem, the Same Risk

Caveman already had a better structure: it loaded no separate glossaries and used one canonical `SKILL.md`. Even so, the default `full` mode sent 4,670 bytes through SessionStart, approximately 1,168 tokens by the rough `bytes / 4` proxy. The raw skill occupied 6,518 bytes.

Absolute size was not the main problem. The runtime mixed several different concerns in one document:

- semantic prohibitions, such as never dropping `not`, numbers, or exact errors;
- tool-use and language-selection rules;
- a table of six intensity levels;
- two complete sets of technical examples;
- a separate irreversible-operation example;
- repeated wording that the intensity table already expressed.

Existing evals measured response length, but they did not explicitly measure factual accuracy, cross-model stability, or preservation of semantic constraints. A comment in the hook code justified the large prompt as protection against drift after compaction, so deleting examples without a new gate would have been unsafe.

We first extracted the invariants:

- compress form only, never technical content;
- preserve negations, constraints, numbers, units, code, APIs, commands, and exact errors;
- never add words merely to simulate broken speech;
- preserve the user's language and grammatical markers;
- remove tool narration except for warnings and necessary clarification;
- write code, documentation, commits, issues, and other external artifacts in normal language;
- use classical Chinese forms only in `wenyan` modes;
- temporarily suspend the compressed style when it would undermine safety or an unambiguous sequence of actions.

Each invariant then received a stable identifier and a negative mutant test. The runtime byte budget became part of the same contract. This gate does not prove model-output quality, but it prevents a protective rule from being removed accidentally for the sake of an attractive benchmark number.

The implementation and reproducible artifacts are published in [Caveman PR #944](https://github.com/JuliusBrussee/caveman/pull/944).

After compaction, the canonical skill occupies 4,494 bytes instead of 6,518 bytes, a reduction of 31.05%. The real default `full` payload delivered to Claude Code through SessionStart fell from 4,670 to 3,455 bytes, a reduction of 26.02%. The OpenClaw bootstrap fell from 7,241 to 5,217 bytes, a reduction of 27.95%. These are exact UTF-8 byte counts. The `bytes / 4` figures are only rough input-size proxies and are not presented as token counts for a particular model.

A paired evaluation on `claude-haiku-4-5` ran the old and compact skills against identical cases. The deterministic judge marked the compact version as `pass` where the baseline lost the exact spellings `250 ms` and `"ECONNRESET"`. Both versions lost some explicit constraints in a separate case involving `not`, `only`, and `except`; this remains a known limitation rather than a concealed success. Cases requiring human semantic judgment remain `unknown` and are never counted as passes. A single run on one model does not prove equivalence and cannot be generalized automatically to other models.

## Why Mutation Testing Matters

A check that says "the file exists, the JSON is valid, and the current prompt passes" proves very little. A useful contract test must damage the production source and confirm that the checker rejects it.

For Pohuy, we separately tested:

- changing the mandatory reference-load limit from `0` to `1`;
- adding a glossary reference to the runtime;
- exceeding the byte and line budgets;
- removing the explicit opt-in guard;
- creating overlap between positive and negative activation fixtures;
- weakening the safety threshold;
- removing the clear boundary for destructive and data-loss scenarios;
- running the same negative cases under `PYTHONOPTIMIZE=1`, ensuring that Python `assert` removal cannot disable the checks.

For Caveman, the same approach binds every invariant to the production payload and every level filtered by the hook. The real SessionStart output is measured separately rather than inferring runtime size from the source file alone.

## A Practical Process

A reliable sequence looks like this:

1. Capture the exact production payload for every installation and activation path.
2. Separate rules into semantic invariants, calibration examples, and optional references.
3. Move scenarios out of runtime and into eval fixtures.
4. Add negative mutant tests for every critical invariant.
5. Set byte and line budgets.
6. Compact only the canonical source, then regenerate mirrors and archives.
7. Run structural gates, model evals, and an independent blind review.
8. Publish numbers together with the model, date, prompt boundaries, and measurement limitations.

The order matters. Starting with text deletion makes it easy to mistake stylistic similarity for semantic equivalence. Starting with a huge model benchmark can waste money evaluating a contract that has not yet been defined.

## What Is Not Part of the Solution

A semantic core should not depend on a private runtime, a shared agent manager, or the author's internal infrastructure. Such dependencies complicate external review and conflate the product idea with one local installation method.

In Pohuy, we removed the `relux-agents-infra` coupling from setup, documentation, and contract tests. Native installation paths, the product-owned skill, evals, and checks remain. Caveman never added such a dependency. Both optimizations can be discussed and reproduced as standalone techniques for managing LLM context.

## Conclusion

A large phrasebook creates an illusion of control, often purchased through expensive repetition while hiding the absence of a real contract. A semantic core makes behavior explicit: what may change, what must never be lost, and when style must yield.

Pohuy demonstrated the extreme case: a 93.68% runtime reduction accompanied by a better result in one preserved blind A/B evaluation. Caveman demonstrated a more typical case: a moderately large prompt where the main value of optimization came not only from fewer bytes, but from a testable boundary between style and meaning.

The best short prompt is the one with less text and more verifiable guarantees.
