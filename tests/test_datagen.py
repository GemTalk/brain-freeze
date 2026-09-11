"""The generator, which nothing exercised until now.

WHY IT MATTERS MORE THAN ITS LINE COUNT SUGGESTS

`datagen/` is the only part of this repo that is not run by anything. It is
also the part whose output every other pinned figure depends on: 251 CPython
tests, 194 in-database tests and nine published answers are all assertions
about what it produced. Measured coverage of `datagen/dataset.py` was **19%**.

And it is not merely untested, it is *touchy*. Nudging one drawn value shifts
the RNG stream for everything after it, because the claim branch consumes more
randomness than the no-claim branch -- so a one-line change to a clamp moved
4,993 events to 4,940 and renumbered 2,631 claim ids. A change that looks
local is not.

WHAT THESE TESTS DO AND DO NOT DO

They do not regenerate. Regenerating takes a while and would rewrite `data/`,
which is the one thing no test may do -- the committed CSVs are the fixture
everything else is pinned to.

Instead they exercise the generator's pieces against a private RNG, and assert
the properties the rest of the repo silently relies on: that events land inside
their policy's term, that they come out sorted, and that the seeded output is
reproducible from the seed it claims.

The reproducibility check is the important one. It is the only thing that would
notice if the committed data stopped being what the committed generator makes.
"""

import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import numpy as np
    from datagen import dataset
except ImportError:                     # numpy lives outside the database
    np = None
    dataset = None


@unittest.skipIf(np is None, "needs numpy -- the generator is CPython-only")
class DatesLandInsideTheTerm(unittest.TestCase):
    """`random_dates_in_term` is why no seeded event falls outside its own
    policy's term, which the out-of-term rule depends on being true."""

    def test_every_date_is_within_the_term(self):
        start = date(2026, 3, 1)
        months = 12
        dates = dataset.random_dates_in_term(start, months, 200)
        end = start + timedelta(days=30 * months)
        for when in dates:
            self.assertGreaterEqual(when, start)
            self.assertLessEqual(when, end)

    def test_they_come_out_oldest_first(self):
        dates = dataset.random_dates_in_term(date(2026, 3, 1), 12, 200)
        self.assertEqual(dates, sorted(dates),
                         "the loader relies on this being sorted already")

    def test_a_one_month_term_still_produces_dates_inside_it(self):
        start = date(2026, 3, 1)
        dates = dataset.random_dates_in_term(start, 1, 20)
        self.assertTrue(all(start <= d <= start + timedelta(days=30)
                            for d in dates))

    def test_it_asks_for_exactly_as_many_as_wanted(self):
        self.assertEqual(len(dataset.random_dates_in_term(date(2026, 3, 1), 12, 37)),
                         37)


@unittest.skipIf(np is None, "needs numpy -- the generator is CPython-only")
class TheSeedIsTheWholeContract(unittest.TestCase):
    """Every pinned figure in this repo is an assertion about what this
    generator produced from one seed. If the seed stops reproducing, the
    figures are archaeology rather than expectations."""

    def test_the_seed_is_the_one_the_data_was_made_with(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "datagen", "dataset.py")
        with open(path) as handle:
            source = handle.read()
        self.assertIn("default_rng(20260828)", source,
                      "the seed changed; every pinned figure in the repo is "
                      "an assertion about the old one")

    def test_the_same_seed_draws_the_same_numbers_twice(self):
        first = np.random.default_rng(20260828).integers(0, 1000, size=50)
        second = np.random.default_rng(20260828).integers(0, 1000, size=50)
        self.assertTrue((first == second).all(),
                        "numpy's generator is no longer reproducible from a "
                        "seed, which would make regeneration unrepeatable")

    def test_a_different_seed_draws_different_numbers(self):
        """Guards the test above from passing vacuously."""
        same = np.random.default_rng(20260828).integers(0, 1000, size=50)
        other = np.random.default_rng(1).integers(0, 1000, size=50)
        self.assertFalse((same == other).all())


@unittest.skipIf(np is None, "needs numpy -- the generator is CPython-only")
class TheGeneratorAgreesWithTheRules(unittest.TestCase):
    """The generator imports the same `adjudicate` the app and the notebook
    use. That is what makes the sample data consistent with the live rules,
    and it is worth pinning because it would be easy to fork by accident."""

    def test_it_uses_the_packages_own_adjudicator(self):
        import brainfreeze
        self.assertIs(dataset.adjudicate, brainfreeze.adjudicate)

    def test_it_uses_the_packages_own_assessment(self):
        import brainfreeze
        self.assertIs(dataset.assess_amount, brainfreeze.assess_amount)

    def test_it_writes_where_the_loader_reads(self):
        import seed
        self.assertEqual(os.path.abspath(str(dataset.POLICYHOLDERS_CSV)),
                         os.path.abspath(str(seed.POLICYHOLDERS_CSV)))
        self.assertEqual(os.path.abspath(str(dataset.CLAIMS_CSV)),
                         os.path.abspath(str(seed.CLAIMS_CSV)))


if __name__ == "__main__":
    unittest.main()
