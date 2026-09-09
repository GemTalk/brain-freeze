"""Read the whole book back out of the database, from a session of its own.

    gemdb verify_book.py                 # the whole book
    gemdb verify_book.py BF-100539       # ...and one policy in full

This loads nothing. It opens `gemdb.root["brainfreeze"]` and reports what is
there, which is the demo's central claim reduced to one command: **the objects
were never anywhere but the database.** There is no load step because there
was no save step -- only `commit()`.

WHY THIS IS NOT THE TEST SUITE

`tests/test_seed.py` builds a book from `data/*.csv` and asserts against it.
That proves the loader agrees with the files; it cannot prove anything about
what is committed, because it never reads the committed graph. `seed.py
--dry-run` reads the CSVs and never opens the database at all.

This is the other half. Stop the app, stop the stone, start it again, run this,
and the same numbers come back -- from a process that has never seen a CSV.
Against a test suite that could be reading its own fixtures, that is the
stronger argument.

It also doubles as the "did the demo work" smoke test, which is what it is
mostly used for.

WHAT IT CHECKS AGAINST

The figures `tests/test_seed.py` pins, listed in EXPECTED below. A freshly
seeded book matches all of them. A book the app has been driven against will
not -- filing a claim adds a policy or an event on purpose -- so a mismatch is
reported as drift rather than failure, with the exit code saying which. Re-run
`gemdb seed.py` to get back to the baseline.
"""

import sys

from brainfreeze import analysis
from brainfreeze.money import format_usd, usd

#: What a freshly seeded book holds. These are the same figures
#: `tests/test_seed.py` pins and `docs/mcp-questions.md` promises.
EXPECTED = {
    "policies": 900,
    "events": 4993,
    "claims": 2172,
    "approved": 1691,
    "premium": usd("92081.22"),
    "paid": usd("54671.44"),
}

EXEMPLAR = "BF-100539"


def show_book(book):
    summary = analysis.book_summary(book)
    drift = []

    print("  %-22s %s" % ("policies", summary["policies"]))
    print("  %-22s %s" % ("events", summary["events"]))
    print("  %-22s %s of them a brain freeze" % ("", summary["brain_freeze_events"]))
    print("  %-22s %s" % ("claims", summary["claims"]))
    print("  %-22s %s" % ("approved", summary["approved"]))
    print("  %-22s %s" % ("premium collected", format_usd(summary["premium"])))
    print("  %-22s %s" % ("paid out", format_usd(summary["paid"])))
    print("  %-22s %s" % ("loss ratio", summary["loss_ratio"]))

    for name, want in sorted(EXPECTED.items()):
        got = summary[name]
        if got != want:
            drift.append((name, want, got))

    print()
    # `% (x,)`, not `% x`: a dict on the right of `%` is read as a mapping for
    # named substitutions, and `"%s" % {"Low": 0.4}` is "format requires a
    # mapping" rather than the dict.
    print("  loss ratio by tier     %s" % (analysis.loss_ratio_by_tier(book),))
    print("  least profitable plan  %s" % (analysis.least_profitable_plan(book),))
    return drift


def show_policy(book, policy_id):
    policy = book.policies.get(policy_id)
    if policy is None:
        print("\n  %s is not in this book." % policy_id)
        return
    print("\n  %s -- %s, %s, %s" % (policy_id, policy.plan_name,
                                    policy.risk_tier, policy.policy_status))
    print("    %-20s %s a year, %s a month" % (
        "premium", format_usd(policy.annual_premium),
        format_usd(policy.monthly_premium)))
    print("    %-20s %s an episode, %s deductible" % (
        "cover", format_usd(policy.coverage_limit),
        format_usd(policy.deductible)))
    print("    %-20s %s .. %s%s" % (
        "term", policy.policy_start_date, policy.policy_end_date,
        ", lapsed %s" % policy.policy_lapse_date if policy.policy_lapse_date else ""))
    print("    %-20s %s paid over %d events, %d claims"
          % ("history", format_usd(policy.total_paid),
             len(policy.events), len(policy.claims)))
    print()
    for event in policy.events:
        claim = event.claim
        if claim is None:
            print("      %s  no claim" % event.event_date)
        else:
            print("      %s  %-11s %-10s %s"
                  % (event.event_date, claim.claim_id, claim.status,
                     format_usd(claim.approved) if claim.is_approved else claim.reason))


def verify_book():
    import gemdb

    print("Reading gemdb.root[\"brainfreeze\"] -- nothing is loaded here.")
    print("-" * 70)

    book = gemdb.root.get("brainfreeze")
    if book is None:
        print("  NOTHING IS COMMITTED. Run `gemdb seed.py` first.")
        return 2

    print("  %-22s %s" % ("the root holds", type(book).__name__))
    drift = show_book(book)

    for policy_id in (sys.argv[1:] or [EXEMPLAR]):
        show_policy(book, policy_id)

    print()
    if not drift:
        print("  Every figure matches a freshly seeded book.")
        return 0
    print("  DRIFT from the seeded baseline -- expected if the app has been")
    print("  driven since the last `gemdb seed.py`:")
    for name, want, got in drift:
        print("    %-12s expected %-12s got %s" % (name, want, got))
    return 1


if __name__ == "__main__":
    sys.exit(verify_book())
