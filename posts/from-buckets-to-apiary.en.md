---
title: "From Carrying Buckets to an Apiary: How We Build Agent Systems"
description: "How we went from copying code between a chat and an editor to a system where one orchestrator runs agents in any environment, processes are configuration, and many people and machines work on one project."
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

Our own projects show where the old way breaks. Orchestrators block each other on one trunk, validation suites queue behind each other on one machine, and every model vendor lives in its own tab, so a person spends the day carrying context between them. Most tools are built around one person driving one agent, and that shape stops working once a project needs many agents, several vendors and more than one operator.

This post answers one question: what does it take to put many agents, several vendors and several people on one project while keeping quality, cost and trust under control? It covers the design we settled between 17 and 24 September 2026. The specifications behind it are drafts, every non-obvious claim links to its source, and when this post disagrees with our [decisions page](https://github.com/relux-works/wiki/blob/main/decisions.md) or [roadmap](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md), those win. Each chapter opens with the problem its epoch ran into and closes with the piece of our system that solves it.

## TL;DR

- **One orchestrator, any agent environment.** Contexts come from Curator and every launch is built in one place, the agents-management module. A person enters through `curator run`, and tracked children start through `task-board spawn`. A new session-host module (`agent-session-host`) drives Claude, Codex, Muse, agy, Pi and Qwen behind one contract: goals in, acknowledgements and events out, notices into a running session.
- **Quality and cost are engineered.** A producer-reviewer cycle with worktrees and signed landings raises quality. A router, an availability view, local engines and per-launch network profiles put each task on a model that fits it at the lowest sufficient cost, across several subscriptions on one machine.
- **Goals are per agent and recursive.** Every spawned agent has its own goal, the orchestrator has one above them, and milestones change on the fly.
- **Agents talk through waggle.** Messages carry SSH signatures by role over untrusted providers. Scope leases decide who owns what, and quorum records decide together.
- **Processes are configuration.** A project declares its roles, element types and workflows in `Playbook.json`. Roles are skills, and a published playbook is a collection of skills that one Skillfile selector installs. The same machinery runs a café.
- **A Hive runs many processes; an Apiary runs many hives.** One root loop on one machine wakes the orchestrator of the right process. Many machines and many people then join one project with trust enforced by signatures, leases and diverse reviewers.
- **The current board stays in maintenance.** New capability ships as modules plugged into it.

## 1. Epochs

**Carrying buckets.** We started by pasting code into a chat window and carrying the answer back: copy the snippet, paste it into the editor, build, carry the compiler error back, repeat. The model saw only what we remembered to paste.

**Scripts.** Next came scripts that collected the right files as context, sent them, and applied what came back. That was faster, but every step of the loop was still ours.

**Agents.** Then agents learned to run the loop themselves: open files, edit them, compile, run the tests, read the failures, try again. For a while it felt like the problem was solved.

**Traffic jams.** Then the agents got stuck, like cars in a traffic jam. They dug into details, lost the thread and came back to the same wall. People wrapped them in patches: Ralph loops that restart the agent until the work is done, and goals that keep it working toward one objective. It still failed often, because a project mixes many classes of task. Architecture, a boilerplate edit and a security review need different models, and one agent on one model does all of them.

**Spawns.** Agents learned to start sub-agents, but only of their own kind: Codex spawns Codex, Claude spawns Claude, and some environments cannot spawn at all, so everything runs in one stream.

**The epoch we are entering.** A few teams now point thousands of agents at a single problem, from formal proofs to large codebases, and much of what makes that work is how many agents synchronize on one project. Only a few can build such systems today. This post describes how anyone can step into that epoch, and which pieces we are building for it.

## 2. A layer of indirection: one orchestrator, any agent environment

**The problem.** Say we want a security review of one change from three angles at once: the strongest Codex model, the strongest Claude model, and a local or uncensored model that is willing to attack the code for real. Today that means three tabs, three environments, and a person carrying the diff and the findings between them. Every environment spawns only its own kind, and none of them knows the other two exist.

As the saying goes, every problem in computer science can be solved by adding another layer of indirection. Our layer lets one orchestrator, in whatever environment it runs, start sub-agents in any other one with the same instructions, so that even a local Qwen can orchestrate top Claude and Codex models. Which model does the work becomes a matter of role and policy.

The layer spans three planes.

| Plane | Answers | Module | Status | Specification |
| --- | --- | --- | --- | --- |
| Sessions | who hosts a live session: goals in, events out | `agent-session-host` (new); ax later; tb-sessiond today | first priority | [roadmap §3 SH](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#sh-session-host-module) |
| Launch | how intent becomes argv and environment | [agents-management](https://github.com/relux-works/skill-agents-management) module; [curator-agent-launcher](https://github.com/relux-works/curator-agent-launcher) (`curator run`); `task-board spawn` | module in use; launcher untagged | [launch profiles](https://github.com/relux-works/skill-project-management/blob/main/.specs/drafts/launch-profiles.md), Decisions [0019](https://github.com/relux-works/curator-spec/blob/main/decisions/0019-fragment-consumers-and-one-construction-site.md) and [0021](https://github.com/relux-works/curator-spec/blob/main/decisions/0021-sessions-enter-through-curator-run.md) |
| Context | what an agent receives | [Curator](https://github.com/relux-works/curator) | release candidates | [curator-spec](https://github.com/relux-works/curator-spec) |

The rest of the planes (routing, availability, inference, network, orchestration, communication) arrive in the chapters where their problems do.

### 2.1 Context: Curator

Curator resolves a profile (root instructions, skills, MCP servers) into a **managed home**. That is a per-profile configuration directory, like `~/.claude` or `~/.codex`, that holds only that profile's context. An agent launched there sees exactly that context and nothing the machine has globally. `curator env resolve` emits an environment fragment (`launch-env-fragment-v1`) that says what to attach: the home, an MCP file, a system-prompt file ([roadmap §8.2](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#82-why-launches-are-built-in-one-place)).

Every harness needs its own managed home, Muse included (decided 2026-09-24). A managed home also scopes things that would otherwise be machine-global, such as agy's hooks (chapter 6).

Curator also installs skills. Its Skillfile schema 2, already implemented behind a flag and not yet released, adds repository sources and selectors that pick skills by directory ([skillfile-sources](https://github.com/relux-works/curator-spec/blob/main/protocol/skillfile-sources.md)); playbook distribution builds on it (chapter 8).

### 2.2 Launch: one construction site

**The agents-management module** holds the model registry, one plugin per harness (binary, argv grammar, environment contract, stdin transport) and the provider limit plane. It produces plan values and deliberately starts no process ([architecture](https://github.com/relux-works/skill-agents-management/blob/main/docs/architecture.md)).

**Decision 0019 (proposed): one construction site.** Several processes may read the Curator fragment. The context channels (MCP configuration, system prompt, home variable) and the harness argv, however, are spelled in exactly one place: the module ([0019](https://github.com/relux-works/curator-spec/blob/main/decisions/0019-fragment-consumers-and-one-construction-site.md)). The reason is concrete. If `curator-run`, task-board and the session host each spell `claude … --mcp-config <file> --strict-mcp-config`, the copies drift. A single forgotten `--strict-mcp-config` then lets the machine's own MCP servers leak into a child.

**Runtime bindings.** A runtime binding has two halves ([LP D1](https://github.com/relux-works/skill-project-management/blob/main/.specs/drafts/launch-profiles.md#d1-object-runtime-binding-two-halves-no-profile-word) to [D3](https://github.com/relux-works/skill-project-management/blob/main/.specs/drafts/launch-profiles.md#d3-profile-transport-per-harness-under-managed-homes)): a stable runtime id, and a private machine catalog entry (`runtimes.toml`) that binds the id to a transport, an endpoint, a credential source and possibly an engine. That lets codex talk to a llama.cpp server through `-c model_provider=…` overrides without anyone committing a machine address.

### 2.3 Two doors

From [roadmap §8.3](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#83-two-doors-into-an-agent):

- **`curator run claude|codex` is the one door for a person.** Under **Decision 0021 (proposed)**, if the machine has the ax integration enabled (`ax.json`), `curator run` hands the composed plan to a session host through the `ax start --launch-plan` contract. The session is then hosted from birth, with resume, notices, the board goal and the waggle doorbell ([0021](https://github.com/relux-works/curator-spec/blob/main/decisions/0021-sessions-enter-through-curator-run.md), [launcher §4.6](https://github.com/relux-works/curator-agent-launcher/blob/main/SPEC.md#46-hand-off-and-exec)). `--untracked` gives one direct launch when tracking was the operator's own setting, and is refused when the machine's file enables tracking. `task-board claude|codex` become aliases, and `--native-home` is withdrawn: a session outside Curator is simply the harness binary.
- **`task-board spawn` stays the door for tracked, non-interactive children.** There is no headless `curator run`.

### 2.4 Sessions: agent-session-host

**The problem.** Delivering a goal into a harness, confirming it took the exact revision and typing a notice into a live session exist only in task-board's Claude and Codex hosts; each new harness would add thousands of lines to task-board ([roadmap §3 SH](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#sh-session-host-module), [goal-host synthesis](https://github.com/relux-works/wiki/blob/main/research/goal-host-plane-synthesis.md)).

**The decision** (2026-09-24): extract that logic into a module named `agent-session-host`, beside agents-management and paired with `agent-session-manager` (ax). task-board keeps only the goal ledger and the routing of goals to owners.

**The contract, per harness:**
- start or resume a session;
- apply, change or clear a goal;
- acknowledge the exact goal revision;
- inject a notice into the running session;
- emit goal events (done, blocked, limit) and usage events.

**The wire format is ax's provider plugin format**: line-delimited JSON over stdin and stdout, one versioned request envelope per operation, providers discovered and trusted by path and digest, and a refusal on anything malformed ([ax SPEC §7](https://github.com/relux-works/agent-session-manager-spec/blob/main/SPEC.md#7-provider-plugin-protocol)). Each adapter has a manifest and answers a probe with its capabilities. Today tb-sessiond loads the adapters as a library; later ax can host the same adapters without a rewrite, which is the long-term host path of Decision 0021.

**Upgrade without hangup.** The daemon works like a tmux server: sessions live inside its process, so restarting it to upgrade kills every session it hosts. Today's rule "never upgrade from inside a hosted session" exists because of that. The module removes the problem in one of two ways: a small, rarely changing host process per session, or handing live terminals from the old process to the new one, as a web server passes its sockets on reload. Until that works, hosting stays off by default on every machine ([risks](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#9-risks)).

**Back to the security review.** With the layer in place, one orchestrator spawns three reviewers into three environments with the same role instructions. Each runs in its own managed home, on its own runtime binding, and reports back to the same board. Nobody carries a diff between tabs.

## 3. Roles and the producer-reviewer cycle

**The problem.** An agent that grades its own work passes its own mistakes. A model that wrote the code is the worst-placed model to find what is wrong with it.

**task-board** is today's orchestration system. Its board is a set of files in the repository: a hierarchy of Epics, Stories and Tasks or Bugs, with dependencies that escalate across parents and a planner that sorts the graph. Every child agent is spawned for a **role** with explicit model and effort, and tracked as a run.

Delivery follows one cycle ([Change Request lifecycle](https://github.com/relux-works/skill-project-management/blob/main/references/change-request-lifecycle.md), [tracked background spawn](https://github.com/relux-works/skill-project-management/blob/main/references/tracked-background-spawn.md)):
- a **producer** works in the Story's own worktree and publishes a Change Request;
- the configured validation suite runs against exactly that candidate ([validation binding](https://github.com/relux-works/skill-project-management/blob/main/.specs/validation-binding.md));
- a **reviewer**, typically a model from another vendor, accepts it or sends it back to rework;
- the orchestrator integrates the Story, and the signed result reaches the trunk through a reviewed pull request.

An independent reviewer catches what the producer did not see, and a second model family catches what the first one systematically misses. The same cycle becomes a security control in chapter 10.

The cycle has a price on one trunk and one machine. Validation suites queue behind each other ([risks](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#9-risks)), and CI jobs could land on the development Mac while it ran them: on 2026-09-24 a documentation-only pull request hit the 90-minute `cmd` package timeout that way ([roadmap §1](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#1-where-we-are-2026-09-24)). The operator has since paused that machine's runner. That pain is one reason new work ships as modules with their own repositories and boards, and large directions may move to forks (chapter 11).

task-board is in maintenance: it receives fixes, validation throughput work, the model-alias fix and `vX.Y.Z` release tags. Everything new ships as a module that plugs into it. A rebuilt "Board 2.0" remains a direction without a schedule ([roadmap §5b](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#5b-the-current-board-modules-and-forks)). In chapter 8, today's board turns out to be one configuration of a more general machine.

## 4. Smart routing, availability and the token bill

**The problem.** You pick one strong model for a project, and most of the tasks it does are low-class work: a rename, a boilerplate test, a documentation fix. They still burn expensive tokens.

task-board already offers advisory model recommendations per workload class ([workload-class recommendations](https://github.com/relux-works/skill-project-management/blob/main/.specs/workload-class-recommendations.md)). Three modules take it further.

### 4.1 Model routing: curator-model-router

The router is a separate, inspectable step of launch preparation. It runs before the launch and never sits between an agent and a model API. It asks four questions, each with its own owner ([R2](https://github.com/relux-works/curator-model-router/blob/main/spec/model-routing.md#r2-four-questions-four-owners)):

- **Allowed?** The operator's policy answers.
- **Compatible?** The module registry and the catalog answer.
- **Fit for the work?** The router's estimator answers.
- **Available now?** The availability view answers (§4.2).

A task assessor turns the work into requirements, deterministically first and with a rubric-based assessor next; the estimator compares them with evidence such as benchmarks and our own outcomes ([R4](https://github.com/relux-works/curator-model-router/blob/main/spec/model-routing.md#r4-evidence), [R5](https://github.com/relux-works/curator-model-router/blob/main/spec/model-routing.md#r5-evaluator-contracts)). A good score never overrides the other three answers. The router runs in one of four modes: `off`, `shadow` (record the decision, change nothing), `recommend` and `select` ([R7](https://github.com/relux-works/curator-model-router/blob/main/spec/model-routing.md#r7-modes-defaults-manual-choice)). Its first slice, A0, is the agent-selection resolver and ships with M4. Evidence-based recommendation comes in M8.

### 4.2 Availability: one question, per profile

"What can run now, in this profile?" is one query answered by an aggregator in agents-management (decided 2026-09-24). Three sources feed it:
- provider limits, from the module's existing limit plane;
- engine state, from curator-inference-manager;
- login inside the managed home, from Curator.

Facts are keyed by `(runtime, managed home)`, because a login is per home ([LP D9](https://github.com/relux-works/skill-project-management/blob/main/.specs/drafts/launch-profiles.md#d9-availability-one-block-keyed-by-managed-home)). A failed read never counts as headroom. The specification is still to be written, as milestone M5b ([roadmap M5b](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#m5b-availability-per-profile)).

### 4.3 Local models: curator-inference-manager

`curator-inference-manager` owns local engines, and Curator itself stays engine-blind:
- **Provider.** An umbrella provider found on a trust root, never in `~/.local/bin`, that offers `curator-inference-manager status|ensure|release|stop` ([§2](https://github.com/relux-works/curator-inference-manager/blob/main/spec/inference-plane.md#2-the-provider)).
- **Leases.** `ensure` takes a lease for the caller's deadline or hands it to the launched harness.
- **Lifecycle and arbitration.** Engines move `serving → lingering → draining`. Host arbitration caps the number of resident engines and never drains an engine that holds active leases ([§4](https://github.com/relux-works/curator-inference-manager/blob/main/spec/inference-plane.md#4-lifecycle)).
- **Two availability facts.** `ready` means serving or lingering; `ensurable` means the weights are present, the engine is not quarantined and arbitration would admit it. A cold but ensurable engine stays selectable at a start cost ([§5](https://github.com/relux-works/curator-inference-manager/blob/main/spec/inference-plane.md#5-availability-facts)).

agents-infra, deprecated, is still underneath: its residual runs local models and provides task-board's compose and prepare contracts ([wiki map](https://github.com/relux-works/wiki/blob/main/README.md#deprecated)). Milestone M5a moves the local-model broker out of agents-infra into curator-inference-manager, which unblocks archiving agents-infra (M6). Its decision record will be Decision 0020, reserved and not yet written.

Put together, a trivial task can land on a local model at night, a hard one on a frontier model, and neither choice is made by a person switching tabs.

## 5. Network profiles: several subscriptions on one machine

**The problem.** Every agent on a machine leaves through the same network path, and two launches cannot use two egresses at the same time.

A launch has five independent settings: the Curator profile, the credential selection, the runtime binding, the **network profile** and the execution profile ([N1](https://github.com/relux-works/curator-network-profiles/blob/main/spec/network-profiles.md#n1-five-independent-launch-settings)). The credential selection picks the account; the network profile decides which application proxy the supported connections of that one launch go through. Together they let two agents on one machine use two accounts and two egresses side by side.

This is cooperative proxy routing for supported clients. It does not isolate a process, so we avoid calling it a sandbox. `curator-network-profiles` is a library, `resolve → validate → probe → patch`, that starts no processes. The process owners apply its patch just before spawn: the launcher `curator-run`, task-board's spawn and the session host ([N2](https://github.com/relux-works/curator-network-profiles/blob/main/spec/network-profiles.md#n2-one-library-three-process-owners)). That is the proxy capability of the launcher. Milestone M7.

## 6. Goals: one per agent, recursive, delivered everywhere

**The problem.** Claude and Codex each implement goals inside their own environment. That helps one agent, but we need something else: every spawned agent with its own goal, the orchestrator with its own higher goal, and goals that change as the work reveals milestones. An agent can never finish a goal like "make it nice and working".

task-board keeps a primary goal for the orchestrator and a separate goal for every spawned run, each with revisions, so the orchestrator can move a child's target mid-flight ([Claude goal runtime](https://github.com/relux-works/skill-project-management/blob/main/docs/claude-goal-runtime.md), [Codex goal runtime](https://github.com/relux-works/skill-project-management/blob/main/docs/codex-goal-runtime.md)). The operators' experience adds one rule: an orchestrator given a very large goal starts mixing tasks and digging into details, so it should cut long objectives into milestones, and the weaker its model, the closer together those milestones must be ([call digest](https://github.com/relux-works/wiki/blob/main/research/call-digest-2026-09-24.md)).

The session host delivers goals to every harness, and the harnesses differ a lot ([synthesis](https://github.com/relux-works/wiki/blob/main/research/goal-host-plane-synthesis.md), [Muse](https://github.com/relux-works/wiki/blob/main/research/muse-code-cli.md), [agy](https://github.com/relux-works/wiki/blob/main/research/agy-cli.md)):

| Harness | Control channel | Proof the goal revision took | Hosting |
| --- | --- | --- | --- |
| Claude | terminal (PTY) | reading the rendered terminal | PTY |
| Codex | app-server API | API response | app-server |
| Muse 1.3 | `muse serve` (JSON-RPC with a native goal API) | `goalChanged` event | owner through `serve`; a person's session through a PTY |
| agy 1.2.9 | headless stream-json and hooks | our own `Stop` hook call | headless owner with the hook; PTY for a person |
| Pi, Qwen (planned) | an extension over a private socket | extension digest acknowledgement | PTY plus extension |

Decisions of 2026-09-24 on the adapters:
- **Order.** Extract Claude and Codex first, with identical behaviour.
- **Muse** comes after the extraction, in its own orchestrator run, with a pinned version and its own managed home.
- **agy hooks** are installed in the profile's managed home and only act in sessions marked by task-board.
- **Token budgets** are enforced by the host for every harness: accounting always, a wrap-up notice at 90% and a pause with a message to the orchestrator at 100%. Only Codex takes a budget natively.

Once goals work on every harness, orchestrators can spread across harnesses, subscriptions and limits. That is **sharding**, and it needs the next chapter: orchestrators that know about each other.

## 7. Orchestrators talking: waggle

**The problem.** Two orchestrators on one project block each other, redo each other's work and race to land on the same trunk. Nothing carries messages between them; a run's notices reach only the orchestrator that owns the run, and nothing is signed ([waggle §1](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#1-what-exists-summary)). We want them to agree among themselves, with no person managing each one.

waggle has two layers ([§2](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#2-two-layers)). **Communication** answers "who said what to whom, who approved it, and did it arrive". **Coordination**, built on top, answers "who works on what, and how do we agree".

- **Envelope and signatures.** A message is the exact payload bytes plus one or more SSHSIG signatures, each with a role: `author`, `approver` or `endorser`. The namespace binds message class and role, so a signature cannot be reused in another role. The roster is a stock OpenSSH `allowed_signers` file, and a committed policy says which types need which roles ([§4.4](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#44-signature-policy-and-attested-approval)). A stored message can be re-verified offline with `ssh-keygen`.
- **Classes and authority** ([§5](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#5-classes-and-authority)): `coord` between orchestrators, `cmd` from an orchestrator or operator to a worker, `report` from a worker, `receipt` from a host. The roster limits namespaces per key, so a worker key cannot produce a valid `coord` or `cmd` over any transport.
- **Key hardware is pluggable** ([§4.5](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#45-signer-providers-and-key-assurance)). Signer providers cover `ssh-agent`, Apple Secure Enclave, FIDO, and later TPM and PIV. Keys get an assurance level: `software` < `hardware-bound` < `attested`. Only FIDO signatures carry a checkable "user verified" flag, so a halt of someone else's worker can demand that proof of presence. An operator without special hardware signs with an ordinary key, and the policy limits what that key may approve.
- **Conversation model** ([§8](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#8-conversation-model)): spaces, threads and participants. The `space`, `thread` and `reply_to` fields live inside the signed payload, so a provider cannot move a message.
- **Providers are untrusted pipes** ([§9](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#9-providers)): a local directory, NATS JetStream, IRC, XMPP, Matrix, Slack, Telegram, email. Authority comes from signatures, the roster and the policy, never from the provider, so a proprietary chat can serve as an adapter while the core stays independent of it. IRC suits a project that runs its own server; XMPP suits federation between organizations.
- **Delivery into sessions** is a doorbell plus a pull. A fixed-template doorbell goes into the session through the session host's notice injection, and the agent then pulls the content as data with `task-board mail read` ([§10](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#10-delivery-into-agent-loops-doorbell-and-pull)). waggle ships no harness-specific code.
- **Scope leases decide; messages negotiate** ([§12](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#12-scope-leases)). A lease names the orchestrator that owns part of a project, with a term and a token in a compare-and-set store. The kernel checks it at spawn, integrate and board commit. Leadership is holding the lease.
- **Deciding together.** Group decisions follow honeybee quorum sensing: proposals, `support` and `objection`, then a `decide` record that carries the supporters' signatures ([§11](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#11-coordination-vocabulary-and-decisions)).
- **Protocol lab.** A disposable fixture project on three machines with a deliberately primitive channel, full logs and a reset. Agents are left to invent their own coordination there, and the coordination vocabulary grows from what they actually do, through reviewed changes ([§13](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#13-protocol-lab)).
- **Fast path** ([§14](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#14-fast-path-to-internet-coordination)): the library first (F1), then a local carrier with `task-board mail` (F2), then NATS JetStream for two operators on a dedicated Mac mini, tailnet-only and clear of that host's production ingress (F3), then leases enforced at write boundaries (F4).

Locally first (milestone CM1: two orchestrators on one machine coordinate, each cancelling only its own children), then two operators over the internet (CM2). A person watches in the terminal console first; an IRC bridge is optional.

## 8. Beyond software: processes as configuration

**The problem.** Everything so far describes software delivery, and the board's structure (element types, statuses, the producer-reviewer loop, the roles) is Go code inside task-board. A team with a different development process has to fork the code, and a process that is not development at all, such as a café's purchasing, cannot use the machine at any price.

The answer is **process configuration**, drafted in [curator-playbook](https://github.com/relux-works/curator-playbook) (PC0). It was the operators' top product priority from their call ([call digest](https://github.com/relux-works/wiki/blob/main/research/call-digest-2026-09-24.md)). The vision behind it: any process becomes configuration run by agents, with humans and tools owning the steps that need them, whether it is software delivery, a café's purchasing, a patent pipeline or a family calendar.

**Two files, two jobs** ([§2.1](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#21-playbookjson-and-skillfilejson-two-files-two-jobs-decided)). `Skillfile.json` says what is installed; Curator reads it, and it carries sources and versions. `Playbook.json` says how the project works; the board reads it, and it carries role aliases, entity types, workflows and policy. They meet only through skill names. The format is JSON with a published schema, `description` fields instead of comments, and an optional `ui` block the kernel ignores, so a visual constructor can later draw and edit the process without losing anything.

**Owners.** Every state has exactly one owner and optional helpers ([§4.2](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#42-owner-kinds-decided)).

| Owner kind | Who does the work | Example |
| --- | --- | --- |
| `agent` | an agent running a role skill | developer, reviewer, refuter |
| `human` | a person or a group | approving a purchase, confirming a delivery |
| `tool` | a command exported by a skill that Curator installed and audited | a CI check, the Lean kernel, a payment gateway client |
| `comb` | another process | handing a proven finding to the process that fixes it |

Two different results are two states; parallel work is child elements plus a join guard. Planning poker, for example, is a state owned by a facilitator whose helpers are blind estimators.

**Guards and actions come from modules** ([§6.3](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#63-guards-and-actions-come-from-modules-decided)). The kernel offers what every process needs: `description`, `estimate`, `assignee`, `children.terminal`, `approvals`, `spawn.owner`, `handoff`. Change Requests, worktrees, integration and validation suites are development-specific, so they move into a **delivery module** that contributes guards such as `delivery.cr-published` and `review.accepted`. A café never loads it.

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

That iOS project swaps the developer and adds QA before `done`; when dev-cycle publishes a new version, everything else updates. A project can also **use** several playbooks and bind their **slots**, abstract types a playbook leaves open ([§7.2](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#72-uses-and-slots-composition-decided)). Scrum is the example. It does not say how a task is done; it says how work is selected and timeboxed. So `{"uses": ["dev-cycle", "scrum"]}` plus binding scrum's `work-item` to dev-cycle's `story` puts dev-cycle's stories into scrum's sprints ([roadmap §8.6](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#86-scrum-over-dev-cycle)).

**Roles are skills; a playbook is a collection of skills** ([§8](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#8-distribution-roles-are-skills-decided)):

```
curator-playbook-dev-cycle/
  skills/
    orchestrator/   SKILL.md (the root role) + data/playbook.json (the process template)
    developer/      SKILL.md + data/role.json (capability, default needs)
    reviewer/  refuter/  researcher/  designer/
```

One Skillfile schema 2 source plus one collection selector, `{"from": "dev-cycle", "directory": "skills", "include": ["*"]}`, installs the orchestrator and every role as ordinary skills. A reusable role from another repository is one more selector. Two Curator changes follow ([§8.3](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#83-proposed-curator-change)):
- schema 2 must be released;
- skill dependencies (`dependencies.skills`) need the same `directory` selection, so that a playbook can depend on one role inside another repository.

Without Curator the same directories are copied into the harness skill folders by hand, and `Playbook.json` does not change.

**Needs and unmet needs** ([§9](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#9-model-needs-and-unmet-needs-decided)). Today one configuration file mixes project policy with one operator's machine facts, and its ceilings name concrete model ids, so a teammate with other harnesses gets a broken project ([agent selection §1](https://github.com/relux-works/skill-project-management/blob/main/.specs/drafts/agent-selection.md#1-facts-verified-2026-09-23)). Instead, a role states `require` and `prefer` in terms of publisher, family, capability, local, or `not_same_publisher_as`, and never names a model id or a reasoning effort. Each operator's private `~/.curator/models.toml` binds concrete models. It is TOML because people edit it by hand, and its bindings run from specific to general:

```toml
[bindings]
"dev-cycle/developer" = { run = "codex/gpt-6-luna", effort = "high..max" }
"*/refuter"           = { run = ["claude/claude-opus-5-5", "codex/gpt-6-sol"], effort = "high" }
"@reviewer"           = { run = "claude/claude-opus-5-5", effort = "medium" }
```

The most specific key wins: one role of one playbook, then a role in any playbook, then a capability. `run` takes one model or an ordered list of candidates, `effort` takes a value or a range, and the project may only set a floor. Without the file nothing fails: the resolver picks the best admitted model that meets the role's needs among the harnesses that are installed and logged in, and says what it picked and why. When a requirement cannot be met at all, `on_unmet` decides:

| `on_unmet` | What happens |
| --- | --- |
| `block` | refuse, naming the layer that emptied the candidate set (default) |
| `fallback` | try the playbook's ordered fallback needs |
| `ask` | request the operator's approval, as a board card or a waggle approver signature, with a scope and an expiry, and record it |
| `degrade` | run on the best available, mark the result, insert an extra review |

**`playbook validate`** is a standalone library and CLI. The board runs it on load and a constructor on every edit ([§10](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#10-static-validation-decided)). It catches, before anything runs:
- a workflow that can never reach a terminal state;
- a transition to an undefined state;
- a role bound to a skill that is not installed (with the `curator add` fix);
- an owner whose capability a guard does not accept;
- an estimate guard on a type without estimate dimensions.

**The refuter** tries to refute a draft by contradiction ([§12](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#12-the-refuter-role-and-decision-memory)):
- **Where it sits.** A `challenge` state after `draft`.
- **What it does.** It assumes the draft is implemented as written, derives the consequences and compares them with recorded `decision` elements, the board's memory of what was decided.
- **What it returns.** A typed verdict: `no-contradiction` with the decisions it checked, `contradiction` with claim ↔ decision pairs, or `human-decision`.

Its first run, on this very draft, returned `human-decision`: 36 findings, three of them blocking. An agent could act for a human owner, because nothing authenticates who fires a transition. Installed package data could decide what runs, through tool commands, schedules and effort. And the default configuration failed the draft's own validator. That is the point of the role: the contradictions surfaced before a line of the module was written.

The operator answered all eight questions the same day. Agent runs never act for a human owner, and risky states need a waggle approver signature. A playbook carries no executable at all: a tool state names a command exported by a skill installed through Curator, so Curator's audit, signatures and lock cover everything that runs, and schedules or automatic spawns take effect only when the project enables them. Reasoning effort moved to the operator's file. Delivery rules such as "no `done` before integration" hold for every type that uses delivery. Until the Keeper exists, an idempotent `task-board tick` fires timers. Draft v2 folds these answers in.

**Generality comes with tests** ([§11](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#11-generality-vectors-decided)). The module ships a conformance set that covers:
- custom typed fields, human and tool owners;
- timers and SLAs, recurring items, external events;
- hand-off between processes, parallel branches with joins, quorum votes;
- loop limits with escalation, resolutions and reopening;
- per-process privacy, multi-dimensional estimates with capacity.

Seven demo playbooks exercise it, each starting from a poorly specified request: dev-cycle; bug-hunt → dev-cycle; scrum over dev-cycle; café operations (inventory → purchasing → accounting); incident → postmortem → fix; a patent pipeline; an agency (lead → estimate → project → invoice). One example borrows the model of [prove2.me](https://prove2.me/), where results are split into missions and milestone lemmas and a contribution is accepted only when the Lean kernel checks it. It fits naturally: `checking` is a state owned by a `tool` ([example](https://github.com/relux-works/curator-playbook/blob/main/examples/prove2me-style.playbook.json)).

**Today's board is itself a playbook** ([§14](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md#14-todays-task-board-as-a-playbook)). `default.playbook.json` maps the current kernel with file and line references. Mapping it turned up three surprises:
- the kernel has no transition table (any non-terminal status can be set once its gates pass), which the default expresses as `from: "*"`;
- a leaf state's worker is chosen by assignment, so an owner may be `one_of` several roles;
- `integrating` is a locked state with no public exits.

PC1 loads this default with identical behaviour; PC2 ships the role skills (this is the old milestone M1); PC3 turns on custom types and the delivery-module seams.

## Interlude: one project, end to end

Two operators, Alice and Bob, work on one project. Alice uses Claude and Codex subscriptions; Bob uses Codex and a local model on his Mac.

1. **The committed files.**
   - `Skillfile.json` has two collection selectors, one for `curator-playbook-dev-cycle` and one for `curator-playbook-bug-hunt`.
   - `Playbook.json` says `"uses": ["dev-cycle", "bug-hunt"]`, binds bug-hunt's slot `fix-target` to dev-cycle's `dev-task`, and gives the reviewer the need `not_same_publisher_as: developer` with `on_unmet: ask`.
   - Neither file names a model, a machine or an endpoint.
2. **The private files.**
   - Alice's `models.toml` binds producer needs to her Codex subscription and reviewer needs to Claude.
   - Bob's `models.toml` binds producers to a local engine. His `runtimes.toml` points a runtime at his llama.cpp server and his `engines.toml` describes it.
   - `playbook validate` passes on both machines, because both have the skills installed.
3. **Hosted sessions.** Each operator runs `curator run codex` in the project. Both machines have the ax integration enabled, so the session host hosts each session from birth: resume, notices, the board goal, and a doorbell. A third orchestrator, on another harness, can join later; that is sharding.
4. **Scopes.** Alice's orchestrator leases Epic Auth, and Bob's leases Epic Billing. When Alice's orchestrator tries to spawn on a Billing story, the kernel refuses (`scope_owned_by`), and the orchestrators negotiate a hand-off with `coord` messages.
5. **A finding flows into delivery.**
   - bug-hunt proves a finding. Its `handoff` action creates a `dev-task` in dev-cycle and links it back.
   - The task moves `open → development`. Bob's developer runs on his local engine: curator-inference-manager `ensure`s it, the availability view said it was ensurable, and the network profile of that launch applies.
   - At `review`, the reviewer's need for another publisher fails on Bob's machine. `ask` fires, and Bob approves "same-publisher review for this epic, 30 days" once; the selection records it.
6. **A spec is refuted.** The fix needs a small specification. Its `challenge` state finds that the draft proposes plain release tags while a recorded decision says `vX.Y.Z`, and sends it back to `draft` with the pair quoted.
7. **A halt needs a human.**
   - Alice's orchestrator sees Bob's worker about to integrate onto a broken base. Its lease does not cover that worker, so a plain `cmd.halt` would be refused.
   - The policy requires an operator approver with user verification. Alice reads the rendered message and touches her FIDO key.
   - The envelope now carries two signatures, and Bob's host verifies both before the supervisor halts the worker ([waggle §6](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#6-example-of-multi-signature-in-use)).
8. **Same machinery, different business.** On a third machine a café runs `cafe.playbook.json` on the same kernel:
   - a manager (a human owner) approves each purchase order;
   - the order goes to the supplier portal (a tool owner), and if the supplier's confirmation event does not arrive within 15 minutes, the order escalates;
   - once every delivery line is received, the order is handed off to the accounting process as an invoice;
   - `payment.received` arrives as an external event and marks it paid;
   - a weekly schedule creates the inventory check ([example](https://github.com/relux-works/curator-playbook/blob/main/examples/cafe/cafe.playbook.json)).

   Nothing in the kernel knows what a café is.

## 9. The Hive: one root loop, many domains

**The problem.** Always-on personal assistants in the OpenClaw style put one agent loop on a schedule and ask it to do everything. The loop's memory clogs, it tries to do everything at once and finishes little, it needs an expensive subscription to run at all, and not every provider sells a subscription that such a loop can use.

A **Hive** is one machine's agent system built from the pieces above ([naming](https://github.com/relux-works/wiki/blob/main/naming.md)):
- **The Keeper**, a root loop: a schedule, an inbox for the person, a classifier and a small model to answer at once. It can run on a small local model, because its job is to understand what the person wants, answer at once and route the rest.
- **Combs**, one per domain. Each Comb is a process with its own playbook, its own board, a long-lived root orchestrator and its own roles: development of project X, the café's purchasing, a family calendar, a smart home. Processes can be lifestyle, business or a mix of both ([call digest](https://github.com/relux-works/wiki/blob/main/research/call-digest-2026-09-24.md)).
- **Routing.** The Keeper merges the person's request with the descriptions and task classes each Comb declares, and wakes the right orchestrator. Waking it is a waggle doorbell into its hosted session (chapters 2 and 7), and that orchestrator delegates to sub-agents with the roles of its own process.

Several orchestrators can run under one Keeper as long as their tasks do not overlap, which is what scope leases enforce. Later, the roots of two people (two households, two companies) may talk, read-only at first.

**The Keeper and OpenClaw.** Plugging into existing loops is how we reach their users, and the core stays our own loop ([roadmap §5](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#5-later-tracks), [agent loop research](https://github.com/relux-works/wiki/blob/main/research/agent-loop.md)). A Keeper API comes before any loop: a process registry, routing a request to a process, `create`, `wake` and `status`. Our own loop and an OpenClaw skill would both be thin fronts over it, and an orchestrator answers such a loop through the messenger it watches, an inbound hook if it has one, or polling `status`. That shape is still under discussion. The subscription problem is already solved underneath: the launch plane binds any subscription, API key or local engine the operator has, per machine.

**Our own minimal agent loop (Bee).** Three parts of the plan need a loop we control: the Keeper, worker agents with a deliberately restricted tool set in the Apiary, and long-lived orchestrator nodes ([research](https://github.com/relux-works/wiki/blob/main/research/agent-loop.md)). The requirements:
- a minimal core: model calls, tool dispatch, context management and an event stream;
- extension by tool skills that Curator installs, whose command-line tools are the surface a tool call executes;
- native sub-agent spawn with completion events delivered to the parent;
- a harness plugin in agents-management, so `curator run <our-loop>` launches it like any other harness, and a session-host adapter.

Candidates to study are pi (already supported by the launch plane as exec-mode `pi-native`), the Claude Agent SDK and Claude Code's architecture, OpenCode and Codex CLI. The Apiary design already treats its own harness as "the next client, not a rewrite" ([Apiary §9](https://github.com/relux-works/curator-agent-runtime/blob/main/docs/drafts/apiary/minimal-roadmap.md#9-own-harness-and-tools-through-curator-the-next-client-not-a-rewrite)).

A Hive is a small autonomous organization on one machine: a person talks to the Keeper, and domain orchestrators run their processes with agents, humans and tools owning the steps.

## 10. The Apiary: from one hive to many

**The problem.** Some projects need more than one person can bring. Two to five subscriptions are affordable; a hundred are not. A new operating-system kernel, written from scratch with the best patterns of decades of research, needs many people, many machines and a shared environment with virtual machines and compile capacity. It also needs trust, because not every participant will be honest.

The **Apiary** is that scale: many hives across machines and people ([naming](https://github.com/relux-works/wiki/blob/main/naming.md)). Its design lives in `curator-agent-runtime` ([Apiary roadmap](https://github.com/relux-works/curator-agent-runtime/blob/main/docs/drafts/apiary/minimal-roadmap.md), [track](https://github.com/relux-works/curator-agent-runtime/blob/main/docs/drafts/apiary/track.md)), and its thesis is gradual: Apiary is where today's orchestration infrastructure ends up, so nobody has to migrate to a new platform ([§0](https://github.com/relux-works/curator-agent-runtime/blob/main/docs/drafts/apiary/minimal-roadmap.md#0-thesis-and-scope)). The first product is one orchestrator over a shared pool of local and remote agent loops, each using its owner's credentials, whose results go through the existing review and integration path.

**Four questions kept apart** ([§2](https://github.com/relux-works/curator-agent-runtime/blob/main/docs/drafts/apiary/minimal-roadmap.md#2-core-model)): who runs the agent loop, what serves inference, where the tools run, and who assigns work and accepts the result. Locality is a placement property and trust is a policy property: a remote agent may be fully trusted, and a local one may execute untrusted code.

**The staged plan** ([§10](https://github.com/relux-works/curator-agent-runtime/blob/main/docs/drafts/apiary/minimal-roadmap.md#10-staged-plan-with-a-useful-result-at-every-stage)), with a useful result at every stage:

| Stage | Adds |
| --- | --- |
| 0 | the local spawn path as the first backend of an AgentHost adapter (Hive scale) |
| 1 | one remote executor: an agent on a second machine changes code on the first with its own credentials |
| 2 | a reliable trusted pool: durable mailbox, headless wake, reconnect, leases, queues, limits |
| 3 | restricted execution profiles with the same verifiable restrictions for local and remote agents |
| 4 | several orchestrators with scoped roles and messages between them |
| 5 | external participants and our own client: untrusted inference capacity under stricter admission |
| 6 | distributed autonomy: replicated state and automated role transfer |

A hive that sends a starter team, an orchestrator with its workers, to another hive sends a **nuc**, the beekeeper's word for a small colony used to start a new one.

**Patterns from distributed databases.** Scope leases carry a term and a token in a compare-and-set store, so a stale owner is fenced out. Group decisions are quorum records carrying the supporters' signatures. Several orchestrators do not need immediate decentralization: one coordinator and one authoritative project store come first. Before another orchestrator inherits a role, the previous generation of assignments is revoked or fenced, otherwise the old orchestrator keeps acting once it wakes up ([§10.1](https://github.com/relux-works/curator-agent-runtime/blob/main/docs/drafts/apiary/minimal-roadmap.md#101-several-orchestrators-do-not-require-immediate-decentralization)).

**Trusted orchestrators, untrusted agents.** Participants join and leave a pool dynamically, so the system itself has to enforce trust:
- **Signatures with hardware behind them.** Multi-signature envelopes, key assurance levels and FIDO proof of presence (chapter 7). A draft amendment proposes the same SSHSIG envelopes for the Apiary's authority wire ([amendment](https://github.com/relux-works/curator-agent-runtime/blob/main/docs/drafts/apiary/authority-wire-amendment.md)).
- **Injection defense in depth** ([waggle §7](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#7-injection-defense-in-depth)). Authority stays outside the model and messages are typed and framed as data. For external senders, deterministic inspectors and quarantine with human release are on by default, a quarantined reader that turns free text into a typed request is recommended, and rate limits apply. The trust tier (`own`, `team`, `external`) comes from the roster line that verified the author.
- **Security stages** ([waggle §15](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#15-security-stages)). The trusted stage relies on roster pull requests, operator keys and tailnet ACLs. The external stage admits partner certificate authorities limited to `coord`, hosted accounts first and XMPP federation later.
- **The producer-reviewer cycle becomes a security control.** A task passes several reviewers from different model families and different owners. If someone plants a vulnerability, the chance that at least one uncompromised reviewer catches it grows with every independent reviewer.

**Phases of communication** ([waggle §17](https://github.com/relux-works/waggle/blob/main/spec/waggle.md#17-phases)): CM3 lets an orchestrator reach a remote worker through the AgentHost (Apiary stage 1), which can receive `clarify` or `cancel` but never send `coord` or `cmd`. CM4 opens the door to other organizations: partner certificate authorities, inspectors on by default, XMPP federation, an A2A gateway and quotas.

At that scale, tens of orchestrators and thousands of sub-agents work on one project. Today only a few can build systems like that. We want communities to be able to do it too, including for defence, so that the balance does not tip toward those who already can.

## 11. Where we are and what's next

### Level 0 and Level 1

**Level 0 is small modules.** Each has one job, its own repository and its own board. Higher planes use the lower ones:

| Plane | Answers | Module | Status | Specification |
| --- | --- | --- | --- | --- |
| Communication | who said what to whom, and who approved it | [waggle](https://github.com/relux-works/waggle) | draft v5 | [waggle.md](https://github.com/relux-works/waggle/blob/main/spec/waggle.md) |
| Orchestration | how a project works and what happens next | task-board today; [curator-playbook](https://github.com/relux-works/curator-playbook); [curator-model-router](https://github.com/relux-works/curator-model-router) | task-board in maintenance; drafts | [process-configuration.md](https://github.com/relux-works/curator-playbook/blob/main/spec/process-configuration.md), [model-routing.md](https://github.com/relux-works/curator-model-router/blob/main/spec/model-routing.md) |
| Sessions | who hosts a live session: goals in, events out | `agent-session-host` (new); ax later; tb-sessiond today | first priority | [roadmap §3 SH](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#sh-session-host-module) |
| Availability | what can run now, per profile | an aggregator in agents-management | specification to write | [roadmap M5b](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#m5b-availability-per-profile) |
| Inference | which local engines are up | [curator-inference-manager](https://github.com/relux-works/curator-inference-manager) | draft | [inference-plane.md](https://github.com/relux-works/curator-inference-manager/blob/main/spec/inference-plane.md) |
| Network | which egress a launch uses | [curator-network-profiles](https://github.com/relux-works/curator-network-profiles) | draft | [network-profiles.md](https://github.com/relux-works/curator-network-profiles/blob/main/spec/network-profiles.md) |
| Launch | how intent becomes argv and environment | [agents-management](https://github.com/relux-works/skill-agents-management) module; [curator-agent-launcher](https://github.com/relux-works/curator-agent-launcher) (`curator run`); `task-board spawn` | module in use; launcher untagged | [launch profiles](https://github.com/relux-works/skill-project-management/blob/main/.specs/drafts/launch-profiles.md), Decisions [0019](https://github.com/relux-works/curator-spec/blob/main/decisions/0019-fragment-consumers-and-one-construction-site.md) and [0021](https://github.com/relux-works/curator-spec/blob/main/decisions/0021-sessions-enter-through-curator-run.md) |
| Context | what an agent receives | [Curator](https://github.com/relux-works/curator) | release candidates | [curator-spec](https://github.com/relux-works/curator-spec) |

**Level 1 is systems assembled from them.** Today that is task-board; next comes the Hive, one machine's agent system running many processes under a main loop; later the Apiary, a pool of machines and people.

### The order of work

From [roadmap §2b](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#2b-priority-order-decided-2026-09-24), with the reason for each step:

1. **Session-host module, and waggle CM1 on it.** It removes harness code from task-board, gives every harness goals and notices, unblocks orchestrator sharding, and is the host behind `curator run` ([roadmap §8.5](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#85-why-a-session-host-module-comes-first)). CM1 relieves the daily collisions between orchestrators.
2. **Process configuration PC0/PC1**, the first demo playbooks and the refuter's first run. This was the operators' top product priority, and PC1 proves the model on the real board.
3. **Leaving agents-infra.** The M0 remainder (Curator tags, onboarding this Mac and a bare machine), then M2 (children in managed homes), then M5a → M6 → M5b. The M5 split archives agents-infra earlier, because only the local-model broker still needs it once sessions move.
4. **CM2**, so two operators coordinate over NATS; **M3**, `curator run` hosted through the module; **PC2**, role skills, which delivers the old M1.
5. **M4**, launch profiles and portable configuration, with acceptance on a local engine; **PC3**, custom types and delivery seams.
6. **Later:** M7 network profiles, M8 routing with evidence, the Keeper API, our own agent loop, Apiary distribution, and formal-methods research: each milestone gets the strongest machine-checkable acceptance available: tests for code, the validator for configurations, the refuter for specifications, a model checker for critical protocols such as leases.

### Forks with one board, and why board-server stays down

**Modules first.** Most large directions are cut as a module or behind a narrow seam, as waggle was, and need no fork.

**When a fork is needed**, the fork is a separate code owner, and a checkout of upstream stays the board owner. That is task-board's existing separate-owner completion ([contract](https://github.com/relux-works/skill-project-management/blob/main/.specs/separate-owner-completion.md)), with board state published through `board publish`. The board keeps one signed history, and code comes back through pull requests. The sync protocol ([roadmap §5b](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#5b-the-current-board-modules-and-forks)):
- At every story landing in the fork, fetch upstream, rebase and measure the conflict: overlapping files and hunks, and tests after the merge.
- A large conflict stops the line with a `coord` message to upstream orchestrators and a note on the board.
- Sync on a schedule even without landings.
- Open a pull request from the fork at the end of each milestone.

**The central board-server is not revived** ([assessment](https://github.com/relux-works/wiki/blob/main/research/board-server-assessment.md)):
- its remote mode supports planning only (no Change Requests, worktrees, integration, board commit or producer spawns);
- its tokens are user-level and unscoped;
- the deployment is pinned at March content, and the container build has been broken since late August.

Separate-owner completion gives forks one board for a small setup cost, and NATS gives messaging in days. Decommissioning the old deployment waits for the owners of the two legacy boards it still serves.

### Names

People see the Apiary names; specifications, code and board items use technical terms ([naming](https://github.com/relux-works/wiki/blob/main/naming.md)).

| Name | Technical term |
| --- | --- |
| Apiary | the brand; at full scale, many hives across machines and people |
| Hive | one machine's agent system: main loop, processes, orchestrators, workers |
| Comb | one process: its playbook, board, root orchestrator and roles |
| Keeper | the main loop: schedule, inbox, classifier, conversation with the person |
| Bee | our own minimal agent loop (research) |
| nuc | a starter team a hive sends to another hive |
| Waggle | the messaging protocol |

"Hive" and "swarm" are crowded words in software, so the names live under the brand, and "swarm" is not used at all.

### The demo

The strongest demonstration is a run: a project taken from a specification to a working result by the system on its own, over hundreds of hours of autonomous work. The logs of the orchestrator and every sub-agent then become a visualization of the development as it happened, with real wall-clock time, so a viewer sees how long it took and what was built. The board itself is developed this way.

### Decided, open and in flight

**Decided late on 2026-09-24** (recorded on the decisions page):
- the module name `agent-session-host` and its place beside agents-management, with the contract in ax's plugin format;
- Muse after the extraction, agy hooks in managed homes, host-enforced budgets;
- the availability aggregator in agents-management;
- the development Mac's CI runner paused;
- the operator's model file at `~/.curator/models.toml`;
- the refuter's eight questions answered (chapter 8);
- waggle under Apache-2.0, a terminal console first with an IRC bridge optional, and federation (XMPP, an A2A gateway) later;
- the component repositories and, later, the board's core to become source-available under our Relux Community License, which keeps ownership with its authors.

**Still open** (see [decisions](https://github.com/relux-works/wiki/blob/main/decisions.md) and [roadmap §7](https://github.com/relux-works/wiki/blob/main/roadmap/ecosystem-roadmap.md#7-decisions)):
- the details of temporary exceptions to hard requirements;
- the final license terms before the component repositories go public;
- the Keeper's shape and the base of our own agent loop;
- decommissioning the old board deployment;
- the open points of the process-configuration draft (role metadata location, template lookup, merge rules for `extends`, how review policies appear);
- the two Curator changes.

**In flight:**
- the model-alias fix, accepted in review and landing now;
- the move to `vX.Y.Z` release tags;
- draft v2 of process configuration, which folds in the refuter's verdict and the operator's answers.

## What comes next

The next concrete step is the session-host module. Once it lands, a third orchestrator on another harness can join a project the same day, the waggle doorbell reaches every harness, and `curator run` gets its host. Everything else in this post builds on that step.
