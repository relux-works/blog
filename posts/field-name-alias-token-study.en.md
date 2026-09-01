---
title: "Do Short Field Names Actually Save Agent Tokens?"
description: "A reproducible study of field-name aliases in agent-facing CLI output: raw token counts, comprehension, session economics, and why schema-once formats make abbreviations mostly redundant."
slug: "field-name-alias-token-study"
lang: "en"
authors:
  - name: "Alexis Grigoryev"
    title: "CTO / Founding Engineer, Relux Works"
    links:
      - "https://www.linkedin.com/in/alexis-grigoryev-22bab159/"
aiSystems:
  - "Claude Opus 4.6"
  - "OpenAI Codex"
---

Agent-facing tools should return only the data an agent needs, in a form that consumes as little context as practical. Once a CLI supports field projection, batching, and compact tabular output, another optimization looks tempting: abbreviate field names.

Replace `status` with `s`, `assignee` with `a`, and `description` with `d`. The strings become shorter, so the output should use fewer tokens.

We tested that idea in [agentquery](https://github.com/relux-works/skill-agent-facing-api), our Go library and design pattern for agent-facing CLI query layers. The result was a no-go. In a schema-once format, aliases saved a fixed five tokens per eligible response. Teaching the alias dictionary cost 85 tokens. Under the compact-session scenarios we modeled, aliases produced a net loss 75% of the time.

The more useful finding was structural: once field names appear only once, shortening them has almost nothing left to optimize.

## The Optimization Stack Before Aliases

A token-efficient query layer already has four stronger tools:

1. **Field projection** returns only requested fields.
2. **Compact tabular output** declares a schema once, then emits value rows without repeated keys.
3. **Batching** combines several lookups into one tool call.
4. **Presets** give common field bundles short, meaningful names.

Aliases target repeated field names. Compact output has already removed that repetition.

Consider this JSON:

```json
[
  {"id":"T-1","status":"done","assignee":"alice"},
  {"id":"T-2","status":"blocked","assignee":"bob"}
]
```

Every object repeats the keys. A compact schema-once representation writes them once:

```text
id,status,assignee
T-1,done,alice
T-2,blocked,bob
```

Aliases can shorten only that one header:

```text
i,s,a
T-1,done,alice
T-2,blocked,bob
```

The data rows, which dominate larger payloads, remain identical.

## Study 1: Raw Token Savings

We generated synthetic task-tracker payloads at four scales: 5, 20, 100, and 500 items. Every item had eight fields: `id`, `name`, `status`, `assignee`, `description`, `priority`, `created`, and `updated`.

Each dataset was rendered in three forms:

- pretty-printed JSON;
- compact CSV-style output with full field names;
- the same compact output with one-character aliases.

The generator used a fixed random seed of 42. Counts were measured with OpenAI's `cl100k_base` encoding through `tiktoken`. These are tokenizer-specific measurements, not universal counts for every model provider. The [generator, payloads, and measurement script](https://github.com/relux-works/skill-agent-facing-api/tree/main/.research/synthetic-payloads) are public.

### Raw counts

| Items | JSON | Compact, full names | Compact, aliases |
| ---: | ---: | ---: | ---: |
| 5 | 485 | 269 | 264 |
| 20 | 1,957 | 1,055 | 1,050 |
| 100 | 9,836 | 5,283 | 5,278 |
| 500 | 48,933 | 26,144 | 26,139 |

### Marginal savings

| Transition | 5 items | 20 items | 100 items | 500 items |
| --- | ---: | ---: | ---: | ---: |
| JSON to compact | -44.5% | -46.1% | -46.3% | -46.6% |
| Compact to aliases | -1.86% | -0.47% | -0.09% | -0.02% |
| Absolute alias saving | 5 tok | 5 tok | 5 tok | 5 tok |

Compact output removed roughly 46% of `cl100k_base` tokens. Aliases then saved exactly five more tokens at every scale.

The reason is visible in the wire format. The full header consumed 14 tokens:

```text
id,name,status,assignee,description,priority,created,updated
```

The aliased header consumed nine:

```text
i,n,s,a,d,p,c,u
```

The difference is fixed. Adding 495 more rows does not repeat the header and creates no new alias saving.

## Study 2: Comprehension

Small savings could still be useful if aliases were free to understand. We tested three levels of schema complexity:

| Level | Fields | Alias style | Collision risk |
| --- | ---: | --- | --- |
| 1 | 5 | Single character | Low |
| 2 | 15 | One or two characters | Medium |
| 3 | 30 | Near-collisions such as `s`, `sc`, `sp`, `st`, `sr` | High |

Each level contained 12 data items and 10 questions covering direct lookup, filtering, cross-reference, aggregation, and multi-field reasoning. Every dataset was tested twice: once with full names, and once with aliases plus an explicit dictionary.

Claude Opus 4.6 answered all 60 conditions correctly: 10/10 for full names and 10/10 for aliases at every level. The recorded [benchmark and fixtures](https://github.com/relux-works/skill-agent-facing-api/tree/main/.research/comprehension-tests) are available in the source repository.

This was a same-pipeline evaluation, not an independent model benchmark. The model that answered the questions also participated in the evaluation workflow. Ground truth was checked by field position, and the comparison used identical data, so the result supports a narrow claim: this test observed no accuracy delta when the dictionary remained present. It does not prove that aliases are harmless across models, domains, or long contexts.

Even with perfect answers, the 30-field condition exposed friction. A question about sprint and scope required resolving `sp` and `sc` while avoiding `s` for status and `st` for story points. Full names needed no dictionary lookup.

Aliases also introduce operational failure modes:

- a missing or partially evicted dictionary makes one-character headers ambiguous;
- two tools may assign different meanings to the same alias;
- dense collision families require repeated lookup;
- wide tables still require difficult column tracking;
- a stale dictionary can produce a plausible but incorrect interpretation.

The test showed that a dictionary can preserve comprehension in a controlled case. Requiring that dictionary creates the economic problem measured next.

## Study 3: Session Economics

We measured an 85-token `schema()` roundtrip on real agentquery CLI output:

- 10 tokens for the call;
- 71 tokens for the response;
- 4 tokens of modeled framing overhead.

An aliased compact header saved five tokens on a query that returned such a header. The theoretical break-even point is therefore 17 eligible data queries after each schema lookup:

```text
85 / 5 = 17
```

Real workflows also include operations such as `summary()` that receive no alias benefit. Our simulator used this query mix:

- 50% `get`;
- 30% `list`;
- 10% `summary`;
- 10% other operations.

That mix averages four saved tokens per query and pushes practical break-even above 21 mixed queries per dictionary load.

We modeled 16 compact-output scenarios using session lengths of 10, 20, 50, and 100 queries, with dictionary reload intervals of 10, 20, 50, or never. These are explicit simulation assumptions, not observed production context-eviction rates. The [simulator and complete results](https://github.com/relux-works/skill-agent-facing-api/tree/main/.research/session-simulator) are reproducible.

| Session | Reload interval | Schema calls | Schema cost | Alias savings | Net |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 10 | 1 | 85 | 40 | -45 |
| 20 | 10 | 2 | 170 | 80 | -90 |
| 20 | 20 | 1 | 85 | 80 | -5 |
| 50 | 20 | 3 | 255 | 200 | -55 |
| 50 | 50 | 1 | 85 | 200 | +115 |
| 100 | 10 | 10 | 850 | 400 | -450 |
| 100 | 20 | 5 | 425 | 400 | -25 |
| 100 | never | 1 | 85 | 400 | +315 |

Aliases had a positive balance in 4 of the 16 compact scenarios. Every positive case required at least 50 queries and no dictionary reload more often than every 50 queries.

### Batching beats aliasing

The difference becomes clearer in a common workflow: check five task statuses.

Five separate compact lookups cost 246 tokens in the recorded model, including one schema call. Aliases saved 25 response tokens but required the 85-token dictionary, for a net loss of 60 tokens.

One batched lookup cost approximately 165 tokens. Batching saved about 81 tokens without a dictionary or readability loss.

The precise values depend on query shape and tokenizer. The ordering does not: batching removes whole call boundaries, while aliases shorten one header.

## Why JSON Creates the Wrong Incentive

Aliases look more attractive in JSON because keys repeat inside every object. In our model, aliases saved about three tokens per item in a JSON list. All 16 modeled JSON scenarios had a positive alias balance.

That does not make aliases the best optimization. Switching from JSON to compact output removed about 46% of tokens in the measured payloads. Once the format changed, the repeated keys disappeared and so did most of the alias opportunity.

JSON aliases and schema-once output address the same source of waste. Applying both produces diminishing returns.

## Structure Matters More Than Header Length

The result aligns with work on structured inputs. [Columbo](https://arxiv.org/abs/2508.09403) studies undocumented abbreviated database columns and reports substantial degradation in schema understanding. Our controlled benchmark supplied an explicit dictionary and observed no accuracy loss, but the dictionary itself created the discovery cost.

[TOON](https://github.com/toon-format/toon) also uses schema-once structure with full field names. Its design targets repeated syntax and keys instead of making headers cryptic. [Better Think with Tables](https://arxiv.org/abs/2412.17189) likewise studies gains from tabular structure. These sources cover different tasks and cannot validate our exact percentages, but they point toward the same engineering priority: fix representation before abbreviating vocabulary.

Modern tokenizers add another reason to measure before shortening names. Common fields such as `status`, `name`, and `id` may already be single tokens in a given encoding. Changing a one-token word into a one-token letter saves nothing. Multi-token names can shrink, but in a schema-once header that saving still occurs only once.

## Decision

We rejected field aliases for compact agentquery output.

| Criterion | Threshold | Measured | Result |
| --- | ---: | ---: | --- |
| Net token saving | More than 10% | 0.02% to 1.86%, five tokens fixed | Fail |
| Comprehension degradation | Less than 5% | 0% in controlled benchmark | Pass |
| Discovery economics | Better than 1:5 | 17 eligible queries per schema call | Fail |

The decision is specific to compact schema-once output. A different protocol, tokenizer, query mix, or persistent out-of-band schema may produce different economics.

## What to Optimize Instead

Our optimization order is now:

1. **Field projection.** Do not return fields the agent did not request.
2. **Compact schema-once output.** Remove repeated keys and structural punctuation.
3. **Batching.** Avoid repeated tool-call framing and latency.
4. **Preset tuning.** Match field bundles to real workflows.
5. **Value-level experiments.** Measure date, enum, and identifier representations separately before changing them.

This hierarchy favors savings that begin on the first query and require no hidden dictionary. It also preserves self-describing output, which matters when agents switch tools, lose old context, or hand evidence to a human.

The lesson is broader than field names: optimize repeated structure before compressing meaning. Once a format declares its schema only once, readable names become nearly free.
