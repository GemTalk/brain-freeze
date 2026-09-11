"""Run the test suite INSIDE the database, so both surfaces can be compared.

    gemdb run_db_tests.py              # every module
    gemdb run_db_tests.py money seed   # just these

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
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

#: In dependency order, cheapest first, so a broken foundation fails fast.
MODULES = ["test_money", "test_brainfreeze", "test_seed", "test_analysis",
           "test_packaging", "test_api", "test_app"]


def load_module_from_file(name, path):
    module = types.ModuleType(name)
    module.__file__ = path
    with open(path) as handle:
        source = handle.read()
    exec(compile(source, path, "exec"), module.__dict__)
    return module


def run_db_tests():
    wanted = [a if a.startswith("test_") else "test_" + a
              for a in sys.argv[1:]] or MODULES
    suite = unittest.TestSuite()
    for name in wanted:
        path = os.path.join(HERE, "tests", "%s.py" % name)
        if not os.path.exists(path):
            print("no such test module: %s" % path)
            return 2
        module = load_module_from_file("%s_live" % name, path)
        suite.addTests(unittest.TestLoader().loadTestsFromModule(module))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_db_tests())
