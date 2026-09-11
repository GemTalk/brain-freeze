"""No undefined name reaches a handler.

WHY THIS EXISTS

The modules that serve requests -- `app`, `routes_html`, `routes_api`,
`lookups`, `wire` -- import `gemdb` and `flask`, so CPython cannot import
them. Nothing in the CPython suite executes a single line of them. A name
that does not exist is therefore invisible until a request reaches that line
inside the database, and the demo's most expensive half hour was spent
finding exactly that: handlers calling helpers under names they had been
given while the app was one file.

`tests/test_imports.py` resolves the imports between these modules without
running them. This closes the other half -- a name used but never bound --
by handing the files to pyflakes, which does the scope analysis properly
rather than approximately.

Pyflakes is the one development dependency, and it is optional on purpose:
the application itself is standard library only, so that the same code runs
under CPython and inside GemStone. When it is missing this module says so
and skips, which is why `run_db_tests.py` and the in-database suite remain
the backstop rather than the only line of defence.

    python3 -m pip install pyflakes
"""

import os
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Everything that only ever runs inside the database: the web app, and the
#: commands. `verify_book.py` and `lapse.py` import a module purely to put
#: the repository on `sys.path` and are the one place a "not used" complaint
#: is the right answer, so a `# noqa` on the line excuses it -- pyflakes does
#: not read those itself.
SURFACE = sorted(
    os.path.join(directory, name)
    for directory in ("web", "tools")
    for name in os.listdir(os.path.join(REPO, directory))
    if name.endswith(".py"))


def pyflakes_is_available():
    try:
        import pyflakes  # noqa: F401  presence is the whole check
    except ImportError:
        return False
    return True


@unittest.skipUnless(pyflakes_is_available(),
                     "pyflakes is not installed -- `python3 -m pip install "
                     "pyflakes` to check the modules CPython cannot import")
class TheModulesTheDatabaseRunsAreClean(unittest.TestCase):
    def flakes(self, *paths):
        finished = subprocess.run(
            [sys.executable, "-m", "pyflakes"] + list(paths),
            cwd=REPO, capture_output=True, text=True)
        return [line for line in finished.stdout.splitlines()
                if line.strip() and not self.excused(line)]

    def excused(self, complaint):
        """True when the line complained about carries a `# noqa`."""
        head = complaint.split(":")
        if len(head) < 2 or not head[1].isdigit():
            return False
        try:
            with open(os.path.join(REPO, head[0])) as handle:
                line = handle.read().splitlines()[int(head[1]) - 1]
        except (OSError, IndexError):
            return False
        return "# noqa" in line

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
