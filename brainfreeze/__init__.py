"""Brain Freeze Insurance: the underwriting and claims model.

Pure Python, standard library only, one policyholder or one claim at a time.
Nothing here imports numpy or pandas, so the same functions run under CPython
(where the dataset generator uses them) and inside the database (where the web
app uses them). That is the whole point of the package: the quote a customer
sees and the quote that produced the sample data come from one piece of code.
"""

from .underwriting import (
    COVERAGE_PLANS,
    RISK_TIER_MULT,
    TRIGGER_RISK_MULT,
    CONSUMPTION_SPEEDS,
    TRIGGER_TYPES,
    BASE_RISK,
    Plan,
    Quote,
    annual_premium,
    quote,
    risk_score,
    risk_tier,
    score_breakdown,
)
from .model import (
    Book,
    Claim,
    Event,
    Policyholder,
    SavedQuote,
)
from .analysis import (
    book_summary,
    claim_approval_rate,
    denial_reasons,
    denial_rules,
    least_profitable_plan,
    loss_ratio_by_plan,
    loss_ratio_by_tier,
    top_n_by_expected_claims,
    top_n_by_loss_ratio,
)
from .adjudication import (
    ANNUAL_CLAIM_LIMIT,
    REASON_ANNUAL_LIMIT,
    REASON_BELOW_DEDUCTIBLE,
    REASON_OUTSIDE_TERM,
    REASON_PER_INCIDENT_LIMIT,
    REASON_POLICY_LAPSED,
    RULE_ANNUAL_LIMIT,
    RULE_BELOW_DEDUCTIBLE,
    RULE_OUTSIDE_TERM,
    RULE_PER_INCIDENT_LIMIT,
    RULE_POLICY_LAPSED,
    Decision,
    adjudicate,
    assess_amount,
    rule_for_reason,
)

#: The package's public surface, grouped exactly as the imports above are.
#: `tests/test_brainfreeze.py` requires the two to agree name for name, so a
#: function added to a submodule and imported here cannot quietly fail to be
#: published -- which is the one way a hand-kept list of names goes wrong.
__all__ = [
    # underwriting: what a policy costs and why
    "BASE_RISK", "CONSUMPTION_SPEEDS", "COVERAGE_PLANS", "RISK_TIER_MULT",
    "TRIGGER_RISK_MULT", "TRIGGER_TYPES",
    "Plan", "Quote",
    "annual_premium", "quote", "risk_score", "risk_tier", "score_breakdown",

    # model: the objects that live in the database
    "Book", "Claim", "Event", "Policyholder", "SavedQuote",

    # analysis: questions asked of a whole book
    "book_summary", "claim_approval_rate", "denial_reasons", "denial_rules",
    "least_profitable_plan", "loss_ratio_by_plan", "loss_ratio_by_tier",
    "top_n_by_expected_claims", "top_n_by_loss_ratio",

    # adjudication: whether a claim is paid, and the rule that decided
    "ANNUAL_CLAIM_LIMIT",
    "REASON_ANNUAL_LIMIT", "REASON_BELOW_DEDUCTIBLE", "REASON_OUTSIDE_TERM",
    "REASON_PER_INCIDENT_LIMIT", "REASON_POLICY_LAPSED",
    "RULE_ANNUAL_LIMIT", "RULE_BELOW_DEDUCTIBLE", "RULE_OUTSIDE_TERM",
    "RULE_PER_INCIDENT_LIMIT", "RULE_POLICY_LAPSED",
    "Decision", "adjudicate", "assess_amount", "rule_for_reason",
]
