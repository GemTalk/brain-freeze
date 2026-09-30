"""Run the test suite INSIDE the database, so both surfaces can be compared.

    gemdb tools/run_db_tests.py              # every module
    gemdb tools/run_db_tests.py money seed   # just these

`python3 -m unittest discover` runs the same files under CPython; running them
here too checks that one set of rules gives the same answers in both runtimes.
That matters most for money, where they round differently (`round()` is
half-up in the database, banker's outside it).

Modules are read from disk and executed into a fresh namespace rather than
imported, because the database can serve a compiled copy of a module that no
longer matches its file (GemTalk/Grail#1223).
"""

import os
import sys
import types
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
           "test_packaging", "test_serving", "test_api", "test_app"]


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

    A child gets its module name on the command line and so takes the other
    branch in `run_db_tests`, which is what stops this recursing.
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
