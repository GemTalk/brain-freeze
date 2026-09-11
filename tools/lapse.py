"""Lapse or reinstate one policy, from a session of its own, while the app serves.

    gemdb tools/lapse.py BF-100184                 # lapse it, as of yesterday
    gemdb tools/lapse.py BF-100184 --reinstate     # put it back
    gemdb tools/lapse.py BF-100184 --on 2027-01-31 # lapse it on a chosen date

This is the demo's central claim made watchable. Leave the web app running,
open the policy in a browser, run this in a terminal, and reload. The page
changes. No restart, no reload of the app, no polling, and **nothing here talks
to the app** -- this script does not know the app exists. Both processes are
looking at the same objects.

It is the counterpart to the notebook's refresh beat, on the surface an
evaluator is actually looking at.

WHY IT WORKS, AND WHY IT DID NOT

A GemStone session sees the repository as of its last transaction boundary, so
for most of this demo's life the app would NOT have noticed: it read the book
once at startup and served that view until it was restarted. The app now has
a `before_request` hook that commits and then refreshes, and this script is the
payoff for that fix rather than a feature of its own.

The order matters, and both halves are load-bearing: `refresh()` refuses while
a session holds uncommitted work, and under Grail merely running code leaves
some. `abort()` would take a new view too and is the wrong tool -- it discards
the session's compiled code, which for the app is its own handlers.

REVERSIBLE ON PURPOSE

Lapsing and reinstating are the same operation with a different argument, so
the change can be shown back and forth in front of an audience without
re-seeding between takes.
"""

import os
import sys
from datetime import date, timedelta

#: The repository, for the same reason and in the same way as every other
#: script in here -- see `seed.py`.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from brainfreeze.money import format_usd


def parse_date(text):
    year, month, day = (int(part) for part in text.split("-"))
    return date(year, month, day)


def describe(policy, today):
    """What the app's own screens would say about this policy right now."""
    in_force = policy.is_in_force_on(today)
    return "%-8s status=%-8s lapse=%-10s in force today=%s" % (
        policy.policy_id, policy.policy_status,
        policy.policy_lapse_date or "none", in_force)


def lapse():
    import gemdb

    args = sys.argv[1:]
    if not args:
        print(__doc__.split("\n\n")[1])
        return 2

    policy_id = args[0].upper()
    reinstate = "--reinstate" in args
    # Yesterday, not today. Cover runs to the lapse date INCLUSIVE -- someone
    # who lapses on the 12th is still covered for the treat they ate that
    # morning -- so lapsing as of today leaves the policy in force and the
    # demo shows a status change with no consequence. Yesterday ends cover,
    # so the claim screen refuses and says why, which is the point.
    when = date.today() - timedelta(days=1)
    if "--on" in args:
        when = parse_date(args[args.index("--on") + 1])

    # Commit first, then refresh: this session has compiled code of its own,
    # and refresh() refuses while anything is uncommitted. Same recipe the
    # notebook and the app use.
    gemdb.commit()
    gemdb.refresh()

    book = gemdb.root.get("brainfreeze")
    if book is None:
        print("Nothing is committed. Run `gemdb tools/seed.py` first.")
        return 2

    policy = book.policies.get(policy_id)
    if policy is None:
        print("%s is not in this book." % policy_id)
        return 2

    today = date.today()
    print("before   %s" % describe(policy, today))

    if reinstate:
        policy.policy_status = "Active"
        policy.policy_lapse_date = None
    else:
        policy.policy_status = "Lapsed"
        policy.policy_lapse_date = when

    gemdb.commit()

    print("after    %s" % describe(policy, today))
    print()
    print("  Committed. The running app sees this on its NEXT request -- it")
    print("  takes a new view per request, so no restart is needed.")
    print("    the policy page   /policies/%s" % policy_id)
    print("    filing a claim    %s"
          % ("allowed again" if reinstate else "now refused, and told why"))
    print("    paid to date      %s" % format_usd(policy.total_paid))
    return 0


if __name__ == "__main__":
    sys.exit(lapse())
