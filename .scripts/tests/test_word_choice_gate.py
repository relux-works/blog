"""Negative and positive tests for .scripts/word_choice_gate.py.

The gate under test is loaded from ``$BLOG_SCRIPTS_DIR`` (default: the
``.scripts`` directory next to this test package) so a mutated copy can be
tested without editing the real script.  ``$SEMANTIC_CORES_DIR`` must point at
a semantic-cores checkout with ``tools/gate_word_choice.py``; a missing value
fails the suite instead of skipping it, because a skipped gate test is not
evidence that the gate works.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = Path(os.environ.get("BLOG_SCRIPTS_DIR", TESTS_DIR.parent))
REPO_ROOT = TESTS_DIR.parents[1]
SEMANTIC_CORES = os.environ.get("SEMANTIC_CORES_DIR")

FRONT_MATTER = '---\ntitle: "Откат неудачного релиза"\ndescription: "{description}"\nslug: "x"\nlang: "ru"\n---\n\n'
CLEAN_DESCRIPTION = "Как мы откатили релиз после сбоя API и что показал разбор"
GRATUITOUS_DESCRIPTION = "Как мы откатили релиз после сбоя API: evidence, review и rewrite"
CLEAN_BODY = (
    "# Откат неудачного релиза\n\n"
    "После выкладки новой версии API перестал отвечать на запросы старых клиентов.\n"
    "Мы открыли pull request с откатом, попросили коллег из GitHub проверить его,\n"
    "и через десять минут команда `git revert 4f3a2c1` вернула прошлую версию.\n"
    "Мейнтейнер Caveman закрыл наш PR, а Pohuy показал рабочую сторону границы\n"
    "вместе с конфигурацией MCP.\n"
)
GRATUITOUS_BODY = (
    "# Откат неудачного релиза\n\n"
    "После выкладки новой версии API перестал отвечать на запросы старых клиентов.\n"
    "Мы собрали evidence, провели review и сделали rewrite runtime-промпта,\n"
    "чтобы каждый claim был проверяемым.\n"
)


def load_script():
    path = SCRIPTS_DIR / "word_choice_gate.py"
    spec = importlib.util.spec_from_file_location("blog_word_choice_gate", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_gate(module, argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = module.main(argv)
    return code, out.getvalue(), err.getvalue()


class WordChoiceGateTests(unittest.TestCase):
    def setUp(self) -> None:
        if not SEMANTIC_CORES:
            self.fail("SEMANTIC_CORES_DIR is not set; the gate tests need a semantic-cores checkout")
        self.semantic_cores = Path(SEMANTIC_CORES)
        self.module = load_script()
        self.temp = tempfile.TemporaryDirectory(prefix="word-choice-gate-tests-")
        self.root = Path(self.temp.name)
        self.overlay = SCRIPTS_DIR / "word-choice" / "blog-word-choice.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, name: str, description: str, body: str) -> Path:
        path = self.root / name
        path.write_text(FRONT_MATTER.format(description=description) + body, encoding="utf-8")
        return path

    def write_raw(self, name: str, front_matter_block: str, body: str) -> Path:
        """Write a post whose front matter block is given verbatim (no quoting)."""
        path = self.root / name
        path.write_text(f"---\n{front_matter_block}\n---\n\n" + body, encoding="utf-8")
        return path

    def parts(self, payload: dict) -> dict:
        return {entry["part"]: entry for entry in payload["results"]}

    def gate(self, *posts: Path, overlay: Path | None = None, semantic_cores: Path | None = None):
        argv = [str(post) for post in posts] + [
            "--language",
            "ru",
            "--semantic-cores",
            str(semantic_cores or self.semantic_cores),
            "--overlay",
            str(overlay or self.overlay),
            "--format",
            "json",
        ]
        code, out, err = run_gate(self.module, argv)
        payload = json.loads(out) if out.strip().startswith("{") else None
        return code, payload, err

    # Proves the gate is reachable and admits the approved terms: core canonical
    # (API, pull request, PR), core names (GitHub), overlay names (Caveman,
    # Pohuy) and the overlay canonical term (MCP) all pass with zero violations
    # in both the body and the front matter.
    def test_clean_post_with_overlay_terms_passes(self) -> None:
        post = self.write("clean.md", CLEAN_DESCRIPTION, CLEAN_BODY)
        code, payload, err = self.gate(post)
        self.assertEqual(code, 0, err)
        parts = {entry["part"]: entry for entry in payload["results"]}
        self.assertEqual(parts["body"]["violation_count"], 0)
        self.assertEqual(parts["front-matter"]["violation_count"], 0)
        self.assertEqual(parts["body"]["names"], 3, "GitHub, Caveman and Pohuy are names")
        self.assertGreaterEqual(parts["body"]["canonical"], 4, "API, pull request, PR, MCP are canonical")

    # Negative: gratuitous English in the body is located and fails the gate;
    # the located words are exactly the gratuitous ones, so the gate does not
    # merely reject everything.
    def test_gratuitous_english_in_body_fails(self) -> None:
        post = self.write("gratuitous.md", CLEAN_DESCRIPTION, GRATUITOUS_BODY)
        code, payload, err = self.gate(post)
        self.assertEqual(code, 1)
        body = next(entry for entry in payload["results"] if entry["part"] == "body")
        words = sorted(v["word"] for v in body["violations"])
        self.assertEqual(words, ["claim", "evidence", "review", "rewrite", "runtime"])
        self.assertIn("FOREIGN_WORD_NOT_CANONICAL", body["violations"][0]["code"])

    # Negative: gratuitous English only in the front matter description fails,
    # while the body is clean.  This is the check the shared gate does not do
    # on its own because it strips front matter as non-prose.
    def test_gratuitous_english_in_description_fails(self) -> None:
        post = self.write("description.md", GRATUITOUS_DESCRIPTION, CLEAN_BODY)
        code, payload, err = self.gate(post)
        self.assertEqual(code, 1)
        parts = {entry["part"]: entry for entry in payload["results"]}
        self.assertEqual(parts["body"]["violation_count"], 0)
        self.assertEqual(
            sorted(v["word"] for v in parts["front-matter"]["violations"]),
            ["evidence", "review", "rewrite"],
        )

    # Negative: a post without the overlay names is rejected when the overlay
    # is empty, so the pass in the first test is attributable to the overlay
    # and not to the core policy admitting Caveman/Pohuy/MCP by itself.
    def test_overlay_names_are_what_admits_project_names(self) -> None:
        empty_overlay = self.root / "empty-overlay.json"
        empty_overlay.write_text('{"names": [], "languages": {"ru": {"canonical": []}}}', encoding="utf-8")
        post = self.write("clean.md", CLEAN_DESCRIPTION, CLEAN_BODY)
        code, payload, err = self.gate(post, overlay=empty_overlay)
        self.assertEqual(code, 1)
        body = next(entry for entry in payload["results"] if entry["part"] == "body")
        self.assertEqual(sorted(v["word"] for v in body["violations"]), ["Caveman", "MCP", "Pohuy"])

    # Negative: an overlay that repeats a core entry is refused, so the overlay
    # cannot silently shadow or duplicate a shared policy decision.
    def test_overlay_duplicating_core_entry_is_refused(self) -> None:
        overlay = self.root / "dup-overlay.json"
        overlay.write_text(
            '{"names": ["GitHub"], "languages": {"ru": {"canonical": ["api"]}}}', encoding="utf-8"
        )
        post = self.write("clean.md", CLEAN_DESCRIPTION, CLEAN_BODY)
        code, payload, err = self.gate(post, overlay=overlay)
        self.assertEqual(code, 1)
        self.assertIsNone(payload)
        self.assertIn("OVERLAY_DUPLICATES_CORE", err)
        self.assertIn("GitHub", err)
        self.assertIn("api", err)

    # Negative: a semantic-cores directory without the gate fails closed with
    # GATE_MISSING; an absent gate must never read as a clean text.
    def test_missing_gate_fails_closed(self) -> None:
        fake_cores = self.root / "no-cores"
        fake_cores.mkdir()
        post = self.write("clean.md", CLEAN_DESCRIPTION, CLEAN_BODY)
        code, payload, err = self.gate(post, semantic_cores=fake_cores)
        self.assertEqual(code, 1)
        self.assertIsNone(payload)
        self.assertIn("GATE_MISSING", err)

    # Negative: a post without front matter is an error, not a clean pass.
    def test_post_without_front_matter_is_an_error(self) -> None:
        post = self.root / "bare.md"
        post.write_text(CLEAN_BODY, encoding="utf-8")
        code, payload, err = self.gate(post)
        self.assertEqual(code, 1)
        errors = [entry["error"] for entry in payload["results"] if "error" in entry]
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith("FRONT_MATTER_MISSING"), errors[0])

    # Negative (F1, gate bypass): a description written as a YAML folded or
    # literal block scalar is read whole.  The planted words sit on both the
    # first and the second continuation line, so a gate that reads only the
    # header (the original bypass, which saw the value ">") or only the first
    # continuation line fails this test; the located words must be exactly the
    # planted ones.
    def test_gratuitous_english_in_block_scalar_description_fails(self) -> None:
        for indicator in (">", "|", ">-", "|+"):
            with self.subTest(indicator=indicator):
                post = self.write_raw(
                    f"block-{len(indicator)}{indicator[0] == '|'}.md",
                    'title: "Откат неудачного релиза"\n'
                    f"description: {indicator}\n"
                    "  Как мы откатили релиз после сбоя API: evidence\n"
                    "  и что показали review и rewrite\n"
                    'slug: "x"\nlang: "ru"',
                    CLEAN_BODY,
                )
                code, payload, err = self.gate(post)
                self.assertEqual(code, 1, err)
                parts = self.parts(payload)
                self.assertEqual(parts["body"]["violation_count"], 0)
                self.assertEqual(
                    sorted(v["word"] for v in parts["front-matter"]["violations"]),
                    ["evidence", "review", "rewrite"],
                )

    # Positive control for the block scalar path: a clean folded description
    # passes, and it is gated as exactly the same text as its one-line form
    # (equal letter counts), so the pass is not the description being dropped.
    def test_clean_block_scalar_description_matches_one_line_form(self) -> None:
        one_line = self.write("one-line.md", CLEAN_DESCRIPTION, CLEAN_BODY)
        head, tail = CLEAN_DESCRIPTION.split(" после ", 1)
        code_one, payload_one, err_one = self.gate(one_line)
        self.assertEqual(code_one, 0, err_one)
        fm_one = self.parts(payload_one)["front-matter"]
        # ``> # note`` is a valid block header with a trailing YAML comment; the
        # comment is not rendered and must neither be gated nor turn the value
        # into a plain scalar that the scanner then blanks as a blockquote.
        for header in (">", "> # note"):
            with self.subTest(header=header):
                folded = self.write_raw(
                    f"folded-{len(header)}.md",
                    'title: "Откат неудачного релиза"\n'
                    f"description: {header}\n  {head}\n  после {tail}\n"
                    'slug: "x"\nlang: "ru"',
                    CLEAN_BODY,
                )
                code_folded, payload_folded, err_folded = self.gate(folded)
                self.assertEqual(code_folded, 0, err_folded)
                fm_folded = self.parts(payload_folded)["front-matter"]
                self.assertEqual(fm_folded["violation_count"], 0)
                self.assertEqual(fm_folded["total_letters"], fm_one["total_letters"])
                self.assertEqual(fm_folded["target_letters"], fm_one["target_letters"])

    # Negative: a quoted description that wraps onto an indented continuation
    # line is read whole; the planted words are only on the continuation line.
    def test_gratuitous_english_on_wrapped_quoted_description_line_fails(self) -> None:
        post = self.write_raw(
            "wrapped.md",
            'title: "Откат неудачного релиза"\n'
            'description: "Как мы откатили релиз после сбоя API\n'
            '  и что показали review и rewrite"\n'
            'slug: "x"\nlang: "ru"',
            CLEAN_BODY,
        )
        code, payload, err = self.gate(post)
        self.assertEqual(code, 1, err)
        self.assertEqual(
            sorted(v["word"] for v in self.parts(payload)["front-matter"]["violations"]),
            ["review", "rewrite"],
        )

    # Negative: a gated field whose value is not a scalar the gate can read
    # whole (a list, a nested mapping, an empty block scalar, a block scalar
    # interrupted at column zero) is refused with FRONT_MATTER_UNSUPPORTED and
    # never reported as a clean front-matter part; the body is still gated.
    def test_unsupported_description_shape_is_refused_not_passed(self) -> None:
        shapes = {
            "list": "description:\n  - evidence\n  - review",
            "mapping": "description:\n  en: evidence\n  ru: обзор",
            "empty-block": "description: >",
            "column-zero": "description: >\n  Как мы откатили релиз\n- evidence",
            "inline-list": "description: - evidence",
        }
        for name, description in shapes.items():
            with self.subTest(shape=name):
                post = self.write_raw(
                    f"{name}.md",
                    f'title: "Откат неудачного релиза"\n{description}\nslug: "x"\nlang: "ru"',
                    CLEAN_BODY,
                )
                code, payload, err = self.gate(post)
                self.assertEqual(code, 1, err)
                parts = self.parts(payload)
                self.assertEqual(parts["body"]["violation_count"], 0)
                self.assertIn("FRONT_MATTER_UNSUPPORTED", parts["front-matter"].get("error", ""))
                self.assertNotIn("violation_count", parts["front-matter"])

    # Negative (F4, repeat of the F1 class; F5 folded in): front matter is plain
    # text, but the shared scanner strips Markdown.  A value that the scanner
    # would blank in part (a line starting with ``>``, a fence line, an HTML
    # comment) or that the wrapper could skip in part (a block header with a
    # trailing comment, a ``#``-leading content line) must either have its
    # planted words located or be refused with a named error; a front-matter
    # part reported clean with ``violation_count == 0`` fails this test for
    # every fixture.  ``b5`` is the positive control: the same words in a plain
    # value are located, so the located outcomes are not the gate rejecting
    # everything.  Each fixture is driven through ``main()``.
    def test_front_matter_text_is_never_stripped_before_scanning(self) -> None:
        fixtures = {
            # header comment: valid block scalar, whole content must be judged
            "a6-header-comment": ("description: > # note\n  Как мы откатили релиз evidence", "located", ["evidence"]),
            # indented ``#``-leading content line inside a block (F5)
            "a3-hash-content-line": (
                "description: >\n  Как мы откатили релиз\n  #944 evidence review",
                "located",
                ["evidence", "review"],
            ),
            # quoted scalar whose text starts with ``>``: scanner blanks it as a blockquote
            "b1-quoted-leading-gt": ('description: "> Как мы откатили релиз: evidence review"', "refused", ["FRONT_MATTER_UNSUPPORTED"]),
            # literal block with a later ``>`` line
            "b2-literal-gt-line": ("description: |\n  Как мы откатили релиз\n  > evidence review", "refused", ["FRONT_MATTER_UNSUPPORTED"]),
            # literal block with a fence line: the scanner refuses the unclosed fence itself
            "b3-literal-fence-line": ("description: |\n  Как мы откатили релиз\n  ```\n  evidence review", "refused", ["FENCE_UNCLOSED"]),
            # HTML comment inside the value
            "b4-html-comment": ('description: "Как мы откатили релиз <!-- evidence review -->"', "refused", ["FRONT_MATTER_UNSUPPORTED"]),
            # positive control: plain value, words located
            "b5-control-plain": ('description: "Как мы откатили релиз: evidence review"', "located", ["evidence", "review"]),
            # the title is gated by the same rule: a ``>``-leading title with a clean description
            "b6-title-leading-gt": ('title: "> Откат релиза evidence"\ndescription: "Как мы откатили релиз"', "refused", ["FRONT_MATTER_UNSUPPORTED"]),
        }
        for name, (fields, outcome, expected) in fixtures.items():
            with self.subTest(fixture=name):
                if not fields.startswith("title:"):
                    fields = f'title: "Откат релиза"\n{fields}'
                post = self.write_raw(f"{name}.md", f'{fields}\nslug: "x"\nlang: "ru"', CLEAN_BODY)
                code, payload, err = self.gate(post)
                self.assertEqual(code, 1, err)
                parts = self.parts(payload)
                self.assertEqual(parts["body"]["violation_count"], 0)
                front = parts["front-matter"]
                self.assertNotEqual(front.get("violation_count"), 0, "front matter reported clean with text dropped")
                if outcome == "located":
                    self.assertNotIn("error", front)
                    self.assertEqual(sorted(v["word"] for v in front["violations"]), expected)
                else:
                    self.assertNotIn("violation_count", front)
                    self.assertIn(expected[0], front["error"])
                    if expected[0] == "FRONT_MATTER_UNSUPPORTED":
                        self.assertRegex(front["error"], r"only \d+ of \d+ title/description letters were judged")

    # Negative (F6, third repeat of the F1 class, plus the F7 bound): a valid
    # YAML front matter whose gated field the wrapper's key-line parse does not
    # recognise (``description : ...``, ``"description": ...``, the block form)
    # used to be swallowed as the continuation of the preceding *non-gated*
    # key, so the description counted as absent and the part was reported
    # clean with the title's letters alone.  The same class: a column-zero
    # ``#`` line inside an open quoted scalar is YAML content but was skipped
    # as a comment; a post with a title and no description was a clean part;
    # a double-quoted ``\u0065`` escape was judged as a digit identifier.
    # Every fixture must exit 1 and be refused with a named
    # FRONT_MATTER_UNSUPPORTED error (or locate the planted words); the
    # front-matter part must never carry ``violation_count == 0``.  ``r17``
    # shows the refusal is not tied to the preceding key being gated (it sits
    # under ``date``, ``slug`` and ``title`` alike); ``b5-control`` is the
    # positive control that the same planted words in a recognised shape are
    # located rather than everything being refused.  Each fixture is driven
    # through ``main()``.
    def test_unrecognised_front_matter_lines_and_missing_keys_are_refused(self) -> None:
        planted = "Как мы откатили релиз: evidence review"
        fixtures = {
            # F6 r1: space before the colon, preceding key not gated
            "r1-space-colon": (
                f'title: "Заголовок"\ndate: 2026-01-01\ndescription : "{planted}"',
                "refused",
                "line 4 is at column zero",
            ),
            # F6 r2: quoted key, preceding key not gated
            "r2-quoted-key": (
                f'title: "Заголовок"\ndate: 2026-01-01\n"description": "{planted}"',
                "refused",
                "line 4 is at column zero",
            ),
            # F6 r16: space before the colon on a block scalar header, under ``slug``
            "r16-space-colon-block": (
                f'title: "Заголовок"\nslug: x\ndescription : >\n  {planted}',
                "refused",
                "line 4 is at column zero",
            ),
            # F6 r17: same line directly under the gated ``title`` (already refused in rev3)
            "r17-space-colon-under-title": (
                f'title: "Заголовок"\ndescription : "{planted}"',
                "refused",
                "line 3 is at column zero",
            ),
            # F6: quoted key for the title, under a non-gated key
            "r18-quoted-title-key": (
                f'slug: x\n"title": "Заголовок"\ndescription: "{planted}"',
                "refused",
                "line 3 is at column zero",
            ),
            # F6: ``key:value`` without a space is a plain scalar in YAML, not a key line
            "r22-no-space-after-colon": (
                f'title: "Заголовок"\nslug: x\ndescription:"{planted}"',
                "refused",
                "line 4 is at column zero",
            ),
            # F6 r5: column-zero ``#`` line inside an open double-quoted scalar is content
            "r5-quoted-hash-line": (
                'title: "Заголовок"\ndescription: "Как мы откатили релиз:\n#evidence review"',
                "refused",
                "does not end with its closing quote",
            ),
            # F6 r6: same with a space after the ``#``
            "r6-quoted-wrapped-comment": (
                'title: "Заголовок"\ndescription: "Как мы откатили релиз:\n# evidence review"',
                "refused",
                "does not end with its closing quote",
            ),
            # F6: the same rule for a single-quoted title
            "r19-single-quoted-title-open": (
                "title: 'Заголовок\n# evidence\n" + f'description: "{planted}"',
                "refused",
                "does not end with its closing quote",
            ),
            # F6 r8: title present, description key absent
            "r8-title-only": ('title: "Заголовок"\nslug: x', "refused", "description missing"),
            # F6: description present and clean, title key absent
            "r7-description-only-clean": (
                f'description: "{CLEAN_DESCRIPTION}"\nslug: x',
                "refused",
                "title missing",
            ),
            # F6: gated key present but empty
            "r20-empty-title": (
                f'title: ""\ndescription: "{CLEAN_DESCRIPTION}"',
                "refused",
                "title is empty",
            ),
            "r21-empty-description": ('title: "Заголовок"\ndescription:', "refused", "description is empty"),
            # F7 r15: double-quoted escapes would be judged as digit identifiers
            "r15-full-escape": (
                'title: "Заголовок"\ndescription: "Как мы откатили релиз: \\u0065vidence \\u0072eview"',
                "refused",
                "backslash escape",
            ),
            # positive control: recognised shape, planted words located
            "b5-control-plain": (f'title: "Заголовок"\ndescription: "{planted}"', "located", ["evidence", "review"]),
        }
        for name, (fields, outcome, expected) in fixtures.items():
            with self.subTest(fixture=name):
                post = self.write_raw(f"{name}.md", fields, CLEAN_BODY)
                code, payload, err = self.gate(post)
                self.assertEqual(code, 1, err)
                parts = self.parts(payload)
                self.assertEqual(parts["body"]["violation_count"], 0)
                front = parts["front-matter"]
                self.assertNotEqual(front.get("violation_count"), 0, "front matter reported clean")
                if outcome == "located":
                    self.assertNotIn("error", front)
                    self.assertEqual(sorted(v["word"] for v in front["violations"]), expected)
                else:
                    self.assertNotIn("violation_count", front)
                    self.assertTrue(front["error"].startswith("FRONT_MATTER_UNSUPPORTED"), front["error"])
                    self.assertIn(expected, front["error"])

    # Positive control for the strict block walk: the front matter shapes the
    # tracked posts actually use (column-zero ``key:`` lines, indented list
    # and mapping continuations under ``authors``, a column-zero ``#`` comment
    # between keys, a single-quoted title) are still gated and pass, and the
    # description is gated as the same text as in the plain fixture (equal
    # letter counts), so the F6 refusals are not the walk rejecting everything.
    def test_recognised_front_matter_shapes_still_pass(self) -> None:
        plain = self.write("plain.md", CLEAN_DESCRIPTION, CLEAN_BODY)
        code_plain, payload_plain, err_plain = self.gate(plain)
        self.assertEqual(code_plain, 0, err_plain)
        fm_plain = self.parts(payload_plain)["front-matter"]
        rich = self.write_raw(
            "rich.md",
            "title: 'Откат неудачного релиза'\n"
            "# generated by hand\n"
            f'description: "{CLEAN_DESCRIPTION}"\n'
            'slug: "x"\n'
            "# a comment between keys\n"
            'lang: "ru"\n'
            "authors:\n"
            '  - name: "Ivan Oparin"\n'
            '    title: "CEO"\n'
            "    links:\n"
            '      - "https://github.com/ivanopcode"\n'
            "aiSystems:\n"
            '  - "Claude Fable 5"\n'
            "draft: false",
            CLEAN_BODY,
        )
        code, payload, err = self.gate(rich)
        self.assertEqual(code, 0, err)
        fm = self.parts(payload)["front-matter"]
        self.assertEqual(fm["violation_count"], 0)
        self.assertEqual(fm["total_letters"], fm_plain["total_letters"])
        self.assertEqual(fm["target_letters"], fm_plain["target_letters"])

    # Negative: a leading ``---`` block whose first line is not a ``key:`` line
    # is not front matter to the shared gate (it scans the block as prose), so
    # this entry point must not read it as front matter either: the part is
    # reported FRONT_MATTER_MISSING and the planted words surface in the body,
    # never in neither.
    def test_front_matter_block_must_start_with_a_key_line(self) -> None:
        post = self.write_raw(
            "comment-first.md",
            '# comment first\ntitle: "Заголовок"\ndescription: "Как мы откатили релиз: evidence review"',
            CLEAN_BODY,
        )
        code, payload, err = self.gate(post)
        self.assertEqual(code, 1, err)
        parts = self.parts(payload)
        self.assertTrue(parts["front-matter"]["error"].startswith("FRONT_MATTER_MISSING"))
        self.assertIn("evidence", [v["word"] for v in parts["body"]["violations"]])

    # Negative: a semantic-cores gate that lacks a name this entry point calls
    # (here the letter counter the front matter check depends on) is refused at
    # load with GATE_INCOMPATIBLE; the entry point does not fall back to a
    # weaker check and never reports a text clean through such a gate.
    def test_incompatible_gate_is_refused_at_load(self) -> None:
        fake_cores = self.root / "old-cores"
        (fake_cores / "tools").mkdir(parents=True)
        real_gate = (self.semantic_cores / "tools" / "gate_word_choice.py").read_text(encoding="utf-8")
        (fake_cores / "tools" / "gate_word_choice.py").write_text(
            real_gate.replace("def _letters_by_script(", "def _letters_by_script_renamed("), encoding="utf-8"
        )
        post = self.write("clean.md", CLEAN_DESCRIPTION, CLEAN_BODY)
        code, payload, err = self.gate(post, semantic_cores=fake_cores)
        self.assertEqual(code, 1)
        self.assertIsNone(payload)
        self.assertIn("GATE_INCOMPATIBLE", err)
        self.assertIn("_letters_by_script", err)

    # Positive control on the real deliverable: both tracked Russian taxonomy
    # posts pass body and front matter with zero violations.
    def test_tracked_russian_taxonomy_posts_pass(self) -> None:
        posts = [
            REPO_ROOT / "posts" / "instruction-markers-as-diagnostics.ru.md",
            REPO_ROOT / "posts" / "semantic-core-instead-of-phrasebooks.ru.md",
        ]
        code, payload, err = self.gate(*posts)
        self.assertEqual(code, 0, err)
        self.assertEqual(len(payload["results"]), 4)
        self.assertTrue(all(entry.get("violation_count") == 0 for entry in payload["results"]))


if __name__ == "__main__":
    unittest.main()
