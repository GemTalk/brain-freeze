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
from datetime import date

from brainfreeze import analysis
from brainfreeze.money import usd
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
        self.assertEqual(s["premium"], usd("92081.22"))
        self.assertEqual(s["paid"], usd("54671.44"))
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

    def test_the_published_answer_has_not_moved(self):
        # docs/mcp-questions.md prints this list under question 4. Grouping
        # by rule is a new question, not a new answer to this one, so this
        # asserts the whole thing rather than its first two rows.
        self.assertEqual(analysis.denial_reasons(self.book), [
            ("Policy lapsed", 254),
            ("Exceeded annual claim limit", 183),
            ("Pre-existing headache condition exclusion", 15),
            ("Claim amount exceeds per-incident coverage limit", 10),
            ("Insufficient severity documented", 10),
            ("Filed outside claim window", 9),
        ])

    def test_every_denial_reason_is_one_the_rules_can_give(self):
        # or one the generator's unmodelled denials produce -- either way a
        # refusal without a reason is a bug.
        for reason, count in analysis.denial_reasons(self.book):
            self.assertTrue(reason)
            self.assertGreater(count, 0)


class DenialRules(unittest.TestCase):
    """#49: the same refusals, grouped by identifier instead of by English.

    `denial_reasons` stays exactly as it was -- its output is published in
    docs/mcp-questions.md and an agent may already be reading it. This is a
    sibling, because the two count different things: prose counts what
    claimants were told, including 44 refusals no rule produced.
    """

    @classmethod
    def setUpClass(cls):
        cls.book = seed.load()

    def test_it_groups_by_identifier(self):
        rules = analysis.denial_rules(self.book)
        self.assertEqual(rules[0], ("policy-lapsed", 254))
        self.assertEqual(rules[1], ("annual-claim-count-cap", 183))

    def test_it_accounts_for_every_refusal(self):
        # 2172 claims, 1691 approved. Nothing may be dropped on the way to an
        # identifier, or the counts quietly stop adding up.
        self.assertEqual(sum(count for _, count in analysis.denial_rules(self.book)),
                         2172 - 1691)

    def test_refusals_no_rule_produced_are_not_claimed_as_rules(self):
        # 15 + 10 + 10 + 9 of the generator's unmodelled denials.
        self.assertEqual(dict(analysis.denial_rules(self.book))["unclassified"], 44)

    def test_it_is_ordered_the_same_way_denial_reasons_is(self):
        rules = analysis.denial_rules(self.book)
        self.assertEqual(rules, sorted(rules, key=lambda pair: (-pair[1], pair[0])))

    def test_a_claim_that_stored_its_rule_is_read_from_the_rule(self):
        # A claim filed by the app carries `rule` outright. One loaded from
        # the committed CSVs has only prose, and is mapped back.
        from brainfreeze.model import Book, Claim, Event, Policyholder
        book = Book()
        policy = Policyholder(
            policy_id="BF-TEST", age=10, sex=None, migraine_history=False,
            tension_type_headache_history=False,
            typical_consumption_speed="fast", favourite_trigger="slushie",
            underwriting_base=45.0, plan_name="Standard",
            annual_premium=usd("171.00"), policy_start_date=date(2026, 1, 1))
        book.add(policy)
        for n, claim in enumerate((
                Claim("CLM-1", usd("10.00"), usd("0.00"), "Denied",
                      reason="Reworded next Tuesday", rule="policy-lapsed"),
                Claim("CLM-2", usd("10.00"), usd("0.00"), "Denied",
                      reason="Policy lapsed"),
                Claim("CLM-3", usd("10.00"), usd("0.00"), "Denied"))):
            policy.add_event(Event("EVT-00000%d" % n, date(2026, 6, 1),
                                   "slushie", -5.0, 250.0, "fast", True,
                                   claim=claim))
        self.assertEqual(analysis.denial_rules(book),
                         [("policy-lapsed", 2), ("unrecorded", 1)])


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
        self.assertEqual(analysis.denial_rules(self.book), [])
        self.assertEqual(analysis.top_n_by_loss_ratio(self.book, 5), [])


if __name__ == "__main__":
    unittest.main()
