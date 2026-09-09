"""The model, pinned against rows that are actually in the shipped CSVs.

Run: python3 -m unittest test_brainfreeze -v

These are not unit tests for their own sake. Every number below was read out
of policyholders.csv or claims.csv, so if the app and the sample data ever
start disagreeing, this is what says so.
"""

import unittest

from brainfreeze import (
    REASON_OUTSIDE_TERM,
    REASON_POLICY_LAPSED,
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
    def test_clm_001288_approved(self):
        # BF-100539, Standard: $60 limit, $5 deductible, three approvals used
        d = adjudicate(64.32, 60.0, 5.0, 3)
        self.assertEqual(d.status, "Approved")
        self.assertEqual(d.amount, 55.00)
        self.assertEqual(d.capped_by_limit, 4.32)
        self.assertEqual(d.deductible_applied, 5.00)

    def test_clm_001289_hits_the_annual_cap(self):
        d = adjudicate(54.53, 60.0, 5.0, 4)
        self.assertEqual(d.status, "Denied")
        self.assertEqual(d.amount, 0.0)
        self.assertEqual(d.reason, "Exceeded annual claim limit")

    def test_the_other_three_approvals_on_bf_100539(self):
        # requested, approvals already used, what was paid
        for assessed, used, expected in ((39.19, 0, 34.19),
                                         (40.78, 1, 35.78),
                                         (71.37, 2, 55.00)):
            d = adjudicate(assessed, 60.0, 5.0, used)
            self.assertEqual(d.amount, expected, assessed)

    def test_below_the_deductible_is_a_denial_not_a_zero_payment(self):
        d = adjudicate(8.00, 25.0, 10.0, 0)
        self.assertEqual(d.status, "Denied")
        self.assertEqual(d.reason, "Claim amount below deductible")

    def test_the_cap_short_circuits_everything(self):
        d = adjudicate(200.00, 150.0, 0.0, 4)
        self.assertEqual(d.status, "Denied")
        self.assertEqual(d.amount, 0.0)

    def test_a_lapsed_policy_pays_nothing(self):
        # CLM-001291: filed 20 April 2027, six weeks after cover ended
        d = adjudicate(43.09, 60.0, 5.0, 0, policy_in_force=False)
        self.assertEqual(d.status, "Denied")
        self.assertEqual(d.amount, 0.0)
        self.assertEqual(d.reason, "Policy lapsed")

    def test_lapse_is_reported_ahead_of_the_cap(self):
        # Both rules would refuse this. The claimant is entitled to the reason
        # that actually applies: there was no cover, cap or no cap.
        d = adjudicate(43.09, 60.0, 5.0, 4, policy_in_force=False)
        self.assertEqual(d.reason, "Policy lapsed")

    def test_an_out_of_term_claim_is_not_refused_as_a_lapse(self):
        # A policy that never lapsed cannot be refused for lapsing. The caller
        # says which absence of cover it found; "Policy lapsed" is only the
        # default so that every existing call keeps its wording.
        d = adjudicate(43.09, 60.0, 5.0, 0, policy_in_force=False,
                       no_cover_reason=REASON_OUTSIDE_TERM)
        self.assertEqual(d.status, "Denied")
        self.assertEqual(d.amount, 0.0)
        self.assertEqual(d.reason, "Event outside policy term")

    def test_the_lapse_wording_is_the_default(self):
        # The 254 refusals in claims.csv say "Policy lapsed" and go on saying
        # it; only the new case gets the new wording.
        self.assertEqual(adjudicate(43.09, 60.0, 5.0, 0,
                                    policy_in_force=False).reason,
                         REASON_POLICY_LAPSED)

    def test_a_policy_in_force_is_unaffected(self):
        # The default has to stay the old behaviour or every existing call
        # silently changes meaning.
        self.assertEqual(adjudicate(43.09, 60.0, 5.0, 0).amount,
                         adjudicate(43.09, 60.0, 5.0, 0, policy_in_force=True).amount)

    def test_premium_plan_has_no_deductible(self):
        d = adjudicate(120.00, 150.0, 0.0, 0)
        self.assertEqual(d.amount, 120.00)
        self.assertEqual(d.deductible_applied, 0.0)


class Assessment(unittest.TestCase):
    def test_the_claimant_never_enters_a_figure(self):
        # pain 6.4 over 456.3s, the CLM-001288 episode, before the generator's
        # jitter took it to the $64.32 that is in the CSV
        self.assertEqual(assess_amount(6.4, 456.3), 71.22)

    def test_bounds(self):
        self.assertEqual(assess_amount(0, 0), 10.0)
        # the worst episode the generator can produce is nowhere near the cap
        self.assertEqual(assess_amount(10, 900), 115.0)
        # the floor and ceiling only bite with the generator's jitter on top
        self.assertEqual(assess_amount(0, 0, jitter=-50), 5.0)
        self.assertEqual(assess_amount(10, 900, jitter=500), 200.0)


if __name__ == "__main__":
    unittest.main()
