"""The repo's shape, not its arithmetic.

Run: python3 -m unittest tests.test_packaging -v

`brainfreeze/` is compiled and run *inside* the database. `datagen/` is the
only package allowed to reach for numpy and pandas. Nothing else in the suite
notices when that boundary is crossed -- a third-party import added to
`brainfreeze/` passes every other test here and then fails the first time the
web app starts.
"""

import ast
import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: What `brainfreeze/` is allowed to import. Not "the standard library" --
#: Grail ships a partial one, and these are the modules PLAN.md records as
#: actually present inside the database. Anything else, third-party or not,
#: is a module that will import fine here and fail there.
GRAIL_AVAILABLE = {"csv", "datetime", "decimal", "math", "random",
                   "statistics", "typing"}


class ThePackageBoundary(unittest.TestCase):
    """`brainfreeze/` runs inside the database. numpy and pandas do not.

    The generator lives in `datagen/` and is the only thing in the repo that
    may reach for them. This is the test that keeps that true -- a third-party
    import added here would pass every other test in the suite and then fail
    the first time the web app is started.
    """

    def test_brainfreeze_imports_only_what_grail_has(self):
        package = os.path.join(REPO_ROOT, "brainfreeze")
        checked = 0
        for name in sorted(os.listdir(package)):
            if not name.endswith(".py"):
                continue
            checked += 1
            path = os.path.join(package, name)
            with open(path) as handle:
                tree = ast.parse(handle.read(), filename=path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level:          # relative -- within the package
                        continue
                    roots = [node.module.split(".")[0]]
                else:
                    continue
                for root in roots:
                    self.assertIn(root, GRAIL_AVAILABLE,
                                  "brainfreeze/%s imports %r, which is not "
                                  "available inside the database" % (name, root))
        self.assertGreater(checked, 1, "found no modules to check")


