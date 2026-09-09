"""The objects, as JSON-ready data. One place, so money has one rule.

    from brainfreeze import wire
    wire.policy(book["BF-100539"], date.today())

`app.py` renders these same objects as HTML; issue #50 asks for them over
`curl` as well. What that needs is not an ORM or a schema -- the objects are
already in the database and nothing maps them -- but an answer to one
question: what does money look like on the wire?

MONEY IS AN EXACT DECIMAL STRING

`json.dumps` cannot serialise a `decimal.Decimal`, so the API has to choose,
and `"92081.22"` is the choice: exact, two places, no symbol, no grouping,
`null` when no money was recorded. The reasoning is in
`brainfreeze.money.wire_usd`, which is the only function here that turns money
into text. Every money field in every payload below goes through `money()`,
which is that function under a shorter name, and that is the whole point of
this module existing rather than six handlers building dicts for themselves:
six handlers is six places for the rule to be got wrong once.

`money.format_usd` is display -- `"$92,081.22"` -- and must never appear in a
payload.

A RATIO IS NOT MONEY

Loss ratios stay floats, because that is what they honestly are. They are the
already-rounded ones the model and `brainfreeze.analysis` publish, so the
number in a JSON body is the number on the screen. `brain_freeze_rate` is
deliberately absent: it is an unrounded division, and two surfaces could
disagree in its last digit. The two counts it divides are both here.

Standard library only, like the rest of the package, and it imports nothing
from `app` -- so the payloads can be driven under CPython from a seeded book,
which `tests/test_api.py` does.
"""

from datetime import date

from .analysis import (
    book_summary,
    claim_approval_rate,
    denial_reasons,
    loss_ratio_by_plan,
    loss_ratio_by_tier,
)
from .money import wire_usd

#: Money, for a JSON body. The single door every Decimal leaves by.
money = wire_usd


def _date(value):
    """A date as `YYYY-MM-DD`, or None. `str()` on a `date` is already that."""
    if value is None:
        return None
    return str(value)


def claim(a_claim):
    """One claim: both figures, the outcome, and why."""
    return {
        "claim_id": a_claim.claim_id,
        "requested": money(a_claim.requested),
        "approved": money(a_claim.approved),
        "status": a_claim.status,
        "is_approved": a_claim.is_approved,
        # The reason is the point of CUJ-2: an agent can only explain a
        # refusal from the reason that actually refused it.
        "reason": a_claim.reason,
        # CUJ-4. A claim written before these fields existed reads None and
        # () through the class, and publishes as null and [].
        "flavour": a_claim.flavour,
        "toppings": list(a_claim.toppings),
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

    Cover is answered `as of` a date rather than described. The picker renders
    "Lapses 2027-03-10" because a person reads that; a script wants
    `in_force` and a reason, and it must not have to parse a sentence. Note
    that `policy_status` is a different question again -- it records the
    policy's fate over the whole term, and 217 policies are stored "Lapsed"
    while only 53 have reached the date.
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

    Every event, not just the claimed ones -- the treats that hurt nobody are
    the denominator, and a surface that drops them cannot answer how often a
    slushie causes brain freeze. They arrive in the order the model keeps
    them in, which is oldest first.
    """
    payload = policy(policyholder, when)
    payload["events"] = [event(e) for e in policyholder.events]
    return payload


def claim_detail(policyholder, an_event):
    """One claim, with the episode behind it and the terms it was judged by.

    The limit and the deductible are here because without them the two
    figures do not explain themselves: a script reading `requested` and
    `approved` can see what the episode cap and the excess took only if it is
    told what they were. It is not told the subtraction -- that would be a
    second copy of arithmetic the decision screen already does.
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

    The breakdown is not decoration. CUJ-2 asks an agent to explain a price,
    and it can only do that from the same rows the quote screen shows.
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
        "tier": offer.tier,
        "breakdown": [{"label": label, "points": points}
                      for label, points in offer.breakdown],
        "plans": plans,
    }


def stats(book):
    """Book-level aggregates: `brainfreeze.analysis`, serialised.

    Every figure is one of the named questions rather than a count worked out
    here. A surface that did its own aggregation would be a second answer, and
    the denominator is exactly what gets got wrong.

    The counts are renamed on the way out. `book_summary` calls them
    `policies`, `claims` and `approved`, which is fine in Python and ambiguous
    in JSON: `approved` is money on a claim and a count here, and `events` is
    a list on a policy. `_count` throughout, so a reader never has to ask.
    """
    summary = book_summary(book)
    return {
        "policy_count": summary["policies"],
        "event_count": summary["events"],
        "brain_freeze_event_count": summary["brain_freeze_events"],
        "claim_count": summary["claims"],
        "approved_claim_count": summary["approved"],
        "premium": money(summary["premium"]),
        "paid": money(summary["paid"]),
        "loss_ratio": summary["loss_ratio"],
        "claim_approval_rate": claim_approval_rate(book),
        "loss_ratio_by_tier": loss_ratio_by_tier(book),
        "loss_ratio_by_plan": loss_ratio_by_plan(book),
        "denial_reasons": [{"reason": reason, "claims": count}
                           for reason, count in denial_reasons(book)],
    }
