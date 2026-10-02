"""What every page needs: rendering, and how to describe a policy's cover.

Here rather than in app.py so the routes reach them by name on every
request -- `pages.render(...)` -- and pick up a loaded change. See routes.py.
"""

from flask import render_template_string

import brainfreeze
import brainfreeze.money as money


def render(template, **context):
    """Render, with `usd` available to every template to format money.

    `format_usd` gives `$170.10` whatever places the Decimal carries, and
    copes with `None`.

    It goes in the context rather than being registered as a Jinja filter or
    global: Grail's `cached_property` does not cache, so each read of
    `app.jinja_env` builds a fresh Environment and a registration on it is
    discarded.
    """
    return render_template_string(template, usd=money.format_usd, **context)


def cover_state(policy, today):
    """How to describe this policy's cover, as of a date.

    `policy_status` records a policy's fate over its whole term, and the
    sample book's terms run either side of the present, so a stored "Lapsed"
    may not have lapsed yet and some policies have not started. Compare
    against the date instead.
    """
    if policy.is_in_force_on(today):
        if policy.policy_lapse_date is None:
            return ("Active", "ok")
        return ("Lapses %s" % policy.policy_lapse_date, "tag")
    if policy.no_cover_reason_on(today) == brainfreeze.REASON_POLICY_LAPSED:
        return ("Lapsed %s" % policy.policy_lapse_date, "no")
    if today < policy.policy_start_date:
        return ("Starts %s" % policy.policy_start_date, "tag")
    return ("Term ended %s" % policy.policy_end_date, "no")


def refuse(code, message):
    """Stop the request with `code`, and say `message` to whoever made it.

    What `abort(code, message)` should do, but Grail's werkzeug `abort`
    drops the message. Setting it on the exception works there and in real
    Werkzeug. Removing it is GemTalk/brain-freeze#87, once GemTalk/Grail#1290
    ships.
    """
    from werkzeug.exceptions import default_exceptions
    refusal = default_exceptions[code]()
    refusal.description = message
    raise refusal

