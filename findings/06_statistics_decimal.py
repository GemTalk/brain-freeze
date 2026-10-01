"""Finding 6: `statistics.mean` and `median` over Decimals end the session.

    gemdb findings/06_statistics_decimal.py

Live on GemDB Code 1.5.3 (Grail 84821c1). Fixed by GemTalk/Grail#1280, not yet
in a GemDB release.

`decimal` itself works inside the database as it does under CPython -- which is
why money is a Decimal here (brainfreeze/money.py). But `statistics.mean` or
`statistics.median` over a list of Decimals does not raise: the session ends,
with a Smalltalk error and no Python exception to catch:

    a MessageNotUnderstood occurred (error 2010),
    a Decimal does not understand #'_generality'

CPython answers `Decimal('1.65')`. This script shows the float case working,
then makes the call -- so the last thing it prints is the session ending.
"""

import statistics
from decimal import Decimal

print("statistics.mean([1.1, 2.2])         ", statistics.mean([1.1, 2.2]))
print("statistics.mean([Decimal('1.10'), Decimal('2.20')]) -- ends the session:",
      flush=True)
print(statistics.mean([Decimal("1.10"), Decimal("2.20")]))
print("...and it did not: this build is fixed. Delete this finding.")
