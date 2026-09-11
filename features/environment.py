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

import os
import signal
import shutil
import socket
import subprocess
import time

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


def before_scenario(context, scenario):
    context.page = context.browser.new_page(viewport={"width": 1100, "height": 900})
    context.page.set_default_timeout(PAGE_TIMEOUT_MS)
    context.shot_number = 0
    context.shot_dir = os.path.join(
        ARTIFACTS, scenario.feature.name.lower().replace(" ", "-"))
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
    try:
        context.page.close()
    except Exception:
        pass


def shoot(context, name):
    """Screenshot the page, numbered so a reader can follow the journey."""
    context.shot_number += 1
    slug = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
    path = os.path.join(context.shot_dir, "%02d-%s.png" % (context.shot_number, slug))
    context.page.screenshot(path=path, full_page=True)
    return path
