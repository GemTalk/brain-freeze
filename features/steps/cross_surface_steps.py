"""Steps for the cross-surface beat.

The only steps in this suite that run something OUTSIDE the browser.
`lapse.py` opens the book from a GemStone session of its own and commits; the
app then sees it because it takes a new view before each request. That is the
whole demonstration, and it needs both halves in one scenario.

Two details are load-bearing and neither is decoration.

`lapse.py` lapses as of YESTERDAY, not today. Cover runs to the lapse date
inclusive -- someone who lapses on the 12th is still covered for the treat
they ate that morning -- so lapsing as of today changes the status label and
refuses nothing. A screenshot of that would look like the feature working
while proving nothing.

And the policy is put back in teardown even when the scenario fails. Otherwise
one bad run leaves BF-100184 lapsed for every run after it, and the next
person debugs a fixture rather than their change.
"""

import subprocess

from behave import then, when

from environment import REPO, gemdb_env

#: A policy of its own, per the rule at the top of tests/test_app.py. Active,
#: no lapse date, and not written by any other scenario or by
#: tests/test_app.py -- which reserves BF-100092, BF-100150, BF-100186 and
#: BF-100000, and uses this one only for reads.
POLICY = "BF-100184"


def run_lapse(*args):
    """Run `gemdb lapse.py` to completion, in a session of its own."""
    finished = subprocess.run(
        ["gemdb", "lapse.py"] + list(args),
        cwd=REPO, env=gemdb_env(), capture_output=True, text=True)
    assert finished.returncode == 0, (
        "gemdb lapse.py %s failed:\n%s\n%s"
        % (" ".join(args), finished.stdout[-1500:], finished.stderr[-1500:]))
    return finished.stdout


@when('{policy_id} is lapsed from a session of its own')
def lapse_it(context, policy_id):
    context.lapsed_policy = policy_id
    context.lapse_output = run_lapse(policy_id)
    assert "status=Lapsed" in context.lapse_output, (
        "lapse.py did not report a lapse:\n%s" % context.lapse_output)
    # It reports `in force today=False`, which is the difference between a
    # status label and cover actually ending. If this ever says True, the
    # scenario below would screenshot a page that refuses nothing.
    assert "in force today=False" in context.lapse_output, (
        "the policy is still in force after lapsing, so nothing would be "
        "refused and this scenario would prove nothing:\n%s"
        % context.lapse_output)


@when('{policy_id} is reinstated from a session of its own')
def reinstate_it(context, policy_id):
    run_lapse(policy_id, "--reinstate")
    context.lapsed_policy = None


@when('I re-open the policy {policy_id}')
def reopen_policy(context, policy_id):
    context.page.goto("%s/policies/%s" % (context.base_url, policy_id),
                      wait_until="load")


@when('I open the claim form for {policy_id}')
def open_claim_form(context, policy_id):
    context.page.goto("%s/policies/%s/claims/new" % (context.base_url, policy_id),
                      wait_until="load")


@then('the policy is shown as active')
def shown_active(context):
    body = context.page.inner_text("body")
    assert "Active" in body, (
        "expected the policy to read Active:\n%s" % body[:400])
    assert "Lapsed" not in body, (
        "the policy still reads Lapsed:\n%s" % body[:400])


@then('the policy is shown as lapsed')
def shown_lapsed(context):
    body = context.page.inner_text("body")
    assert "Lapsed" in body, (
        "the running app did NOT pick up the change -- this is the whole "
        "point of the scenario. Either the app is not taking a new view per "
        "request, or lapse.py did not commit.\n%s" % body[:400])


@then('I am invited to file a claim')
def invited_to_file(context):
    assert context.page.locator('button[type="submit"]').count() == 1, (
        "expected a claim form with a submit button on %s" % context.page.url)
    body = context.page.inner_text("body")
    assert "Cover on this policy ended" not in body, (
        "the form is already refusing before anything was lapsed")


@then('I am told cover has ended')
def told_cover_ended(context):
    body = context.page.inner_text("body")
    assert "Cover on this policy ended" in body, (
        "the claim form does not say cover ended:\n%s" % body[:600])


@then('the app was never restarted')
def app_never_restarted(context):
    """The claim that makes the rest of it interesting.

    The harness started the app and holds the handle, so this is a fact rather
    than an inference: same process, still running, across a change made by a
    different GemStone session.
    """
    assert context.app.poll() is None, (
        "the app process is gone -- whatever the browser is talking to, it is "
        "not the server this scenario started")


def after_scenario_restore(context):
    """Put the policy back, even when the scenario failed."""
    if getattr(context, "lapsed_policy", None):
        try:
            run_lapse(context.lapsed_policy, "--reinstate")
        except Exception:
            pass
        context.lapsed_policy = None
