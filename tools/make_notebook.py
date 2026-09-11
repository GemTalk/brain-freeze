"""Generate brain-freeze.ipynb.

    python3 tools/make_notebook.py

The notebook is generated rather than hand-edited for the same reason
`mockups/build_c.py` generates the screens: a .ipynb is JSON with the source
split into per-line strings, and editing that by hand invites exactly the
drift this repo keeps testing for. Change the cells here.

Outputs are deliberately left empty. A notebook shipped with saved output is a
screenshot; this one has to be run against a live database, which is the point
of it.
"""

import io
import json
import os

#: This one writes a file and imports nothing of ours, so it needs the
#: repository's location but not its place on `sys.path`.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTEBOOK = os.path.join(REPO, "brain-freeze.ipynb")


MD = "markdown"
PY = "code"

CELLS = [
    (MD, """# Brain Freeze Insurance, from the inside

This notebook runs **inside the database**. There is no connection string, no
driver, no query language and no result set to unpack — the kernel *is* a
GemStone session, and `gemdb.root` is the database's root namespace. The
objects below are the same objects the web app reads and writes.

Pick the **GemDB** kernel in the kernel picker. That is the whole of the
connection step."""),

    (PY, """import gemdb

book = gemdb.root["brainfreeze"]
book"""),

    (MD, """## There is no schema to introspect

That is not a boast, it is the thing to look at. Ask a policyholder what it
knows about itself and you get 30-odd names — but only about half are *stored*.
The rest are computed on the way out, from the rules in `brainfreeze`.

No table, no columns, no migration: `risk_tier` and `total_paid` are not
fields that could drift out of step with the data, they are questions the
object answers."""),

    (PY, """policy = book["BF-100539"]

public = [name for name in dir(policy) if not name.startswith("_")]
stored = sorted(vars(policy))

print("class            :", type(policy).__name__, "from", type(policy).__module__)
print("answers to       :", len(public), "public names")
print("actually stored  :", len(stored))
print()
print("stored on the instance:")
print("   ", ", ".join(stored))
print()
print("derived on demand (a sample):")
for name in ("risk_tier", "underwriting_risk_score", "total_paid",
             "loss_ratio", "claims_remaining_this_year"):
    print("    %-26s %s" % (name, getattr(policy, name)))"""),

    (MD, """`asFloat` and `mro` in the full list are not ours — they leak in from the
Smalltalk side, because these really are GemStone objects rather than Python
objects in a wrapper."""),

    (MD, """## Three aggregates

The helpers live in `brainfreeze.analysis` so that the notebook, the web app
and an agent over MCP all answer these the same way. Deriving them inline is
easy to get subtly wrong — see the notes on weighting and on `min_events`."""),

    (PY, """from brainfreeze import analysis

analysis.book_summary(book)"""),

    (PY, """# 1. How the book splits by risk band.
tiers = {}
for holder in book:
    tiers[holder.risk_tier] = tiers.get(holder.risk_tier, 0) + 1

for tier in ("Low", "Medium", "High"):
    print("%-7s %3d policies" % (tier, tiers.get(tier, 0)))"""),

    (PY, """# 2. Loss ratio by band -- and this one is worth a second look.
analysis.loss_ratio_by_tier(book)"""),

    (MD, """Read that again. **High is cheaper to carry than Medium.**

The 1.9x loading on the High band over-prices the risk it is pricing for, so
the customers the underwriter is most worried about are the most profitable,
and the middle of the book is where the money leaks. That is a real finding
about this data, not a scripted one — and it is the kind of thing that is
tedious to reach through an ORM and trivial when the objects are just there."""),

    (PY, """# 3. What an approved claim is actually worth.
#
# Money here is decimal.Decimal, not float -- see brainfreeze/money.py.
# `statistics.median` and `statistics.mean` do not merely fail on a Decimal
# inside the database, they END THE SESSION ("a Decimal does not understand
# #'_generality'"), so the middle is taken by hand. Printing goes through
# format_usd, which restores the trailing zero that str() drops.
from brainfreeze.money import ZERO, format_usd, round_cents

paid = sorted(claim.approved for claim in book.claims if claim.is_approved)
middle = len(paid) // 2
if len(paid) % 2:
    median = paid[middle]
else:
    median = round_cents((paid[middle - 1] + paid[middle]) / 2)
mean = round_cents(sum(paid, ZERO) / len(paid))

print("approved claims   :", len(paid))
print("min / median / max:", format_usd(paid[0]),
      "/", format_usd(median), "/", format_usd(paid[-1]))
print("mean              :", format_usd(mean))"""),

    (MD, """## A chart, with no plotting library

Grail has no matplotlib and the kernel renders `text/plain`, so a chart here is
a chart you draw yourself. Ten lines, and it says as much as an image would."""),

    (PY, """def bar_chart(pairs, width=48, fmt="%.3f"):
    \"\"\"A horizontal bar chart in text. `pairs` is (label, value).\"\"\"
    if not pairs:
        return
    biggest = max(value for _, value in pairs) or 1.0
    label_width = max(len(str(label)) for label, _ in pairs)
    for label, value in pairs:
        filled = int(round(width * value / biggest))
        print("%-*s %-*s %s" % (label_width, label, width,
                                "\\u2588" * filled, fmt % value))


ratios = analysis.loss_ratio_by_tier(book)
print("Loss ratio by risk band  (paid / premium)\\n")
bar_chart([(tier, ratios[tier]) for tier in ("Low", "Medium", "High")
           if tier in ratios])"""),

    (PY, """# Severity, in $10 bands -- where the payouts actually cluster.
#
# `int(amount // 10)` would be the obvious way to band these, and Grail has no
# floor division for Decimal -- it raises TypeError. `int()` truncates toward
# zero, which is the same thing for money that is never negative.
bands = {}
for amount in paid:
    low = int(amount / 10) * 10
    bands[low] = bands.get(low, 0) + 1

print("Approved claim amounts\\n")
bar_chart([("$%d-%d" % (low, low + 9), bands[low]) for low in sorted(bands)],
          width=40, fmt="%d")"""),

    (MD, """## The refresh beat

This is the part worth doing slowly, because it is the one thing about sharing
a database across three surfaces that is *not* automatic.

Every notebook, the web app and each MCP client gets its own gem and its own
transaction. A GemStone session sees the repository as of its last transaction
boundary — so work another session commits is **not** visible here until this
session takes a new view. That is a feature (your analysis does not shift under
you mid-cell) but it will look like a bug the first time it bites.

Run the next cell, then go and file a claim in the web app, then run it again."""),

    (PY, """print("policies:", len(gemdb.root["brainfreeze"]))
print("events  :", len(gemdb.root["brainfreeze"].events))"""),

    (MD, """Nothing moved — even though the app committed. Now take a new view.

**`gemdb.refresh()` on its own will usually refuse here**, with *"refresh()
would discard uncommitted changes"*. That is not because you changed any data:
Grail compiles your code into the database, so simply having run the cells
above leaves this session with uncommitted work and `gemdb.needs_commit()`
returning `True`.

`gemdb.abort()` also takes a new view, and it is the wrong tool — it discards
this session's uncommitted work, **including the functions defined in the cells
above**. `bar_chart` would stop existing.

So: commit first, then refresh."""),

    (PY, """print("needs_commit before:", gemdb.needs_commit())

gemdb.commit()     # keep this session's compiled cells
gemdb.refresh()    # then take the new view

book = gemdb.root["brainfreeze"]
print("policies:", len(book))
print("events  :", len(book.events))
print("bar_chart still defined:", callable(bar_chart))"""),

    (MD, """There it is. The claim filed in the browser is in the notebook's objects,
with no export step, no reload, and no serialisation format in between — but
only once this session deliberately asked for it.

That last point is the honest version of "one dataset, three surfaces": the
objects are genuinely shared, *and* each surface has its own transaction."""),
]


def cell(kind, source):
    lines = source.split("\n")
    body = [line + "\n" for line in lines[:-1]] + [lines[-1]]
    if kind == MD:
        return {"cell_type": MD, "metadata": {}, "source": body}
    return {"cell_type": PY, "execution_count": None, "metadata": {},
            "outputs": [], "source": body}


notebook = {
    "cells": [cell(kind, source) for kind, source in CELLS],
    "metadata": {
        "kernelspec": {"display_name": "GemDB", "language": "python",
                       "name": "gemdb"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

path = NOTEBOOK
with io.open(path, "w", encoding="utf-8") as handle:
    json.dump(notebook, handle, indent=1, ensure_ascii=False)
    handle.write("\n")

print("Wrote %s (%d cells: %d markdown, %d code)" % (
    os.path.basename(path), len(CELLS),
    sum(1 for k, _ in CELLS if k == MD),
    sum(1 for k, _ in CELLS if k == PY)))
