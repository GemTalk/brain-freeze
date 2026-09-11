"""Lifecycle for the acceptance suite: the database, the app, and the browser.

    .venv-acceptance/bin/behave

Everything here exists because the app under test is not an ordinary one. It
runs *inside* a GemStone database, it holds one of ten available sessions for
as long as it is up, and it serves one request per connection on a single
thread. So this file owns starting it, and — more importantly — owns making
sure it stopped.

WHAT A RUN DOES

1. Re-seeds the book, so scenarios start from the figures everything else
   pins. Nine seconds, once, not per scenario.
2. Starts `gemdb web/app.py` and waits for the port.
3. Runs the scenarios, each with a fresh browser page.
4. Stops the app, and **fails the run if the port is still open**.

WHY NOT RE-SEED PER SCENARIO

It costs about nine seconds each and would dominate the run. `tests/test_app.py`
already solved this the cheap way: every test that writes gets a policy of its
own. The feature files follow the same rule, and the reseed at the start of the
next run is the reset.

A LEAKED APP IS A LEAKED SESSION

The stone allows ten sessions and does not forgive running out — a leaked one
is not tidy-up debt, it is one step closer to a database that refuses every
login including `topaz`. So teardown runs even when a scenario fails, and a
stale listener at startup is a refusal rather than something to quietly reuse:
a suite that silently tested yesterday's server would be worse than no suite.
"""

import ast
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ARTIFACTS = os.path.join(REPO, "artifacts")

HOST, PORT = "127.0.0.1", 5000
BASE_URL = "http://%s:%d" % (HOST, PORT)

#: Generous on purpose. Rendering is slow here -- Grail runs each Jinja
#: template in a forked green thread, which is why the picker pages at 25 rows
#: instead of showing all 900 -- and a cold first render also compiles the
#: template into the database. A tight timeout would fail on a slow machine
#: and teach everyone to re-run rather than to read.
PAGE_TIMEOUT_MS = 60000
APP_START_TIMEOUT_S = 120


#: The modules that declare routes. Read rather than imported: they import
#: `gemdb` and `flask`, so this process cannot load them.
ROUTE_MODULES = ("routes_html.py", "routes_api.py")

def note_request(context, method, url):
    """Record one request against the routing table.

    WHY THIS IS NOT A LIST OF URLS IN THE FEATURE FILES

    Most of these pages are reached by clicking, not by typing an address --
    accepting a quote is a form button, opening the claim form is a link. A
    check that grepped the feature files for URLs would call those uncovered,
    and would call a scenario that merely MENTIONS an address covered. This
    records what was actually asked for.

    WHY IT IS KEPT ON THE CONTEXT AND NOT IN A MODULE GLOBAL

    It was a module global, and half the requests went missing. A step file
    that says `from environment import ...` gets a DIFFERENT module object
    from the one behave loaded to run these hooks, so the steps recorded into
    one set and `after_all` read another. The context is the single thing
    both halves demonstrably share.
    """
    context.driven.add((method.upper(), urllib.parse.urlparse(url).path))


def watch(context, page):
    """Record every request a page makes, navigations and form posts alike."""
    page.on("request",
            lambda request: note_request(context, request.method, request.url))


#: The JSON surface answers `curl`, so the steps drive it with an HTTP client
#: rather than a browser. Long enough for a cold first render, like the page
#: timeout above and for the same reason.
API_TIMEOUT_S = 60


def fetch_json(context, path, method="GET", body=None):
    """Call the JSON surface, returning (status, decoded payload).

    An error status is a result here, not an exception: half of what the
    surface promises is what it says when it cannot answer.
    """
    url = "%s%s" % (context.base_url, path)
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers,
                                     method=method)
    note_request(context, method, url)
    try:
        with urllib.request.urlopen(request, timeout=API_TIMEOUT_S) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as refused:
        return refused.code, json.loads(refused.read().decode("utf-8"))


def keep(context, name, text, extension="json"):
    """Write a payload beside the screenshots, numbered in the same series.

    A JSON endpoint has no screenshot, and "the evidence is a picture" was
    never the point -- the point is that a reader can see afterwards exactly
    what the run was shown.
    """
    context.shot_number += 1
    path = os.path.join(context.shot_dir,
                        "%02d-%s.%s" % (context.shot_number, slug(name),
                                        extension))
    with open(path, "w") as handle:
        handle.write(text)
        handle.write("\n")
    return path


def declared_routes():
    """(rule, method) for every route the app registers."""
    found = []
    for name in ROUTE_MODULES:
        with open(os.path.join(REPO, "web", name)) as handle:
            tree = ast.parse(handle.read(), filename=name)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for decorator in node.decorator_list:
                if not (isinstance(decorator, ast.Call)
                        and getattr(decorator.func, "attr", "") == "route"
                        and decorator.args):
                    continue
                methods = ["GET"]
                for keyword in decorator.keywords:
                    if keyword.arg == "methods":
                        methods = [item.value for item in keyword.value.elts]
                for method in methods:
                    found.append((decorator.args[0].value, method))
    return found


def matches(rule, path):
    """Does this request path belong to this rule? `<converters>` are
    one path segment each, so a rule cannot claim a deeper address."""
    pattern = "^%s$" % "[^/]+".join(
        re.escape(part) for part in re.split(r"<[^>]+>", rule))
    return re.match(pattern, path) is not None


def undriven_routes(driven):
    return [(rule, method) for rule, method in declared_routes()
            if not any(seen_method == method and matches(rule, seen_path)
                       for seen_method, seen_path in driven)]


def gemdb_env():
    env = dict(os.environ)
    env["PATH"] = os.path.expanduser("~/GemDB/bin") + os.pathsep + env.get("PATH", "")
    return env


def port_is_open(host=HOST, port=PORT, timeout=1.0):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(timeout)
        return probe.connect_ex((host, port)) == 0


def run_gemdb(script, *args):
    """Run a gemdb script to completion, raising with its output on failure."""
    finished = subprocess.run(
        ["gemdb", script] + list(args),
        cwd=REPO, env=gemdb_env(), capture_output=True, text=True)
    if finished.returncode != 0:
        raise RuntimeError("gemdb %s failed:\n%s\n%s"
                           % (script, finished.stdout[-2000:], finished.stderr[-2000:]))
    return finished.stdout


def before_all(context):
    if port_is_open():
        raise RuntimeError(
            "Something is already listening on %s.\n"
            "This suite starts its own app and will not reuse a server it did "
            "not start -- a run that silently tested a stale one would be "
            "worse than no run. Stop it and try again." % BASE_URL)

    shutil.rmtree(ARTIFACTS, ignore_errors=True)
    os.makedirs(ARTIFACTS)

    #: (method, path) for every request this run drives. `after_all` requires
    #: every route the app declares to appear here.
    context.driven = set()

    #: Which feature files this run actually executed. Route coverage is only
    #: meaningful when all of them did -- see `after_all`.
    context.features_run = set()

    print("  seeding the book ...", flush=True)
    run_gemdb("tools/seed.py")

    print("  starting the app ...", flush=True)
    context.app_log = open(os.path.join(ARTIFACTS, "app.log"), "w")
    # `start_new_session` is load-bearing, not hygiene. `gemdb` is a shell
    # wrapper that execs topaz; terminating the wrapper leaves topaz running,
    # reparented to init, still holding its GemStone session and still bound
    # to the port. Measured the first time this suite ran: the scenario
    # passed, teardown "succeeded", and the leak check caught a server that
    # had outlived its own launcher. Its own group means the whole tree can
    # be signalled.
    context.app = subprocess.Popen(
        ["gemdb", "web/app.py"], cwd=REPO, env=gemdb_env(),
        stdout=context.app_log, stderr=subprocess.STDOUT,
        start_new_session=True)

    deadline = time.time() + APP_START_TIMEOUT_S
    while time.time() < deadline:
        if context.app.poll() is not None:
            raise RuntimeError("the app exited before it served; see artifacts/app.log")
        if port_is_open():
            break
        time.sleep(1)
    else:
        raise RuntimeError("the app did not serve within %ds" % APP_START_TIMEOUT_S)
    print("  serving on %s" % BASE_URL, flush=True)

    from playwright.sync_api import sync_playwright
    context.playwright = sync_playwright().start()
    context.browser = context.playwright.chromium.launch()
    context.base_url = BASE_URL


def after_all(context):
    for close in (
        lambda: context.browser.close(),
        lambda: context.playwright.stop(),
    ):
        try:
            close()
        except Exception:
            pass                      # never let cleanup hide a real failure

    app = getattr(context, "app", None)
    if app is not None and app.poll() is None:
        stop_process_group(app)
    if getattr(context, "app_log", None):
        context.app_log.close()

    # The check that matters. A leaked listener is a leaked GemStone session,
    # and ten is all there are.
    for _ in range(10):
        if not port_is_open():
            break
        time.sleep(1)
    else:
        raise RuntimeError(
            "the app is STILL listening on %s after teardown -- that is a "
            "leaked GemStone session, and the stone allows ten" % BASE_URL)
    print("\n  app stopped, port free. Screenshots in artifacts/", flush=True)

    # Last, so that a coverage complaint can never be the reason a leaked
    # session goes unreported.
    #
    # Only when the whole suite ran. `behave features/quote.feature` is what
    # anyone does while writing a scenario, and a run told to drive one
    # feature has not failed to drive the others.
    #
    # Which features ran, rather than what was on the command line: behave
    # fills `config.paths` in for itself when given none, so asking it what
    # it was told skipped the check on every run.
    on_disk = {name for name in os.listdir(HERE) if name.endswith(".feature")}
    skipped = sorted(on_disk - context.features_run)
    if skipped:
        print("  ran %d of %d features, so route coverage was not checked."
              % (len(context.features_run), len(on_disk)), flush=True)
        return

    missing = undriven_routes(context.driven)
    if missing:
        raise RuntimeError(
            "the suite never drove these routes:\n  %s\n"
            "Every route this app serves is supposed to be exercised by a "
            "scenario. Add one, or take the route out."
            % "\n  ".join("%s %s" % (method, rule) for rule, method in missing))
    print("  every route the app declares was driven by a scenario.", flush=True)


def stop_process_group(app):
    """Signal the whole group, because the thing holding the port is a
    grandchild -- see the comment where the app is started."""
    for sig, grace in ((signal.SIGTERM, 15), (signal.SIGKILL, 10)):
        try:
            os.killpg(os.getpgid(app.pid), sig)
        except (ProcessLookupError, PermissionError):
            return
        try:
            app.wait(timeout=grace)
            return
        except subprocess.TimeoutExpired:
            continue


def slug(name):
    """A filename that still reads like the sentence it came from."""
    return "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")


def before_feature(context, feature):
    context.features_run.add(os.path.basename(feature.filename))
    context.feature_dir = os.path.join(ARTIFACTS, slug(feature.name))

    # Behave pops everything a scenario hook sets, so a counter incremented
    # there would be 1 every time. The feature already knows the order.
    context.scenario_order = [s.name for s in feature.scenarios]


def before_scenario(context, scenario):
    context.page = context.browser.new_page(viewport={"width": 1100, "height": 900})
    context.page.set_default_timeout(PAGE_TIMEOUT_MS)
    watch(context, context.page)
    context.shot_number = 0

    # A directory per SCENARIO, not per feature. The shot numbers restart
    # with each scenario, so two scenarios in one feature both wrote a `01-`,
    # and two that captured the same moment under the same name overwrote
    # each other in silence -- evidence a reader would have had no way to
    # know was missing.
    position = context.scenario_order.index(scenario.name) + 1
    context.shot_dir = os.path.join(
        context.feature_dir, "%d-%s" % (position, slug(scenario.name)))
    os.makedirs(context.shot_dir, exist_ok=True)


def after_scenario(context, scenario):
    # Scenario-specific restoration first, and always -- a scenario that
    # lapses a policy has to put it back even when it failed, or one bad run
    # leaves a fixture broken for every run after it and the next person
    # debugs the fixture rather than their change.
    try:
        from cross_surface_steps import after_scenario_restore
        after_scenario_restore(context)
    except Exception:
        pass

    if scenario.status == "failed":
        # The most useful screenshot in the run is the one nobody asked for.
        try:
            shoot(context, "FAILED")
        except Exception:
            pass
    elif not os.listdir(context.shot_dir):
        # A scenario that passes and leaves nothing behind is a scenario
        # nobody can check afterwards. The suite exists to be read as much as
        # to be run.
        raise RuntimeError(
            "%r passed without capturing anything. Every scenario ends in "
            "evidence a reader can look at -- a screenshot, or the payload "
            "for a surface that has no picture." % scenario.name)
    try:
        context.page.close()
    except Exception:
        pass


def shoot(context, name):
    """Screenshot the page, numbered so a reader can follow the journey."""
    context.shot_number += 1
    path = os.path.join(context.shot_dir,
                        "%02d-%s.png" % (context.shot_number, slug(name)))
    context.page.screenshot(path=path, full_page=True)
    return path
