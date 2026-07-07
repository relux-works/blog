---
title: "CocoaSkills: Package Manager Discipline for Agent Skills"
description: "Skill distribution works for individuals and breaks for teams. CocoaSkills answers with one pinned version for everyone, content-hash verification tied to security audits, project, global and hybrid install scopes, and skills that depend on skills. Plus the story behind the name."
slug: "cocoaskills"
lang: "en"
authors:
  - name: "Ivan Oparin"
    title: "CEO / Founding Engineer, Relux Works"
    links:
      - "https://github.com/ivanopcode"
      - "https://www.linkedin.com/in/ivanoparin/"
aiSystems:
  - "Claude Fable 5"
---

Agent skills quietly became a unit of engineering knowledge. A skill teaches an
assistant how your team reviews code, runs incidents, queries internal systems,
writes migrations. The best ones get shared, and sharing today mostly means
copying folders: a zip in a chat, a "clone this repo into ~/.claude/skills"
line in a README, a dotfiles symlink farm.

For one developer this is fine. For a team of forty on a codebase that ships
to production, it fails in ways package management solved decades ago. We hit
those failures ourselves, so we built [CocoaSkills](https://cocoaskills.org),
a local skill manager with the boring properties teams need. It is open
source, Apache-2.0, and installs with one command:

```bash
pipx install cocoaskills
```

## Where copying breaks

The failure list will look familiar to anyone who lived through pre-package-manager
platforms:

- Drift. Thirty repositories hold thirty slightly different copies of the
  review skill. A bug fixed in one copy lives on in twenty-nine others.
- Provenance. An incident retro asks which exact version of a skill produced a
  given suggestion, and nobody can answer, because the skill is a folder that
  anyone may have edited.
- Security. A skill is executable content: prompt instructions plus scripts
  that run on developer machines with developer credentials. Teams review
  application dependencies through lockfiles and registries, then paste agent
  skills from gists.
- Onboarding and cleanup. A new engineer assembles their environment by hand.
  A removed skill leaves its files behind forever.

Most current skill tooling ships skills into a single user-level directory
and serves the individual developer well. Team scale adds supply chain
questions: who pinned what, who verified it, and how the same answer reaches
every machine. Those questions want a package manager.

## One version for everyone, verifiable

CocoaSkills starts from a manifest committed to the project repository.
`Skillfile.json` declares the skills a project uses, each pinned to an exact
git ref:

```json
{
  "schema_version": 1,
  "project": { "alias": "demo-ios" },
  "agents": ["claude_code", "codex_cli", "cursor"],
  "skills": [
    {
      "name": "skill-tracker",
      "git": "git@gitlab.example.com:skills/skill-tracker.git",
      "tag": "v1.4.2"
    }
  ]
}
```

`csk install` resolves the ref to a commit, takes a content snapshot, and
records a sha256 of every installed file set in an install marker. The
manifest travels through code review like any other dependency change, CI can
assert that installs are current, and `csk status` detects drift down to a
single modified byte on any machine. Everyone runs the same skill at the same
commit, and can prove it.

## Audit that binds to bytes

Saying "we reviewed this skill" is only useful if the statement survives the
next `git push` to the skill repository. CocoaSkills makes the audit verdict
stick to content, and places the check at the one point where skill content
enters an agent.

The mechanism, precisely: agent environments such as Claude Code, Codex CLI,
Cursor and Gemini read skills from adapter directories that CocoaSkills
populates. Nothing reaches those directories without passing the install
pipeline, and the audit gate lives inside that pipeline. There are no wrappers
around the agents and no runtime interception; the guarantee is simpler than
that. Files an agent can see are files that passed the gate.

Inside the gate:

- Skills declare capabilities in their manifest: which hosts their code may
  contact, which binaries it may execute, which secrets it may read.
  Deterministic static detectors check the actual content against the
  declaration.
- Optional LLM-assisted backends can extract additional findings. They can
  only add information; the allow-or-block decision stays deterministic
  inside the tool, so an audit cannot be sweet-talked.
- Verdicts are cached by the content hash, and trust pins attach to the same
  hash. Approval covers those exact bytes. A new commit produces a new hash
  and inherits nothing.
- Revocation works by content hash or by source pattern, so a compromised
  skill can be blocked across every project at once.
- Strict mode turns findings into hard install failures, which is what you
  want in CI.

The audit trail this leaves is the one the incident retro asked for: this
suggestion came from this skill at this commit with this content hash, audited
on this date, approved by this pin.

## Three install scopes

Teams need finer distribution control than "installed for me". CocoaSkills
separates three scopes:

- Project scope. Declared in the repository's `Skillfile.json`, installed
  into the checkout (generated paths are gitignored), identical for every
  person and CI job that works on the project.
- Global scope. A user-level baseline for personal skills that follow the
  developer across all their work.
- Hybrid scope. Skills stored once per machine in the user-level store and
  activated for specific projects only, with no files materialized into the
  project tree. This fits skills a platform team rolls out to selected
  repositories when committing anything to those repositories is undesirable:
  internal tooling in open source checkouts, org-wide conventions in client
  work, anything whose lifecycle belongs to the platform team.

Project skills shadow global ones on name collisions, so the repository
manifest always wins where it applies.

## Skills that depend on skills

Real workflows compose. An incident workflow delegates to a tracker skill, a
monitoring skill and a review skill; a documentation skill builds on a wiki
CLI another skill exports. Copying composed skills by hand multiplies every
problem above by the depth of the graph.

Since version 0.9, a skill declares requirements on other skills, each
self-contained with a git URL and an exact tag or revision
([RFC 0007](https://cocoaskills.org/v0.9-design.md)):

```json
{
  "schema_version": 4,
  "capabilities": { "exec": "none", "network": "none" },
  "dependencies": {
    "skills": {
      "skill-tracker": {
        "git": "git@gitlab.example.com:skills/skill-tracker.git",
        "ref": { "kind": "tag", "value": "v1.4.2" }
      }
    }
  }
}
```

`csk install` resolves the transitive closure: within one closure a skill
name unifies to one commit and one canonical source, cycles fail with the
full requirement chain, and a machine-level allowlist gates every clone
before the first network operation. Each requirement carries an activation
mode, so a dependency can contribute its prompt context, its commands, or
both, and the agent's context window stays as small as the composition
allows.

The consequence teams care about: a workflow is just a skill that declares
requirements and exports no commands. Publish it once, and a consuming
project installs the entire composition with a single manifest line. The
whole graph arrives pinned, unified and audited.

Development stays humane. `Skillfile.dev.json` substitutes any provider in
the closure with a local checkout or a branch, lives outside version control,
and is loudly reported by every install. Strict audit refuses substituted
installs, so the escape hatch cannot leak into CI.

## About the name

In 2011 the iPhone was four years old, everything was Objective-C, and
dependency management meant dragging folders into Xcode by hand. Git was
winning but had not yet won; a large share of the industry still lived on
Subversion. Into that vacuum came [CocoaPods](https://cocoapods.org), and one
`Podfile` taught an entire platform what dependency discipline feels like.
Swift Package Manager arrived years later, standing on that experience.

Agent skills in 2026 sit at the same point on the curve. The assets are
valuable, the sharing is folders and chat attachments, and the infrastructure
is a vacuum. We named CocoaSkills as a tip of the hat to the tool that
civilized our previous platform: same tree, new fruit, and the cocoa tree
turns out to bear well.

## Boring on purpose

Infrastructure for teams earns trust with dullness, so the dull parts are
load-bearing: the runtime is Python standard library only, the codebase
type-checks under mypy strict, the test suite runs on Linux, macOS and
Windows across four Python versions, releases ship to
[PyPI](https://pypi.org/project/cocoaskills/) with attestations and checksums,
and release tags are immutable. The design history lives in public RFCs in
the [repository](https://github.com/ivanopcode/cocoaskills).

We run CocoaSkills across our own projects and across large-team client work,
and the design above is the direct residue of that use. If your team shares
skills through chat attachments today, start with one `Skillfile.json` in one
repository. The rest of the discipline follows from there.
