"""A schema change must not strand the records written before it.

Run: python3 -m unittest test_class_identity -v

Adding a class attribute to a class that already has committed instances is
the ordinary shape of a schema change -- step 3 of the tutorial. If Grail
re-minted the class instead of reusing it, every record committed under the
old one would point at a class nothing recognises, and `isinstance` would
answer False. This guards against that.

The record's data is not what is at risk; its relationship to its class,
which is what makes it findable by type, is.

It drives two real sessions (the scripts in `tests/class_identity/`), because
a genuine re-import needs a genuine new session. So it is a CPython-side test:
it spawns database sessions and cannot be one. It skips when there is no
database to ask.
"""

import os
import shutil
import subprocess
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "tests", "class_identity")
TMP_PKG = os.path.join(SCRIPTS, "tmp_migration")


def gemdb_command():
    """The `gemdb` CLI, from PATH or from the one place it installs."""
    found = shutil.which("gemdb")
    if found:
        return found
    default = os.path.join(os.path.expanduser("~"), "GemDB", "bin", "gemdb")
    return default if os.path.isfile(default) else None


def run_arm(command, script):
    return subprocess.run(
        [command, os.path.join(SCRIPTS, script)],
        cwd=REPO, capture_output=True, text=True, timeout=300,
    )


def facts(stdout):
    """The `KEY: value` lines the read arm prints, as a dict."""
    out = {}
    for line in stdout.splitlines():
        if ": " in line:
            key, _, value = line.partition(": ")
            out[key.strip()] = value.strip()
    return out


class ASchemaChange(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.command = gemdb_command()
        if not cls.command:
            raise unittest.SkipTest("no gemdb CLI on this machine")

        wrote = run_arm(cls.command, "migration_write.py")
        if wrote.returncode != 0:
            # No database, no measurement -- and no failure either, because
            # this test is about Grail's behaviour, not about whether a
            # database happens to be running on the machine running it.
            raise unittest.SkipTest(
                "could not arm the check (no database?):\n%s%s"
                % (wrote.stdout, wrote.stderr)
            )

        cls.read = run_arm(cls.command, "migration_read.py")
        cls.facts = facts(cls.read.stdout)

    @classmethod
    def tearDownClass(cls):
        # The read arm cleans up after itself; this is for the case where it
        # never ran, so a failed run cannot leave a package behind to be
        # imported -- and silently reused -- by the next one.
        shutil.rmtree(TMP_PKG, ignore_errors=True)

    def test_the_read_arm_ran(self):
        self.assertEqual(
            self.read.returncode, 0,
            "read arm failed:\n%s%s" % (self.read.stdout, self.read.stderr),
        )
        self.assertIn("ISINSTANCE", self.facts, self.read.stdout)

    def test_the_record_is_still_an_instance_of_its_class(self):
        """The whole point: the class is reused, not re-minted."""
        self.assertEqual(
            self.facts.get("ISINSTANCE"), "True",
            "a record committed before the edit is no longer an instance of "
            "its own class -- the class was re-minted and the record is "
            "stranded.\n%s" % self.read.stdout,
        )

    def test_the_class_object_itself_is_reused(self):
        self.assertEqual(
            self.facts.get("TYPE_IS"), "True",
            "the edited source compiled a different class object.\n%s"
            % self.read.stdout,
        )

    def test_the_record_keeps_its_data(self):
        # Not the point of the test, but a re-mint that also lost data would
        # be a different and worse bug, and this is what tells them apart.
        self.assertEqual(self.facts.get("DATA_INTACT"), "True", self.read.stdout)


if __name__ == "__main__":
    unittest.main()
