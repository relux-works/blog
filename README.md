# Relux Works — Blog Content

Content source for [relux.works](https://relux.works) blog. Posts live here as plain
markdown; the site pulls them at build time and derives publication metadata from
**git history**, so publication dates are publicly verifiable.

## How publishing works

1. A post is a markdown file in `posts/`, named `<slug>.<lang>.md`
   (langs: `en`, `ru`, `hy`, `ka`). Frontmatter: `title`, `description`, `slug`,
   `lang`, `authors` (array of {name, title, links[]}), `aiSystems` (list of AI generation systems that
   co-created the content of that post, e.g. "Claude Fable 5"; required for honesty). **No dates in frontmatter** — they come from git.
2. On push to `main`, a GitHub Action calls a Cloudflare Deploy Hook; the site
   rebuilds automatically.

### Drafts

Add `draft: true` to a post's frontmatter to publish it **unlisted**: it still builds
and is viewable at its normal URL (bookmark it to preview), but it is excluded from the
blog index and the sitemap, marked `noindex, nofollow`, carries no Article schema, and
shows a "Draft" banner. Push it like any post — it goes live at its URL within ~2 min,
hidden from the public. Remove the `draft` flag (or set it to `false`) to publish for real.
3. During the site build, `datePublished` is derived from the **first commit** that
   touched the file, `dateModified` from the **last commit**. Each rendered post links
   to its commit on GitHub, so anyone can verify when it was published.

## Provenance model

- Git history in this public repo gives traceable, third-party-visible publication
  timestamps (GitHub records push events independently of author-set commit dates).
- Planned next step: anchoring sha256 digests of each post into
  [OpenTimestamps](https://opentimestamps.org/) for cryptographic, Bitcoin-attested
  proof of existence. The build pipeline is already shaped for it.

## Writing rules

- Languages: en is the source of truth; ru, hy, ka follow.
- Style: no em dashes, no guillemets, no blunt antitheses; technical, human, readable.
- Every fact that can be checked should link to a first-party source.

© 2026 RELUX WORKS LLC. Content may be quoted with attribution and a link.

<!-- relux-ecosystem:start -->

## About Relux Works

This project is part of the open-source ecosystem of
[Relux Works](https://relux.works), an AI-native software development studio.
We build fixed-price MVPs, rescue vibe-coded apps, run local AI inference, and
train teams to work with coding agents. Much of the infrastructure behind that
work is open source.

- Full catalog: [relux.works/en/open-source](https://relux.works/en/open-source/)
- Agentic enablement: [agent harnesses & team training](https://relux.works/en/agentic-enablement/)
- Hire us the agent-native way: point your assistant at `https://api.relux.works/mcp`
- Contact: ivan@relux.works

<!-- relux-ecosystem:end -->
