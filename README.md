# Brain Freeze Insurance

A small insurance company that covers the cold-stimulus headache, living
entirely inside the database. It exists to answer the question an evaluator
asks once the rabbit is out of the hat: *fine, but can I build an application
on this?*

Three surfaces over one dataset — a Flask app running **inside** GemDB, a
Jupyter notebook, and an MCP server an agent talks to. The point is not the
three surfaces. It is that none of them has a persistence layer: no ORM, no
schema, no migration, no serializer. A handler assigns to an object and
commits.

Every command and every line of output below was run on **2026-09-08** against
a real GemStone/S 3.7.5 stone carrying Grail `c875e56`. Where something
surprised us it is written down rather than tidied away — the
[findings](#what-this-cost-us) cost more time than the code did.

> **A companion document.** [the parallel demo](https://github.com/GemTalk/GemDB_Code/blob/c9c261ac017fd7831cd29aa71b79da4ee8c1ed9b/docs/demo/brain-freeze/) (pinned at `c9c261a`) is a separate,
> earlier walkthrough of the same idea, built independently against Grail
> `5e8fc42`. It covers the quote and claims flows in more narrative detail and
> is worth reading beside this. Where its findings and ours overlap they are
> cross-referenced below; two people hitting the same walls from different code
> is the strongest evidence those walls are real.

---

## Before you start

A terminal opened in VS Code already has `gemdb` on its PATH. Anywhere else:

```sh
export PATH="$HOME/GemDB/bin:$PATH"      # not needed in a VS Code terminal
cd ~/GemTalk/"Brain Freeze Insurance"
```

**Check the database can run a web framework**, because the failure mode is
otherwise baffling:

```sh
gemdb -c 'import re; print("re works:", bool(re.match(r"a+", "aaa")))'
```

```console
re works: True
```

If that says `No module named '_sre'`, stop: the extent has no CPython shim
recorded, and nothing web-shaped will import — not Flask, not Jinja2, not
Werkzeug. The fix is one assignment, not a reinstall; see
[finding 1](#1-a-database-can-be-installed-without-the-regex-engine).

Running the generator additionally needs numpy and pandas, which the model
deliberately does not — `python3 -m pip install --user numpy pandas`. Nothing
else does.

---

## CUJ-0 — Clone and seed

```sh
gemdb seed.py
```

```console
Loaded 900 policyholders and 4993 cold-treat events.

  brain freeze in            3730 of 4993 events (74.7%)
  claims filed               2172
  approved                   1691
  refused                    481
  premium collected          $92081.22
  paid out                   $54671.44
  loss ratio                 0.59

  by tier:
    Low     137 policies   premium $  7564.28   paid $  3094.43   loss ratio 0.41
    Medium  497 policies   premium $ 40456.87   paid $ 29498.98   loss ratio 0.73
    High    266 policies   premium $ 44060.07   paid $ 22078.03   loss ratio 0.50

  BF-100539: 9 events, 8 claims, 4 approved, $179.97 paid, cap 4 of 4 used
Replaced gemdb.root["brainfreeze"]. Committed.
```

That is the whole import story. Two CSVs become ordinary Python objects, one
of them goes in `gemdb.root`, and the session commits. There is no import tool,
no schema to declare and no mapping file.

Quit, start a new session, and the objects are still there:

```sh
gemdb -c 'import gemdb; b = gemdb.root["brainfreeze"]; print(len(b), "policies |", b["BF-100539"].total_paid, "paid |", b.loss_ratio, "loss ratio")'
```

```console
900 policies | 179.97 paid | 0.594 loss ratio
```

**Re-running `gemdb seed.py` is the reset.** It replaces
`gemdb.root["brainfreeze"]` wholesale rather than merging, so a second run
leaves one book of 900 policies, not two. Every step below can be started over
that way, and takes about nine seconds.

### The tests

```sh
python3 -m unittest discover        # everything, under CPython
gemdb run_db_tests.py               # the same tests, inside the database
gemdb run_notebook_check.py         # every notebook cell, in order
```

```console
Ran 225 tests in 0.934s
OK (skipped=48)

Ran 175 tests
OK

All 10 code cells ran.
```

**Running the same suite twice is the demo's central claim reduced to a
check.** One set of rules, two runtimes, identical answers. It matters most
for money: `round()` is half-up inside the database and banker's outside it,
`round(Decimal, 2)` brings the VM down, and `int(Decimal)` floors here and
truncates there. `brainfreeze/money.py` exists so none of that can reach a
premium, and the second run is what proves it.

The 48 skips are the app's tests, HTML and JSON alike: they need a database,
so under plain CPython
the module skips itself and `unittest discover` stays green.

Every figure in those tests was read out of `data/*.csv`, not invented. They
exist to catch the app and the dataset drifting apart.

---

## CUJ-1 — Take out a policy, file a claim

```sh
gemdb app.py
```

Then open <http://127.0.0.1:5000/>. **Start it from the project directory** —
see [finding 3](#3-__main__-is-one-shared-namespace-for-every-script-the-database-has-run).

Answer the five questions at `/quote` — age 11, eats fast, favourite is a
slushie, no headache history — and the app prices all three plans:

```console
Risk band High
scored 75.0
$85.50    Basic
$171.00   Standard
$342.00   Premium
```

Those numbers come from `brainfreeze.quote()`, the same function that priced
the 900 policies in the CSVs. The screen also shows `score_breakdown()`, so the
price explains itself rather than asserting itself.

Take out a plan and the app creates BF-100900 and commits it. That handler is
four lines: build a `Policyholder`, `book.add(...)`, `gemdb.commit()`, redirect.

Now file a claim on **BF-100092** (Active, three of four approvals used):

```console
$55.00 is yours
CLM-002173 · ice cream (Mint choc chip, sprinkles, hot fudge) · 2026-09-08
  What we worked it out at          $67.00
  Trimmed to your $60.00 episode cap -$7.00
  Your deductible                    -$5.00
  Paid to you                        $55.00
```

The claimant never types an amount. `assess_amount()` derives it from the
episode, so two people describing the same headache get the same figure, and
`adjudicate()` applies the rules in order: cover, then the annual cap, then the
per-incident limit, then the deductible.

File a second claim on the same policy and it is refused for the cap. File one
on **BF-100746**, which lapsed on 2026-07-12, and it is refused for the lapse —
and the form says so *before* you fill it in. Cover is bounded by the term as
well as by the lapse, and a claim outside the term is refused for that and told
so in those words, because a policy that never lapsed cannot be refused for
lapsing.

### The same objects over `curl`

Six JSON endpoints sit beside the HTML routes, so a demo can show one object
through a browser and through a shell without a notebook or MCP in the way:

```
GET  /api/questions        the quote questionnaire, as data
POST /api/quote            price a set of answers
GET  /api/policies         the whole book
GET  /api/policy/<id>      one policy and every event under it
GET  /api/claim/<id>       one claim, by claim id alone
GET  /api/stats            book-level aggregates
```

```console
$ curl -s localhost:5000/api/stats
{"policy_count": 900, "event_count": 4993, "claim_count": 2172,
 "approved_claim_count": 1691, "premium": "92081.22", "paid": "54671.44",
 "loss_ratio": 0.594, "claim_approval_rate": 0.7785,
 "loss_ratio_by_tier": {"Low": 0.409, "Medium": 0.729, "High": 0.501}, ...}
```

**Money is an exact decimal string.** `json.dumps` cannot serialise a
`Decimal` at all, so the wire format had to be decided rather than inherited,
and `"92081.22"` is the decision — two places always, no symbol, no grouping,
`null` where no money was recorded. Not a float, which would put back the two
answers the move to `Decimal` removed (issue #68); not integer
cents, which would be exact but would make every reader divide by a hundred.
A string is the same text `money.usd()` already reads, so a figure goes back
into the model unchanged. `money.wire_usd` is the only function that turns
money into text for a payload, and `brainfreeze/wire.py` is the only place
that builds one.

```console
$ curl -s localhost:5000/api/quote -H 'Content-Type: application/json' \
       -d '{"age": 11, "typical_consumption_speed": "fast",
            "favourite_trigger": "slushie"}'
{"answers": {...},
 "quote": {"score": 75.0, "tier": "High", "breakdown": [...],
           "plans": {"Basic":    {"annual": "85.50",  "monthly": "7.13", ...},
                     "Standard": {"annual": "171.00", "monthly": "14.25", ...},
                     "Premium":  {"annual": "342.00", "monthly": "28.50", ...}}}}
```

`"171.00"` is the point of it: `str()` on a Decimal inside the database drops
the trailing zero, so the naive spelling would publish `171.0` there and
`171.00` here — one figure, two answers, which is the failure the whole demo
argues against. `"7.13"` is `85.50 / 12` rounded half-up, by the same rule the
screen and the notebook use.

The JSON surface is **read-only**. `/api/quote` is a POST because it carries a
body; it prices answers and commits nothing. Taking out a policy and filing a
claim stay POSTs from a form, where the redirect after the write is what stops
a refresh re-submitting them.

---

## CUJ-2 — Ask an agent

GemDB's MCP surface is code-level, not data-level: `eval_python`,
`execute_code`, `commit`/`abort`/`refresh`, browsing and search. **There is no
tool that knows what a policyholder is.** An agent answers questions by writing
Python that runs inside the database.

The endpoint is `http://127.0.0.1:50390/mcp` (Streamable HTTP, loopback, no
auth). In a GemDB build that ships the server, `gemdb.mcp.enabled` turns it on
and `gemdb.mcp.port` moves it; **no released GemDB ships it yet**, so this repo
drives the server directly instead:

```sh
python3 refresh_mcp.py                    # upstream vs staged vs installed
python3 refresh_mcp.py --install          # move to the current server
python3 refresh_mcp.py --install --verify # ...and re-ask every promise
```

The server is its own repository on its own schedule, so it moves under this
demo without a line here changing. That is why updating and checking are one
command: `--verify` starts the router, replays every snippet in
`docs/mcp-questions.md` over MCP, compares against the answer printed beneath
it, and stops the router. Nine of nine kept on `0280593`.

It opens exactly **one** session. Each client costs a worker gem, the router
caps them at three, and the stone allows ten.

[`docs/mcp-questions.md`](docs/mcp-questions.md) is the list of questions this
demo promises to answer, with the Python for each. It is **generated by running
them** — `gemdb make_mcp_questions.py` re-seeds, executes every snippet and
writes down what came back — so the answers cannot be typed in wrong, and
regenerating after a change is how the promises get caught drifting.

That file is the answers. [`docs/dataset-for-agents.md`](docs/dataset-for-agents.md)
is the map an agent needs to write its own questions: the object model with the
real field names, why records are found by index rather than by `isinstance`,
the two aggregation traps `analysis.py` exists to avoid, and the `sys.path` line
a worker gem needs and a notebook does not.

The two that carry the demo:

**"Why was CLM-001291 refused?"**

```
[('CLM-001291', 'Policy lapsed', date(2027, 4, 20), date(2027, 3, 10), False)]
```

The reason, the event date, the lapse date and the in-force test. The agent can
*check* the refusal rather than repeat a stored string.

**"What is the loss ratio by risk tier?"**

```
{'Low': 0.409, 'Medium': 0.729, 'High': 0.501}
```

Read that twice. The 1.9× loading on High over-prices the risk it prices for,
so the customers the underwriter worries about most are the most profitable,
and the middle of the book is where the money leaks.

---

### Change a policy while the app is serving it

The same beat on the surface an evaluator is actually looking at. Leave the app
running, open a policy, and in another terminal:

```sh
gemdb lapse.py BF-100184              # lapse it, as of yesterday
gemdb lapse.py BF-100184 --reinstate  # put it back
```

Reload the page. It changes:

```
Active                    ->  Lapsed 2026-09-08
(claim form)              ->  Cover on this policy ended on 2026-09-08.
                              Anything filed now is refused.
```

No restart, no reload of the app, no polling — and `lapse.py` does not know the
app exists. It opens the same objects from a session of its own and commits.
The app takes a new view before each request, so it sees the next one.

It goes back as easily as it goes forward, which is what makes it worth doing
in front of people rather than once.

**This did not work until recently**, and the reason is the interesting part. A
GemStone session sees the repository as of its last transaction boundary, so
the app served whatever it read at startup until it was restarted. It was the
one surface of three that could not see the others' writes. `take_new_view()`
in `app.py` is the fix and this is its payoff.

## CUJ-3 — The notebook, and the beat worth slowing down for

Open [`brain-freeze.ipynb`](brain-freeze.ipynb) and pick **GemDB** in the
kernel picker. That is the entire connection step.

The cell worth stopping on asks a policyholder what it knows about itself:

```console
class            : Policyholder from brainfreeze.model
answers to       : 33 public names
actually stored  : 15
```

`risk_tier`, `total_paid` and `loss_ratio` are not columns that could drift out
of step with the data. They are questions the object answers.

There is no plotting library — Grail has no matplotlib and the kernel renders
`text/plain` — so the chart is ten lines of Python in a cell:

```console
Loss ratio by risk band  (paid / premium)

Low    ███████████████████████████                      0.409
Medium ████████████████████████████████████████████████ 0.729
High   ████████████████████████████████                 0.501
```

### The refresh beat

This is the one thing about sharing a database across three surfaces that is
**not** automatic, so do it deliberately.

1. Run the cell that prints the policy and event counts.
2. Leave the notebook open. Go to the web app and file a claim.
3. Run the same cell again. **Nothing has changed.**
4. Run `gemdb.commit()` then `gemdb.refresh()`, and run it again. Now it has.

Each surface gets its own gem and its own transaction, and a GemStone session
sees the repository as of its last transaction boundary. Your analysis does not
shift under you mid-cell — which is a feature, and will look like a bug the
first time it bites.

**Why `commit()` first.** `gemdb.refresh()` alone will usually refuse here,
with *"refresh() would discard uncommitted changes"* — not because you changed
data, but because Grail compiles your code into the database, so merely having
run the cells above leaves `gemdb.needs_commit()` returning `True`.
`gemdb.abort()` also takes a new view and is the wrong tool: it discards this
session's uncommitted work, **including the functions defined in earlier
cells**. See [finding 4](#4-a-read-only-session-is-not-clean).

**The web app does this for you, on every request.** Its `take_new_view()`
runs the same `commit()` then `refresh()` before each handler, so the browser
needs no beat of its own: commit a change from a notebook cell or a `gemdb -c`
one-liner, reload the page, and it is there. Nothing to restart. The notebook
is deliberately not wired that way — an analysis that shifted under you
mid-cell would be worse than one that waits to be told.

---

## CUJ-4 — Add a field to a live database

The claim form now asks which flavour it was and what was on top. New claims
carry both. The 2,172 claims that came out of the CSVs read `None` and `()`.
Nothing was migrated, nothing was rewritten, and no downtime was needed.

The entire migration is two lines in `brainfreeze/model.py`:

```python
class Claim:
    flavour = None
    toppings = ()
```

**And the honest version of that claim matters.** It works because those
defaults were on the class *before anything was committed*. A claim written
without them has no slot of its own and reads the default through the class.

Adding a field *later* is a different story, and it is worth demonstrating
because it is what a sceptic will try. Add an attribute to `Claim` now, import
the edited source and commit, and:

```console
imported Claim             : <class 'brainfreeze.model.Claim'> 1947956
persisted claim's class    : <class 'brainfreeze.model.Claim'>  309322
SAME CLASS OBJECT?         : False
an existing claim reads it : AttributeError
a NEW claim reads it       : None
```

Editing a class compiles a *different* class. Instances already committed keep
the one they were created under. So the demo's line is not "edit the model and
the database just knows" — it is that a schemaless object database lets you
declare optional fields up front and pay nothing for them later. That is a
claim about foresight, and it is true.

See [finding 5](#5-editing-a-class-compiles-a-different-class) and, for the
same behaviour reached from a model with no class-level defaults, finding 3 in
the companion document.

---

## What this cost us

Five things that were not in any documentation, in the order they cost time.

### 1. A database can be installed without the regex engine

`import flask` failed with `No module named '_sre'`, and so did `import re` —
which is the real problem, since Werkzeug's routing, Jinja2's lexer and header
parsing all need it. The database started, ran Python, seeded and passed every
test, because `brainfreeze/` is standard-library only and never touches `re`.

Nothing was missing from disk. `install.gs` records the shim path only when
`SHIM_LIB_PATH` is non-empty, and `install-grail.sh` blanks that variable when
the file is not there at the moment it looks, then installs anyway with a
warning to a log. Asked directly, the extent said so:

```console
topaz> CPythonShim libraryPath
ERROR 2318 ... reason:halt, CPythonShim library path not configured.
```

The fix is one assignment and a commit, not a reinstall — `install.gs` only
ever records the path, because the shim's built-ins resolve lazily per gem:

```smalltalk
CPythonShim libraryPath: '<GRAIL_DIR>/src/c/shim/libcpython_ua.dylib'.
System commit.
```

The seeded book survived it. A reinstall would have recreated the Python
runtime classes with new identity and orphaned everything.

### 2. An exception in a view is invisible

When a route raises, Flask's error path calls `Logger.error(..., exc_info=...)`
and Grail's `Logger` has no `exc_info`, so the console ends with
`TypeError: Logger.error() got an unexpected keyword argument 'exc_info'` and
the actual exception is further up the log. Scroll past the last traceback.

*(Independently found in the companion document, finding 4.)*

### 3. `__main__` is one shared namespace for every script the database has run

A brand-new script, before defining anything:

```console
__name__ is: __main__
globals before I define anything: ['_band', '_bool', '_date', ..., 'create_app',
 'load', 'main', 'my_cell_helper', 'read_policyholders', 'report', 'run', 'wrap']
```

`create_app` from `app.py`, `load` and `report` from `seed.py`, `run` and
`wrap` from `make_mcp_questions.py` — accumulated in the database across
sessions. Dispatch is by argument count and defaults do not disambiguate, so
`app.py`'s `main()` — declared `main(host=..., port=...)`, called with none —
reached another script's zero-argument `main` and failed inside it.

**Do not name a script's entry point `main`.** This app's is `serve()`.

Relatedly, `gemdb file.py` puts the *script's* directory on `sys.path`, not the
working directory, and a module already compiled into the database can be
served stale in preference to an edited file on disk — `run_db_tests.py` reads
and execs its test module rather than importing it for exactly that reason.

*(The companion document's finding 5 is the same family.)*

### 4. A read-only session is not clean

`gemdb.needs_commit()` returns `True` after merely running code, because Grail
compiles what you run into the database. That is why `refresh()` refuses in a
notebook, and why the recipe is `commit()` then `refresh()` rather than
`refresh()` or `abort()`.

*(Independently found in the companion document, finding 2.)*

### 5. Editing a class compiles a different class

Covered under [CUJ-4](#cuj-4--add-a-field-to-a-live-database). The trap is that
`seed.py` hides it: seeding rebuilds every object from the new class, so no
instance is left holding the old one and a source edit *looks* like it
propagated. It did not; the objects were replaced.

### And one about the sample data

`policy_status` records a policy's fate over its whole term, not whether there
is cover today. The book's terms run either side of the present: of 217
policies marked `Lapsed`, only 53 have actually reached their lapse date, and
147 policies have not started yet. Any screen reading the stored status calls a
policy lapsed while it is still paying claims, so the app compares against the
date and says "Active", "Lapses 2027-03-10", "Lapsed 2026-07-12", "Starts
2026-10-04" or "Term ended 2027-05-30".

---

## What is in here

```
brainfreeze/   the model and the rules; standard library only, runs in the DB
datagen/       the generator; the only numpy/pandas in the repo
data/          the two generated CSVs
tests/         the suite -- python3 -m unittest discover
mockups/       nine screens, an insurer sketch, and build_c.py that makes them
docs/          the PRD, the questions the demo promises to answer, the
               dataset description an agent needs to ask its own, the rules
               for writing Python that runs inside the database, and the
               column dictionary for the two CSVs
findings/      the eight things that cost time, as scripts you can run
app.py         the web app -- the HTML screens and the JSON API
seed.py        data/ -> gemdb.root
PLAN.md        the working notes, including what is still open
```

[`docs/csv-schema.md`](docs/csv-schema.md) is that column dictionary: every
column in `data/*.csv`, its type, whether it can be empty, what it means, and
which attribute it becomes when `seed.py` loads it — plus the `policy_id`
relationship and the six columns that are derived and therefore never loaded.
It is the reference to check a mapping against;
[`docs/dataset-for-agents.md`](docs/dataset-for-agents.md) is the orientation
for asking questions of the objects once they are in the database.

[`docs/writing-python-for-gemdb.md`](docs/writing-python-for-gemdb.md) is its
counterpart for the code itself, and is the one to read first if you are about
to write Python that runs in here. Claude writes good Python; it writes good
*CPython*, and this is not that. Money that ends the session rather than
raising, a `__main__` shared by every script the database has ever run, a
committed module the database then serves forever — with the through-line that
in most of these, **the code that exists to report a problem is the code that
breaks.** The evidence is [`findings/`](findings/README.md), summarised
[below](#what-this-cost-us).

`brainfreeze/` imports nothing outside the standard library and is not allowed
to — it is compiled and run inside the database, where numpy and pandas do not
exist. `tests/test_packaging.py` fails if anything in it reaches for a module
Grail does not ship.

The dataset is regenerated with `python3 -m datagen`, whose output is
byte-identical run to run:

```console
Wrote 900 policyholders -> policyholders.csv
Wrote 4,993 events -> claims.csv
```

If that output ever stops matching what is committed, either the change was
wrong or the dataset is being regenerated deliberately — and if it is the
latter, say so loudly, because every figure in `mockups/` and every number in
the tests is read out of these two files.
