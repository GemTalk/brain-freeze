"""The two surfaces a browser cannot reach, put beside the ones it can.

Both are driven the way a person would drive them -- the notebook through its
own runner, the published snippets by pasting them into a session -- and then
compared against the JSON surface and the page.

The comparison is always live-against-live. The figures printed in
`docs/mcp-questions.md` describe a freshly seeded book and the suite has
written to this one by the time these run, so comparing against those numbers
would be a test of which scenario happened to go first. `tools/refresh_mcp.py
--verify` is where the frozen answers are replayed, against a fresh seed and
over the real transport.
"""

import os
import re
import subprocess
import sys

from behave import then, when

from environment import REPO, gemdb_env, keep

# `tools/` is a plain directory rather than a package, so it goes on the path.
# The document parser lives in `refresh_mcp` and there is no reason to have a
# second one here: a snippet this file extracted differently from the way the
# verifier extracts it would not be the published snippet.
if os.path.join(REPO, "tools") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "tools"))

import refresh_mcp                           # noqa: E402  (needs the path first)

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


def published(title_fragment):
    """The snippet the document publishes under a heading, with its preamble.

    Wrapped in a `print` because the document is written for a notebook and an
    agent, where the last expression echoes itself. That is the only change
    made to it.
    """
    with open(refresh_mcp.DOC) as handle:
        markdown = handle.read()
    preamble = refresh_mcp.published_preamble(markdown)
    for promise in refresh_mcp.promises(markdown):
        if title_fragment.lower() in promise.title.lower():
            return "%s\nprint(%s)\n" % (preamble, promise.code.strip())
    raise AssertionError(
        "no published question matches %r -- have %s"
        % (title_fragment,
           [p.title for p in refresh_mcp.promises(markdown)]))


def run_published(context, title_fragment):
    # At the repository root, not under `artifacts/`. `gemdb <file>.py` puts
    # the SCRIPT's directory on `sys.path`, and the published preamble omits
    # the path line on purpose -- the document says its snippets are written
    # to run in a notebook or a `gemdb script.py`, both of which already have
    # the right directory. Running it anywhere else would be testing a
    # snippet the document does not publish.
    path = os.path.join(REPO, "_published_snippet.py")
    with open(path, "w") as handle:
        handle.write(published(title_fragment))
    try:
        context.published_output = run_gemdb_script(
            os.path.relpath(path, REPO)).strip()
    finally:
        os.remove(path)
    return context.published_output


# -- the notebook ---------------------------------------------------------

@when('the notebook is run inside the database')
def run_the_notebook(context):
    context.notebook_output = run_gemdb_script("tools/run_notebook_check.py")
    context.notebook_figures = {
        name: int(value)
        for name, value in NOTEBOOK_FIGURE.findall(context.notebook_output)}


@then('every one of its cells ran')
def every_cell_ran(context):
    assert "FAILED" not in context.notebook_output, context.notebook_output[-2000:]
    assert re.search(r"All \d+ code cells ran", context.notebook_output), (
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


# -- the answers the demo publishes ---------------------------------------

@when('I run the book summary the demo publishes')
def run_published_summary(context):
    run_published(context, "how big is this book")


@when('I run the loss ratio by tier the demo publishes')
def run_published_loss_ratio(context):
    run_published(context, "loss ratio by risk tier")


@then('it answers what the JSON surface answers')
def published_matches_payload(context):
    """The snippet returns `analysis.book_summary`; so does the payload, under
    names chosen for JSON. Compared field by field rather than as text."""
    found = context.published_output
    for key, name in (("policy_count", "policies"),
                      ("event_count", "events"),
                      ("claim_count", "claims"),
                      ("approved_claim_count", "approved")):
        expected = str(context.stats_payload[key])
        assert re.search(r"'%s':\s*%s\b" % (name, expected), found), (
            "the published snippet does not report %s as %s:\n%s"
            % (name, expected, found))
    for key, name in (("premium", "premium"), ("paid", "paid")):
        expected = context.stats_payload[key]
        assert re.search(r"'%s':\s*Decimal\('%s'\)" % (name, re.escape(expected)),
                         found), (
            "the published snippet does not report %s as %s:\n%s"
            % (name, expected, found))


@then('it answers what the JSON surface answers for every band')
def published_loss_ratio_matches(context):
    found = context.published_output
    by_tier = context.stats_payload["loss_ratio_by_tier"]
    assert by_tier, "the payload reports no loss ratio by tier"
    for tier in by_tier:
        assert re.search(r"'%s':\s*%s\b" % (tier, re.escape(str(by_tier[tier]))),
                         found), (
            "the published snippet does not report %s as %s:\n%s"
            % (tier, by_tier[tier], found))


# -- evidence -------------------------------------------------------------

@then('I keep its output as "{name}"')
def keep_notebook_output(context, name):
    path = keep(context, name, context.notebook_output, extension="txt")
    print("      %s" % path.rsplit("artifacts/", 1)[-1])


@then('I keep the comparison as "{name}"')
def keep_comparison(context, name):
    body = ("the snippet the demo publishes, run in a session of its own:\n\n"
            "%s\n\nwhat the JSON surface serves:\n\n%r\n"
            % (context.published_output, context.stats_payload))
    path = keep(context, name, body, extension="txt")
    print("      %s" % path.rsplit("artifacts/", 1)[-1])
