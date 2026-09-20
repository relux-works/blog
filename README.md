# Relux Works: Blog Content

Content source for [relux.works](https://relux.works) blog. Posts live here as plain
markdown; the site pulls them at build time and derives publication metadata from
**git history**, so publication dates are publicly verifiable.

## How publishing works

1. A post is a markdown file in `posts/`, named `<slug>.<lang>.md`
   (langs: `en`, `ru`, `hy`, `ka`). Frontmatter: `title`, `description`, `slug`,
   `lang`, `authors` (array of {name, title, links[]}), `aiSystems` (list of AI generation systems that
   co-created the content of that post, e.g. "Claude Fable 5"; required for honesty). **No dates in frontmatter**: they come from git.
2. On push to `main`, a GitHub Action calls a Cloudflare Deploy Hook; the site
   rebuilds automatically.

### Drafts

Add `draft: true` to a post's frontmatter to publish it **unlisted**: it still builds
and is viewable at its normal URL (bookmark it to preview), but it is excluded from the
blog index and the sitemap, marked `noindex, nofollow`, carries no Article schema, and
shows a "Draft" banner. Push it like any post; it goes live at its URL within ~2 min,
hidden from the public. Remove the `draft` flag (or set it to `false`) to publish for real.
3. During the site build, `datePublished` is derived from the **first commit** that
   touched the file, `dateModified` from the **last commit**. Each rendered post links
   to its commit on GitHub, so anyone can verify when it was published.

## Tools

- **Git** stores post content and publication history. Add or update files under
  `posts/`, commit them, and push the reviewed branch. No generated artifacts are
  written locally.
- **GitHub Actions** runs `.github/workflows/publish.yml` after a `posts/**` change
  reaches `main`. Inspect a publication run with `gh run list --workflow publish.yml`;
  logs remain in GitHub Actions.
- **Cloudflare Deploy Hooks** rebuild the public site. The GitHub workflow calls the
  configured hook automatically; rendered posts appear at
  `https://relux.works/<lang>/blog/<slug>/`.
- **Word-choice gate** (`.scripts/word_choice_gate.py`) checks that the prose of a
  non-English post uses its own language by default, admitting foreign words only
  as canonical terms, listed names, identifiers or quotations. It wraps
  `tools/gate_word_choice.py` from the
  [semantic-cores](https://github.com/relux-works/semantic-cores) repository and
  merges the blog-only overlay `.scripts/word-choice/blog-word-choice.json`
  (project names such as `Caveman`, `Pohuy`; the `MCP` acronym) into the shared
  policy; an overlay entry the core already lists is refused. Body and front
  matter (`title`, `description`) are gated as separate texts. Both keys are
  required: a missing or empty one is refused, never reported as a clean part.
  The front matter block must start with a `key:` line (the same rule the
  shared gate uses to tell front matter from prose), every key line is `key:`
  at column zero with no space before the colon and a space or line end after
  it, continuation lines are indented, and the only other column-zero lines
  allowed are `#` comments; any other column-zero line (`key :`, `"key":`,
  `key:value`) is refused with `FRONT_MATTER_UNSUPPORTED` under every key, so
  a gated key the walk did not recognise can never be swallowed as part of a
  neighbouring key and count as absent. A gated value is read whole whether it
  is a one-line, wrapped or block (`>` / `|`, with or without a trailing
  `# comment`) scalar; any other value shape, a quoted value without its
  closing quote (a trailing comment after a quoted value is not supported) and
  a double-quoted value containing a backslash escape (the gate judges source
  text, not the decoded value) are refused with `FRONT_MATTER_UNSUPPORTED`
  instead of being gated in part. Front matter is plain text while the shared
  gate scans Markdown, so a value containing anything the scanner strips (a
  line starting with `>`, a code fence, inline code, a link or URL, an HTML tag
  or comment) is also refused with `FRONT_MATTER_UNSUPPORTED` and the measured
  ratio of letters judged; write such values as plain words instead. Known
  bound: a trailing ` # comment` on a plain (unquoted) scalar is gated as text,
  which can only add violations, never hide them. Run:
  `SEMANTIC_CORES_DIR=/path/to/semantic-cores python3 .scripts/word_choice_gate.py posts/<slug>.ru.md --language ru`
  (add `--format json` for machine-readable counts). Exit 0 only when every
  text has zero violations; a missing checkout, a missing gate or a gate
  without the functions this entry point calls (`GATE_INCOMPATIBLE`) fails closed.
- **Post preservation check** (`.scripts/check_post_preservation.py`) compares a
  post before and after a rewrite and fails when front matter (except keys named
  with `--allow-frontmatter-key`), link destinations, fenced code, inline code
  spans, numbers, heading levels, table rows, list items or paragraph count
  differ. Run:
  `python3 .scripts/check_post_preservation.py --before <old.md> --after posts/<slug>.ru.md --allow-frontmatter-key description`.
- **Script tests** (`.scripts/tests/`) hold the negative and positive controls for
  both scripts. Run `SEMANTIC_CORES_DIR=/path/to/semantic-cores python3 -m unittest discover -s .scripts/tests`.
  Logs, before-copies and mutant runs from a rewrite task go under
  `.temp/<TASK-ID>/`, which the tracked `.gitignore` excludes.

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
