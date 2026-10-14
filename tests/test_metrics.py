"""The metrics page's text format: what the monitoring agent parses.

    python3 -m unittest tests.test_metrics -v
    gemdb tools/run_db_tests.py test_metrics

`web/metrics.py` is standard library only, so it runs under both. Both,
because a number is where the two runtimes could differ: a float that prints
as `1e-05` here and something else in the database is a page the agent
cannot read.
"""

import os
import re
import sys
import unittest

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
if WEB not in sys.path:
    sys.path.insert(0, WEB)

import metrics

#: One sample line, as the text format defines it: a name, optional labels,
#: and a number.
SAMPLE = re.compile(r'^[a-zA-Z_:][a-zA-Z0-9_:]*(\{[^}]*\})? -?[0-9.e+-]+$')


class ThePage(unittest.TestCase):
    def page(self):
        return metrics.exposition([
            ("brainfreeze_policies", "gauge", "Policies on the book.",
             [({}, 900)]),
            ("brainfreeze_claims", "gauge", "Claims filed, by outcome.",
             [({"outcome": "approved"}, 1585), ({"outcome": "refused"}, 587)]),
            ("brainfreeze_metrics_seconds", "gauge", "How long.",
             [({}, 0.25)]),
        ])

    def test_each_family_says_what_it_is_before_its_samples(self):
        lines = self.page().splitlines()
        self.assertEqual(lines[:3], [
            "# HELP brainfreeze_policies Policies on the book.",
            "# TYPE brainfreeze_policies gauge",
            "brainfreeze_policies 900"])

    def test_labels_are_quoted_and_sorted(self):
        self.assertIn('brainfreeze_claims{outcome="approved"} 1585',
                      self.page())
        self.assertEqual(metrics.label_set({"b": "2", "a": "1"}),
                         '{a="1",b="2"}')

    def test_every_sample_line_is_one_the_agent_can_parse(self):
        for line in self.page().splitlines():
            if line.startswith("#"):
                continue
            self.assertRegex(line, SAMPLE)

    def test_the_page_ends_in_a_newline(self):
        # The format requires it, and a parser that is strict about it drops
        # the last sample without one.
        self.assertTrue(self.page().endswith("\n"))

    def test_no_families_is_an_empty_page_not_an_error(self):
        self.assertEqual(metrics.exposition([]), "\n")


class TheNumbers(unittest.TestCase):
    def test_an_int_stays_an_int(self):
        self.assertEqual(metrics.number(10737418240), "10737418240")

    def test_a_float_is_written_so_it_reads_back_the_same(self):
        for value in (0.25, 0.1, 1e-05, 3.0):
            self.assertEqual(float(metrics.number(value)), value)

    def test_a_bool_is_one_or_zero(self):
        self.assertEqual(metrics.number(True), "1")
        self.assertEqual(metrics.number(False), "0")


class TheEscaping(unittest.TestCase):
    def test_a_label_value_cannot_end_its_own_quotes(self):
        self.assertEqual(metrics.label_set({"why": 'said "no"\\\n'}),
                         '{why="said \\"no\\"\\\\\\n"}')

    def test_help_cannot_start_a_new_line(self):
        self.assertEqual(metrics.escape_help("one\ntwo \\"), "one\\ntwo \\\\")


if __name__ == "__main__":
    unittest.main()
