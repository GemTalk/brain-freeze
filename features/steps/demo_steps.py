"""Steps shared by every feature.

Written in the language of the demo rather than of the browser: a step says
"I am shown the policy for BF-100539", not "click the third link". A feature
file that reads like a click script documents nothing.
"""

from behave import given, then, when

from environment import shoot

#: What `gemdb tools/seed.py` makes, pinned by tests/test_seed.py. Scenarios that
#: buy a policy push the live count above it.
SEEDED_POLICIES = 900


# -- going places ---------------------------------------------------------

@given('the demo is running')
def the_demo_is_running(context):
    """Nothing to do -- `environment.py` seeded the book and started the app
    before any scenario ran. The step exists so the feature files can say so."""
    assert context.browser is not None


@when('I open the {page} page')
@given('I open the {page} page')
def open_named_page(context, page):
    paths = {
        "customer picker": "/",
        "quote": "/quote",
    }
    assert page in paths, "no such named page: %s (have %s)" % (page, sorted(paths))
    context.page.goto(context.base_url + paths[page], wait_until="load")


@when('I open the policy {policy_id}')
@given('I open the policy {policy_id}')
def open_policy(context, policy_id):
    context.policy_id = policy_id
    context.page.goto("%s/policies/%s" % (context.base_url, policy_id),
                      wait_until="load")


# -- looking at things ----------------------------------------------------

@then('I see "{text}"')
def i_see(context, text):
    body = context.page.content()
    assert text in body, (
        "expected to see %r on %s\n--- page ---\n%s"
        % (text, context.page.url, _visible(context)[:1500]))


@then('I do not see "{text}"')
def i_do_not_see(context, text):
    body = context.page.content()
    assert text not in body, "did not expect %r on %s" % (text, context.page.url)


@then('the page says how many policyholders there are')
def page_says_how_many(context):
    """At least the seeded 900, not exactly 900.

    Scenarios share one book -- re-seeding between them would cost nine
    seconds each and dominate the run -- so any scenario that buys a policy
    moves this number for every scenario after it. An exact assertion here
    passed alone and failed as soon as a second feature existed, which is the
    order-dependence you get for free with shared state.

    At-least still earns its place: it proves the count came from the
    database rather than from a template, which is the whole point of the
    smoke test.
    """
    import re
    match = re.search(r"([\d,]+) policyholders", context.page.inner_text("body"))
    assert match, "the picker does not say how many policyholders there are"
    count = int(match.group(1).replace(",", ""))
    assert count >= SEEDED_POLICIES, (
        "the picker says %d policyholders, fewer than the %d the seed makes"
        % (count, SEEDED_POLICIES))
    context.policy_count = count


# -- evidence -------------------------------------------------------------

@then('I capture "{name}"')
@when('I capture "{name}"')
def capture(context, name):
    path = shoot(context, name)
    print("      %s" % path.rsplit("artifacts/", 1)[-1])


def _visible(context):
    try:
        return context.page.inner_text("body")
    except Exception:
        return "(no body)"


@then('the app said it was running, and logged that request')
def the_app_spoke_for_itself(context):
    """The banner and the access log, read out of the run's own evidence.

    A server here prints nothing unless it is made to -- Grail's werkzeug
    defines `log_request` and never calls it -- and a silent app is
    indistinguishable from a hung one, which is how this repo once ran two at
    once. `web/serving.py` prints the banner before the socket opens and hangs
    the access log off Flask's after_request. If that ever regresses, it
    regresses quietly, so it is asserted here rather than trusted.
    """
    import os
    from environment import ARTIFACTS, HOST, PORT
    context.app_log.flush()
    with open(os.path.join(ARTIFACTS, "app.log"), encoding="utf-8") as handle:
        said = handle.read()
    assert "Brain Freeze Insurance is running" in said, (
        "the app printed no banner:\n%s" % said[:600])
    assert "http://%s:%d/" % (HOST, PORT) in said, (
        "the banner does not name the address to open:\n%s" % said[:600])
    assert "GET" in said, (
        "no request was logged, so the access log is not reaching the "
        "terminal:\n%s" % said[:600])
