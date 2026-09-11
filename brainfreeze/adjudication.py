"""Adjudication: what a claim is worth, and whether it is paid.

Four rules, in order: whether the policy was in force at all, the annual cap,
the per-incident coverage limit, then the deductible. Nothing here is random -- a claimant is entitled to a reason
that follows from what they told us, and an agent asked "why was CLM-000123
turned down?" has to be able to answer it.

Between them those rules produce five refusals, and every `Decision` names
which one bound twice over: `reason` in English for the claimant, and `rule`
as a fixed identifier for whoever has to check rather than paraphrase. Absence
of cover splits into two of the five -- a lapse and an episode outside the
term are different facts -- and the two money caps can both apply at once, in
which case the tighter one is reported, because that is the one that decided
the number.

The generator adds a small chance of a denial for an unmodelled reason
(paperwork, an exclusion) on top of these rules. That belongs to the
generator, not here: it makes the sample history look lived-in, and it is
exactly the part the app must not reproduce.
"""

from decimal import Decimal
from typing import NamedTuple, Optional

from .money import ZERO, round_cents, usd

#: Approved claims allowed per policy per year, on every plan.
ANNUAL_CLAIM_LIMIT = 4

#: Reasons this module can return.
REASON_ANNUAL_LIMIT = "Exceeded annual claim limit"
REASON_BELOW_DEDUCTIBLE = "Claim amount below deductible"
REASON_POLICY_LAPSED = "Policy lapsed"
#: Cover can also be absent because the episode happened before the policy was
#: sold or after its term ran out, which is not a lapse and must not say it is.
REASON_OUTSIDE_TERM = "Event outside policy term"
#: A per-incident limit low enough to leave nothing above the deductible. The
#: wording is deliberately not the generator's "Claim amount exceeds
#: per-incident coverage limit": that string is one of the unmodelled denials
#: in the committed data, and if these two collided, ten refusals no rule
#: produced would start counting as rule outcomes.
REASON_PER_INCIDENT_LIMIT = "Per-incident limit leaves nothing above the deductible"

#: The same five outcomes as identifiers rather than as English.
#:
#: `reason` is written for the claimant and may be reworded; these may not.
#: An agent asked "why was CLM-000123 turned down?" checks the identifier and
#: quotes the prose, instead of parsing the prose and guessing at the rule --
#: which is not hypothetical: a lapse and an out-of-term event were told apart
#: by hand until they were given separate wordings.
#:
#: Kebab-case, naming the constraint that bound rather than the sentence it
#: produced, and matching the parallel implementation's spelling exactly so
#: the two demos group the same book the same way.
RULE_ANNUAL_LIMIT = "annual-claim-count-cap"
RULE_BELOW_DEDUCTIBLE = "below-deductible"
RULE_OUTSIDE_TERM = "event-outside-term"
RULE_PER_INCIDENT_LIMIT = "per-incident-limit"
RULE_POLICY_LAPSED = "policy-lapsed"

#: Which prose came from which rule.
#:
#: This exists for the 2,172 claims committed before `rule` did: they stored a
#: sentence and nothing else, and this is the only way to read one as a rule.
#: New claims carry the identifier outright and should never come through here.
_RULE_BY_REASON = {
    REASON_ANNUAL_LIMIT: RULE_ANNUAL_LIMIT,
    REASON_BELOW_DEDUCTIBLE: RULE_BELOW_DEDUCTIBLE,
    REASON_OUTSIDE_TERM: RULE_OUTSIDE_TERM,
    REASON_PER_INCIDENT_LIMIT: RULE_PER_INCIDENT_LIMIT,
    REASON_POLICY_LAPSED: RULE_POLICY_LAPSED,
}


def rule_for_reason(reason: Optional[str]) -> Optional[str]:
    """The rule that wrote this sentence, or None if no rule did.

    Exact match, and None for anything else. The generator's unmodelled
    denials -- paperwork, an exclusion, a late filing -- are not rule
    outcomes, and one of them ("Claim amount exceeds per-incident coverage
    limit") reads almost exactly like a rule that exists. Guessing at it would
    be the paraphrasing this identifier was added to stop.

    One ambiguity is inherent and cannot be fixed here: the generator also
    picks the real `REASON_ANNUAL_LIMIT` wording for some of its unmodelled
    refusals, so a committed claim saying "Exceeded annual claim limit" is
    read as the cap whether or not the cap is what refused it. That is an
    argument for storing the rule at the source, not for weakening this.
    """
    if reason is None:
        return None
    return _RULE_BY_REASON.get(reason)


class Decision(NamedTuple):
    """The outcome of one claim."""

    status: str                      # "Approved" or "Denied"
    amount: Decimal                    # what is paid, 0.00 when denied
    reason: Optional[str]            # why, when denied
    assessed: Decimal                  # what the claim was worth before limits
    capped_by_limit: Decimal           # taken off by the per-incident limit
    deductible_applied: Decimal        # taken off by the deductible
    #: Which rule decided it, as a stable identifier; None when approved.
    #: Last, with a default, so every existing positional `Decision(...)` and
    #: every `status, amount, reason, ... = decision` still reads as it did.
    rule: Optional[str] = None

    @property
    def approved(self) -> bool:
        return self.status == "Approved"


#: The floor and ceiling on what one episode can be assessed at.
MIN_ASSESSED = usd("5.00")
MAX_ASSESSED = usd("200.00")


def assess_amount(pain_intensity: float, duration_sec: float,
                  jitter: float = 0.0) -> Decimal:
    """What an episode is worth, from its severity.

    The claimant never enters a figure -- this derives it, so two people who
    describe the same episode get the same number. `jitter` is the generator's
    hook for making the sample data less uniform; the app leaves it at zero.

    Severity is a measurement and stays a float; the money it implies is
    rounded to the cent exactly once, here, on the way out. That single
    boundary is the point -- past it nothing is a float, so nothing downstream
    can round the same figure a second, different way.
    """
    raw = 10 + pain_intensity * 6 + duration_sec / 20 + jitter
    assessed = round_cents(Decimal(str(raw)))
    return max(MIN_ASSESSED, min(MAX_ASSESSED, assessed))


def adjudicate(
    assessed: Decimal,
    coverage_limit_per_incident: Decimal,
    deductible_per_incident: Decimal,
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

    The returned `rule` is the identifier for whichever of the five refusals
    applied, and None on an approval, where nothing bound and there is nothing
    to name.
    """
    if not policy_in_force:
        reason = no_cover_reason or REASON_POLICY_LAPSED
        return Decision("Denied", ZERO, reason, assessed, ZERO, ZERO,
                        rule_for_reason(reason))

    if approved_claims_this_year >= annual_claim_limit:
        return Decision("Denied", ZERO, REASON_ANNUAL_LIMIT, assessed, ZERO,
                        ZERO, RULE_ANNUAL_LIMIT)

    limited = min(assessed, coverage_limit_per_incident)
    capped_by_limit = round_cents(assessed - limited)
    payable = max(ZERO, limited - deductible_per_incident)
    deductible_applied = round_cents(limited - payable)

    if payable <= 0:
        # Two caps applied and between them left nothing. Report the tighter
        # one, because that is the one that decided the number: compare what
        # each would have allowed on its own, not what each took off.
        #
        # It matters. A $100 episode on a $5 limit with a $10 deductible pays
        # nothing, and "claim amount below deductible" says something untrue
        # about a claim ten times the deductible -- the limit allowed $5 where
        # the deductible would have allowed $90. On the three shipped plans
        # the limit is far above the deductible, so this branch always lands
        # on the deductible and no committed refusal changes its wording.
        allowed_by_limit = limited
        allowed_by_deductible = max(ZERO, assessed - deductible_per_incident)
        if allowed_by_limit < allowed_by_deductible:
            reason, rule = REASON_PER_INCIDENT_LIMIT, RULE_PER_INCIDENT_LIMIT
        else:
            reason, rule = REASON_BELOW_DEDUCTIBLE, RULE_BELOW_DEDUCTIBLE
        return Decision("Denied", ZERO, reason, assessed,
                        capped_by_limit, deductible_applied, rule)

    return Decision("Approved", round_cents(payable), None, assessed,
                    capped_by_limit, deductible_applied, None)
