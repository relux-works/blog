#!/usr/bin/env python3
"""Gate the prose of blog posts against the developer-writer word-choice policy.

This is a thin project entry point over ``tools/gate_word_choice.py`` from the
semantic-cores repository.  It exists for two reasons that the shared gate does
not cover on its own:

1. The shared policy lists language-independent names and canonical terms that
   every core user shares.  A blog post also names the specific projects it is
   about (``Caveman``, ``Pohuy``); those live in the blog overlay
   ``.scripts/word-choice/blog-word-choice.json`` and are merged into a
   temporary copy of the core policy before gating.  An overlay entry that the
   core already lists is refused, so the overlay stays the minimal blog-only
   delta and never silently shadows a shared decision.
2. The shared gate strips YAML front matter as non-prose.  A post's ``title``
   and ``description`` are prose that readers see on the index page, so this
   entry point gates them as a second text per post.  Both keys are required;
   a missing or empty one is refused, never reported as a clean part.
   One-line, wrapped and block (``>`` / ``|``) scalars are read whole; any
   other value shape is refused with ``FRONT_MATTER_UNSUPPORTED`` rather than
   gated in part.  The block walk itself is strict: a column-zero line that is
   neither a ``key:`` line nor a ``#`` comment is refused under any key, so a
   valid YAML key this entry point does not recognise (``description : ...``,
   ``"description": ...``) cannot be swallowed as the continuation of a
   non-gated key and make the gated key look absent.  A quoted value must end
   with its closing quote (a column-zero ``#`` line inside an open quote is
   YAML content, not a comment), and a double-quoted value may not contain a
   backslash escape, because this entry point gates source text, not the
   decoded value.
   Front matter is plain text, not Markdown, while the shared gate scans
   Markdown and blanks blockquotes, fences, inline code, links, HTML tags and
   comments before judging words.  So after the scan the entry point checks
   that every letter of the composed value was judged and refuses the value
   with ``FRONT_MATTER_UNSUPPORTED`` and the measured ratio when any were
   dropped; a clean report on a partly judged value is never accepted.

Every failure is fail-closed: a missing semantic-cores checkout, a missing
gate, an invalid overlay, or a violation in either text exits 1.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OVERLAY = REPO_ROOT / ".scripts" / "word-choice" / "blog-word-choice.json"
CORE_RELATIVE = Path("cores") / "developer-writer"
GATE_RELATIVE = Path("tools") / "gate_word_choice.py"
SEMANTIC_CORES_ENV = "SEMANTIC_CORES_DIR"

# Same rule as the shared gate: a front matter block is a leading ``---`` whose
# first line is a ``key:`` mapping line.  Anything else after ``---`` is prose
# to the shared gate, so this entry point must not read it as front matter
# either; the two would otherwise disagree about what the body is.
_FRONT_MATTER_RE = re.compile(
    r"\A---[ \t]*\n(?=[A-Za-z_][\w.-]*:(?:[ \t]|$))(.*?)\n---[ \t]*\n", re.DOTALL
)
# A key line is ``key:`` at column zero followed by whitespace or the end of
# the line; ``key:value`` is a plain scalar in YAML, not a mapping, and is
# refused by the block walk like every other unrecognised column-zero line.
_TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*):(?:[ \t]+(.*))?$")
# A block scalar header may carry a trailing YAML comment (``> # note``).
_BLOCK_SCALAR_HEADER_RE = re.compile(r"^([>|])(?:[1-9]?[+-]?|[+-]?[1-9]?)(?:[ \t]+#.*)?$")
_GATED_KEYS = ("title", "description")


class FrontMatterError(ValueError):
    """A gated front matter field whose value this entry point cannot read whole."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


class GateSetupError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


# Names this entry point calls on the shared gate.  ``_letters_by_script`` is
# the gate's own letter counter; the front matter check below must count with
# the same function the report was built from, or the two totals would not be
# comparable.  A gate without any of these is refused at load, not worked around.
_REQUIRED_GATE_API = (
    "LANGUAGE_SCRIPTS",
    "POLICY_FILE_NAME",
    "WordChoiceError",
    "load_policy",
    "scan_text",
    "_letters_by_script",
)


def load_gate_module(semantic_cores: Path) -> ModuleType:
    gate_path = semantic_cores / GATE_RELATIVE
    if not gate_path.is_file():
        raise GateSetupError(
            "GATE_MISSING",
            f"{gate_path} does not exist; pass --semantic-cores or set {SEMANTIC_CORES_ENV} "
            "to a semantic-cores checkout that contains tools/gate_word_choice.py",
        )
    spec = importlib.util.spec_from_file_location("semantic_cores_gate_word_choice", gate_path)
    if spec is None or spec.loader is None:
        raise GateSetupError("GATE_MISSING", f"{gate_path} cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    missing = [name for name in _REQUIRED_GATE_API if not hasattr(module, name)]
    if missing:
        raise GateSetupError(
            "GATE_INCOMPATIBLE", f"{gate_path} lacks {', '.join(missing)}; this entry point cannot gate with it"
        )
    return module


def _string_list(value: object, location: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise GateSetupError("OVERLAY_INVALID", f"{location} must be an array of non-empty strings")
    return list(value)


def merge_policy(core_policy_path: Path, overlay_path: Path, language: str) -> dict:
    """Return the core policy with the overlay's names and canonical terms added.

    An overlay entry already present in the core (case-insensitively) is an
    error: the overlay is the blog-only delta, not a second copy of the policy.
    """

    try:
        core = json.loads(core_policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GateSetupError("CORE_POLICY_INVALID", f"{core_policy_path}: {error}") from error
    try:
        overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GateSetupError("OVERLAY_INVALID", f"{overlay_path}: {error}") from error
    if not isinstance(overlay, dict) or not isinstance(core, dict):
        raise GateSetupError("OVERLAY_INVALID", "policy documents must be JSON objects")

    core_names = _string_list(core.get("names", []), "$.names")
    overlay_names = _string_list(overlay.get("names", []), "overlay $.names")
    core_language = core.get("languages", {}).get(language, {})
    core_canonical = _string_list(core_language.get("canonical", []), f"$.languages.{language}.canonical")
    overlay_canonical = _string_list(
        overlay.get("languages", {}).get(language, {}).get("canonical", []),
        f"overlay $.languages.{language}.canonical",
    )

    core_folded = {entry.casefold() for entry in core_names + core_canonical}
    duplicates = sorted(
        entry for entry in overlay_names + overlay_canonical if entry.casefold() in core_folded
    )
    if duplicates:
        raise GateSetupError(
            "OVERLAY_DUPLICATES_CORE",
            "overlay repeats entries the core policy already lists: " + ", ".join(duplicates),
        )

    merged = json.loads(json.dumps(core))
    merged["names"] = core_names + overlay_names
    merged.setdefault("languages", {}).setdefault(language, {})["canonical"] = (
        core_canonical + overlay_canonical
    )
    return merged


def _scalar_text(key: str, header: str, continuation: list[str]) -> str:
    """Return the whole text of one gated front matter value.

    Supports the shapes a post can use for a title or description: a one-line
    plain or quoted scalar, a quoted or plain scalar that wraps onto indented
    lines, and a folded (``>``) or literal (``|``) block scalar, with or
    without a trailing comment on the block header.  Anything else (a list, a
    nested mapping, an empty block scalar, an empty value, a quoted value
    without its closing quote, a double-quoted value with a backslash escape)
    is refused with ``FRONT_MATTER_UNSUPPORTED`` so that a partly or wrongly
    read value never passes the gate as clean text.  ``continuation`` holds
    only indented, blank and column-zero ``#`` lines: ``front_matter_text``
    refuses every other column-zero line before this function runs.
    """

    header = header.strip()
    lines: list[str] = []
    for raw in continuation:
        if not raw.strip():
            continue
        if raw[0] not in " \t":
            # A column-zero comment.  ``front_matter_text`` admits nothing else
            # here; the quote balance check below still catches a ``#`` line
            # that YAML would read as content inside an open quoted scalar.
            continue
        lines.append(raw.strip())
    block = _BLOCK_SCALAR_HEADER_RE.match(header)
    if block is not None:
        if not lines:
            raise FrontMatterError("FRONT_MATTER_UNSUPPORTED", f"{key}: block scalar has no content")
        return (" " if block.group(1) == ">" else "\n").join(lines)
    if header.startswith("- ") or header == "-":
        raise FrontMatterError("FRONT_MATTER_UNSUPPORTED", f"{key}: value is a list, not a scalar")
    if not header and lines:
        raise FrontMatterError(
            "FRONT_MATTER_UNSUPPORTED",
            f"{key}: value starts on the next line without a block scalar indicator",
        )
    if lines and (lines[0].startswith("- ") or _TOP_LEVEL_KEY_RE.match(lines[0])):
        raise FrontMatterError(
            "FRONT_MATTER_UNSUPPORTED", f"{key}: value is a list or mapping, not a scalar"
        )
    value = " ".join([header, *lines]).strip()
    if value and value[0] in "\"'":
        quote = value[0]
        if len(value) < 2 or value[-1] != quote:
            raise FrontMatterError(
                "FRONT_MATTER_UNSUPPORTED",
                f"{key}: quoted value does not end with its closing quote {quote}; "
                "a column-zero line inside the quotes is content, not a comment, and "
                "a trailing comment after a quoted value is not supported",
            )
        if quote == '"' and "\\" in value:
            raise FrontMatterError(
                "FRONT_MATTER_UNSUPPORTED",
                f"{key}: double-quoted value contains a backslash escape; this gate judges "
                "the source text, not the decoded value, so write the characters themselves",
            )
        value = value[1:-1]
    if not value.strip():
        raise FrontMatterError("FRONT_MATTER_UNSUPPORTED", f"{key} is empty")
    return value


def front_matter_text(post_text: str) -> str:
    """Return the post's title and description as one Markdown text.

    Raises FrontMatterError when the post has no front matter block
    (``FRONT_MATTER_MISSING``), when a gated key is missing or empty, when a
    column-zero line of the block is neither a ``key:`` line nor a ``#``
    comment, or when a gated value is not a scalar this entry point can read
    whole (all ``FRONT_MATTER_UNSUPPORTED``).  The caller reports every case
    as an error, never as a clean part.
    """

    match = _FRONT_MATTER_RE.match(post_text)
    if match is None:
        raise FrontMatterError("FRONT_MATTER_MISSING", "the post has no front matter block")
    block_lines = match.group(1).split("\n")
    fields: dict[str, tuple[str, list[str]]] = {}
    current: str | None = None
    for number, line in enumerate(block_lines, start=2):
        key_match = _TOP_LEVEL_KEY_RE.match(line)
        if key_match is not None:
            current = key_match.group(1)
            fields[current] = (key_match.group(2) or "", [])
            continue
        if line.strip() and line[0] not in " \t" and not line.startswith("#"):
            # Refused under every key, gated or not: a ``key :`` or ``"key":``
            # line this walk does not recognise would otherwise be swallowed
            # as the continuation of the preceding key and a gated key that
            # it names would count as absent.
            raise FrontMatterError(
                "FRONT_MATTER_UNSUPPORTED",
                f"line {number} is at column zero but is neither a `key:` line nor a `#` "
                f"comment: {line.strip()!r}; write keys as `key:` with no space before the "
                "colon and indent continuation lines",
            )
        if current is not None:
            fields[current][1].append(line)
    parts: list[str] = []
    for key in _GATED_KEYS:
        if key not in fields:
            raise FrontMatterError(
                "FRONT_MATTER_UNSUPPORTED", f"{key} missing; every post needs a title and a description"
            )
        header, continuation = fields[key]
        parts.append(_scalar_text(key, header, continuation))
    return "\n\n".join(parts) + "\n"


def check_judged_whole(gate: ModuleType, text: str, report: object) -> None:
    """Raise FrontMatterError unless every letter of *text* reached the judgment.

    The shared gate blanks Markdown structure before judging words.  A front
    matter value is plain text, so a difference between the letters in the
    composed value and the letters the report judged means part of the value
    was dropped as Markdown (a line starting with ``>``, a fence, inline code,
    a link, an HTML tag or comment) and never judged; that value is refused
    with the measured ratio instead of being reported clean.
    """

    expected = sum(gate._letters_by_script(text).values())
    judged = report.total_letters
    if judged != expected:
        raise FrontMatterError(
            "FRONT_MATTER_UNSUPPORTED",
            f"only {judged} of {expected} title/description letters were judged; the value "
            "contains Markdown syntax the gate strips (blockquote, fence, inline code, link, "
            "HTML tag or comment) and front matter is plain text, so rewrite it without that syntax",
        )


def run(
    posts: list[Path],
    language: str,
    semantic_cores: Path,
    overlay: Path,
    output_format: str,
) -> int:
    gate = load_gate_module(semantic_cores)
    if language not in gate.LANGUAGE_SCRIPTS:
        raise GateSetupError("LANGUAGE_UNSUPPORTED", f"{language!r} is not supported by the gate")
    merged = merge_policy(semantic_cores / CORE_RELATIVE / gate.POLICY_FILE_NAME, overlay, language)

    exit_code = 0
    results: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="blog-word-choice-") as temp_dir:
        core_dir = Path(temp_dir)
        (core_dir / gate.POLICY_FILE_NAME).write_text(
            json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        policy = gate.load_policy(core_dir / gate.POLICY_FILE_NAME, language)
        for post in posts:
            try:
                text = post.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as error:
                results.append({"post": str(post), "error": f"TEXT_READ_ERROR: {error}"})
                exit_code = 1
                continue
            try:
                front_matter: str | None = front_matter_text(text)
            except FrontMatterError as error:
                results.append({"post": str(post), "part": "front-matter", "error": str(error)})
                exit_code = 1
                front_matter = None
            for part, part_text in (("body", text), ("front-matter", front_matter)):
                if part_text is None:
                    continue
                try:
                    report = gate.scan_text(part_text, language, policy)
                except gate.WordChoiceError as error:
                    results.append({"post": str(post), "part": part, "error": f"{error.code}: {error.detail}"})
                    exit_code = 1
                    continue
                if part == "front-matter":
                    try:
                        check_judged_whole(gate, part_text, report)
                    except FrontMatterError as error:
                        results.append({"post": str(post), "part": part, "error": str(error)})
                        exit_code = 1
                        continue
                entry = {"post": str(post), "part": part, **report.as_json()}
                results.append(entry)
                if report.violations:
                    exit_code = 1

    if output_format == "json":
        print(json.dumps({"exit_code": exit_code, "results": results}, ensure_ascii=False, indent=2))
        return exit_code
    for entry in results:
        label = f"{entry['post']} [{entry.get('part', '-')}]"
        if "error" in entry:
            print(f"ERROR: {label}: {entry['error']}", file=sys.stderr)
            continue
        summary = (
            f"letters {entry['target_letters']}/{entry['total_letters']} in target script; "
            f"foreign words {entry['foreign_words']}: canonical {entry['canonical']}, "
            f"names {entry['names']}, identifiers {entry['identifiers']}, "
            f"violations {entry['violation_count']}"
        )
        if entry["violation_count"]:
            for violation in entry["violations"]:
                print(
                    f"{violation['code']}: {label}:{violation['line']}:{violation['column']}: "
                    f"{violation['detail']}",
                    file=sys.stderr,
                )
            print(f"FAIL: {label}: {summary}", file=sys.stderr)
        else:
            print(f"OK: {label}: {summary}")
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("posts", nargs="+", type=Path, help="Markdown posts to gate")
    parser.add_argument("--language", required=True, help="target language code, e.g. ru")
    parser.add_argument(
        "--semantic-cores",
        type=Path,
        default=os.environ.get(SEMANTIC_CORES_ENV),
        help=f"semantic-cores checkout (default: ${SEMANTIC_CORES_ENV})",
    )
    parser.add_argument("--overlay", type=Path, default=DEFAULT_OVERLAY, help="blog policy overlay")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    if args.semantic_cores is None:
        print(
            f"GATE_MISSING: pass --semantic-cores or set {SEMANTIC_CORES_ENV}",
            file=sys.stderr,
        )
        return 1
    try:
        return run(args.posts, args.language, Path(args.semantic_cores), args.overlay, args.format)
    except GateSetupError as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
