"""What every page needs: rendering, and how to describe a policy's cover.

Here rather than in app.py so the routes can reach them by name on every
request -- `pages.render(...)` -- and pick up a change once it is loaded and
committed. When app.py passed them in, the routes held the functions app.py
had at startup. See routes.py.
"""

from flask import render_template_string

import brainfreeze
import brainfreeze.money as money


def render(template, **context):
    """Render, with `usd` available to every template to format money.

    Money is Decimal, and `str()` on one drops the trailing zero, so `$170.10`
    would print as `170.1`. (`'%.2f'|format` would have handled that -- printf
    on a Decimal works here, contrary to what this docstring claimed for a
    while. `format(x, '.2f')` is the spelling that raises.) `format_usd` is
    used instead because it is the only one that also copes with `None`.

    It arrives in the CONTEXT rather than as a Jinja filter or global, and
    that part IS measured. `app.jinja_env.filters["usd"] = ...` does not work,
    for a reason that has nothing to do with money: Flask's `jinja_env` is a
    `cached_property`, and Grail realises cached_property WITHOUT caching, so
    `app.jinja_env is app.jinja_env` is False. Every read builds a fresh
    Environment and the registration is written to one that is discarded.
    `jinja_env.globals` is lost the same way, which is why it appears to be
    silently ignored.

    Until Grail#895 that also KILLED THE GEM rather than merely failing: the
    unknown filter raised, and jinja2's error reporting called
    `code.replace(co_name=...)` on a `compile()` result that Grail answers as
    source text, landing on `str.replace` called by keyword, which read past
    the end of an empty array. Reporting the error was what ended the session.
    """
    return render_template_string(template, usd=money.format_usd, **context)


def cover_state(policy, today):
    """How to describe this policy's cover, as of a date.

    `policy_status` records the fate of a policy over its whole term, and the
    sample book's terms run either side of the present -- of 217 policies
    marked Lapsed, only 53 have actually reached their lapse date. So a screen
    that reads the stored status calls a policy lapsed while it is still
    paying claims. Compare against the date instead and say which it is.

    The term counts too, at both ends: 147 of the 900 policies have not
    started yet today, and calling those "Active" says cover is running when
    a claim filed against them would be refused.
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
