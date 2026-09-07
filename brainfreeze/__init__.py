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
from .adjudication import (
    ANNUAL_CLAIM_LIMIT,
    Decision,
    adjudicate,
    assess_amount,
)

__all__ = [
    "COVERAGE_PLANS", "RISK_TIER_MULT", "TRIGGER_RISK_MULT", "TRIGGER_TYPES",
    "BASE_RISK", "Plan", "Quote", "annual_premium", "quote", "risk_score",
    "risk_tier", "score_breakdown", "ANNUAL_CLAIM_LIMIT", "Decision",
    "adjudicate", "assess_amount",
]
