"""What every page needs: rendering, how to describe a policy's cover, the
fields of an ID card, and a window onto a long list.

Here rather than in app.py so the routes reach them by name on every
request -- `pages.render(...)` -- and pick up a loaded change. See routes.py.

THE TEMPLATES ARE FILES

`web/templates/` holds the pages as Jinja templates: `base.html` is the frame
every page extends, `_macros.html` the pieces they share, `app.css` the
stylesheet. They are read through one Environment that `create_app` makes
and keeps on the app, not through Flask's `render_template`: Grail's
`cached_property` does not cache, so every read of `app.jinja_env` would
build a fresh Environment and compile every template again, and anything
registered on it would be lost.

Kept, the Environment keeps its compiled templates, and a page renders in
hundredths of a second instead of most of one. It still checks each file's
modification time, so an edited template is live on the next request --
no `tools/load.py`, and no restart. Grail reports that time in whole
seconds, so a second save within the same second can go unseen until the
file is saved again.
"""

import jinja2
from flask import current_app, url_for

import brainfreeze
import brainfreeze.money as money

#: Where the Environment lives on the app: `app.extensions[TEMPLATES]`.
TEMPLATES = "brainfreeze.templates"


def usd(value):
    """Money for a page: `$170.10` whatever places the Decimal carries, and
    `--` for None. A function that looks `format_usd` up on each call, so a
    loaded change to money.py reaches pages without a restart."""
    return money.format_usd(value)


def environment(folder):
    """The Environment the pages render through, reading `folder`.

    Autoescaping everything, the SVG card included. `url_for` and `usd` are
    globals, so every template and macro has them.
    """
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(folder),
                             autoescape=True, auto_reload=True)
    env.globals.update(url_for=url_for, usd=usd)
    return env


def render(template, **context):
    """Render the named template from `web/templates/`."""
    env = current_app.extensions[TEMPLATES]
    return env.get_template(template).render(**context)


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



#: The longest name the ID card prints. Longer is cut, not wrapped: the
#: card is an image, and a name that runs into the next column spoils it.
CARD_NAME_LIMIT = 24


def card_name(wanted, policy):
    """The subscriber name on a card: what the holder typed, tidied, or a
    stand-in from the policy when they typed nothing.

    The book records no names, so a name is the reader's, for the card they
    share, and goes no further than the card: it is never stored.
    """
    name = " ".join((wanted or "").split())[:CARD_NAME_LIMIT].strip()
    return name or "Member, age %d" % policy.age


def id_card(policy, today, name=None):
    """What the ID card prints, as display strings.

    The only thing `templates/id_card.svg` reads, so a new design for the card
    is a new SVG over these fields and nothing else. Every figure is the
    policy's own, formatted the way every other page formats it. `name` is
    the subscriber name the holder typed, if any.
    """
    label, _css = cover_state(policy, today)
    return {
        "policy_id": policy.policy_id,
        "plan": policy.plan_name,
        "subscriber": card_name(name, policy),
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

    The `pager` macro in `templates/_macros.html` prints this. The links keep `arguments` -- a filter,
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
