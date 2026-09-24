"""`redeploy.point_at_disk` -- a redeploy must survive the checkout moving.

Run: python3 -m unittest tests.test_redeploy_path -v

Grail keeps a module compiled by a session that commits, and keeps the path it
was compiled from with it. `importlib.reload` re-reads that path, so once the
directory has been renamed the database cannot be given new code at all:

    GsFile open failed for '.../Brain Freeze Insurance/brainfreeze/money.py'
    (mode 'rb'): No such file or directory

That is not hypothetical. It is what this repository's own database did after
the checkout was renamed from `Brain Freeze Insurance` to `brain-freeze`, and
it disabled `gemdb tools/redeploy.py` -- the one command the README documents
for getting edited rules into the database -- while leaving every other command
working, so nothing pointed at the cause.

These are CPython tests of a pure path calculation, deliberately: the database
behaviour they defend against is expensive to stage and already recorded above,
and what can actually go wrong in the fix is the arithmetic on module names.
"""

import os
import sys
import types
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(REPO, "tools") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "tools"))

import redeploy


def a_module(name, recorded):
    module = types.ModuleType(name)
    module.__file__ = recorded
    return module


class PointingAModuleAtItsSourceOnDisk(unittest.TestCase):
    def test_a_stale_path_is_replaced_with_where_the_source_is_now(self):
        module = a_module(
            "brainfreeze.money", "/gone/Brain Freeze Insurance/brainfreeze/money.py")
        self.assertTrue(redeploy.point_at_disk(module, "brainfreeze.money", REPO))
        self.assertEqual(
            module.__file__, os.path.join(REPO, "brainfreeze", "money.py"))

    def test_a_package_is_found_through_its_dunder_init(self):
        """`brainfreeze` is a directory; its source is `__init__.py`."""
        module = a_module("brainfreeze", "/gone/Brain Freeze Insurance/brainfreeze/__init__.py")
        self.assertTrue(redeploy.point_at_disk(module, "brainfreeze", REPO))
        self.assertEqual(
            module.__file__, os.path.join(REPO, "brainfreeze", "__init__.py"))

    def test_a_path_that_is_already_right_is_left_alone(self):
        """So a redeploy on an unmoved checkout is not silently rewriting."""
        right = os.path.join(REPO, "brainfreeze", "money.py")
        module = a_module("brainfreeze.money", right)
        self.assertFalse(redeploy.point_at_disk(module, "brainfreeze.money", REPO))
        self.assertEqual(module.__file__, right)

    def test_a_module_with_no_source_on_disk_is_not_touched(self):
        """Inventing a path would turn a clear failure into a confusing one."""
        module = a_module("brainfreeze.nosuch", "/gone/brainfreeze/nosuch.py")
        self.assertFalse(redeploy.point_at_disk(module, "brainfreeze.nosuch", REPO))
        self.assertEqual(module.__file__, "/gone/brainfreeze/nosuch.py")

    def test_a_module_with_no_recorded_file_at_all_is_still_pointed(self):
        """Grail has handed back modules without `__file__`; do not crash."""
        module = types.ModuleType("brainfreeze.money")
        self.assertTrue(redeploy.point_at_disk(module, "brainfreeze.money", REPO))
        self.assertEqual(
            module.__file__, os.path.join(REPO, "brainfreeze", "money.py"))


if __name__ == "__main__":
    unittest.main()
