"""The model, pinned against rows that are actually in the shipped CSVs.

Run: python3 -m unittest test_brainfreeze -v

These are not unit tests for their own sake. Every number below was read out
of policyholders.csv or claims.csv, so if the app and the sample data ever
start disagreeing, this is what says so.
"""

import unittest
from datetime import date

from brainfreeze.money import round_cents, usd

from brainfreeze.model import Event, Policyholder

from brainfreeze import (
    COVERAGE_PLANS,
    REASON_BELOW_DEDUCTIBLE,
    REASON_OUTSIDE_TERM,
    REASON_PER_INCIDENT_LIMIT,
    REASON_POLICY_LAPSED,
    RULE_ANNUAL_LIMIT,
    RULE_BELOW_DEDUCTIBLE,
    RULE_OUTSIDE_TERM,
    RULE_PER_INCIDENT_LIMIT,
    RULE_POLICY_LAPSED,
    adjudicate,
    annual_premium,
    assess_amount,
    quote,
    risk_score,
    risk_tier,
    rule_for_reason,
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
        # Not `round(x, 2)`. The builtin on a Decimal brings the VM down
        # inside the database -- "a Decimal does not understand #'*'", with no
        # Python exception -- which is one of the reasons money rounding lives
        # in brainfreeze.money rather than being taken from the language.
        self.assertEqual(round_cents(annual_premium("Basic", "Low")), usd("31.50"))
        self.assertEqual(round_cents(annual_premium("Standard", "Low")), usd("63.00"))
        self.assertEqual(round_cents(annual_premium("Premium", "Low")), usd("126.00"))

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
        d = adjudicate(usd("64.32"), usd("60.0"), usd("5.0"), 3)
        self.assertEqual(d.status, "Approved")
        self.assertEqual(d.amount, usd("55.00"))
        self.assertEqual(d.capped_by_limit, usd("4.32"))
        self.assertEqual(d.deductible_applied, usd("5.00"))

    def test_clm_001289_hits_the_annual_cap(self):
        d = adjudicate(usd("54.53"), usd("60.0"), usd("5.0"), 4)
        self.assertEqual(d.status, "Denied")
        self.assertEqual(d.amount, usd("0.00"))
        self.assertEqual(d.reason, "Exceeded annual claim limit")

    def test_the_other_three_approvals_on_bf_100539(self):
        # requested, approvals already used, what was paid
        for assessed, used, expected in (("39.19", 0, "34.19"),
                                         ("40.78", 1, "35.78"),
                                         ("71.37", 2, "55.00")):
            d = adjudicate(usd(assessed), usd("60.00"), usd("5.00"), used)
            self.assertEqual(d.amount, usd(expected), assessed)

    def test_below_the_deductible_is_a_denial_not_a_zero_payment(self):
        d = adjudicate(usd("8.00"), usd("25.0"), usd("10.0"), 0)
        self.assertEqual(d.status, "Denied")
        self.assertEqual(d.reason, "Claim amount below deductible")

    def test_the_cap_short_circuits_everything(self):
        d = adjudicate(usd("200.00"), usd("150.0"), usd("0.0"), 4)
        self.assertEqual(d.status, "Denied")
        self.assertEqual(d.amount, usd("0.00"))

    def test_a_lapsed_policy_pays_nothing(self):
        # CLM-001291: filed 20 April 2027, six weeks after cover ended
        d = adjudicate(usd("43.09"), usd("60.0"), usd("5.0"), 0, policy_in_force=False)
        self.assertEqual(d.status, "Denied")
        self.assertEqual(d.amount, usd("0.00"))
        self.assertEqual(d.reason, "Policy lapsed")

    def test_lapse_is_reported_ahead_of_the_cap(self):
        # Both rules would refuse this. The claimant is entitled to the reason
        # that actually applies: there was no cover, cap or no cap.
        d = adjudicate(usd("43.09"), usd("60.0"), usd("5.0"), 4, policy_in_force=False)
        self.assertEqual(d.reason, "Policy lapsed")

    def test_an_out_of_term_claim_is_not_refused_as_a_lapse(self):
        # A policy that never lapsed cannot be refused for lapsing. The caller
        # says which absence of cover it found; "Policy lapsed" is only the
        # default so that every existing call keeps its wording.
        d = adjudicate(usd("43.09"), usd("60.0"), usd("5.0"), 0, policy_in_force=False,
                       no_cover_reason=REASON_OUTSIDE_TERM)
        self.assertEqual(d.status, "Denied")
        self.assertEqual(d.amount, usd("0.00"))
        self.assertEqual(d.reason, "Event outside policy term")

    def test_the_lapse_wording_is_the_default(self):
        # The 254 refusals in claims.csv say "Policy lapsed" and go on saying
        # it; only the new case gets the new wording.
        self.assertEqual(adjudicate(usd("43.09"), usd("60.0"), usd("5.0"), 0,
                                    policy_in_force=False).reason,
                         REASON_POLICY_LAPSED)

    def test_a_policy_in_force_is_unaffected(self):
        # The default has to stay the old behaviour or every existing call
        # silently changes meaning.
        self.assertEqual(adjudicate(usd("43.09"), usd("60.0"), usd("5.0"), 0).amount,
                         adjudicate(usd("43.09"), usd("60.0"), usd("5.0"), 0, policy_in_force=True).amount)

    def test_premium_plan_has_no_deductible(self):
        d = adjudicate(usd("120.00"), usd("150.0"), usd("0.0"), 0)
        self.assertEqual(d.amount, 120.00)
        self.assertEqual(d.deductible_applied, 0.0)


class EventOrderSurvivesAdding(unittest.TestCase):
    """#71: sorting at load time is not enough.

    The app files a claim by adding an event dated TODAY to a policy whose
    seeded events run into 2027, so an appended event lands in the middle of
    the history and is shown last."""

    def event(self, event_id, when):
        return Event(event_id, when, "slushie", -5.0, 250.0, "fast", True)

    def policy(self):
        return Policyholder(
            policy_id="BF-TEST", age=10, sex=None, migraine_history=False,
            tension_type_headache_history=False,
            typical_consumption_speed="fast", favourite_trigger="slushie",
            underwriting_base=45.0, plan_name="Standard",
            annual_premium=usd("171.00"), policy_start_date=date(2026, 1, 1),
            policy_term_months=24)

    def test_an_event_added_out_of_order_lands_in_order(self):
        p = self.policy()
        for day, event_id in ((10, "EVT-000003"), (20, "EVT-000004")):
            p.add_event(self.event(event_id, date(2027, 1, day)))
        p.add_event(self.event("EVT-000005", date(2026, 6, 1)))
        self.assertEqual([e.event_date for e in p.events],
                         [date(2026, 6, 1), date(2027, 1, 10), date(2027, 1, 20)])

    def test_two_events_on_one_day_order_by_id(self):
        p = self.policy()
        p.add_event(self.event("EVT-000009", date(2026, 6, 1)))
        p.add_event(self.event("EVT-000002", date(2026, 6, 1)))
        self.assertEqual([e.event_id for e in p.events],
                         ["EVT-000002", "EVT-000009"])

    def test_appending_at_the_end_still_works(self):
        p = self.policy()
        p.add_event(self.event("EVT-000001", date(2026, 2, 1)))
        newest = p.add_event(self.event("EVT-000002", date(2026, 3, 1)))
        self.assertIs(p.events[-1], newest)

    def test_it_returns_the_event_it_was_given(self):
        p = self.policy()
        event = self.event("EVT-000001", date(2026, 2, 1))
        self.assertIs(p.add_event(event), event)


class RuleIdentifiers(unittest.TestCase):
    """#49: a refusal has to be checkable, not just readable.

    The prose `reason` is what the claimant is told and it is allowed to be
    reworded. `rule` is what an agent explaining the refusal reads, so it is
    fixed: the same five strings the parallel implementation uses.
    """

    def test_an_approved_claim_names_no_rule(self):
        # Nothing bound, so there is nothing to name. `reason` is already
        # None here and `rule` keeps it company.
        d = adjudicate(usd("64.32"), usd("60.0"), usd("5.0"), 3)
        self.assertEqual(d.status, "Approved")
        self.assertIsNone(d.rule)

    def test_each_refusal_carries_its_identifier(self):
        cases = (
            (dict(policy_in_force=False), RULE_POLICY_LAPSED),
            (dict(policy_in_force=False, no_cover_reason=REASON_OUTSIDE_TERM),
             RULE_OUTSIDE_TERM),
        )
        for kwargs, rule in cases:
            d = adjudicate(usd("43.09"), usd("60.0"), usd("5.0"), 0, **kwargs)
            self.assertEqual(d.rule, rule, kwargs)

    def test_the_annual_cap_names_itself(self):
        d = adjudicate(usd("54.53"), usd("60.0"), usd("5.0"), 4)
        self.assertEqual(d.rule, RULE_ANNUAL_LIMIT)

    def test_below_the_deductible_names_itself(self):
        d = adjudicate(usd("8.00"), usd("25.0"), usd("10.0"), 0)
        self.assertEqual(d.rule, RULE_BELOW_DEDUCTIBLE)

    def test_a_lapse_still_outranks_the_cap_in_the_identifier_too(self):
        d = adjudicate(usd("43.09"), usd("60.0"), usd("5.0"), 4,
                       policy_in_force=False)
        self.assertEqual(d.rule, RULE_POLICY_LAPSED)

    def test_the_identifiers_are_the_five_the_card_names(self):
        self.assertEqual(
            sorted((RULE_ANNUAL_LIMIT, RULE_BELOW_DEDUCTIBLE,
                    RULE_OUTSIDE_TERM, RULE_PER_INCIDENT_LIMIT,
                    RULE_POLICY_LAPSED)),
            ["annual-claim-count-cap", "below-deductible",
             "event-outside-term", "per-incident-limit", "policy-lapsed"])


class TheTightestCapIsTheOneReported(unittest.TestCase):
    """When two caps both apply, the one that decided the number is named.

    A $100 episode on a policy with a $5 per-incident limit and a $10
    deductible pays nothing. Saying "below deductible" states something
    untrue about a claim four times the deductible: what actually decided
    the number is the limit, which allowed $5 where the deductible would
    have allowed $90.
    """

    def test_the_limit_is_named_when_it_is_the_tighter_cap(self):
        d = adjudicate(usd("100.00"), usd("5.00"), usd("10.00"), 0)
        self.assertEqual(d.status, "Denied")
        self.assertEqual(d.amount, usd("0.00"))
        self.assertEqual(d.rule, RULE_PER_INCIDENT_LIMIT)
        self.assertEqual(d.reason, REASON_PER_INCIDENT_LIMIT)

    def test_the_deductible_is_named_when_it_is_the_tighter_cap(self):
        # The limit binds -- $1 comes off -- but the deductible takes the
        # other $10, so the deductible is what decided it.
        d = adjudicate(usd("11.00"), usd("10.00"), usd("10.00"), 0)
        self.assertEqual(d.status, "Denied")
        self.assertEqual(d.rule, RULE_BELOW_DEDUCTIBLE)
        self.assertEqual(d.reason, REASON_BELOW_DEDUCTIBLE)

    def test_a_limit_that_does_not_bind_is_never_named(self):
        d = adjudicate(usd("8.00"), usd("25.00"), usd("10.00"), 0)
        self.assertEqual(d.rule, RULE_BELOW_DEDUCTIBLE)

    def test_the_shipped_plans_cannot_reach_the_limit_refusal(self):
        # Every plan's limit is well above its deductible, so on real data a
        # payable-of-zero is always the deductible. This is why no committed
        # claim's wording moves.
        for name, plan in COVERAGE_PLANS.items():
            for assessed in ("5.00", "9.99", "10.00", "24.99", "60.00",
                             "150.00", "200.00"):
                d = adjudicate(usd(assessed), plan.coverage_limit_per_incident,
                               plan.deductible_per_incident, 0)
                if not d.approved:
                    self.assertEqual(d.rule, RULE_BELOW_DEDUCTIBLE,
                                     "%s at %s" % (name, assessed))


class ReasonsMapBackToRules(unittest.TestCase):
    """The 2,172 committed claims store prose and nothing else.

    `rule_for_reason` is how those are read as rules. It maps only the
    wordings `adjudicate` itself produces, and refuses to guess at anything
    else -- the generator's unmodelled refusals are not rule outcomes, and
    one of them is worded almost exactly like a rule.
    """

    def test_every_reason_the_rules_produce_maps_back(self):
        pairs = ((REASON_POLICY_LAPSED, RULE_POLICY_LAPSED),
                 (REASON_OUTSIDE_TERM, RULE_OUTSIDE_TERM),
                 (REASON_BELOW_DEDUCTIBLE, RULE_BELOW_DEDUCTIBLE),
                 (REASON_PER_INCIDENT_LIMIT, RULE_PER_INCIDENT_LIMIT),
                 ("Exceeded annual claim limit", RULE_ANNUAL_LIMIT))
        for reason, rule in pairs:
            self.assertEqual(rule_for_reason(reason), rule, reason)

    def test_it_does_not_guess_at_prose_the_rules_never_wrote(self):
        # The generator's unmodelled denials. The second one reads like the
        # per-incident rule and is not it: no rule produced it, so naming one
        # would be the paraphrasing this whole change exists to stop.
        for reason in ("Pre-existing headache condition exclusion",
                       "Claim amount exceeds per-incident coverage limit",
                       "Insufficient severity documented",
                       "Filed outside claim window"):
            self.assertIsNone(rule_for_reason(reason), reason)

    def test_no_reason_at_all_is_not_a_rule(self):
        self.assertIsNone(rule_for_reason(None))

    def test_the_new_wording_does_not_collide_with_the_generators(self):
        # If it did, 10 committed unmodelled refusals would start counting as
        # rule outcomes.
        self.assertNotEqual(REASON_PER_INCIDENT_LIMIT,
                            "Claim amount exceeds per-incident coverage limit")


class Assessment(unittest.TestCase):
    def test_the_claimant_never_enters_a_figure(self):
        # pain 6.4 over 456.3s, the CLM-001288 episode, before the generator's
        # jitter took it to the $64.32 that is in the CSV
        self.assertEqual(assess_amount(6.4, 456.3), usd("71.22"))

    def test_bounds(self):
        self.assertEqual(assess_amount(0, 0), usd("10.00"))
        # the worst episode the generator can produce is nowhere near the cap
        self.assertEqual(assess_amount(10, 900), 115.0)
        # the floor and ceiling only bite with the generator's jitter on top
        self.assertEqual(assess_amount(0, 0, jitter=-50), 5.0)
        self.assertEqual(assess_amount(10, 900, jitter=500), 200.0)


if __name__ == "__main__":
    unittest.main()
