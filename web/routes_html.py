"""The pages a person clicks through.

Registered onto an app rather than defined inside a factory. `create_app` was
349 lines holding all fifteen routes and twenty-one helpers, which meant
nothing in it could be imported, read, or tested on its own -- and is why the
tests for this surface had to resort to parsing the file's own syntax tree.

`register(app)` rather than a Flask blueprint: a blueprint would prefix every
endpoint name, and the templates call `url_for('history')` and friends by the
bare name. Blueprints would be the idiom in a larger application; here they
would buy nothing and break every template.

A top-level module, so Grail recompiles it from disk each run. See lookups.py.
"""

from datetime import date

from flask import abort, redirect, request, url_for

import brainfreeze
import forms
import gemdb
from brainfreeze import Claim, Event, Policyholder, SavedQuote
from brainfreeze.money import ZERO
from lookups import book, next_id, policy_or_404, quote_or_404, quotes
from templates import (
    CLAIM_FORM, DECISION, HISTORY, PICKER, PLANS, QUOTE_FORM)

#: How many policyholders the picker renders at once. Grail runs each Jinja
#: template in a forked green thread, and 900 of them takes the best part of
#: a minute; a page is what makes the front door feel like a web page.
PAGE = 50


def register(app, render, cover_state):
    """Add every HTML route to `app`.

    `render` and `cover_state` are passed in rather than imported to keep the
    import graph a tree: app.py owns them, and both surfaces get what they
    need handed to them.
    """

    @app.route("/")
    def index():
        # A page at a time. Rendering all 900 takes the best part of a minute
        # -- Grail runs each Jinja template in a forked green thread, and 900
        # rows of it is not what that is for. The count is the point, not the
        # scroll, so the total is stated and the table is a window onto it.
        today = date.today()
        everyone = sorted(book(), key=lambda p: p.policy_id)

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
        rows = [(p,) + cover_state(p, today) for p in window]
        return render(
            PICKER, rows=rows, total=len(book()), shown=len(everyone),
            start=start, page=PAGE, wanted=wanted)


    @app.route("/quote")
    def quote_form():
        return render(
            QUOTE_FORM, triggers=forms.TRIGGERS, speeds=forms.SPEED_BANDS)


    @app.route("/quote", methods=["POST"])
    def quote_result():
        """Price a quote, keep it, and send the browser to its address.

        A write like any other here, so it commits and redirects: refreshing
        the result re-opens the quote instead of minting a second one, and the
        quote's id is in the address bar where a person can copy it.

        The answers come back through the same reader the JSON surface uses,
        so a value the form should not have been able to send is a 400 that
        names the field rather than a KeyError inside the risk model.
        """
        try:
            answers = forms.answers_from(request.form)
        except ValueError as bad:
            abort(400, str(bad))
        offer = brainfreeze.quote(**answers)
        the_book = book()
        saved = the_book.add_quote(SavedQuote(
            quote_id=next_id(quotes(the_book), "QTE", 6, 1),
            quoted_on=date.today(),
            score=offer.score,
            risk_tier=offer.risk_tier,
            breakdown=offer.breakdown,
            plans=offer.plans,
            **answers))
        gemdb.commit()
        return redirect(url_for("saved_quote", quote_id=saved.quote_id))


    @app.route("/quote/<quote_id>")
    def saved_quote(quote_id):
        return render(PLANS, q=quote_or_404(quote_id))


    @app.route("/quote/<quote_id>/accept", methods=["POST"])
    def accept_quote(quote_id):
        """Turn a quote into a policy, at the price the quote quoted.

        Note what is NOT here: a second call to `brainfreeze.quote`. The
        answers and the three prices were stored when the quote was given, and
        a customer is sold what they were shown. Re-pricing at this point
        would be the old round-trip with the hidden fields taken out.
        """
        saved = quote_or_404(quote_id)
        plan_name = request.form.get("plan", "Standard")
        if plan_name not in saved.plans:
            abort(404)

        the_book = book()
        policy = Policyholder(
            policy_id=next_id([p.policy_id for p in the_book], "BF", 6, 100000),
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


    @app.route("/policies/<policy_id>")
    def history(policy_id):
        policy = policy_or_404(policy_id)
        today = date.today()
        label, css = cover_state(policy, today)
        return render(
            HISTORY, p=policy, cover=label, cover_css=css,
            limit=brainfreeze.ANNUAL_CLAIM_LIMIT)


    def _warnings(policy, today):
        """What the form should say before anyone fills it in.

        Both of these would otherwise only be discovered by filing and being
        refused, and the lapse is the more confusing one to receive silently.

        Which absence of cover it is comes from the model, so the warning on
        the form and the reason on the refusal cannot disagree -- and so a
        policy that has not started yet is not told it lapsed on None.
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


    @app.route("/policies/<policy_id>/claims/new")
    def claim_form(policy_id):
        policy = policy_or_404(policy_id)
        return render(
            CLAIM_FORM, p=policy, triggers=forms.TRIGGERS, colds=forms.COLD_BANDS,
            portions=forms.PORTION_BANDS, speeds=forms.SPEED_BANDS,
            durations=forms.DURATION_BANDS, locations=forms.PAIN_LOCATIONS,
            qualities=forms.PAIN_QUALITIES, flavours=forms.FLAVOURS, toppings=forms.TOPPINGS,
            warnings=_warnings(policy, date.today()))


    @app.route("/policies/<policy_id>/claims", methods=["POST"])
    def file_claim(policy_id):
        policy = policy_or_404(policy_id)
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

        the_book = book()
        claim = Claim(
            claim_id=next_id([c.claim_id for c in the_book.claims],
                              "CLM", 6, 1),
            requested=requested,
            approved=decision.amount,
            status=decision.status,
            reason=decision.reason,
            rule=decision.rule,
            flavour=request.form.get("flavour") or None,
            toppings=request.form.getlist("toppings") or None)
        policy.add_event(Event(
            event_id=next_id([e.event_id for e in the_book.events],
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


    @app.route("/policies/<policy_id>/claims/<claim_id>")
    def decision(policy_id, claim_id):
        policy = policy_or_404(policy_id)
        for event in policy.events:
            if event.claim is not None and event.claim.claim_id == claim_id:
                claim = event.claim
                # Worked out here rather than in the template. Handlers do the
                # sums; templates print them. A conditional expression over
                # Decimals inside `{{ }}` is more Grail-compiled Jinja than
                # this needs to be.
                trimmed = claim.requested - claim.approved - policy.deductible
                return render(DECISION, p=policy, e=event, c=claim,
                              trimmed=max(ZERO, trimmed))
        abort(404)

