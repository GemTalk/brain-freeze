"""Money, as `decimal.Decimal` rather than as `float`.

    from brainfreeze.money import usd, round_cents, format_usd, wire_usd

A premium is an exact quantity of cents, and a `float` cannot hold most of
them: `0.1 * 3` is not `0.3`. Two floats rounded by two libraries (numpy in
the generator, Python in the model) once gave this repo 23 monthly premiums a
cent off their own annual figure.

The standard library's `decimal` works inside the database exactly as it does
under CPython, so money is a Decimal in both runtimes, and this module gives it
one rounding rule and one written form:

- Rounding is half-up (`round_half_up`, `round_cents`), which is what a person
  expects of money. Bare `round()` rounds half to even.
- Money is never shown with `str()` or `%s`, which print whatever places a
  Decimal happens to carry (`Decimal("171")` is `171`). `format_usd` is for a
  screen and `wire_usd` for JSON, both to the cent.

A *ratio* is not money and stays a float -- see `brainfreeze.analysis`.
"""

from decimal import ROUND_HALF_UP, Decimal

#: No money at all, as distinct from `None`, which is no money *recorded*.
ZERO = Decimal("0")


def usd(value):
    """Money from a string or an integer. Never from a float.

    A float argument is a `TypeError` rather than a conversion: by the time it
    arrives, the value it was meant to carry is already gone.

    An empty field reads as `None`: no money *recorded*, which is a different
    fact from zero money, and the CSVs contain both.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        raise TypeError(
            "money must not come from a float (%r); pass the text it was "
            "read from, or an int" % value)
    if isinstance(value, int):
        return Decimal(value)
    if not hasattr(value, "strip"):
        # Anything else is a programming error. One shape of it is named: after
        # a Python runtime upgrade, committed money can answer False to
        # `isinstance(value, Decimal)` while still being exact money, because
        # the class moved (GemTalk/Grail#1181). Without this branch
        # the error would be a baffling `AttributeError: strip`.
        raise TypeError(
            "money of type %s, which this runtime does not recognise as a "
            "Decimal. If this is a figure read back from the database after "
            "a Python runtime upgrade, the value is intact and it is the "
            "class that moved (GemTalk/Grail#1181), not the data."
            % type(value).__name__)
    text = value.strip()
    if not text:
        return None
    return Decimal(text)


def round_half_up(value, places=2):
    """Half-up to `places`.

    Money uses this through `round_cents`; ratios use it too, so a published
    figure is rounded the same way everywhere. Floats are accepted here,
    unlike in `usd`: a ratio is a measurement. A tie rounds away from zero,
    so -0.125 goes to -0.13.
    """
    if value is None:
        return None
    value = value if isinstance(value, Decimal) else Decimal(str(value))
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def round_cents(value):
    """Half-up to the cent. The only rounding money gets, anywhere.

    Half-up rather than half to even: it is what a person expects of money,
    and 36 of the 900 monthly premiums are exact half-cents.
    """
    return round_half_up(value, 2)


def wire_usd(value):
    """Money as an exact decimal string: `"92081.22"`. For JSON, not for eyes.

    Always two places, no symbol and no grouping. `None` stays `None` -- JSON
    writes that as `null`, which is no money *recorded* and a different fact
    from `"0.00"`.

    A string rather than a float (which would bring back the rounding
    disagreements) or integer cents: it is the same text `usd()` reads, so a
    published figure goes back into the model unchanged, with no multiplying
    or dividing by a hundred at either end.

    Not `str(value)`, which prints whatever places the Decimal carries:
    `Decimal("171")` would publish as `"171"`. The cents are written out here,
    and `format_usd` is built on top of this so the two cannot disagree.
    """
    if value is None:
        return None
    cents = round_cents(value)
    if cents == ZERO:
        cents = ZERO.quantize(cents)       # a tiny negative is "0.00", not "-0.00"
    return format(cents, "f")


def format_usd(value):
    """A display string, always two places, thousands grouped.

    `None` is `--`, because a field with no money recorded should not read as
    free. The digits come from `wire_usd`, so the screen and the JSON body
    cannot round a half-cent differently; this adds the symbol and commas.
    Never put it in a payload: `"$92,081.22"` is not a number.
    """
    if value is None:
        return "--"
    text = wire_usd(value)
    sign = ""
    if text[0] == "-":
        sign, text = "-", text[1:]
    whole, fraction = text.split(".")
    return "%s$%s.%s" % (sign, "{:,}".format(int(whole)), fraction)
