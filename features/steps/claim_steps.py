"""Steps for filing a claim and reading the decision.

Like the quote steps, these read the page rather than the database.
`tests/test_app.py` already drives the same journey against objects, and a
browser repeating that would only be a slower copy of it. What only a browser
can say is that a person is *shown* figures that hold together.

There are two exceptions, and both are deliberate.

The first is that this file imports `brainfreeze`. The demo's whole claim is
that the app REPORTS payouts rather than working them out, and the only way to
test a claim like that is to run the rules independently and check the page
agrees. So `adjudicate` is driven here -- but every input it is given was read
off a page first: the episode cap and the deductible off the policy's own
subtitle, the approvals already used off the policy's own summary card, the
assessed amount off the decision. Nothing is read from the book to do it, and
nothing is hardcoded. If the app ever grows a sum of its own, these two
answers part company and this step is what notices.

The second is `DURATION_SECONDS`, which mirrors four numbers from
`app.DURATION_BANDS`. `app` imports `gemdb` and cannot be imported outside the
database, so the band a duration answer stands for has to be repeated here to
check `assess_amount`. Four constants is a cheap price for proving the
claimant never enters a figure.

Money is Decimal throughout and is never compared to a float -- `usd()` raises
a TypeError on one, which is the point of it.
"""

import re
import sys
from datetime import date

from behave import then, when

from environment import REPO

# behave already puts the repo root on sys.path while step modules load. This
# makes it certain, so reading the rules module does not depend on how behave
# happened to be started.
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import brainfreeze                                            # noqa: E402
from brainfreeze.money import usd                             # noqa: E402


#: `$34.19`, `$1,205.00`. The page also writes a real minus sign (U+2212)
#: before the two figures it takes off, which is why every amount is found by
#: this rather than by slicing off a leading character.
MONEY = re.compile(r"\$[\d,]+\.\d{2}")

#: What each duration answer on the form stands for, in seconds. The copy of
#: record is `app.DURATION_BANDS`; see the module docstring for why it cannot
#: be imported.
DURATION_SECONDS = {
    "Under 30 seconds": 20.0,
    "Half a minute to two": 70.0,
    "Two to ten minutes": 300.0,
    "Longer than ten": 700.0,
}


# -- reading money and figures off a page ---------------------------------

def _money(text, where):
    """The one money figure in this piece of page, as a Decimal.

    Exactly one, on purpose. The row that names the cap reads "Trimmed to your
    $60.00 episode cap  -$39.00" and carries two figures; taking the first
    would silently compare the cap against itself and pass.
    """
    found = MONEY.findall(text)
    assert len(found) == 1, (
        "expected one money figure in %s, found %d in %r" % (where, len(found), text))
    return usd(found[0].replace("$", "").replace(",", ""))


def _decision_row(context, needle):
    """One row of the decision's table, as (what it says, what it says in cash)."""
    row = context.page.locator("table tr", has_text=needle)
    assert row.count() == 1, (
        "expected exactly one decision row mentioning %r, found %d"
        % (needle, row.count()))
    return row.locator("td").first.inner_text(), row.locator("td").last.inner_text()


def _summary(context):
    """The policy's five headline figures, keyed by the label under each.

    `{"cold treats": "8", "claims sent": "0", "paid out": "$0.00",
      "claims used": "0/4", ...}` -- still as the page wrote them.
    """
    tiles = context.page.locator(".card.row > div")
    assert tiles.count() >= 5, (
        "the policy page is not showing its summary card: %d tiles" % tiles.count())
    figures = {}
    for index in range(tiles.count()):
        tile = tiles.nth(index)
        figures[tile.locator(".muted").inner_text().strip()] = \
            tile.locator(".big").inner_text().strip()
    return figures


# -- before the claim ------------------------------------------------------

@then('the policy is covered today')
def the_policy_is_covered_today(context):
    """The scenario's premise, asserted rather than assumed.

    If this policy ever stops being in force -- the seed changes, or its term
    simply runs out as the demo ages -- the claim below is refused and every
    assertion after it fails somewhere far less informative than here.
    """
    tag = context.page.locator("p.sub .tag").inner_text().strip()
    assert tag == "Active", (
        "%s is not showing cover today, it says %r. This scenario needs a "
        "policy that is in force; pick another Active one with no lapse date "
        "and spare claim allowance." % (context.policy_id, tag))


@then('I note the cover terms and what the policy has claimed so far')
def note_the_terms(context):
    """Everything `adjudicate` will need, taken from the policy page itself.

    Read here rather than looked up, so the comparison later is between two
    things the browser was shown and a rule, and not between the app and a
    figure this file already knew."""
    subtitle = context.page.locator("p.sub").inner_text()

    per_episode = re.search(r"\$([\d,]+\.\d{2}) an episode", subtitle)
    deductible = re.search(r"\$([\d,]+\.\d{2}) deductible", subtitle)
    assert per_episode and deductible, (
        "the policy page does not state its episode cap and deductible: %r" % subtitle)
    context.coverage_limit = usd(per_episode.group(1).replace(",", ""))
    context.deductible = usd(deductible.group(1).replace(",", ""))

    context.before = _summary(context)
    used = re.match(r"(\d+)/(\d+)$", context.before["claims used"])
    assert used, "the policy page does not say how much of the annual cap is used"
    context.approvals_used = int(used.group(1))
    context.annual_limit = int(used.group(2))
    assert context.approvals_used < context.annual_limit, (
        "%s has used %s of its annual approvals, so a claim filed against it "
        "is refused for the cap. That is a refusal scenario's job, not this "
        "one's -- give this scenario a policy with allowance left."
        % (context.policy_id, context.before["claims used"]))


@when('I go to file a claim')
def go_to_file_a_claim(context):
    context.page.click('a[href$="/claims/new"]')
    context.page.wait_for_load_state("load")
    assert context.page.url.endswith("/claims/new"), (
        "expected the claim form, got %s" % context.page.url)


@then('nothing warns that a claim would be refused')
def nothing_warns(context):
    """The form says up front when cover has ended or the cap is spent. On a
    policy with cover and allowance it should say nothing, and a warning here
    means the scenario's premise is wrong rather than the decision is."""
    warnings = context.page.locator(".warn")
    assert warnings.count() == 0, (
        "the claim form warns %r -- this scenario expects a claim that pays"
        % warnings.all_inner_texts())


# -- describing the episode ------------------------------------------------

@when('I report {trigger}, {flavour}, topped with {toppings}, pain {pain:d}, '
      'lasting {duration}')
def report_an_episode(context, trigger, flavour, toppings, pain, duration):
    """Answer the questions the way a claimant would and send the claim.

    Only the answers this scenario is about are given. Everything else --
    how cold it was, how much of it, how fast, where it hurt, what it felt
    like -- keeps the answer the form arrives pre-set to, because those bands
    do not reach the money and a step that set all ten would read like a
    click script.
    """
    page = context.page
    context.toppings = [t.strip() for t in toppings.split(" and ")]
    context.flavour = flavour
    context.trigger = trigger
    context.pain = pain
    assert duration in DURATION_SECONDS, (
        "%r is not one of the durations the form offers (%s)"
        % (duration, ", ".join(sorted(DURATION_SECONDS))))
    context.duration_sec = DURATION_SECONDS[duration]

    page.check('input[name="trigger"][value="%s"]' % trigger)
    page.check('input[name="duration"][value="%s"]' % duration)
    page.check('input[name="flavour"][value="%s"]' % flavour)
    for topping in context.toppings:
        page.check('input[name="toppings"][value="%s"]' % topping)
    page.fill('input[name="pain"]', str(pain))

    page.click('button[type="submit"]')
    page.wait_for_load_state("load")


# -- the decision ----------------------------------------------------------

@then('I am shown a decision')
def shown_a_decision(context):
    """A decision of its own, with an id, at a URL that can be re-opened.

    The claim id is the handle everything after this uses. It is never a
    position: the claim was filed today into a history that runs into 2027,
    so it lands in the middle of the table rather than at the end.
    """
    match = re.search(r"/policies/(BF-\d+)/claims/(CLM-\d+)$", context.page.url)
    assert match, (
        "expected to land on a decision for a saved claim, got %s" % context.page.url)
    assert match.group(1) == context.policy_id
    context.claim_id = match.group(2)

    subtitle = context.page.locator("p.sub").inner_text()
    assert context.claim_id in subtitle, "the decision does not show its own claim id"

    dated = re.search(r"\d{4}-\d{2}-\d{2}", subtitle)
    assert dated, "the decision does not say when the episode was: %r" % subtitle
    context.claim_date = dated.group(0)
    # The app dates the claim with the server's own `date.today()`, and the
    # server is this machine. Only a run that straddles midnight can see these
    # differ, and it would be a confusing failure later if it were not one here.
    assert context.claim_date == date.today().isoformat(), (
        "the claim is dated %s and today is %s" % (context.claim_date, date.today()))


@then('the decision names the flavour and the toppings')
def decision_names_flavour_and_toppings(context):
    """CUJ-4's two questions, captured and shown.

    The page writes the toppings lowercased and joined, so each is checked on
    its own rather than as one string -- an assertion on the joined phrase
    would be an assertion about the punctuation between them.
    """
    subtitle = context.page.locator("p.sub").inner_text()
    assert context.flavour in subtitle, (
        "the decision does not say the flavour was %r: %r" % (context.flavour, subtitle))
    for topping in context.toppings:
        assert topping.lower() in subtitle.lower(), (
            "the decision does not mention %r: %r" % (topping, subtitle))
    assert context.trigger in subtitle, (
        "the decision does not say what was eaten: %r" % subtitle)


@then('the decision shows the assessment, the episode cap, the deductible and '
      'the payout')
def decision_shows_the_four_figures(context):
    """Read all four off the page, and check the terms it names are the policy's.

    A decision that quoted a different episode cap or deductible from the ones
    the policy page showed would be the app deciding terms for itself, which
    is the one thing it must not do.
    """
    context.assessed = _money(
        _decision_row(context, "What we worked it out at")[1], "the assessed row")

    prose, cash = _decision_row(context, "episode cap")
    context.cap_taken = _money(cash, "the episode cap row")
    named_cap = _money(prose, "the episode cap row's wording")
    assert named_cap == context.coverage_limit, (
        "the policy page says the episode cap is %s and the decision says %s"
        % (context.coverage_limit, named_cap))

    context.deductible_taken = _money(
        _decision_row(context, "Your deductible")[1], "the deductible row")
    assert context.deductible_taken == context.deductible, (
        "the policy page says the deductible is %s and the decision took %s off"
        % (context.deductible, context.deductible_taken))

    context.paid = _money(_decision_row(context, "Paid to you")[1], "the payout row")

    headline = context.page.locator("h1").inner_text()
    assert "is yours" in headline, (
        "expected a decision that pays out, and the headline says %r.\n"
        "If this says 'Not this time' the claim was refused, and the reason "
        "is on the page." % headline)
    assert _money(headline, "the headline") == context.paid, (
        "the headline says %r and the table says %s was paid" % (headline, context.paid))


@then('the amount assessed is what that severity is worth')
def assessed_from_the_severity(context):
    """Nobody typed a figure in -- the form has no money field at all -- so the
    assessment has to follow from the pain and the duration that were given."""
    expected = brainfreeze.assess_amount(float(context.pain), context.duration_sec)
    assert context.assessed == expected, (
        "pain %s lasting %ss is worth %s, and the page assessed it at %s"
        % (context.pain, context.duration_sec, expected, context.assessed))


@then('those four figures add up')
def the_figures_add_up(context):
    """The decision's own arithmetic, checked without leaving the page.

    It is not a tautology. The page derives what the cap took off by
    subtraction and floors it at zero, so a payout that did not come from
    these terms shows up here as a decision that does not balance.
    """
    total = context.assessed - context.cap_taken - context.deductible_taken
    assert total == context.paid, (
        "the decision does not balance: assessed %s, less %s to the cap, less "
        "%s deductible, is %s -- and it says it paid %s"
        % (context.assessed, context.cap_taken, context.deductible_taken,
           total, context.paid))


@then('those four figures are the ones the rules give')
def the_figures_match_adjudicate(context):
    """`brainfreeze.adjudicate`, run on what the browser was shown.

    The app is supposed to report this function and add nothing. Every
    argument here came off a page: the assessment off the decision, the cap
    and the deductible off the policy's subtitle, the approvals already used
    off its summary card.
    """
    decision = brainfreeze.adjudicate(
        context.assessed,
        context.coverage_limit,
        context.deductible,
        context.approvals_used,
        annual_claim_limit=context.annual_limit)

    assert decision.approved, (
        "the rules refuse this claim (%s) and the page paid it out" % decision.reason)
    for what, on_the_page, by_the_rules in (
        ("paid", context.paid, decision.amount),
        ("taken off by the episode cap", context.cap_taken, decision.capped_by_limit),
        ("taken off by the deductible", context.deductible_taken,
         decision.deductible_applied),
        ("assessed", context.assessed, decision.assessed),
    ):
        assert on_the_page == by_the_rules, (
            "the page and the rules disagree about what was %s: the page says "
            "%s, adjudicate() says %s.\nThe app is meant to report this "
            "function, not to work the money out for itself."
            % (what, on_the_page, by_the_rules))


# -- and afterwards, in the book ------------------------------------------

def _history(context):
    """The policy's table of episodes as three parallel lists: dates, claim
    ids, outcomes. The header row has no `td` and drops out on its own."""
    dates = context.page.locator("table tr td:nth-child(1)").all_inner_texts()
    claims = context.page.locator("table tr td:nth-child(3)").all_inner_texts()
    outcomes = context.page.locator("table tr td:nth-child(4)").all_inner_texts()
    assert len(dates) == len(claims) == len(outcomes), (
        "the history is ragged: %d dates, %d claims, %d outcomes"
        % (len(dates), len(claims), len(outcomes)))
    return ([d.strip() for d in dates], [c.strip() for c in claims],
            [o.strip() for o in outcomes])


def _row_of_the_new_claim(context):
    dates, claims, outcomes = _history(context)
    assert context.claim_id in claims, (
        "%s is not on %s's record at all. It was filed and a decision was "
        "shown for it, so a claim missing here is a claim that did not commit."
        % (context.claim_id, context.policy_id))
    assert claims.count(context.claim_id) == 1, (
        "%s appears %d times on the record"
        % (context.claim_id, claims.count(context.claim_id)))
    index = claims.index(context.claim_id)
    return index, dates, outcomes


@then('the claim is on the record with the figures the decision showed')
def claim_is_on_the_record(context):
    """Found by its id, never by position -- see the next step for why."""
    index, dates, outcomes = _row_of_the_new_claim(context)
    assert dates[index] == context.claim_date, (
        "the decision dated %s %s and the record dates it %s"
        % (context.claim_id, context.claim_date, dates[index]))
    paid = _money(outcomes[index], "%s's row on the record" % context.claim_id)
    assert paid == context.paid, (
        "the decision said %s was paid on %s and the record says %s"
        % (context.paid, context.claim_id, paid))


@then('it sits in date order, among episodes that have not happened yet')
def it_sits_in_date_order(context):
    """Events are kept in date order, not appended.

    This policy's seeded history runs into 2027, so a claim filed today
    belongs in the middle of it. A row at the end would mean the record is
    kept in the order things were entered, which is the bug those two issues
    fixed -- and it is also why nothing here looks the claim up by position.
    """
    index, dates, _ = _row_of_the_new_claim(context)
    assert dates == sorted(dates), (
        "the record is not in date order: %s" % dates)
    assert index < len(dates) - 1, (
        "%s is the last row of the record. It was filed today and this policy "
        "has episodes dated after today, so landing at the end means the "
        "history is in entry order rather than date order."
        % context.claim_id)
    assert index > 0, (
        "%s is the first row, so this policy has nothing older than today and "
        "cannot show that a claim lands in the middle. Give the scenario a "
        "policy with episodes both sides of today." % context.claim_id)


@then("the policy's totals moved by exactly this claim")
def the_totals_moved_by_this_claim(context):
    """One episode, one claim, one approval, and the payout the decision named.

    The summary card is what an underwriter reads, and it is derived rather
    than stored -- so this is the check that the claim went into the book as
    an event on this policy and not merely into a table somewhere.
    """
    after = _summary(context)
    before = context.before

    for label in ("cold treats", "gave a headache", "claims sent"):
        assert int(after[label]) == int(before[label]) + 1, (
            "%r went from %s to %s, and filing one claim should move it by one"
            % (label, before[label], after[label]))

    assert after["claims used"] == "%d/%d" % (context.approvals_used + 1,
                                              context.annual_limit), (
        "the annual cap went from %s to %s" % (before["claims used"],
                                               after["claims used"]))

    paid_before = _money(before["paid out"], "the policy's total paid, before")
    paid_after = _money(after["paid out"], "the policy's total paid, after")
    assert paid_after - paid_before == context.paid, (
        "the policy had paid out %s and now says %s, a difference of %s -- and "
        "the decision paid %s"
        % (paid_before, paid_after, paid_after - paid_before, context.paid))
