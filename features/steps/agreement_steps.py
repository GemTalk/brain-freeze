"""The notebook, put beside the app's page and payload.

The notebook runs in a session of its own, through its own runner, and its
figures are compared live against the JSON surface and the page.
"""

import re
import subprocess

from behave import then, when

from environment import REPO, ensure_app_answering, gemdb_env, keep

#: How long a `gemdb` run may take. The notebook renders charts and walks the
#: whole book; a cold first run also compiles into the database.
GEMDB_TIMEOUT_S = 300

#: "policies: 903" and "events  : 5000", printed by the notebook itself.
NOTEBOOK_FIGURE = re.compile(r"^(policies|events)\s*:\s*(\d+)", re.MULTILINE)

def run_gemdb_script(path):
    finished = subprocess.run(
        ["gemdb", path], cwd=REPO, env=gemdb_env(),
        capture_output=True, text=True, timeout=GEMDB_TIMEOUT_S)
    assert finished.returncode == 0, (
        "gemdb %s failed:\n%s\n%s"
        % (path, finished.stdout[-2000:], finished.stderr[-2000:]))
    return finished.stdout


# -- the notebook ---------------------------------------------------------

@when('the notebook is run inside the database')
def run_the_notebook(context):
    context.notebook_output = run_gemdb_script("tools/run_notebook.py")
    context.notebook_figures = {
        name: int(value)
        for name, value in NOTEBOOK_FIGURE.findall(context.notebook_output)}

    # The notebook ran in a session of its own, and the steps below ask the app
    # questions: make sure it still answers.
    ensure_app_answering(context, "the notebook")


@then('every one of its cells ran')
def every_cell_ran(context):
    assert "FAILED" not in context.notebook_output, context.notebook_output[-2000:]
    assert re.search(r"OK -- \d+ cells, in order, in one session", context.notebook_output), (
        "the runner did not say every cell ran:\n%s"
        % context.notebook_output[-2000:])


@then('the notebook and the payload agree about the size of the book')
def notebook_agrees_with_payload(context):
    """The notebook counted the book itself, in its own session. The JSON
    surface counted it in the app's. Two sessions, one book."""
    assert context.notebook_figures, (
        "the notebook printed no figures to compare:\n%s"
        % context.notebook_output[-2000:])
    pairs = (("policies", "policy_count"), ("events", "event_count"))
    for printed, key in pairs:
        assert printed in context.notebook_figures, printed
        assert context.notebook_figures[printed] == context.stats_payload[key], (
            "the notebook says %d %s and the payload says %d"
            % (context.notebook_figures[printed], printed,
               context.stats_payload[key]))


@then('the page states the same number of policyholders')
def page_states_the_same(context):
    count = context.stats_payload["policy_count"]
    body = context.page.inner_text("body")
    assert ("%d policyholders" % count) in body, (
        "the payload says %d policyholders and the page does not" % count)


# -- evidence -------------------------------------------------------------

@then('I keep its output as "{name}"')
def keep_notebook_output(context, name):
    path = keep(context, name, context.notebook_output, extension="txt")
    print("      %s" % path.rsplit("artifacts/", 1)[-1])
