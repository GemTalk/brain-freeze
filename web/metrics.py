"""Numbers for the monitoring agent, in Prometheus's text format.

    metrics.exposition([
        ("brainfreeze_policies", "gauge", "Policies on the book.", [({}, 900)]),
        ("brainfreeze_claims", "gauge", "Claims filed, by outcome.",
         [({"outcome": "approved"}, 1585), ({"outcome": "refused"}, 587)]),
    ])

A family is `(name, kind, help, samples)` and a sample is `(labels, value)`.
`routes_ops.py` gathers them from the book and the database; this only
writes them down, so it is standard library only and `tests/test_metrics.py`
checks it under CPython as well as inside the database.

The deployed agent (brain-freeze-deploy's node/ops-agent.yaml) reads this
through the proxy and sends it to Cloud Monitoring, where each family becomes
`prometheus.googleapis.com/<name>/<kind>`.
"""

#: What `/metrics` answers with: the text format, version 0.0.4.
CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def exposition(families):
    """The whole page, one family after another, ending in a newline."""
    lines = []
    for name, kind, help_text, samples in families:
        lines.append("# HELP %s %s" % (name, escape_help(help_text)))
        lines.append("# TYPE %s %s" % (name, kind))
        for labels, value in samples:
            lines.append("%s%s %s" % (name, label_set(labels), number(value)))
    return "\n".join(lines) + "\n"


def label_set(labels):
    """`{a="1",b="2"}`, sorted so a page reads the same every time; empty
    for no labels at all."""
    if not labels:
        return ""
    return "{%s}" % ",".join('%s="%s"' % (key, escape_value(labels[key]))
                             for key in sorted(labels))


def number(value):
    """An int as an int, anything else as a float, as the format reads them.

    `bool` first: True is an int, and "True" is not a number.
    """
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    return repr(float(value))


def escape_help(text):
    return text.replace("\\", "\\\\").replace("\n", "\\n")


def escape_value(text):
    return (str(text).replace("\\", "\\\\").replace('"', '\\"')
            .replace("\n", "\\n"))
