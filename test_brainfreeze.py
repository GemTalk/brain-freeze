"""The model, pinned against rows that are actually in the shipped CSVs.

Run: python3 -m unittest test_brainfreeze -v

These are not unit tests for their own sake. Every number below was read out
of policyholders.csv or claims.csv, so if the app and the sample data ever
start disagreeing, this is what says so.
"""

import unittest

from brainfreeze import (
    adjudicate,
    annual_premium,
    assess_amount,
    quote,
    risk_score,
    risk_tier,
)


class Underwriting(unittest.TestCase):
    def test_the_quote_shown_in_the_mockups(self):
        # age 11, eats fast, favourite is a slushie, no headache history
        q = quote(11, False, False, "fast", "slushie")
        self.assertEqual(q.score, 75.0)          # 45 + 18 + 12
        self.assertEqual(q.tier, "High")
        self.assertEqual(q.plans["Basic"]["annual"], 85.50)
        self.assertEqual(q.plans["Standard"]["annual"], 171.00)
        self.assertEqual(q.plans["Premium"]["annual"], 342.00)
        self.assertEqual(q.plans["Standard"]["monthly"], 14.25)

    def test_low_tier_prices(self):
        self.assertEqual(round(annual_premium("Basic", "Low"), 2), 31.50)
        self.assertEqual(round(annual_premium("Standard", "Low"), 2), 63.00)
        self.assertEqual(round(annual_premium("Premium", "Low"), 2), 126.00)

    def test_band_edges(self):
        self.assertEqual(risk_tier(33.9), "Low")
        self.assertEqual(risk_tier(34.0), "Medium")
        self.assertEqual(risk_tier(66.9), "Medium")
        self.assertEqual(risk_tier(67.0), "High")

    def test_score_is_clamped(self):
        # young, migraine, tension headache, eats fast, worst trigger
        self.assertEqual(risk_score(8, True, True, "fast", "slushie"), 100.0)
        # a score cannot fall below 1 however favourable the answers
        self.assertGreaterEqual(risk_score(16, False, False, "slow", "smoothie", base=-500), 1.0)

    def test_breakdown_sums_to_the_score(self):
        q = quote(11, False, False, "fast", "slushie")
        self.assertEqual(round(sum(points for _, points in q.breakdown), 1), q.score)


class Adjudication(unittest.TestCase):
    def test_clm_000059_approved(self):
        # BF-100023, Standard: $60 limit, $5 deductible, three approvals used
        d = adjudicate(62.77, 60.0, 5.0, 3)
        self.assertEqual(d.status, "Approved")
        self.assertEqual(d.amount, 55.00)
        self.assertEqual(d.capped_by_limit, 2.77)
        self.assertEqual(d.deductible_applied, 5.00)

    def test_clm_000060_hits_the_annual_cap(self):
        d = adjudicate(38.68, 60.0, 5.0, 4)
        self.assertEqual(d.status, "Denied")
        self.assertEqual(d.amount, 0.0)
        self.assertEqual(d.reason, "Exceeded annual claim limit")

    def test_the_other_three_approvals_on_bf_100023(self):
        for assessed, expected in ((63.05, 55.00), (37.70, 32.70), (55.73, 50.73)):
            d = adjudicate(assessed, 60.0, 5.0, 0)
            self.assertEqual(d.amount, expected, assessed)

    def test_below_the_deductible_is_a_denial_not_a_zero_payment(self):
        d = adjudicate(8.00, 25.0, 10.0, 0)
        self.assertEqual(d.status, "Denied")
        self.assertEqual(d.reason, "Claim amount below deductible")

    def test_the_cap_short_circuits_everything(self):
        d = adjudicate(200.00, 150.0, 0.0, 4)
        self.assertEqual(d.status, "Denied")
        self.assertEqual(d.amount, 0.0)

    def test_premium_plan_has_no_deductible(self):
        d = adjudicate(120.00, 150.0, 0.0, 0)
        self.assertEqual(d.amount, 120.00)
        self.assertEqual(d.deductible_applied, 0.0)


class Assessment(unittest.TestCase):
    def test_the_claimant_never_enters_a_figure(self):
        # pain 4.9 over 522.2s, the CLM-000059 episode, before jitter
        self.assertEqual(assess_amount(4.9, 522.2), 65.51)

    def test_bounds(self):
        self.assertEqual(assess_amount(0, 0), 10.0)
        # the worst episode the generator can produce is nowhere near the cap
        self.assertEqual(assess_amount(10, 900), 115.0)
        # the floor and ceiling only bite with the generator's jitter on top
        self.assertEqual(assess_amount(0, 0, jitter=-50), 5.0)
        self.assertEqual(assess_amount(10, 900, jitter=500), 200.0)


if __name__ == "__main__":
    unittest.main()
