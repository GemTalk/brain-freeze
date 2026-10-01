"""Lifecycle for the acceptance suite: the database, the app, and the browser.

    .venv-acceptance/bin/behave

Everything here exists because the app under test is not an ordinary one. It
runs *inside* a GemStone database, it holds one of ten available sessions for
as long as it is up, and it serves one request per connection on a single
thread. So this file owns starting it, and — more importantly — owns making
sure it stopped.

WHAT A RUN DOES

1. Builds a brand-new database (`tools/fresh_database.sh`): the engine's
   empty extent with GemDB's Grail installed and nothing of ours committed --
   what a reader has before step 1 of the tutorial. Every `gemdb` the suite
   runs goes to it, and it is thrown away at the end.
2. Runs the features in tutorial order, `1_` to `5_`, then the rest. Step 1
   loads the data the way a reader does. A feature run on its own gets the
   book loaded first, and the app started, by `before_feature`.
3. Stops the app, and **fails the run if the port is still open**.

`BRAINFREEZE_DB=existing` runs against ~/GemDB instead, reseeding it: faster,
and exactly the kind of database that has hidden bugs, so not the real run.
`BRAINFREEZE_KEEP_DB=1` leaves the fresh database behind to look at.

WHY NOT RE-SEED PER SCENARIO

It costs about nine seconds each and would dominate the run. Instead, as in
`tests/test_app.py`, every scenario that writes gets a policy of its own, and
the next run's fresh database is the reset.

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
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ARTIFACTS = os.path.join(REPO, "artifacts")

#: The same answer the app will give, from the same function, so the suite
#: probes and refuses on the port the app is about to open. web/serving.py is
#: importable here: it defers everything that needs the database.
sys.path.append(os.path.join(REPO, "web"))
import serving                               # noqa: E402

HOST, PORT = "127.0.0.1", serving.configured_port(os.environ)
BASE_URL = "http://%s:%d" % (HOST, PORT)

#: Generous on purpose. Rendering is slow here -- Grail runs each Jinja
#: template in a forked green thread, which is why the picker pages instead of
#: showing all 900 -- and a cold first render also compiles the template into
#: the database. A tight timeout would fail on a slow machine.
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

    Kept on the context, not in a module global: a step file that says
    `from environment import ...` gets a different module object from the one
    behave runs these hooks in, and the context is what both share.
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


#: Where the `gemdb` this run uses lives. An environment variable rather than
#: a module global, because a steps module that says `from environment import`
#: gets its own copy of this file (see `new_app_state`), and the process
#: environment is the one thing both copies share.
GEMDB_BIN = "BRAINFREEZE_GEMDB_BIN"


def gemdb_env():
    env = dict(os.environ)
    bin_dir = env.get(GEMDB_BIN) or os.path.expanduser("~/GemDB/bin")
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
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



#: The app handle, the restart count and whether the book is loaded live in
#: ONE MUTABLE DICT on `context`, created by `before_all`, and every reader and
#: writer goes through it.
#:
#: Not module state: behave execs this file itself, while a steps module says
#: `from environment import ...` and gets a second, independent copy.
#: Constants survive that; mutable state does not.
#:
#: Not a plain `context.app` either: behave discards what a step ASSIGNS when
#: the scenario ends, so after a restart inside a step, `context.app` would
#: point at the process already killed. Mutating a dict `before_all` put there
#: avoids both.
def new_app_state():
    return {"process": None, "restarts": 0, "seeded": False}


def seed_book(context):
    """Step 1 of the tutorial, as a reader runs it. Returns what it printed."""
    output = run_gemdb("tools/seed.py")
    context.app_state["seeded"] = True
    return output


def ensure_ready(context, feature):
    """Load the book and start the app, unless this feature is the one that
    does it -- so any feature can be run on its own against a fresh database.
    """
    if "no-seed" not in feature.tags and not context.app_state["seeded"]:
        print("  loading the book ...", flush=True)
        seed_book(context)
    if "no-app" not in feature.tags and context.app_state["process"] is None:
        print("  starting the app ...", flush=True)
        start_app(context)
        print("  serving on %s" % BASE_URL, flush=True)


def start_app(context):
    """Start the app and wait until it serves.

    `start_new_session` is load-bearing. `gemdb` is a shell wrapper around
    topaz; terminating the wrapper alone leaves topaz running, still holding
    its GemStone session and still bound to the port. Its own process group
    means the whole tree can be signalled.
    """
    context.app_state["process"] = subprocess.Popen(
        ["gemdb", "web/app.py"], cwd=REPO, env=gemdb_env(),
        stdout=context.app_log, stderr=subprocess.STDOUT,
        start_new_session=True)

    deadline = time.time() + APP_START_TIMEOUT_S
    while time.time() < deadline:
        if context.app_state["process"].poll() is not None:
            raise RuntimeError("the app exited before it served; see artifacts/app.log")
        if port_is_open():
            break
        time.sleep(1)
    else:
        raise RuntimeError("the app did not serve within %ds" % APP_START_TIMEOUT_S)


def stop_app(context):
    """Stop the app and wait for the port, so a restart cannot race the bind."""
    app = context.app_state["process"]
    if app is not None and app.poll() is None:
        stop_process_group(app)
    for _ in range(15):
        if not port_is_open():
            return
        time.sleep(1)
    raise RuntimeError(
        "the app would not let go of %s, so it cannot be restarted -- that is "
        "a leaked GemStone session and the stone allows ten" % BASE_URL)


def app_is_answering(timeout=15):
    """Is the app still serving?

    A cheap route on purpose: `/api/questions` reads the model and renders no
    template, so a slow answer here means something is wrong rather than
    something is big.
    """
    try:
        request = urllib.request.Request(BASE_URL + "/api/questions")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def ensure_app_answering(context, why):
    """Restart the app if it stopped answering after `why` ran in another
    session, and count the restart.

    A guard: since GemDB 1.5.2 another session's commit no longer stops the app,
    so this should not fire. Counted, so a scenario that says `the app was
    never restarted` cannot pass across one.
    """
    if app_is_answering():
        return False
    print("\n  the app stopped answering after %s -- restarting it."
          % why, flush=True)
    stop_app(context)
    start_app(context)
    context.app_state["restarts"] += 1
    if not app_is_answering():
        raise RuntimeError(
            "the app did not answer after being restarted following %s" % why)
    return True


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

    context.app_state = new_app_state()
    context.app_log = open(os.path.join(ARTIFACTS, "app.log"), "w")
    context.fresh_db = None

    if os.environ.get("BRAINFREEZE_DB", "fresh") == "existing":
        print("  using ~/GemDB, reseeding it ...", flush=True)
        seed_book(context)
    else:
        context.fresh_db = tempfile.mkdtemp(prefix="bf-fresh-db-")
        print("  building a brand-new database in %s ..." % context.fresh_db,
              flush=True)
        built = subprocess.run(
            [os.path.join(REPO, "tools", "fresh_database.sh"), "create",
             context.fresh_db], capture_output=True, text=True)
        if built.returncode != 0:
            raise RuntimeError("could not build a fresh database:\n%s%s"
                               % (built.stdout[-2000:], built.stderr[-2000:]))
        os.environ[GEMDB_BIN] = os.path.join(context.fresh_db, "bin")

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

    app = context.app_state["process"]
    if app is not None and app.poll() is None:
        stop_process_group(app)
    if getattr(context, "app_log", None):
        context.app_log.close()

    if context.fresh_db:
        if os.environ.get("BRAINFREEZE_KEEP_DB"):
            print("\n  kept the fresh database in %s" % context.fresh_db, flush=True)
        else:
            subprocess.run([os.path.join(REPO, "tools", "fresh_database.sh"),
                            "destroy", context.fresh_db], capture_output=True)

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
    # Only when the whole suite ran: a run told to drive one feature has not
    # failed to drive the others. Judged by which features ran, not by the
    # command line -- behave fills `config.paths` in itself when given none.
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
    ensure_ready(context, feature)
    context.feature_dir = os.path.join(ARTIFACTS, slug(feature.name))

    # Behave pops everything a scenario hook sets, so a counter incremented
    # there would be 1 every time. The feature already knows the order.
    context.scenario_order = [s.name for s in feature.scenarios]


def before_scenario(context, scenario):
    #: So `the app was never restarted` can mean "not during this scenario"
    #: rather than merely "some app process is alive".
    context.app_restarts_at_start = context.app_state["restarts"]

    context.page = context.browser.new_page(viewport={"width": 1100, "height": 900})
    context.page.set_default_timeout(PAGE_TIMEOUT_MS)
    watch(context, context.page)
    context.shot_number = 0

    # A directory per scenario, not per feature: shot numbers restart with
    # each scenario, so two scenarios in one directory would overwrite each
    # other's evidence.
    position = context.scenario_order.index(scenario.name) + 1
    context.shot_dir = os.path.join(
        context.feature_dir, "%d-%s" % (position, slug(scenario.name)))
    os.makedirs(context.shot_dir, exist_ok=True)


def after_scenario(context, scenario):
    # Scenario-specific restoration first, and always: a scenario that lapses
    # a policy has to put it back even when it failed.
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
