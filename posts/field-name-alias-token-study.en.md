---
title: "How Far to Optimize an Agent's Context"
description: "One row set measured rung by rung: minification, field selection, compact representation, the same two choices over MCP, and the abbreviated header that stops paying. With the adapter code that decides whether the backend does less work or only the agent sees less."
slug: "field-name-alias-token-study"
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
  - "Claude Opus 5"
  - "OpenAI Codex"
---

An agent runs a sprint stand-up roll-call: who owns each task, what state is it
in, how urgent is it. One list call answers that. The tracker returns complete
task records, eight fields each, and every one of those fields lands in the
model's context:

~~~json
[
  {
    "assignee": "heidi",
    "created": "2025-11-24",
    "description": "The our caching layer has issues when token expiration. We should rewrite it to improve reliability.",
    "id": "TASK-0001",
    "name": "Implement metrics dashboard endpoint",
    "priority": "critical",
    "status": "in-progress",
    "updated": "2025-11-27"
  },
  {
    "assignee": "rosa",
    "created": "2025-04-22",
    "description": "The the worker pool has issues when failover events. We should decouple it to support horizontal scaling.",
    "id": "TASK-0002",
    "name": "Extract input sanitization filters",
    "priority": "critical",
    "status": "open",
    "updated": "2025-04-29"
  }
]
~~~

Three more records follow in the same shape. At five rows the whole response is
1,732 bytes and 485 tokens under `cl100k_base`. The roll-call needed four fields
per record: `id`, `status`, `assignee`, `priority`. The agent paid tokens for
the other four, including the free-text `description`, and discarded them. The
record bodies are synthetic filler; only their size and shape matter here.

That gap is where context optimization starts. The interesting engineering
question is where it stops: which layers repay their complexity, and which one is
small enough that the machinery around it costs more than the tokens it saves.

This article walks one fixed scenario up a ladder of six representations of the
same rows, at four scales. Only the field set and the serialization change; the
rows never do. Every number comes from checked-in offline fixtures, counted with
[`tiktoken` 0.14.0](https://pypi.org/project/tiktoken/) and the `cl100k_base`
encoding. The [fixtures, measurement script, tests, and raw results](https://github.com/relux-works/skill-agent-facing-api/tree/main/.research/layer-ladder)
are reproducible. Percentages below are rounded to whole points; the exact values
and the denominator of each one are in the recorded results. No model was called,
no MCP host was started, and no production API was touched, so these are counts
for this payload and this tokenizer rather than a savings estimate for anybody
else's workload.

The six rungs, over identical rows:

| Rung | What it is | 5 rows | 20 rows | 100 rows | 500 rows |
| --- | --- | ---: | ---: | ---: | ---: |
| L0 | pretty JSON, all eight fields | 485 | 1,957 | 9,836 | 48,933 |
| L1 | minified JSON, all eight fields | 346 | 1,398 | 7,037 | 34,934 |
| L2 | pretty JSON, four fields | 186 | 742 | 3,688 | 18,433 |
| L3 | minified JSON, four fields | 107 | 423 | 2,089 | 10,434 |
| L4 | header plus value rows, four fields | 65 | 239 | 1,154 | 5,748 |
| L5 | L4 with one-character header aliases | 63 | 237 | 1,152 | 5,746 |

## Layer one: let the caller name the fields

The caller already knows which fields it needs. A query layer that accepts that
selection can return exactly those four fields. This is the idea GraphQL made
familiar, reduced to a single line a shell can pass:

~~~text
list() { id status assignee priority }
~~~

**Situation:** the agent wants the sprint board with just enough context to run
the roll-call. **Expected behavior:** the response carries the four named fields
for every record and omits the rest.

~~~json
[{"assignee":"heidi","id":"TASK-0001","priority":"critical","status":"in-progress"},{"assignee":"rosa","id":"TASK-0002","priority":"critical","status":"open"}]
~~~

Holding the serialization constant and dropping only the four unrequested
fields, the same rows get cheaper by:

| Projection step | Denominator | 5 rows | 20 rows | 100 rows | 500 rows |
| --- | --- | ---: | ---: | ---: | ---: |
| L1 to L3, minified | minified full record | 69% | 70% | 70% | 70% |
| L0 to L2, pretty | pretty full record | 62% | 62% | 63% | 62% |

At 100 rows the minified response shrinks from 7,037 tokens to 2,089, and the
pretty-printed one from 9,836 to 3,688. The exact values run from 69.08 to 70.31
percent and from 61.65 to 62.51 percent across the four scales.

Selection is the largest single reduction here, and it is the one layer whose
benefit grows with the data: every description, timestamp, and name the agent
never asked for simply never enters the response and never costs anything. It is
also the only layer that changes what the response contains. The measurement
checks that the projected payload carries exactly the selected fields and
nothing else; it makes no claim about the four fields it drops. That is also why
both rows above name their denominator: a projection percentage only means
something against the full record in the same serialization.

One bound belongs right here. This projection drops a long free-text
`description` and keeps four short fields. A projection that kept the description
and dropped four short fields would save far less. These are percentages for this
scenario, not a rate to quote anywhere else.

## The denominator decides the credit

Two orderings reach the same payload: minify the whitespace first and then
project the fields, or project first and then minify. The cumulative saving is
identical; which step gets the credit is not:

| Ordering | First step | Second step | Cumulative |
| --- | ---: | ---: | ---: |
| minify, then project | L0 to L1: 28% | L1 to L3: 70% | 79% |
| project, then minify | L0 to L2: 63% | L2 to L3: 43% | 79% |

At 100 rows, projection removes 70 percent of a record that was already minified
and 63 percent of one that was still pretty-printed. The operation is the same;
only the record the percentage is taken from differs. Neither number is wrong. A
number quoted without its denominator is.

The industry folklore around agent output compression lives exactly here. The
familiar "70 to 90 percent" is close to two real quantities in this scenario and
equal to neither: projection removes 69 to 70 percent of a minified full record,
and the whole stack from pretty full JSON down to projected compact output
removes 87 to 88 percent. Both belong to this scenario's four-of-eight
projection, this fixture set, and this tokenizer.

## Layer two: say each field name once

Selection removes fields. The remaining cost is how the surviving fields are
written. In minified JSON each of the four field names is repeated once per
record, so 100 records spell out four names 400 times. A header plus value rows
says each name once:

~~~text
id,status,assignee,priority
TASK-0001,in-progress,heidi,critical
TASK-0002,open,rosa,critical
TASK-0003,review,ivan,critical
TASK-0004,review,bob,medium
TASK-0005,open,heidi,low
~~~

The rows carry the same four fields as the projected JSON, and the measurement
decodes the compact form back to the fixture records to confirm it.

The field set stays at the scenario's four fields. Only the serialization
changes, from projected minified JSON to a header plus value rows, which is the
step from L3 to L4:

| Scale | Minified projected JSON | Header plus value rows | Reduction |
| ---: | ---: | ---: | ---: |
| 5 | 107 | 65 | 39% |
| 20 | 423 | 239 | 43% |
| 100 | 2,089 | 1,154 | 45% |
| 500 | 10,434 | 5,748 | 45% |

This is the comparison the previous version of this article could not make. Its
fixture had no projected compact payload, so it compared serializations at one
field set and projections at one serialization, and refused to combine them.
This ladder holds the field set fixed across L3 and L4, so the only thing that
changes between the two rungs is the serialization. The exact values run from
39.25 to 44.91 percent.

Representation has a limit that selection does not: the saving scales with the
number of field names and the punctuation around them, not with the amount of
data behind them. Wide records with short values gain the most. A response
dominated by long free text gains the least, because the text is the payload
either way. The ladder shows that directly: minifying the full record, which
still carries the descriptions, removes 28 to 29 percent of its tokens, while
minifying the projected record, where the long field is already gone, removes 42
to 43 percent.

Taking the whole stack together, from pretty full JSON down to the compact view
of four fields, L0 to L4, removes 87 to 88 percent of the tokens. At 100 rows, a
9,836-token response becomes 1,154 tokens.

## What each move costs once

A smaller response saves tokens on every query, but the session as a whole comes
out ahead only once those savings have paid back the input tokens the agent
spent on the text it read to make that particular move up the ladder. The
one-time cost of a transition is easy to state: the transition costs whatever
the agent has to read for the destination rung and did not read for the source
rung. Text the agent reads for both rungs sits on both sides of the transition
and does not enter that cost.

Every rung of this ladder is output from the same query layer, so the agent
reads the schema response on both sides of every transition. Having read it
once, the agent pays nothing extra to write a projected query instead of a full
one, and nothing extra to ask for the compact format instead of JSON. Three
texts the agent reads once per session were measured: the schema response for
this scenario is 535 tokens, the one for the shipped example command-line tool
is 1,154, and the alias legend is 21.

| Move | Charged | Sunk on both sides | One-time | Break-even |
| --- | --- | --- | ---: | ---: |
| projection, L1 to L3 | nothing | schema response | 0 | 1 query |
| compact, L3 to L4 | nothing | schema response | 0 | 1 query |
| aliases, L4 to L5 | alias legend | schema response | 21 | 11 queries |

Only the move to aliases adds anything the agent has to read: the alias legend.
Projection and the compact view add nothing new to read, so inside a session
that already uses the query layer they are free and pay off from the first
query.

An earlier version of this article charged the whole schema response, 535
tokens, against the projection and compact rows, as if a session that sends full
queries never read it. At five rows projection saves 239 tokens per response and
the compact view another 42, so that accounting produced break-evens of three
and thirteen queries and a negative net for compact in any session shorter than
thirteen queries. Those figures charged each of those transitions for a response
the agent reads on both sides of it, and they are withdrawn.

There is a framing this ladder cannot support, and it is worth naming because it
is the one everybody reaches for: whether to adopt a query layer at all. No rung
here skips the query layer. Even the full record, L1, is that layer's own
output, not a REST response. So this measurement cannot say whether one schema
response is worth paying against a plain client that needs no contract; that
comparison has a different baseline, and nothing here measures it. What the
ladder does show is narrower and still useful: an agent already working through
the query layer pays nothing extra to choose projection or the compact view. And
the agent pays for the schema response only if it introspects at all;
documenting the grammar in a skill file moves that cost into the skill file
rather than deleting it.

## Layer three: the same two decisions over MCP

Neither layer is tied to any one transport. A tool exposed over the [Model
Context
Protocol](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
takes the same selection argument and returns the same representation, because
`fields` is an ordinary tool argument in the input schema. Projection is a
server design choice, not a protocol capability, and nothing in this measurement
says MCP is unable to project or to emit compact output.

One bound governs everything in this section. The tool contracts compared here
were built from the real schema response rather than captured from a running
server: no host was started, no SDK was executed, no transcript was recorded.
The recorded results label them as a synthetic contract, not a host measurement.
The protocol revision was probed rather than assumed: on 24 September 2026 the
specification's `latest` path redirected to revision `2026-07-28`, with a
control revision that cannot exist returning 404, so a site outage could not be
read as a withdrawn revision.

How much the agent reads before its first call depends on how fully the server
describes its tools, so both profiles are published. The minimal profile carries
only the fields the tool interface requires plus what the schema response
already publishes. The structured profile adds the output schema that the
current revision expects from a server returning structured content, derived
from the same field list.

| Contract | Tools | Profile | MCP tool list | Schema response | Difference |
| --- | ---: | --- | ---: | ---: | ---: |
| scenario | 3 | minimal | 471 | 535 | -64 |
| scenario | 3 | structured | 676 | 535 | +141 |
| example CLI | 9 | minimal | 1,490 | 1,154 | +336 |
| example CLI | 9 | structured | 1,774 | 1,154 | +620 |

This comparison has no stable winner. For the scenario contract the sign changes
with the profile: the minimal tool list is 64 tokens shorter than the schema
response, and the structured one is 141 tokens longer. So neither side wins on
tool-definition cost, and any claim in either direction has to name its profile.
What is ruled out on every profile measured here is the folk figure of two to
three thousand tokens of dead weight per session for a tool surface of this
size: the largest figure measured anywhere in this slice is 1,774.

The real asymmetry is when the cost is paid, not how large it is. An MCP host
injects the tool list at the start of every session whether the agent asked or
not; the agent pays for the schema response only when it asks for it. That is a
difference in host behavior, and this measurement does not quantify it: how a
particular host caches tool definitions, where it places them, and what it
charges for them is not measured here.

One argument for compact output exists only inside MCP. The server returns a
tool result as a string inside JSON, so every quote character in the payload
itself is escaped and charged a second time. Below is the MCP overhead over the
same response returned by the query layer directly, per payload format:

| Payload | Quotes at 5 rows | Quotes at 500 rows | Overhead at 5 rows | at 500 rows |
| --- | ---: | ---: | ---: | ---: |
| L4, compact | 0 | 0 | +51 | +51 |
| L3, minified projected JSON | 80 | 8,000 | +59 | +1,049 |
| L1, full minified JSON | 160 | 16,000 | +69 | +2,049 |

The compact payload has no quotes, so its overhead is exactly 51 tokens at every
scale: that is the cost of the result envelope itself. Everything above that
grows with the quote count, not with the payload size: the 500-row compact
payload is fifty-three times the size of the 5-row JSON payload and pays less
overhead. In other words, JSON inside MCP pays for escaping that it does not pay
when a command-line tool simply writes it to standard output.

## Layer four: abbreviating the header, and why it stops there

After selection and representation, one visible target remains. The header line
still spells out four field names. Replacing them with single characters makes
that line shorter:

~~~text
i,s,a,p
TASK-0001,in-progress,heidi,critical
TASK-0002,open,rosa,critical
~~~

Every value row is byte-identical to the previous section. Only the header
changed.

| Scale | Full-name header | Aliased header | Saved |
| ---: | ---: | ---: | --- |
| 5 | 65 | 63 | 2 tokens (3.1%) |
| 20 | 239 | 237 | 2 tokens (0.8%) |
| 100 | 1,154 | 1,152 | 2 tokens (0.2%) |
| 500 | 5,748 | 5,746 | 2 tokens (0.03%) |

Two tokens per response, however many rows follow the header. The reason is
structural: the previous layer already moved the field names out of the rows and
into the header, so the only text left to abbreviate is that one line, and its
share of the response shrinks as the row count grows. An earlier study on the
same library measured the same shape on a wider header: five tokens for eight
columns, also constant.

Those two tokens are not free. An agent that meets `s` and `p` in a header has
to learn what they mean, and the legend that teaches it is 21 tokens. The agent
reads the legend once per session and saves two tokens on every response, so
aliases come out ahead only from the eleventh query on, and never by much: ten
queries at five rows net minus one token, a hundred queries net plus 179, and a
single 500-row response already costs 5,748 tokens.

The failure modes are worse than the arithmetic. If the legend is partly evicted
from the context, the header still parses, but the agent now reads it as
something else. Two tools can assign the same letter to different fields. A
schema with `s`, `sc`, `sp`, and `st` in it forces a lookup on every read. Each
of those turns a two-token saving into a correctness question, which is a poor
trade at any session length.

So the useful result of this layer is not its balance sheet but the boundary it
marks: once a format names each field once, the last fraction of a percent of
the problem is all that remains, and abbreviating the names themselves is the
first place where an optimization returns fewer tokens than it adds in
ambiguity. We do not ship alias support, and this rung has no production
implementation.

## Where the boundary sits in a real adapter

All the layers above describe the response as the caller sees it. They say
nothing about how much work the backend did, and that is what decides where the
selection belongs.

When the source API accepts a field selection, the adapter can pass it through,
and the backend genuinely does less. Our Jira adapter maps the selected fields
onto Jira REST field names in
[`APIFieldsFromSelector`](https://github.com/relux-works/skill-jira-management/blob/5c9b31fddb0495d2eaee32564d153fc6955a35b2/internal/query/schema.go#L39-L54),
both the [`get`](https://github.com/relux-works/skill-jira-management/blob/5c9b31fddb0495d2eaee32564d153fc6955a35b2/internal/query/schema.go#L300)
and [`list`](https://github.com/relux-works/skill-jira-management/blob/5c9b31fddb0495d2eaee32564d153fc6955a35b2/internal/query/schema.go#L359-L360)
handlers hand that list to the client, and
[`GetIssue`](https://github.com/relux-works/skill-jira-management/blob/5c9b31fddb0495d2eaee32564d153fc6955a35b2/internal/jira/issues.go#L12-L27)
puts it in the request:

~~~go
q := url.Values{}
if len(fields) > 0 {
    q.Set("fields", strings.Join(fields, ","))
}
~~~

The selection reaches the origin server. The response is smaller on the wire
before the adapter sees it.

The Confluence adapter shows the other shape, with one partial exception inside
it. Its
[`get` handler](https://github.com/relux-works/skill-confluence-management/blob/10e342b1c60e52233cc4ef662e70e6b6dcc8011b/internal/query/schema.go#L247-L256)
derives a single boolean from the projection and passes it down:

~~~go
includeBody := containsField(ctx.Statement.Fields, "body")
page, err := client.GetPage(pageID, includeBody)
~~~

That boolean is the only part of the selection that reaches the API. In
[`pages.go`](https://github.com/relux-works/skill-confluence-management/blob/10e342b1c60e52233cc4ef662e70e6b6dcc8011b/internal/confluence/pages.go#L19-L45)
it decides whether the v2 call sends the `body-format` parameter at all, and
whether the v1 call appends the page body to its `expand` list, which otherwise
never changes. The rest of the projection never leaves the wrapper. The [`list`
handler](https://github.com/relux-works/skill-confluence-management/blob/10e342b1c60e52233cc4ef662e70e6b6dcc8011b/internal/query/schema.go#L275-L303)
has no equivalent at all: it fetches every page the space returns and keeps the
selected fields afterwards. The agent still receives only those fields, and the
context saving is real. But the backend did nearly the same work it would have
done without the selection.

That difference is the honest boundary of a wrapper. Field projection at the
agent boundary always saves agent context; it saves backend work only where the
adapter pushes the selection into the request it sends upstream. Neither shape
is a defect: the Confluence v2 API simply offers no field-selection parameter
for these calls. But they are two different claims, and they must not be merged
into "projection makes it faster". [Named
presets](https://github.com/relux-works/skill-confluence-management/blob/10e342b1c60e52233cc4ef662e70e6b6dcc8011b/internal/query/schema.go#L117-L120)
make the common selections short without changing that fact.

In [agentquery](https://github.com/relux-works/skill-agent-facing-api), the Go
library behind both adapters, both layers are small.
[`FormatCompact`](https://github.com/relux-works/skill-agent-facing-api/blob/5bfc87ffdd3bad877f55bc2d2c369ecaba9d7e35/agentquery/format.go#L20-L35)
writes the header and then the rows, the
[selector](https://github.com/relux-works/skill-agent-facing-api/blob/5bfc87ffdd3bad877f55bc2d2c369ecaba9d7e35/agentquery/selector.go#L17-L25)
applies the projection, and the
[parser](https://github.com/relux-works/skill-agent-facing-api/blob/5bfc87ffdd3bad877f55bc2d2c369ecaba9d7e35/agentquery/parser.go#L318-L370)
accepts several statements separated by semicolons so a batch of lookups is one
call. Whether a batch saves tokens depends on the host's per-call framing, which
this measurement does not observe.

## What this measurement does not show

One scenario, one field-size distribution, one tokenizer. The projection drops
one long free-text field and keeps four short ones; a projection that did the
reverse would save far less, so every percentage above should be read as "in
this scenario". No REST server, no HTTP transfer, no latency, no backend cost:
everything here is a serialized payload's token count. No host was measured, for
MCP or for the query layer, so host framing, tool-use scaffolding and
system-prompt text are all uncounted. The MCP contract is constructed from real
schema output rather than captured from a running server; its minimal profile is
a floor, since no real current-revision server would publish a contract that
short, and its structured profile is itself a lower bound on a fully populated
contract. The revision pin is fresh as of the dated probe, not for all time.
Filtering is deliberately outside the ladder, because it changes the row set and
the ladder's premise is that the row set does not change. And the aliased rung
has no production implementation.

## What to build

Put the selection in the source API when you own it: only a field argument that
reaches the origin query makes the backend do less work, and only that saving
scales with the data rather than with the schema. Make the compact
representation the default for responses an agent reads: at the same field set
it removes 39 to 45 percent of what the projected JSON cost, and an agent
already working through the query layer pays nothing extra to choose it. Offer
both over whichever transport your callers need, including MCP, since neither
layer is tied to the transport.

Quote every percentage with its denominator. The same projection in this
scenario removes 70 percent of a minified record or 63 percent of a
pretty-printed one, and a figure that travels without its denominator will be
read against the wrong one.

When the API is somebody else's, or when the native selection is still ahead of
you, a wrapper is the right answer with one honest caveat: it protects the model's
context and it promises nothing about the load on the origin server. Say which of
the two you are delivering.

And stop before the header. Two tokens per response at every scale, against a
21-token legend the agent has to keep in its context and a class of decoding
failures a correct format does not have: that is what an optimization looks like
when it has run out of structure to remove. When the remaining target is a
single line, the work left to do is somewhere else.
