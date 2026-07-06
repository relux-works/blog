# Relux Works — Blog Content

Content source for [relux.works](https://relux.works) blog. Posts live here as plain
markdown; the site pulls them at build time and derives publication metadata from
**git history**, so publication dates are publicly verifiable.

## How publishing works

1. A post is a markdown file in `posts/`, named `<slug>.<lang>.md`
   (langs: `en`, `ru`, `hy`, `ka`). Frontmatter: `title`, `description`, `slug`,
   `lang`, `author`, `authorTitle`. **No dates in frontmatter** — they come from git.
2. On push to `main`, a GitHub Action calls a Cloudflare Deploy Hook; the site
   rebuilds automatically.
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
