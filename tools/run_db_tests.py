"""Run the test suite INSIDE the database, so both surfaces can be compared.

    gemdb tools/run_db_tests.py              # every module
    gemdb tools/run_db_tests.py money seed   # just these

`python3 -m unittest discover` runs the same files under CPython; running them
here too checks that one set of rules gives the same answers in both runtimes.
That matters most for money, where they round differently (`round()` is
half-up in the database, banker's outside it).

Modules are read from disk and executed into a fresh namespace rather than
imported, so the tests are never deployed: an imported module is recorded in
the database under its name, pinned to the file it came from, and a run from
another checkout whose copy differs would then be refused.
"""

import os
import sys
import time
import types
import tempfile
import subprocess
import unittest

#: The repository on `sys.path`, as in `seed.py`.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

#: The web app's modules, so a test can `import app` or `import wire`.
WEB = os.path.join(REPO, "web")
if WEB not in sys.path:
    sys.path.insert(0, WEB)


#: In dependency order, cheapest first, so a broken foundation fails fast.
MODULES = ["test_money", "test_brainfreeze", "test_seed", "test_analysis",
           "test_packaging", "test_serving", "test_metrics", "test_api",
           "test_app"]

#: How many module sessions run at once. They can share the database: only
#: test_app touches it -- its setUpClass re-seeds gemdb.root and commits, and
#: it is the only module that reads gemdb.root -- while every other module
#: tests an in-memory book of its own (seed.load()). 1 runs them one at a
#: time, in MODULES order, as before.
SESSIONS = max(1, int(os.environ.get("BF_DB_TEST_SESSIONS", "3")))

#: The order sessions start in when several run at once: longest first, so
#: the slowest module is never left to start last. Measured on CI (macos-15,
#: run 40716400776): test_app 4.1 min, test_seed 2.5, test_serving 2.0,
#: test_analysis 1.4, test_api 1.1, the rest seconds.
LONGEST_FIRST = ["test_app", "test_seed", "test_serving", "test_analysis",
                 "test_api", "test_packaging", "test_brainfreeze",
                 "test_metrics", "test_money"]


def load_module_from_file(name, path):
    module = types.ModuleType(name)
    module.__file__ = path
    #: Grail leaves `__cached__` absent (it has no bytecode files), but its
    #: `exec` path looks the attribute up without a default, so without this
    #: every module dies before a line runs. `None` is what CPython sets for a
    #: module with no cached bytecode, which is true of this one.
    module.__cached__ = None
    with open(path) as handle:
        source = handle.read()
    exec(compile(source, path, "exec"), module.__dict__)
    return module


def run_one_module(name):
    """Load and run a single module in THIS session."""
    path = os.path.join(REPO, "tests", "%s.py" % name)
    if not os.path.exists(path):
        print("no such test module: %s" % path)
        return 2
    module = load_module_from_file("%s_live" % name, path)
    suite = unittest.TestLoader().loadTestsFromModule(module)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


def run_each_in_its_own_session():
    """Run every module in a session of its own, and report them together.

    One session cannot hold the whole suite: its execution stack runs out,
    and the run dies of `AlmostOutOfStack` reported against whichever
    `setUpClass` was running, hiding the real failures (#85).

    Up to SESSIONS of them run at once. Each child writes its output to a file
    of its own (BF_DB_TEST_OUTPUT; Grail's subprocess cannot hand a child a
    file), printed whole when the child finishes, so two modules' lines never
    interleave.

    A child gets its module name on the command line and so takes the other
    branch in `run_db_tests`, which is what stops this recursing.
    """
    order = MODULES if SESSIONS == 1 else LONGEST_FIRST
    assert sorted(order) == sorted(MODULES), "LONGEST_FIRST must name every module"
    waiting = list(order)
    running = {}            # name -> (process, output path, start time)
    outputs = tempfile.mkdtemp(prefix="bf-db-tests-")
    failed = []
    started = time.time()
    while waiting or running:
        while waiting and len(running) < SESSIONS:
            name = waiting.pop(0)
            out = os.path.join(outputs, name + ".out")
            child = subprocess.Popen(
                ["gemdb", os.path.join("tools", "run_db_tests.py"), name],
                cwd=REPO, env=dict(os.environ, BF_DB_TEST_OUTPUT=out),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            running[name] = (child, out, time.time())
        for name in list(running):
            child, out, began = running[name]
            if child.poll() is None:
                continue
            del running[name]
            print("\n=== %s (%.0fs) ===" % (name, time.time() - began), flush=True)
            if os.path.exists(out):
                with open(out) as handle:
                    sys.stdout.write(handle.read())
            else:
                print("(no output: the session ended before the module ran)")
            if child.returncode:
                print("exit status %d" % child.returncode)
            sys.stdout.flush()
            if child.returncode != 0:
                failed.append(name)
        if running:
            time.sleep(1)

    print()
    if failed:
        print("FAILED in %d of %d modules: %s"
              % (len(failed), len(MODULES), ", ".join(failed)))
        return 1
    print("OK -- %d modules, each in a session of its own, %d at a time, in %.0fs."
          % (len(MODULES), SESSIONS, time.time() - started))
    return 0


def run_db_tests():
    wanted = [a if a.startswith("test_") else "test_" + a
              for a in sys.argv[1:]]
    if not wanted:
        return run_each_in_its_own_session()
    output = os.environ.get("BF_DB_TEST_OUTPUT")
    if output:
        # A child of run_each_in_its_own_session: everything to its file.
        sys.stdout = sys.stderr = open(output, "w", buffering=1)
    worst = 0
    for name in wanted:
        worst = max(worst, run_one_module(name))
    return worst


if __name__ == "__main__":
    sys.exit(run_db_tests())
