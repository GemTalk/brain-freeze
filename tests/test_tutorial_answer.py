"""The answer to tutorial step 3 still applies to this checkout.

Run: python3 -m unittest tests.test_tutorial_answer -v

Step 3's feature applies the change the README asks for --
features/answers/step3.patch -- to a running app. Any edit near the lines it
touches in brainfreeze/ or web/, a reworded comment included, can stop the
patch applying, and the tutorial job would only say so twenty minutes in. This
says so in a second. The fix is to make the change again on top of main and
write the patch out afresh.
"""

import os
import subprocess
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANSWER = os.path.join(REPO, "features", "answers", "step3.patch")


class TheStep3AnswerApplies(unittest.TestCase):

    def test_it_changes_only_the_application(self):
        with open(ANSWER) as handle:
            touched = [line.split(" b/", 1)[1] for line in handle
                       if line.startswith("diff --git ")]
        self.assertTrue(touched, "the answer changes nothing")
        for path in touched:
            self.assertTrue(path.startswith(("brainfreeze/", "web/")),
                            "the answer is the reader's change to the app, "
                            "and %s is not part of it" % path)

    def test_it_applies_to_this_checkout(self):
        applied = subprocess.run(["git", "apply", "--check", ANSWER],
                                 cwd=REPO, capture_output=True, text=True)
        self.assertEqual(
            applied.returncode, 0,
            "tutorial step 3's answer no longer applies -- make the change "
            "again on top of main and write out features/answers/step3.patch:"
            "\n%s" % applied.stderr)


if __name__ == "__main__":
    unittest.main()
