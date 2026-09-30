"""Is the committed book still usable? Run it either side of an upgrade.

    gemdb findings/runtime-reinstall/survives_upgrade.py > before.txt
    ... let GemDB Code update, or run install-grail.sh ...
    gemdb findings/runtime-reinstall/survives_upgrade.py > after.txt
    diff before.txt after.txt

It reads only, commits nothing, and prints one `KEY: value` per line so the
diff is the answer. On a healthy database the two files are identical.

It checks not whether the data is there -- it is -- but whether the classes
those objects point at are still the classes your code imports. A runtime
reinstall breaks that quietly: `policy_id` still reads. See README.md beside
this file for what a broken one looks like.
"""

import os
import sys

#: The repository, so `brainfreeze` is importable.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)


def main():
    import gemdb

    print("ROOT_KEYS: %s" % sorted(gemdb.root.keys()))
    try:
        book = gemdb.root["brainfreeze"]
    except Exception as error:
        print("BOOK_READ: FAILED %s: %s" % (type(error).__name__, error))
        return 1
    print("BOOK_READ: ok")
    print("POLICY_COUNT: %s" % len(book.policies))

    policy = book.policies["BF-100539"]
    print("POLICY_ID: %s" % policy.policy_id)

    # A date-valued attribute, deliberately: after a reinstall these fail
    # while `policy_id` keeps reading.
    print("POLICY_START: %s" % policy.policy_start_date)
    print("TOTAL_PAID: %s" % policy.total_paid)

    # The question the rest of it is really asking.
    #
    # `from brainfreeze import model`, because this script has to run when
    # things are broken, and when the module is not found the other form
    # (`import brainfreeze.model as model`) reported an UnboundLocalError
    # rather than the ModuleNotFoundError (#82).
    from brainfreeze import model
    print("ISINSTANCE_POLICY: %s" % isinstance(policy, model.Policyholder))
    print("TYPE_IS_POLICY: %s" % (type(policy) is model.Policyholder))

    claims = [e.claim for e in policy.events if e.claim is not None]
    print("CLAIM_COUNT: %s" % len(claims))
    if claims:
        print("ISINSTANCE_CLAIM: %s" % isinstance(claims[0], model.Claim))
        print("CLAIM_AMOUNT: %s %s"
              % (claims[0].requested, type(claims[0].requested).__name__))

    from brainfreeze.money import usd
    print("MONEY: %s" % usd("31.50"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
