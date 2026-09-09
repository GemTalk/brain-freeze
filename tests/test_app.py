"""The web app, driven through Flask's test client inside the database.

Run: gemdb -m unittest tests.test_app -v

These need a real database, because the app reads and writes gemdb.root. Under
plain CPython there is no gemdb module, so the whole module skips and
`python3 -m unittest discover` stays green -- run it under gemdb to get any
coverage of the app at all.

setUpClass re-seeds. The tests file real claims and create a real policy, and
re-running the seed is how this demo resets, so leaning on that keeps them
deterministic and leaves the database in a known state afterwards.
"""

import unittest
from datetime import date

try:
    import gemdb
except ImportError:  # plain CPython -- nothing to test against
    gemdb = None

if gemdb is not None:
    import app as bf_app
    import seed


# The database is shared across these tests and filing a claim mutates it, so
# every test that writes gets a policy of its own. All three are Active,
# Standard plan, with three approvals used -- one more pays out.
ACTIVE = "BF-100092"          # written by: a claim is paid and persisted
ACTIVE_RULES = "BF-100150"    # written by: the payout matches adjudicate()
ACTIVE_READONLY = "BF-100184" # never written -- for the "no warning" checks
CUJ4 = "BF-100186"            # written by: the flavour/toppings claim

#: Already past its lapse date, and its annual cap is NOT spent, so a claim
#: filed against it can only be refused for the lapse. BF-100539 -- the policy
#: the mockups are drawn from -- is no good here: it lapses on 2027-03-10,
#: which has not happened yet, so it is still in force and would be refused
#: for the cap instead.
LAPSED = "BF-100746"

#: Lapses in the future. Its stored policy_status is "Lapsed", but cover has
#: not ended, and the app has to tell those apart.
LAPSES_LATER = "BF-100539"


@unittest.skipIf(gemdb is None, "needs the database -- run under gemdb")
class TheApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gemdb.root["brainfreeze"] = seed.load()
        gemdb.commit()
        # Which claims came out of the CSVs, captured before any test files
        # one. New claims share the CLM-00nnnn shape, so the id is no help.
        cls.seeded_claims = frozenset(
            c.claim_id for c in gemdb.root["brainfreeze"].claims)
        cls.app = bf_app.create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app.test_client()

    def book(self):
        return gemdb.root["brainfreeze"]

    # -- the picker ------------------------------------------------------

    def test_the_picker_lists_real_policyholders(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        body = r.data.decode()
        self.assertIn(str(len(self.book())), body)   # the count is the point
        self.assertIn("BF-100000", body)             # first page, first row

    def test_the_picker_pages_rather_than_rendering_900_rows(self):
        body = self.client.get("/").data.decode()
        shown = body.count('href="/policies/BF-')
        self.assertEqual(shown, bf_app.PAGE)
        later = self.client.get("/?from=25").data.decode()
        self.assertIn("BF-100025", later)
        self.assertNotIn('href="/policies/BF-100000"', later)

    def test_looking_up_one_policy_goes_straight_to_it(self):
        r = self.client.get("/?policy=%s" % LAPSES_LATER)
        self.assertEqual(r.status_code, 302)
        self.assertIn(LAPSES_LATER, r.headers["Location"])

    # -- taking a new view (issue #47) -----------------------------------

    def _spy_on_the_session(self):
        """Record gemdb's transaction calls, still doing the real thing.

        The staleness itself cannot be reproduced from one gem -- this session
        sees its own writes immediately, and a second one is not something a
        test running inside the database can start. What *is* observable is
        whether the app takes a new view at all, and in which order, which is
        the whole of the bug and of the recipe that fixes it.
        """
        calls = []
        original = {}

        def recorded(name):
            real = getattr(gemdb, name)
            original[name] = real

            def wrapper(*args, **kwargs):
                calls.append(name)
                return real(*args, **kwargs)
            return wrapper

        for name in ("commit", "refresh", "abort"):
            setattr(gemdb, name, recorded(name))
        return calls, original

    def _restore(self, original):
        for name, real in original.items():
            setattr(gemdb, name, real)

    def test_a_read_commits_and_then_refreshes(self):
        # Without this the server answers from the view it started with, for
        # as long as it runs: the notebook and the shell can commit all they
        # like and the browser never sees it (issue #47).
        calls, original = self._spy_on_the_session()
        try:
            r = self.client.get("/policies/%s" % ACTIVE_READONLY)
        finally:
            self._restore(original)

        self.assertEqual(r.status_code, 200)
        self.assertIn("refresh", calls)
        self.assertLess(calls.index("commit"), calls.index("refresh"),
                        "refresh() refuses while the session holds "
                        "uncommitted work, and rendering leaves it holding "
                        "some -- commit first")
        self.assertNotIn("abort", calls)   # it would discard the app's own code

    def test_the_picker_takes_a_new_view_too(self):
        # Every handler, not just the ones someone remembered: the count on
        # the front page is the number CUJ-3 asks an evaluator to watch move.
        calls, original = self._spy_on_the_session()
        try:
            r = self.client.get("/")
        finally:
            self._restore(original)
        self.assertEqual(r.status_code, 200)
        self.assertIn("refresh", calls)

    def test_a_dirty_session_can_still_serve_a_request(self):
        # The trap the recipe exists for. Compiling Python is a repository
        # write, so a long-running app is always dirty; a bare refresh() would
        # raise here and every page would be a 500.
        namespace = {}
        exec(compile("def _dirties_the_session(n):\n    return n + 1\n",
                     "<dirty>", "exec"), namespace)
        namespace["_dirties_the_session"](1)
        if not gemdb.needs_commit():
            # findings/04 measured this both ways on different Grails. If the
            # session is clean there is no trap to spring, and saying so is
            # better than passing quietly.
            self.skipTest("this session is clean -- nothing to refuse")
        self.assertEqual(
            self.client.get("/policies/%s" % ACTIVE_READONLY).status_code, 200)

    # -- the quote flow --------------------------------------------------

    def test_the_quote_form_does_not_ask_for_sex(self):
        # FR-5.2: it is in the CSVs and carries no weight in the risk model,
        # so asking would pose a question that changes nothing.
        r = self.client.get("/quote")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("sex", r.data.decode().lower())

    def test_a_quote_shows_what_the_model_says(self):
        r = self.client.post("/quote", data={
            "age": "11", "migraine": "no", "tth": "no",
            "speed": "fast", "trigger": "slushie"})
        self.assertEqual(r.status_code, 200)
        body = r.data.decode()
        offer = bf_app.brainfreeze.quote(11, False, False, "fast", "slushie")
        self.assertEqual(offer.score, 75.0)      # pinned in test_brainfreeze
        self.assertEqual(offer.tier, "High")
        self.assertIn("75", body)
        self.assertIn("High", body)
        for plan in ("Basic", "Standard", "Premium"):
            self.assertIn(plan, body)
        self.assertIn("171.00", body)            # Standard at the High loading

    def test_the_quote_explains_itself(self):
        # CUJ-2 needs the breakdown visible, not just the total.
        r = self.client.post("/quote", data={
            "age": "11", "migraine": "no", "tth": "no",
            "speed": "fast", "trigger": "slushie"})
        self.assertIn("Everyone starts here", r.data.decode())

    def test_taking_out_a_policy_persists_it(self):
        before = len(self.book())
        r = self.client.post("/policies", data={
            "age": "11", "migraine": "no", "tth": "no",
            "speed": "fast", "trigger": "slushie", "plan": "Standard"})
        self.assertEqual(r.status_code, 302)     # POST/redirect/GET
        book = self.book()
        self.assertEqual(len(book), before + 1)
        new_id = r.headers["Location"].rstrip("/").split("/")[-1]
        policy = book[new_id]
        self.assertEqual(policy.plan_name, "Standard")
        self.assertEqual(policy.risk_tier, "High")
        self.assertEqual(policy.annual_premium, 171.00)
        self.assertEqual(policy.events, [])

    # -- history ---------------------------------------------------------

    def test_history_shows_every_event_not_just_claims(self):
        policy = self.book()[LAPSES_LATER]
        r = self.client.get("/policies/%s" % LAPSES_LATER)
        self.assertEqual(r.status_code, 200)
        body = r.data.decode()
        for claim in policy.claims:
            self.assertIn(claim.claim_id, body)
        self.assertIn("179.97", body)            # total paid
        self.assertIn("Policy lapsed", body)

    def test_an_unknown_policy_is_a_404(self):
        self.assertEqual(self.client.get("/policies/BF-999999").status_code, 404)

    # -- the claim form warns before you file ----------------------------

    def test_the_form_warns_when_cover_has_ended(self):
        policy = self.book()[LAPSED]
        r = self.client.get("/policies/%s/claims/new" % LAPSED)
        self.assertEqual(r.status_code, 200)
        body = r.data.decode().lower()
        self.assertIn("cover on this policy ended", body)
        self.assertIn(str(policy.policy_lapse_date), body)

    def test_the_form_warns_when_the_annual_cap_is_spent(self):
        # BF-100539 is in force today but has used all four approvals.
        policy = self.book()[LAPSES_LATER]
        self.assertEqual(policy.claims_remaining_this_year, 0)
        body = self.client.get(
            "/policies/%s/claims/new" % LAPSES_LATER).data.decode().lower()
        self.assertIn("used all 4 approvals", body)

    def test_the_form_does_not_cry_wolf_on_a_policy_in_force(self):
        r = self.client.get("/policies/%s/claims/new" % ACTIVE_READONLY)
        self.assertEqual(r.status_code, 200)
        body = r.data.decode().lower()
        self.assertNotIn("cover on this policy ended", body)
        self.assertNotIn("used all", body)

    def test_a_future_lapse_is_not_a_lapse_yet(self):
        # policy_status says "Lapsed" -- it records the policy's fate over the
        # whole term -- but cover has not ended, so the claim form must not
        # say it has, and a claim filed today must not be refused for it.
        policy = self.book()[LAPSES_LATER]
        self.assertEqual(policy.policy_status, "Lapsed")
        self.assertTrue(policy.is_in_force_on(date.today()))
        body = self.client.get(
            "/policies/%s/claims/new" % LAPSES_LATER).data.decode()
        self.assertNotIn("cover on this policy ended", body.lower())

    def test_the_picker_distinguishes_lapsed_from_lapses_later(self):
        # Both stored as policy_status "Lapsed"; only one has actually lapsed.
        lapsed = self.book()[LAPSED]
        later = self.book()[LAPSES_LATER]
        self.assertEqual(later.policy_status, "Lapsed")
        # An 8-character prefix matches ten policies -- few enough to fit one
        # page, more than one so the lookup lists rather than redirecting.
        page = self.client.get("/?policy=%s" % LAPSED[:8]).data.decode()
        self.assertIn("Lapsed %s" % lapsed.policy_lapse_date, page)
        page = self.client.get("/?policy=%s" % LAPSES_LATER[:8]).data.decode()
        self.assertIn("Lapses %s" % later.policy_lapse_date, page)

    # -- filing a claim --------------------------------------------------

    def _file(self, policy_id):
        return self.client.post("/policies/%s/claims" % policy_id, data={
            "trigger": "slushie", "cold": "Iced", "portion": "Regular",
            "speed": "About normal", "pain": "7", "duration": "Two to ten minutes",
            "location": "Forehead", "quality": "Stabbing"})

    def test_a_claim_on_a_policy_in_force_is_paid_and_persisted(self):
        policy = self.book()[ACTIVE]
        before_paid, before_events = policy.total_paid, len(policy.events)

        r = self._file(ACTIVE)
        self.assertEqual(r.status_code, 302)

        policy = self.book()[ACTIVE]
        self.assertEqual(len(policy.events), before_events + 1)
        claim = policy.events[-1].claim
        self.assertIsNotNone(claim)
        self.assertEqual(claim.status, "Approved")
        self.assertGreater(claim.approved, 0)
        self.assertGreater(policy.total_paid, before_paid)

        # and the decision is a GET, so a refresh cannot re-file it
        decision = self.client.get(r.headers["Location"])
        self.assertEqual(decision.status_code, 200)
        self.assertIn(claim.claim_id, decision.data.decode())

    def test_the_payout_is_the_rules_answer_not_the_apps(self):
        policy = self.book()[ACTIVE_RULES]
        # captured BEFORE filing -- the new claim changes the count it is
        # adjudicated against
        used = len(policy.approved_claims)
        limit, deductible = policy.coverage_limit, policy.deductible

        self._file(ACTIVE_RULES)

        claim = self.book()[ACTIVE_RULES].events[-1].claim
        expected = bf_app.brainfreeze.adjudicate(
            claim.requested, limit, deductible, used)
        self.assertEqual(claim.status, expected.status)
        self.assertEqual(claim.approved, expected.amount)

    def test_a_claim_on_a_lapsed_policy_is_refused_for_the_lapse(self):
        r = self._file(LAPSED)
        self.assertEqual(r.status_code, 302)
        claim = self.book()[LAPSED].events[-1].claim
        self.assertEqual(claim.status, "Denied")
        self.assertEqual(claim.reason, "Policy lapsed")
        self.assertEqual(claim.approved, 0.0)

    # -- CUJ-4: two fields added after the data was already committed -----

    def test_a_new_claim_carries_flavour_and_toppings(self):
        r = self.client.post("/policies/%s/claims" % CUJ4, data={
            "trigger": "ice cream", "cold": "Straight from the freezer",
            "portion": "A lot", "speed": "All at once", "pain": "6",
            "duration": "Half a minute to two", "location": "Temple",
            "quality": "Pulling",
            "flavour": "Mint choc chip",
            "toppings": ["Sprinkles", "Hot fudge"]})
        self.assertEqual(r.status_code, 302)

        claim = self.book()[CUJ4].events[-1].claim
        self.assertEqual(claim.flavour, "Mint choc chip")
        self.assertEqual(claim.toppings, ("Sprinkles", "Hot fudge"))

        # and it survives the commit, read back from the database
        self.assertEqual(gemdb.root["brainfreeze"][CUJ4].events[-1].claim.flavour,
                         "Mint choc chip")

    def test_the_2172_older_claims_still_read(self):
        # This is the whole of the migration. A claim written before the
        # fields existed has no slot of its own; without the class-level
        # default, reading claim.flavour would raise AttributeError.
        older = [c for p in self.book() for c in p.claims
                 if c.claim_id in self.seeded_claims]
        self.assertEqual(len(older), 2172)
        for claim in older:
            self.assertIsNone(claim.flavour)
            self.assertEqual(claim.toppings, ())

    def test_the_form_offers_the_new_questions(self):
        body = self.client.get("/policies/%s/claims/new" % ACTIVE_READONLY).data.decode()
        self.assertIn('name="flavour"', body)
        self.assertIn('name="toppings"', body)
        self.assertIn("Mint choc chip", body)

    def test_a_claim_without_them_is_still_valid(self):
        # The questions are optional; a claim filed without answering them
        # reads exactly like one from before they existed.
        self._file(ACTIVE)
        claim = self.book()[ACTIVE].events[-1].claim
        self.assertIsNone(claim.flavour)
        self.assertEqual(claim.toppings, ())

    def test_the_claimant_never_enters_an_amount(self):
        # The figure is derived from the episode, so the form must not offer
        # anywhere to type one.
        body = self.client.get(
            "/policies/%s/claims/new" % ACTIVE_READONLY).data.decode()
        self.assertNotIn('name="amount"', body)


if __name__ == "__main__":
    unittest.main()
