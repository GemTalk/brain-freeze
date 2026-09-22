"""Steps for the demo walked in order.

These deliberately add as little as possible. Where a step already exists --
lapsing from another session, opening a claim form, re-opening a policy -- this
module reaches it through `context.execute_steps` rather than reimplementing
it, so there is one definition of what lapsing means and this file cannot
drift from `cross_surface_steps`.

The figures are read out of `DEMO.md`. That is the whole point of the feature:
`tests/test_demo_script.py` already proves the script's figures are the ones
the rules give, so proving the browser shows the script's figures closes the
loop without either test knowing about the other.
"""

import csv
import os
import re

from behave import then, when

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DEMO = os.path.join(REPO, "DEMO.md")
SEED_CSV = os.path.join(REPO, "data", "policyholders.csv")

#: Money in a DEMO.md table cell, with or without the minus sign the script
#: uses for the deductions. U+2212, not a hyphen -- the document is typeset,
#: and a regex written with `-` silently matches nothing.
TABLE_MONEY = re.compile(r"`[-−]?(\$[\d,]+\.\d{2})`")


def _demo():
    with open(DEMO, encoding="utf-8") as handle:
        return handle.read()


def _beat(number):
    """The text of one beat, by its heading number."""
    text = _demo()
    start = text.index("### %d " % number)
    try:
        end = text.index("### %d " % (number + 1), start)
    except ValueError:
        end = len(text)
    return text[start:end]


def _text(context):
    return context.page.inner_text("body")


@then('the quote scores {score} and bands it {band}')
def quote_scores(context, score, band):
    body = _text(context)
    for wanted in (score, band):
        assert wanted in body, (
            "the quote page does not show %r, and DEMO.md beat 2 tells the "
            "presenter to read it out.\n--- page ---\n%s" % (wanted, body[:800]))


@then('the {plan} plan is priced at the figure DEMO.md quotes')
def plan_priced_as_scripted(context, plan):
    """The annual premium DEMO.md puts in its plans table, against the one the
    browser showed. `context.quoted` was read off the cards by
    `the quote prices all three plans`, so nothing here re-reads the page."""
    # `^\s*` and not `^`: beat 2's plans table sits inside a numbered list,
    # so every row is indented three spaces.
    row = re.search(r"^\s*\|\s*%s\s*\|\s*(\$[\d,]+\.\d{2})\s*\|" % plan,
                    _beat(2), re.MULTILINE)
    assert row, ("DEMO.md beat 2 no longer prices %s in its plans table, so "
                 "there is nothing to check the page against" % plan)
    promised = row.group(1)
    shown = context.quoted[plan]
    assert shown == promised, (
        "DEMO.md tells the room the %s plan is %s a year and the page quoted "
        "%s. One of them is wrong in front of an audience."
        % (plan, promised, shown))


@then('the policy it sold is one the seeded book did not contain')
def policy_is_newly_minted(context):
    """Read from the seed CSV rather than the database: this asserts a fact
    about what the demo MINTS, and a policy that was already there would mean
    beat 2 sold nothing and every id downstream of it has moved."""
    with open(SEED_CSV, encoding="utf-8") as handle:
        seeded = {row["policy_id"] for row in csv.DictReader(handle)}
    assert context.policy_id not in seeded, (
        "%s was already in the seeded book, so beat 2 did not create it"
        % context.policy_id)


@when('I re-open that policy')
def reopen_the_sold_policy(context):
    context.execute_steps('When I re-open the policy %s' % context.policy_id)


@when("I open that policy's claim form")
def claim_form_for_sold_policy(context):
    context.execute_steps(
        'When I open the claim form for %s' % context.policy_id)


@when('another session lapses that policy')
def lapse_the_sold_policy(context):
    context.execute_steps(
        'When %s is lapsed from a session of its own' % context.policy_id)


@then('the decision reads the figures DEMO.md promises')
def decision_matches_the_script(context):
    """Every money figure DEMO.md's decision table puts in backticks has to be
    on the page the presenter will be pointing at."""
    promised = TABLE_MONEY.findall(_beat(3))
    assert len(promised) >= 4, (
        "DEMO.md beat 3 no longer tabulates four figures (found %r), so this "
        "step is checking nothing" % (promised,))

    body = _text(context).replace("\n", " ")
    missing = [figure for figure in promised if figure not in body]
    assert not missing, (
        "DEMO.md beat 3 promises %s and the decision screen does not show %s.\n"
        "The presenter would be reading figures off a page that disagrees "
        "with them.\n--- decision ---\n%s"
        % (", ".join(promised), ", ".join(missing), body[:900]))
