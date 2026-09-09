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
)
from .analysis import (
    book_summary,
    claim_approval_rate,
    denial_reasons,
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
    REASON_POLICY_LAPSED,
    Decision,
    adjudicate,
    assess_amount,
)

__all__ = [
    "COVERAGE_PLANS", "RISK_TIER_MULT", "TRIGGER_RISK_MULT", "TRIGGER_TYPES",
    "BASE_RISK", "Plan", "Quote", "annual_premium", "quote", "risk_score",
    "risk_tier", "score_breakdown", "ANNUAL_CLAIM_LIMIT", "Decision",
    "REASON_ANNUAL_LIMIT", "REASON_BELOW_DEDUCTIBLE", "REASON_OUTSIDE_TERM",
    "REASON_POLICY_LAPSED",
    "adjudicate", "assess_amount",
    "Book", "Claim", "Event", "Policyholder",
    "book_summary", "claim_approval_rate", "denial_reasons",
    "least_profitable_plan", "loss_ratio_by_plan", "loss_ratio_by_tier",
    "top_n_by_expected_claims", "top_n_by_loss_ratio",
]
