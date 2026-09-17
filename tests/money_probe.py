"""Money arithmetic in a session that has NOT imported `numbers`.

    gemdb tests/money_probe.py

Not a test module -- the name is deliberately outside `test*.py` so neither
`unittest discover` nor `tools/run_db_tests.py` collects it. It is the body of
one, run in a session of its own by `tests/test_decimal_comparison.py`, and it
has to be a separate session for a reason worth stating.

WHY A WHOLE SESSION

`Decimal.__gt__` converts an `int` operand through the `numbers.Rational`
ABC, and `int` only becomes a `Rational` when `numbers`'s module body runs
`Integral.register(int)`. Grail serves a module from the database WITHOUT
re-executing it, so in a session where nothing imports `numbers`, that
registration never happens and every `Decimal < 0` raises

    TypeError: '<' not supported between instances of 'Decimal' and 'int'

Any module that imports `numbers` -- anywhere, once, for any reason -- repairs
it for the whole session. So a guard against this CANNOT share a session with
the rest of the suite: it would pass because something else imported
`numbers`, not because the code under test is correct. Hence one session, and
the precondition asserted below rather than assumed.

The fix it guards is comparing against `money.ZERO` instead of a bare `0`, so
that the ABC is never consulted at all.
"""

import os
import sys
from decimal import Decimal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)


def main():
    # The precondition. If something in the import chain has pulled `numbers`
    # in, this session cannot measure anything: `int` is registered, every
    # comparison works, and a reverted fix would sail through. Say so loudly
    # rather than reporting a pass that means nothing.
    if "numbers" in sys.modules:
        print("PRECONDITION_LOST: numbers was already imported")
        return 3

    from brainfreeze.money import ZERO, round_cents, wire_usd, format_usd
    from brainfreeze.adjudication import adjudicate

    if "numbers" in sys.modules:
        print("PRECONDITION_LOST: importing brainfreeze pulled in numbers")
        return 3

    # Each of these reaches a comparison that used to be `< 0`.
    checks = [
        ("round_cents negative", lambda: round_cents(Decimal("-1.005"))),
        ("round_cents zero", lambda: round_cents(ZERO)),
        ("wire_usd negative", lambda: wire_usd(Decimal("-1.50"))),
        ("format_usd negative", lambda: format_usd(Decimal("-1.50"))),
        # payable = max(ZERO, 10 - 25) == 0, which reaches `payable <= ZERO`.
        ("adjudicate exhausted by deductible", lambda: adjudicate(
            assessed=Decimal("10.00"),
            coverage_limit_per_incident=Decimal("100.00"),
            deductible_per_incident=Decimal("25.00"),
            approved_claims_this_year=0,
        )),
    ]

    for name, call in checks:
        try:
            call()
        except TypeError as error:
            print("PROBE_FAIL: %s raised TypeError: %s" % (name, error))
            return 1

    print("PROBE_OK: %d money paths, no numbers import" % len(checks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
