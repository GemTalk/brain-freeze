"""Steps that walk the README, the tutorial, as a reader would.

Where a step can read what the README says rather than repeat it, it does: the
commands step 1 shows are the commands this runs, and the output it shows is
the output this expects. A README that drifts from what GemDB does fails here,
which is the point -- the README is the deliverable.
"""

import os
import re
import subprocess
import time

from behave import then, when

from environment import (REPO, gemdb_env, keep, start_app,
                         stop_app)

README = os.path.join(REPO, "README.md")

#: Commands a README step shows that start something long-running rather than
#: finish. The suite starts the app itself; running it here would hang.
LONG_RUNNING = ("gemdb web/app.py",)


def readme_step(number):
    """The text of `## <number>.` in the README, up to the next `## `."""
    with open(README, encoding="utf-8") as handle:
        text = handle.read()
    match = re.search(r"^## %d\. .*?(?=^## |\Z)" % number, text, re.M | re.S)
    assert match, "the README has no step %d" % number
    return match.group(0)


def commands_and_outputs(section):
    """Each ```sh block, paired with the ```console block after it, if any."""
    blocks = re.findall(r"```(sh|console)\n(.*?)```", section, re.S)
    pairs = []
    for i, (kind, body) in enumerate(blocks):
        if kind != "sh":
            continue
        shown = blocks[i + 1][1] if i + 1 < len(blocks) and blocks[i + 1][0] == "console" else ""
        pairs.append((body.strip(), shown.strip()))
    return pairs


# -- step 1 -----------------------------------------------------------------

@then('nothing of ours is in the database yet')
def nothing_of_ours_yet(context):
    if os.environ.get("BRAINFREEZE_DB") == "existing":
        return                  # quick mode: ~/GemDB, which is not new
    finished = subprocess.run(
        ["gemdb", "-c", 'import gemdb; print("KEYS", sorted(gemdb.root.keys()))'],
        cwd=REPO, env=gemdb_env(), capture_output=True, text=True)
    assert "KEYS []" in finished.stdout, (
        "a brand-new database should hold nothing, and this one has: %s"
        % finished.stdout[-500:])


@when('I run the commands step {number:d} of the README shows')
def run_the_readme_commands(context, number):
    context.readme_runs = []
    for command, shown in commands_and_outputs(readme_step(number)):
        if command.startswith(LONG_RUNNING):
            continue
        finished = subprocess.run(["bash", "-c", command], cwd=REPO,
                                  env=gemdb_env(), capture_output=True, text=True)
        context.readme_runs.append((command, shown, finished))
        if "tools/seed.py" in command and finished.returncode == 0:
            context.app_state["seeded"] = True
    assert context.readme_runs, "step %d of the README shows no commands" % number


@then('each one prints what the README says it prints')
def each_prints_what_the_readme_shows(context):
    record = []
    for command, shown, finished in context.readme_runs:
        record.append("$ %s\n%s%s" % (command, finished.stdout, finished.stderr))
        assert finished.returncode == 0, (
            "`%s` failed:\n%s%s" % (command, finished.stdout[-1500:], finished.stderr[-1500:]))
        for line in shown.splitlines():
            assert line.strip() in finished.stdout, (
                "the README says `%s` prints %r, and it printed:\n%s"
                % (command, line.strip(), finished.stdout[-1500:]))
    keep(context, "the commands and what they printed", "\n".join(record), extension="txt")


@then('the book holds {policies:d} policyholders and {claims:d} claims, as objects')
def the_book_holds(context, policies, claims):
    code = ('import gemdb\n'
            'b = gemdb.root["brainfreeze"]\n'
            'print("COUNTS", len(b), len(b.claims), type(b["BF-100539"]).__name__)\n')
    finished = subprocess.run(["gemdb", "-c", code], cwd=REPO, env=gemdb_env(),
                              capture_output=True, text=True)
    match = re.search(r"COUNTS (\d+) (\d+) (\w+)", finished.stdout)
    assert match, finished.stdout[-1000:] + finished.stderr[-1000:]
    assert (int(match.group(1)), int(match.group(2))) == (policies, claims), match.group(0)
    assert match.group(3) == "Policyholder", (
        "a policy should come back as a Policyholder object, not %s" % match.group(3))


# -- step 2 -----------------------------------------------------------------

@when('the app is stopped and started again')
def restart_the_app(context):
    stop_app(context)
    start_app(context)


@when('I go back to the policy I bought')
def open_the_bought_policy(context):
    context.page.goto("%s/policies/%s" % (context.base_url, context.policy_id),
                      wait_until="load")


@then('the claim I filed is on it')
def the_claim_is_on_it(context):
    body = context.page.inner_text("body")
    assert context.claim_id in body, (
        "%s should still be on %s after a restart, and the page shows:\n%s"
        % (context.claim_id, context.policy_id, body[:1500]))


# -- step 4 -----------------------------------------------------------------

class NotebookSession:
    """One database session kept open, the way a notebook kernel is.

    `features/notebook_session.py` runs the notebook's cells in it and then
    waits. Commands go in, and answers come out, through files: the session
    runs inside topaz, and a pipe to its stdin is not something to depend on.
    """

    def __init__(self, directory):
        self.dir = directory
        os.makedirs(directory, exist_ok=True)
        self.process = subprocess.Popen(
            ["gemdb", os.path.join(REPO, "features", "notebook_session.py"), directory],
            cwd=REPO, env=gemdb_env(), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, start_new_session=True)
        self.answer = self._wait_for("ready", 300)

    def _wait_for(self, name, timeout):
        path = os.path.join(self.dir, name)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if os.path.exists(path):
                with open(path) as handle:
                    text = handle.read()
                os.remove(path)
                return text
            if self.process.poll() is not None:
                raise RuntimeError("the notebook session exited:\n%s"
                                   % self.process.stdout.read()[-2000:])
            time.sleep(0.5)
        raise RuntimeError("the notebook session did not answer %r" % name)

    def ask(self, command):
        with open(os.path.join(self.dir, "command"), "w") as handle:
            handle.write(command)
        return self._wait_for("answer", 120)

    def close(self):
        try:
            self.ask("quit")
        except Exception:
            pass
        try:
            self.process.wait(timeout=30)
        except Exception:
            os.killpg(os.getpgid(self.process.pid), 9)


def notebook_count(answer):
    match = re.search(r"policies: (\d+)", answer)
    assert match, "the notebook session printed no count: %r" % answer[-500:]
    return int(match.group(1))


@when('I open the notebook and run its cells')
def open_the_notebook(context):
    context.notebook = NotebookSession(os.path.join(context.shot_dir, "session"))
    context.add_cleanup(context.notebook.close)
    context.notebook_before = notebook_count(context.notebook.answer)
    keep(context, "the notebook, cell by cell", context.notebook.answer, extension="txt")


@then('the notebook counts the policies again, and the count has not changed')
def count_has_not_changed(context):
    answer = context.notebook.ask("count")
    assert notebook_count(answer) == context.notebook_before, (
        "the notebook saw another session's commit before it refreshed: %r" % answer)


@when('the notebook runs gemdb.refresh()')
def notebook_refreshes(context):
    context.refresh_answer = context.notebook.ask("refresh")
    assert "refresh: ok" in context.refresh_answer, context.refresh_answer


@then('the notebook counts one more policy')
def one_more_policy(context):
    answer = context.notebook.ask("count")
    after = notebook_count(answer)
    keep(context, "the count before and after refresh",
         "before: %d\nafter refresh: %d\n" % (context.notebook_before, after),
         extension="txt")
    assert after == context.notebook_before + 1, (
        "expected %d policies after refresh(), the notebook counted %d"
        % (context.notebook_before + 1, after))


# -- step 3 -----------------------------------------------------------------

#: The answer to step 3 -- the change the README asks for -- is the branch
#: `tutorial-step-3`. Only the application's files are applied: the branch also
#: carries the tests of the finished feature, and those are not the reader's.
ANSWER = "tutorial-step-3"
ANSWER_PATHS = ["brainfreeze", "web"]


def answer_diff():
    finished = subprocess.run(
        ["git", "diff", ANSWER + "^", ANSWER, "--"] + ANSWER_PATHS,
        cwd=REPO, capture_output=True, text=True)
    assert finished.returncode == 0 and finished.stdout, (
        "no answer to apply: %s" % finished.stderr)
    return finished.stdout


def put_the_code_back(context):
    """Always, so a failed run cannot leave the reader's change in the tree
    -- or its compiled form in the database for the next scenario."""
    subprocess.run(["git", "apply", "-R", "-"], input=context.step3_diff,
                   cwd=REPO, capture_output=True, text=True)
    subprocess.run(["gemdb", "tools/load.py"], cwd=REPO, env=gemdb_env(),
                   capture_output=True, text=True)


@when('I make the change step 3 of the README describes')
def make_the_change(context):
    context.step3_diff = answer_diff()
    applied = subprocess.run(["git", "apply", "-"], input=context.step3_diff,
                             cwd=REPO, capture_output=True, text=True)
    assert applied.returncode == 0, (
        "the answer does not apply to this checkout:\n%s" % applied.stderr)
    context.add_cleanup(put_the_code_back, context)
    keep(context, "the change, as a diff", context.step3_diff, extension="txt")


def form_asks_about_flavour(context):
    return context.page.locator('input[name="flavour"]').count() > 0


@then('the form does not ask which flavour it was')
def form_does_not_ask(context):
    assert not form_asks_about_flavour(context), (
        "the claim form already asks which flavour, before step 3")


@then('the form asks which flavour it was, and what was on top')
def form_asks(context):
    assert form_asks_about_flavour(context), (
        "after loading, the running app's claim form still does not ask "
        "which flavour: the change did not reach it")
    assert context.page.locator('input[name="toppings"]').count() > 0


@when('I file a claim for {flavour}, topped with {toppings}, pain {pain:d}, lasting {duration}')
def report_with_flavour(context, flavour, toppings, pain, duration):
    context.flavour = flavour
    context.toppings = [t.strip() for t in toppings.split(" and ")]
    context.trigger = "ice cream"
    page = context.page
    page.check('input[name="trigger"][value="ice cream"]')
    page.check('input[name="duration"][value="%s"]' % duration)
    page.check('input[name="flavour"][value="%s"]' % flavour)
    for topping in context.toppings:
        page.check('input[name="toppings"][value="%s"]' % topping)
    page.fill('input[name="pain"]', str(pain))
    page.click('button[type="submit"]')
    page.wait_for_load_state("load")


@then('the decision names the flavour and the toppings')
def decision_names_flavour(context):
    subtitle = context.page.locator("p.sub").inner_text()
    assert context.flavour in subtitle, (
        "the decision does not say the flavour was %r: %r" % (context.flavour, subtitle))
    for topping in context.toppings:
        assert topping.lower() in subtitle.lower(), (
            "the decision does not mention %r: %r" % (topping, subtitle))


@when('I open claim {claim_id} on {policy_id}, filed before the change')
def open_an_old_claim(context, claim_id, policy_id):
    context.page.goto("%s/policies/%s/claims/%s"
                      % (context.base_url, policy_id, claim_id), wait_until="load")


@then('it still loads, and names no flavour')
def old_claim_loads(context):
    subtitle = context.page.locator("p.sub").inner_text()
    assert "(" not in subtitle, (
        "a claim filed before the change names a flavour: %r" % subtitle)


# -- what steps 2 and 4 of the README say ------------------------------------

@then('the address step 2 of the README says to open is where the app serves')
def readme_address(context):
    import serving
    shown = re.findall(r"<(http://[^>]+)>", readme_step(2))
    assert shown, "step 2 of the README gives no address to open"
    if serving.configured_port(os.environ) != serving.DEFAULT_PORT:
        return                  # a run on another port cannot match the README
    for address in shown:
        assert address.rstrip("/") == context.base_url.rstrip("/"), (
            "the README says to open %s, and the app serves %s"
            % (address, context.base_url))


@then('the call step 4 of the README shows is the one the notebook made')
def readme_refresh_call(context):
    shown = re.findall(r"```python\n(.*?)```", readme_step(4), re.S)
    assert [block.strip() for block in shown] == ["gemdb.refresh()"], (
        "step 4 of the README shows %r; the notebook session refreshes with "
        "gemdb.refresh(), so one of them has changed" % shown)
