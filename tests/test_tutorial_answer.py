"""The answer to tutorial step 3 still applies to this checkout.

Run: python3 -m unittest tests.test_tutorial_answer -v

Step 3's feature applies the change the README asks for -- the commit on the
branch `tutorial-step-3` -- to a running app. Any edit near the lines it
touches in brainfreeze/ or web/, a reworded comment included, can stop the
patch applying, and the tutorial job would only say so twenty minutes in. This
says so in a second. The fix is to rebase the branch onto main.

Skips where the branch is not there to check (CI fetches it first).
"""

import os
import subprocess
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANSWER = "tutorial-step-3"


def git(*args, stdin=None):
    return subprocess.run(["git", *args], cwd=REPO, input=stdin,
                          capture_output=True, text=True)


class TheStep3AnswerApplies(unittest.TestCase):

    def setUp(self):
        if git("rev-parse", "--verify", "--quiet", ANSWER).returncode != 0:
            self.skipTest("no %s branch to check here" % ANSWER)

    def test_it_applies_to_this_checkout(self):
        diff = git("diff", ANSWER + "^", ANSWER, "--", "brainfreeze", "web")
        self.assertEqual(diff.returncode, 0, diff.stderr)
        self.assertTrue(diff.stdout, "the answer changes nothing in brainfreeze/ or web/")
        applied = git("apply", "--check", "-", stdin=diff.stdout)
        self.assertEqual(
            applied.returncode, 0,
            "tutorial step 3's answer no longer applies -- rebase %s onto "
            "main:\n%s" % (ANSWER, applied.stderr))


if __name__ == "__main__":
    unittest.main()
