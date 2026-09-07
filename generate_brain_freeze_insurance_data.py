"""
Synthetic "Brain Freeze Insurance" dataset generator.

Produces two linked CSVs for a fun insurance/risk-analytics demo aimed at
kids & teens:

  1. policyholders.csv - one row per policy (the "underwriting" table):
     demographics, risk classification, coverage plan, and premium.
  2. claims.csv - one row per cold-treat event during the policy period
     (the "claims/exposure" table): whether brain freeze occurred, claim
     details, and outcome. This includes non-claim events too, so you can
     compute real actuarial-style metrics (claim frequency, severity,
     loss ratio) rather than only looking at approved claims.

GROUNDING: this version is intentionally PLAYFUL, not clinically precise.
It's loosely inspired by real research on cold-stimulus headache (kids
get it a lot, migraine history and fast eating make it worse, etc.) but
effect sizes, dollar amounts, and risk scores are exaggerated/tuned for
demo drama rather than epidemiological accuracy. Treat every number here
as "for building a fun product demo," not a real actuarial filing.

Run: python3 generate_brain_freeze_insurance_data.py
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta

RNG = np.random.default_rng(20260828)

N_POLICIES = 900
EVENTS_PER_POLICY = (2, 9)  # cold-treat events during the ~1yr policy term
POLICY_TERM_MONTHS = 12

TRIGGER_TYPES = ["ice cream", "slushie", "popsicle", "iced soda", "smoothie", "cold plunge"]
# playful per-trigger risk multiplier (how likely this trigger is to cause brain freeze)
TRIGGER_RISK_MULT = {
    "ice cream": 1.3,
    "slushie": 1.6,
    "popsicle": 1.5,
    "iced soda": 0.8,
    "smoothie": 0.7,
    "cold plunge": 1.1,
}
TRIGGER_TEMP_RANGE_C = {
    "ice cream": (-15, -8),
    "slushie": (-6, -2),
    "popsicle": (-18, -10),
    "iced soda": (0, 4),
    "smoothie": (-2, 4),
    "cold plunge": (10, 18),
}

COVERAGE_PLANS = {
    # plan: (annual base premium $, per-incident coverage limit $, per-incident deductible $)
    "Basic": (45.0, 25.0, 10.0),
    "Standard": (90.0, 60.0, 5.0),
    "Premium": (180.0, 150.0, 0.0),
}

RISK_TIER_MULT = {"Low": 0.7, "Medium": 1.0, "High": 1.9}  # exaggerated on purpose

PAIN_LOCATIONS = ["forehead", "temple", "occipital", "whole head"]
PAIN_LOCATION_PROBS = [0.42, 0.33, 0.13, 0.12]

PAIN_QUALITIES = ["stabbing", "pulling", "dull/pressing"]
PAIN_QUALITY_PROBS = [0.52, 0.28, 0.20]

DENIAL_REASONS = [
    "Pre-existing headache condition exclusion",
    "Claim amount exceeds per-incident coverage limit",
    "Insufficient severity documented",
    "Filed outside claim window",
    "Exceeded annual claim limit",
]

ANNUAL_CLAIM_LIMIT = 4  # max approved claims per policy per year, playful cap


def random_dates_in_term(start, months, n):
    end = start + timedelta(days=30 * months)
    span = (end - start).days
    offsets = np.sort(RNG.integers(0, span, size=n))
    return [start + timedelta(days=int(o)) for o in offsets]


def make_policyholders(n):
    age = RNG.integers(5, 20, size=n)
    sex = RNG.choice(["F", "M", "Nonbinary/Other"], size=n, p=[0.485, 0.485, 0.03])
    migraine_history = RNG.random(n) < 0.10
    tth_history = (~migraine_history) & (RNG.random(n) < 0.20)
    typical_speed = RNG.choice(["slow", "moderate", "fast"], size=n, p=[0.28, 0.44, 0.28])
    favorite_trigger = RNG.choice(TRIGGER_TYPES, size=n)

    # underwriting risk score 0-100, playful/exaggerated weighting
    speed_pts = np.select(
        [typical_speed == "slow", typical_speed == "moderate", typical_speed == "fast"],
        [-8, 0, 18],
    )
    age_pts = np.where(age <= 9, 10, np.where(age >= 15, -6, 0))  # younger = eats recklessly
    trigger_pts = np.array([(TRIGGER_RISK_MULT[t] - 1) * 20 for t in favorite_trigger])

    base = RNG.normal(45, 15, size=n)
    risk_score = (
        base
        + np.where(migraine_history, 22, 0)
        + np.where(tth_history, 10, 0)
        + speed_pts
        + age_pts
        + trigger_pts
    )
    risk_score = np.clip(risk_score, 1, 100)

    risk_tier = np.select(
        [risk_score < 34, risk_score < 67],
        ["Low", "Medium"],
        default="High",
    )

    coverage_plan = RNG.choice(list(COVERAGE_PLANS.keys()), size=n, p=[0.45, 0.4, 0.15])

    annual_premiums = np.zeros(n)
    coverage_limits = np.zeros(n)
    deductibles = np.zeros(n)
    for i in range(n):
        base_prem, cov_limit, ded = COVERAGE_PLANS[coverage_plan[i]]
        tier_mult = RISK_TIER_MULT[risk_tier[i]]
        noise = RNG.normal(1.0, 0.05)
        annual_premiums[i] = round(base_prem * tier_mult * noise, 2)
        coverage_limits[i] = cov_limit
        deductibles[i] = ded

    start_dates = [date(2026, 1, 1) + timedelta(days=int(d)) for d in RNG.integers(0, 300, size=n)]

    policies = pd.DataFrame({
        "policy_id": [f"BF-{100000+i}" for i in range(n)],
        "age": age,
        "sex": sex,
        "migraine_history": migraine_history,
        "tension_type_headache_history": tth_history,
        "typical_consumption_speed": typical_speed,
        "favorite_trigger": favorite_trigger,
        "underwriting_risk_score": np.round(risk_score, 1),
        "risk_tier": risk_tier,
        "coverage_plan": coverage_plan,
        "coverage_limit_per_incident_usd": coverage_limits,
        "deductible_per_incident_usd": deductibles,
        "annual_premium_usd": annual_premiums,
        "monthly_premium_usd": np.round(annual_premiums / 12, 2),
        "policy_start_date": start_dates,
        "policy_term_months": POLICY_TERM_MONTHS,
        "policy_status": RNG.choice(["Active", "Active", "Active", "Lapsed"], size=n),
        "_risk_score_raw": risk_score,
    })
    return policies


def make_claims(policies):
    rows = []
    claim_counter = 0
    for _, pol in policies.iterrows():
        n_events = RNG.integers(EVENTS_PER_POLICY[0], EVENTS_PER_POLICY[1] + 1)
        event_dates = random_dates_in_term(pol["policy_start_date"], pol["policy_term_months"], n_events)
        approved_claims_this_year = 0

        for event_date in event_dates:
            trigger = RNG.choice(TRIGGER_TYPES)
            temp_lo, temp_hi = TRIGGER_TEMP_RANGE_C[trigger]
            item_temp_c = RNG.uniform(temp_lo, temp_hi)

            # event-level speed can differ from "typical" (kids don't always eat the same way)
            speed = RNG.choice(
                ["slow", "moderate", "fast"],
                p={"slow": [0.5, 0.35, 0.15], "moderate": [0.25, 0.5, 0.25], "fast": [0.15, 0.35, 0.5]}[
                    pol["typical_consumption_speed"]
                ],
            )
            speed_factor = {"slow": -0.15, "moderate": 0.0, "fast": 0.30}[speed]
            portion_ml = float(np.clip(RNG.normal(160, 65), 30, 420))
            temp_factor = -item_temp_c / 45  # colder = riskier, exaggerated vs. the research-grounded version
            trigger_factor = (TRIGGER_RISK_MULT[trigger] - 1) * 0.6

            # playful/exaggerated: personal risk score dominates, pushed harder than a
            # "research-grounded" model would justify
            logit = (
                -1.0
                + 3.2 * (pol["_risk_score_raw"] / 100)
                + speed_factor
                + temp_factor
                + trigger_factor
            )
            p_brain_freeze = 1 / (1 + np.exp(-4.5 * (logit - 0.35)))
            brain_freeze_occurred = RNG.random() < p_brain_freeze

            row = {
                "claim_id": None,
                "policy_id": pol["policy_id"],
                "event_date": event_date.isoformat(),
                "trigger_type": trigger,
                "item_temperature_c": round(item_temp_c, 1),
                "portion_size_ml": round(portion_ml, 0),
                "consumption_speed": speed,
                "brain_freeze_occurred": bool(brain_freeze_occurred),
            }

            onset_sec = duration_sec = pain_intensity = np.nan
            pain_location = pain_quality = None
            claim_filed = False
            claim_amount_requested = claim_amount_approved = 0.0
            claim_status = "Not Filed"
            denial_reason = None

            if brain_freeze_occurred:
                onset_sec = float(np.clip(RNG.lognormal(mean=np.log(30), sigma=0.6), 5, 300))
                # playful: duration tail runs a bit longer/more dramatic than clinical reports
                if RNG.random() < 0.8:
                    duration_sec = float(np.clip(RNG.lognormal(mean=np.log(22), sigma=0.65), 3, 120))
                else:
                    duration_sec = float(np.clip(RNG.normal(420, 180), 120, 900))

                intensity_mean = 5.2
                if pol["migraine_history"]:
                    intensity_mean = 7.0
                elif pol["tension_type_headache_history"]:
                    intensity_mean = 6.2
                pain_intensity = float(np.clip(RNG.normal(intensity_mean, 1.8), 0, 10))
                pain_location = RNG.choice(PAIN_LOCATIONS, p=PAIN_LOCATION_PROBS)
                pain_quality = RNG.choice(PAIN_QUALITIES, p=PAIN_QUALITY_PROBS)

                # claim propensity: more likely to file for worse episodes
                file_prob = np.clip(0.12 + pain_intensity / 14 + duration_sec / 1800, 0, 0.9)
                claim_filed = RNG.random() < file_prob

                if claim_filed:
                    claim_counter += 1
                    row["claim_id"] = f"CLM-{claim_counter:06d}"

                    # requested amount scales with severity, playful dollar range
                    claim_amount_requested = round(float(np.clip(
                        10 + pain_intensity * 6 + duration_sec / 20 + RNG.normal(0, 5), 5, 200
                    )), 2)

                    cov_limit = pol["coverage_limit_per_incident_usd"]
                    deductible = pol["deductible_per_incident_usd"]

                    if approved_claims_this_year >= ANNUAL_CLAIM_LIMIT:
                        claim_status = "Denied"
                        denial_reason = "Exceeded annual claim limit"
                    elif RNG.random() < 0.04:
                        claim_status = "Denied"
                        denial_reason = RNG.choice(DENIAL_REASONS)
                    else:
                        payable = max(0.0, min(claim_amount_requested, cov_limit) - deductible)
                        claim_amount_approved = round(payable, 2)
                        claim_status = "Approved" if payable > 0 else "Denied"
                        if payable <= 0:
                            denial_reason = "Claim amount below deductible"
                        else:
                            approved_claims_this_year += 1

            row.update({
                "onset_time_sec": round(onset_sec, 1) if not np.isnan(onset_sec) else onset_sec,
                "duration_sec": round(duration_sec, 1) if not np.isnan(duration_sec) else duration_sec,
                "pain_intensity_nrs": round(pain_intensity, 1) if not np.isnan(pain_intensity) else pain_intensity,
                "pain_location": pain_location,
                "pain_quality": pain_quality,
                "claim_filed": bool(claim_filed),
                "claim_amount_requested_usd": claim_amount_requested,
                "claim_amount_approved_usd": claim_amount_approved,
                "claim_status": claim_status,
                "denial_reason": denial_reason,
            })
            rows.append(row)

    claims = pd.DataFrame(rows)
    # give every row a stable event id even when no claim was filed
    claims.insert(0, "event_id", [f"EVT-{i+1:06d}" for i in range(len(claims))])
    return claims


if __name__ == "__main__":
    policies = make_policyholders(N_POLICIES)
    claims = make_claims(policies)

    policies_out = policies.drop(columns=["_risk_score_raw"])
    policies_out.to_csv("policyholders.csv", index=False)
    claims.to_csv("claims.csv", index=False)

    print(f"Wrote {len(policies_out):,} policyholders -> policyholders.csv")
    print(f"Wrote {len(claims):,} events -> claims.csv")

    print("\nRisk tier distribution:")
    print(policies_out["risk_tier"].value_counts())

    print("\nAvg annual premium by risk tier x coverage plan:")
    print(policies_out.pivot_table(
        index="risk_tier", columns="coverage_plan", values="annual_premium_usd", aggfunc="mean"
    ).round(2))

    print("\nOverall brain-freeze incidence rate:", round(claims["brain_freeze_occurred"].mean() * 100, 1), "%")
    print("Claim filing rate (given brain freeze):",
          round(claims.loc[claims["brain_freeze_occurred"], "claim_filed"].mean() * 100, 1), "%")
    print("Claim status breakdown:")
    print(claims.loc[claims["claim_filed"], "claim_status"].value_counts())

    total_premium = policies_out["annual_premium_usd"].sum()
    total_approved = claims["claim_amount_approved_usd"].sum()
    print(f"\nTotal annual premium collected: ${total_premium:,.2f}")
    print(f"Total approved claims paid out: ${total_approved:,.2f}")
    print(f"Implied loss ratio (claims paid / premium): {total_approved / total_premium:.2f}")
