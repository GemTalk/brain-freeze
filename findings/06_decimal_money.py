"""Finding 6: `decimal` works here, and six things around it do not.

    gemdb findings/06_decimal_money.py

Money must not be a float. `0.1 * 3` is not `0.3`, ten dimes are not a dollar,
and this repo shipped 23 monthly premiums that disagreed with their own annual
figure by a cent because two libraries rounded the same float differently.

The good news, and it contradicts what this repo used to say: **the standard
library's `decimal` module works inside the database.** `Decimal("19.99") * 3`
was recorded as raising. It does not. Sums, products and terminating divisions
are exact, and a `Decimal` survives a commit with its value, ordering and
equality intact.

What does not work is the *surrounding* apparatus -- the operators and helpers
a person reaches for once they have a Decimal in hand. Each one below cost
time, and two of them are not exceptions but hard VM errors with no traceback
and no line number, which is the worst way to meet a limitation.

This script writes nothing and changes nothing.
"""

import sys

#: Not `__doc__` -- `__main__` is shared under Grail; see finding 2.
TITLE = "Finding 6: decimal works; round(), //, format() and statistics do not."


def show(label, fn, note=""):
    try:
        print("    %-34s %-26r %s" % (label, fn(), note))
    except Exception as error:
        print("    %-34s %-26s %s" % (label, type(error).__name__, str(error)[:40]))


def decimal_money():
    from decimal import Decimal

    print(TITLE)
    print("-" * 70)

    print("\n  WHAT WORKS -- and this is why money can be Decimal here\n")
    show("Decimal('0.1') * 3", lambda: Decimal("0.1") * 3, "float: 0.30000000000000004")
    show("ten times Decimal('0.1')",
         lambda: sum([Decimal("0.1")] * 10, Decimal(0)), "float drifts")
    show("Decimal('19.99') * 3", lambda: Decimal("19.99") * 3, "recorded as raising")
    show("Decimal('170.10') / 12", lambda: Decimal("170.10") / 12,
         "float: 14.174999999999999")

    print("\n  WHAT RAISES -- catchable, and each one has a workaround\n")
    show("Decimal('19.99') // 3", lambda: Decimal("19.99") // 3, "no floor division")
    show("Decimal('19.99') % 3", lambda: Decimal("19.99") % 3)
    show("divmod(Decimal('19.99'), 3)", lambda: divmod(Decimal("19.99"), 3))
    show("format(d, '.2f')", lambda: format(Decimal("19.99"), ".2f"), "so is '{:.2f}'.format")
    show("Decimal('19.99').quantize", lambda: Decimal("19.99").quantize, "missing")
    show("Decimal('19.99').as_tuple", lambda: Decimal("19.99").as_tuple, "missing")

    print("\n  WHAT WORKS THAT YOU MIGHT EXPECT NOT TO\n")
    show("'%.2f' % Decimal('170.1')", lambda: "%.2f" % Decimal("170.1"),
         "printf is fine; format() is not")
    show("'{}'.format(Decimal('19.99'))", lambda: "{}".format(Decimal("19.99")),
         "no spec is fine")

    print("\n  WHAT IS FATAL -- not run here, because they end the session\n")
    print("    round(Decimal, 2)          a Decimal does not understand #'*'")
    print("    statistics.mean([Decimal]) a Decimal does not understand #'_generality'")
    print("    ...and statistics.median with it. Neither raises; both end the gem.")

    print("\n  WHAT IS MERELY DIFFERENT -- and so much worse\n")
    print("    Each of these SUCCEEDS with a different answer than CPython,")
    print("    so nothing fails until two surfaces disagree in front of you.\n")
    show("int(Decimal('-14.5'))", lambda: int(Decimal("-14.5")),
         "CPython: -14 (floors here)")
    show("Decimal('92081.22') == 92081.22",
         lambda: Decimal("92081.22") == 92081.22,
         "same as CPython -- listed because this repo once claimed it differed")
    show("str(Decimal('170.10'))", lambda: str(Decimal("170.10")),
         "CPython: '170.10'")
    show("Decimal(1) / Decimal(3)", lambda: Decimal(1) / Decimal(3),
         "CPython: 28 digits")

    print("""
  WHAT THIS REPO DOES ABOUT IT

  `brainfreeze/money.py`. `usd()` builds money from text and refuses a float
  outright; `round_cents()` is half-up, written in Decimal arithmetic, and
  rounds a magnitude so the `int()` difference above cannot reach it;
  `format_usd()` restores the trailing zero that `str()` drops.

  The tests run under CPython and again inside the database -- `gemdb
  run_db_tests.py` -- because every line above is a way for the same rules to
  give two answers, and the demo's whole claim is that they give one.

  FOR THE GRAIL TEAM

  `quantize` is the one to add first: it is the operation money code reaches
  for before any other. After that, make `round(Decimal, n)` and a custom
  Jinja filter raise a Python exception rather than taking the VM down --
  a wrong answer is recoverable and a dead session is not.
""")
    return 0


if __name__ == "__main__":
    sys.exit(decimal_money())
