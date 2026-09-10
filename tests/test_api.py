"""The JSON surface: what the objects look like on the wire.

Run: python3 -m unittest tests.test_api -v

Two halves, and both of them run under plain CPython, which is the point of
splitting them out of `tests/test_app.py`. That module needs a live database
and skips everywhere else, so pinning the JSON API only there would leave the
one genuinely interesting decision in this work -- what money looks like in a
JSON body -- untested on the machine most likely to change it.

* `brainfreeze.wire` turns model objects into JSON-ready dicts. It imports
  nothing from `app`, so it can be driven from the real seeded book.
* The routes themselves are read out of `app.py` as a syntax tree, the same
  trick `tests/test_refresh.py` uses, because `app.py` imports `gemdb` and
  `flask` and neither exists out here. What that pins is the contract from
  issue #50 -- six paths, and which verbs they answer.

MONEY ON THE WIRE

`json.dumps` cannot serialise a `decimal.Decimal`, so a JSON API has to say
what money is. It is an exact decimal string here -- `"92081.22"` -- always
two places, no symbol and no grouping, and `null` when no money was recorded.

Not a float, which would put back the two answers `brainfreeze.money` exists
to remove. Not integer cents either, which would be exact but would ask every
reader to divide by a hundred, and dividing money is where the bugs live. A
string goes back into `money.usd()` unchanged, so the wire format is the same
text the model already accepts as input.

The format itself is `money.wire_usd` and is pinned in `tests/test_money.py`,
which runs inside the database too -- and inside the database is where the
naive spellings of it come apart. What these tests check is that every money
field in every payload actually goes through it.
"""

import ast
import json
import os
import unittest
from datetime import date
from decimal import Decimal

import brainfreeze
import seed
from brainfreeze import wire
from brainfreeze.money import format_usd, usd, wire_usd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(REPO_ROOT, "app.py")


def app_namespace(*names):
    """Run just these top-level definitions out of `app.py`.

    `import app` cannot happen here -- it needs `gemdb` and `flask` -- but the
    questionnaire and the answer-checking beneath `/api/quote` are plain
    Python that touches neither, and they are worth more than a syntax tree
    can say about them. So the file is parsed, the named statements are
    lifted out, and those alone are executed.

    Narrow on purpose: it will raise rather than quietly return an empty
    namespace if a name is not found at the top level.
    """
    with open(APP) as handle:
        tree = ast.parse(handle.read(), filename=APP)
    wanted, body = set(names), []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            body.append(node)
            wanted.discard(node.name)
        elif isinstance(node, ast.Assign):
            bound = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if set(bound) & wanted:
                body.append(node)
                wanted.difference_update(bound)
    if wanted:
        raise AssertionError("app.py has no top-level %s" % ", ".join(sorted(wanted)))
    namespace = {"brainfreeze": brainfreeze}
    exec(compile(ast.Module(body=body, type_ignores=[]), APP, "exec"), namespace)
    return namespace


#: Every key in the payloads below that carries money. Each one is an exact
#: decimal string or None -- never a float, and never a Decimal, which would
#: not have survived `json.dumps` in the first place.
MONEY_KEYS = frozenset([
    "annual_premium", "monthly_premium", "coverage_limit", "deductible",
    "total_paid", "requested", "approved", "premium", "paid", "annual",
    "monthly", "limit",
])

#: The policy the mockups are drawn from: active, four approved claims,
#: $179.97 paid, lapses 2027-03-10.
MOCKUP = "BF-100539"


def walk(value, path=""):
    """Every (path, value) pair in a nested payload, leaves included."""
    yield path, value
    if isinstance(value, dict):
        for key in value:
            for pair in walk(value[key], "%s.%s" % (path, key)):
                yield pair
    elif isinstance(value, list):
        for index, item in enumerate(value):
            for pair in walk(item, "%s[%d]" % (path, index)):
                yield pair


class MoneyOnTheWire(unittest.TestCase):
    """`wire.money` is the single door a Decimal leaves by.

    The format itself -- two places, no symbol, half-up, exact -- is pinned in
    `tests/test_money.py`, beside the rest of the money rules and where it
    also runs inside the database. What is pinned here is that the serialiser
    uses that function and not another one.
    """

    def test_it_is_the_money_modules_wire_format(self):
        self.assertIs(wire.money, wire_usd)

    def test_a_decimal_is_the_thing_json_cannot_take(self):
        # The reason any of this had to be decided. Not a test of Python: it
        # is the constraint the wire format exists to satisfy.
        with self.assertRaises(TypeError):
            json.dumps({"premium": usd("92081.22")})
        self.assertEqual(json.dumps({"premium": wire.money(usd("92081.22"))}),
                         '{"premium": "92081.22"}')

    def test_the_display_string_never_reaches_a_payload(self):
        # `format_usd` is the other way to turn money into text, and
        # "$92,081.22" is not a number a caller can parse.
        self.assertNotEqual(wire.money(usd("92081.22")),
                            format_usd(usd("92081.22")))


class Payloads(unittest.TestCase):
    """The real book, serialised. Every figure is one the CSVs already hold."""

    @classmethod
    def setUpClass(cls):
        cls.book = seed.load()

    def money_leaves(self, payload):
        return [(path, value) for path, value in walk(payload)
                if path.rsplit(".", 1)[-1].split("[")[0] in MONEY_KEYS]

    def assert_wire_safe(self, payload):
        """It survives `json.dumps`, and every money field is a string."""
        json.dumps(payload)
        found = self.money_leaves(payload)
        self.assertTrue(found, "no money in this payload to check")
        for path, value in found:
            self.assertTrue(value is None or isinstance(value, str),
                            "%s is %r -- money on the wire is a string"
                            % (path, value))

    def test_a_policy_serialises(self):
        payload = wire.policy(self.book[MOCKUP], date(2026, 9, 9))
        self.assert_wire_safe(payload)
        self.assertEqual(payload["policy_id"], MOCKUP)
        self.assertEqual(payload["plan_name"], "Standard")
        self.assertEqual(payload["total_paid"], "179.97")
        self.assertEqual(payload["claim_count"], 8)
        self.assertEqual(payload["approved_claim_count"], 4)
        self.assertEqual(payload["claims_remaining_this_year"], 0)

    def test_a_policy_says_whether_cover_is_running_rather_than_how_to_say_so(self):
        # The picker renders "Lapses 2027-03-10"; a script wants the fact, not
        # the sentence. policy_status records the policy's fate over the whole
        # term and is not the same question -- this one is stored "Lapsed"
        # while cover is still running.
        payload = wire.policy(self.book[MOCKUP], date(2026, 9, 9))
        self.assertEqual(payload["policy_status"], "Lapsed")
        self.assertTrue(payload["in_force"])
        self.assertIsNone(payload["no_cover_reason"])
        self.assertEqual(payload["policy_lapse_date"], "2027-03-10")

    def test_cover_is_answered_as_of_a_date(self):
        payload = wire.policy(self.book[MOCKUP], date(2027, 6, 1))
        self.assertFalse(payload["in_force"])
        self.assertEqual(payload["no_cover_reason"], "Policy lapsed")
        self.assertEqual(payload["as_of"], "2027-06-01")

    def test_the_detail_adds_every_event_not_just_the_claims(self):
        # Same argument as the history screen: the treats that hurt nobody are
        # the denominator.
        policy = self.book[MOCKUP]
        payload = wire.policy_detail(policy, date(2026, 9, 9))
        self.assert_wire_safe(payload)
        self.assertEqual(len(payload["events"]), len(policy.events))
        self.assertGreater(len(payload["events"]), len(policy.claims))
        unclaimed = [e for e in payload["events"] if e["claim"] is None]
        self.assertTrue(unclaimed)

    def test_events_keep_the_order_the_model_keeps_them_in(self):
        payload = wire.policy_detail(self.book[MOCKUP], date(2026, 9, 9))
        dates = [e["event_date"] for e in payload["events"]]
        self.assertEqual(dates, sorted(dates))

    def test_a_claim_carries_both_figures_and_the_reason(self):
        policy = self.book[MOCKUP]
        refused = [c for c in policy.claims if not c.is_approved][0]
        payload = wire.claim(refused)
        self.assert_wire_safe(payload)
        self.assertFalse(payload["is_approved"])
        self.assertEqual(payload["approved"], "0.00")
        self.assertEqual(payload["reason"], "Exceeded annual claim limit")

    def test_a_claim_from_before_the_new_questions_reads_as_null(self):
        # CUJ-4: the 2,172 seeded claims have no flavour slot of their own.
        claim = self.book[MOCKUP].claims[0]
        payload = wire.claim(claim)
        self.assertIsNone(payload["flavour"])
        self.assertEqual(payload["toppings"], [])

    def test_a_claim_detail_names_its_policy_and_the_terms_it_was_judged_by(self):
        policy = self.book[MOCKUP]
        event = [e for e in policy.events if e.claim is not None][0]
        payload = wire.claim_detail(policy, event)
        self.assert_wire_safe(payload)
        self.assertEqual(payload["policy_id"], MOCKUP)
        self.assertEqual(payload["claim"]["claim_id"], event.claim.claim_id)
        self.assertEqual(payload["coverage_limit"], "60.00")
        self.assertEqual(payload["deductible"], "5.00")
        # the event is here too, and does not repeat the claim inside itself
        self.assertEqual(payload["event"]["event_id"], event.event_id)
        self.assertNotIn("claim", payload["event"])

    def test_a_quote_serialises_with_its_reasoning(self):
        # The mockup quote: age 11, eats fast, favourite is a slushie.
        from brainfreeze import quote as price
        payload = wire.quote(price(11, False, False, "fast", "slushie"))
        self.assert_wire_safe(payload)
        self.assertEqual(payload["score"], 75.0)
        self.assertEqual(payload["tier"], "High")
        self.assertEqual(payload["plans"]["Standard"]["annual"], "171.00")
        self.assertEqual(payload["plans"]["Standard"]["monthly"], "14.25")
        self.assertEqual(payload["plans"]["Premium"]["deductible"], "0.00")
        # CUJ-2 needs the breakdown, not just the total
        self.assertEqual(payload["breakdown"][0],
                         {"label": "Everyone starts here", "points": 45.0})

    def test_the_stats_are_the_analysis_helpers_and_not_a_second_count(self):
        payload = wire.stats(self.book)
        self.assert_wire_safe(payload)
        self.assertEqual(payload["policy_count"], 900)
        self.assertEqual(payload["event_count"], 4993)
        self.assertEqual(payload["claim_count"], 2172)
        self.assertEqual(payload["approved_claim_count"], 1691)
        self.assertEqual(payload["premium"], "92081.22")
        self.assertEqual(payload["paid"], "54671.44")
        self.assertEqual(payload["loss_ratio"], 0.594)
        self.assertEqual(payload["claim_approval_rate"], 0.7785)
        self.assertEqual(payload["loss_ratio_by_tier"],
                         {"Low": 0.409, "Medium": 0.729, "High": 0.501})
        self.assertEqual(payload["denial_reasons"][0],
                         {"reason": "Policy lapsed", "claims": 254})

    def test_a_ratio_is_still_a_float_because_it_is_not_money(self):
        # The rule is about money, not about every number. A loss ratio is a
        # measurement and it is honestly a float -- see brainfreeze.analysis.
        payload = wire.stats(self.book)
        self.assertIsInstance(payload["loss_ratio"], float)
        self.assertIsInstance(payload["loss_ratio_by_plan"]["Basic"], float)

    def test_nothing_anywhere_in_the_book_survives_as_a_decimal(self):
        # A Decimal that reached a payload would raise inside json.dumps, so
        # this is the whole guarantee, checked over real rows rather than
        # over one hand-built object.
        for policy in list(self.book)[:25]:
            payload = wire.policy_detail(policy, date(2026, 9, 9))
            json.dumps(payload)
            for path, value in walk(payload):
                self.assertNotIsInstance(value, Decimal, path)


class TheQuestionnaire(unittest.TestCase):
    """What `/api/questions` publishes, and what `/api/quote` will accept.

    These two have to be one thing: a caller reads the questions, fills them
    in and posts them back, so a default the questionnaire offers that the
    parser then refuses is a broken round trip. Both halves are plain Python
    inside `app.py`, so they can be run out here -- see `app_namespace`.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = app_namespace("SPEED_BANDS", "TRIGGERS", "quote_questions",
                                "_flag", "_json_answers")

    def questions(self):
        return self.app["quote_questions"]()

    def answers(self, **overrides):
        return self.app["_json_answers"](overrides)

    def test_the_questionnaire_is_json(self):
        json.dumps(self.questions())

    def test_it_asks_the_five_questions_the_model_prices(self):
        names = [q["name"] for q in self.questions()]
        self.assertEqual(names, ["age", "migraine_history",
                                 "tension_type_headache_history",
                                 "typical_consumption_speed",
                                 "favourite_trigger"])
        # FR-5.2 asks for sex; the risk model gives it no weight, so neither
        # surface poses a question that changes nothing.
        self.assertNotIn("sex", json.dumps(self.questions()).lower())

    def test_its_options_are_the_values_the_model_accepts(self):
        by_name = {q["name"]: q for q in self.questions()}
        self.assertEqual(
            [o["value"] for o in by_name["favourite_trigger"]["options"]],
            brainfreeze.TRIGGER_TYPES)
        self.assertEqual(
            [o["value"] for o in by_name["typical_consumption_speed"]["options"]],
            ["slow", "moderate", "fast"])

    def test_answering_it_with_its_own_defaults_prices(self):
        # The round trip. Every default it publishes goes back in unchanged,
        # and what comes out is what the model can be called with.
        defaults = {q["name"]: q["default"] for q in self.questions()}
        answers = self.app["_json_answers"](defaults)
        self.assertEqual(answers, defaults)
        offer = brainfreeze.quote(**answers)
        self.assertEqual(offer.tier, brainfreeze.risk_tier(offer.score))

    def test_an_empty_body_prices_the_defaults(self):
        self.assertEqual(self.answers(), {q["name"]: q["default"]
                                          for q in self.questions()})

    def test_an_unknown_trigger_is_refused_by_name(self):
        # Left unchecked this is a KeyError inside TRIGGER_RISK_MULT, which
        # reaches the caller as a 500 with an HTML traceback in it.
        with self.assertRaises(ValueError) as caught:
            self.answers(favourite_trigger="gravel")
        self.assertIn("favourite_trigger", str(caught.exception))
        self.assertIn("slushie", str(caught.exception))

    def test_an_unknown_speed_is_refused_by_name(self):
        with self.assertRaises(ValueError) as caught:
            self.answers(typical_consumption_speed="briskly")
        self.assertIn("typical_consumption_speed", str(caught.exception))

    def test_an_age_that_is_not_a_number_is_refused(self):
        with self.assertRaises(ValueError):
            self.answers(age="eleven")
        with self.assertRaises(ValueError):
            self.answers(age=None)

    def test_the_flags_take_json_booleans(self):
        answers = self.answers(migraine_history=True,
                               tension_type_headache_history=False)
        self.assertIs(answers["migraine_history"], True)
        self.assertIs(answers["tension_type_headache_history"], False)

    def test_the_flags_also_take_what_the_html_form_sends(self):
        # So a body captured from the form's own vocabulary still replays.
        self.assertIs(self.answers(migraine_history="yes")["migraine_history"], True)
        self.assertIs(self.answers(migraine_history="no")["migraine_history"], False)

    def test_the_answers_are_named_as_the_model_names_them(self):
        # `quote(**answers)` has to work, so these are its parameters and not
        # the form's shorthand.
        brainfreeze.quote(**self.answers())


class TheRouteContract(unittest.TestCase):
    """Issue #50 names six endpoints. `app.py` imports gemdb and flask, so
    this reads them out of the source rather than driving them --
    `tests/test_app.py` does the driving, inside the database."""

    #: path -> the verbs it must answer.
    WANTED = {
        "/api/questions": {"GET"},
        "/api/quote": {"POST"},
        "/api/policies": {"GET"},
        "/api/policy/<policy_id>": {"GET"},
        "/api/claim/<claim_id>": {"GET"},
        "/api/stats": {"GET"},
    }

    def setUp(self):
        with open(APP) as handle:
            self.source = handle.read()
        self.tree = ast.parse(self.source, filename=APP)

    def routes(self):
        """path -> methods, for every `@app.route(...)` in app.py."""
        found = {}
        for node in ast.walk(self.tree):
            for decorator in getattr(node, "decorator_list", []):
                if not (isinstance(decorator, ast.Call)
                        and isinstance(decorator.func, ast.Attribute)
                        and decorator.func.attr == "route"):
                    continue
                path = decorator.args[0].value
                methods = {"GET"}
                for keyword in decorator.keywords:
                    if keyword.arg == "methods":
                        methods = {item.value for item in keyword.value.elts}
                found.setdefault(path, set()).update(methods)
        return found

    def test_all_six_endpoints_are_registered(self):
        found = self.routes()
        for path, methods in self.WANTED.items():
            self.assertIn(path, found, "issue #50 asks for %s" % path)
            self.assertEqual(found[path] & methods, methods,
                             "%s does not answer %s" % (path, sorted(methods)))

    def test_the_html_routes_are_untouched(self):
        # Additive, per the card: the JSON surface goes beside the HTML one.
        #
        # `POST /policies` was on this list until #53. It is the one HTML
        # route that has moved since, and it moved because it was the wrong
        # address: it took the five answers back off the form and priced them
        # a second time. Selling a quote now happens at the quote's own
        # address, and the two that replaced it are listed here so this test
        # goes on saying what it was written to say.
        found = self.routes()
        for path in ("/", "/quote", "/quote/<quote_id>",
                     "/quote/<quote_id>/accept", "/policies/<policy_id>",
                     "/policies/<policy_id>/claims/new",
                     "/policies/<policy_id>/claims",
                     "/policies/<policy_id>/claims/<claim_id>"):
            self.assertIn(path, found)

    def test_the_json_surface_writes_nothing(self):
        # The card asks whether the API should be writable by script. It is
        # not: /api/quote is a POST because it carries a body, but pricing
        # answers commits nothing. Nothing under /api reaches gemdb.commit().
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not node.name.startswith("api_"):
                continue
            for child in ast.walk(node):
                if (isinstance(child, ast.Call)
                        and isinstance(child.func, ast.Attribute)
                        and isinstance(child.func.value, ast.Name)
                        and child.func.value.id == "gemdb"):
                    self.fail("%s calls gemdb.%s -- the JSON surface is "
                              "read-only" % (node.name, child.func.attr))

    def test_no_handler_formats_money_for_itself(self):
        # One home for the money rule. `format_usd` is the display spelling
        # and belongs to the templates; a handler reaching for it, or for
        # `str()` on a premium, is the second answer starting.
        for node in ast.walk(self.tree):
            if not (isinstance(node, ast.FunctionDef)
                    and node.name.startswith("api_")):
                continue
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                    self.assertNotIn(child.func.id, ("format_usd", "float"),
                                     "%s formats money itself" % node.name)

    def test_the_main_guard_is_still_the_last_statement(self):
        # Constraint from app.py's docstring: `gemdb app.py` runs the file top
        # to bottom, so a guard above the templates would serve routes that
        # raise NameError -- and importing the module hides it completely.
        last = self.tree.body[-1]
        self.assertIsInstance(last, ast.If)
        self.assertIn("__main__", ast.dump(last.test))

    def test_the_server_is_still_single_threaded(self):
        # Grail renders each template in a forked green thread and the
        # threaded dev server's ContextVar cannot span them.
        self.assertIn("threaded=False", self.source)


if __name__ == "__main__":
    unittest.main()
