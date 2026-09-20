"""Negative and positive tests for .scripts/check_post_preservation.py.

The checker under test is loaded from ``$BLOG_SCRIPTS_DIR`` (default: the
``.scripts`` directory next to this test package) so a mutated copy can be
tested without editing the real script.
"""

from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = Path(os.environ.get("BLOG_SCRIPTS_DIR", TESTS_DIR.parent))

BEFORE = """---
title: "Заголовок"
description: "Старое description с evidence"
slug: "post"
lang: "ru"
---

Первый абзац с [ссылкой](https://example.com/a) и числом 2 694 байта.

## Раздел

Второй абзац с `code_span` и 31 процентом.

```json
{"id": "CAV-SEM-02"}
```

| a | b |
| --- | --- |
| 1 | 2 |

- пункт один
- пункт два
"""

AFTER = """---
title: "Заголовок"
description: "Новое описание без лишних слов"
slug: "post"
lang: "ru"
---

Переписанный первый абзац с [другим текстом ссылки](https://example.com/a) и числом 2694 байта.

## Другой раздел

Переписанный второй абзац с `code_span`, `new_span` и 31 процентом.

```json
{"id": "CAV-SEM-02"}
```

| a | b |
| --- | --- |
| 1 | 2 |

- пункт раз
- пункт два
"""


def load_script():
    path = SCRIPTS_DIR / "check_post_preservation.py"
    spec = importlib.util.spec_from_file_location("blog_check_post_preservation", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CheckPostPreservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_script()
        self.temp = tempfile.TemporaryDirectory(prefix="post-preservation-tests-")
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_check(self, before: str, after: str, allow: tuple[str, ...] = ("description",)):
        before_path = self.root / "before.md"
        after_path = self.root / "after.md"
        before_path.write_text(before, encoding="utf-8")
        after_path.write_text(after, encoding="utf-8")
        argv = ["--before", str(before_path), "--after", str(after_path)]
        for key in allow:
            argv += ["--allow-frontmatter-key", key]
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = self.module.main(argv)
        return code, out.getvalue(), err.getvalue()

    # Positive control: a rewrite that changes only prose, the allowed
    # description, link text and number grouping passes every check, and the
    # added inline span is reported rather than hidden.
    def test_prose_only_rewrite_passes(self) -> None:
        code, out, err = self.run_check(BEFORE, AFTER)
        self.assertEqual(code, 0, err)
        self.assertIn("9/9 checks passed", out)
        self.assertIn("changed under allowance: ['description']", out)
        self.assertIn("added: ['new_span']", out)
        self.assertIn("numbers: 4/4 preserved", out)

    # Negative: the description change is rejected when it is not allowed, so
    # the allowance is what admits it and nothing else in the checker does.
    def test_description_change_without_allowance_fails(self) -> None:
        code, out, err = self.run_check(BEFORE, AFTER, allow=())
        self.assertEqual(code, 1)
        self.assertIn("FAIL: front-matter", err)
        self.assertIn("changed outside allowance: ['description']", err)

    # Negative: a changed slug fails even with the description allowance.
    def test_changed_slug_fails(self) -> None:
        code, out, err = self.run_check(BEFORE, AFTER.replace('slug: "post"', 'slug: "other"'))
        self.assertEqual(code, 1)
        self.assertIn("changed outside allowance: ['slug']", err)

    # Negative: a changed link destination fails and the missing URL is named.
    def test_changed_link_destination_fails(self) -> None:
        code, out, err = self.run_check(BEFORE, AFTER.replace("https://example.com/a", "https://example.com/b"))
        self.assertEqual(code, 1)
        self.assertIn("FAIL: links: 0/1 destinations preserved, 1 added", err)
        self.assertIn("missing: ['https://example.com/a']", err)

    # Negative: a dropped link (nothing added in its place) fails; this is the
    # case a checker that only looks for additions would admit.
    def test_dropped_link_fails(self) -> None:
        code, out, err = self.run_check(
            BEFORE, AFTER.replace("[другим текстом ссылки](https://example.com/a)", "текстом без ссылки")
        )
        self.assertEqual(code, 1)
        self.assertIn("FAIL: links: 0/1 destinations preserved, 0 added", err)
        self.assertIn("missing: ['https://example.com/a']", err)

    # Negative: a changed number fails, with the missing and added values named.
    def test_changed_number_fails(self) -> None:
        code, out, err = self.run_check(BEFORE, AFTER.replace("31 процентом", "32 процентом"))
        self.assertEqual(code, 1)
        self.assertIn("FAIL: numbers: 3/4 preserved, 1 added", err)
        self.assertIn("missing: ['31']; added: ['32']", err)

    # Negative (M3): a number that appears twice in the before text and once in
    # the after text fails; numbers are compared as a multiset, so a checker
    # that compares the set of distinct numbers admits this and fails here.
    # The positive control keeps both occurrences and passes.
    def test_dropped_repeated_number_fails(self) -> None:
        before = BEFORE.replace("31 процентом", "31 процентом и ещё 31 разом")
        code, out, err = self.run_check(before, AFTER.replace("31 процентом", "31 процентом и ещё 31 разом"))
        self.assertEqual(code, 0, err)
        self.assertIn("numbers: 5/5 preserved", out)
        code, out, err = self.run_check(before, AFTER)
        self.assertEqual(code, 1)
        self.assertIn("FAIL: numbers: 4/5 preserved, 0 added", err)
        self.assertIn("missing: ['31']; added: []", err)

    # Negative (M4): a link destination added with nothing removed fails, and
    # the added URL is named; a checker that only looks for missing links
    # admits this and fails here.
    def test_added_link_destination_fails(self) -> None:
        code, out, err = self.run_check(
            BEFORE, AFTER.replace("и числом 2694", "и [ещё](https://example.com/extra) числом 2694")
        )
        self.assertEqual(code, 1)
        self.assertIn("FAIL: links: 1/1 destinations preserved, 1 added", err)
        self.assertIn("missing: []; added: ['https://example.com/extra']", err)

    # Negative: a changed fenced code block fails.
    def test_changed_code_fence_fails(self) -> None:
        code, out, err = self.run_check(BEFORE, AFTER.replace("CAV-SEM-02", "CAV-SEM-03"))
        self.assertEqual(code, 1)
        self.assertIn("FAIL: code-fences: 0/1 blocks identical", err)

    # Negative: a dropped inline code span fails; additions alone do not.
    def test_dropped_inline_code_fails(self) -> None:
        code, out, err = self.run_check(BEFORE, AFTER.replace("`code_span`, ", ""))
        self.assertEqual(code, 1)
        self.assertIn("FAIL: inline-code: 0/1 spans preserved", err)
        self.assertIn("missing: ['code_span']", err)

    # Negative: a dropped heading, list item or paragraph fails the structure
    # counts; each is a separate claim about the rewrite keeping its shape.
    def test_dropped_structure_fails(self) -> None:
        code, out, err = self.run_check(BEFORE, AFTER.replace("## Другой раздел\n\n", ""))
        self.assertEqual(code, 1)
        self.assertIn("FAIL: headings", err)
        code, out, err = self.run_check(BEFORE, AFTER.replace("- пункт два\n", ""))
        self.assertEqual(code, 1)
        self.assertIn("FAIL: list-items: before 2 after 1", err)
        code, out, err = self.run_check(BEFORE, AFTER.replace("| 1 | 2 |\n", ""))
        self.assertEqual(code, 1)
        self.assertIn("FAIL: table-rows: before 3 after 2", err)

    # Negative: an unclosed fence or missing front matter is an error exit, not
    # a pass over whatever could be parsed.
    def test_unparseable_post_is_an_error(self) -> None:
        code, out, err = self.run_check(BEFORE, AFTER.replace("```\n\n| a", "\n\n| a"))
        self.assertEqual(code, 1)
        self.assertIn("ERROR: code fence is never closed", err)
        code, out, err = self.run_check(BEFORE, AFTER.split("---\n\n", 1)[1])
        self.assertEqual(code, 1)
        self.assertIn("ERROR: front matter block is missing", err)


if __name__ == "__main__":
    unittest.main()
