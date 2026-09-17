"""The notebook, checked the way a kernel will meet it.

WHY THIS EXISTS, AND WHAT IT IS MAKING UP FOR

`brain-freeze.ipynb` shipped for weeks unable to import its own model. Cell
three said `from brainfreeze import analysis` and raised
`ModuleNotFoundError` in a real kernel, because a kernel starts in the
database's working directory and a cell has no `__file__` to derive one from.

Nothing caught it, and the reason is the interesting part.
`tools/run_notebook_check.py` put the repository on `sys.path` and THEN
executed the cells. Every cell ran, every run was green, and the acceptance
suite -- which drives the notebook through that same runner -- was green with
it. The check had arranged a condition the thing being checked would not have.

So these tests are about the shape of the notebook rather than its output,
because output is the part that was already being checked wrongly:

  * the first code cell puts the repository on the path itself;
  * the runner does NOT, so it cannot go back to hiding this;
  * the committed .ipynb is what the generator produces, since a notebook
    edited by hand drifts from the file that is supposed to define it.
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTEBOOK = os.path.join(REPO, "brain-freeze.ipynb")
GENERATOR = os.path.join(REPO, "tools", "make_notebook.py")
RUNNER = os.path.join(REPO, "tools", "run_notebook_check.py")


def notebook():
    with open(NOTEBOOK, encoding="utf-8") as handle:
        return json.load(handle)


def code_cells():
    return [c for c in notebook()["cells"] if c["cell_type"] == "code"]


def source(cell):
    return "".join(cell["source"])


class TheNotebookCanFindItsOwnModel(unittest.TestCase):
    """The defect, pinned. A kernel gets no help from anybody."""

    def test_the_first_code_cell_puts_the_repository_on_the_path(self):
        first = source(code_cells()[0])
        self.assertIn("sys.path", first,
                      "the notebook's first cell does not touch sys.path, so "
                      "`import brainfreeze` raises ModuleNotFoundError in any "
                      "kernel that did not start inside this checkout")
        self.assertIn("brainfreeze", first,
                      "the first cell adjusts the path without checking it "
                      "found the package, so a wrong answer is silent")

    def test_it_happens_before_anything_is_imported_from_the_model(self):
        """Order, not presence. A path set after the import is decoration."""
        cells = code_cells()
        first_model_import = None
        for index, cell in enumerate(cells):
            if "brainfreeze" in source(cell) and "import" in source(cell):
                if "sys.path" not in source(cell):
                    first_model_import = index
                    break
        self.assertIsNotNone(first_model_import,
                             "no cell imports from brainfreeze at all")
        path_cells = [i for i, c in enumerate(cells)
                      if "sys.path" in source(c)]
        self.assertTrue(path_cells, "no cell sets sys.path")
        self.assertLess(min(path_cells), first_model_import,
                        "the path is set after the model is first imported")

    def test_a_reader_is_told_what_to_do_when_it_cannot_find_it(self):
        """The failure a presenter meets ten minutes before a demo has to say
        what to do, not just what went wrong."""
        first = source(code_cells()[0])
        self.assertIn("raise", first)
        self.assertIn("BRAINFREEZE_REPO", first,
                      "no escape hatch for a kernel started outside the tree")

    def test_the_first_cell_is_valid_python(self):
        ast.parse(source(code_cells()[0]))


class TheCheckerDoesNotArrangeWhatItChecks(unittest.TestCase):
    """`run_notebook_check.py` used to put the repository on `sys.path` before
    executing the cells, which is exactly how the defect above survived. This
    is the test that would have caught that, and it is deliberately about the
    runner's source rather than its output."""

    def setUp(self):
        with open(RUNNER) as handle:
            self.source = handle.read()
        self.tree = ast.parse(self.source)

    def test_the_runner_never_touches_sys_path(self):
        touches = [node for node in ast.walk(self.tree)
                   if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Attribute)
                   and node.func.attr in ("insert", "append")
                   and getattr(node.func.value, "attr", "") == "path"
                   and getattr(getattr(node.func.value, "value", None),
                               "id", "") == "sys"]
        self.assertEqual(
            touches, [],
            "the notebook checker puts the repository on sys.path again. "
            "That is how it came to pass for weeks while the notebook could "
            "not import its own model in a real kernel: the check supplied "
            "the one thing a kernel does not.")

    def test_it_still_says_why(self):
        self.assertIn("sys.path", self.source,
                      "the comment explaining why the runner must not do "
                      "this has gone, and the next person will add it back")


class TheCommittedNotebookIsWhatTheGeneratorMakes(unittest.TestCase):
    """`make_notebook.py` is the source of truth -- a .ipynb is JSON with the
    code split into per-line strings, and editing that by hand is how a
    notebook and the file that defines it quietly diverge."""

    def test_regenerating_changes_nothing(self):
        with open(NOTEBOOK, encoding="utf-8") as handle:
            before = handle.read()
        backup = tempfile.NamedTemporaryFile(
            "w", suffix=".ipynb", delete=False, encoding="utf-8")
        backup.write(before)
        backup.close()
        try:
            finished = subprocess.run([sys.executable, GENERATOR],
                                      cwd=REPO, capture_output=True, text=True)
            self.assertEqual(finished.returncode, 0, finished.stderr)
            with open(NOTEBOOK, encoding="utf-8") as handle:
                after = handle.read()
        finally:
            with open(NOTEBOOK, "w", encoding="utf-8") as handle:
                handle.write(before)
            os.remove(backup.name)
        self.assertEqual(
            after, before,
            "the committed notebook is not what tools/make_notebook.py "
            "produces -- it has been edited by hand, or the generator has "
            "changed and nobody regenerated")

    def test_no_cell_ships_saved_output(self):
        """A notebook with saved output is a screenshot. This one has to be
        run against a live database, which is the point of it."""
        loaded = [c for c in code_cells() if c.get("outputs")]
        self.assertEqual(
            [source(c).split("\n")[0] for c in loaded], [],
            "these cells ship with output saved")

    def test_every_cell_parses(self):
        for number, cell in enumerate(code_cells(), 1):
            try:
                ast.parse(source(cell))
            except SyntaxError as bad:
                self.fail("code cell %d does not parse: %s" % (number, bad))


if __name__ == "__main__":
    unittest.main()


class TheFirstCellFindsACheckoutBelowWhereTheKernelStarted(unittest.TestCase):
    """A kernel does not start inside the checkout, and it does not start
    above it in the useful sense either. It starts at HOME, and the checkout
    is three directories underneath.

    Measured, from the GemDB extension's own error output:

        GemDBError: RuntimeError - No brainfreeze/ at or above
        '/Users/srbaker'. Open this repository as the folder in your editor

    `find_repo` walked upward only, so a checkout BELOW the starting point was
    unreachable by construction: the parents of `/Users/srbaker` are `/Users`
    and `/`, and neither holds a `brainfreeze/`. The first cell raised, and
    every cell after it failed on a name that was never bound -- which is why
    this reads as "the notebook gets errors" rather than as one error.

    This is the same defect as `TheNotebookCanFindItsOwnModel` above, one step
    out: that one fixed a cell that never looked, this one fixes a cell that
    looked in the only direction that could not work.

    It runs the first cell the way a kernel does -- its own process, and a
    working directory that is an ANCESTOR of the checkout.
    """

    def run_first_cell(self, cwd):
        env = dict(os.environ)
        # The escape hatch is not what is under test; discovery is.
        env.pop("BRAINFREEZE_REPO", None)
        return subprocess.run([sys.executable, "-c", source(code_cells()[0])],
                              cwd=cwd, env=env, capture_output=True, text=True)

    def reported(self, done):
        """The path the cell says it found, not merely that it said something."""
        for line in done.stdout.splitlines():
            if line.startswith("repository:"):
                return line.split(":", 1)[1].strip()
        return None

    def test_it_finds_a_checkout_underneath_the_working_directory(self):
        with tempfile.TemporaryDirectory() as raw:
            tmp = os.path.realpath(raw)
            checkout = os.path.join(tmp, "GemTalk", "Brain Freeze Insurance")
            os.makedirs(os.path.join(checkout, "brainfreeze"))
            done = self.run_first_cell(tmp)
            self.assertEqual(done.returncode, 0,
                             "the first cell failed from an ancestor of the "
                             "checkout, which is where a kernel starts:\n"
                             + done.stderr)
            self.assertEqual(self.reported(done), checkout)

    def test_a_checkout_it_is_standing_in_still_wins(self):
        """The downward search is a fallback, not a replacement. A kernel
        started inside a checkout must use that one, even when another lies
        beneath it."""
        with tempfile.TemporaryDirectory() as raw:
            tmp = os.path.realpath(raw)
            here = os.path.join(tmp, "here")
            os.makedirs(os.path.join(here, "brainfreeze"))
            os.makedirs(os.path.join(here, "nested", "decoy", "brainfreeze"))
            done = self.run_first_cell(here)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(self.reported(done), here)

    def test_it_still_says_what_to_do_when_there_is_no_checkout_anywhere(self):
        """Losing the message would trade one silent failure for another."""
        with tempfile.TemporaryDirectory() as raw:
            done = self.run_first_cell(os.path.realpath(raw))
            self.assertNotEqual(done.returncode, 0)
            self.assertIn("BRAINFREEZE_REPO", done.stderr)
