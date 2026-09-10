"""Steps for the three refusals: cover ended, allowance spent, term not begun.

Every scenario here is a pure read. The states they need are already in the
seeded book -- BF-100746 lapsed in July, BF-100539 has spent its four
approvals, and something over a hundred of the 900 terms begin after today --
so nothing files a claim, nothing writes, and re-running them changes nothing.
The count is left vague on purpose, because it falls every day. Reading only
is deliberate as well: a scenario that cannot dirty the book cannot make the
next one fail.

Two things are read besides the page.

`data/policyholders.csv` is read to FIND a policy whose term has not begun. It
is the seed's own input, so a policy that is in the future there is in the
future in the book, and the alternative -- paging the picker looking for a
"Starts ..." tag -- would be slower and no more true. The date moves and the
file does not, so this can run out: when it does the scenario SKIPS with a
sentence saying why, rather than failing in 2027 for a reason that has nothing
to do with the code.

`/api/policy/<id>` is read to get the reason the RULES give, as a string the
adjudicator produced rather than prose a template wrote. That is what makes
"the refusal matches the rules" an assertion instead of a restatement: the
sentence comes off the screen, the reason comes out of the model, and this
file is the only place the two meet.
"""

import csv
import json
import os
import sys
import urllib.request
from datetime import date

from behave import given, then, when

from environment import REPO

if REPO not in sys.path:                    # behave puts features/ on the
    sys.path.insert(0, REPO)                # path, not the repo root
import brainfreeze                          # noqa: E402  (needs the path first)

POLICYHOLDERS_CSV = os.path.join(REPO, "data", "policyholders.csv")

#: The reasons the adjudicator can give for there being no cover. Taken from
#: the library rather than typed here, so a feature file that spells one wrong
#: is caught instead of quietly asserting nothing.
NO_COVER_REASONS = (brainfreeze.REASON_POLICY_LAPSED,
                    brainfreeze.REASON_OUTSIDE_TERM)

API_TIMEOUT_S = 60


# -- reading the two sources ----------------------------------------------

def api_policy(context, policy_id=None):
    """What the rules say about a policy today, as JSON.

    Deliberately not the model loaded into this process: the assertion is
    about the book the app is serving, and a second copy read here could agree
    with the feature file while disagreeing with the server.
    """
    policy_id = policy_id or context.policy_id
    url = "%s/api/policy/%s" % (context.base_url, policy_id)
    with urllib.request.urlopen(url, timeout=API_TIMEOUT_S) as response:
        return json.loads(response.read().decode("utf-8"))


def not_yet_started(today):
    """Policies whose term begins after today and which never lapsed.

    Both halves matter. A policy with a lapse date already passed would be
    refused for the lapse first -- `no_cover_reason_on` tests that before the
    term -- and this is the scenario about a policy that never lapsed at all.
    """
    with open(POLICYHOLDERS_CSV) as handle:
        rows = list(csv.DictReader(handle))
    future = [row for row in rows
              if date.fromisoformat(row["policy_start_date"]) > today
              and not row["policy_lapse_date"]]
    return sorted(future, key=lambda row: row["policy_id"])


def refusals_on_the_page(context):
    """Every warning the claim form is showing, whitespace normalised."""
    warnings = context.page.locator("div.warn")
    return [" ".join(warnings.nth(i).inner_text().split())
            for i in range(warnings.count())]


def the_refusal(context):
    assert getattr(context, "refusal", None), (
        "no refusal has been read yet -- go to the claim form first")
    return context.refusal


# -- picking a policy -----------------------------------------------------

@given('the policy {policy_id}')
@when('the customer opens the policy {policy_id}')
def the_policy(context, policy_id):
    context.policy_id = policy_id
    context.cover_starts = None
    context.page.goto("%s/policies/%s" % (context.base_url, policy_id),
                      wait_until="load")


@given('a policy whose cover has not started yet')
@when('the customer opens a policy whose cover has not started yet')
def a_policy_not_started(context):
    today = date.today()
    candidates = not_yet_started(today)
    if not candidates:
        context.scenario.skip(
            "every term in the seeded book has begun as of %s, so no policy "
            "is left whose cover has not started. The book is fixed and the "
            "date is not: re-generate data/policyholders.csv with terms ahead "
            "of today to get this scenario back." % today)
        return

    row = candidates[0]
    context.policy_id = row["policy_id"]
    context.cover_starts = row["policy_start_date"]
    context.page.goto("%s/policies/%s" % (context.base_url, context.policy_id),
                      wait_until="load")

    # The CSV said so; the book has to agree, or this scenario would be
    # reading one policy and asserting about another.
    facts = api_policy(context)
    assert facts["policy_start_date"] == context.cover_starts, (
        "%s starts %s in data/policyholders.csv but %s in the book"
        % (context.policy_id, context.cover_starts,
           facts["policy_start_date"]))
    assert facts["in_force"] is False, (
        "%s starts on %s, which is after today, and yet the book says it is "
        "in force" % (context.policy_id, context.cover_starts))


@given("the year's approvals are already spent")
def the_years_approvals_are_spent(context):
    """The spent allowance is the refusal only while cover is still running.

    BF-100539 lapses 2027-03-10. After that day the lapse becomes the first
    refusal and the form says so, which would fail this scenario for a reason
    that is not a bug -- so check the calendar, not the app, and say what to
    do about it.
    """
    facts = api_policy(context)
    lapses = facts["policy_lapse_date"]
    ends = facts["policy_end_date"]
    today = date.today()
    if lapses and date.fromisoformat(lapses) < today:
        context.scenario.skip(
            "%s lapsed on %s, so cover ending is now the first refusal and "
            "the spent allowance is no longer what the form would say. Point "
            "this scenario at a policy with its approvals used and a term "
            "still running." % (context.policy_id, lapses))
        return
    if date.fromisoformat(ends) < today:
        context.scenario.skip(
            "the term on %s ended on %s, so the spent allowance is no longer "
            "the refusal it would be shown. Point this scenario at a policy "
            "with its approvals used and a term still running."
            % (context.policy_id, ends))
        return

    assert facts["claims_remaining_this_year"] == 0, (
        "%s has %d of its %d approvals left, so the seeded book no longer "
        "holds it as the policy whose allowance is spent"
        % (context.policy_id, facts["claims_remaining_this_year"],
           brainfreeze.ANNUAL_CLAIM_LIMIT))


# -- what the policy page says --------------------------------------------

@then('the policy page marks cover lapsed on {when}')
def policy_page_marks_lapsed(context, when):
    tag = context.page.locator("p.sub span.tag").inner_text().strip()
    assert tag == "Lapsed %s" % when, (
        "the policy page describes cover as %r, not as lapsed on %s"
        % (tag, when))


@then('the policy page marks cover as starting on the day the term begins')
def policy_page_marks_not_started(context):
    tag = context.page.locator("p.sub span.tag").inner_text().strip()
    assert tag == "Starts %s" % context.cover_starts, (
        "the policy page describes cover as %r, not as starting on %s -- a "
        "term that has not begun must not be shown as anything else"
        % (tag, context.cover_starts))


@then('the policy page shows all {allowed:d} approvals used')
def policy_page_shows_allowance_used(context, allowed):
    assert allowed == brainfreeze.ANNUAL_CLAIM_LIMIT, (
        "the scenario says %d approvals a year and the rules allow %d"
        % (allowed, brainfreeze.ANNUAL_CLAIM_LIMIT))
    body = " ".join(context.page.inner_text("body").split())
    assert "%d/%d claims used" % (allowed, allowed) in body, (
        "the policy page for %s does not show %d/%d claims used"
        % (context.policy_id, allowed, allowed))


@then('the policy still has cover')
def the_policy_still_has_cover(context):
    facts = api_policy(context)
    assert facts["in_force"] is True and facts["no_cover_reason"] is None, (
        "%s is out of cover (%s), so the refusal on its claim form would be "
        "about that rather than about the year's allowance"
        % (context.policy_id, facts["no_cover_reason"]))


# -- the claim form -------------------------------------------------------

@when('the customer goes to file a claim')
def goes_to_file_a_claim(context):
    """By the link a person would use, rather than by typing the URL.

    Reading the warnings is part of arriving, so every scenario that gets here
    has the refusal in hand and none of them has to submit anything to see it.
    """
    link = context.page.locator('a[href$="/claims/new"]')
    assert link.count() == 1, (
        "expected one way to file a claim from %s, found %d"
        % (context.page.url, link.count()))
    link.first.click()
    context.page.wait_for_load_state("load")
    found = refusals_on_the_page(context)
    context.refusals_shown = found
    context.refusal = found[0] if found else None


@then('the claim is refused before a word is typed')
def refused_before_a_word_is_typed(context):
    shown = context.refusals_shown
    assert len(shown) == 1, (
        "expected the claim form for %s to give exactly one reason a claim "
        "would be refused; it gives %d: %r"
        % (context.policy_id, len(shown), shown))
    assert "refused" in shown[0], (
        "the form's warning does not say a claim would be refused: %r"
        % shown[0])


@then('the refusal reads "{sentence}"')
def the_refusal_reads(context, sentence):
    """The whole sentence, not a fragment of it.

    `<the day cover starts>` stands in for the one date that moves, so the
    feature file still carries the wording word for word.
    """
    if "<the day cover starts>" in sentence:
        assert context.cover_starts, "no start date was remembered"
        sentence = sentence.replace("<the day cover starts>",
                                    context.cover_starts)
    assert the_refusal(context) == sentence, (
        "the claim form for %s says\n  %r\nand the scenario expects\n  %r"
        % (context.policy_id, the_refusal(context), sentence))


@then('the rules give "{reason}" as the reason there is no cover')
def the_rules_give_the_reason(context, reason):
    assert reason in NO_COVER_REASONS, (
        "%r is not a reason the rules can give; they give %r"
        % (reason, list(NO_COVER_REASONS)))
    facts = api_policy(context)
    assert facts["no_cover_reason"] == reason, (
        "the claim form for %s shows a refusal, but the rules give %r as the "
        "reason there is no cover, not %r -- the screen and the adjudicator "
        "have drifted apart"
        % (context.policy_id, facts["no_cover_reason"], reason))


# -- the distinction ------------------------------------------------------

@when('that refusal is kept as "{name}"')
def keep_that_refusal(context, name):
    if not hasattr(context, "kept"):
        context.kept = {}
    context.kept[name] = (the_refusal(context), context.policy_id)


def _kept(context, name):
    kept = getattr(context, "kept", {})
    assert name in kept, (
        "no refusal was kept as %r (have %r)" % (name, sorted(kept)))
    return kept[name]


@then('the two refusals are not the same sentence')
def the_two_refusals_differ(context):
    kept = getattr(context, "kept", {})
    assert len(kept) == 2, (
        "expected two refusals to compare, kept %d" % len(kept))
    first, second = [text for text, _ in kept.values()]
    assert first and second, "one of the refusals is empty: %r" % (kept,)
    assert first != second, (
        "both policies are refused with the same sentence:\n  %r\n"
        "One of them lapsed and the other has not started yet. Saying the "
        "same thing about both is a bug this demo has had." % first)


@then('"{ended}" speaks of cover that ended, and "{not_started}" does not')
def only_one_speaks_of_cover_ending(context, ended, not_started):
    """The strict half of the distinction.

    Two different sentences is not enough on its own -- two wordings of
    "lapsed" would pass that. This says the lapse names an ending, the other
    names a beginning, and the policy that never lapsed is not told about a
    lapse in any words at all.
    """
    lapse_text, lapse_id = _kept(context, ended)
    other_text, other_id = _kept(context, not_started)

    assert "ended on" in lapse_text, (
        "%s lapsed, and its refusal does not say when cover ended: %r"
        % (lapse_id, lapse_text))
    assert "does not start until" in other_text, (
        "%s has not started, and its refusal does not say when cover starts: "
        "%r" % (other_id, other_text))
    for forbidden in ("ended", "lapse", "expired"):
        assert forbidden not in other_text.lower(), (
            "the refusal for %s says %r. That policy never lapsed and its "
            "term has not ended -- it has not begun. Telling its customer "
            "otherwise is the bug this check exists for:\n  %r"
            % (other_id, forbidden, other_text))


@then('neither refusal names a date the policy does not have')
def neither_names_a_missing_date(context):
    """The shape the old bug took: a lapse date read off a policy that has
    none renders as the word None in the middle of a sentence."""
    for name, (text, policy_id) in getattr(context, "kept", {}).items():
        assert "None" not in text, (
            "the refusal kept as %r (%s) names a date the policy does not "
            "have: %r" % (name, policy_id, text))


@then('the rules tell the two apart as well')
def the_rules_tell_them_apart(context):
    """Not only the prose. A checking agent reads the reason rather than the
    sentence, and the two policies must not answer it with the same one."""
    reasons = {}
    for name, (_, policy_id) in getattr(context, "kept", {}).items():
        reasons[name] = api_policy(context, policy_id)["no_cover_reason"]

    assert sorted(reasons.values()) == sorted(NO_COVER_REASONS), (
        "the rules give %r for the two policies; expected one %r and one %r"
        % (reasons, brainfreeze.REASON_POLICY_LAPSED,
           brainfreeze.REASON_OUTSIDE_TERM))
