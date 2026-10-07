"""The notebook finds this checkout from where a notebook actually starts.

Run: python3 -m unittest tests.test_notebook_finds_its_checkout -v

A GemDB notebook does not start in the folder the editor has open. It starts in
the database's own directory, ~/GemDB/db, and the first cell used to search
only above and below where it started -- so it never looked sideways into
~/GemDB/brain-freeze, which is exactly where Install Brain Freeze Demo puts the
checkout, and a reader had to set BRAINFREEZE_REPO by hand to get past it.

The tutorial's own run never met this: `gemdb tools/run_notebook.py` runs the
cells from the repository. So these run cell 1 the way an editor does, from a
directory shaped like ~/GemDB/db, under a HOME of their own and with no
BRAINFREEZE_REPO.

CPython-side, because each SPAWNS a database session. Skips where there is no
gemdb to spawn.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def gemdb_command():
    found = shutil.which("gemdb")
    if found:
        return found
    default = os.path.join(os.path.expanduser("~"), "GemDB", "bin", "gemdb")
    return default if os.path.isfile(default) else None


def first_code_cell():
    with open(os.path.join(REPO, "brain-freeze.ipynb")) as handle:
        cells = json.load(handle)["cells"]
    return "".join(next(c for c in cells if c["cell_type"] == "code")["source"])


def recorded_checkout(command):
    """What step 1 recorded in this database, or None."""
    ran = subprocess.run(
        [command, "-c", 'import gemdb; print("RECORDED", gemdb.root.get("brainfreeze_repo"))'],
        cwd=REPO, capture_output=True, text=True, timeout=300)
    for line in ran.stdout.splitlines():
        if line.startswith("RECORDED "):
            value = line.split(" ", 1)[1]
            return None if value == "None" else value
    return None


@unittest.skipUnless(gemdb_command(), "needs GemDB: no gemdb command here")
class TheNotebookFindsItsCheckout(unittest.TestCase):

    def run_cell_from_a_gemdb_db(self, demo_checkout):
        """Run cell 1 from <home>/GemDB/db, as an editor's notebook starts.
        `demo_checkout` puts this checkout at <home>/GemDB/brain-freeze, where
        Install Brain Freeze Demo would. Answers the repository it printed."""
        home = tempfile.mkdtemp(prefix="bf-notebook-home-")
        self.addCleanup(shutil.rmtree, home, True)
        start = os.path.join(home, "GemDB", "db")
        os.makedirs(start)
        if demo_checkout:
            os.symlink(REPO, os.path.join(home, "GemDB", "brain-freeze"))
        cell = os.path.join(home, "cell1.py")
        with open(cell, "w") as handle:
            handle.write(first_code_cell())
        env = {k: v for k, v in os.environ.items() if k != "BRAINFREEZE_REPO"}
        env["HOME"] = home
        ran = subprocess.run([gemdb_command(), cell], cwd=start, env=env,
                             capture_output=True, text=True, timeout=300)
        self.assertEqual(ran.returncode, 0,
                         "cell 1 failed from %s:\n%s%s" % (start, ran.stdout, ran.stderr))
        printed = [l for l in ran.stdout.splitlines() if l.startswith("repository: ")]
        self.assertTrue(printed, "cell 1 printed no repository:\n%s" % ran.stdout)
        return printed[-1].split(": ", 1)[1]

    def test_it_finds_the_demo_where_install_brain_freeze_demo_puts_it(self):
        found = self.run_cell_from_a_gemdb_db(demo_checkout=True)
        self.assertEqual(os.path.realpath(found), os.path.realpath(REPO))

    def test_it_finds_a_checkout_elsewhere_from_where_step_1_ran(self):
        """Wherever the clone is, step 1's seed.py has recorded it."""
        if not recorded_checkout(gemdb_command()):
            self.skipTest("this database was seeded before seed.py recorded its "
                          "checkout -- run `gemdb tools/seed.py`")
        found = self.run_cell_from_a_gemdb_db(demo_checkout=False)
        self.assertTrue(os.path.isdir(os.path.join(found, "brainfreeze")), found)


if __name__ == "__main__":
    unittest.main()
