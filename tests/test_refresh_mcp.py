"""The pure parts of refresh_mcp.py: reading stamps and reading the promises.

The network, topaz and the router are not exercised here. What is exercised is
everything that decides *whether* to act and *what counts as correct*, because
those are what silently rot when the upstream server moves.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import refresh_mcp


class StampTests(unittest.TestCase):
    def test_it_reads_the_commit_out_of_a_stamp(self):
        stamp = "mcp=3c08dde\ncommit=3c08dde\n"
        self.assertEqual(refresh_mcp.parse_stamp(stamp)["commit"], "3c08dde")

    def test_it_survives_a_stamp_carrying_keys_it_does_not_know(self):
        stamp = "mcp=v0.7.0\ncommit=abc1234\nurl=https://example.invalid\n"
        parsed = refresh_mcp.parse_stamp(stamp)
        self.assertEqual(parsed["commit"], "abc1234")
        self.assertEqual(parsed["url"], "https://example.invalid")

    def test_a_stamp_with_no_commit_reads_as_unknown_rather_than_raising(self):
        self.assertIsNone(refresh_mcp.parse_stamp("mcp=v0.7.0\n").get("commit"))


class DriftTests(unittest.TestCase):
    def test_the_same_sha_is_not_drift(self):
        self.assertFalse(refresh_mcp.has_drifted("3c08dde", "3c08dde"))

    def test_a_short_sha_matching_the_head_of_a_long_one_is_not_drift(self):
        self.assertFalse(refresh_mcp.has_drifted("3c08dde", "3c08dde9f1a2b3c4"))

    def test_a_different_sha_is_drift(self):
        self.assertTrue(refresh_mcp.has_drifted("3c08dde", "deadbee"))

    def test_nothing_staged_is_drift(self):
        self.assertTrue(refresh_mcp.has_drifted(None, "3c08dde"))


class PromiseTests(unittest.TestCase):
    """docs/mcp-questions.md is the pinned expectation, so parsing it is the
    part that must not be approximate."""

    DOC = (
        "# Questions\n\n"
        "## 1. How big is this book?\n\n"
        "Some prose.\n\n"
        "```python\n"
        "analysis.book_summary(book)\n"
        "```\n\n"
        "```\n"
        "{'policies': 900}\n"
        "```\n\n"
        "## 2. Loss ratio by tier?\n\n"
        "```python\n"
        "analysis.loss_ratio_by_tier(book)\n"
        "```\n\n"
        "```\n"
        "{'Medium': 0.729}\n"
        "```\n"
    )

    def test_it_pairs_each_snippet_with_the_answer_beneath_it(self):
        promises = refresh_mcp.promises(self.DOC)
        self.assertEqual(len(promises), 2)
        self.assertEqual(promises[0].code, "analysis.book_summary(book)")
        self.assertEqual(promises[0].answer, "{'policies': 900}")
        self.assertEqual(promises[1].answer, "{'Medium': 0.729}")

    def test_it_keeps_the_question_title_so_a_failure_names_itself(self):
        self.assertEqual(refresh_mcp.promises(self.DOC)[1].title,
                         "2. Loss ratio by tier?")

    def test_a_multi_line_snippet_survives_intact(self):
        doc = ("## 1. Why?\n\n```python\n[x\n for x in y]\n```\n\n```\n[]\n```\n")
        self.assertEqual(refresh_mcp.promises(doc)[0].code, "[x\n for x in y]")

    def test_the_preamble_block_is_not_mistaken_for_a_question(self):
        """The doc opens with a preamble snippet that has no answer under it."""
        doc = ("# Questions\n\n"
               "```python\nimport gemdb\n```\n\n"
               "---\n\n"
               "## 1. Real?\n\n```python\nq()\n```\n\n```\n42\n```\n")
        promises = refresh_mcp.promises(doc)
        self.assertEqual([p.code for p in promises], ["q()"])


if __name__ == "__main__":
    unittest.main()
