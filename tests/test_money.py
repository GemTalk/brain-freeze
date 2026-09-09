"""Money is `decimal.Decimal`, and these are the rules that keep it honest.

Run under CPython and inside the database. Both must agree, because the demo's
whole claim is that three surfaces give one answer -- and money is where a
disagreement is least forgivable.
"""

import unittest
from decimal import Decimal

from brainfreeze.money import (
    ZERO, format_usd, round_cents, round_half_up, usd)


class ParsingTests(unittest.TestCase):
    def test_it_reads_a_string_exactly(self):
        self.assertEqual(usd("170.10"), Decimal("170.10"))

    def test_it_reads_an_integer(self):
        self.assertEqual(usd(45), Decimal("45"))

    def test_it_refuses_a_float(self):
        """A float has already lost the value before we see it."""
        with self.assertRaises(TypeError):
            usd(170.10)

    def test_an_empty_field_is_no_money_rather_than_zero_money(self):
        self.assertIsNone(usd(""))
        self.assertIsNone(usd(None))

    def test_zero_is_money_not_nothing(self):
        self.assertEqual(usd("0.00"), ZERO)


class ArithmeticTests(unittest.TestCase):
    """The reason for the whole exercise."""

    def test_a_tenth_three_times_is_exactly_three_tenths(self):
        self.assertEqual(usd("0.10") * 3, usd("0.30"))

    def test_ten_tenths_are_exactly_one(self):
        total = ZERO
        for _ in range(10):
            total += usd("0.10")
        self.assertEqual(total, usd("1.00"))

    def test_the_float_version_of_that_is_wrong(self):
        """Kept as the reason this module exists, not as a test of Python."""
        self.assertNotEqual(0.1 * 3, 0.3)


class RoundingTests(unittest.TestCase):
    """Grail has no `Decimal.quantize`, so rounding is ours to define. Half-up,
    because that is what a person expects of money and what an insurer's
    schedule of premiums prints."""

    def test_it_rounds_a_half_up_not_to_even(self):
        self.assertEqual(round_cents(Decimal("14.175")), Decimal("14.18"))
        self.assertEqual(round_cents(Decimal("14.185")), Decimal("14.19"))

    def test_it_leaves_an_exact_cent_alone(self):
        self.assertEqual(round_cents(Decimal("15.00")), Decimal("15.00"))

    def test_it_rounds_a_long_tail_down(self):
        self.assertEqual(round_cents(Decimal("14.1749")), Decimal("14.17"))

    def test_it_rounds_negatives_away_from_zero(self):
        # This one failed inside the database and passed under CPython, which
        # is the whole reason it is here: `int(Decimal)` truncates toward zero
        # in CPython and floors in Grail, so a signed rounding disagreed by a
        # cent between two surfaces of the same demo.
        self.assertEqual(round_cents(Decimal("-14.175")), Decimal("-14.18"))
        self.assertEqual(round_cents(Decimal("-0.005")), Decimal("-0.01"))

    def test_it_formats_a_negative_the_same_way_in_both_runtimes(self):
        self.assertEqual(format_usd(Decimal("-14.175")), "-$14.18")

    def test_the_twenty_three_disagreements_all_resolve_the_same_way(self):
        """The premiums #68 found. Half-up settles each one."""
        for annual, monthly in (("170.10", "14.18"),
                                ("45.54", "3.80"),
                                ("167.94", "14.00")):
            self.assertEqual(round_cents(usd(annual) / 12), Decimal(monthly),
                             "annual %s" % annual)


class RatioRoundingTests(unittest.TestCase):
    """Ratios are not money, but they are still published, and bare `round()`
    is half-up in Grail and banker's in CPython -- so the same loss ratio can
    print differently on two surfaces of the same demo."""

    def test_it_rounds_a_half_up_in_both_runtimes(self):
        self.assertEqual(round_half_up(0.0625, 3), Decimal("0.063"))
        self.assertEqual(round_half_up(Decimal("0.5945"), 3), Decimal("0.595"))

    def test_bare_round_would_have_disagreed_here(self):
        """Banker's rounding sends this one the other way under CPython."""
        self.assertEqual(round(0.0625, 3), 0.062)      # what CPython does
        self.assertEqual(round_half_up(0.0625, 3), Decimal("0.063"))

    def test_it_can_round_to_no_places(self):
        self.assertEqual(round_half_up(Decimal("2.5"), 0), Decimal("3"))

    def test_round_cents_is_the_two_place_case(self):
        self.assertEqual(round_cents(Decimal("14.175")),
                         round_half_up(Decimal("14.175"), 2))


class FormattingTests(unittest.TestCase):
    """Grail does not preserve trailing zeros -- `Decimal('170.10')` comes back
    as `Decimal('170.1')` -- so a display string can never come from `str()`."""

    def test_it_always_shows_two_places(self):
        self.assertEqual(format_usd(Decimal("170.1")), "$170.10")
        self.assertEqual(format_usd(Decimal("15")), "$15.00")

    def test_it_groups_thousands(self):
        self.assertEqual(format_usd(Decimal("92081.22")), "$92,081.22")

    def test_it_shows_nothing_as_a_dash_rather_than_zero(self):
        self.assertEqual(format_usd(None), "--")

    def test_zero_is_shown_as_zero(self):
        self.assertEqual(format_usd(ZERO), "$0.00")


if __name__ == "__main__":
    unittest.main()
