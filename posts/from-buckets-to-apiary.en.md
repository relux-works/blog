---
title: "From Carrying Buckets to an Apiary: How We Build Agent Systems"
description: "How we went from copying code between a chat and an editor to orchestrators that work across every agent environment and belong to no vendor, processes described as configuration, many people and machines on one project, and next a swarm of outside agents around one shared environment."
slug: "from-buckets-to-apiary"
lang: "en"
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
  - "Claude Opus 5.5"
draft: true
---

These days the fashionable move is to quit IT and start a farm. We started one too, right inside IT: this post is how we went from carrying buckets of code between a chat and an editor to keeping an apiary of agents.

Our own projects show where the old way breaks. Orchestrators block each other on one trunk, validation suites queue behind each other on one machine, and every model vendor lives in its own tab, so a person spends the day carrying context between them. Most tools are built around one person driving one agent from one vendor, and that shape stops working once a project needs many agents, several vendors and more than one operator.

This post answers one question: what does it take to put many agents, several vendors and several people on one project while keeping quality, cost and trust under control? It follows the path in epochs: chatbots, orchestrators inside one vendor, orchestrators across vendors' environments, orchestrators that belong to no vendor, the Apiary, and one more step after it. Each chapter opens with the problem its epoch ran into and closes with the piece of our system that solves it.

It covers the design we settled between 17 and 28 September 2026. The specifications behind it are merged as drafts and not frozen, much of what follows is not built yet, and the vision runs well ahead of the first working version. Every non-obvious claim links to its source, and when this post disagrees with our [decisions page](https://github.com/relux-works/wiki/blob/main/decisions.md) or [roadmap](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md), those win.

## TL;DR

- **One orchestrator, any agent environment.** An orchestrator starts sub-agents in Claude Code, Codex, Muse, agy, Pi or Qwen with the same role instructions, and every one of them gets its own goal.
- **No vendor at the core.** Contexts come from Curator profiles, every launch is built in one place, and a session host keeps any harness alive behind one contract. A person keeps the harness and the subscription they already pay for and can switch without losing processes, boards or memory.
- **Quality and cost are engineered.** A producer-reviewer cycle across model families raises quality; routing, local engines and network profiles put each task on the cheapest model that is good enough.
- **Processes are configuration.** A project declares its roles, element types and workflows in `Playbook.json`. The same machinery runs software delivery, a café and a family calendar.
- **The Apiary.** On each machine the Keeper runs many processes, each with its own board and root orchestrator. Orchestrators across machines and people coordinate through waggle, a protocol of signed messages, and trust rests on keys that need a person present.
- **One more thing: a swarm.** Untrusted outside agents join a pool around one shared environment, receive work over a one-way channel, and pass reviewers from different model families and owners.

## 1. Chatbots and carrying buckets

**Carrying buckets.** We started by pasting code into a chat window and carrying the answer back: copy the snippet, paste it into the editor, build, carry the compiler error back, repeat. The model saw only what we remembered to paste.

**Scripts.** Next came scripts that collected the right files as context, sent them, and applied what came back. That was faster, but every step of the loop was still ours.

**Agents.** Then agents learned to run the loop themselves: open files, edit them, compile, run the tests, read the failures, try again. For a while it felt like the problem was solved.

**Traffic jams.** Then the agents got stuck, like cars in a traffic jam. They dug into details, lost the thread and came back to the same wall. People wrapped them in patches: Ralph loops that restart the agent until the work is done, and goals that keep it working toward one objective. It still failed often, because a project mixes many classes of task. Architecture, a boilerplate edit and a security review need different models, and one agent on one model does all of them. Worse, it grades its own work, and a model that wrote the code is the worst-placed model to find what is wrong with it.

## 2. Orchestrators inside one vendor

**The problem.** One agent cannot hold a whole project, and nobody checks its work.

The answer of this epoch is an orchestrator: an agent that splits the work, starts sub-agents for parts of it and checks what they return. Vendors built this into their own environments, so Codex spawns Codex, Claude spawns Claude, and some environments cannot spawn at all, so everything runs in one stream.

Our orchestration system of this epoch is **task-board**. Its board is a set of files in the repository: a hierarchy of Epics, Stories and Tasks or Bugs, with dependencies that escalate across parents and a planner that sorts the graph. Every child agent is spawned for a **role** with an explicit model and effort, and tracked as a run.

Delivery follows one cycle ([Change Request lifecycle](https://github.com/relux-works/skill-project-management/blob/main/references/change-request-lifecycle.md), [tracked background spawn](https://github.com/relux-works/skill-project-management/blob/main/references/tracked-background-spawn.md)):
- a **producer** works in the Story's own worktree and publishes a Change Request;
- the configured validation suite runs against exactly that candidate ([validation binding](https://github.com/relux-works/skill-project-management/blob/main/.specs/validation-binding.md));
- a **reviewer**, typically a model from another vendor, accepts it or sends it back to rework;
- the orchestrator integrates the Story, and the signed result reaches the trunk through a reviewed pull request.

An independent reviewer catches what the producer did not see, and a second model family catches what the first one systematically misses.

**Goals per agent.** Claude and Codex each implement goals inside their own environment. That helps one agent, but an orchestrator needs more: every spawned agent with its own goal, the orchestrator with its own higher goal, and goals that change as the work reveals milestones. An agent can never finish a goal like "make it nice and working". task-board keeps a primary goal for the orchestrator and a separate goal for every spawned run, each with revisions, so the orchestrator can move a child's target mid-flight ([Claude goal runtime](https://github.com/relux-works/skill-project-management/blob/main/docs/claude-goal-runtime.md), [Codex goal runtime](https://github.com/relux-works/skill-project-management/blob/main/docs/codex-goal-runtime.md)). Our experience adds one rule: an orchestrator given a very large goal starts mixing tasks and digging into details, so it should cut long objectives into milestones, and the weaker its model, the closer together those milestones must be ([call digest](https://github.com/relux-works/wiki/blob/main/research/call-digest-2026-09-24.md)).

This board has been built this way for hundreds of hours, by its own orchestrators, with little human intervention. It stays in maintenance now: fixes and validation throughput go in, and everything new ships as modules that plug into it ([roadmap §5b](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#5b-the-current-board-modules-and-forks)).

The limit of this epoch is the vendor. Every orchestrator spawns only its own kind.

## 3. Orchestrators across harnesses

**The problem.** Say we want a security review of one change from three angles at once: the strongest Codex model, the strongest Claude model, and a local or uncensored model that is willing to attack the code for real. Inside one vendor that means three tabs, three environments, and a person carrying the diff and the findings between them. None of the environments knows the other two exist.

As the saying goes, every problem in computer science can be solved by adding another layer of indirection. Ours lets one orchestrator, in whatever environment it runs, start sub-agents in any other one with the same instructions, so that even a local Qwen can orchestrate top Claude and Codex models. Which model does the work becomes a matter of role and policy. task-board already spawns tracked children in Claude and Codex this way; the rest of this chapter is about making every harness equal.

**Goals in every harness.** Delivering a goal into a harness, confirming it took the exact revision and typing a notice into a live session exist only in task-board's Claude and Codex hosts, and each new harness would add thousands of lines to task-board ([goal-host synthesis](https://github.com/relux-works/wiki/blob/main/research/goal-host-plane-synthesis.md)). The harnesses differ a lot ([Muse](https://github.com/relux-works/wiki/blob/main/research/muse-code-cli.md), [agy](https://github.com/relux-works/wiki/blob/main/research/agy-cli.md)):

| Harness | Control channel | Proof the goal revision took | Hosting |
| --- | --- | --- | --- |
| Claude | terminal (PTY) | reading the rendered terminal | PTY |
| Codex | app-server API | API response | app-server |
| Muse 1.3 | `muse serve` (JSON-RPC with a native goal API) | `goalChanged` event | owner through `serve`; a person's session through a PTY |
| agy 1.2.9 | headless stream-json and hooks | our own `Stop` hook call | headless owner with the hook; PTY for a person |
| Pi, Qwen (planned) | an extension over a private socket | extension digest acknowledgement | PTY plus extension |

So the goal logic moves into a module of its own, the session host (next chapter), with one contract per harness: start or resume a session; apply, change or clear a goal; acknowledge the exact goal revision; inject a notice into the running session; emit goal and usage events. task-board keeps only the goal ledger and the routing of goals to owners. Token budgets are enforced by the host for every harness: accounting always, a wrap-up notice at 90% and a pause with a message to the orchestrator at 100%. Only Codex takes a budget natively.

**Back to the security review.** With the layer in place, one orchestrator spawns three reviewers into three environments with the same role instructions. Each reports back to the same board. Nobody carries a diff between tabs.

Once goals work on every harness, orchestrators themselves can spread across harnesses, subscriptions and limits. That is **sharding**, and it needs orchestrators that know about each other (chapter 5).

## 4. Orchestrators that belong to no vendor

**The problem.** Crossing harnesses is not enough if every piece still assumes one vendor. Each harness reads the machine's global configuration, so a child agent sees skills and MCP servers it should never see. Each tool that starts an agent spells the harness flags itself, and the copies drift. Committed configuration names concrete model ids, so a teammate with other subscriptions gets a broken project. And the orchestrator's session dies with the daemon that holds it.

The answer is to abstract everything that belongs to a vendor behind our own contracts. This chapter goes plane by plane.

| Plane | Answers | Module | Status |
| --- | --- | --- | --- |
| Context | what an agent receives | [Curator](https://github.com/relux-works/curator) | release candidates |
| Launch | how intent becomes argv and environment | [agents-management](https://github.com/relux-works/skill-agents-management) module; [curator-agent-launcher](https://github.com/relux-works/curator-agent-launcher) (`curator run`); `task-board spawn` | module in use; launcher tagged v0.1.0 |
| Sessions | who keeps a live session: goals in, events out | [agent-session-host](https://github.com/relux-works/agent-session-host/blob/main/spec/session-host.md); tb-sessiond today | draft v0.3; extraction first |
| Selection | which model a role gets, and whether it is available | [curator-model-router](https://github.com/relux-works/curator-model-router); an availability aggregator in agents-management | drafts |
| Inference | which local engines are up | [curator-inference-manager](https://github.com/relux-works/curator-inference-manager) | draft |
| Network | which egress a launch uses | [curator-network-profiles](https://github.com/relux-works/curator-network-profiles) | draft |

### 4.1 Context: a Curator profile per agent

Curator resolves a profile (root instructions, skills, MCP servers) into a **managed home**. That is a per-profile configuration directory, like `~/.claude` or `~/.codex`, that holds only that profile's context. An agent launched there sees exactly that context and nothing the machine has globally ([roadmap §8.2](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#82-why-launches-are-built-in-one-place)). Managed homes exist today for Claude Code, Codex, OpenCode and Pi; Muse has no adapter yet.

Since 25 September every run launches with the Curator profile of its **role**, so a reviewer's skills live only in the reviewer's home and never in a project folder where an orchestrator could pick them up and start acting as a reviewer ([keeper §13.5](https://github.com/relux-works/curator-keeper/blob/main/spec/keeper.md#135-role-profiles-instead-of-project-folders-decided-2026-09-25)). Which profile a role uses is the operator's choice, recorded in the operator's own `~/.curator/models.toml`.

### 4.2 Launch: one construction site

The **agents-management module** holds the model registry, one plugin per harness (binary, argv grammar, environment contract, stdin transport) and the provider limit plane. It produces plan values and deliberately starts no process ([architecture](https://github.com/relux-works/skill-agents-management/blob/main/docs/architecture.md)).

**Decision 0019 (proposed): one construction site.** Several processes may read the Curator profile's launch fragment, but the context channels (MCP configuration, system prompt, home variable) and the harness argv are spelled in exactly one place: the module ([0019](https://github.com/relux-works/curator-spec/blob/main/decisions/0019-fragment-consumers-and-one-construction-site.md)). The reason is concrete. If the launcher, task-board and the session host each spell `claude … --mcp-config <file> --strict-mcp-config`, the copies drift, and a single forgotten `--strict-mcp-config` lets the machine's own MCP servers leak into a child.

**Runtime bindings.** A runtime binding has two halves ([LP D1](https://github.com/relux-works/skill-project-management/blob/main/.specs/drafts/launch-profiles.md#d1-object-runtime-binding-two-halves-no-profile-word) to [D3](https://github.com/relux-works/skill-project-management/blob/main/.specs/drafts/launch-profiles.md#d3-profile-transport-per-harness-under-managed-homes)): a stable runtime id, and a private machine entry in `~/.curator/runtimes.toml` that binds the id to a transport, an endpoint, a credential source and possibly an engine. That lets Codex talk to a llama.cpp server without anyone committing a machine address.

**Three front doors.** On 27 September we adopted one shape for every command line ([decision](https://github.com/relux-works/wiki/blob/main/decisions.md#2026-09-27-the-command-line-shape), [review](https://github.com/relux-works/wiki/blob/main/research/cli-shaping-review.md)):
- `keeper` serves the person in an apiary (chapter 5);
- `curator` installs and configures the machine, and dispatches a noun it does not know to a provider named `curator-<noun>`: `curator run`, `curator session`, `curator models`, `curator runtimes`, `curator engines`, `curator network`, `curator playbook`;
- `task-board` is the kernel that agents, the session host, the timer and `keeper` call.

One verb keeps one meaning across all three, `--profile` always means the Curator profile, and each operator file holds one noun: `~/.curator/{models,runtimes,engines,network}.toml`. A person enters a session through `curator run claude|codex` ([Decision 0021, proposed](https://github.com/relux-works/curator-spec/blob/main/decisions/0021-sessions-enter-through-curator-run.md)), and tracked, non-interactive children still start through `task-board spawn`.

### 4.3 Sessions: the session host

A long-lived orchestrator needs something to keep it running when nobody is looking. Today that is `tb-sessiond`, the session daemon inside task-board. It is fused into task-board, holds Claude sessions in its own address space, and serves one board's primary session and that board's runs. Restarting it to upgrade kills every Claude session it hosts ([session host §2.7](https://github.com/relux-works/agent-session-host/blob/main/spec/session-host.md#27-restart)).

The plan for the **session host** module ([specification](https://github.com/relux-works/agent-session-host/blob/main/spec/session-host.md)) runs in a fixed order:
1. **Extract it as it is.** The provider-host plane moves into its own repository behind the contract of chapter 3, with byte-identical goldens and no change in behaviour ([§3](https://github.com/relux-works/agent-session-host/blob/main/spec/session-host.md#3-phase-1-extract-the-module-as-it-is-decided-2026-09-24-priority)).
2. **Close access to it.** Today one bearer token, which any process of the operator's user can read, controls every session. The first refactor gives every session its own capability token that names what it may act on: itself and the sessions it spawned ([§6.2](https://github.com/relux-works/agent-session-host/blob/main/spec/session-host.md#62-capability-tokens)).
3. **Deliver into sessions nobody watches.** Every message goes in one of three doorbell modes: `next_turn` by default, `steer` into the running turn where the harness can take it, and `interrupt` only for halt, park and the emergency stop ([§7](https://github.com/relux-works/agent-session-host/blob/main/spec/session-host.md#7-doorbell-delivery-modes-proposed)).
4. **Survive upgrades.** One host per machine with a small terminal holder per session, so the host can restart without hanging up anyone.

**Park and the emergency stop.** Park is the orderly stop: the orchestrator writes a park note, the note is bound into its board goal, and the next start reads it first ([§8](https://github.com/relux-works/agent-session-host/blob/main/spec/session-host.md#8-park-decided-2026-09-24-the-mechanics-proposed)). The emergency stop is a separate command nobody runs by accident: `keeper estop` asks for a typed phrase and the operator's presence, has the kernel snapshot every board, then stops every run and session so that they can resume ([§9](https://github.com/relux-works/agent-session-host/blob/main/spec/session-host.md#9-emergency-stop-proposed)). The person types `keeper park` and `keeper estop`; underneath they are the host's `curator session park` and `curator session estop`, and no kernel command stops a session.

### 4.4 Selection: routing, availability and the token bill

**The problem.** You pick one strong model for a project, and most of the tasks it does are low-class work: a rename, a boilerplate test, a documentation fix. They still burn expensive tokens.

The **router** is a separate, inspectable step of launch preparation that never sits between an agent and a model API. It asks four questions, each with its own owner ([R2](https://github.com/relux-works/curator-model-router/blob/main/spec/model-routing.md#r2-four-questions-four-owners)):
- **Allowed?** The operator's and the project's policy answer.
- **Compatible?** The module registry and the catalog answer.
- **Fit for the work?** The router's estimator answers, from the task's requirements and evidence such as benchmarks and our own outcomes ([R4](https://github.com/relux-works/curator-model-router/blob/main/spec/model-routing.md#r4-evidence)).
- **Available now?** One per-profile availability view in agents-management answers: provider limits, engine state and the login inside the managed home. A failed read never counts as headroom.

A good score never overrides the other three answers. The router runs in one of four modes: `off`, `shadow` (record the decision, change nothing), `recommend` and `select` ([R7](https://github.com/relux-works/curator-model-router/blob/main/spec/model-routing.md#r7-modes-defaults-manual-choice)). In time, a very fast classifier can read a task's specification and pick the model, knowing benchmarks, limits and what is available.

**Local models.** `curator-inference-manager` owns local engines and gives them leases, so an engine is never drained while a launch uses it. An engine is `ready` when it serves, and `ensurable` when its weights are present and the machine would admit it, so a cold engine stays selectable at a start cost ([§5](https://github.com/relux-works/curator-inference-manager/blob/main/spec/inference-plane.md#5-availability-facts)).

Put together, a trivial task can land on a local model at night and a hard one on a frontier model, and neither choice is made by a person switching tabs. We do not assume we will always run the strongest model: strong models are expensive, and a deterministic process around a small model makes it productive (chapter 5).

### 4.5 Network profiles: several subscriptions on one machine

**The problem.** Every agent on a machine leaves through the same network path, so two launches cannot use two accounts through two egresses side by side.

A launch has five independent settings: the Curator profile, the credential selection, the runtime binding, the **network profile** and the execution profile ([N1](https://github.com/relux-works/curator-network-profiles/blob/main/spec/network-profiles.md#n1-five-independent-launch-settings)). The network profile decides which application proxy the supported connections of that one launch go through. This is cooperative proxy routing for supported clients, not process isolation, so we avoid calling it a sandbox. It is a library that starts no process: the launcher, task-board's spawn and the session host apply its patch just before they start the harness ([N2](https://github.com/relux-works/curator-network-profiles/blob/main/spec/network-profiles.md#n2-one-library-three-process-owners)). That is the proxy capability of the launcher.

### 4.6 The Keeper: an entry point with no loop of its own

With every plane abstracted, the top of the stack does not need an agent loop of its own. The **Keeper**, the always-on main loop of a machine (chapter 5), runs on the existing harnesses: Claude Code, Codex, Muse or a harness bound to a local engine. Our own agent loop is postponed; it may later serve a cheaper always-on front, restricted workers or native sub-agent completion, and none of that is needed now ([keeper §7.7](https://github.com/relux-works/curator-keeper/blob/main/spec/keeper.md#77-our-own-loop-later-decided-2026-09-28), decided 28 September).

Being abstract over the harness is the core advantage. A person keeps the harness and the subscription they already pay for, and can switch harness without losing processes, boards or memory. Large vendors ship always-on personal assistants in the OpenClaw style. They have no profiles and no flows, so they cannot be given software development. Ours gives profiles, flows, any harness, the subscriptions people already have, and a minimal install ([call digest](https://github.com/relux-works/wiki/blob/main/research/call-digest-2026-09-keeper-concept.md)).

## 5. The Apiary

**The problem.** Everything so far serves one project on one machine. A person has more than one domain of work, a project outgrows one person, and the process itself, meaning the element types, statuses, roles and the producer-reviewer loop, is Go code inside task-board. A team with a different process has to fork the code, and a process that is not development at all, such as a café's purchasing, cannot use the machine at any price.

The **Apiary** is the whole system. Its names are for people; specifications and code use technical terms ([naming](https://github.com/relux-works/wiki/blob/main/naming.md)):

| Name | Technical term | What it is |
| --- | --- | --- |
| Apiary | the whole system | every machine and process of one owner; one machine is a small apiary |
| Yard | node | one machine |
| Keeper | main loop | the always-on loop of a node: schedule, inbox, classifier, conversation with the person; it wakes the orchestrator of the right process |
| Hive | process | one domain, such as a family calendar, a café or the development of a project, with its own directory, board, playbook and root orchestrator |
| Queen | root orchestrator | the single orchestrator of a process that is started from outside it |
| Comb | board | the process's board; its cells are the tasks |
| Bee | run | one agent run |
| Wild bees | external participants | agents of other owners working on part of a process under leases and signatures |
| Nuc | process package | a published playbook from which a new process starts |
| Waggle | messaging protocol | signed messages and coordination between agents |

Beekeeping words appear only where people type them: the `keeper` command and its nouns (`keeper hive …`), the apiary's directories and the profile name `apiary`. "Hive" and "swarm" are crowded words in software (Apache Hive, Docker Swarm), so the names live under the brand. "Swarm" is not a technical term at all; in this post it names the vision of chapter 6.

### 5.1 Processes as configuration

The answer to a hard-coded process is **process configuration**, drafted in [curator-playbook](https://github.com/relux-works/curator-playbook) and merged as DRAFT v4.8, the freeze candidate. The vision: any process becomes configuration run by agents, with humans and tools owning the steps that need them, whether it is software delivery, a café's purchasing, a patent pipeline or a family calendar.

**Two files, two jobs** ([§2.1](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#21-the-projects-files-decided)). `Skillfile.json` says what is installed; Curator reads it. `Playbook.json` says how the project works; the board reads it, and it carries role aliases, entity types, workflows and policy. They meet only through skill names. The format is JSON with a published schema and an optional `ui` block the kernel ignores, so a visual constructor can later draw and edit the process.

**Owners.** Every state has exactly one owner and optional helpers ([§4.2](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#42-owner-kinds-and-who-may-move-work-decided)).

| Owner kind | Who does the work | Example |
| --- | --- | --- |
| `agent` | an agent running a role skill | developer, reviewer, refuter |
| `human` | a person or a group | approving a purchase, confirming a delivery |
| `tool` | a command exported by a skill that Curator installed and audited | a CI check, the Lean kernel, a payment gateway client |
| `process` | another process | handing a proven finding to the process that fixes it |

Change Requests, worktrees, integration and validation are development-specific, so they move into a **delivery module** that contributes guards such as `delivery.cr-published` and `delivery.cr-accepted` ([§6.3](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#63-guards-actions-and-events-come-from-modules-decided)). A café never loads it. Machine checks come from named **check sets** that run locally, on the project's CI, or both ([§6.12](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#612-check-sets-decided-2026-09-24)).

**Composition.** A project **extends** one published playbook and writes only its differences ([§7.1](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#71-extends-only-the-differences-decided)):

```json
{
  "extends": "dev-cycle",
  "roles": { "developer": { "skill": "role-ios-developer" },
             "tester":    { "skill": "role-ios-tester" } },
  "workflows": { "dev": {
    "states": { "qa": { "owner": "tester" } },
    "transitions": [ { "from": "review", "to": "qa" }, { "from": "qa", "to": "done" } ] } }
}
```

That iOS project swaps the developer and adds QA before `done`; when dev-cycle publishes a new version, everything else updates. A project can also **use** several playbooks and bind their **slots**, abstract types a playbook leaves open ([§7.2](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#72-uses-and-slots-composition-decided)). Scrum does not say how a task is done; it says how work is selected and timeboxed. So `{"uses": ["dev-cycle", "scrum"]}` plus binding scrum's `work-item` to dev-cycle's `story` puts dev-cycle's stories into scrum's sprints. Numbers a team chooses are **parameters**: a loop limit can be set down to unbounded, because a real case of ours needed thirty legitimate rounds of rework ([§7.3](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#73-parameters-the-operators-direction-2026-09-25-the-form-is-proposed)).

**Roles are skills; a playbook is a collection of skills** ([§8](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#8-distribution-roles-are-skills-decided)). A published playbook such as `curator-playbook-dev-cycle` holds the orchestrator skill, whose data carries the process template, and one skill per role. One Skillfile selector installs them all, and each role's skill reaches only that role's runs through its Curator profile.

**Needs, not models** ([§9](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#9-model-needs-and-unmet-needs-decided)). A role states `require` and `prefer` in terms of publisher, family, capability, locality or `not_same_publisher_as`, and never names a model id or a reasoning effort. Each operator's private `~/.curator/models.toml` binds concrete models, from specific to general:

```toml
[bindings]
"dev-cycle/developer" = { run = "codex/gpt-6-luna", effort = "high..max" }
"*/refuter"           = { run = ["claude/claude-opus-5-5", "codex/gpt-6-sol"], effort = "high" }
"@reviewer"           = { run = "claude/claude-opus-5-5", effort = "medium" }
```

Without the file nothing fails: the resolver picks the best admitted model that meets the role's needs among the harnesses that are installed and logged in, never picks pay-per-token billing on its own, and says what it picked and why. When a requirement cannot be met, `on_unmet` decides: `block` (the default), `fallback` to an ordered list, `ask` the operator for a scoped, expiring approval, or `degrade` to the best available with an extra review.

**Validation and the refuter.** `curator playbook check` catches a workflow that can never finish, a role bound to a skill that is not installed or a guard no owner can satisfy, before anything runs ([§10](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#10-static-validation-decided)). A **refuter** role then tries to refute a draft by contradiction: it assumes the draft is implemented as written, derives the consequences and compares them with the recorded decisions, the board's memory ([§12](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#12-the-refuter-role-and-decision-memory)). Its first run on this very specification returned 36 findings, three of them blocking; for example, an agent could act for a human owner, because nothing authenticated who fired a transition. The draft has since gone through seven refuter runs, each answered ([reviews](https://github.com/relux-works/curator-playbook/tree/main/reviews)).

**Which changes wait for a person** ([§2.4](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#24-which-version-is-in-force-decided-2026-09-24-h1-revised-in-v40-and-v41)). The kernel runs the committed version of the process that took effect, never the working tree, so an orchestrator cannot quietly edit its own rules.
- A process asks a person once for a **capability**, one kind of change, the way a phone app asks for a permission; the person answers always, once or no. Changes a capability covers, such as preferences, estimates or schedules within limits, take effect on commit.
- Everything else, meaning workflow structure and anything that carries authority, waits for a person's touch, and one touch confirms every pending change in a batch.
- An explicit, loud **yolo mode**, optionally for a period such as 24 hours, trusts every change on a board that nobody else shares and where no delegation covers money.

**Dreams** (proposed). A process can be rehearsed in a dream: every tool runs with `--dream` against a copy of the board, nothing reaches the real world, the agent knows it is dreaming, and nothing recorded in a dream counts as real evidence ([§6.13](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#613-dream-mode-proposed-2026-09-25)). At night a dream also replays the day's sessions and consolidates memory.

**Today's board is itself a playbook** ([§14](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#14-todays-task-board-as-a-playbook)): `default.playbook.json` maps the current kernel line by line, and PC1 loads it with identical behaviour. The generality tests run seven demo playbooks, each starting from a poorly specified request, from dev-cycle and bug-hunt to café operations, a patent pipeline and a process modelled on [prove2.me](https://prove2.me/), where a `checking` state is owned by the Lean kernel as a tool. A demo outside software we want to show next: a residence permit in Georgia, with its documents, services and appointments.

### Interlude: one project, end to end

Two operators, A and B, work on one project. A uses Claude and Codex subscriptions; B uses Codex and a local model on a laptop.

1. **The committed files.**
   - `Skillfile.json` has two collection selectors, for `curator-playbook-dev-cycle` and `curator-playbook-bug-hunt`.
   - `Playbook.json` says `"uses": ["dev-cycle", "bug-hunt"]`, binds bug-hunt's slot `fix-target` to dev-cycle's `dev-task`, and gives the reviewer the need `not_same_publisher_as: developer` with `on_unmet: ask`.
   - Neither file names a model, a machine or an endpoint.
2. **The private files.** A's `models.toml` binds producers to Codex and reviewers to Claude. B's binds producers to a local engine, which B's `runtimes.toml` and `engines.toml` describe. `curator playbook check` passes on both machines.
3. **Hosted sessions.** Each operator runs `curator run codex` in the project, and the session host keeps each session from birth: resume, notices, the board goal and a doorbell. A third orchestrator on another harness can join later; that is sharding.
4. **Scopes.** A's orchestrator leases Epic Auth, and B's leases Epic Billing. When A's orchestrator tries to spawn on a Billing story, the kernel refuses (`scope_owned_by`), and the orchestrators negotiate a hand-off with waggle `coord` messages.
5. **A finding flows into delivery.**
   - bug-hunt proves a finding, and its `handoff` action creates a `dev-task` in dev-cycle.
   - B's developer runs on the local engine: curator-inference-manager `ensure`s it, and the network profile of that launch applies.
   - At `review`, the reviewer's need for another publisher fails on B's machine. `ask` fires, and B approves "same-publisher review for this epic, 30 days" once.
6. **A spec is refuted.** The fix needs a small specification. Its `challenge` state finds that the draft proposes plain release tags while a recorded decision says `vX.Y.Z`, and sends it back to `draft` with the pair quoted.
7. **A halt needs a human.** A's orchestrator sees B's worker about to integrate onto a broken base. Its lease does not cover that worker, so the policy requires an operator's approval with a key that proves presence. A reads the rendered message and touches a hardware key; B's host verifies both signatures before the supervisor halts the worker ([waggle §6](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#6-example-of-multi-signature-in-use)).
8. **Same machinery, different business.** On a third machine a café runs `cafe.playbook.json` on the same kernel: a manager approves each purchase order, the order goes to the supplier's portal through a tool, a missing confirmation escalates after 15 minutes, delivered orders are handed to bookkeeping, and a weekly schedule creates the inventory check ([example](https://github.com/relux-works/curator-playbook/blob/main/examples/cafe/cafe.playbook.json)). Nothing in the kernel knows what a café is.

### 5.2 The Keeper: many hives on one machine

**The problem.** Always-on assistants put one agent loop on a schedule and ask it to do everything. Its memory clogs, it tries to do everything at once and finishes little, and it needs an expensive subscription to run at all.

The Keeper does no process work itself ([specification](https://github.com/relux-works/curator-keeper/blob/main/spec/keeper.md), DRAFT v0.5.1). It keeps a registry of the machine's processes, each a separate repository with its own playbook, board and exactly one root orchestrator, and it routes each request a person makes to the right one. "Move Saturday's dentist to 11 and order oat milk" is split in two: the first half wakes the calendar's queen, the second starts the café's, and a purchase above the café's delegated limit waits for the person's approval on the phone.

- **`keeper up`** brings a machine up at login or after a reboot: the session host, the Keeper's own session and every hive's queen, each through `curator run <runtime> --profile <role profile>` and resumed from its goal and park note ([§7.3](https://github.com/relux-works/curator-keeper/blob/main/spec/keeper.md#73-what-keeper-up-runs-the-launch-nesting-proposed)).
- **Routing** follows a fixed order: an explicit reference wins, then a channel bound to a process, then one confident candidate; close candidates get one short question whose answer becomes a visible routing hint; no candidate leads to the process designer ([§8.2](https://github.com/relux-works/curator-keeper/blob/main/spec/keeper.md#82-order)).
- **The process designer** writes a playbook for a new request, such as "keep the family calendar", starting from the simplest process that works, rehearses it in a dream and sets the process up once the person confirms ([§9](https://github.com/relux-works/curator-keeper/blob/main/spec/keeper.md#9-the-life-of-processes-outline-decided-2026-09-24-details-proposed)).
- **The person** talks to the Keeper in the terminal first. Messengers such as Telegram come in KP2, the second milestone; approvals go through a companion app on the phone or the machine's own user authentication.

Several queens run under one Keeper as long as their work does not overlap. One install brings the system up: Curator installs the `apiary` profile, and `keeper init` creates the person's own apiary repository with no upstream to us ([§6](https://github.com/relux-works/curator-keeper/blob/main/spec/keeper.md#6-installation-from-zero)).

### 5.3 Orchestrators talking: waggle

**The problem.** Two orchestrators on one project block each other, redo each other's work and race to land on the same trunk. Nothing carries messages between them, and nothing is signed ([waggle §1](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#1-what-exists-summary)). We want them to agree among themselves, with no person managing each one.

waggle has two layers ([§2](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#2-two-layers)). **Communication** answers "who said what to whom, who approved it, and did it arrive". **Coordination**, built on top, answers "who works on what, and how do we agree".

- **Envelope and signatures.** A message is the exact payload bytes plus one or more SSHSIG signatures, each with a role: `author`, `approver` or `endorser`. The roster is a stock OpenSSH `allowed_signers` file, so a stored message can be re-verified offline with `ssh-keygen` ([§4](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#4-where-signatures-live-and-how-they-are-checked)).
- **Classes and authority** ([§5](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#5-classes-and-authority)): `coord` between orchestrators, `cmd` from an orchestrator or operator to a worker, `report` from a worker, `receipt` from a host. A worker key cannot produce a valid `coord` or `cmd` over any transport.
- **Pluggable key hardware** ([§4.5](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#45-signer-providers-and-key-assurance)): `ssh-agent`, Apple Secure Enclave, FIDO keys, later TPM and PIV, with assurance levels from `software` to `attested`.
- **Providers are untrusted pipes** ([§9](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#9-providers)): a local directory, NATS JetStream, IRC, XMPP, Matrix, Slack, Telegram, email. Authority comes from signatures, the roster and the policy, never from the provider.
- **Delivery into sessions** is a doorbell plus a pull: a fixed-template doorbell rings through the session host, and the agent pulls the content as data with `task-board mail read` ([§10](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#10-delivery-into-agent-loops-doorbell-and-pull)).
- **Scope leases decide; messages negotiate** ([§12](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#12-scope-leases)). A lease names the orchestrator that owns part of a project, with a term and a token in a compare-and-set store, and the kernel checks it at spawn, integration and board commit.
- **Deciding together** follows honeybee quorum sensing: proposals, `support` and `objection`, then a `decide` record that carries the supporters' signatures ([§11](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#11-coordination-vocabulary-and-decisions)).
- **A protocol lab**, a disposable project on three machines with a deliberately primitive channel, lets agents invent their own coordination, and the vocabulary grows from what they actually do ([§13](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#13-protocol-lab)).

Locally first (milestone CM1: two orchestrators on one machine coordinate, each cancelling only its own children), then two operators over the internet through NATS on a dedicated machine of our private network (CM2).

### 5.4 Two operators on one module, and trust

When two people develop one module, each with a Keeper, the process keeps one board, and its queen lives on the machine that owns it ([keeper §4](https://github.com/relux-works/curator-keeper/blob/main/spec/keeper.md#4-several-nodes-proposed-architected-for-not-implemented)). On 28 September we added one accepting writer per board, or per collaboration, with **epoch fencing** ([decisions](https://github.com/relux-works/wiki/blob/main/decisions.md#2026-09-28-drafts-on-main-the-keepers-scope-two-operators-the-campaigns)):
- every typed operation carries the actor, the board, the configuration version, the scope and its lease epoch, the expected revision and an operation id;
- the epoch is checked at spawn, at the final mutation and at integration;
- a writer that loses its authority pauses new writes.

Whether that writer is assigned by ownership or elected among the nodes is still open. The patterns come from distributed databases: a lease with a term fences out a stale owner, and before another orchestrator inherits a role, the previous generation of assignments is revoked, otherwise the old orchestrator keeps acting once it wakes up ([Apiary §10.1](https://github.com/relux-works/curator-agent-runtime/blob/main/docs/drafts/apiary/minimal-roadmap.md#101-several-orchestrators-do-not-require-immediate-decentralization)).

**Trust** has its own specification, and its principles are simple ([decisions of 25 September](https://github.com/relux-works/wiki/blob/main/decisions.md#2026-09-25-names-the-trust-framework-and-the-split-draft-v40)):
- a person's acts are confirmed only with keys that need the person present, such as a hardware security key or a phone app whose key sits behind biometrics;
- the signing device renders what it signs, never a digest computed elsewhere;
- grants and confirmations are records on the board that every machine verifies;
- revoking a key, a grant or a tool takes effect at once;
- agents run under an operating-system account of their own, which is the real boundary; until then every check is a guardrail against well-behaved agents, not a wall against a hostile one;
- privileged operations, such as payments, deploys or the use of secrets, are requested by an agent and performed by a trusted executor after authorization.

## 6. One more thing: a swarm over one environment

**The problem.** Some projects need more than one person can bring. Two to five subscriptions are affordable; a hundred are not. A new operating-system kernel, written from scratch with the best patterns of decades of research, needs many people, many machines and a shared environment with virtual machines and compile capacity. It also needs trust, because not every participant will be honest.

Our answer is a **swarm**: many wild bees over one environment. The environment is one project, its board and its build capacity. Trusted orchestrators run it, and untrusted agent environments of other owners join and leave a pool around it dynamically ([call digest](https://github.com/relux-works/wiki/blob/main/research/call-digest-2026-09-keeper-concept.md)).

- **A one-way channel.** The orchestrator writes to a wild bee, and the wild bee cannot write back as an instruction, because its output may carry an injection. What it returns is work to review, read as data behind layered injection defense: authority outside the model, typed messages, inspectors and quarantine by default for external senders ([waggle §7](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#7-injection-defense-in-depth)).
- **Tools through our bridge.** Its tool calls can be routed through our bridge by the harnesses' own tool-override mechanisms, so its tools run on our side, under our rules, and the project's secrets never enter its environment.
- **Reviews as security.** A task passes several independent reviewers from different model families and different owners. If someone plants a vulnerability, the chance that at least one uncompromised reviewer catches it grows with every independent reviewer. The producer-reviewer cycle of chapter 2 becomes a security control.
- **The patterns of distributed databases.** Leases with terms and tokens, epochs that fence out a stale participant, and quorum records signed by the supporters keep many untrusted participants from corrupting one shared state.
- **Staged admission.** The trusted stage relies on roster changes a person confirms, operator keys and a private network; the external stage admits partners limited to `coord`, hosted accounts first and federation later ([waggle §15](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#15-security-stages)).

The Apiary design reaches this in stages, with a useful result at every one ([Apiary roadmap §10](https://github.com/relux-works/curator-agent-runtime/blob/main/docs/drafts/apiary/minimal-roadmap.md#10-staged-plan-with-a-useful-result-at-every-stage)):

| Stage | Adds |
| --- | --- |
| 0 | the local spawn path as the first backend of an agent host (one machine) |
| 1 | one remote executor: an agent on a second machine changes code on the first with its own credentials |
| 2 | a reliable trusted pool: durable mailbox, headless wake, reconnect, leases, queues, limits |
| 3 | restricted execution profiles with the same verifiable restrictions for local and remote agents |
| 4 | several orchestrators with scoped roles and messages between them |
| 5 | external participants: untrusted capacity under stricter admission |
| 6 | distributed autonomy: replicated state and automated role transfer |

People could lend spare subscription capacity at night to open-source projects that speak the protocol, the way they once lent spare processor time to volunteer computing. At that scale, tens of orchestrators and, in time, thousands of sub-agents work on one project. Today only a few can build systems like that. We want communities to be able to do it too, defence included, so that a new operating-system kernel from scratch becomes a community project and the balance does not tip toward those who already can.

## 7. Where we are and what's next

As of 28 September 2026, the specifications are merged on `main` as drafts, so every orchestrator reads one source; each is frozen later. Nothing of the Keeper, the Apiary or waggle is implemented yet. What runs today is Curator, `curator run`, the agents-management module, and task-board with its session daemon and `task-board spawn`.

| Module | Status |
| --- | --- |
| [waggle](https://github.com/relux-works/waggle/blob/main/spec/waggle.md) | draft v5.2 |
| [curator-playbook](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md) | draft v4.8, the freeze candidate |
| [curator-keeper](https://github.com/relux-works/curator-keeper/blob/main/spec/keeper.md) | draft v0.5.1 |
| [agent-session-host](https://github.com/relux-works/agent-session-host/blob/main/spec/session-host.md) | draft v0.3 |
| the trust specification | draft, private until review |
| [curator-model-router](https://github.com/relux-works/curator-model-router/blob/main/spec/model-routing.md), [curator-inference-manager](https://github.com/relux-works/curator-inference-manager/blob/main/spec/inference-plane.md), [curator-network-profiles](https://github.com/relux-works/curator-network-profiles/blob/main/spec/network-profiles.md) | drafts |
| task-board | in use, in maintenance |

### The order of work

From [roadmap §2b](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#2b-priority-order-decided-2026-09-24-amended-2026-09-28), amended on 28 September:

1. **The session host, and waggle CM1 on it.** It removes harness code from task-board, gives every harness goals and notices, and unblocks sharding.
2. **Process configuration PC0 and PC1**, the first demo playbooks and the refuter. PC1 proves the model on the real board.
3. **Leaving agents-infra**, our older infrastructure, in a campaign of two gates:
   - Gate A: nothing needs agents-infra any more, and every child runs in its role's Curator profile. Primary and goal-bound sessions use the same construction as children, so Gate A does not wait for `curator run` to hand sessions to the host.
   - Gate B: the first machine-local runtime binding, a Codex child on a local engine with a real tool round trip, plus moving the local-model broker into curator-inference-manager.
4. **CM2**, two operators over the internet; `curator run` hosted by the session host; PC2, role skills as packages.
5. **The rest of launch profiles (M4), then availability per profile (M5b)**; PC3 with the delivery module and real trust. M4 now comes before M5b, which needs it.
6. **Later:** network profiles, routing with evidence, the Keeper, Apiary distribution and formal-methods research, where each milestone gets the strongest machine-checkable acceptance available.

**The Keeper's first milestone, KP1, is terminal-only**: one machine on existing harnesses, the registry, routing, `keeper up` and supervision through the extracted session host. Channels come in KP2, and the minute timer that fires schedules comes with PC3.

**Muse goes first, narrowly.** Ahead of the host extraction we give Muse a curated child environment, a pinned version and an owner host over `muse serve`, not yet wired into task-board. Muse runs no producers until that curated environment is released and pinned.

### Forks and the old board server

Most large directions are cut as a module or behind a narrow seam, as waggle was. When a fork is needed, the fork owns the code and a checkout of upstream stays the board owner, so the board keeps one signed history ([separate-owner completion](https://github.com/relux-works/skill-project-management/blob/main/.specs/separate-owner-completion.md)); the fork syncs from upstream at every landing and stops the line on a large conflict. The central board server is not revived: its remote mode supports planning only and its tokens are unscoped ([assessment](https://github.com/relux-works/wiki/blob/main/research/board-server-assessment.md)).

### The demo

The strongest demonstration is a run: a project taken from a specification to a working result by the system almost in one shot. The logs of the orchestrator and every sub-agent then become a visualization of the development as it happened, with real wall-clock time, so a viewer sees how long it took and what was built. The board itself is developed this way.

### Decided, open and in flight

**Decided between 25 and 28 September:**
- the names of the Apiary, with beekeeping words only where people type them;
- capabilities granted once, batched touches, an explicit yolo mode, loop limits as parameters, and dreams as a proposal;
- the trust principles, and the separate operating-system account for agents as the real boundary;
- role skills through per-role Curator profiles;
- the command-line shape: `keeper`, `curator` with its providers, and `task-board` as the kernel;
- the Keeper runs on existing harnesses, our own loop is postponed, and KP1 is terminal-only;
- one accepting writer per board with epoch fencing;
- specifications merged on `main` as drafts.

**Still open** ([open questions](https://github.com/relux-works/wiki/blob/main/open-questions.md)):
- whether a shared board's writer is assigned by ownership or elected;
- the companion app's design and platforms;
- how the operator's files and executables are protected until agents run under their own account;
- the freeze of each specification.

**In flight:** the agents-infra exit campaign in its two gates, the narrow Muse slice, and the extraction of the session host.

## What comes next

The next concrete steps are Gate A and the session host. Once children run in their roles' profiles and the host stands on its own, a third orchestrator on another harness can join a project the same day, the waggle doorbell reaches every harness, and the Keeper gets the host it runs on. Everything else in this post, the Apiary and the swarm included, builds on those two steps.
