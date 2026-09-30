"""No undefined name reaches a handler.

The modules that serve requests -- `app`, `routes_html`, `routes_api`,
`lookups`, `wire` -- import `gemdb` and `flask`, so CPython cannot import or
execute them. A name that does not exist is invisible until a request reaches
that line inside the database.

`tests/test_imports.py` resolves the imports between these modules without
running them. This closes the other half -- a name used but never bound -- by
handing the files to pyflakes, which does the scope analysis properly.

Pyflakes is the one development dependency, and it is optional on purpose:
the application itself is standard library only, so that the same code runs
under CPython and inside GemStone. When it is missing this module skips, and
the in-database suite remains the backstop.

    python3 -m pip install pyflakes
"""

import importlib.util
import os
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Everything that only ever runs inside the database: the web app, and the
#: commands. Read off the directories rather than listed, so a module added
#: to either is checked without anyone remembering to add it here.
#:
#: Nothing is excused: no `# noqa`, which would be a standing offer to hide
#: the next real complaint.
SURFACE = sorted(
    os.path.join(directory, name)
    for directory in ("web", "tools")
    for name in os.listdir(os.path.join(REPO, directory))
    if name.endswith(".py"))


def pyflakes_is_available():
    """Asked without importing it, so the answer is not itself a complaint
    pyflakes would make about this file."""
    return importlib.util.find_spec("pyflakes") is not None


@unittest.skipUnless(pyflakes_is_available(),
                     "pyflakes is not installed -- `python3 -m pip install "
                     "pyflakes` to check the modules CPython cannot import")
class TheModulesTheDatabaseRunsAreClean(unittest.TestCase):
    def flakes(self, *paths):
        finished = subprocess.run(
            [sys.executable, "-m", "pyflakes"] + list(paths),
            cwd=REPO, capture_output=True, text=True)
        return [line for line in finished.stdout.splitlines() if line.strip()]

    def test_the_surface_modules_have_no_complaints_at_all(self):
        complaints = self.flakes(*SURFACE)
        self.assertEqual(
            complaints, [],
            "these modules never run under CPython, so nothing else would "
            "have said so:\n  %s" % "\n  ".join(complaints))

    def test_the_check_actually_runs(self):
        """A subprocess that fails to start returns no complaints, which
        reads exactly like success."""
        broken = os.path.join(REPO, "artifacts", "_lint_probe.py")
        os.makedirs(os.path.dirname(broken), exist_ok=True)
        with open(broken, "w") as handle:
            handle.write("def f():\n    return undefined_on_purpose\n")
        try:
            self.assertTrue(self.flakes(broken),
                            "pyflakes reported nothing for a file that "
                            "uses an undefined name -- it did not run")
        finally:
            os.remove(broken)


if __name__ == "__main__":
    unittest.main()
