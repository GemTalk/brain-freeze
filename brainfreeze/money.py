"""Money, as `decimal.Decimal` rather than as `float`.

    from brainfreeze.money import usd, round_cents, format_usd, wire_usd

A premium is not a measurement. It is an exact quantity of cents that someone
is charged, and a `float` cannot hold most of them: `0.1 * 3` is not `0.3`,
and ten dimes do not add to a dollar. That is not pedantry here -- this repo
shipped `data/policyholders.csv` with 23 monthly premiums that disagree by a
cent with the same figure derived from the annual one, because the generator
rounded with numpy and the model rounded with Python and the two disagree on
halves. Neither was wrong. Both were floats.

WHY THE STANDARD LIBRARY AND NOT INTEGER CENTS

Integer cents would also work, and it is the usual advice for this database
because `decimal` used to be unusable here. **It is not any more**, and this
module is partly a demonstration of that: a real Python library, imported from
the standard library, doing exact arithmetic inside a GemStone database.

Measured on Grail `c875e56`, 2026-09-09:

    Decimal("0.1") * 3          ->  Decimal("0.3")     exactly
    ten times Decimal("0.1")    ->  Decimal("1.0")     exactly
    Decimal("170.10") / 12      ->  Decimal("14.175")  exactly
    Decimal("19.99") * 3        ->  Decimal("59.97")   exactly

That last one is worth noting: `docs/grail-improvements.md` recorded it as
raising. It does not any more, and the note was stale.

TWO THINGS GRAIL'S DECIMAL DOES NOT DO, BOTH HANDLED HERE

`quantize` is missing, so rounding to cents is `round_cents` below, written in
Decimal arithmetic with no float in it.

Trailing zeros are not preserved -- `Decimal("170.10")` reads back as
`Decimal("170.1")`, and a committed one likewise. The values are equal and the
arithmetic is identical, but a display string can never come from `str()`.
That is what `format_usd` is for, and why nothing should interpolate money
with `%s`.

AND MONEY LEAVING THE BUILDING

`format_usd` is for a screen. `wire_usd` is for a wire: an exact decimal
string, `"170.10"`, which is what the JSON API publishes and what `usd()`
reads straight back. Nothing else may turn money into text, and nothing at
all may turn it into a float on the way out.

AND ONE THING TO KNOW

Division that does not terminate degrades to about 16 significant digits:
`Decimal(1) / Decimal(3)` is `0.3333333333333333`. Money divisions here
terminate, and every one of them is rounded to cents immediately. A *ratio* is
not money and stays a float -- see `brainfreeze.analysis`.
"""

from decimal import Decimal

#: No money at all, as distinct from `None`, which is no money *recorded*.
ZERO = Decimal("0")

_CENT = Decimal("0.01")
_HUNDRED = Decimal(100)
_HALF = Decimal("0.5")


def usd(value):
    """Money from a string or an integer. Never from a float.

    A float argument is a `TypeError` rather than a conversion, because by the
    time it reaches us the value it was meant to carry is already gone -- and
    silently accepting one is how a repository ends up with two answers to
    what a customer pays.

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
    text = value.strip()
    if not text:
        return None
    return Decimal(text)


def round_half_up(value, places=2):
    """Half-up to `places`, giving the same answer in both runtimes.

    Money uses this through `round_cents`. Ratios use it too, and that is not
    over-care: bare `round()` is **half-up inside the database and banker's
    outside it**, so a loss ratio of `0.0625` prints as `0.063` in the web app
    and `0.062` in the notebook. One dataset and three surfaces is the demo's
    whole argument; two answers to the same ratio is that argument failing in
    front of the person being shown it.

    Floats are accepted here, unlike in `usd`. A ratio is a measurement and it
    is honestly a float; the conversion is exact and the result deterministic,
    which is all this needs.

    The sign is handled by magnitude, because `int(Decimal)` truncates toward
    zero in CPython and floors in Grail -- see `round_cents`.
    """
    if value is None:
        return None
    value = value if isinstance(value, Decimal) else Decimal(str(value))
    scale = Decimal(10) ** places
    negative = value < 0
    shifted = (-value if negative else value) * scale
    whole = int(shifted)
    if shifted - whole >= _HALF:
        whole += 1
    result = Decimal(whole) / scale
    return -result if negative else result


def round_cents(value):
    """Half-up to the cent. The only rounding money gets, anywhere.

    Half-up rather than banker's, deliberately: it is what a person expects of
    money and what a schedule of premiums prints. It is also the rule that
    settles that disagreement -- 36 of the 900 monthly premiums are exact
    half-cents, and both the generator and the model had been rounding them
    down while disagreeing with each other on 23 of them.

    Grail has no `Decimal.quantize`, so this is not a wrapper around the
    library's own rounding; see `round_half_up`, which is where the arithmetic
    and the CPython/Grail differences are explained.
    """
    return round_half_up(value, 2)


def wire_usd(value):
    """Money as an exact decimal string: `"92081.22"`. For JSON, not for eyes.

    Always two places, no symbol and no grouping. `None` stays `None` -- JSON
    writes that as `null`, which is no money *recorded* and a different fact
    from `"0.00"`.

    WHY A STRING AND NOT A NUMBER

    `json.dumps` cannot serialise a Decimal at all, so a JSON API has to
    choose a wire format, and the choice is the interesting part rather than a
    detail. A float is not one of the options: it would put back the two
    answers this module exists to remove, and 23 wrong premiums in a shipped
    CSV is what that costs.

    That leaves an exact string or integer cents. Both are exact; the string
    wins on one argument, which is that it is *the same text `usd()` already
    reads*. A figure published here goes back into the model unchanged, and
    nothing at either end multiplies or divides by a hundred -- and dividing
    money is where this repo's bugs have lived. It is also what most financial
    APIs put on the wire, so a reader does not have to be told.

    NEVER `str(value)`, AND NEVER `format(value, '.2f')`

    Inside the database a Decimal does not keep its trailing zeros, so
    `str()` would publish `$170.10` as `"170.1"` and the API would answer
    differently in each runtime -- the exact failure the demo cannot afford.
    `format(value, '.2f')` raises there, and `round(value, 2)` brings the
    session down. So the arithmetic is written out, and `format_usd` is built
    on top of it rather than beside it.
    """
    if value is None:
        return None
    cents = round_cents(value)
    negative = cents < 0
    magnitude = -cents if negative else cents     # never int() a negative here
    whole = int(magnitude)
    fraction = int((magnitude - whole) * _HUNDRED + Decimal("0.5"))
    return "%s%d.%02d" % ("-" if negative else "", whole, fraction)


def format_usd(value):
    """A display string, always two places, thousands grouped.

    Never `str(value)`: Grail does not keep trailing zeros, so a premium of
    `$170.10` would print as `170.1`. `None` is `--`, because a field with no
    money recorded should not read as free.

    The two places come from `wire_usd`, so the screen and the JSON body
    cannot round a half-cent differently; this adds the symbol and the commas
    and nothing else. Which is also the reason this one must never reach a
    payload: `"$92,081.22"` is not a number.
    """
    if value is None:
        return "--"
    text = wire_usd(value)
    sign = ""
    if text[0] == "-":
        sign, text = "-", text[1:]
    whole, fraction = text.split(".")
    return "%s$%s.%s" % (sign, "{:,}".format(int(whole)), fraction)
