---
title: "Designing the Relux Works Identity With an AI Agent"
description: "How a rough two-arrow mark became a production identity through hard constraints, direct vector construction, small-size testing, and a collaboration with OpenAI Codex."
slug: "designing-relux-works-identity-with-ai"
lang: "en"
authors:
  - name: "Timur Kackan"
    title: "AI/ML Engineer, Relux Works"
    links:
      - "https://www.linkedin.com/in/timur-kachkan/"
aiSystems:
  - "OpenAI Codex"
---

A logo can be recognizable and still be unfinished.

Our first mark tried hard to explain what we do. The initial Relux Works site shipped
with an [orbital R](/blog/designing-relux-works-identity-with-ai/orbital-r.svg):
a geometric letter surrounded by paths that stood for state cycles, agents, and a
single source of truth. It had a reason for every line. It also carried the visual
memory of React and Redux, and it became fragile at the sizes where a studio logo
actually has to work.

We kept exploring. One direction turned the agent loop into four literal arrows:
observe, plan, act, verify. It explained the workflow perfectly. It also looked like
refresh, recycling, or software synchronization. A sentence in our
working identity deck became the real brief:

> The final mark keeps the motion, not the diagram.

By July we had a much stronger reference: one red chevron moving right, with a smaller
ink arrow moving northeast. The silhouette felt like delivery and improvement at the
same time. The file itself was still a raster preview with gradients, uneven geometry,
and a cramped internal gap.

That was where we brought in OpenAI Codex.

## Give the brief a spine

We began with a set of constraints strong enough to reject plausible-looking work.

The mark had to keep exactly two elements. The red chevron had to point right. The
smaller arrow had to point northeast. Every edge had to follow a 45°/90° grid,
every corner had to stay sharp, and the two shapes could never touch. No loops,
circles, extra arrows, gradients, shadows, or external-link boxes were allowed to
creep back in.

We also set a production boundary early: image generation could help with visual
exploration, while the master itself had to be constructed directly as vector paths.
No automatic trace, no generated lettering, and no attempt to clean a noisy bitmap by
adding more anchor points.

Those constraints were human decisions. They captured what the company wanted to
mean, what the mark had to preserve, and which familiar technology symbols were wrong
for us. Codex turned them into a specification that could be measured.

## Measure the feeling

The useful first step was an audit.

The upper red arm in the reference was two to three pixels heavier than the lower
one. The tip landed slightly below its best centerline. The black arrow was five
pixels wider than it was tall, its stem was only about 0.79 times the red arm weight,
and the nearest clearance changed from roughly 0.22T above to 0.36T below. That was
the source of the vague feeling that the arrow was trapped.

Codex was especially useful in this unglamorous translation. "It feels cramped"
became bounds, reflections, distances, and a measurement we could verify. The full
audit gave us the dimensions and spacing rules now recorded in the public
[brand identity reference](https://github.com/relux-works/relux-product-web-design/blob/0c5a66988ae04a1ae2128e43c1826ea88b24384d/references/brand-identity.md#fixed-identity-values).

[![The original raster symbol and lockup beside the refined production artwork](/blog/designing-relux-works-identity-with-ai/before-after.png)](/blog/designing-relux-works-identity-with-ai/before-after.png)

*The idea survived. We removed the accidental asymmetry and color variation, then
opened the internal spacing.*

## Draw in coordinates

The final symbol lives in a normalized 100 by 100 viewBox. The red chevron is the
union of two identical bars, mirrored across the horizontal centerline. Its tip sits
at `(88, 50)`. The ink arrow is symmetric around a northeast axis, and both stems use
the same base thickness, `T = 10√2`.

The
[production geometry](https://github.com/relux-works/relux-product-web-design/blob/0c5a66988ae04a1ae2128e43c1826ea88b24384d/assets/relux-symbol.svg)
is just thirteen anchor points:

```text
Red:
M48 10 L88 50 L48 90
L38 80 L68 50 L38 20 Z

Ink:
M15 63 L32 46 L26 40 L48 40
L48 62 L42 56 L25 73 Z
```

Codex wrote those paths directly and rendered them through a normal SVG toolchain.
The raster references stayed untouched. The master contains two filled paths, flat
colors, and no hidden editor debris.

The most important number was the space between them. We started with a minimum
clearance of 0.4T, then moved the black arrow within the opening before considering
any change to its shape. That order matters. A gap is part of the drawing, even though
there is nothing to select.

## Judge it at 24 pixels

At large size, both arrow candidates looked reasonable. One gave the black stem the
same weight as a red arm. The other reduced it to 95 percent, a small optical
adjustment that sounded sensible in conversation.

We rendered both at 24, 32, and 64 pixels. At 24 pixels the thinner arrow lost
presence, while the equal-weight version stayed distinct and kept the gap open. The
hierarchy already came from the arrow's smaller footprint. The 95 percent candidate
answered a theoretical concern while weakening the real-size mark.

[![Equal-weight and 95 percent arrow candidates at native and enlarged sizes](/blog/designing-relux-works-identity-with-ai/arrow-weight-comparison.png)](/blog/designing-relux-works-identity-with-ai/arrow-weight-comparison.png)

*The equal-weight candidate won at the size where the difference mattered.*

The same habit settled the micro-size question. We rendered the final master at 16,
24, 32, 48, 64, and 128 pixels, plus a 10 mm print proof. The black arrow remained
separate at 16 pixels, so a special micro redraw would have introduced another asset
without improving recognition.

[![Responsive logo tests from 16 to 128 pixels with enlarged pixel inspection](/blog/designing-relux-works-identity-with-ai/responsive-size-test.png)](/blog/designing-relux-works-identity-with-ai/responsive-size-test.png)

This changed the rhythm of the design conversation. A question no longer ended in a
long defense of one option. It ended in a sheet we could inspect together.

## The wordmark had to stop wandering

One of the best corrections arrived through an ordinary screenshot. A comparison
sheet showed two completely different wordmark styles, one serif and one sans-serif.
It looked like a design decision from a distance. Up close, it was unresolved input.

We went back to the website source and found Inter already in use. Inter Bold 700
therefore became the wordmark source. We kept an
editable live-type SVG and converted the production lockups to clean outlines. The
final horizontal lockup uses a symbol-to-cap-height ratio of 1.935 to 1, a gap of
0.476 cap height, and a small optical vertical correction for the letterforms.

We made the surrounding type roles explicit too. The approved system uses Inter Tight
for display, Inter for interface copy, and Roboto Mono for compact technical labels
and code. The public
[typography rules](https://github.com/relux-works/relux-product-web-design/blob/0c5a66988ae04a1ae2128e43c1826ea88b24384d/references/typography-and-content.md)
record those roles for future work.

## A color has to survive the interface

The reference gave us the right red: `#F60D10`. We paired it with one ink value,
`#181A18`, for both the arrow and wordmark, plus white for dark surfaces.

Then we tested the palette where it would live. Relux red works well inside the
mark and falls short of the 4.5 to 1 contrast target for ordinary text on our light
surfaces. The website therefore keeps exact red inside the mark and uses a
separate accessible semantic red ramp for links, controls, and focus. That distinction
is encoded in the public
[brand rules](https://github.com/relux-works/relux-product-web-design/blob/0c5a66988ae04a1ae2128e43c1826ea88b24384d/references/brand-identity.md),
keeping future implementation work from slowly turning every red pixel into the same
token.

## Production is where the brand became real

A clean SVG was only the middle of the job. We built horizontal and stacked lockups,
full-color, one-color, knockout, light and dark variants, favicons, avatars,
transparent PNG exports, print PDFs, EPS files, and a one-page usage guide.

This part produced the most useful failures.

The first print proof exposed a CMYK API that interpreted percentages on a zero-to-one
scale. A later independent EPS inspection found geometry with no paint operator. The
file opened and contained the right coordinates, yet a printer would have received an
empty page. We corrected the exporter to emit `eofill`, added a regression check, and
rerendered every print master.

A logo can look finished in a browser while remaining broken in production. The
final audit ran 336 checks across SVG, PNG, ICO, PDF, EPS, geometry, transparency,
color, fonts, and proof freshness. All 336 passed. The public
[release checklist](https://github.com/relux-works/relux-product-web-design/blob/0c5a66988ae04a1ae2128e43c1826ea88b24384d/references/brand-identity.md#release-checks)
carries those checks into future products.

[![Full-color, dark-background, one-color, and knockout identity proofs](/blog/designing-relux-works-identity-with-ai/identity-family-proof.png)](/blog/designing-relux-works-identity-with-ai/identity-family-proof.png)

*The open gap keeps the two-element mark recognizable in every color treatment.*

## Put it on the actual site

Brand work sharpened when it reached the website. The new lockup had to sit beside
navigation across every locale, stay left-to-right inside right-to-left layouts,
remain visible in forced colors, work as a favicon, and coexist with service pages
that already had a strong information hierarchy. Those behaviors are now part of the
public
[accessibility and direction rules](https://github.com/relux-works/relux-product-web-design/blob/0c5a66988ae04a1ae2128e43c1826ea88b24384d/references/brand-identity.md#accessibility-and-direction).

We deliberately kept the full production folder out of the landing repository. The
site imports only the approved assets it needs, regenerates the favicon and social
bundle through a repeatable build step, and hash-verifies the canonical files. That
avoids a second hand-edited logo library. The canonical web assets live in the public
[identity package](https://github.com/relux-works/relux-product-web-design/tree/0c5a66988ae04a1ae2128e43c1826ea88b24384d/assets),
and the rollout is visible on
[relux.works](https://relux.works/).

That implementation pass also corrected the relationship between identity and
interface. The logo owns the exact red. Product actions own accessible semantic
colors. The wordmark owns its outlined Inter geometry. The rest of the site remains
free to use typography as a system, without imitating the logo.

## Teach the next agent

An AI-assisted identity creates an unusual maintenance question: what will the next
agent know when it is asked to design a page six months from now?

We answered by packaging the identity as an agent-readable design skill. It includes
the approved assets, color tokens, clear-space and minimum-size rules, accessibility
requirements, forbidden transformations, localization behavior, and a release
checklist. Future agents receive the constraints that shaped the mark alongside the
files and their explanation.

The skill lives in the open-source
[Relux product web design repository](https://github.com/relux-works/relux-product-web-design/tree/0c5a66988ae04a1ae2128e43c1826ea88b24384d).
It turns brand governance into something a coding agent can read before touching a
header, social image, theme, or product page.

## What the collaboration changed

Codex shortened the distance between a design question and inspectable evidence. It
measured the references, wrote a production specification, constructed candidate
vectors, rendered real sizes, inspected the results, built the export pipeline, and
turned failures into regression checks.

Human judgment remained visible throughout the work. We chose the meaning worth
preserving, rejected the diagram that explained too much, noticed when two fonts had
entered the story, judged the candidates at native size, and set the boundary between
the corporate mark and the interface around it.

The result has two arrows, thirteen anchor points, and very little visual noise. It
also has source files, proofs, tests, usage rules, and instructions for the agents that
will work with it next. That second part is what made the identity feel like ours.
