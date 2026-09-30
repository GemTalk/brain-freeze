"""Reading docs/mcp-questions.md: the questions, their answers, and the preamble."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mcp_questions


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
        promises = mcp_questions.promises(self.DOC)
        self.assertEqual(len(promises), 2)
        self.assertEqual(promises[0].code, "analysis.book_summary(book)")
        self.assertEqual(promises[0].answer, "{'policies': 900}")
        self.assertEqual(promises[1].answer, "{'Medium': 0.729}")

    def test_it_keeps_the_question_title_so_a_failure_names_itself(self):
        self.assertEqual(mcp_questions.promises(self.DOC)[1].title,
                         "2. Loss ratio by tier?")

    def test_a_multi_line_snippet_survives_intact(self):
        doc = ("## 1. Why?\n\n```python\n[x\n for x in y]\n```\n\n```\n[]\n```\n")
        self.assertEqual(mcp_questions.promises(doc)[0].code, "[x\n for x in y]")

    def test_the_preamble_block_is_not_mistaken_for_a_question(self):
        """The doc opens with a preamble snippet that has no answer under it."""
        doc = ("# Questions\n\n"
               "```python\nimport gemdb\n```\n\n"
               "---\n\n"
               "## 1. Real?\n\n```python\nq()\n```\n\n```\n42\n```\n")
        promises = mcp_questions.promises(doc)
        self.assertEqual([p.code for p in promises], ["q()"])


class PublishedPreambleTests(unittest.TestCase):
    """The verifier must run what the document publishes, not its own copy.

    A preamble executed but not printed could leave the published one unable
    to run the questions beneath it, and nothing would notice. Reading it back
    from the document makes that impossible.
    """

    def test_it_lifts_the_preamble_block_from_above_the_first_heading(self):
        doc = ("# Questions\n\nProse.\n\n"
               "```python\nimport gemdb\nbook = gemdb.root['x']\n```\n\n"
               "---\n\n## 1. Real?\n\n```python\nq()\n```\n\n```\n42\n```\n")
        self.assertEqual(mcp_questions.published_preamble(doc),
                         "import gemdb\nbook = gemdb.root['x']")

    def test_it_does_not_take_a_question_snippet_as_the_preamble(self):
        doc = "# Questions\n\n## 1. Real?\n\n```python\nq()\n```\n\n```\n42\n```\n"
        self.assertIsNone(mcp_questions.published_preamble(doc))

    def test_the_real_document_publishes_a_preamble_that_binds_brainfreeze(self):
        """Question 6 calls `brainfreeze.score_breakdown`, so the name has to
        be bound by the preamble a reader is told to paste."""
        with open(mcp_questions.DOC) as handle:
            published = mcp_questions.published_preamble(handle.read())
        self.assertIsNotNone(published)
        self.assertIn("import brainfreeze", published)


if __name__ == "__main__":
    unittest.main()
