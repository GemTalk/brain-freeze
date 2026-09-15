"""Every factual claim in the demo script, checked against the thing it claims.

WHY A DOCUMENT GETS A TEST

`docs/demo-script.md` is not prose about the demo, it is instructions for
driving it: type this id, click that button, expect these four figures. Every
one of those is a fact about code that changes, and the failure mode is not a
broken build. It is someone standing in front of an audience clicking a button
that has been renamed.

The README has the same exposure and is checked the same way for the parts
that overlap. What is special here is the click targets and the arithmetic,
because nothing else in the suite reads them.

Deliberately NOT checked here: that the app serves those pages. The acceptance
suite drives them in a real browser and fails if a route goes unreached. This
is about whether the SCRIPT still describes what the acceptance suite drives.
"""

import ast
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "docs", "demo-script.md")


def script():
    with open(SCRIPT, encoding="utf-8") as handle:
        return handle.read()


def read(*parts):
    with open(os.path.join(REPO, *parts), encoding="utf-8") as handle:
        return handle.read()


class TheCommandsItTellsYouToRunExist(unittest.TestCase):
    """A script naming a file that moved is worse than one naming none: it
    reads as authoritative right up to the moment it fails."""

    def setUp(self):
        self.text = script()

    def commands(self):
        """Every `gemdb <path>` and `python3 <path>` in a fenced block."""
        return set(re.findall(r"(?:gemdb|python3)\s+((?:tools|web|findings)/[\w./-]+\.py)",
                              self.text))

    def test_every_script_it_names_is_there(self):
        missing = sorted(c for c in self.commands()
                         if not os.path.exists(os.path.join(REPO, c)))
        self.assertEqual(missing, [], "commands naming files that do not exist")

    def test_it_names_the_ones_the_demo_actually_needs(self):
        """A guard on the extractor: if the regex stops matching, every
        assertion above passes for the wrong reason."""
        for needed in ("tools/seed.py", "web/app.py", "tools/lapse.py"):
            self.assertIn(needed, self.commands())

    def test_every_file_it_points_at_exists(self):
        missing = []
        for target in re.findall(r"\]\(([^)]+)\)", self.text):
            target = target.split("#")[0]
            if not target or target.startswith(("http", "mailto")):
                continue
            full = os.path.normpath(os.path.join(os.path.dirname(SCRIPT), target))
            if not os.path.exists(full):
                missing.append(target)
        self.assertEqual(missing, [])


class TheThingsItTellsYouToClickAreOnThePages(unittest.TestCase):
    """Button and link text, and the form's questions and answers. These live
    in `web/templates.py` and `web/forms.py`, and a rename there silently
    turns this document into fiction."""

    def setUp(self):
        self.text = script()
        self.templates = read("web", "templates.py")
        self.forms = read("web", "forms.py")

    def test_the_controls_it_names_are_in_the_templates(self):
        for control in ("Find", "File a claim", "Send the claim",
                        "All policyholders", "see the policy",
                        "Go to a policy", "Take out"):
            self.assertIn(control, self.templates,
                          "the script says to click %r and no template "
                          "renders it" % control)

    def test_the_form_questions_it_lists_are_the_form_s_questions(self):
        """The script carries the claim form as a table. Every left-hand cell
        has to be a real legend, or the presenter is reading a form that does
        not exist."""
        legends = set(re.findall(r"<legend>([^<]+)", self.templates))
        legends |= set(re.findall(r"<legend>([^<]+)<", self.templates))
        flat = " ".join(l.strip() for l in legends)
        for question in ("What did they have?", "How cold was it?",
                         "How much of it?", "How fast?",
                         "How long did it last?", "Where did it hurt?",
                         "What did it feel like?"):
            self.assertIn(question, self.text,
                          "the script no longer lists %r" % question)
            self.assertIn(question, flat,
                          "the script lists %r and the form does not ask it"
                          % question)

    def test_the_answers_it_tells_you_to_pick_are_offered(self):
        """Every label the script says to click has to be one the form
        renders.

        Parsed rather than grepped. A regex over the source picks up the
        insides of docstrings -- the first version of this test "found"
        several hundred fragments of prose and still missed `All at once`,
        which is three lines of real code away.
        """
        offered = {node.value
                   for node in ast.walk(ast.parse(self.forms))
                   if isinstance(node, ast.Constant)
                   and isinstance(node.value, str)}
        for answer in ("Straight from the freezer", "A lot", "All at once",
                       "Longer than ten", "Forehead", "Stabbing",
                       "Mint choc chip", "Sprinkles"):
            self.assertIn(answer, self.text, "script dropped %r" % answer)
            self.assertIn(answer, offered,
                          "the script says to pick %r and the form does not "
                          "offer it" % answer)

    def test_the_refusal_wording_is_what_the_app_says(self):
        routes = read("web", "routes_html.py")
        self.assertIn("Cover on this policy ended on", routes)
        self.assertIn("Cover on this policy ended on", self.text)
        self.assertIn("has used all", routes)
        self.assertIn("has used all", self.text)


class TheArithmeticItQuotesIsWhatTheRulesGive(unittest.TestCase):
    """The decision screen's four figures, recomputed from the model rather
    than trusted. These are the numbers a presenter reads aloud."""

    def setUp(self):
        import brainfreeze
        from brainfreeze.money import format_usd, usd
        import sys
        web = os.path.join(REPO, "web")
        if web not in sys.path:
            sys.path.insert(0, web)
        import forms
        self.text = script()
        duration = dict(forms.DURATION_BANDS)["Longer than ten"]
        assessed = brainfreeze.assess_amount(9, duration)
        limit, deductible = usd("60.00"), usd("5.00")
        self.figures = {
            "assessed": format_usd(assessed),
            "trimmed": format_usd(assessed - min(assessed, limit)),
            "deductible": format_usd(deductible),
            "paid": format_usd(min(assessed, limit) - deductible),
        }

    def test_the_script_quotes_the_figures_the_rules_produce(self):
        for name, figure in self.figures.items():
            self.assertIn(figure, self.text,
                          "the rules give %s for the %s and the script does "
                          "not say so" % (figure, name))

    def test_the_payout_it_leads_with_is_the_payout(self):
        self.assertIn('"%s is yours"' % self.figures["paid"], self.text)


class ThePoliciesItNamesAreFitForTheirBeat(unittest.TestCase):
    """Each beat needs a policy in a particular state, and a regenerated
    dataset moves every one of them."""

    @classmethod
    def setUpClass(cls):
        import seed
        cls.book = seed.load()

    def setUp(self):
        self.text = script()

    def test_every_policy_it_names_is_in_the_book(self):
        """Looked up rather than tested with `in`: iterating a Book yields
        policyholders, so `"BF-100092" in book` is False for every policy in
        it -- which is what the first version of this test reported."""
        named = sorted(set(re.findall(r"BF-1\d{5}", self.text)))
        self.assertTrue(named, "the script names no policies at all")
        for policy_id in named:
            try:
                self.book[policy_id]
            except KeyError:
                self.fail("the script sends the presenter to %s and the "
                          "seeded book has no such policy" % policy_id)

    def test_the_claim_beat_s_policy_has_a_clean_history(self):
        """BF-100332 is chosen so nothing on screen competes with the point."""
        policy = self.book["BF-100332"]
        self.assertEqual(len(policy.claims), 0,
                         "BF-100332 arrives with claims already on it, so the "
                         "decision screen is no longer the only thing to read")
        self.assertEqual(policy.plan_name, "Standard")

    def test_the_refusal_beat_s_policy_has_exactly_one_approval_left(self):
        """BF-100092 has to pay once and then refuse. Two left and the beat
        needs an extra click; none left and the first claim never pays."""
        policy = self.book["BF-100092"]
        self.assertEqual(policy.claims_remaining_this_year, 1,
                         "BF-100092 has %d approvals left, and the beat is "
                         "written for exactly one"
                         % policy.claims_remaining_this_year)

    def test_the_cross_surface_policy_starts_in_force(self):
        """BF-100184 is lapsed live in beat 6, so it must begin active."""
        from datetime import date
        self.assertTrue(self.book["BF-100184"].is_in_force_on(date.today()),
                        "BF-100184 does not start in force, so beat 6 opens "
                        "by lapsing something already lapsed")


class TheNotebookCellsItNumbersAreTheNotebookS(unittest.TestCase):
    """Beat 5 tells the presenter to stop on numbered cells. Adding a cell
    shifts every number after it, which is how the path fix nearly left this
    document pointing at the wrong ones."""

    def setUp(self):
        import json
        self.text = script()
        with open(os.path.join(REPO, "brain-freeze.ipynb"), encoding="utf-8") as h:
            notebook = json.load(h)
        self.cells = [("".join(c["source"]))
                      for c in notebook["cells"] if c["cell_type"] == "code"]

    def cited(self):
        table = self.text[self.text.index("| Cell | What to say"):]
        table = table[:table.index("\n\n")]
        return [int(n) for n in re.findall(r"\|\s*\*\*(\d+)\*\*", table)]

    def test_every_cell_it_cites_exists(self):
        cited = self.cited()
        self.assertTrue(cited, "beat 5 cites no cells")
        for number in cited:
            self.assertLessEqual(number, len(self.cells),
                                 "beat 5 sends the presenter to cell %d and "
                                 "the notebook has %d"
                                 % (number, len(self.cells)))

    def test_the_cells_it_describes_are_the_ones_it_means(self):
        for number, expect in ((1, "sys.path"), (2, "gemdb.root"),
                               (3, "BF-100539")):
            self.assertIn(expect, self.cells[number - 1],
                          "beat 5 describes cell %d as doing something with "
                          "%r and it does not" % (number, expect))

    def test_the_cells_it_says_to_leave_alone_are_the_refresh_beat(self):
        said = re.search(r"Leave cells (\d+) and (\d+) alone", self.text)
        self.assertIsNotNone(said, "beat 5 no longer names the cells to skip")
        for number in said.groups():
            self.assertIn("gemdb.", self.cells[int(number) - 1])
        self.assertIn("refresh", self.cells[int(said.group(2)) - 1])


if __name__ == "__main__":
    unittest.main()
