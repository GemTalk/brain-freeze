"""The pages a person clicks through.

`register(app)` rather than a Flask blueprint: a blueprint would prefix every
endpoint name, and the templates call `url_for('history')` and friends by the
bare name.

Declared with `ROUTES.route`, and every template, lookup and helper reached
through its module, so a running app picks up a loaded change to this file.
See routes.py.
"""

from datetime import date

from flask import abort, redirect, request, url_for

import brainfreeze
import brainfreeze.money as money
import forms
import gemdb
import lookups
import pages
import templates
from routes import Routes

ROUTES = Routes(__name__)

#: How many policyholders the picker renders at once. Rendering all 900
#: takes several seconds under Grail, which autoescapes each value slowly.
PAGE = 50


@ROUTES.route("/")
def index():
    # A page at a time (see PAGE); the total is stated and the table is a
    # window onto it.
    today = date.today()
    everyone = sorted(lookups.book(), key=lambda p: p.policy_id)

    wanted = (request.args.get("policy") or "").strip().upper()
    if wanted:
        match = [p for p in everyone if wanted in p.policy_id]
        if len(match) == 1:
            return redirect(url_for("history",
                                    policy_id=match[0].policy_id))
        everyone, start = match, 0
    else:
        try:
            start = max(0, int(request.args.get("from", 0)))
        except ValueError:
            start = 0

    window = everyone[start:start + PAGE]
    rows = [(p,) + pages.cover_state(p, today) for p in window]
    return pages.render(
        templates.PICKER, rows=rows, total=len(lookups.book()), shown=len(everyone),
        start=start, page=PAGE, wanted=wanted)


@ROUTES.route("/quote")
def quote_form():
    return pages.render(
        templates.QUOTE_FORM, triggers=forms.TRIGGERS, speeds=forms.SPEED_BANDS)


@ROUTES.route("/quote", methods=["POST"])
def quote_result():
    """Price a quote, keep it, and send the browser to its address.

    Commits and redirects like any write, so a refresh re-opens the quote
    instead of minting a second one. The answers go through the same reader
    as the JSON surface, so a bad value is a 400 naming the field.
    """
    try:
        answers = forms.answers_from(request.form)
    except ValueError as bad:
        pages.refuse(400, str(bad))
    offer = brainfreeze.quote(**answers)
    the_book = lookups.book()
    saved = the_book.add_quote(brainfreeze.SavedQuote(
        quote_id=lookups.next_id(lookups.quotes(the_book), "QTE", 6, 1),
        quoted_on=date.today(),
        score=offer.score,
        risk_tier=offer.risk_tier,
        breakdown=offer.breakdown,
        plans=offer.plans,
        **answers))
    gemdb.commit()
    return redirect(url_for("saved_quote", quote_id=saved.quote_id))


@ROUTES.route("/quote/<quote_id>")
def saved_quote(quote_id):
    return pages.render(templates.PLANS, q=lookups.quote_or_404(quote_id))


@ROUTES.route("/quote/<quote_id>/accept", methods=["POST"])
def accept_quote(quote_id):
    """Turn a quote into a policy, at the price the quote quoted.

    No second call to `brainfreeze.quote`: the answers and prices were
    stored with the quote, and a customer is sold what they were shown.
    """
    saved = lookups.quote_or_404(quote_id)
    plan_name = request.form.get("plan", "Standard")
    if plan_name not in saved.plans:
        abort(404)

    the_book = lookups.book()
    policy = brainfreeze.Policyholder(
        policy_id=lookups.next_id([p.policy_id for p in the_book], "BF", 6, 100000),
        sex=None,
        underwriting_base=brainfreeze.BASE_RISK,
        plan_name=plan_name,
        annual_premium=saved.plans[plan_name]["annual"],
        policy_start_date=date.today(),
        **saved.answers)
    the_book.add(policy)
    # The quote remembers what it became, so re-opening it says so rather
    # than offering to sell the same cover a second time.
    saved.policy_id = policy.policy_id
    gemdb.commit()
    return redirect(url_for("history", policy_id=policy.policy_id))


@ROUTES.route("/policies/<policy_id>")
def history(policy_id):
    policy = lookups.policy_or_404(policy_id)
    today = date.today()
    label, css = pages.cover_state(policy, today)
    return pages.render(
        templates.HISTORY, p=policy, cover=label, cover_css=css,
        limit=brainfreeze.ANNUAL_CLAIM_LIMIT)


def warnings_for(policy, today):
    """What the form should say before anyone fills it in.

    Otherwise these are only discovered by filing and being refused. Which
    absence of cover it is comes from the model, so the warning and the
    refusal's reason cannot disagree.
    """
    notes = []
    no_cover = policy.no_cover_reason_on(today)
    if no_cover == brainfreeze.REASON_POLICY_LAPSED:
        notes.append(
            "Cover on this policy ended on %s. Anything filed now is "
            "refused." % policy.policy_lapse_date)
    elif no_cover is not None:
        if today < policy.policy_start_date:
            notes.append(
                "Cover on this policy does not start until %s. Anything "
                "filed now is refused." % policy.policy_start_date)
        else:
            notes.append(
                "The term on this policy ended on %s. Anything filed now "
                "is refused." % policy.policy_end_date)
    elif policy.claims_remaining_this_year == 0:
        notes.append(
            "This policy has used all %d approvals for the year. A new "
            "claim is refused until it renews."
            % brainfreeze.ANNUAL_CLAIM_LIMIT)
    return notes


@ROUTES.route("/policies/<policy_id>/claims/new")
def claim_form(policy_id):
    policy = lookups.policy_or_404(policy_id)
    return pages.render(
        templates.CLAIM_FORM, p=policy, triggers=forms.TRIGGERS, colds=forms.COLD_BANDS,
        portions=forms.PORTION_BANDS, speeds=forms.SPEED_BANDS,
        durations=forms.DURATION_BANDS, locations=forms.PAIN_LOCATIONS,
        qualities=forms.PAIN_QUALITIES,
        warnings=warnings_for(policy, date.today()))


@ROUTES.route("/policies/<policy_id>/claims", methods=["POST"])
def file_claim(policy_id):
    policy = lookups.policy_or_404(policy_id)
    today = date.today()

    pain = float(request.form.get("pain", 5))
    duration = forms._band(forms.DURATION_BANDS, request.form.get("duration"))

    # The claimant never enters a figure. This derives it, so two people
    # who describe the same episode get the same number.
    requested = brainfreeze.assess_amount(pain, duration)

    decision = brainfreeze.adjudicate(
        requested,
        policy.coverage_limit,
        policy.deductible,
        len(policy.approved_claims),
        policy_in_force=policy.is_in_force_on(today),
        no_cover_reason=policy.no_cover_reason_on(today))

    the_book = lookups.book()
    claim = brainfreeze.Claim(
        claim_id=lookups.next_id([c.claim_id for c in the_book.claims],
                          "CLM", 6, 1),
        requested=requested,
        approved=decision.amount,
        status=decision.status,
        reason=decision.reason,
        rule=decision.rule)
    policy.add_event(brainfreeze.Event(
        event_id=lookups.next_id([e.event_id for e in the_book.events],
                          "EVT", 6, 1),
        event_date=today,
        trigger=request.form.get("trigger", "ice cream"),
        temperature_c=forms._band(forms.COLD_BANDS, request.form.get("cold")),
        portion_ml=forms._band(forms.PORTION_BANDS, request.form.get("portion")),
        consumption_speed=forms._band(forms.SPEED_BANDS, request.form.get("speed"),
                                default="moderate"),
        brain_freeze=True,
        duration_sec=duration,
        pain_intensity=pain,
        pain_location=request.form.get("location"),
        pain_quality=request.form.get("quality"),
        claim=claim))
    gemdb.commit()

    return redirect(url_for("decision", policy_id=policy.policy_id,
                            claim_id=claim.claim_id))


@ROUTES.route("/policies/<policy_id>/claims/<claim_id>")
def decision(policy_id, claim_id):
    policy = lookups.policy_or_404(policy_id)
    for event in policy.events:
        if event.claim is not None and event.claim.claim_id == claim_id:
            claim = event.claim
            # Handlers do the sums; templates print them.
            trimmed = claim.requested - claim.approved - policy.deductible
            return pages.render(templates.DECISION, p=policy, e=event, c=claim,
                          trimmed=max(money.ZERO, trimmed))
    abort(404)


def register(app):
    """Add every HTML route to `app`."""
    ROUTES.register(app)
