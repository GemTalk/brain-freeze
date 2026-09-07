"""Run the app's tests inside the database.

    gemdb run_app_tests.py

The CPython suite stays `python3 -m unittest discover`, where tests/test_app.py
skips itself for want of a database. This runner is the only way to exercise
the app at all, so it has to be trustworthy about *which* source it ran.

TWO GRAIL WRINKLES, BOTH FOUND THE HARD WAY

`gemdb -m unittest ...` exits silently with status 0 and runs nothing, and
Grail's unittest has no `loadTestsFromName`, so the suite is loaded from a
module object by hand.

More importantly, `from tests import test_app` kept returning a **stale**
module -- source edits to `tests/test_app.py` were invisible run after run,
while edits to top-level `app.py` in the same tree took effect immediately.
Grail keeps compiled modules in the database (see "Editing a class does not
update the database" in PLAN.md), and something about that registry held the
old submodule. A test runner that silently tests the previous version of the
tests is worse than no runner, so this reads the file and executes it into a
fresh namespace every time. Slower than an import, and certain.
"""

import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load_module_from_file(name, path):
    """Compile and run a source file into a brand-new module object.

    Deliberately not an import: the point is to bypass any cached or
    database-resident copy and use what is on disk right now.
    """
    module = types.ModuleType(name)
    module.__file__ = path
    with open(path) as handle:
        source = handle.read()
    exec(compile(source, path, "exec"), module.__dict__)
    return module


test_app = load_module_from_file(
    "test_app_live", os.path.join(HERE, "tests", "test_app.py"))

suite = unittest.TestLoader().loadTestsFromModule(test_app)
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
