#!/usr/bin/env python3
"""Check that a rewritten post preserves everything a rewrite must not change.

Compares a ``before`` and an ``after`` Markdown post and fails when any of the
following differs:

- front matter, key by key, except keys explicitly allowed with
  ``--allow-frontmatter-key`` (the allowance is reported, never silent);
- the multiset of link destinations (``](url)`` and bare URLs);
- fenced code blocks, in order and byte for byte;
- inline code spans: every span of ``before`` must survive; added spans are
  reported as additions so the review can judge them;
- the multiset of numbers in prose (digits, with a thin/regular space or comma
  group separator collapsed, so ``2 694`` and ``2694`` are the same number);
- the sequence of heading levels, the number of table rows, the number of list
  items and the number of paragraphs.

Each check prints a measured ratio.  Exit 0 only when every check passes.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_FRONT_MATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n", re.DOTALL)
_FENCE_RE = re.compile(r"^[ \t]{0,3}(```|~~~)")
_INLINE_CODE_RE = re.compile(r"(`+)(?!`)(.+?)(?<!`)\1(?!`)")
_LINK_DEST_RE = re.compile(r"\]\(([^\s()]+)(?:[ \t]+\"[^\"]*\")?\)")
_BARE_URL_RE = re.compile(r"(?<![(\"'<])(?:https?://)[^\s<>()\[\]]+")
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+\S")
_TABLE_ROW_RE = re.compile(r"^[ \t]{0,3}\|.*\|[ \t]*$")
_LIST_ITEM_RE = re.compile(r"^[ \t]{0,3}(?:[-*+]|\d+\.)[ \t]+\S")
_NUMBER_RE = re.compile(r"\d+(?:[   ,]\d{3})*(?:[.,]\d+)?")
_TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*):", re.MULTILINE)


@dataclass
class Check:
    name: str
    passed: bool
    measured: str
    detail: str = ""


@dataclass
class Post:
    front_matter: dict[str, str]
    fences: list[str]
    prose: str
    inline_code: Counter
    links: Counter
    numbers: Counter
    heading_levels: list[int]
    table_rows: int
    list_items: int
    paragraphs: int


def _front_matter(text: str) -> tuple[dict[str, str], str]:
    match = _FRONT_MATTER_RE.match(text)
    if match is None:
        raise ValueError("front matter block is missing")
    block = match.group(1)
    keys = [(m.group(1), m.start()) for m in _TOP_LEVEL_KEY_RE.finditer(block)]
    fields: dict[str, str] = {}
    for index, (key, start) in enumerate(keys):
        end = keys[index + 1][1] if index + 1 < len(keys) else len(block)
        fields[key] = block[start:end].rstrip("\n")
    return fields, text[match.end():]


def parse(text: str) -> Post:
    front_matter, body = _front_matter(text)
    fences: list[str] = []
    prose_lines: list[str] = []
    current: list[str] | None = None
    fence_marker = None
    for line in body.split("\n"):
        fence = _FENCE_RE.match(line)
        if current is None:
            if fence is not None:
                current = [line]
                fence_marker = fence.group(1)
            else:
                prose_lines.append(line)
        else:
            current.append(line)
            if fence is not None and fence.group(1) == fence_marker:
                fences.append("\n".join(current))
                current = None
    if current is not None:
        raise ValueError("code fence is never closed")
    prose = "\n".join(prose_lines)

    inline_code = Counter(match.group(2) for match in _INLINE_CODE_RE.finditer(prose))
    links = Counter(_LINK_DEST_RE.findall(prose))
    links.update(_BARE_URL_RE.findall(_LINK_DEST_RE.sub("]()", prose)))

    stripped = _INLINE_CODE_RE.sub(" ", prose)
    stripped = _LINK_DEST_RE.sub("]()", stripped)
    stripped = _BARE_URL_RE.sub(" ", stripped)
    numbers = Counter(
        re.sub(r"[   ,](?=\d{3})", "", match.group(0)) for match in _NUMBER_RE.finditer(stripped)
    )

    heading_levels = [len(m.group(1)) for line in prose_lines if (m := _HEADING_RE.match(line))]
    table_rows = sum(1 for line in prose_lines if _TABLE_ROW_RE.match(line))
    list_items = sum(1 for line in prose_lines if _LIST_ITEM_RE.match(line))
    paragraphs = sum(1 for block in re.split(r"\n[ \t]*\n", prose) if block.strip())
    return Post(
        front_matter=front_matter,
        fences=fences,
        prose=prose,
        inline_code=inline_code,
        links=links,
        numbers=numbers,
        heading_levels=heading_levels,
        table_rows=table_rows,
        list_items=list_items,
        paragraphs=paragraphs,
    )


def _counter_diff(before: Counter, after: Counter) -> tuple[list[str], list[str]]:
    missing = sorted((before - after).elements())
    added = sorted((after - before).elements())
    return missing, added


def compare(before: Post, after: Post, allowed_keys: set[str]) -> list[Check]:
    checks: list[Check] = []

    keys = sorted(set(before.front_matter) | set(after.front_matter))
    changed = [key for key in keys if before.front_matter.get(key) != after.front_matter.get(key)]
    unexpected = [key for key in changed if key not in allowed_keys]
    allowed_changed = [key for key in changed if key in allowed_keys]
    checks.append(
        Check(
            "front-matter",
            not unexpected,
            f"{len(keys) - len(changed)}/{len(keys)} keys byte-identical",
            (f"changed outside allowance: {unexpected}; " if unexpected else "")
            + (f"changed under allowance: {allowed_changed}" if allowed_changed else ""),
        )
    )

    missing, added = _counter_diff(before.links, after.links)
    total = sum(before.links.values())
    checks.append(
        Check(
            "links",
            not missing and not added,
            f"{total - len(missing)}/{total} destinations preserved, {len(added)} added",
            f"missing: {missing}; added: {added}" if missing or added else "",
        )
    )

    same_fences = before.fences == after.fences
    checks.append(
        Check(
            "code-fences",
            same_fences,
            f"{sum(1 for b, a in zip(before.fences, after.fences) if b == a)}/{len(before.fences)} "
            f"blocks identical, {len(after.fences)} after",
            "" if same_fences else "fenced code differs",
        )
    )

    missing, added = _counter_diff(before.inline_code, after.inline_code)
    total = sum(before.inline_code.values())
    checks.append(
        Check(
            "inline-code",
            not missing,
            f"{total - len(missing)}/{total} spans preserved, {len(added)} added",
            (f"missing: {missing}; " if missing else "") + (f"added: {added}" if added else ""),
        )
    )

    missing, added = _counter_diff(before.numbers, after.numbers)
    total = sum(before.numbers.values())
    checks.append(
        Check(
            "numbers",
            not missing and not added,
            f"{total - len(missing)}/{total} preserved, {len(added)} added",
            f"missing: {missing}; added: {added}" if missing or added else "",
        )
    )

    checks.append(
        Check(
            "headings",
            before.heading_levels == after.heading_levels,
            f"levels before {before.heading_levels} after {after.heading_levels}",
        )
    )
    for name, b, a in (
        ("table-rows", before.table_rows, after.table_rows),
        ("list-items", before.list_items, after.list_items),
        ("paragraphs", before.paragraphs, after.paragraphs),
    ):
        checks.append(Check(name, b == a, f"before {b} after {a}"))
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument(
        "--allow-frontmatter-key",
        action="append",
        default=[],
        metavar="KEY",
        help="front matter key that may change (reported, not silent)",
    )
    args = parser.parse_args(argv)
    try:
        before = parse(args.before.read_text(encoding="utf-8"))
        after = parse(args.after.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    checks = compare(before, after, set(args.allow_frontmatter_key))
    failed = [check for check in checks if not check.passed]
    for check in checks:
        status = "OK" if check.passed else "FAIL"
        line = f"{status}: {check.name}: {check.measured}"
        if check.detail:
            line += f" ({check.detail})"
        print(line, file=sys.stderr if not check.passed else sys.stdout)
    print(f"{'FAIL' if failed else 'OK'}: {len(checks) - len(failed)}/{len(checks)} checks passed for {args.after}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
