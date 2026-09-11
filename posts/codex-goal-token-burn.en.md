---
title: "Why Codex burns a weekly limit in a day while the agent waits for the tide"
description: "Spin-waiting in Codex CLI: goal mode restarts the model 0.03 seconds after every turn and demands proof of waiting by live polling, the pause tool is issued to one model in the catalog, and every poll rereads a context of hundreds of thousands of tokens. In an archive of 3808 sessions, the 52 with goal mode ate half of all input tokens. How Claude Code solves the same task, and how to describe it in async/await terms."
slug: "codex-goal-token-burn"
lang: "en"
draft: false
authors:
  - name: "Ivan Oparin"
    title: "CEO / Founding Engineer, Relux Works"
    links:
      - "https://github.com/ivanopcode"
      - "https://www.linkedin.com/in/ivanoparin/"
  - name: "Alexis Grigoryev"
    title: "CTO / Founding Engineer, Relux Works"
    links:
      - "https://www.linkedin.com/in/alexis-grigoryev-22bab159/"
aiSystems:
  - "Claude Fable 5.1"
---

This is the story of how we found an input-token leak in models running
inside Codex. The leak is still there, and because of it crowds of people on
X keep wondering why a $200 weekly subscription limit is gone in a day. As
often happens in programming, the spark was a small bug around integers and
floats, but that is only the spark and a small part of it; the real story is
more interesting. Reading it with full understanding takes about 30
minutes.

## TL;DR

- Our Codex orchestrator was waiting for its child agents. The model was
  muse-spark 1.3 through the opencode provider (kudos to the Muse team, 1.3
  is already a strong model). In 48 minutes goal mode launched 173
  continuations, each rereading 120 to 470 thousand tokens of context, until
  the provider answered 429. From here on this is the source session.
- The cause: goal mode restarts the model 0.03 seconds after every turn and
  counts waiting only if the model polled a live process, while the pause
  tool `clock.sleep` is issued only to the recently released `gpt-6-astra`.
  Waiting turns into a spin: every check costs the full context.
- The price: out of 3808 sessions from July to September 2026, the 52 with
  goal mode ate half of 59.2 billion input tokens. An hour of waiting cost 83
  to 188 million. The weekly limit of a $200 Pro account ran out fifteen
  times over the summer, with a median of 23 hours from the start of the
  window.
- What to do: the simplest option is to take `gpt-6-astra` at minimal effort
  as the floor for goal tasks, it is the only model with `sleep` out of the
  box. Otherwise turn `sleep` on through the config for the other models,
  wait for all child processes with a single call and put a budget on every
  goal. We are rolling out the second path ourselves but have not verified
  it at scale yet. On the Codex side: issue `sleep` whenever a goal is
  active and pause between continuations, the way Claude Code does.
- All numbers are for Codex 0.154 and rollouts from July, August and
  September 2026. Every claim about the mechanics links to the Codex source
  on GitHub; the rollouts themselves are not published.

## How tokens are counted

A language model doesn't remember the conversation. Every time it needs to
take a step, the entire transcript is sent to it again, and it answers with a
single action: a tool call or text. If the transcript is 240 thousand tokens
long, every step costs 240 thousand input tokens. It doesn't matter that the
step itself is "run `tail -n 18`". We pay for the volume the model rereads on
every step. So any piece of work costs the number of steps times the size of
the context, and the only ways to make it cheaper are fewer steps or a smaller
context.

### A short detour into the KV cache

To process a long context, the model computes a set of internal values for
every token, called keys and values, hence KV. If the next request starts with
the very same sequence of tokens, those values don't need to be recomputed,
they can be taken from the cache. Only the tail that differs has to be
computed fresh.

In an agent session almost every request is the previous request plus a few
new lines. So the cache hits almost every time. In the archive analyzed here,
97.8% of input tokens came from the cache.

Providers reflect this in the price. At OpenAI cached input costs 10% of the
regular rate, and caching kicks in automatically on prompts longer than 1024
tokens, see the [prompt caching docs](https://developers.openai.com/api/docs/guides/prompt-caching).
For API billing that's good news: almost all of the reread context goes at the
discounted rate.

### What about the subscription

For a ChatGPT subscription the unit of accounting is a share of a limit in a
sliding window. The formula behind that share isn't published. The Codex
client only receives a usage percentage and a reset time from the server,
visible in the
[protocol](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/protocol/src/protocol.rs)
in the `RateLimitWindow` struct. Whether the cache discount applies there
can't be checked from the outside. In the same caching docs OpenAI says
plainly that for API rate limits cached tokens count as regular ones. The only
thing we know about the subscription comes from experience: sessions where
98% of the input came from the cache still blew through the weekly limit. So
from here on I count input tokens in full, no discount: they appear to be what
decides when you hit the wall.

## What "waiting" means

An agent often has to wait for something external: a build, tests, another
agent. There are two ways to do it.

**Notification.** The agent takes one step, "tell me when it's done", and
releases the turn. While we wait there are no steps, so there is no cost.
When the event happens, one message arrives, and that's one new step.

```
launched → released the turn → silence, zero tokens → "done" → one step
```

**Polling.** The agent checks periodically on its own: is it done yet? Every
check is a step, every step is the full context.

```
checked → 240k → "no" → waited → checked → 240k → "no" → ...
```

Hence the formula the whole text is built around:

```
cost of waiting = number of checks × size of context
```

Polling isn't evil in itself. If the agent can sleep between checks without
spending a step, polling costs the same as a notification. The trouble starts
when it can't sleep.

### A known pause and an unknown one

A simple test. Ask the model: "write one, and five seconds later write two".
It will do it correctly and cheaply: one `sleep 5` call in the shell, the
command blocks the turn for five seconds, returns, the model writes "two".
One step, the context paid for once.

Now ask: "wait until the build finishes". The duration is unknown. Could be a
minute, could be three hours. The model can't do a single three-hour `sleep`:
if the build finishes in a minute it sleeps through the result, and if it
doesn't finish it runs into the ceiling on how long one command may take. So
it picks an interval, say 30 seconds, and loops: sleep, check, sleep, check.

```
known pause:    1 sleep               = 1 step
unknown pause:  N × (sleep + check)   = 2N steps
```

The model waits five seconds correctly because it was told how long. For an
unknown pause it needs a different primitive: "wake me when it happens".
Everything that follows is about whether the model has one.

### In async/await terms

For programmers (sorry, vibe coders) it's easier to think of this as an async
task. A model turn is a task run, the end of the turn is the point
where the task yields control. There are three ways to wait for an external
event, and all three are familiar from asynchronous code.

```
// 1. await: the task is suspended, the runtime keeps the continuation
let result = await child.finished     // zero calls while we wait
handle(result)                        // one call on the event

// 2. sleep-poll: suspend for a fixed interval
while !child.finished {
    await sleep(45s)                  // one call per interval
}

// 3. spin: the task can't suspend at all
while !child.finished {
    poll()                            // call after call, no pauses
}
```

In ordinary code a spin-wait just heats one core. For an agent it's worse:
the model's memory is its context, and every iteration of the spin rereads
that whole memory. It's a `while` loop that copies the entire process heap on
every pass.

<a href="/blog/codex-goal-token-burn/wait-primitives-en-light.png"><picture>
<source srcset="/blog/codex-goal-token-burn/wait-primitives-en-dark.png" media="(prefers-color-scheme: dark)">
<img src="/blog/codex-goal-token-burn/wait-primitives-en-light.png" alt="One minute of waiting three ways: await, sleep-poll, spin">
</picture></a>

Which of the three variants the model gets is decided by the dispatcher that
launches its turns and by the set of tools it was handed. Next, what Codex
hands out.

## How Codex waits

Codex recently got the right tool. It's called `clock.sleep`: "sleep this
many milliseconds, wake me earlier if something arrives". It landed in
[PR 28429](https://github.com/openai/codex/pull/28429) and shipped in 0.141.0
on June 18, 2026; it has gone by the name `clock.sleep` since 0.143.0 on
July 8. The implementation in
[`sleep.rs`](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/core/src/tools/handlers/sleep.rs)
does exactly that: sleeps for up to 12 hours and is interrupted by new input.
This is the second variant from the list above, and for waiting it's almost as
good as the first.

Only the model doesn't get it. The tool is registered by a rule in
[`spec_plan.rs`](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/core/src/tools/spec_plan.rs):
it's there if the model's catalog entry declares `clock` support, or if it has
been force-enabled in the config. In the built-in
[model catalog](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/models-manager/models.json)
`clock` is present on one model, `gpt-6-astra`. For `gpt-5.6-sol`, `gpt-5.5`,
`gpt-5.4` and every model on a custom provider the list is empty. Meanwhile
`codex features list` says `sleep_tool stable true`, but that's a feature
flag, not evidence that the tool is in the request. Across the archive of 3808
sessions `sleep` was called 420 times, and 418 of those were `gpt-6-astra`.

Why the tool is issued to one model isn't written in the sources, but there
are hints. The catalog field is called `experimental_supported_tools`, and the
default mode is annotated in the code as "preserve the existing model
defaults". It looks like a staged rollout: the tool itself runs on the client
and asks nothing of the model. `gpt-6-astra` has a second experimental tool in
the same field, `send_user_message_async`, which lets it write to the user
without ending the turn. Together they describe a model that was taught to
work in long background sessions: wait, wake up, report along the way. This
looks like a new line of behavior that was measured on the new model and not
attributed to the older ones. There is a reason for caution: a model that
wasn't trained to pick a sleep duration may fall asleep instead of working or
spin `sleep 1` in a loop. The logic has a hole in it: goal mode is on for
every model, while the tool without which goal mode turns into a spin is on
for one.

### What is left without sleep

The only way to wait is to run a command in the shell: `sleep 30`, `tail` on
a log, whatever. That's a step, so it's the full context. And the step has a
ceiling on its length. The shell in Codex runs through unified exec: the
command starts in a pseudo-terminal, and the tool hands control back to the
model on a `yield_time_ms` timer. The default is 10 seconds, the maximum 30,
see the constants in
[`unified_exec/mod.rs`](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/core/src/unified_exec/mod.rs)
and the default in
[`handlers/unified_exec.rs`](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/core/src/tools/handlers/unified_exec.rs).
If the process is still alive, the model gets a session id and can keep
reading its output with an empty-input `write_stdin`. That empty call can wait
longer, up to five minutes. So even without `sleep` the model has a legitimate
way to pay one call for five minutes of waiting.

In the source session that path was closed. muse-spark was running through a
custom provider and passed numbers in tool arguments as floats: `60000.0`
instead of `60000`. The Codex parser expects an integer and rejects the call.
The archive shows it across every session on this model: 10 of 10
`write_stdin` calls and 23 of 25 calls with `yield_time_ms` failed with an
error like `invalid type: floating point 60000.0, expected u64`. It also means
a force-enabled `sleep` wouldn't help it: its `duration_ms` argument is an
integer too.

<a href="https://knowyourmeme.com/memes/drakeposting"><picture>
<source srcset="/blog/codex-goal-token-burn/drake-muse-spark-dark.jpg" media="(prefers-color-scheme: dark)">
<img src="/blog/codex-goal-token-burn/drake-muse-spark-light.jpg" alt="Drake turns away from 60000 and approves of 60000.0">
</picture></a>

That's where the 10-second ceiling comes from. When the model launches a
command, Codex hands control back on the `yield_time_ms` timer, 10 seconds by
default. The timer can only be extended with a number in the argument, and
numbers from this model don't get through. The empty `write_stdin`, which can
wait up to five minutes, fails for the same reason. So one trip to the shell
never lasts longer than 10 seconds, whatever the model writes.

In practice the model never even reached that ceiling. Its poll was a
snapshot: the command read the child process's event log and came back within a
second. The rest of the turn went into two model calls, one to launch the poll
and one to write "no changes". The median turn was ten seconds, the mean
seventeen counting the longer turns, and goal launches the next one right
away. Over 48 minutes that added up to 173 such turns and 466 model calls,
each call rereading 120 to 470 thousand tokens. In total, 149 million input
tokens in 48 minutes, or 188 million per hour.

For comparison, on the official `gpt-5.6-sol` the same loop in session A cost
83 million per hour: there the model waited 30 seconds per call, the ceiling
for a running command. In session B, 20 million: the model kept reading output
with an empty `write_stdin` and got five minutes of pause per call. The longer
the pause inside a single call, the cheaper the hour. The source session took
the last brake off the loop, and that's how the bug became visible.

## What goal mode adds

Without goal the model has an escape hatch: end the turn and go quiet. Even
without `sleep` that's a free pause. The human comes back, writes something,
we continue. In async terms it's the first variant, await: the task
yielded control, and nobody wakes it until an event happens.

Goal mode removes that hatch too. As soon as the thread becomes idle, the goal
extension immediately sends the model a new turn: "continue working toward
the goal". It's visible in
[`extension.rs`](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/ext/goal/src/extension.rs):
the `on_thread_idle` handler calls `continue_if_idle` from
[`runtime.rs`](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/ext/goal/src/runtime.rs),
which starts a turn right away. No backoff, no counter of empty
continuations. The token budget per goal is unset by default.

[![Ralph Wiggum on the bus: (chuckles) I'm in danger](/blog/codex-goal-token-burn/ralph-in-danger.jpg)](https://knowyourmeme.com/memes/ralph-in-danger-im-in-danger)

Ralph is here for a reason: any goal mode is essentially a
[Ralph loop](https://ghuntley.com/ralph/),
`while true; do codex "continue"; done`, just built into the product. The
face fits.

The word "immediately" is measurable here. In the source session, between
the end of one turn and the start of the next there were 0.02 to 0.05
seconds, median 0.03. A turn usually lasted ten seconds: exactly what the
model needs to read the context, call one poll and write "no changes". The
polling frequency was set by the model's response latency and nothing else.

<a href="/blog/codex-goal-token-burn/turn-cadence-en-light.png"><picture>
<source srcset="/blog/codex-goal-token-burn/turn-cadence-en-dark.png" media="(prefers-color-scheme: dark)">
<img src="/blog/codex-goal-token-burn/turn-cadence-en-light.png" alt="Two and a half minutes of the source session: turns of 8 to 27 seconds with 0.03-second gaps">
</picture></a>

There is an important moment in this picture. At 23:50 I asked the model why
it checks so often. The model answered, translated from Russian: "The goal
contract requires every turn to either move the work or prove a verified wait
by live-polling the runs", and promised to poll less often. 0.3 seconds after
its answer, goal mode launched the next turn. The promise could not be kept:
the model doesn't control when it gets called next.

The text of that contract lives in
[`continuation.md`](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/ext/goal/templates/goals/continuation.md).
It has a paragraph about waiting. Waiting only counts if in this turn the
model polled a live process. "I'm waiting" without a poll counts as no
progress. The model itself can only move the goal to `complete` or `blocked`,
and `blocked` is allowed after three identical blockers in a row, while
waiting for child processes doesn't count as a blocker. Only a human can pause
the goal.

The result is a trap:

- you can't end the turn and wait, you get restarted at once;
- the restart counts as "no progress" unless you poll a process;
- so every turn has to poll something;
- every poll costs the full context.

The model follows the requirement literally. The requirement is phrased so
that the behavior that is correct by the contract is the most expensive in
tokens. In async terms the goal extension is a dispatcher with a single
rule: the queue is empty, enqueue the same task again. And the contract
forbids the task to suspend in any way other than polling. Together that's a
spin, the third variant on the list.

## How the same idea works in Claude Code

Claude Code has the same mode, also called
[`/goal`](https://code.claude.com/docs/en/goal): you set a condition and
Claude works until it's met. The dispatcher is what differs. Per the
[docs](https://code.claude.com/docs/en/goal), after every turn a separate
small model checks the condition, and only then does a new turn start. If a
background command or a subagent is still running, the check is deferred and
their result arrives as a new turn. When background work drags on, the first
check-in comes after 30 minutes, then the interval doubles, and there are no
more than three check-ins without a human. Several turns in a row without a
single tool call stop the loop with a warning. In Codex the answer to each of
these cases is the same: a new turn in 0.03 seconds.

The line about background work is the key one. That's the await from the
first variant: the task yielded control, the dispatcher holds the
continuation and wakes it on the event. The background primitives themselves
are there too: Bash has a
[background mode](https://code.claude.com/docs/en/interactive-mode#background-bash-commands)
with a notification on completion, subagents have one as well, and
[Monitor](https://code.claude.com/docs/en/tools-reference) watches a stream of
events and wakes the model on every output line. The
[`/loop`](https://code.claude.com/docs/en/scheduled-tasks) docs plainly
recommend Monitor over polling on a timer because it's cheaper in tokens.

That's why this loop doesn't show up in Claude Code sessions: the dispatcher
knows how to wait for events and how to slow down when the wait gets long.
The Codex dispatcher only knows how to restart.

Model training has nothing to do with it. In Claude Code the wrapper watches
the background process: when it finishes, the wrapper puts a "task finished"
message into the conversation and calls the model. Codex has similar
primitives, the thread queue and `sleep` interrupted by input, but the
completion of a shell command never becomes a message; the model has to read
the output itself. The whole difference is who waits: a wrapper that wakes the
model, or a model that asks on its own.

The Claude Code sources are closed, so we looked at the mechanics through
[ClawCodex](https://github.com/agentforce314/clawcodex), a third-party Python
port that carries the TypeScript reference over file by file with the
original line numbers. The notification path there is short:
[`background.py`](https://github.com/agentforce314/clawcodex/blob/main/src/tool_system/tools/bash/background.py)
waits for the process and puts a `<task-notification>` envelope on the queue,
[`agent_server.py`](https://github.com/agentforce314/clawcodex/blob/main/src/server/agent_server.py)
drains the queue between turns and hands it to the model as a single turn.
While the process runs, the model isn't called. Goal mode isn't fully
reproduced in the port, so for that the docs remain the source.

## Empty turns

There's an even simpler version of the same trap. The model ends the turn
having done nothing, say it wrote "waiting". Goal restarts it at once. It does
nothing again. Restart again. The logs have chains of four such turns in 20
seconds. In one session fourteen empty turns cost 77 million input tokens:
nothing happened, and the context was reread fourteen times. This is exactly
the case Claude Code guards against by stopping after several turns without
tool calls.

## Why this hits orchestrators hardest

Our orchestrator works like this: it doesn't write code itself, it hands
tasks to child agents, each in its own branch with its own context. That
parallelizes the work and keeps the parent's context from bloating. But the
parent has to wait for the child processes, and there are usually many of them.

With one child process it's still cheap. There's a command that blocks the
turn until the process finishes, and it's the same case as `sleep 5`: one
step, except the duration is set by an event rather than a timer. The ceiling
for a single call in Codex is about five minutes, that's how long an empty
`write_stdin` can wait, so a three-hour process costs about 36 calls in a row.
That's 12 steps per hour, not 270.

With two or more, everything changes. While the orchestrator is blocked on
process A, process B can finish, crash or ask for help, and the orchestrator
won't see it. If all it needed was the fact "both finished", it could wait for
A, then B, and that would still be cheap. But the orchestrator has to react
along the way: accept a result, lift a lock, restart the one that crashed. So
it doesn't dare block for long and replaces the block with a short loop: look
at A, look at B, wait, again. Bottom line: one child process is a known wait,
N processes without a shared barrier is polling. The sessions below show it
literally: the orchestrator knew about the blocking wait and used it 31 times,
but between the blocks it still walked through both processes' logs.

The same thing happens in any pattern where an agent starts several long
processes and can't get notified: several CI runs, a build and a deploy in
parallel, several remote jobs. An orchestrator with child processes is just
the most common case.

Codex has its own barrier over several child agents, the `wait_agent` tool,
described as "pass multiple ids to wait for whichever finishes first", see
[`multi_agents_spec.rs`](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/core/src/tools/handlers/multi_agents_spec.rs).
But it only sees agents that Codex itself spawned through `spawn_agent`. Our
orchestrator's child processes don't exist for it.

## What the model had in the source session

Here are the ways to wait that a model in Codex has in theory, and what
happened to each of them in the source session.

| Way to wait | What happened |
|---|---|
| `clock.sleep` | Not issued: a model on a custom provider has no `clock` in the catalog |
| `wait_agent`, the barrier over several child agents | The child processes aren't Codex agents, the tool can't see them; in the next session that same night an attempt at a native `spawn_agent` returned `unsupported call` |
| Empty-input `write_stdin`, up to 5 minutes per call | The only attempt failed: `floating point 36429.0, expected i32` |
| `yield_time_ms` longer than 10 seconds | The only attempt failed: `floating point 60000.0, expected u64` |
| `sleep` in the shell | Ten times, 4 to 8 seconds each; anything over 10 seconds would have been cut off by unified exec |
| The blocking flag on the watch command | Never used, and it wouldn't have helped: the same 10-second ceiling |
| End the turn and wait | A new turn in 0.03 seconds |

Five of the seven doors were shut by the environment, one the model never
found, and one was locked by the contract. What remained is what we saw in
the log: one poll per turn. Of the session's 181 turns, 135 consisted of
exactly one such command.

<a href="/blog/codex-goal-token-burn/night-session-calls-en-light.png"><picture>
<source srcset="/blog/codex-goal-token-burn/night-session-calls-en-dark.png" media="(prefers-color-scheme: dark)">
<img src="/blog/codex-goal-token-burn/night-session-calls-en-light.png" alt="The source session: 544 model calls, input tokens of every call, the goal loop highlighted">
</picture></a>

This picture also gives us a natural experiment. While goal is active, the
orange bars come as a solid wall, each taller than the last, because the
context grows. At 00:03 the provider answers 429, the turn fails with an
error, and the loop freezes for an hour until I come back. At 01:34 I resume
the goal, and the polling starts again, every 12 seconds. At 01:35 I press
Ctrl-C, the goal pauses, and eight minutes later I say "let's continue
without the goal". Then five calls, the work is done, the session ends. Same
context, same model, same task; only the dispatcher changed.

## What the sessions showed

I took every Codex rollout from two machines for July, August and September:
3808 files, each one thread, child threads included. They hold 59.2 billion
input tokens and 129 million output tokens, with 97.8% of the input from the
cache. CLI versions from 0.144 to 0.154, mostly `gpt-5.6-sol`, plus `terra`,
`luna`, `gpt-5.5`, `gpt-5.4`, `gpt-6-astra`, `gpt-5.3-codex-spark`, as well
as Qwen 3.6 and muse models through custom providers.

Goal mode was on in 52 sessions out of 3808, one and a half percent. Here is
what they weigh.

<a href="/blog/codex-goal-token-burn/goal-share-en-light.png"><picture>
<source srcset="/blog/codex-goal-token-burn/goal-share-en-dark.png" media="(prefers-color-scheme: dark)">
<img src="/blog/codex-goal-token-burn/goal-share-en-light.png" alt="52 goal sessions take 49% of input tokens across 3808 sessions">
</picture></a>

One and a half percent of the sessions ate half the tokens: 29.2 billion out
of 59.2. The seven most expensive sessions in the archive, 1.8 to 5.7 billion
each, all had goal mode on. The heaviest session without it weighs 1.2
billion. Without forced continuation the model ended its turn and waited for
the human, and that's free.

And here is what it meant for the limit. Every `token_count` event in the
rollouts carries a snapshot of the account limits, and it shows: over ten
weeks from July to September the weekly window came up to 99% thirteen times
and hit 100% eleven times, and the "You've hit your usage limit" error
appears on 28 calendar days. From the start of a window to 99% took a median
of 25 hours, the fastest case 7 hours, the slowest 93. The five-hour window
ran out twice over the same period; it was almost always the weekly one that
hit. At the 83 to 188 million input tokens per hour that waiting costs in the
sessions below, a day yields two to four billion. Hence "in a day" in the
title: that's the median.

Here is one of the goal sessions turn by turn. Blue turns were started by a
human or by the orchestrator itself, orange ones by goal mode.

<a href="/blog/codex-goal-token-burn/session-a-timeline-en-light.png"><picture>
<source srcset="/blog/codex-goal-token-burn/session-a-timeline-en-dark.png" media="(prefers-color-scheme: dark)">
<img src="/blog/codex-goal-token-burn/session-a-timeline-en-light.png" alt="Session A: input tokens per turn, goal continuations highlighted">
</picture></a>

The orange bars are hours of log polling. The tallest, 71 million tokens, is a
single three-hour turn with 439 tool calls, mostly `tail` on the child
processes' logs. On the right, four nearly invisible orange bars are empty
continuations within 20 seconds.

The main number: what one hour of waiting costs at comparable context.

<a href="/blog/codex-goal-token-burn/waiting-cost-per-hour-en-light.png"><picture>
<source srcset="/blog/codex-goal-token-burn/waiting-cost-per-hour-en-dark.png" media="(prefers-color-scheme: dark)">
<img src="/blog/codex-goal-token-burn/waiting-cost-per-hour-en-light.png" alt="Cost of an hour of waiting: from 0.5 million with a notification to 188 million in a goal loop without sleep">
</picture></a>

Session A waited 7.8 hours and spent 650 million input tokens on it, 271
steps per hour. Session B waited 92 hours and spent 1.85 billion, 43 steps
per hour, with the model running `sleep 30` through the shell 61 times. The
source session made 466 calls in 48 minutes of goal loop, 590 per hour, and
spent 149 million. The top bar is an estimate for the same context with a
notification: one or two steps per event.

Between them lies a measured case with `sleep`. The archive has two goal
sessions on `gpt-6-astra`, the one model that gets the tool. The model used
it, 60 and 129 times, sleeping 45 seconds per call. An hour of waiting cost
it 10 to 15 million input tokens at 55 to 100 calls. That's 6 to 18 times
cheaper than the spin, and still 20 to 30 times more expensive than a
notification: goal mode kept restarting it after every turn, 600 and 443
times per session, and it didn't sleep for long. Sleep lowers the price of
the loop but doesn't remove the loop.

One more detail from the data. Qwen 3.6 through a local llama.cpp showed the
same pattern: 21 of the 22 turns in its goal session were pure polling. The
pause tool is gated by the model catalog, the provider has nothing to do with
it, and it isn't limited to one muse model.

## What to do about it

On the Codex side it's a few small changes, and each has a ready-made example
in the neighboring product.

- Register `clock.sleep` whenever the thread has an active goal, regardless
  of the model catalog. Weaker but also workable: make `always_on` the
  default when goals are enabled.
- Add a delay between continuations when the previous goal turn was a waiting
  turn or an empty one. Claude Code does it at 30 minutes with a doubling
  interval and a cap of three automatic check-ins, and stops the loop after
  several turns without tools. Right now `continue_if_idle` starts the turn
  at once.
- Accept `60000.0` where `60000` is expected. Models on custom providers
  write numbers that way, and because of it not one waiting tool works for
  them.
- One line in `continuation.md`: name `clock.sleep` and a long `write_stdin`
  as acceptable forms of a verified wait, otherwise even a model with the
  tool will go poll the shell.

### How to check your own sessions

Every table in this text can be reproduced on your own rollouts with one
script: [codex-rollout-audit](https://github.com/relux-works/codex-rollout-audit),
a single Python file with no dependencies. It reads `~/.codex/sessions`,
sends nothing anywhere, and prints the per-session summary, the limit
exhaustion episodes, a per-turn view of one session and the count of
rejected float arguments.

### How to turn sleep on for yourself

The flag lives in `~/.codex/config.toml`:

```toml
[features]
sleep_tool = { mode = "always_on" }
```

The key is described in
[`feature_configs.rs`](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/features/src/feature_configs.rs);
the `always_on` mode registers the tool regardless of the model catalog. After
a Codex restart `clock.sleep` is in the tool set for any model. The easiest
check is to ask the model to sleep five seconds via `clock.sleep` and see
whether the call shows up in the response. Three caveats. On `gpt-6-astra`
nothing needs enabling: it declares `clock` in the catalog, and in the default
mode the tool registers itself. For the other models the flag only adds the
tool to the set. The model wasn't taught to use it sensibly: it may keep
polling the shell or fall asleep instead of working. For models on custom
providers that write `60000.0` instead of `60000`, the tool won't work until
number serialization is fixed.

At home we turned `sleep` on through the config, we're teaching the
orchestrator to wait for all its child processes with a single call, and we
put a budget on every goal. The formula is the same: number of checks times
size of context. Until the model is given a way to wait without spending a
step, the one who waits is the one who pays.
