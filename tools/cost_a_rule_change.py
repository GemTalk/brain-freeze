"""What would a rule change move? Costed against the book, not estimated.

    python3 tools/cost_a_rule_change.py

Written for issue #48, which asks whether adopting an annual MONEY cap forces
the dataset to be regenerated. It re-adjudicates all 2,172 claims under a cap
of `multiple x per-incident limit`, with partial payment down to the remaining
cap, and reports what moves against today's cap of 4 approvals.

WHY A SCRIPT RATHER THAN AN ESTIMATE

Every book-wide aggregate in this repository is pinned somewhere -- loss ratio
by tier alone appears in two test modules, the README three times, the MCP
answers, the notebook and DEMO.md beat 8. So "a few claims would change" is
not a small answer: any payout change at all triggers a regeneration across
about thirty files. Knowing whether the number is 0 or 28 is the whole
decision, and only the book can say.

It reads the book and writes nothing.
"""

import os
import sys

#: The repository, for the same reason and in the same way as every other
#: script in here -- see `seed.py`.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _path in (REPO, os.path.join(REPO, "tools")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import seed
from brainfreeze import adjudication as adj
from brainfreeze.underwriting import COVERAGE_PLANS
from brainfreeze.money import ZERO

book = seed.load()

def claims_in_order(policy):
    rows = []
    for e in policy.events:
        if e.claim is not None:
            rows.append((e.event_date, e.claim))
    rows.sort(key=lambda r: r[0])
    return rows

def simulate(multiple):
    """Return (changed, denied_now_partial, approved_now_denied, money_delta)."""
    changed = newly_partial = newly_denied = 0
    delta = ZERO
    for policy in book:
        plan = COVERAGE_PLANS[policy.plan_name]
        cap = plan.coverage_limit_per_incident * multiple
        paid = ZERO
        for _, claim in claims_in_order(policy):
            was = claim.approved if claim.is_approved else ZERO
            if not claim.is_approved:
                continue                      # denials stay denied
            remaining = cap - paid
            if remaining <= ZERO:
                now = ZERO
                newly_denied += 1
            elif was > remaining:
                now = remaining
                newly_partial += 1
            else:
                now = was
            if now != was:
                changed += 1
                delta += (now - was)
            paid += now
    return changed, newly_partial, newly_denied, delta

total_claims = sum(len(claims_in_order(p)) for p in book)
approved = sum(1 for p in book for _, c in claims_in_order(p) if c.is_approved)
print("book: %d policies, %d claims, %d approved" % (len(book.policies), total_claims, approved))
print()
print("%-9s %-9s %-9s %-9s %s" % ("cap x", "changed", "partial", "denied", "payout delta"))
for m in (1, 2, 3, 4, 6):
    ch, pa, de, d = simulate(m)
    print("%-9s %-9d %-9d %-9d %s" % ("%dx" % m, ch, pa, de, d))
print()
print("today's cap is 4 APPROVALS, so the money equivalent is 4x the")
print("per-incident limit: Basic $100, Standard $240, Premium $600.")

print()
print("=== IF THE MONEY CAP REPLACES THE COUNT CAP ===")
print("Claims denied ONLY for the count cap become eligible again.")
count_denied = 0
for policy in book:
    for _, c in claims_in_order(policy):
        if (not c.is_approved) and getattr(c, "reason", None) == adj.REASON_ANNUAL_LIMIT:
            count_denied += 1
print("claims currently denied by the count cap: %d" % count_denied)
print()
print("%-9s %-14s %-14s %s" % ("cap x", "reinstated", "still denied", "payout delta"))
for m in (3, 4, 6):
    reinstated = 0
    still = 0
    delta = ZERO
    for policy in book:
        plan = COVERAGE_PLANS[policy.plan_name]
        cap = plan.coverage_limit_per_incident * m
        paid = ZERO
        for _, claim in claims_in_order(policy):
            eligible = claim.is_approved or (
                getattr(claim, "reason", None) == adj.REASON_ANNUAL_LIMIT)
            if not eligible:
                continue
            want = claim.approved if claim.is_approved else (
                min(claim.requested, plan.coverage_limit_per_incident)
                - plan.deductible_per_incident)
            if want < ZERO:
                want = ZERO
            remaining = cap - paid
            got = want if want <= remaining else (remaining if remaining > ZERO else ZERO)
            if not claim.is_approved:
                if got > ZERO:
                    reinstated += 1
                    delta += got
                else:
                    still += 1
            else:
                delta += (got - claim.approved)
            paid += got
    print("%-9s %-14d %-14d %s" % ("%dx" % m, reinstated, still, delta))
