"""Steps for the quote-to-policy journey.

These read the page rather than the database. That is the point of an
acceptance test: `tests/test_app.py` already asserts against objects, and if
these did the same they would be a slower copy of it. What only a browser can
say is that a person is *shown* the right thing.

The one exception is the price check, which compares two things the browser
showed at different moments -- the quote's Sundae price, and the premium on
the policy that quote became. Nothing is read from the book to do it.
"""

import re

from behave import then, when

MONEY = re.compile(r"\$[\d,]+\.\d{2}")


def _text(context):
    return context.page.inner_text("body")


@when('I answer age {age:d}, {migraine} migraine, {tth} tension headaches, '
      'eating {speed}, on {trigger}')
def answer_the_questions(context, age, migraine, tth, speed, trigger):
    page = context.page
    page.fill('input[name="age"]', str(age))
    page.check('input[name="migraine_history"][value="%s"]'
               % ("yes" if migraine == "a" else "no"))
    page.check('input[name="tension_type_headache_history"][value="%s"]'
               % ("yes" if tth == "" else "no"))
    page.check('input[name="typical_consumption_speed"][value="%s"]' % speed)
    page.check('input[name="favourite_trigger"][value="%s"]'
               % trigger.rstrip("s"))
    page.click('button[type="submit"]')
    page.wait_for_load_state("load")


@then('I am shown a saved quote')
def shown_a_saved_quote(context):
    url = context.page.url
    match = re.search(r"/quote/(QTE-\d+)", url)
    assert match, (
        "expected to land on a saved quote, got %s.\n"
        "A quote with no id of its own would mean the answers went back "
        "through the browser instead." % url)
    context.quote_id = match.group(1)
    assert context.quote_id in _text(context), "the quote does not show its own id"


@then('the quote prices all three plans')
def quote_prices_all_plans(context):
    """Read the ANNUAL premium off each plan's card.

    Not the first money in the card: that is the per-episode limit, which the
    policy page also shows -- so taking it would let the price check pass
    while comparing something that is not the premium.
    """
    context.quoted = {}
    for plan in ("Sprinkle", "Sundae", "Parfait"):
        card = context.page.locator("form.card", has_text=plan)
        assert card.count() == 1, (
            "expected exactly one %s card, found %d" % (plan, card.count()))
        annual = card.locator(".big.num").inner_text().strip()
        assert MONEY.fullmatch(annual), (
            "the %s plan's headline figure is %r, which is not money" % (plan, annual))
        context.quoted[plan] = annual

    assert len(set(context.quoted.values())) == 3, (
        "three plans priced identically is almost certainly a bug: %r"
        % (context.quoted,))


@then('no state is hidden in the page')
def no_hidden_state(context):
    hidden = context.page.locator('input[type="hidden"]').count()
    assert hidden == 0, (
        "%d hidden field(s) on %s -- the quote is supposed to be an object in "
        "the database, not state parked in the browser" % (hidden, context.page.url))


@when('I re-open the quote by its id')
def reopen_the_quote(context):
    context.page.goto("%s/quote/%s" % (context.base_url, context.quote_id),
                      wait_until="load")


@when('I accept the {plan} plan')
def accept_the_plan(context, plan):
    context.accepted_plan = plan
    context.page.click('button[name="plan"][value="%s"]' % plan)
    context.page.wait_for_load_state("load")


@then('I am shown a policy')
def shown_a_policy(context):
    match = re.search(r"/policies/(BF-\d+)", context.page.url)
    assert match, "expected to land on a policy, got %s" % context.page.url
    context.policy_id = match.group(1)


@then('I am shown its ID card')
def shown_its_id_card(context):
    """Taking out a policy lands on the card, drawn for this policy."""
    assert context.page.url.endswith("/policies/%s/card" % context.policy_id), (
        "expected the new policy's ID card, got %s" % context.page.url)
    card = context.page.locator("#id-card svg")
    assert card.count() == 1, "the ID card page has no card on it"
    assert context.policy_id in card.text_content(), (
        "the ID card does not carry the policy number %s" % context.policy_id)


@then('its card can be kept as an SVG of the same policy')
def card_as_svg(context):
    """The "Download SVG" link serves the card on its own, as an image.

    Opened rather than clicked: the link's `download` attribute would hand
    it to the browser's downloads, and what matters is what it serves.
    """
    link = context.page.locator('a[download$=".svg"]')
    assert link.count() == 1, "the ID card page has no SVG download"
    response = context.page.goto(context.base_url + link.get_attribute("href"),
                                 wait_until="load")
    assert response.ok, "the card's SVG answered %d" % response.status
    assert response.headers["content-type"].startswith("image/svg+xml"), (
        "the card's SVG is served as %s" % response.headers["content-type"])
    assert context.policy_id in response.text(), (
        "the SVG card does not carry the policy number %s" % context.policy_id)


@then('the policy was sold at the price the quote showed')
def sold_at_the_quoted_price(context):
    quoted = context.quoted[context.accepted_plan]
    body = _text(context)
    assert "%s a year" % quoted in body.replace("\n", " "), (
        "the quote showed %s for the %s plan, and the policy page does not "
        "mention that figure.\n"
        "A quote that re-prices itself on acceptance is the hidden-field bug "
        "wearing a different coat.\n--- policy page ---\n%s"
        % (quoted, context.accepted_plan, body[:800]))


@then('the quote names the policy it became')
def quote_names_the_policy(context):
    body = _text(context)
    assert context.policy_id in body, (
        "the quote does not say it became %s -- accepting should record what "
        "the quote turned into" % context.policy_id)
