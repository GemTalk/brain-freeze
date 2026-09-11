"""The JSON surface, driven the way a script would drive it.

An HTTP client rather than a browser, on purpose. This surface answers `curl`;
putting a browser in front of it would test Chromium's JSON viewer and would
make "the same objects, no second model" harder to see rather than easier.

The money rule is checked by walking every payload, and which keys carry money
is taken from `wire.MONEY_KEYS` rather than restated here. A decoded payload
has nothing left to recognise a figure by except its key, so a list copied
into this file would quietly stop covering the next money field somebody adds.
`tests/test_api.py` fails if that list and the serialiser disagree.
"""

import json
import os
import re
import sys

from behave import then, when

from environment import REPO, fetch_json, keep

# The serialiser, for the one piece of knowledge this file must not restate.
# `web/` is a plain directory rather than a package, so it goes on the path.
if os.path.join(REPO, "web") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "web"))

import wire                                  # noqa: E402  (needs the path first)

#: The policy the mockups are drawn from: active, a full history, and a lapse
#: date far enough out that it is still in force.
MOCKUP = "BF-100539"

#: What `gemdb tools/seed.py` makes. Scenarios that buy a policy push the live
#: count above it, so this is a floor and never an equality.
SEEDED_POLICIES = 900

#: The five answers the price depends on, spelled as the model spells them.
THE_FIVE = ["age", "migraine_history", "tension_type_headache_history",
            "typical_consumption_speed", "favourite_trigger"]

#: Exactly two decimal places, no symbol, no grouping, optionally negative.
EXACT_MONEY = re.compile(r"^-?\d+\.\d\d$")

#: Every key that carries money, anywhere in any payload here -- from the
#: module that decides which those are.
MONEY_KEYS = wire.MONEY_KEYS


def walk(value, path="payload"):
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


def last(context):
    assert hasattr(context, "payload"), "no payload has been fetched yet"
    return context.payload


def get(context, path):
    context.status, context.payload = fetch_json(context, path)
    return context.payload


# -- asking ---------------------------------------------------------------

@when('I ask for the questions')
def ask_for_questions(context):
    get(context, "/api/questions")


@when('I ask for the whole book')
@when('I ask for the whole book again')
def ask_for_book(context):
    context.book_payload = get(context, "/api/policies")


@when('I ask for the policy {policy_id}')
def ask_for_policy(context, policy_id):
    context.policy_id = policy_id
    context.policy_payload = get(context, "/api/policy/%s" % policy_id)


@when('I ask for the statistics')
def ask_for_stats(context):
    context.stats_payload = get(context, "/api/stats")


@when('I ask for a policy that does not exist')
def ask_for_a_missing_policy(context):
    context.status, context.payload = fetch_json(context, "/api/policy/BF-000000")


@when('I ask for a claim on that policy by its id alone')
def ask_for_a_claim(context):
    """The claim id is the whole address -- no policy id, no event index.

    That is most of what makes this endpoint useful from a shell, and it is
    only possible because a claim is an object the book can be searched for
    rather than a row in a table keyed by something else.
    """
    claims = [e["claim"] for e in context.policy_payload["events"]
              if e.get("claim")]
    assert claims, "%s has no claims to ask about" % context.policy_id
    context.claim_id = claims[0]["claim_id"]
    context.claim_payload = get(context, "/api/claim/%s" % context.claim_id)


# -- answering ------------------------------------------------------------

@when('I answer them exactly as they were offered')
def answer_as_offered(context):
    """The round trip is the point: every answer posted back is a default the
    questionnaire itself published. A default the parser then refuses would
    be a surface that cannot be used by the script it documents."""
    context.answers = {q["name"]: q["default"] for q in last(context)["questions"]}
    context.status, context.payload = fetch_json(
        context, "/api/quote", method="POST", body=context.answers)
    assert context.status == 200, context.payload


@when('I send an answer the model does not accept')
def send_a_bad_answer(context):
    bad = dict(context.answers)
    bad["typical_consumption_speed"] = "at the speed of light"
    context.status, context.payload = fetch_json(
        context, "/api/quote", method="POST", body=bad)


@when('I open the same policy in the browser')
def open_the_same_policy(context):
    context.page.goto("%s/policies/%s" % (context.base_url, context.policy_id),
                      wait_until="load")


# -- what came back -------------------------------------------------------

@then('the questions name the five things the price depends on')
def questions_name_the_five(context):
    names = [q["name"] for q in last(context)["questions"]]
    assert names == THE_FIVE, "the questionnaire asks %s" % (names,)


@then('every question offers the values the model will accept')
def questions_offer_values(context):
    for question in last(context)["questions"]:
        if "options" not in question:
            continue
        values = [o["value"] for o in question["options"]]
        assert question["default"] in values, (
            "%s defaults to %r, which is not one of %s"
            % (question["name"], question["default"], values))


@then('I am quoted a score, a band and three priced plans')
def quoted_three_plans(context):
    quote = last(context)["quote"]
    assert isinstance(quote["score"], float), quote["score"]
    assert quote["risk_tier"] in ("Low", "Medium", "High"), quote["risk_tier"]
    assert sorted(quote["plans"]) == ["Basic", "Premium", "Standard"], quote["plans"]
    assert quote["breakdown"], "a price with no reasoning cannot be explained"


@then('the answers come back with the price')
def answers_come_back(context):
    """Reply and request together are a fixture: replay one, get the other."""
    returned = last(context)["answers"]
    assert sorted(returned) == sorted(THE_FIVE), returned
    assert returned["favourite_trigger"] == context.answers["favourite_trigger"]


@then('I am refused with a message naming the field at fault')
def refused_naming_the_field(context):
    assert context.status == 400, context.status
    message = last(context)["error"]
    assert "typical_consumption_speed" in message, message
    assert "quote" not in last(context), "a refused answer was priced anyway"


@then('the book holds every policy the seed made')
def book_holds_everyone(context):
    payload = last(context)
    assert payload["count"] >= SEEDED_POLICIES, payload["count"]
    assert len(payload["policies"]) == payload["count"]


@then('the policy carries its whole history, treats and claims alike')
def policy_carries_history(context):
    payload = last(context)
    events = payload["events"]
    assert events, "a policy with no events cannot answer how often a treat hurt"
    assert any(e.get("claim") for e in events), "no claims on the mockup policy"
    assert any(not e.get("claim") for e in events), (
        "every event was claimed -- the treats that hurt nobody are the "
        "denominator, and a surface that drops them cannot be asked how "
        "often a cold treat causes brain freeze")


@then('the page and the payload agree about what it has been paid')
def page_agrees_with_payload(context):
    paid = context.policy_payload["total_paid"]
    body = context.page.inner_text("body")
    assert ("$%s" % paid) in body, (
        "the JSON says %s was paid and the page does not show it" % paid)


@then('the claim comes back with the terms it was judged by')
def claim_comes_back(context):
    payload = last(context)
    assert payload["claim"]["claim_id"] == context.claim_id
    assert payload["policy_id"] == context.policy_id
    for term in ("coverage_limit", "deductible"):
        assert payload[term] is not None, (
            "without %s the figures do not explain themselves" % term)


@then('I am told there is no such policy, in JSON rather than in HTML')
def missing_policy_is_json(context):
    assert context.status == 404, context.status
    assert "BF-000000" in context.payload["error"], context.payload


@then('the loss ratio is reported by tier and by plan')
def loss_ratio_reported(context):
    payload = last(context)
    assert sorted(payload["loss_ratio_by_tier"]) == ["High", "Low", "Medium"]
    assert payload["loss_ratio_by_plan"], "no loss ratio by plan"


@then('the refusals are counted by reason')
def refusals_counted(context):
    reasons = last(context)["denial_reasons"]
    assert reasons, "no refusals reported"
    counts = [r["claims"] for r in reasons]
    assert counts == sorted(counts, reverse=True), "commonest first: %s" % counts


@then('the statistics agree with the policies about how many there are')
def stats_agree_with_book(context):
    assert context.stats_payload["policy_count"] == context.book_payload["count"], (
        "the statistics say %d policies and the book lists %d"
        % (context.stats_payload["policy_count"], context.book_payload["count"]))


# -- the property that holds everywhere -----------------------------------

@then('every figure that is money is an exact decimal string')
def money_is_an_exact_string(context):
    wrong = []
    for path, value in walk(last(context)):
        key = path.rsplit(".", 1)[-1]
        if key not in MONEY_KEYS or value is None:
            continue
        if not (isinstance(value, str) and EXACT_MONEY.match(value)):
            wrong.append("%s = %r" % (path, value))
    assert not wrong, (
        "money on the wire has to be an exact decimal string:\n  %s"
        % "\n  ".join(wrong))


# -- evidence -------------------------------------------------------------

@then('I keep the payload as "{name}"')
def keep_the_payload(context, name):
    path = keep(context, name, json.dumps(last(context), indent=2, sort_keys=True))
    print("      %s" % path.rsplit("artifacts/", 1)[-1])
