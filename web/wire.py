"""The objects, as JSON-ready data. One place, so money has one rule.

    import wire
    wire.policy(book["BF-100539"], date.today())

`routes_html.py` renders these same objects as HTML; the JSON surface serves
them through here. Nothing maps them -- the only question is what money
looks like on the wire.

MONEY IS AN EXACT DECIMAL STRING

`"92081.22"`: exact, two places, no symbol, no grouping, `null` when no money
was recorded. The rule is `brainfreeze.money.wire_usd`, and every money field
below goes through `money()`, so it is applied in one place rather than in
each handler. `money.format_usd` (`"$92,081.22"`) is display and never
appears in a payload.

A RATIO IS NOT MONEY

Loss ratios stay floats: the already-rounded ones `brainfreeze.analysis`
publishes, so the number in a JSON body is the number on the screen.
`brain_freeze_rate` is absent because it is unrounded and two surfaces could
disagree in its last digit; the two counts it divides are both here.

Standard library only, and nothing from the routes, so `tests/test_api.py`
drives the payloads under CPython from a seeded book.
"""

from datetime import date

import brainfreeze.analysis as analysis
import brainfreeze.money


def money(value):
    """Money, for a JSON body. The single door every Decimal leaves by.

    A function rather than `money = wire_usd`, which would be a copy of the
    function this module had when it loaded -- see routes.py.
    """
    return brainfreeze.money.wire_usd(value)


def _date(value):
    """A date as `YYYY-MM-DD`, or None. `str()` on a `date` is already that."""
    if value is None:
        return None
    return str(value)


#: Every key in every payload here whose value is money. The unit tests and
#: the acceptance suite check the wire format on decoded payloads, where the
#: key is all that identifies a figure. `tests/test_api.py` fails if a key is
#: handed to `money()` and is not listed here.
MONEY_KEYS = frozenset([
    "annual", "annual_premium", "approved", "coverage_limit", "deductible",
    "limit", "monthly", "monthly_premium", "paid", "premium", "requested",
    "total_paid",
])


def claim(a_claim):
    """One claim: both figures, the outcome, and why."""
    return {
        "claim_id": a_claim.claim_id,
        "requested": money(a_claim.requested),
        "approved": money(a_claim.approved),
        "status": a_claim.status,
        "is_approved": a_claim.is_approved,
        # An agent can only explain a refusal from the reason that refused it.
        "reason": a_claim.reason,
    }


def event(an_event, with_claim=True):
    """One cold treat, whether or not it caused anything.

    `with_claim=False` for the places that publish the claim alongside rather
    than inside it, so the same claim is not written twice in one body.
    """
    payload = {
        "event_id": an_event.event_id,
        "event_date": _date(an_event.event_date),
        "trigger": an_event.trigger,
        "temperature_c": an_event.temperature_c,
        "portion_ml": an_event.portion_ml,
        "consumption_speed": an_event.consumption_speed,
        "brain_freeze": an_event.brain_freeze,
        "onset_sec": an_event.onset_sec,
        "duration_sec": an_event.duration_sec,
        "pain_intensity": an_event.pain_intensity,
        "pain_location": an_event.pain_location,
        "pain_quality": an_event.pain_quality,
    }
    if with_claim:
        payload["claim"] = None if an_event.claim is None else claim(an_event.claim)
    return payload


def policy(policyholder, when=None):
    """One policy, without its history. What a list of them shows.

    Cover is answered as of a date: `in_force` and a reason, where the picker
    shows a sentence. `policy_status` is different -- the policy's fate over
    its whole term (see `pages.cover_state`).
    """
    if when is None:
        when = date.today()
    return {
        "policy_id": policyholder.policy_id,
        "plan_name": policyholder.plan_name,
        "risk_tier": policyholder.risk_tier,
        "underwriting_risk_score": policyholder.underwriting_risk_score,
        "age": policyholder.age,
        "migraine_history": policyholder.migraine_history,
        "tension_type_headache_history":
            policyholder.tension_type_headache_history,
        "typical_consumption_speed": policyholder.typical_consumption_speed,
        "favourite_trigger": policyholder.favourite_trigger,
        "annual_premium": money(policyholder.annual_premium),
        "monthly_premium": money(policyholder.monthly_premium),
        "coverage_limit": money(policyholder.coverage_limit),
        "deductible": money(policyholder.deductible),
        "policy_start_date": _date(policyholder.policy_start_date),
        "policy_end_date": _date(policyholder.policy_end_date),
        "policy_lapse_date": _date(policyholder.policy_lapse_date),
        "policy_status": policyholder.policy_status,
        "as_of": _date(when),
        "in_force": policyholder.is_in_force_on(when),
        "no_cover_reason": policyholder.no_cover_reason_on(when),
        "event_count": len(policyholder.events),
        "brain_freeze_event_count": len(policyholder.brain_freeze_events),
        "claim_count": len(policyholder.claims),
        "approved_claim_count": len(policyholder.approved_claims),
        "claims_remaining_this_year": policyholder.claims_remaining_this_year,
        "total_paid": money(policyholder.total_paid),
        "loss_ratio": policyholder.loss_ratio,
    }


def policy_detail(policyholder, when=None):
    """One policy and everything that has happened under it.

    Every event, not just the claimed ones: the treats that hurt nobody are
    the denominator. Oldest first, as the model keeps them.
    """
    payload = policy(policyholder, when)
    payload["events"] = [event(e) for e in policyholder.events]
    return payload


def claim_detail(policyholder, an_event):
    """One claim, with the episode behind it and the terms it was judged by.

    The limit and the deductible are here so `requested` and `approved`
    explain themselves. The subtraction is not: that would be a second copy
    of the decision screen's arithmetic.
    """
    return {
        "policy_id": policyholder.policy_id,
        "plan_name": policyholder.plan_name,
        "coverage_limit": money(policyholder.coverage_limit),
        "deductible": money(policyholder.deductible),
        "claim": claim(an_event.claim),
        "event": event(an_event, with_claim=False),
    }


def quote(offer):
    """A priced quote, with the reasoning that produced it.

    The breakdown is what lets an agent explain a price from the same rows
    the quote screen shows.
    """
    plans = {}
    for name in offer.plans:
        plan = offer.plans[name]
        plans[name] = {
            "annual": money(plan["annual"]),
            "monthly": money(plan["monthly"]),
            "limit": money(plan["limit"]),
            "deductible": money(plan["deductible"]),
        }
    return {
        "score": offer.score,
        "risk_tier": offer.risk_tier,
        "breakdown": [{"label": label, "points": points}
                      for label, points in offer.breakdown],
        "plans": plans,
    }


def stats(book):
    """Book-level aggregates: `brainfreeze.analysis`, serialised.

    Every figure comes from `brainfreeze.analysis`, not from aggregation
    here, so there is only one answer.

    Counts are renamed `*_count` on the way out: `approved` is money on a
    claim and `events` a list on a policy, so the bare names are ambiguous
    in JSON.
    """
    summary = analysis.book_summary(book)
    return {
        "policy_count": summary["policies"],
        "event_count": summary["events"],
        "brain_freeze_event_count": summary["brain_freeze_events"],
        "claim_count": summary["claims"],
        "approved_claim_count": summary["approved"],
        "premium": money(summary["premium"]),
        "paid": money(summary["paid"]),
        "loss_ratio": summary["loss_ratio"],
        "claim_approval_rate": analysis.claim_approval_rate(book),
        "loss_ratio_by_tier": analysis.loss_ratio_by_tier(book),
        "loss_ratio_by_plan": analysis.loss_ratio_by_plan(book),
        "denial_reasons": [{"reason": reason, "claims": count}
                           for reason, count in analysis.denial_reasons(book)],
    }
