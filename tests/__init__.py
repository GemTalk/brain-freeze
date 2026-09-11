"""Tests for Brain Freeze Insurance.

Run them all from the repo root:

    python3 -m unittest discover        # under CPython
    gemdb tools/run_db_tests.py         # the same files, inside the database

IMPORTING THIS PACKAGE PUTS THE REPOSITORY ON `sys.path`

The tests import three kinds of thing: the model from `brainfreeze/`, the web
app's modules from `web/`, and the seeder from `tools/`. Only the repository
root is on the path when `unittest discover` runs, so the other two are added
here -- `discover` imports this package before it loads a single test, which
makes this the one place that has to know.

`tools/run_db_tests.py` does the same by hand rather than relying on this: it
reads each test module from disk and executes it, because Grail will otherwise
serve a compiled copy of a test that no longer matches the file.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

for _directory in (REPO, os.path.join(REPO, "web"), os.path.join(REPO, "tools")):
    if _directory not in sys.path:
        sys.path.insert(0, _directory)
