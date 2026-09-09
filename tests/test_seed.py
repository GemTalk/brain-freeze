"""The loader, against the CSVs actually in the repo.

Run: python3 -m unittest test_seed -v

This is the smoke test FR-2.3 asks for, as tests rather than as eyeballing a
printout. It reads `data/policyholders.csv` and `data/claims.csv`.
"""

import csv
import unittest
from datetime import date, timedelta

import brainfreeze
import seed


class TheLoad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book = seed.load()

    def test_counts(self):
        self.assertEqual(len(self.book), 900)
        self.assertEqual(len(self.book.events), 4993)

    def test_every_event_belongs_to_a_policyholder(self):
        # attach_events raises rather than dropping, so reaching here is the
        # assertion; this pins the total as well.
        self.assertEqual(sum(len(p.events) for p in self.book), 4993)

    def test_money_matches_the_generator(self):
        self.assertEqual(self.book.total_premium, 92081.22)
        self.assertEqual(self.book.total_paid, 54671.44)
        self.assertEqual(self.book.loss_ratio, 0.594)

    def test_claim_counts(self):
        claims = self.book.claims
        self.assertEqual(len(claims), 2172)
        self.assertEqual(len([c for c in claims if c.is_approved]), 1691)

    def test_the_non_events_survived_the_load(self):
        # If these were dropped, claim frequency would be uncomputable --
        # which is the reason events rather than claims hang off a policy.
        froze = [e for e in self.book.events if e.brain_freeze]
        self.assertEqual(len(froze), 3730)
        self.assertLess(len(froze), len(self.book.events))

    def test_a_refused_claim_keeps_its_reason(self):
        refused = [c for c in self.book.claims if not c.is_approved]
        self.assertTrue(all(c.reason for c in refused))
        self.assertTrue(all(c.approved == 0.0 for c in refused))


class TheUnderwritingBase(unittest.TestCase):
    """The score is derived from the recorded base, not stored twice.

    The generator draws each policyholder a starting point and, until this
    column existed, threw it away -- so a score already in the dataset could
    not be reproduced from the answers that are in it. An applicant matching
    BF-100539 could land in a different tier, and an agent asked "why is this
    policy High tier?" had nothing to work from. Recording the base closes
    that, and making the score derived rather than stored means there is one
    source of truth: change a weight in underwriting.py and every score moves
    with it, instead of silently disagreeing with the column.
    """

    @classmethod
    def setUpClass(cls):
        cls.book = seed.load()
        cls.stored = {}
        with open(seed.POLICYHOLDERS_CSV, newline="") as handle:
            for row in csv.DictReader(handle):
                cls.stored[row["policy_id"]] = float(row["underwriting_risk_score"])

    def test_every_policyholder_has_a_recorded_base(self):
        for policyholder in self.book:
            self.assertIsInstance(policyholder.underwriting_base, float)

    def test_the_derived_score_matches_the_stored_column(self):
        # This is the drift detector. Scoring the answers from the recorded
        # base has to land on the number the generator wrote, and the model's
        # property has to be that derivation rather than the stored column --
        # otherwise the two can disagree without anything failing.
        for policyholder in self.book:
            derived = round(brainfreeze.risk_score(
                policyholder.age,
                policyholder.migraine_history,
                policyholder.tension_type_headache_history,
                policyholder.typical_consumption_speed,
                policyholder.favourite_trigger,
                base=policyholder.underwriting_base), 1)
            self.assertEqual(derived, self.stored[policyholder.policy_id],
                             policyholder.policy_id)
            self.assertEqual(policyholder.underwriting_risk_score, derived,
                             policyholder.policy_id)

    def test_a_quote_from_the_answers_reproduces_the_policy(self):
        # FR-5.3: an applicant who gives an existing policyholder's answers
        # must be scored and tiered exactly as that policy was.
        for policyholder in self.book:
            offer = brainfreeze.quote(
                policyholder.age,
                policyholder.migraine_history,
                policyholder.tension_type_headache_history,
                policyholder.typical_consumption_speed,
                policyholder.favourite_trigger,
                base=policyholder.underwriting_base)
            self.assertEqual(offer.score, policyholder.underwriting_risk_score,
                             policyholder.policy_id)
            self.assertEqual(offer.tier, policyholder.risk_tier,
                             policyholder.policy_id)


class LapsedPolicies(unittest.TestCase):
    """A lapsed policy has a date it lapsed on, and cover stops there.

    Before this, a quarter of the book was marked Lapsed with no lapse date
    while claims went on being approved across the full term -- incoherent the
    moment the app or an agent reasons about it. Events still happen after the
    lapse (a child does not stop eating ice cream because a policy ended);
    what stops is cover.
    """

    @classmethod
    def setUpClass(cls):
        cls.book = seed.load()

    def test_a_lapsed_policy_lapses_inside_its_term(self):
        lapsed = [p for p in self.book if p.policy_status == "Lapsed"]
        self.assertTrue(lapsed)
        for policyholder in lapsed:
            self.assertIsNotNone(policyholder.policy_lapse_date,
                                 policyholder.policy_id)
            self.assertGreaterEqual(policyholder.policy_lapse_date,
                                    policyholder.policy_start_date,
                                    policyholder.policy_id)
            self.assertLessEqual(policyholder.policy_lapse_date,
                                 policyholder.policy_end_date,
                                 policyholder.policy_id)

    def test_an_active_policy_has_no_lapse_date(self):
        for policyholder in self.book:
            if policyholder.policy_status == "Active":
                self.assertIsNone(policyholder.policy_lapse_date,
                                  policyholder.policy_id)

    def test_nothing_is_paid_after_the_policy_lapsed(self):
        for policyholder in self.book:
            for event in policyholder.events:
                if not policyholder.is_in_force_on(event.event_date):
                    if event.claim is not None:
                        self.assertFalse(event.claim.is_approved,
                                         event.claim.claim_id)

    def test_a_claim_after_the_lapse_says_why(self):
        after = [e.claim for p in self.book for e in p.events
                 if e.claim is not None and not p.is_in_force_on(e.event_date)]
        self.assertTrue(after, "no claim falls after a lapse -- nothing pinned")
        for claim in after:
            self.assertEqual(claim.reason, "Policy lapsed", claim.claim_id)

    def test_cover_runs_to_the_lapse_date_inclusive(self):
        lapsed = [p for p in self.book if p.policy_status == "Lapsed"][0]
        self.assertTrue(lapsed.is_in_force_on(lapsed.policy_start_date))
        self.assertTrue(lapsed.is_in_force_on(lapsed.policy_lapse_date))
        self.assertFalse(
            lapsed.is_in_force_on(lapsed.policy_lapse_date + timedelta(days=1)))


class ThePolicyTerm(unittest.TestCase):
    """Cover starts when the policy does and ends when the term does.

    `is_in_force_on` used to test the lapse date and nothing else, so a
    policy with no lapse was in force forever in both directions -- an event
    a year before the policy was sold, or ten years after the term ended, was
    adjudicated as covered and paid. `policy_end_date` existed and was used by
    nothing. These pin both ends of the term, and pin the wording: an
    out-of-term event was refused as a lapse, which is a false statement about
    a policy that never lapsed and the one thing CUJ-2 asks an agent to
    explain.
    """

    @classmethod
    def setUpClass(cls):
        cls.book = seed.load()
        # An ordinary policy that never lapsed, so the term is the only thing
        # that can end cover on it.
        cls.active = [p for p in cls.book
                      if p.policy_lapse_date is None][0]

    def test_cover_starts_on_the_start_date(self):
        p = self.active
        self.assertFalse(p.is_in_force_on(p.policy_start_date - timedelta(days=1)),
                         p.policy_id)
        self.assertTrue(p.is_in_force_on(p.policy_start_date), p.policy_id)

    def test_cover_ends_with_the_term(self):
        p = self.active
        self.assertTrue(p.is_in_force_on(p.policy_end_date), p.policy_id)
        self.assertFalse(p.is_in_force_on(p.policy_end_date + timedelta(days=1)),
                         p.policy_id)
        self.assertFalse(p.is_in_force_on(p.policy_end_date + timedelta(days=3650)),
                         p.policy_id)

    def test_an_out_of_term_event_is_not_called_a_lapse(self):
        # The policy never lapsed. Saying it did would be a lie, and it is the
        # explanation the claimant and the agent are both given.
        p = self.active
        self.assertEqual(p.no_cover_reason_on(p.policy_start_date - timedelta(days=365)),
                         brainfreeze.REASON_OUTSIDE_TERM)
        self.assertEqual(p.no_cover_reason_on(p.policy_end_date + timedelta(days=1)),
                         brainfreeze.REASON_OUTSIDE_TERM)
        self.assertIsNone(p.no_cover_reason_on(p.policy_start_date))

    def test_a_lapse_is_still_reported_as_a_lapse(self):
        # Inside the term but after the lapse: the lapse is the specific fact,
        # and it is what the 254 refusals in the CSVs say.
        lapsed = [p for p in self.book if p.policy_lapse_date is not None][0]
        self.assertLess(lapsed.policy_lapse_date, lapsed.policy_end_date)
        self.assertEqual(
            lapsed.no_cover_reason_on(lapsed.policy_lapse_date + timedelta(days=1)),
            brainfreeze.REASON_POLICY_LAPSED)
        # ...and before it was ever sold, the term is what is wrong.
        self.assertEqual(
            lapsed.no_cover_reason_on(lapsed.policy_start_date - timedelta(days=1)),
            brainfreeze.REASON_OUTSIDE_TERM)

    def test_no_seeded_event_falls_outside_its_own_policys_term(self):
        """Asserted, not assumed -- this is what says the fix moves no figure.

        The generator draws event dates inside the term, but nothing checked
        it. If it ever stops being true, tightening `is_in_force_on` silently
        unpays claims that the pinned totals above still expect.
        """
        checked = 0
        for policyholder in self.book:
            for event in policyholder.events:
                checked += 1
                self.assertGreaterEqual(event.event_date,
                                        policyholder.policy_start_date,
                                        "%s before %s started"
                                        % (event.event_id, policyholder.policy_id))
                self.assertLessEqual(event.event_date,
                                     policyholder.policy_end_date,
                                     "%s after %s ended"
                                     % (event.event_id, policyholder.policy_id))
        self.assertEqual(checked, 4993)

    def test_every_event_in_claims_csv_is_inside_its_term(self):
        """The same check straight off the CSV, not through the loader."""
        terms = {}
        with open(seed.POLICYHOLDERS_CSV, newline="") as handle:
            for row in csv.DictReader(handle):
                policyholder = self.book[row["policy_id"]]
                terms[row["policy_id"]] = (policyholder.policy_start_date,
                                           policyholder.policy_end_date)
        outside = []
        with open(seed.CLAIMS_CSV, newline="") as handle:
            for row in csv.DictReader(handle):
                start, end = terms[row["policy_id"]]
                when = seed._date(row["event_date"])
                if when < start or when > end:
                    outside.append((row["event_id"], row["policy_id"],
                                    row["event_date"], str(start), str(end)))
        self.assertEqual(outside, [])


class BF100539(unittest.TestCase):
    """The policy the mockups are drawn from, so the screens stay honest.

    Chosen because its history runs through every rule in order: four
    approvals, then the annual cap, then the policy lapses and the last two
    are refused for that. One table on one screen demonstrates the whole of
    adjudication, which is what CUJ-2 asks an agent to explain.
    """

    @classmethod
    def setUpClass(cls):
        cls.policy = seed.load()["BF-100539"]

    def test_the_shape_the_screens_show(self):
        p = self.policy
        self.assertEqual(p.plan_name, "Standard")
        self.assertEqual(p.risk_tier, "Medium")
        self.assertEqual(p.underwriting_risk_score, 65.2)
        self.assertEqual(p.coverage_limit, 60.0)
        self.assertEqual(p.deductible, 5.0)
        self.assertEqual(p.annual_premium, 98.10)
        self.assertEqual(p.monthly_premium, 8.17)
        self.assertEqual(p.policy_status, "Lapsed")
        self.assertEqual(p.policy_lapse_date, date(2027, 3, 10))

    def test_the_history_table(self):
        p = self.policy
        self.assertEqual(len(p.events), 9)
        self.assertEqual(len(p.claims), 8)
        self.assertEqual(len(p.approved_claims), 4)
        self.assertEqual(len(p.brain_freeze_events), 9)
        self.assertEqual(p.total_paid, 179.97)
        self.assertEqual(p.claims_remaining_this_year, 0)

    def test_the_amounts_in_order(self):
        paid = [c.approved for c in self.policy.claims]
        self.assertEqual(paid, [34.19, 35.78, 55.00, 55.00, 0.0, 0.0, 0.0, 0.0])

    def test_the_refusals_tell_the_story_in_order(self):
        # Four paid, then the cap bites, then cover ends. A screen showing
        # this in date order explains the whole rule set without prose.
        refused = [(c.claim_id, c.reason) for c in self.policy.claims
                   if not c.is_approved]
        self.assertEqual(refused, [
            ("CLM-001289", "Exceeded annual claim limit"),
            ("CLM-001290", "Exceeded annual claim limit"),
            ("CLM-001291", "Policy lapsed"),
            ("CLM-001292", "Policy lapsed"),
        ])

    def test_the_lapse_refusals_fall_after_the_lapse_date(self):
        p = self.policy
        for event in p.events:
            if event.claim is not None and event.claim.reason == "Policy lapsed":
                self.assertGreater(event.event_date, p.policy_lapse_date,
                                   event.claim.claim_id)

    def test_events_are_in_date_order(self):
        dates = [e.event_date for e in self.policy.events]
        self.assertEqual(dates, sorted(dates))

    def test_this_policy_loses_money(self):
        self.assertGreater(self.policy.loss_ratio, 1.5)

    def test_old_claims_read_cleanly_without_the_cuj4_fields(self):
        # Nothing in the CSVs has a flavour. Reading one must not raise.
        for claim in self.policy.claims:
            self.assertIsNone(claim.flavour)
            self.assertEqual(claim.toppings, ())


if __name__ == "__main__":
    unittest.main()
