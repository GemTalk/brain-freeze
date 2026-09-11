"""The picker: paging, and finding one policy by name.

The window size is read off the page rather than restated here. A number
copied into a test agrees with the code until someone changes the code, and
then it agrees with nothing -- while still passing, because it would be
comparing a constant to itself.
"""

import re

from behave import then, when

#: "Showing 1-50 of 900." -- the sentence the picker uses to say which window
#: of the book is on screen.
WINDOW = re.compile(r"Showing\s+(\d+)[–-](\d+)\s+of\s+(\d+)")

#: Every policy id visible in the table, in the order they are listed.
POLICY_ID = re.compile(r"BF-\d{6}")


def text(context):
    return context.page.inner_text("body")


def window(context):
    found = WINDOW.search(text(context))
    assert found, "the picker does not say which window of the book it shows"
    return tuple(int(g) for g in found.groups())


def listed(context):
    """The ids in the table, which is not every id the page mentions -- the
    search box keeps whatever was typed into it."""
    return context.page.eval_on_selector_all(
        "table a", "links => links.map(a => a.textContent.trim())")


@then('it shows a window onto the book rather than all of it')
def shows_a_window(context):
    first, last, total = window(context)
    assert first == 1, "the first page starts at %d" % first
    assert last < total, (
        "the page claims to show %d of %d -- that is the whole book, and "
        "rendering it takes the best part of a minute here" % (last, total))
    context.first_page = listed(context)
    assert len(context.first_page) == last, (
        "it says it is showing %d rows and lists %d"
        % (last, len(context.first_page)))


@when('I go to the next page')
def go_to_next_page(context):
    context.page.click("text=next")


@when('I go back to the previous page')
def go_to_previous_page(context):
    context.page.click("text=previous")


@then('I am shown the customers after the ones I have seen')
def shown_the_next_customers(context):
    first, _last, _total = window(context)
    assert first > 1, "still on the first page"
    now = listed(context)
    assert now, "the second page is empty"
    assert not (set(now) & set(context.first_page)), (
        "the second page repeats customers from the first")


@then('the page still says how many policyholders there are')
def still_says_the_total(context):
    _first, _last, total = window(context)
    assert ("%d policyholders" % total) in text(context), (
        "the heading and the window disagree about the size of the book")


@then('I am shown the customers I started with')
def back_where_i_started(context):
    assert listed(context) == context.first_page, (
        "going back did not return to the page I was on")


@when('I look up {wanted}')
def look_up(context, wanted):
    context.wanted = wanted
    context.page.fill('input[name="policy"]', wanted)
    context.page.click("text=Find")


@then('I am taken to that policy without having to choose it')
def taken_straight_there(context):
    assert context.page.url.endswith("/policies/%s" % context.wanted), (
        "a search with one answer left me on %s" % context.page.url)
    assert context.wanted in text(context)


@then('I am shown only the policies whose ids contain it')
def shown_only_matches(context):
    ids = listed(context)
    assert ids, "a partial id that matches several policies found none"
    assert all(context.wanted in policy_id for policy_id in ids), ids
    assert len(ids) > 1, (
        "%s matches only one policy, so this is not testing the narrowing"
        % context.wanted)


@then('I am told nothing matches, rather than shown an empty table')
def told_nothing_matches(context):
    body = text(context)
    assert "Nothing matches" in body, (
        "an empty table says the app is broken; a sentence says it looked")
    assert not POLICY_ID.search(body.split("Nothing matches")[0].split("Find")[-1]), (
        "it says nothing matches and still lists policies")
