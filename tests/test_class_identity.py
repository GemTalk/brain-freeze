"""A schema change must not strand the records written before it.

Run: python3 -m unittest test_class_identity -v

Adding a class attribute to a class that already has committed instances is
the ordinary shape of a schema change, and it used to re-mint the class: an
added class attribute needed a slot on the metaclass, a metaclass cannot grow
one, so Grail declined to reuse the class. Every record committed under the
old one was left pointing at a class nothing recognised, and `isinstance`
answered False.

That is the whole of what this asserts, and it is deliberately narrow. The
record's DATA was never at risk and asserting it proves nothing; what the edit
threatens is the record's relationship to its class -- which is what makes it
findable by type, and what an application actually depends on.

This drives two real sessions, because a genuine re-import needs a genuine new
session; `findings/class-identity/` holds the scripts and says why. It is a
CPython-side test for that reason: it SPAWNS database sessions, so it cannot
itself be one. `tools/run_db_tests.py` names its modules explicitly and does
not pick this up.

It skips rather than fails when there is no database to ask, so a checkout
without one still runs the suite.
"""

import os
import shutil
import subprocess
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "findings", "class-identity")
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
