"""The pages a person clicks through.

`register(app)` rather than a Flask blueprint: a blueprint would prefix every
endpoint name, and the templates call `url_for('history')` and friends by the
bare name.

Declared with `ROUTES.route`, and every template, lookup and helper reached
through its module, so a running app picks up a loaded change to this file.
See routes.py.
"""

from datetime import date

from flask import Response, abort, redirect, request, url_for

import brainfreeze
import brainfreeze.money as money
import brainfreeze.underwriting as underwriting
import forms
import gemdb
import lookups
import pages
from routes import Routes

ROUTES = Routes(__name__)

#: How many policyholders the picker renders at once. Rendering all 900
#: takes several seconds under Grail, which autoescapes each value slowly.
PAGE = 50

#: Claims per page on the claims list, for the same reason.
CLAIMS_PAGE = 25

#: The claims list's filters: the value in `?status=`, and its label.
CLAIM_FILTERS = [("all", "All"), ("approved", "Approved"),
                 ("refused", "Refused")]


def plan_holders(the_book):
    """How many policyholders hold each plan, by plan name."""
    held = dict((name, 0) for name in brainfreeze.COVERAGE_PLANS)
    for policy in the_book:
        held[policy.plan_name] = held.get(policy.plan_name, 0) + 1
    return held


def most_chosen(held):
    """The plan most policyholders hold -- the one the pages mark."""
    return max(held, key=held.get)


def monthly_price(plan_name, band):
    """What a plan costs a month in a band, rounded as `quote()` rounds it:
    the annual price to the cent, then a twelfth of that."""
    annual = money.round_cents(brainfreeze.annual_premium(plan_name, band))
    return money.round_cents(annual / 12)


@ROUTES.route("/")
def home():
    """What this is, what the plans are, and the way into a quote.

    The plan prices are the model's, not copy. Each plan is shown at the band
    that pays its base price (Medium: $7, $12, $19 a month), with the range
    the other bands span, each worked out the way `quote()` works it out --
    so they move when `underwriting.py` does.

    Counts only, no money totals: `book_summary` sums every premium and
    payout, which takes over three seconds under Grail -- too slow for the
    front door.
    """
    the_book = lookups.book()
    held = plan_holders(the_book)
    bands = brainfreeze.RISK_TIER_MULT
    typical = [band for band in bands if bands[band] == 1][0]
    plans = []
    for name, plan in brainfreeze.COVERAGE_PLANS.items():
        monthly = dict((band, monthly_price(name, band)) for band in bands)
        plans.append(dict(
            name=name,
            monthly=monthly[typical],
            lowest=min(monthly.values()),
            highest=max(monthly.values()),
            limit=plan.coverage_limit_per_incident,
            deductible=plan.deductible_per_incident,
            holders="{:,}".format(held[name]),
            popular=(name == most_chosen(held))))
    return pages.render(
        "home.html", plans=plans, typical=typical,
        claim_limit=brainfreeze.ANNUAL_CLAIM_LIMIT,
        stats=dict(policies="{:,}".format(len(the_book)),
                   claims="{:,}".format(len(the_book.claims))))


@ROUTES.route("/policies")
def policies():
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
        start = pages.window_start(request.args)

    window = everyone[start:start + PAGE]
    rows = [(p,) + pages.cover_state(p, today) for p in window]
    return pages.render(
        "policies.html", rows=rows, total=len(lookups.book()), wanted=wanted,
        pager=pages.pager("policies", start, PAGE, len(everyone)))


@ROUTES.route("/quote")
def quote_form():
    """Step 1: the five questions.

    `?answers=QTE-...` fills them in from a saved quote, which is how "Change
    the answers" on step 2 goes back without the browser carrying anything.
    """
    answers = dict((q["name"], q["default"]) for q in forms.quote_questions())
    again = request.args.get("answers")
    if again:
        answers.update(lookups.quote_or_404(again).answers)
    return pages.render(
        "quote_form.html", a=answers, triggers=forms.TRIGGERS,
        speeds=forms.SPEED_BANDS)


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
        quote_id=the_book.issue("QTE", 6, 1,
                                lambda: lookups.quotes(the_book)),
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
    """Step 2: the three prices, and a button on each to take it."""
    saved = lookups.quote_or_404(quote_id)
    the_book = lookups.book()
    chosen = None
    if saved.policy_id is not None:
        chosen = the_book[saved.policy_id].plan_name
    return pages.render(
        "plans.html", q=saved, chosen=chosen,
        popular=most_chosen(plan_holders(the_book)),
        claim_limit=brainfreeze.ANNUAL_CLAIM_LIMIT,
        bands=dict(low="%g" % underwriting.LOW_MAX,
                   medium="%g" % underwriting.MEDIUM_MAX))


@ROUTES.route("/quote/<quote_id>/accept", methods=["POST"])
def accept_quote(quote_id):
    """Turn a quote into a policy, at the price the quote quoted.

    No second call to `brainfreeze.quote`: the answers and prices were
    stored with the quote, and a customer is sold what they were shown.
    """
    saved = lookups.quote_or_404(quote_id)
    if saved.policy_id is not None:
        # Taken up already: a second press, or a refresh. One quote sells one
        # policy, so show the one it sold rather than minting another.
        return redirect(url_for("id_card", policy_id=saved.policy_id))
    plan_name = request.form.get("plan", "Sundae")
    if plan_name not in saved.plans:
        abort(404)

    the_book = lookups.book()
    policy = brainfreeze.Policyholder(
        policy_id=the_book.issue("BF", 6, 100000,
                                 lambda: [p.policy_id for p in the_book]),
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
    return redirect(url_for("id_card", policy_id=policy.policy_id))


@ROUTES.route("/policies/<policy_id>")
def history(policy_id):
    policy = lookups.policy_or_404(policy_id)
    today = date.today()
    label, css = pages.cover_state(policy, today)
    return pages.render(
        "policy.html", p=policy, cover=label, cover_css=css,
        limit=brainfreeze.ANNUAL_CLAIM_LIMIT)


@ROUTES.route("/policies/<policy_id>/card")
def id_card(policy_id):
    """The policy's ID card, where taking out a policy lands."""
    policy = lookups.policy_or_404(policy_id)
    return pages.render("card.html", p=policy,
                        card=pages.id_card(policy, date.today(),
                                           request.args.get("name")),
                        named=bool(request.args.get("name")),
                        style=request.args.get("style"))


@ROUTES.route("/policies/<policy_id>/card.svg")
def id_card_svg(policy_id):
    """The same card on its own, as an image a person can keep: in the
    colourway `?style=` names and with the subscriber `?name=`, as the card
    page draws it."""
    policy = lookups.policy_or_404(policy_id)
    svg = pages.render("id_card.svg",
                       card=pages.id_card(policy, date.today(),
                                          request.args.get("name")),
                       style=request.args.get("style"))
    return Response(svg, mimetype="image/svg+xml")


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
        "claim_form.html", p=policy, triggers=forms.TRIGGERS, colds=forms.COLD_BANDS,
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
        claim_id=the_book.issue("CLM", 6, 1,
                                lambda: [c.claim_id for c in the_book.claims]),
        requested=requested,
        approved=decision.amount,
        status=decision.status,
        reason=decision.reason,
        rule=decision.rule)
    policy.add_event(brainfreeze.Event(
        event_id=the_book.issue("EVT", 6, 1,
                                lambda: [e.event_id for e in the_book.events]),
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
            return pages.render("decision.html", p=policy, e=event, c=claim,
                          trimmed=max(money.ZERO, trimmed))
    abort(404)


@ROUTES.route("/claims")
def claims():
    """Every claim on the book, newest first, filtered and a page at a time.

    Newest by claim id rather than by date: claims are numbered as they are
    filed, while the seeded episodes are dated into 2027, so by date the
    first page would be claims about the future.

    A search that names one claim exactly goes straight to it, as the
    policy search does.
    """
    status = request.args.get("status", "all")
    if status not in dict(CLAIM_FILTERS):
        status = "all"
    wanted = (request.args.get("q") or "").strip().upper()

    rows = []
    approved = refused = 0
    for policy in lookups.book():
        for event in policy.events:
            claim = event.claim
            if claim is None:
                continue
            if claim.is_approved:
                approved += 1
            else:
                refused += 1
            if status == "approved" and not claim.is_approved:
                continue
            if status == "refused" and claim.is_approved:
                continue
            if wanted and wanted not in claim.claim_id \
                    and wanted not in policy.policy_id:
                continue
            rows.append((claim, event, policy))

    exact = [row for row in rows if row[0].claim_id == wanted]
    if len(exact) == 1:
        return redirect(url_for("decision", policy_id=exact[0][2].policy_id,
                                claim_id=wanted))

    rows.sort(key=lambda row: row[0].claim_id, reverse=True)
    start = pages.window_start(request.args)
    return pages.render(
        "claims.html", rows=rows[start:start + CLAIMS_PAGE], status=status,
        wanted=wanted, filters=CLAIM_FILTERS,
        pager=pages.pager("claims", start, CLAIMS_PAGE, len(rows),
                          status=status, q=wanted or None),
        summary=dict(claims="{:,}".format(approved + refused),
                     approved="{:,}".format(approved),
                     refused="{:,}".format(refused)))


def register(app):
    """Add every HTML route to `app`."""
    ROUTES.register(app)
