"""Write down everything the book holds, so two databases can be compared.

    gemdb ci/upgrade_record.py

Used by ci/upgrade.sh before and after GemDB moves to a new engine: if the
two records differ, something stored was lost or changed.

Prints one `REC` line per stored object -- every policy, event, claim and
quote, the identifier series and the root's keys -- in a fixed order, and a
`COUNTS` line. Each object is written as ALL of its own stored attributes
(`vars`), not a chosen few, so a slot that went missing shows up even where
nobody thought to look; `flavour` and `toppings` are also read through the
class, since step 3 puts them there.

Values are spelled out by hand rather than with `repr`: the record is compared
across two Grail versions, and a repr that changed spelling between them would
read as data that changed.
"""

from datetime import date, datetime
from decimal import Decimal

import gemdb


def spell(value):
    if value is None or value is True or value is False:
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return "f%.12g" % value
    if isinstance(value, Decimal):
        return "D%s" % value
    if isinstance(value, str):
        return '"%s"' % value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return "[%s]" % ", ".join(spell(v) for v in value)
    if isinstance(value, dict):
        return "{%s}" % ", ".join("%s: %s" % (spell(k), spell(value[k]))
                                  for k in sorted(value))
    # A stored model object inside another one (an event's claim): named by
    # its identifier here, written out in full on its own line.
    for key in ("claim_id", "event_id", "policy_id", "quote_id"):
        if key in own(value):
            return "<%s %s>" % (type(value).__name__, own(value)[key])
    return "<%s>" % type(value).__name__


def own(obj):
    try:
        return vars(obj)
    except TypeError:
        return {}


def record(kind, obj, also=()):
    fields = dict(own(obj))
    for name in also:
        fields.setdefault(name, getattr(obj, name, None))
    print("REC %s %s" % (kind, ", ".join("%s=%s" % (k, spell(fields[k]))
                                         for k in sorted(fields))))


def main():
    root = gemdb.root
    print("REC root keys=%s" % spell(sorted(root.keys())))
    book = root["brainfreeze"]
    record("book", book, also=("serials",))

    policies = sorted(book, key=lambda p: p.policy_id)
    events = claims = flavoured = 0
    for policy in policies:
        fields = dict(own(policy))
        fields.pop("events", None)
        print("REC policy %s, events=%d" % (
            ", ".join("%s=%s" % (k, spell(fields[k])) for k in sorted(fields)),
            len(policy.events)))
        for event in policy.events:
            events += 1
            record("event", event)
            if event.claim is not None:
                claims += 1
                record("claim", event.claim, also=("flavour", "toppings", "rule"))
                if getattr(event.claim, "flavour", None):
                    flavoured += 1

    quotes = getattr(book, "quotes", None) or {}
    for quote_id in sorted(quotes):
        record("quote", quotes[quote_id], also=("policy_id",))

    print("COUNTS policies=%d events=%d claims=%d quotes=%d flavoured=%d"
          % (len(policies), events, claims, len(quotes), flavoured))


main()
