"""The analysis helpers, against the CSVs actually in the repo.

Run: python3 -m unittest tests.test_analysis -v

These exist so an agent composes rather than derives. The MCP surface offers
no tool that knows what a policyholder is -- it runs Python inside the
database -- so "loss ratio by risk tier" is answered by calling a named
function, not by an agent reinventing the aggregation and getting the
denominator wrong.

Every figure below was read out of data/*.csv by a separate script, not taken
from what these functions returned.
"""

import unittest

from brainfreeze import analysis
import seed


class Aggregates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = seed.load()

    def test_the_headline_figures(self):
        s = analysis.book_summary(self.book)
        self.assertEqual(s["policies"], 900)
        self.assertEqual(s["events"], 4993)
        self.assertEqual(s["claims"], 2172)
        self.assertEqual(s["approved"], 1691)
        self.assertEqual(s["premium"], 92081.22)
        self.assertEqual(s["paid"], 54671.44)
        self.assertEqual(s["loss_ratio"], 0.594)

    def test_loss_ratio_by_tier(self):
        # The demo's punchline: the 1.9x High loading over-prices the risk, so
        # the riskiest customers are the most profitable and Medium is the
        # band losing money relative to its price.
        self.assertEqual(analysis.loss_ratio_by_tier(self.book),
                         {"Low": 0.409, "Medium": 0.729, "High": 0.501})

    def test_loss_ratio_by_plan(self):
        self.assertEqual(analysis.loss_ratio_by_plan(self.book),
                         {"Basic": 0.493, "Standard": 0.771, "Premium": 0.455})

    def test_least_profitable_plan(self):
        self.assertEqual(analysis.least_profitable_plan(self.book),
                         ("Standard", 0.771))

    def test_claim_approval_rate(self):
        self.assertEqual(analysis.claim_approval_rate(self.book), 0.7785)

    def test_denial_reasons_are_ordered_by_how_often_they_bite(self):
        reasons = analysis.denial_reasons(self.book)
        self.assertEqual(reasons[0], ("Policy lapsed", 254))
        self.assertEqual(reasons[1], ("Exceeded annual claim limit", 183))
        self.assertEqual(sum(count for _, count in reasons),
                         2172 - 1691)

    def test_every_denial_reason_is_one_the_rules_can_give(self):
        # or one the generator's unmodelled denials produce -- either way a
        # refusal without a reason is a bug.
        for reason, count in analysis.denial_reasons(self.book):
            self.assertTrue(reason)
            self.assertGreater(count, 0)


class Rankings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = seed.load()

    def test_top_by_expected_claims_ignores_thin_histories(self):
        # A policy with two treats and two claims scores 100% and means
        # nothing. The guard is the whole point of the function.
        top = analysis.top_n_by_expected_claims(self.book, 3)
        self.assertEqual([p.policy_id for p, _ in top],
                         ["BF-100052", "BF-100083", "BF-100098"])
        self.assertEqual(top[0][1], 0.8)
        for policyholder, _ in top:
            self.assertGreaterEqual(len(policyholder.events), 5)

    def test_a_thinner_guard_admits_more_policies(self):
        loose = analysis.top_n_by_expected_claims(self.book, 3, min_events=8)
        self.assertEqual([p.policy_id for p, _ in loose],
                         ["BF-100015", "BF-100043", "BF-100045"])
        self.assertEqual(loose[0][1], 0.5)

    def test_top_by_loss_ratio_finds_the_underpriced(self):
        top = analysis.top_n_by_loss_ratio(self.book, 3)
        self.assertEqual([p.policy_id for p, _ in top],
                         ["BF-100813", "BF-100367", "BF-100495"])
        self.assertEqual(top[0][1], 2.728)

    def test_rankings_are_stable(self):
        # Ties are broken by policy_id, so an agent asked the same question
        # twice gets the same answer and a demo does not wobble.
        self.assertEqual(analysis.top_n_by_loss_ratio(self.book, 5),
                         analysis.top_n_by_loss_ratio(self.book, 5))
        self.assertEqual(
            [p.policy_id for p, _ in analysis.top_n_by_expected_claims(self.book, 5)],
            [p.policy_id for p, _ in analysis.top_n_by_expected_claims(self.book, 5)])

    def test_asking_for_more_than_there_is_returns_what_there_is(self):
        self.assertEqual(len(analysis.top_n_by_loss_ratio(self.book, 10000)),
                         len(self.book))


class EmptyBook(unittest.TestCase):
    """A fresh book answers rather than dividing by zero.

    The app creates policies with no events, and CUJ-1 looks at one straight
    after taking it out.
    """

    def setUp(self):
        from brainfreeze.model import Book
        self.book = Book()

    def test_summary_of_nothing(self):
        s = analysis.book_summary(self.book)
        self.assertEqual(s["policies"], 0)
        self.assertEqual(s["events"], 0)
        self.assertIsNone(s["loss_ratio"])

    def test_rates_of_nothing_are_none_not_zero(self):
        # 0.0 would claim every claim was refused, which is a different fact.
        self.assertIsNone(analysis.claim_approval_rate(self.book))
        self.assertIsNone(analysis.least_profitable_plan(self.book))

    def test_aggregates_of_nothing_are_empty(self):
        self.assertEqual(analysis.loss_ratio_by_tier(self.book), {})
        self.assertEqual(analysis.denial_reasons(self.book), [])
        self.assertEqual(analysis.top_n_by_loss_ratio(self.book, 5), [])


if __name__ == "__main__":
    unittest.main()
