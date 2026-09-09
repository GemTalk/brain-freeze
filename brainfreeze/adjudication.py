"""Adjudication: what a claim is worth, and whether it is paid.

Four rules, in order: whether the policy was in force at all, the annual cap,
the per-incident coverage limit, then the deductible. Nothing here is random -- a claimant is entitled to a reason
that follows from what they told us, and an agent asked "why was CLM-000123
turned down?" has to be able to answer it.

The generator adds a small chance of a denial for an unmodelled reason
(paperwork, an exclusion) on top of these rules. That belongs to the
generator, not here: it makes the sample history look lived-in, and it is
exactly the part the app must not reproduce.
"""

from typing import NamedTuple, Optional

#: Approved claims allowed per policy per year, on every plan.
ANNUAL_CLAIM_LIMIT = 4

#: Reasons this module can return.
REASON_ANNUAL_LIMIT = "Exceeded annual claim limit"
REASON_BELOW_DEDUCTIBLE = "Claim amount below deductible"
REASON_POLICY_LAPSED = "Policy lapsed"
#: Cover can also be absent because the episode happened before the policy was
#: sold or after its term ran out, which is not a lapse and must not say it is.
REASON_OUTSIDE_TERM = "Event outside policy term"


class Decision(NamedTuple):
    """The outcome of one claim."""

    status: str                      # "Approved" or "Denied"
    amount: float                    # what is paid, 0.00 when denied
    reason: Optional[str]            # why, when denied
    assessed: float                  # what the claim was worth before limits
    capped_by_limit: float           # taken off by the per-incident limit
    deductible_applied: float        # taken off by the deductible

    @property
    def approved(self) -> bool:
        return self.status == "Approved"


def assess_amount(pain_intensity: float, duration_sec: float, jitter: float = 0.0) -> float:
    """What an episode is worth, from its severity.

    The claimant never enters a figure -- this derives it, so two people who
    describe the same episode get the same number. `jitter` is the generator's
    hook for making the sample data less uniform; the app leaves it at zero.
    """
    raw = 10 + pain_intensity * 6 + duration_sec / 20 + jitter
    return round(max(5.0, min(200.0, raw)), 2)


def adjudicate(
    assessed: float,
    coverage_limit_per_incident: float,
    deductible_per_incident: float,
    approved_claims_this_year: int,
    annual_claim_limit: int = ANNUAL_CLAIM_LIMIT,
    policy_in_force: bool = True,
    no_cover_reason: Optional[str] = None,
) -> Decision:
    """Run one claim through the rules and say what happens.

    Cover is checked before anything else: a claim on a policy that had already
    lapsed is refused for that reason and not for whatever else would also have
    refused it. The annual cap is next and short-circuits the same way -- a
    policy that has used its four approvals is turned down whatever the episode
    was worth.

    `policy_in_force` defaults to True so that a caller who has no lapse to
    consider reads exactly as before. `no_cover_reason` is which absence of
    cover the caller found -- a lapse, or an episode outside the policy term.
    It defaults to the lapse, because that is what every refusal in the sample
    data says and what callers written before the term was checked meant.
    """
    if not policy_in_force:
        return Decision("Denied", 0.0, no_cover_reason or REASON_POLICY_LAPSED,
                        assessed, 0.0, 0.0)

    if approved_claims_this_year >= annual_claim_limit:
        return Decision("Denied", 0.0, REASON_ANNUAL_LIMIT, assessed, 0.0, 0.0)

    limited = min(assessed, coverage_limit_per_incident)
    capped_by_limit = round(assessed - limited, 2)
    payable = max(0.0, limited - deductible_per_incident)
    deductible_applied = round(limited - payable, 2)

    if payable <= 0:
        return Decision("Denied", 0.0, REASON_BELOW_DEDUCTIBLE, assessed,
                        capped_by_limit, deductible_applied)

    return Decision("Approved", round(payable, 2), None, assessed,
                    capped_by_limit, deductible_applied)
