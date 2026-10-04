"""The claims page: the book's count, the order, the filter, the search.

The page size is read off the page, as the policies page's steps read theirs:
a number copied in here would agree with the code only until it changed.
"""

import re

from behave import then, when

from environment import fetch_json

#: "2,172 claims on the book" -- the sentence that states the count.
COUNT = re.compile(r"([\d,]+) claims on the book")

#: "Showing 1-25 of 2172." -- which window of the list is on screen.
WINDOW = re.compile(r"Showing\s+(\d+)[–-](\d+)\s+of\s+(\d+)")


def listed_claims(context):
    """The claim ids in the table, in the order the page lists them."""
    return context.page.eval_on_selector_all(
        "table tbody tr td:first-child a",
        "links => links.map(a => a.textContent.trim())")


@then('the page says as many claims as the book holds')
def says_the_books_count(context):
    found = COUNT.search(context.page.inner_text("body"))
    assert found, "the claims page does not say how many claims there are"
    stated = int(found.group(1).replace(",", ""))
    status, stats = fetch_json(context, "/api/stats")
    assert status == 200, "GET /api/stats answered %d" % status
    assert stated == stats["claim_count"], (
        "the claims page says %d claims and the book holds %d"
        % (stated, stats["claim_count"]))


@then('the claims are listed newest first')
def newest_first(context):
    ids = listed_claims(context)
    first, last, total = (int(g) for g in
                          WINDOW.search(context.page.inner_text("body")).groups())
    assert len(ids) == last - first + 1, (
        "the page says it shows %d-%d but lists %d claims"
        % (first, last, len(ids)))
    assert ids == sorted(ids, reverse=True), (
        "the claims are not newest first: %s" % ids)


@when('I narrow the list to the refused claims')
def narrow_to_refused(context):
    context.page.click(".filters >> text=Refused")
    context.page.wait_for_load_state("load")


@then('every claim listed was refused')
def all_refused(context):
    outcomes = context.page.locator(
        "table tbody tr td:nth-child(5)").all_inner_texts()
    assert outcomes, "the refused filter lists no claims at all"
    approved = [o for o in outcomes if "Refused" not in o]
    assert not approved, (
        "the refused filter lists claims that were not refused: %s" % approved)


@when('I search the claims for {claim_id}')
def search_for_claim(context, claim_id):
    context.page.fill('input[name="q"]', claim_id)
    context.page.click('button[type="submit"]')
    context.page.wait_for_load_state("load")


@then('I am shown the decision on {claim_id}')
def shown_that_decision(context, claim_id):
    assert re.search(r"/policies/BF-\d+/claims/%s$" % claim_id,
                     context.page.url), (
        "a search for one claim id left me on %s" % context.page.url)
    subtitle = context.page.locator("p.sub").inner_text()
    assert claim_id in subtitle, (
        "the decision page does not name %s: %r" % (claim_id, subtitle))
