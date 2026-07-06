---
title: "How We Made Our Site Agent-Native, Honestly"
description: "The story of relux.works going from an agent-readiness score of 29 to 79, Level 5: a working MCP server, an inquiries API, OAuth for agents, five registries, and the checks we deliberately left red."
slug: "agent-ready-website"
lang: "en"
author: "Ivan Oparin"
authorTitle: "CEO / Founding Engineer, Relux Works"
---

AI assistants are becoming the first visitor many products ever meet. When a founder
asks ChatGPT or Claude to find a studio that fixes vibe-coded apps, the thing crawling
your site, reading your pricing and deciding whether to mention you is an agent. So we
asked ourselves a simple question: can an agent actually do business with us?

Cloudflare's [agent-readiness scanner](https://isitagentready.com) gave a blunt answer:
29 out of 100, "Bot-Aware". Crawlable, and useless to any agent that wanted to act.
Two days later the same scanner shows 79 and the top tier, Level 5 "Agent-Native",
with a working agent sales channel behind the score. Here is what we did, in order,
including the parts we refused to fake.

## The rule that kept us honest

Every emerging agentic-web standard can be gamed with a static JSON file. You can
publish OAuth discovery metadata for APIs that do not exist, or an MCP server card
with no server behind it. The score goes up, and every agent that trusts the metadata
burns its tokens authenticating into a void.

So we adopted a single rule: every discovery document must point at something that
answers. If we were not prepared to run the endpoint, we did not publish the pointer.

## Step one: hygiene (29 to 50)

Half the score is basics any site can ship in an afternoon:

- robots.txt with an explicit allowlist for AI crawlers (GPTBot, ClaudeBot,
  PerplexityBot, Google-Extended and the rest), plus a
  [Content Signals](https://contentsignals.org) line: search=yes, ai-input=yes,
  ai-train=yes. One gotcha worth checking in your own Cloudflare zone: the Managed
  robots.txt toggle silently prepends Disallow rules for AI training crawlers. We only
  noticed during our own audit.
- llms.txt, a structured company summary. Ship it, and know the data: industry
  measurements show AI crawlers barely fetch the file today. It costs nothing and
  helps AI-assisted IDEs, so publish it without building a strategy on it.
- Link headers (RFC 8288) and a sitemap, machine-readable pointers to everything
  above.
- Agent Skills at /.well-known/agent-skills/: two plain-markdown skills any agent can
  read, one with our canonical facts, one describing how to request a quote properly.

That pass moved us from 29 to 50. Every remaining red check said the same thing: you
have no API, no MCP server, and nowhere for an agent to authenticate. The scanner was
right, so we built the missing piece.

## Step two: a real agent gateway (50 to 79)

We stood up api.relux.works, a single Cloudflare Worker that acts as the agent-facing
side of the studio:

- POST /v1/inquiries, a validated project-inquiry endpoint. An agent submits a brief
  on behalf of its user, the notification lands in our Telegram within seconds, and a
  human replies within one business day.
- An MCP server at /mcp (Streamable HTTP, stateless, about two hundred hand-written
  lines, no SDK) with two tools: get_services_pricing and request_project_quote. Any
  MCP-capable assistant can connect and, with the user's consent, hire us.
- OpenAPI 3.1, human-readable docs and a health endpoint, so the REST surface is
  discoverable too.
- OAuth 2.0 for agents: RFC 8414 metadata, open dynamic client registration
  (RFC 7591), and a client_credentials grant issuing short-lived ES256 JWTs. The
  pleasant part is that the whole thing is stateless. A client secret is an HMAC of
  the client id, so the token endpoint validates credentials without a database.
  Authentication stays optional by design: anonymous callers get strict rate limits,
  registered agents get generous ones, and /auth.md documents the flow.

The first end-to-end test was the moment that justified the whole exercise. An
assistant called request_project_quote over MCP, the gateway validated the brief, and
the notification hit Telegram about two seconds later. A qualified lead arrived with
no human involved on our side of the pipe.

## Step three: discovery

An endpoint nobody can find might as well not exist, so we published in every channel
where our presence is honest:

| Channel | What lives there |
|---|---|
| Official MCP Registry | works.relux/agent-gateway, verified via DNS |
| ClawHub (OpenClaw) | clawhub install relux-works |
| Hermes tap | hermes skills tap add relux-works/agent-skills |
| HermesHub (ARD) | /.well-known/ai-catalog.json, crawled automatically |
| Well-knowns on the apex | API catalog (RFC 9727), MCP server card, agent-skills index, OAuth metadata |
| The pages themselves | WebMCP tools via navigator.modelContext for in-browser agents |

We also published DNS-AID records (_index._agents and _mcp._agents) pointing at the
gateway. The standard is an early draft, and the records are real, resolve globally
and cost a minute to add.

## What is still red, and why that is fine

- DNS-AID wants a validated DNSSEC chain. Our zone already signs responses; the trust
  chain completes when the DS record lands at the registrar, which is queued.
- Commerce protocols (x402, ACP, UCP). We do not sell checkout-style, and pretending
  otherwise would mislead shopping agents.
- Anything else that would require endpoints we do not run.

A check that only turns green if you lie to machines should stay red. Agents keep
receipts.

## Takeaways for founders

1. Agent traffic is real and it converts differently. This visitor reads llms.txt and
   ignores your hero animation.
2. An afternoon of hygiene (robots rules, content signals, sitemap, llms.txt, Link
   headers) is table stakes. Ship it this week.
3. The compounding move is an agent-facing action: one endpoint that lets an assistant
   do the thing your business exists for.
4. Publish discovery documents only for things that answer. Cargo-cult metadata is
   negative SEO for the agentic web.
5. Check your CDN's default bot policy. It may be quietly blocking the crawlers you
   want most.

We build exactly this for clients, from [fixed-price MVPs](/en/ai-mvp-development/)
and [rescuing vibe-coded apps](/en/vibe-code-rescue/) to
[running the whole publishing operation](/en/app-publishing/). And if you would rather
skip the clicking entirely: point your assistant at https://api.relux.works/mcp and
let it talk to ours.
