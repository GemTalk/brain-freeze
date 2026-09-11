"""The same objects over `curl`.

Read-only by design: a JSON surface that could mutate would need an
authentication story this demo does not have, and the point here is that the
objects are reachable, not that they are writable.

Money on the wire is an exact decimal string -- see `brainfreeze.money.wire_usd`
and `wire.py`. Never a float: publishing money as a JSON number would put back
at the boundary the defect the money work removed from the data.
"""

from datetime import date

from flask import jsonify, request

import brainfreeze
import forms
import wire
from lookups import book


def register(app):
    """Add every JSON route to `app`."""

    def _api_error(status, message):
        """A JSON error, from the handler rather than from an errorhandler.

        A global `@app.errorhandler(404)` would be shorter and would also
        turn the HTML routes' 404s into JSON, which is the wrong answer to
        give a browser. Two surfaces, two shapes of failure.
        """
        return jsonify(error=message), status


    @app.route("/api/questions")
    def api_questions():
        return jsonify(questions=forms.quote_questions())


    @app.route("/api/quote", methods=["POST"])
    def api_quote():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return _api_error(400, "send a JSON object of answers -- "
                                   "GET /api/questions says which")
        try:
            answers = forms.answers_from(data)
        except ValueError as bad:
            return _api_error(400, str(bad))
        # The answers go back out with the price. A saved request body and
        # the reply together are a fixture: replay it and get this screen.
        return jsonify(answers=answers,
                       quote=wire.quote(brainfreeze.quote(**answers)))


    @app.route("/api/policies")
    def api_policies():
        # The whole book, where the picker shows 25 at a time. That page size
        # is not a JSON problem: it is there because Grail renders each Jinja
        # row in a forked green thread and 900 of those take the best part of
        # a minute. Serialising 900 dicts does not, and a script wants the
        # book rather than a window onto it.
        today = date.today()
        everyone = sorted(book(), key=lambda p: p.policy_id)
        return jsonify(count=len(everyone),
                       policies=[wire.policy(p, today)
                                 for p in everyone])


    @app.route("/api/policy/<policy_id>")
    def api_policy(policy_id):
        try:
            policy = book()[policy_id]
        except KeyError:
            return _api_error(404, "no policy %s" % policy_id)
        return jsonify(wire.policy_detail(policy, date.today()))


    @app.route("/api/claim/<claim_id>")
    def api_claim(claim_id):
        # A claim id is enough here where the HTML route needs the policy id
        # as well, and that is most of what makes this one useful from a
        # shell. The scan is linear over the book because nothing indexes
        # claims by id -- an index would be a second copy of `Book.claims`,
        # and the demo's whole argument is that there is only ever one.
        for policyholder in book():
            for an_event in policyholder.events:
                if (an_event.claim is not None
                        and an_event.claim.claim_id == claim_id):
                    return jsonify(wire.claim_detail(
                        policyholder, an_event))
        return _api_error(404, "no claim %s" % claim_id)


    @app.route("/api/stats")
    def api_stats():
        return jsonify(wire.stats(book()))

