"""Named questions about a book of business.

The MCP surface GemDB offers is code-level, not data-level: `eval_python`,
`execute_code`, `commit`, browsing and search. There is no tool that knows
what a policyholder is. An agent answers "loss ratio by risk tier" by writing
Python and running it inside the database -- which is the better story, and it
needs help, or the agent derives the aggregation itself and gets the
denominator wrong in a way nobody notices.

So these are the questions the demo promises will work. An agent composes
them; it does not reinvent them. They are also what the notebook's cells are
made of.

Standard library only, and not even `collections` -- like the rest of the
package this is compiled and run inside the database. Nothing here decides
anything: the rules live in `underwriting` and `adjudication`, and these only
count what those two produced.

Rates are `None` rather than 0.0 when there is nothing to divide by. An empty
book has no approval rate; saying 0.0 would claim every claim was refused,
which is a different fact and a wrong one.

Money is `decimal.Decimal` throughout -- see `brainfreeze.money`. Sums here
are exact; only the ratios become floats, and only on the way out.
"""

from .money import ZERO, round_half_up


def _rounded(value, places=3):
    """Half-up, and a float on the way out.

    Bare `round()` is half-up inside the database and banker's outside it, so
    a published ratio could differ between two surfaces of the same demo. A
    ratio is not money and stays a float; only the rounding rule is borrowed.
    """
    if value is None:
        return None
    return float(round_half_up(value, places))


def book_summary(book):
    """The figures you would put at the top of a report."""
    events = book.events
    claims = book.claims
    return {
        "policies": len(book),
        "events": len(events),
        "brain_freeze_events": len([e for e in events if e.brain_freeze]),
        "claims": len(claims),
        "approved": len([c for c in claims if c.is_approved]),
        "premium": book.total_premium,
        "paid": book.total_paid,
        "loss_ratio": book.loss_ratio,
    }


def _loss_ratio_grouped(book, key):
    """Premium and payout summed per group, then divided. Not an average of
    ratios -- that would weight a $45 policy the same as a $342 one."""
    premium = {}
    paid = {}
    for policyholder in book:
        group = key(policyholder)
        premium[group] = premium.get(group, ZERO) + policyholder.annual_premium
        paid[group] = paid.get(group, ZERO) + policyholder.total_paid
    return {group: _rounded(paid[group] / total)
            for group, total in premium.items() if total}


def loss_ratio_by_tier(book):
    """Paid over premium, per risk band.

    The answer is worth looking at twice: the tier loading over-prices High,
    so the riskiest customers are the most profitable.
    """
    return _loss_ratio_grouped(book, lambda p: p.risk_tier)


def loss_ratio_by_plan(book):
    """Paid over premium, per coverage plan."""
    return _loss_ratio_grouped(book, lambda p: p.plan_name)


def least_profitable_plan(book):
    """The plan with the highest loss ratio, as (name, ratio), or None."""
    ratios = loss_ratio_by_plan(book)
    if not ratios:
        return None
    name = sorted(ratios, key=lambda k: (-ratios[k], k))[0]
    return (name, ratios[name])


def claim_approval_rate(book):
    """Share of filed claims that were paid, or None if none were filed."""
    claims = book.claims
    if not claims:
        return None
    return _rounded(len([c for c in claims if c.is_approved]) / len(claims), 4)


def denial_reasons(book):
    """Every reason a claim was refused, commonest first, as (reason, count).

    Ties are broken alphabetically so the order does not wobble between runs.
    """
    counts = {}
    for claim in book.claims:
        if not claim.is_approved:
            reason = claim.reason or "Unrecorded"
            counts[reason] = counts.get(reason, 0) + 1
    return [(reason, counts[reason])
            for reason in sorted(counts, key=lambda r: (-counts[r], r))]


def top_n_by_expected_claims(book, n=10, min_events=5):
    """Policies most likely to claim, by approvals per cold treat.

    `min_events` is the whole point. A policy with two treats and two approved
    claims scores 1.0 and tells you nothing; without a floor the ranking is a
    list of the shortest histories in the book. Five is low enough to keep
    most of the book and high enough that the rate means something -- say
    which floor you used when quoting the answer.

    Returns (policyholder, rate) pairs, highest first, ties by policy id.
    """
    scored = [(p, _rounded(len(p.approved_claims) / len(p.events), 4))
              for p in book
              if len(p.events) >= min_events]
    scored.sort(key=lambda pair: (-pair[1], pair[0].policy_id))
    return scored[:n]


def top_n_by_loss_ratio(book, n=10):
    """Policies costing most relative to what they pay, highest first.

    This is the underpriced end of the book -- above 1.0 the policy has cost
    more than it brought in. Returns (policyholder, ratio) pairs, ties by
    policy id.
    """
    scored = [(p, _rounded(p.total_paid / p.annual_premium))
              for p in book if p.annual_premium]
    scored.sort(key=lambda pair: (-pair[1], pair[0].policy_id))
    return scored[:n]
