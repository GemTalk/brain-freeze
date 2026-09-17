"""Money must never be compared against a bare `0`.

Run: python3 -m unittest test_decimal_comparison -v

`Decimal.__gt__` converts an `int` operand through the `numbers.Rational` ABC,
and `int` becomes a `Rational` only when `numbers`'s module body runs
`Integral.register(int)`. Grail serves a persisted module from the database
without re-executing it, so in a session where nothing imports `numbers` that
registration never happens and `Decimal("1.5") < 0` raises TypeError. Comparing
against `money.ZERO` sidesteps the ABC entirely and is correct in both
runtimes.

Two guards, because each catches what the other cannot:

`ASessionWithoutNumbers` is the real one -- it runs the money paths in a
database session of its own (`money_probe.py` says why it must be its own) and
so measures the actual behaviour. It skips where there is no database.

`TheSourceItself` is a static check, and it is not redundant. Under CPython
`Decimal < 0` works perfectly, so a reverted fix passes every ordinary test on
a machine without a database -- which is most CI. This catches the regression
by reading the source instead, so the guard survives where the first cannot
run.
"""

import ast
import os
import shutil
import subprocess
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = os.path.join(REPO, "tests", "money_probe.py")

#: Where money lives. A bare-int comparison in either is the bug.
MONEY_MODULES = [
    os.path.join(REPO, "brainfreeze", "money.py"),
    os.path.join(REPO, "brainfreeze", "adjudication.py"),
]


def gemdb_command():
    found = shutil.which("gemdb")
    if found:
        return found
    default = os.path.join(os.path.expanduser("~"), "GemDB", "bin", "gemdb")
    return default if os.path.isfile(default) else None


class ASessionWithoutNumbers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        command = gemdb_command()
        if not command:
            raise unittest.SkipTest("no gemdb CLI on this machine")
        cls.probe = subprocess.run(
            [command, PROBE], cwd=REPO, capture_output=True, text=True, timeout=300,
        )
        if "PROBE_OK" not in cls.probe.stdout and "PROBE_FAIL" not in cls.probe.stdout \
                and "PRECONDITION_LOST" not in cls.probe.stdout:
            raise unittest.SkipTest(
                "the probe did not run (no database?):\n%s%s"
                % (cls.probe.stdout, cls.probe.stderr)
            )

    def test_the_probe_could_measure_anything(self):
        # A session that has already imported `numbers` cannot see this bug,
        # so a pass from one would be meaningless. Fail instead of pretending.
        self.assertNotIn(
            "PRECONDITION_LOST", self.probe.stdout,
            "the probe's session had `numbers` imported, so it proves "
            "nothing:\n%s" % self.probe.stdout,
        )

    def test_money_arithmetic_works_without_numbers_imported(self):
        self.assertIn(
            "PROBE_OK", self.probe.stdout,
            "money arithmetic failed in a session that never imported "
            "`numbers` -- something compares a Decimal against a bare int "
            "again.\n%s%s" % (self.probe.stdout, self.probe.stderr),
        )
        self.assertEqual(self.probe.returncode, 0, self.probe.stdout)


class TheSourceItself(unittest.TestCase):
    def test_no_money_module_compares_against_a_bare_int(self):
        offenders = []
        for path in MONEY_MODULES:
            with open(path) as handle:
                tree = ast.parse(handle.read(), filename=path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Compare):
                    continue
                for operand in [node.left] + node.comparators:
                    # A bare numeric literal on either side of a comparison in
                    # a money module. `ZERO` is a Name, not a Constant, so the
                    # fixed form does not match.
                    if isinstance(operand, ast.Constant) and isinstance(
                        operand.value, int
                    ) and not isinstance(operand.value, bool):
                        offenders.append(
                            "%s:%d compares against the literal %r"
                            % (os.path.basename(path), operand.lineno, operand.value)
                        )
        self.assertEqual(
            offenders, [],
            "money is compared against a bare int; use money.ZERO so the "
            "`numbers` ABC is never consulted:\n  " + "\n  ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
