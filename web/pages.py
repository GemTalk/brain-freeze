"""What every page needs: rendering, how to describe a policy's cover, the
fields of an ID card, and a window onto a long list.

Here rather than in app.py so the routes reach them by name on every
request -- `pages.render(...)` -- and pick up a loaded change. See routes.py.
"""

from flask import render_template_string, url_for

import brainfreeze
import brainfreeze.money as money
import templates


def render(template, **context):
    """Render, with `usd` to format money and `css` for the page's styles.

    `format_usd` gives `$170.10` whatever places the Decimal carries, and
    copes with `None`.

    It goes in the context rather than being registered as a Jinja filter or
    global: Grail's `cached_property` does not cache, so each read of
    `app.jinja_env` builds a fresh Environment and a registration on it is
    discarded.

    The stylesheet arrives the same way, as a value the head writes out,
    rather than as text inside every template, where Jinja would lex it on
    each render.
    """
    return render_template_string(template, usd=money.format_usd,
                                  css=templates.STYLE, **context)


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



def id_card(policy, today):
    """What the ID card prints, as display strings.

    The only thing `templates.ID_CARD` reads, so a new design for the card
    is a new SVG over these fields and nothing else. Every figure is the
    policy's own, formatted the way every other page formats it.
    """
    label, _css = cover_state(policy, today)
    return {
        "policy_id": policy.policy_id,
        "plan": policy.plan_name,
        "member": "Age %d \u00b7 favourite treat: %s"
                  % (policy.age, policy.favourite_trigger),
        "cover": money.format_usd(policy.coverage_limit),
        "deductible": money.format_usd(policy.deductible),
        "premium": money.format_usd(policy.annual_premium),
        "risk_tier": policy.risk_tier,
        "valid_from": str(policy.policy_start_date),
        "valid_to": str(policy.policy_end_date),
        "claims_a_year": brainfreeze.ANNUAL_CLAIM_LIMIT,
        "status": label,
    }


def window_start(args):
    """Where a paged list starts, from `?from=`; the beginning if it is not
    a number."""
    try:
        return max(0, int(args.get("from", 0)))
    except ValueError:
        return 0


def pager(endpoint, start, size, total, **arguments):
    """Which slice of a list is showing, and the links either side of it.

    `templates._PAGER` prints this. The links keep `arguments` -- a filter,
    say -- so paging does not drop it.
    """
    def link(where):
        return url_for(endpoint, **dict(arguments, **{"from": where}))

    return {
        "first": min(start + 1, total),
        "last": min(start + size, total),
        "total": total,
        "previous": link(max(0, start - size)) if start > 0 else None,
        "next": link(start + size) if start + size < total else None,
    }
