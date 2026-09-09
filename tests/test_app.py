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

import json
import unittest
from datetime import date

try:
    import gemdb
except ImportError:  # plain CPython -- nothing to test against
    gemdb = None

if gemdb is not None:
    import app as bf_app
    import seed
    from brainfreeze.money import usd


# The database is shared across these tests and filing a claim mutates it, so
# every test that writes gets a policy of its own. All three are Active,
# Standard plan, with three approvals used -- one more pays out.
ACTIVE = "BF-100092"          # written by: a claim is paid and persisted
ACTIVE_RULES = "BF-100150"    # written by: the payout matches adjudicate()
ACTIVE_READONLY = "BF-100184" # never written -- for the "no warning" checks
CUJ4 = "BF-100186"            # written by: the flavour/toppings claim

#: Active, six events running to 2027-01-16, and written by exactly one test:
#: the one that checks a filed claim lands in date order rather than at the
#: end (#71). It needs seeded events BOTH sides of today.
ORDERING = "BF-100000"

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

    def newest_claim(self, policy):
        """The claim just filed, found by claim id rather than by position.

        `policy.events[-1]` was the obvious way and stopped being true in #71:
        events are kept in date order now, and the app files a claim dated
        TODAY against policies whose seeded events run into 2027, so a new
        event usually lands in the MIDDLE. Position was never the thing that
        made it the new one.
        """
        seeded = self.seeded_claims
        fresh = [e.claim for e in policy.events
                 if e.claim is not None and e.claim.claim_id not in seeded]
        self.assertTrue(fresh, "no new claim on %s" % policy.policy_id)
        # The highest id, not the last position and not "the only one":
        # several tests file against the same policy, and ids are minted in
        # sequence through `_next_id`, so the newest is the largest.
        return max(fresh, key=lambda claim: claim.claim_id)

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
    # Instrumenting `gemdb` is not available to us. Rebinding an attribute on
    # the module -- the ordinary way to spy on `commit`/`refresh` -- puts the
    # session into a dirty state that `commit()` does NOT clear, so the very
    # next `refresh()` raises PendingChangesError and the test destroys what it
    # came to measure. Measured 2026-09-09; see findings/05_module_monkeypatch.py.
    #
    # So the order of the recipe is pinned by reading app.py's syntax tree in
    # tests/test_refresh.py, which runs under plain CPython, and what is
    # checked here is only what needs a live database.

    def test_the_app_takes_a_new_view_before_every_request(self):
        # Flask's own registry, rather than gemdb's -- introspecting the app
        # is safe where introspecting the module is not.
        hooks = self.app.before_request_funcs.get(None, [])
        self.assertTrue(hooks, "no before_request hook: a route added later "
                               "would silently read a stale view")

    def test_the_recipe_itself_succeeds_against_this_database(self):
        # commit-then-refresh is the whole fix, and it is the half that can
        # fail for real: refresh() refuses on a dirty session, and this app is
        # always dirty. Call it directly so a failure names the recipe rather
        # than a route.
        bf_app.take_new_view()
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

    def test_a_filed_claim_lands_in_date_order_not_at_the_end(self):
        # #71. The app dates a claim TODAY, and ACTIVE's seeded events run
        # into 2027, so an appended event would show up last in a history it
        # belongs in the middle of -- on the screen CUJ-3 drives.
        policy = self.book()[ORDERING]
        later = [e for e in policy.events if e.event_date > date.today()]
        if not later:
            self.skipTest("no seeded event after today -- nothing to land before")

        self._file(ORDERING)
        policy = self.book()[ORDERING]

        dates = [e.event_date for e in policy.events]
        self.assertEqual(dates, sorted(dates), "history is out of order")
        self.assertIsNot(policy.events[-1], None)
        self.assertLess(policy.events.index(
            [e for e in policy.events
             if e.claim is self.newest_claim(policy)][0]),
            len(policy.events) - 1,
            "the new event should not be last -- later events exist")

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
        self.assertEqual(policy.annual_premium, usd("171.00"))
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

    def test_a_policy_that_has_not_started_is_not_told_it_lapsed(self):
        # 147 of the 900 terms begin after today. Cover has not started, so a
        # claim is refused -- but not for a lapse these policies never had,
        # and the old warning would have said "ended on None".
        today = date.today()
        not_started = [p for p in self.book()
                       if today < p.policy_start_date and p.policy_lapse_date is None]
        if not not_started:
            self.skipTest("every term in the book has started -- nothing to check")
        policy = not_started[0]
        self.assertFalse(policy.is_in_force_on(today))
        body = self.client.get(
            "/policies/%s/claims/new" % policy.policy_id).data.decode()
        self.assertIn("does not start until %s" % policy.policy_start_date, body)
        self.assertNotIn("ended on None", body)
        self.assertNotIn("cover on this policy ended", body.lower())
        # An exact id redirects to the policy page -- see
        # test_looking_up_one_policy_goes_straight_to_it -- and Grail's
        # Werkzeug cannot follow a redirect for us (`follow_redirects=True`
        # raises TypeError on a `header_property`), so ask for the target.
        page = self.client.get(
            "/policies/%s" % policy.policy_id).data.decode()
        self.assertIn("Starts %s" % policy.policy_start_date, page)

    def test_a_claim_outside_the_term_says_so_rather_than_saying_lapsed(self):
        today = date.today()
        not_started = [p for p in self.book()
                       if today < p.policy_start_date and p.policy_lapse_date is None]
        if not not_started:
            self.skipTest("every term in the book has started -- nothing to check")
        policy_id = not_started[0].policy_id
        r = self._file(policy_id)
        self.assertEqual(r.status_code, 302)
        claim = self.newest_claim(self.book()[policy_id])
        self.assertEqual(claim.status, "Denied")
        self.assertEqual(claim.approved, usd("0.00"))
        self.assertEqual(claim.reason, "Event outside policy term")
        # #49: and the identifier a checking agent reads, which is what tells
        # this apart from a lapse without parsing the sentence.
        self.assertEqual(claim.rule, "event-outside-term")

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
        claim = self.newest_claim(policy)
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

        claim = self.newest_claim(self.book()[ACTIVE_RULES])
        expected = bf_app.brainfreeze.adjudicate(
            claim.requested, limit, deductible, used)
        self.assertEqual(claim.status, expected.status)
        self.assertEqual(claim.approved, expected.amount)

    def test_a_claim_on_a_lapsed_policy_is_refused_for_the_lapse(self):
        r = self._file(LAPSED)
        self.assertEqual(r.status_code, 302)
        claim = self.newest_claim(self.book()[LAPSED])
        self.assertEqual(claim.status, "Denied")
        self.assertEqual(claim.reason, "Policy lapsed")
        self.assertEqual(claim.rule, "policy-lapsed")
        self.assertEqual(claim.approved, usd("0.00"))

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

        claim = self.newest_claim(self.book()[CUJ4])
        self.assertEqual(claim.flavour, "Mint choc chip")
        self.assertEqual(claim.toppings, ("Sprinkles", "Hot fudge"))

        # and it survives the commit, read back from the database
        self.assertEqual(self.newest_claim(gemdb.root["brainfreeze"][CUJ4]).flavour,
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
        claim = self.newest_claim(self.book()[ACTIVE])
        self.assertIsNone(claim.flavour)
        self.assertEqual(claim.toppings, ())

    def test_the_claimant_never_enters_an_amount(self):
        # The figure is derived from the episode, so the form must not offer
        # anywhere to type one.
        body = self.client.get(
            "/policies/%s/claims/new" % ACTIVE_READONLY).data.decode()
        self.assertNotIn('name="amount"', body)


@unittest.skipIf(gemdb is None, "needs the database -- run under gemdb")
class TheJsonApi(unittest.TestCase):
    """Issue #50: the same objects, over `curl`.

    The shapes are pinned in `tests/test_api.py`, which runs under CPython
    against a seeded book. What is left for here is what only a live database
    can answer: that the routes exist, that they answer JSON rather than an
    HTML error page, and -- the one that matters -- that the money in a body
    is the exact figure the model holds, in a runtime whose Decimals do not
    keep their trailing zeros.
    """

    @classmethod
    def setUpClass(cls):
        # Nothing here writes, so it does not need its own seed -- but it
        # must not depend on another class having run first either.
        try:
            gemdb.root["brainfreeze"]
        except KeyError:
            gemdb.root["brainfreeze"] = seed.load()
            gemdb.commit()
        cls.app = bf_app.create_app()
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app.test_client()

    def book(self):
        return gemdb.root["brainfreeze"]

    def get(self, path, status=200):
        response = self.client.get(path)
        self.assertEqual(response.status_code, status, path)
        self.assertIn("application/json", response.headers["Content-Type"])
        return json.loads(response.data.decode())

    def post(self, path, payload, status=200):
        response = self.client.post(
            path, data=json.dumps(payload),
            content_type="application/json")
        self.assertEqual(response.status_code, status, path)
        self.assertIn("application/json", response.headers["Content-Type"])
        return json.loads(response.data.decode())

    # -- the questionnaire, as data --------------------------------------

    def test_the_questions_are_the_ones_the_form_asks(self):
        body = self.get("/api/questions")
        names = [q["name"] for q in body["questions"]]
        self.assertEqual(names, ["age", "migraine_history",
                                 "tension_type_headache_history",
                                 "typical_consumption_speed",
                                 "favourite_trigger"])
        # FR-5.2: sex is in the CSVs and carries no weight in the model, so
        # the JSON surface does not ask for it either.
        self.assertNotIn("sex", json.dumps(body).lower())

    def test_the_options_are_the_values_the_model_accepts(self):
        body = self.get("/api/questions")
        by_name = {q["name"]: q for q in body["questions"]}
        speeds = [o["value"] for o in by_name["typical_consumption_speed"]["options"]]
        self.assertEqual(speeds, ["slow", "moderate", "fast"])
        triggers = [o["value"] for o in by_name["favourite_trigger"]["options"]]
        self.assertEqual(triggers, bf_app.TRIGGERS)

    def test_the_answers_it_describes_are_the_answers_it_prices(self):
        # The pair is the point: GET the questions, POST them back.
        questions = self.get("/api/questions")["questions"]
        answers = {q["name"]: q["default"] for q in questions}
        body = self.post("/api/quote", answers)
        self.assertEqual(body["answers"], answers)
        self.assertIn("Standard", body["quote"]["plans"])

    # -- pricing ----------------------------------------------------------

    def test_a_quote_is_the_models_quote(self):
        body = self.post("/api/quote", {
            "age": 11, "migraine_history": False,
            "tension_type_headache_history": False,
            "typical_consumption_speed": "fast",
            "favourite_trigger": "slushie"})
        offer = bf_app.brainfreeze.quote(11, False, False, "fast", "slushie")
        self.assertEqual(body["quote"]["score"], offer.score)
        self.assertEqual(body["quote"]["tier"], "High")
        self.assertEqual(body["quote"]["plans"]["Standard"]["annual"], "171.00")

    def test_money_in_a_body_is_a_string_and_not_a_number(self):
        # The decision this card turns on. `str()` on a Decimal inside the
        # database drops the trailing zero, so this would read "171.0" if the
        # serialiser were not doing the two places itself -- and a float would
        # put back the disagreement #68 removed.
        plan = self.post("/api/quote", {
            "age": 11, "typical_consumption_speed": "fast",
            "favourite_trigger": "slushie"})["quote"]["plans"]["Standard"]
        for key in ("annual", "monthly", "limit", "deductible"):
            self.assertIsInstance(plan[key], str, key)
        self.assertEqual(plan["annual"], "171.00")
        self.assertEqual(plan["deductible"], "5.00")

    def test_a_figure_from_the_wire_goes_back_into_the_model_unchanged(self):
        body = self.get("/api/policy/%s" % LAPSES_LATER)
        policy = self.book()[LAPSES_LATER]
        self.assertEqual(usd(body["annual_premium"]), policy.annual_premium)
        self.assertEqual(usd(body["total_paid"]), policy.total_paid)
        self.assertEqual(usd(body["coverage_limit"]), policy.coverage_limit)

    def test_an_unpriceable_answer_is_a_400_and_not_a_500(self):
        # Without validation this reaches a KeyError inside the risk model and
        # the caller gets an HTML traceback page from a JSON endpoint.
        body = self.post("/api/quote", {"favourite_trigger": "gravel"},
                         status=400)
        self.assertIn("error", body)
        body = self.post("/api/quote", {"age": "eleven"}, status=400)
        self.assertIn("error", body)

    def test_a_quote_with_no_body_at_all_says_so(self):
        response = self.client.post("/api/quote")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", json.loads(response.data.decode()))

    def test_pricing_commits_nothing(self):
        # The JSON surface is read-only. /api/quote is a POST because it
        # carries a body, not because it writes.
        before = len(self.book())
        self.post("/api/quote", {"age": 11})
        self.assertEqual(len(self.book()), before)

    # -- the book ---------------------------------------------------------

    def test_the_policies_endpoint_lists_the_whole_book(self):
        # The HTML picker pages because Grail renders each row in a forked
        # green thread; JSON has no such cost, and a script wants all of it.
        body = self.get("/api/policies")
        self.assertEqual(body["count"], len(self.book()))
        self.assertEqual(len(body["policies"]), body["count"])
        ids = [p["policy_id"] for p in body["policies"]]
        self.assertEqual(ids, sorted(ids))

    def test_one_policy_carries_its_whole_history(self):
        policy = self.book()[LAPSES_LATER]
        body = self.get("/api/policy/%s" % LAPSES_LATER)
        self.assertEqual(len(body["events"]), len(policy.events))
        claimed = [e for e in body["events"] if e["claim"] is not None]
        self.assertEqual(len(claimed), len(policy.claims))

    def test_a_lapsed_policy_says_why_rather_than_how_to_phrase_it(self):
        body = self.get("/api/policy/%s" % LAPSED)
        self.assertFalse(body["in_force"])
        self.assertEqual(body["no_cover_reason"], "Policy lapsed")

    def test_an_unknown_policy_is_a_json_404_not_an_html_one(self):
        body = self.get("/api/policy/BF-999999", status=404)
        self.assertIn("error", body)
        self.assertIn("BF-999999", body["error"])

    # -- one claim --------------------------------------------------------

    def test_a_claim_can_be_fetched_by_its_own_id(self):
        # The HTML route needs the policy id as well; a claim id is enough
        # here, which is what makes it useful from a shell.
        policy = self.book()[LAPSES_LATER]
        claim = policy.claims[0]
        body = self.get("/api/claim/%s" % claim.claim_id)
        self.assertEqual(body["policy_id"], LAPSES_LATER)
        self.assertEqual(body["claim"]["claim_id"], claim.claim_id)
        self.assertEqual(usd(body["claim"]["approved"]), claim.approved)
        self.assertIsNotNone(body["event"]["event_id"])

    def test_a_refused_claim_carries_the_reason_it_was_refused(self):
        policy = self.book()[LAPSES_LATER]
        refused = [c for c in policy.claims if not c.is_approved][0]
        body = self.get("/api/claim/%s" % refused.claim_id)
        self.assertFalse(body["claim"]["is_approved"])
        self.assertEqual(body["claim"]["reason"], refused.reason)
        self.assertEqual(body["claim"]["approved"], "0.00")

    def test_an_unknown_claim_is_a_json_404(self):
        body = self.get("/api/claim/CLM-999999", status=404)
        self.assertIn("error", body)

    # -- the aggregates ---------------------------------------------------

    def test_the_stats_agree_with_the_book_they_came_from(self):
        book = self.book()
        body = self.get("/api/stats")
        self.assertEqual(body["policy_count"], len(book))
        self.assertEqual(body["event_count"], len(book.events))
        self.assertEqual(usd(body["premium"]), book.total_premium)
        self.assertEqual(usd(body["paid"]), book.total_paid)
        self.assertEqual(body["loss_ratio"], book.loss_ratio)

    def test_the_stats_are_the_analysis_helpers(self):
        body = self.get("/api/stats")
        self.assertEqual(body["loss_ratio_by_tier"],
                         bf_app.brainfreeze.loss_ratio_by_tier(self.book()))
        self.assertIn("reason", body["denial_reasons"][0])

    # -- and the HTML surface is untouched --------------------------------

    def test_the_html_routes_still_answer_html(self):
        response = self.client.get("/policies/%s" % ACTIVE_READONLY)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["Content-Type"])

    def test_an_unknown_policy_is_still_an_html_404_on_the_html_route(self):
        # The JSON 404s are returned by the API handlers themselves rather
        # than by a global error handler, precisely so this stays true.
        self.assertEqual(
            self.client.get("/policies/BF-999999").status_code, 404)


if __name__ == "__main__":
    unittest.main()
