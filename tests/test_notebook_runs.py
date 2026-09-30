"""The notebook must actually RUN, not merely parse.

Run: python3 -m unittest tests.test_notebook_runs -v

`tests/test_notebook.py` checks the document: the first cell puts the
repository on the path, every cell parses, regenerating changes nothing. It
cannot catch the notebook's real hazards, which are not syntactic and do not
exist under CPython: `statistics.median` on a Decimal ENDS THE SESSION inside
the database, floor division on money raises TypeError, `ast` cannot be
walked, and a `__repr__` that is fine outside is not necessarily fine in here
-- and cell 2 ends with a bare `book`, so the reader sees that repr.

The notebook is step 4 of the tutorial.

CPython-side, because it SPAWNS a database session and so cannot be one.
Skips rather than fails where there is no database to ask.
"""

import os
import re
import shutil
import subprocess
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join("tools", "run_notebook.py")


def gemdb_command():
    found = shutil.which("gemdb")
    if found:
        return found
    default = os.path.join(os.path.expanduser("~"), "GemDB", "bin", "gemdb")
    return default if os.path.isfile(default) else None


class TheNotebookRunsEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        command = gemdb_command()
        if not command:
            raise unittest.SkipTest("no gemdb CLI on this machine")
        # NOT `cls.run` -- that shadows TestCase.run and unittest calls it.
        cls.ran = subprocess.run(
            [command, RUNNER], cwd=REPO,
            capture_output=True, text=True, timeout=900,
        )
        if "could not" in cls.ran.stderr.lower() and cls.ran.returncode == 2:
            raise unittest.SkipTest(
                "no database:\n%s%s" % (cls.ran.stdout, cls.ran.stderr))

    def test_every_cell_ran(self):
        self.assertEqual(
            self.ran.returncode, 0,
            "the notebook does not run, and it is step 4 of the tutorial."
            "\n%s%s" % (self.ran.stdout, self.ran.stderr),
        )

    def test_it_ran_all_of_them(self):
        """A runner that stopped early and exited 0 would prove nothing."""
        self.assertRegex(
            self.ran.stdout,
            r"OK -- \d+ cells, in order, in one session\.",
            self.ran.stdout,
        )

    def test_it_ran_as_many_cells_as_the_notebook_has(self):
        import json
        with open(os.path.join(REPO, "brain-freeze.ipynb"), encoding="utf-8") as h:
            document = json.load(h)
        expected = len([c for c in document["cells"] if c["cell_type"] == "code"])
        reported = int(re.search(r"OK -- (\d+) cells", self.ran.stdout).group(1))
        self.assertEqual(reported, expected, self.ran.stdout)

    def test_the_book_echoed_itself(self):
        """Cell 2 ends with a bare `book`; the reader sees that repr."""
        self.assertRegex(
            self.ran.stdout, r"<Book \d+ policies, \d+ events, loss ratio ",
            "cell 2's bare `book` did not echo a Book.\n%s" % self.ran.stdout,
        )


if __name__ == "__main__":
    unittest.main()
