"""The same objects over `curl`.

Read-only: a JSON surface that could mutate would need authentication this
app does not have.

Money on the wire is an exact decimal string, never a float -- see
`brainfreeze.money.wire_usd` and `wire.py`.
"""

from datetime import date

from flask import jsonify, request

import brainfreeze
import forms
import lookups
import wire
from routes import Routes

ROUTES = Routes(__name__)


def api_error(status, message):
    """A JSON error, from the handler rather than from an errorhandler.

    A global `@app.errorhandler(404)` would also turn the HTML routes' 404s
    into JSON, which is the wrong answer to give a browser.
    """
    return jsonify(error=message), status


@ROUTES.route("/api/questions")
def api_questions():
    return jsonify(questions=forms.quote_questions())


@ROUTES.route("/api/quote", methods=["POST"])
def api_quote():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return api_error(400, "send a JSON object of answers -- "
                               "GET /api/questions says which")
    try:
        answers = forms.answers_from(data)
    except ValueError as bad:
        return api_error(400, str(bad))
    # The answers go back out with the price. A saved request body and
    # the reply together are a fixture: replay it and get this screen.
    return jsonify(answers=answers,
                   quote=wire.quote(brainfreeze.quote(**answers)))


@ROUTES.route("/api/policies")
def api_policies():
    # The whole book: the picker pages because rendering is slow under
    # Grail, but serialising 900 dicts is not, and a script wants it all.
    today = date.today()
    everyone = sorted(lookups.book(), key=lambda p: p.policy_id)
    return jsonify(count=len(everyone),
                   policies=[wire.policy(p, today)
                             for p in everyone])


@ROUTES.route("/api/policy/<policy_id>")
def api_policy(policy_id):
    try:
        policy = lookups.book()[policy_id]
    except KeyError:
        return api_error(404, "no policy %s" % policy_id)
    return jsonify(wire.policy_detail(policy, date.today()))


@ROUTES.route("/api/claim/<claim_id>")
def api_claim(claim_id):
    # A claim id alone is enough here, where the HTML route needs the
    # policy id too. The scan is linear because nothing indexes claims by
    # id, and an index would be a second copy of `Book.claims`.
    for policyholder in lookups.book():
        for an_event in policyholder.events:
            if (an_event.claim is not None
                    and an_event.claim.claim_id == claim_id):
                return jsonify(wire.claim_detail(
                    policyholder, an_event))
    return api_error(404, "no claim %s" % claim_id)


@ROUTES.route("/api/stats")
def api_stats():
    return jsonify(wire.stats(lookups.book()))


def register(app):
    """Add every JSON route to `app`."""
    ROUTES.register(app)
