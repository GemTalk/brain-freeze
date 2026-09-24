"""Run the test suite INSIDE the database, so both surfaces can be compared.

    gemdb tools/run_db_tests.py              # every module
    gemdb tools/run_db_tests.py money seed   # just these

`python3 -m unittest discover` runs the same files under CPython. Running them
here as well is the demo's central claim reduced to a check: one set of rules,
two runtimes, identical answers. It matters most for money, where Grail and
CPython round differently -- `round()` is half-up in the database and banker's
outside it -- and `brainfreeze.money` exists so that difference cannot reach a
premium.

Modules are read from disk and executed into a fresh namespace rather than
imported. Grail keeps compiled modules in the database and served a *stale*
`tests/test_app` for a whole afternoon once; a runner that silently tests the
previous version of the tests is worse than no runner.
"""

import os
import sys
import types
import subprocess
import unittest

#: The repository, for the same reason and in the same way as every other
#: script in here -- see `seed.py`.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

#: The web app's modules, so a test can `import app` or `import wire`. A
#: plain directory rather than a package, deliberately: a committed package
#: module is served from the database forever, while these are recompiled
#: from disk each run.
WEB = os.path.join(REPO, "web")
if WEB not in sys.path:
    sys.path.insert(0, WEB)


#: In dependency order, cheapest first, so a broken foundation fails fast.
MODULES = ["test_money", "test_brainfreeze", "test_seed", "test_analysis",
           "test_packaging", "test_serving", "test_api", "test_app"]


def load_module_from_file(name, path):
    module = types.ModuleType(name)
    module.__file__ = path
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

    ONE SESSION CANNOT HOLD THE WHOLE SUITE, AND THE WAY IT FAILS IS A LIE.

    A session's Smalltalk execution stack is finite, and running the corpus in
    one of them exhausts it: the run dies of `AlmostOutOfStack` (notification
    2502) reported against whichever `setUpClass` happened to be running when
    the budget ran out. So the suite failed in classes that had nothing wrong
    with them, on every run, and the real failures underneath went unread --
    including a money assertion comparing a Decimal against a bare int, which
    had never once executed. Issue #85.

    Every module passes on its own. Grail's own SUnit runner partitions for the
    same reason and says so: the partition count decides how much of the corpus
    one session carries.

    A child gets its module name on the command line and so takes the branch
    below, which is what stops this recursing.
    """
    failed = []
    for name in MODULES:
        print("\n=== %s ===" % name, flush=True)
        finished = subprocess.run(
            ["gemdb", os.path.join("tools", "run_db_tests.py"), name],
            cwd=REPO)
        if finished.returncode != 0:
            failed.append(name)

    print()
    if failed:
        print("FAILED in %d of %d modules: %s"
              % (len(failed), len(MODULES), ", ".join(failed)))
        return 1
    print("OK -- %d modules, each in a session of its own." % len(MODULES))
    return 0


def run_db_tests():
    wanted = [a if a.startswith("test_") else "test_" + a
              for a in sys.argv[1:]]
    if not wanted:
        return run_each_in_its_own_session()
    worst = 0
    for name in wanted:
        worst = max(worst, run_one_module(name))
    return worst


if __name__ == "__main__":
    sys.exit(run_db_tests())
