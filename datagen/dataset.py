"""Synthetic "Brain Freeze Insurance" dataset generator.

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

WHAT THIS FILE DOES AND DOES NOT OWN. The underwriting weights, the tier
bands, the plan terms and the claim rules live in the `brainfreeze` package,
which is pure standard-library Python so the web app can import the same
functions inside the database. This file owns the *sampling* -- how many
policyholders, how their answers are drawn, how much noise sits on a premium,
and the small chance of a denial for a reason the rules do not model. Keeping
those apart is what stops the app's quote and the sample data from drifting
into disagreement.

Run: python3 -m datagen
"""

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from brainfreeze import (
    ANNUAL_CLAIM_LIMIT,
    COVERAGE_PLANS,
    TRIGGER_RISK_MULT,
    TRIGGER_TYPES,
    adjudicate,
    annual_premium,
    assess_amount,
    risk_score,
    risk_tier,
)

#: Where the CSVs go: `data/` at the repo root, not the working directory.
#: seed.py and the tests read them from there, so writing them anywhere else
#: produces a dataset nothing loads.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
POLICYHOLDERS_CSV = DATA_DIR / "policyholders.csv"
CLAIMS_CSV = DATA_DIR / "claims.csv"

RNG = np.random.default_rng(20260828)

N_POLICIES = 900
EVENTS_PER_POLICY = (2, 9)  # cold-treat events during the ~1yr policy term
POLICY_TERM_MONTHS = 12

#: The earliest day of the term a policy may lapse on.
LAPSE_EARLIEST_DAY = 30

#: Where each policyholder's score starts, before their answers move it.
#: This is sampled per policyholder and written out as `underwriting_base`,
#: which is what makes a score in the dataset reproducible: the app scores an
#: applicant's answers from the same starting point, so someone matching an
#: existing row lands in that row's tier. It is written at full precision on
#: purpose -- the score column is derived from it, and rounding here would
#: let the two disagree in the last decimal.
BASE_RISK_MEAN, BASE_RISK_SD = 45, 15

#: Multiplicative jitter on a premium, so the sample book is not uniform.
PREMIUM_NOISE_SD = 0.05

#: Chance a claim is turned down for something the rules do not model.
UNMODELLED_DENIAL_RATE = 0.04

TRIGGER_TEMP_RANGE_C = {
    "ice cream": (-15, -8),
    "slushie": (-6, -2),
    "popsicle": (-18, -10),
    "iced soda": (0, 4),
    "smoothie": (-2, 4),
    "cold plunge": (10, 18),
}

PAIN_LOCATIONS = ["forehead", "temple", "occipital", "whole head"]
PAIN_LOCATION_PROBS = [0.42, 0.33, 0.13, 0.12]

PAIN_QUALITIES = ["stabbing", "pulling", "dull/pressing"]
PAIN_QUALITY_PROBS = [0.52, 0.28, 0.20]

#: Reasons only the generator can produce -- see UNMODELLED_DENIAL_RATE.
DENIAL_REASONS = [
    "Pre-existing headache condition exclusion",
    "Claim amount exceeds per-incident coverage limit",
    "Insufficient severity documented",
    "Filed outside claim window",
    "Exceeded annual claim limit",
]


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

    # Each policyholder's starting point. Sampled here, scored in brainfreeze.
    base = RNG.normal(BASE_RISK_MEAN, BASE_RISK_SD, size=n)
    scores = np.array([
        risk_score(int(age[i]), bool(migraine_history[i]), bool(tth_history[i]),
                   str(typical_speed[i]), str(favorite_trigger[i]), float(base[i]))
        for i in range(n)
    ])
    tiers = np.array([risk_tier(float(s)) for s in scores])

    coverage_plan = RNG.choice(list(COVERAGE_PLANS.keys()), size=n, p=[0.45, 0.4, 0.15])

    annual_premiums = np.zeros(n)
    coverage_limits = np.zeros(n)
    deductibles = np.zeros(n)
    for i in range(n):
        plan = COVERAGE_PLANS[coverage_plan[i]]
        noise = RNG.normal(1.0, PREMIUM_NOISE_SD)
        annual_premiums[i] = round(annual_premium(coverage_plan[i], tiers[i]) * noise, 2)
        coverage_limits[i] = plan.coverage_limit_per_incident
        deductibles[i] = plan.deductible_per_incident

    start_dates = [date(2026, 1, 1) + timedelta(days=int(d)) for d in RNG.integers(0, 300, size=n)]

    # A lapsed policy needs a date it lapsed on. Without one, "Lapsed" was a
    # label with nothing behind it while claims went on being paid to the end
    # of the term. Lapses fall at least a month in -- nobody's cover ends the
    # week they buy it -- and cover runs to that date inclusive.
    status = RNG.choice(["Active", "Active", "Active", "Lapsed"], size=n)
    term_days = 30 * POLICY_TERM_MONTHS
    lapse_offsets = RNG.integers(LAPSE_EARLIEST_DAY, term_days, size=n)
    lapse_dates = [
        (start_dates[i] + timedelta(days=int(lapse_offsets[i]))).isoformat()
        if status[i] == "Lapsed" else None
        for i in range(n)
    ]

    policies = pd.DataFrame({
        "policy_id": [f"BF-{100000+i}" for i in range(n)],
        "age": age,
        "sex": sex,
        "migraine_history": migraine_history,
        "tension_type_headache_history": tth_history,
        "typical_consumption_speed": typical_speed,
        "favorite_trigger": favorite_trigger,
        "underwriting_base": base,
        "underwriting_risk_score": np.round(scores, 1),
        "risk_tier": tiers,
        "coverage_plan": coverage_plan,
        "coverage_limit_per_incident_usd": coverage_limits,
        "deductible_per_incident_usd": deductibles,
        "annual_premium_usd": annual_premiums,
        "monthly_premium_usd": np.round(annual_premiums / 12, 2),
        "policy_start_date": start_dates,
        "policy_term_months": POLICY_TERM_MONTHS,
        "policy_status": status,
        "policy_lapse_date": lapse_dates,
        "_risk_score_raw": scores,
    })
    return policies


def make_claims(policies):
    rows = []
    claim_counter = 0
    for _, pol in policies.iterrows():
        n_events = RNG.integers(EVENTS_PER_POLICY[0], EVENTS_PER_POLICY[1] + 1)
        event_dates = random_dates_in_term(pol["policy_start_date"], pol["policy_term_months"], n_events)
        approved_claims_this_year = 0

        lapse_date = pol["policy_lapse_date"]
        # pandas can hand back NaN rather than None here, and NaN is truthy.
        lapse_date = date.fromisoformat(lapse_date) if isinstance(lapse_date, str) else None

        for event_date in event_dates:
            in_force = lapse_date is None or event_date <= lapse_date
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
            temp_factor = -item_temp_c / 45  # colder = riskier
            trigger_factor = (TRIGGER_RISK_MULT[trigger] - 1) * 0.6

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

                    # What the episode is worth. The jitter is the generator's.
                    claim_amount_requested = assess_amount(
                        pain_intensity, duration_sec, jitter=RNG.normal(0, 5)
                    )

                    if not in_force:
                        # Refused for the lapse, not for paperwork or the cap:
                        # those would be true too, but they are not the reason.
                        decision = adjudicate(
                            claim_amount_requested,
                            pol["coverage_limit_per_incident_usd"],
                            pol["deductible_per_incident_usd"],
                            approved_claims_this_year,
                            policy_in_force=False,
                        )
                        claim_status, claim_amount_approved = decision.status, decision.amount
                        denial_reason = decision.reason
                    elif approved_claims_this_year >= ANNUAL_CLAIM_LIMIT:
                        decision = adjudicate(
                            claim_amount_requested,
                            pol["coverage_limit_per_incident_usd"],
                            pol["deductible_per_incident_usd"],
                            approved_claims_this_year,
                        )
                        claim_status, claim_amount_approved = decision.status, decision.amount
                        denial_reason = decision.reason
                    elif RNG.random() < UNMODELLED_DENIAL_RATE:
                        # Not a rule -- paperwork, an exclusion, a late filing.
                        claim_status = "Denied"
                        denial_reason = RNG.choice(DENIAL_REASONS)
                    else:
                        decision = adjudicate(
                            claim_amount_requested,
                            pol["coverage_limit_per_incident_usd"],
                            pol["deductible_per_incident_usd"],
                            approved_claims_this_year,
                        )
                        claim_status, claim_amount_approved = decision.status, decision.amount
                        denial_reason = decision.reason
                        if decision.approved:
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
    claims.insert(0, "event_id", [f"EVT-{i+1:06d}" for i in range(len(claims))])
    return claims


def main():
    policies = make_policyholders(N_POLICIES)
    claims = make_claims(policies)

    policies_out = policies.drop(columns=["_risk_score_raw"])
    policies_out.to_csv(POLICYHOLDERS_CSV, index=False)
    claims.to_csv(CLAIMS_CSV, index=False)

    print(f"Wrote {len(policies_out):,} policyholders -> {POLICYHOLDERS_CSV.name}")
    print(f"Wrote {len(claims):,} events -> {CLAIMS_CSV.name}")

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
