"""Underwriting: what a policyholder's risk is, and what that costs.

Deliberately playful rather than actuarial -- see the generator's docstring.
The weights below are the ones the sample dataset was built with, so a quote
computed here for a given set of answers is the quote that would have produced
that row.

One wrinkle worth naming. The generator draws each policyholder's starting
point from a normal distribution rather than using BASE_RISK, and does not
record what it drew. So a score already in the dataset cannot be reproduced
from its policyholder's answers -- the unobservable part is gone. `base` is a
parameter here rather than a constant so that the generator can pass what it
drew while the app passes BASE_RISK; closing the gap properly means recording
the drawn base alongside the score.
"""

from decimal import Decimal
from typing import NamedTuple

from .money import round_cents, usd

#: Everyone starts here before their answers move them.
BASE_RISK = 45.0

TRIGGER_TYPES = ["ice cream", "slushie", "popsicle", "iced soda", "smoothie", "cold plunge"]

#: How likely each cold treat is to bring on brain freeze, relative to average.
TRIGGER_RISK_MULT = {
    "ice cream": 1.3,
    "slushie": 1.6,
    "popsicle": 1.5,
    "iced soda": 0.8,
    "smoothie": 0.7,
    "cold plunge": 1.1,
}

CONSUMPTION_SPEEDS = ["slow", "moderate", "fast"]

#: Points added to the risk score for how fast the person eats.
SPEED_POINTS = {"slow": -8.0, "moderate": 0.0, "fast": 18.0}

#: Points for a migraine or tension-type-headache diagnosis.
MIGRAINE_POINTS = 22.0
TTH_POINTS = 10.0

#: Younger children eat more recklessly; teenagers have learned.
YOUNG_AGE = 9
YOUNG_AGE_POINTS = 10.0
OLDER_AGE = 15
OLDER_AGE_POINTS = -6.0

#: Score bands. Below LOW_MAX is Low, below MEDIUM_MAX is Medium, else High.
LOW_MAX = 34.0
MEDIUM_MAX = 67.0

#: Tier loading on the base premium. Exaggerated on purpose.
#: Decimal, not float, because these multiply money -- one float in the chain
#: is enough to put the answer back on the wrong side of a half cent.
RISK_TIER_MULT = {"Low": usd("0.7"), "Medium": usd("1.0"), "High": usd("1.9")}


class Plan(NamedTuple):
    """A coverage plan's fixed terms, before any tier loading."""

    base_annual_premium: Decimal
    coverage_limit_per_incident: Decimal
    deductible_per_incident: Decimal


#: The three plans on offer.
COVERAGE_PLANS = {
    "Basic": Plan(usd("45.00"), usd("25.00"), usd("10.00")),
    "Standard": Plan(usd("90.00"), usd("60.00"), usd("5.00")),
    "Premium": Plan(usd("180.00"), usd("150.00"), usd("0.00")),
}


def age_points(age: int) -> float:
    """Risk points for age alone."""
    if age <= YOUNG_AGE:
        return YOUNG_AGE_POINTS
    if age >= OLDER_AGE:
        return OLDER_AGE_POINTS
    return 0.0


def trigger_points(favourite_trigger: str) -> float:
    """Risk points for a favourite cold treat, from its risk multiplier."""
    return (TRIGGER_RISK_MULT[favourite_trigger] - 1) * 20


def risk_score(
    age: int,
    migraine_history: bool,
    tension_type_headache_history: bool,
    typical_consumption_speed: str,
    favourite_trigger: str,
    base: float = BASE_RISK,
) -> float:
    """The underwriting score, 1 to 100, for one applicant.

    `base` exists for the generator, which samples a starting point per
    policyholder instead of using BASE_RISK. Everything else is a lookup.
    """
    score = (
        base
        + (MIGRAINE_POINTS if migraine_history else 0.0)
        + (TTH_POINTS if tension_type_headache_history else 0.0)
        + SPEED_POINTS[typical_consumption_speed]
        + age_points(age)
        + trigger_points(favourite_trigger)
    )
    return max(1.0, min(100.0, score))


def risk_tier(score: float) -> str:
    """Which band a score falls in: Low, Medium or High."""
    if score < LOW_MAX:
        return "Low"
    if score < MEDIUM_MAX:
        return "Medium"
    return "High"


def annual_premium(plan_name: str, tier: str) -> Decimal:
    """What a plan costs a year for a given tier, before any noise.

    Exact: `45.00 * 0.7` is `31.50` here and not `31.499999999999996`.
    """
    return COVERAGE_PLANS[plan_name].base_annual_premium * RISK_TIER_MULT[tier]


def score_breakdown(
    age: int,
    migraine_history: bool,
    tension_type_headache_history: bool,
    typical_consumption_speed: str,
    favourite_trigger: str,
    base: float = BASE_RISK,
) -> list:
    """The score as a list of (label, points) so a quote can explain itself.

    The app shows this; it is also what an agent needs to answer "why is this
    policy High tier?" without guessing.
    """
    rows = [("Everyone starts here", base)]
    if migraine_history:
        rows.append(("Migraine diagnosis", MIGRAINE_POINTS))
    if tension_type_headache_history:
        rows.append(("Tension-headache diagnosis", TTH_POINTS))
    speed = SPEED_POINTS[typical_consumption_speed]
    rows.append(("Eats %s" % {"slow": "slowly", "moderate": "at a normal pace",
                              "fast": "very fast"}[typical_consumption_speed], speed))
    rows.append(("Age %d" % age, age_points(age)))
    rows.append(("Favourite treat: %s" % favourite_trigger, trigger_points(favourite_trigger)))
    return rows


class Quote(NamedTuple):
    """What the quote flow hands back: one score, one tier, three prices.

    `risk_tier` rather than `tier`, because a `Policyholder` spells it that
    way and the two are the same band computed by the same function.
    """

    score: float
    risk_tier: str
    breakdown: list
    plans: dict  # plan name -> {"annual", "monthly", "limit", "deductible"}


def quote(
    age: int,
    migraine_history: bool,
    tension_type_headache_history: bool,
    typical_consumption_speed: str,
    favourite_trigger: str,
    base: float = BASE_RISK,
) -> Quote:
    """Price all three plans for one applicant."""
    score = risk_score(age, migraine_history, tension_type_headache_history,
                       typical_consumption_speed, favourite_trigger, base)
    band = risk_tier(score)
    plans = {}
    for name, plan in COVERAGE_PLANS.items():
        annual = round_cents(annual_premium(name, band))
        plans[name] = {
            "annual": annual,
            "monthly": round_cents(annual / 12),
            "limit": plan.coverage_limit_per_incident,
            "deductible": plan.deductible_per_incident,
        }
    breakdown = score_breakdown(age, migraine_history, tension_type_headache_history,
                                typical_consumption_speed, favourite_trigger, base)
    return Quote(round(score, 1), band, breakdown, plans)
