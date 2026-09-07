# Brain Freeze Insurance — build plan

A demo application for the **GemDB Code** VS Code extension: a mock insurance
product covering kids and teens against brain freeze, exercised through three
surfaces over one live database — a Flask app running *inside* the database, a
Jupyter notebook, and an MCP server that VS Code agent mode talks to.

This file is the handover. It says what exists, what is decided, what is still
open, and what to build next. The PRD (`PRD_ Brain Freeze Insurance.docx`) is
the requirements document; where this file and the PRD disagree, this file is
newer and says why.

---

## The point of the demo

The PRD frames the goal as "three surfaces over one dataset". That is the
mechanism. The goal is to make an evaluator feel that **there is no
persistence layer** — no ORM, no schema, no migration, no serializer — and
every other database demo they have seen spends most of its code on exactly
that gap.

That reframes what each surface is for:

- the web app is the conspicuous *absence* of an ORM: a handler assigns to an
  object and commits;
- the notebook is the same objects, live, from another process, with no export
  step;
- MCP is an agent writing Python that runs *inside* the database;
- CUJ-4 is the punchline: adding a field costs nothing.

The failure mode is not technical. It is that this reads as a toy CRUD app
using an odd database. It needs at least one held-up moment where a normal
stack requires machinery and this one requires none.

---

## Where things are

Everything is in this repo, `~/GemTalk/Brain Freeze Insurance`, on `main`.

```
brainfreeze/   the model and the rules; standard library only, runs in the DB
datagen/       the generator; the only numpy/pandas in the repo
data/          the two generated CSVs
tests/         the suite -- python3 -m unittest discover
mockups/       nine screens, an insurer sketch, and build_c.py that makes them
docs/          the PRD
seed.py        data/ -> gemdb.root
PLAN.md        this file
```

| Path | What it is | State |
| --- | --- | --- |
| `brainfreeze/underwriting.py` | risk score, tiers, plan terms, premiums | done |
| `brainfreeze/adjudication.py` | the claim rules: lapse, cap, limit, deductible | done |
| `brainfreeze/model.py` | `Book`, `Policyholder`, `Event`, `Claim` | done |
| `brainfreeze/analysis.py` | the named questions an agent composes | done |
| `datagen/` | sampling only; internal tool, the only numpy/pandas in the repo | done |
| `data/` | `policyholders.csv`, `claims.csv` — 900 policies, 4,993 events | done, **regenerated 2026-09-07** |
| `seed.py` | `data/` → objects in `gemdb.root`, with a smoke test | done, **verified against a real database** |
| `tests/test_brainfreeze.py` | 16 tests pinning the model and the rules | done |
| `tests/test_seed.py` | 22 tests pinning the load | done |
| `tests/test_packaging.py` | 1 test pinning the numpy/pandas boundary | done |
| `mockups/` | nine screens + insurer sketch, and `build_c.py` | done, **redrawn for BF-100539** |
| `app.py` | seven routes over `gemdb.root`, templates inline | done, **runs and serves** |
| `tests/test_app.py` | 18 tests through Flask's test client | done |
| `run_app_tests.py` | runs those inside the database | done |
| the notebook | — | **not started** |
| the MCP server wiring | — | **not started** |
| the README that sequences CUJ-0→4 | — | **not started** |

`policyholders.xlsx` / `claims.xlsx` — the spreadsheets the dataset was first
delivered as — **were deleted on 2026-09-07**. They had gone stale at the
regeneration and described a different dataset from the one the repo loads,
which is worse than not having them. They are still in git history at
`9abef51` if the original delivery is ever wanted.

### The two commands that must keep working

```sh
python3 -m unittest discover                       # 39 tests (18 skip)
gemdb run_app_tests.py                             # 18 more, in the DB
gemdb app.py                                       # serve on :5000
python3 -m datagen                                 # rewrites both CSVs
```

The generator needs **numpy and pandas**, which the model deliberately does
not — that split is now structural: it lives in `datagen/`, which is the only
package in the repo permitted to import them, and
`tests/test_packaging.py` fails if anything in
`brainfreeze/` reaches for a module Grail does not have. (Verified the way a
guard should be: with numpy imported into `brainfreeze/model.py`, that test
failed and all 22 others still passed. Nothing else covers this.) They are not on a stock macOS `python3`; `python3 -m pip install --user
numpy pandas` is enough, and keeps the command above working as written rather
than hiding it behind a virtualenv. Verified with numpy 2.0.2 / pandas 2.3.3
on CPython 3.9.6.

The generator's output is **byte-identical** to the committed CSVs — checked
by running it twice and `cmp`-ing. That is load-bearing: it is the proof that
pulling the model out of the generator changed no behaviour. If a change to
`brainfreeze/` alters the CSVs, either the change is wrong or the dataset is
deliberately being regenerated — and if it is the latter, say so loudly,
because every figure in `mockups/` and every number in the tests comes from
the current CSVs. It has been regenerated deliberately once, on 2026-09-07;
see "The dataset regeneration" below.

---

## Architecture, and why

### The web app runs inside the database

Grail — the Python implementation GemDB ships — bundles Flask, Werkzeug,
Jinja2 and requests in its standard library, and Grail's own
`grail_rest_demo/` is a working Flask app with an HTML UI and a JSON API over
one store. So the app is not a server that talks to GemDB; it is Flask
executing as GemStone Smalltalk, with the domain objects being the database's
objects. `gemdb app.py` starts it. Routes read and write `gemdb.root` and
commit.

**Rejected, with reasons:**

- **FastAPI** — modern FastAPI needs pydantic v2, whose core is a Rust
  extension. There is no pure-Python fallback, so it cannot run under Grail at
  any effort level. The last FastAPI on pure-Python pydantic is 0.99.x
  (mid-2023). uvicorn is out regardless: it calls `loop.create_server`, the
  transports half of asyncio that Grail does not have.
- **Starlette without FastAPI** — pure Python, but pulls anyio, and Grail's
  asyncio has `tasks`, `taskgroups`, `locks`, `queues`, `runners`, `timeouts`
  and no transports, streams or subprocess. Unknown bottom.
- **Bare ASGI on `grail_asgi`** — genuinely available (`grail_asgi.py` is in
  Grail's stdlib and its docstring explains it exists *because* the goal is
  FastAPI), and it has no consumers anywhere in the Grail tree. Attractive,
  and rejected only because Flask is proven and the risk budget belongs to
  GemDB's story rather than to being `grail_asgi`'s first user. Revisit if
  Flask disappoints.
- **Django** — too heavy; drags settings, an app registry and an ORM pointed
  at nothing.

### The CPython shim is a prerequisite, and it can be silently absent

**Hit on 2026-09-07, on this machine, and it stopped work item 2 dead until it
was diagnosed.** Everything above assumes Flask imports. It does not, unless
the database has Grail's CPython shim recorded.

The symptom is unhelpful:

```sh
gemdb -c 'import flask'   # No module named '_sre'
gemdb -c 'import re'      # No module named '_sre'
```

`_sre` is the regex engine. `re` is not optional for anything web-shaped —
Werkzeug's routing, Jinja2's lexer and header parsing all need it — so Flask,
and every alternative in the rejected list above, fail together. A database in
this state starts fine, runs Python fine, seeds fine, and passes all 39 tests,
because `brainfreeze/` is standard-library only and never touches `re`. That
is why the seeding work was finished before anyone noticed.

The cause is not a missing file. The shim was present at exactly the path
`shimLibraryPath()` computes, the right architecture, and the installer is
handed `SHIM_LIB_PATH` through `engineEnvironment()`. What had happened is
that the path was never *recorded in the extent*: `install.gs` runs
`CPythonShim libraryPath:` only when `SHIM_LIB_PATH` is non-empty, and
`install-grail.sh` quietly blanks that variable when the file is not there at
the moment it looks:

```sh
if [ -n "$SHIM_LIB_PATH" ] && [ ! -f "$SHIM_LIB_PATH" ]; then
    echo "WARNING: no prebuilt CPython shim at $SHIM_LIB_PATH." >&2
    export SHIM_LIB_PATH=""      # installs anyway, without C extensions
fi
```

Ask the database directly rather than guessing:

```
topaz> CPythonShim libraryPath
ERROR 2318 ... reason:halt, CPythonShim library path not configured.
```

**The fix is one assignment, not a reinstall.** `install.gs` only ever records
the path — the shim's built-ins resolve lazily per gem — so setting it and
committing is sufficient, and it leaves the seeded book untouched:

```smalltalk
CPythonShim libraryPath: '<GRAIL_DIR>/src/c/shim/libcpython_ua.dylib'.
System commit.
```

After that, `import re` answers, `from flask import Flask` answers, and a
Flask `test_client()` renders a `render_template_string` route to a 200 inside
the database. The 900-policy book was still there afterwards, unchanged.

Two things follow for the demo:

- **CUJ-0 needs a preflight.** An evaluator whose extent is in this state gets
  `No module named '_sre'` from the app and has nothing to go on. One line in
  the README, or a check in `seed.py`, is worth more than a paragraph of
  troubleshooting later.
- **This is worth reporting against GemDB_Code.** The install degrades to a
  database that cannot run any web framework, and says so only as a warning to
  a log — `~/GemDB/grail/install.out` was empty here. Failing the install, or
  recording the absence somewhere a later session can see, would turn a day of
  archaeology into a sentence.

### Three constraints the Flask app inherits

All three are documented in `grail_rest_demo/app.py`, which found them first:

1. **`threaded=False`.** Grail renders each Jinja template in a forked green
   thread, and the threaded dev server's per-request `contextvars.ContextVar`
   cannot span those threads — so `url_for` inside a template cannot see the
   active request. One CPU per gem means threading buys nothing anyway.
2. **One request per connection.** Use their `CloseAfterResponseHandler`. A
   single-threaded server parked reading a kept-alive connection cannot accept
   the next one, so a second tab or a favicon fetch hangs everything.
3. **Inline templates only.** `render_template_string` is tested in Grail's
   suite (`FlaskScaffoldingTestCase.gs`, tier 4). File-based
   `render_template` and `FileSystemLoader` appear once, in a comment about
   path assembly, and are never exercised end to end. Keep templates as module
   constants the way the reference app does. A `templates/` directory would
   make you the first to try it.

Because the app is single-threaded and shares one session, transaction
handling is simple: one request at a time, commit at the end of a write
handler, abort on exception. No locking story to invent.

### The model is standard-library only

`brainfreeze/` imports nothing outside the standard library, and must stay
that way, because it runs inside the database where **numpy and pandas do not
exist**. `datagen/` is the only thing allowed to import them; it does the
sampling and calls into `brainfreeze` for every deterministic decision.

The boundary is enforced rather than asserted — see `tests/test_packaging.py`. Its
allowlist is not "the standard library" but the modules PLAN.md records Grail
as actually having, because Grail ships a partial one: a `subprocess` import
would pass a stdlib check and still fail inside the database.

Grail *does* have `math`, `random` and `statistics` (native Smalltalk
implementations with their own test cases — `RandomTestCase.gs`,
`MathTestCase.gs`), plus `csv` and `decimal`. Note one gap if you ever need
it: **`random.choices` (weighted, plural) is missing** — only uniform
`choice` and `sample` exist.

---

## The class-identity check: answered, and it holds

**Run on 2026-09-07 against a real database. It passes, completely.** Build on
this shape; nothing below needs the fallback the earlier draft of this section
described.

```sh
export PATH="$HOME/GemDB/bin:$PATH"   # gemdb is installed but not on PATH
                                      # outside VS Code terminals
gemdb seed.py
# quit, start a new session
gemdb -c 'import gemdb; print(gemdb.root["brainfreeze"]["BF-100539"].total_paid)'
# 179.97
```

Three things were checked, and the second and third are the interesting ones.

**The objects survive the session.** A new gem reads `total_paid` and gets
`179.97`, matching the CSVs and `tests/test_seed.py`. (The check was first run
against BF-100023 and `193.43`, before the regeneration below thinned that
policy out. The figures here are the current ones, so the commands above can
be pasted as they stand.)

**They survive without the source.** Run from `/tmp`, where `brainfreeze` is
not on `sys.path` and cannot be imported, a persisted policyholder still
reports `<class 'brainfreeze.model.Policyholder'>` and still answers
`total_paid`, `risk_tier` and `repr(book)` — and `risk_tier` is a derived
property that reaches through `model.py`'s module globals into
`underwriting.risk_tier` and `COVERAGE_PLANS`. So it is not just the instance
data that is in the database. The compiled class, its methods, and the module
namespace those methods close over are all in there too. The database is
holding the *code*, not a pickle of the attributes.

**A later import binds to the same class, and does not orphan anything.** This
was the actual risk, and it is clear:

```
persisted instance class : <class 'brainfreeze.model.Policyholder'>
freshly imported class   : <class 'brainfreeze.model.Policyholder'>
SAME OBJECT?             : True      # type(p) is Policyholder
isinstance?              : True
book / claim / event class same? : True / True / True
```

`import brainfreeze.model` in a fresh session rebinds to the *same class
object* the committed instances already point at. It does not compile a
second class. That is what makes the Flask app viable as one plain module:
a handler can `isinstance`-check, construct a new `Claim`, and hang it off a
policyholder loaded from 2024's seed, and they are the same type.

**The CUJ-4 default already reads on pre-existing data.** On a claim committed
before the fields existed, `claim.flavour` is `None` and `claim.toppings` is
`()` — the class attributes answer through instances that have no slot of
their own. Work item 5's premise is confirmed before it is built.

### Re-running is the reset

`gemdb seed.py` twice in a row leaves **one** book: `root` keys are
`['greeting', 'brainfreeze']`, one `brainfreeze` entry, 900 policies, 5,017
events, 2,239 claims, `total_paid` 62461.02. The second run prints `Replaced`
rather than `Wrote`. FR-8.3 needs no separate command. A full seed takes about
**9 seconds**.

(`greeting` is left over from the rabbit-in-the-hat demo sharing this extent.
Harmless, but if a screenshot ever shows `gemdb.root`, it will be in it.)

### Editing a class does not update the database — read this before CUJ-4

**Found the hard way on 2026-09-07, and it changes how a live edit must be
demonstrated.** Grail persists the *compiled class*, not just the instances.
Editing `brainfreeze/model.py` changes nothing inside the database until some
session imports that module **with the source on `sys.path`** and commits.

While `model.py` had been edited but nothing had re-imported it from source:

```
underwriting_risk_score  -> 44.8     # the OLD stored attribute, not the new
                                     # derived property that replaced it
is_in_force_on           -> AttributeError: no attribute 'is_in_force_on'
```

...and that was in a session that had run `from brainfreeze.model import
Policyholder` first. The import bound to the stale persisted class and said
nothing. `type(p) is Policyholder` was still `True` the whole time — identity
is not the tell, and there is no warning.

The variable that mattered was **where the script lives**, because that is
`sys.path[0]`. A script in `/tmp` cannot see `brainfreeze/`, so its import
resolves out of the database and silently gets the old class. `gemdb seed.py`,
run from the project directory, found the source, recompiled, and committed —
after which *every* session sees the new class, including ones that still
cannot see the source.

So the rule is:

> After editing anything in `brainfreeze/`, run something from the project
> directory that imports it and commits — `gemdb seed.py` does — before
> trusting what any other session reports.

Two consequences worth carrying forward:

- **CUJ-4's premise survives, but for a narrower reason than decision 2
  assumes.** `Claim.flavour = None` costs nothing *because it was already on
  the class when the class was first committed*. Adding a class attribute
  later is not free in the same way — it needs that recompile-and-commit
  first. "Add a field, nothing to migrate" is true; "edit the source and the
  database just knows" is not, and demonstrating the second by accident will
  produce a screen that has not changed.
- **The Flask app must be started from the project directory**, or it will run
  against whatever class the database last compiled.

One unrelated Grail gap found alongside it: `import brainfreeze.model as m`
fails with `local variable referenced before assignment`, and plain `import
brainfreeze.model` leaves the name undefined. `from brainfreeze.model import
Policyholder` is the form that works. Worth knowing before writing a notebook
cell.

### What this buys the demo

This is the held-up moment the top of this file says is missing. The pitch is
not "objects persist" — every database says that. It is: *quit the process,
delete the source directory from the path, come back, and the objects still
compute.* No ORM, no schema, no migration, no serializer, and no source tree
either. That belongs in the README, demonstrated rather than asserted.

## The dataset regeneration (2026-09-07)

The CSVs were regenerated deliberately, once, to settle open decision 3 and the
`policy_status` incoherence. Two changes went in, and they are worth keeping
apart because only one of them moved any numbers.

### `underwriting_base` — a new column, and nothing else changed

The generator drew each policyholder's starting point from `normal(45, 15)` and
threw it away, so a score in the dataset could not be reproduced from the
answers beside it. It is now written out.

Recording it consumes no randomness, so this change was **provably inert**:
`claims.csv` came back byte-identical, `policyholders.csv` gained exactly one
column, and **zero** values changed in any pre-existing column across all 900
rows. The 26 tests then in the suite passed untouched.

`Policyholder.underwriting_risk_score` is now **derived** from that base rather
than stored, so there is one source of truth: change a weight in
`underwriting.py` and every score moves with it. `tests/test_seed.py` pins the
derivation against the CSV column for all 900 policies — that test is the
drift detector the conventions section asks for.

The base is written at full float precision on purpose. Rounding it would let
the derived score and the stored column disagree in the last decimal, which is
exactly what the drift test exists to catch.

> Worth knowing: the base was recoverable by arithmetic anyway, since every
> other term is a lookup from a stored column — it round-tripped for 900 of
> 900. Deriving it at load time was rejected regardless, because a later edit
> to any weight would be silently absorbed by the derived base, leaving the
> stored scores unmoved and the model looking inert. A stored base makes that
> same edit visible.

### The lapse date — this one moved everything

A quarter of the book was `Lapsed` with no lapse date while claims went on
being approved to the end of the term. Policies now carry
`policy_lapse_date`, and cover stops there.

**Events still happen after a lapse** — a child does not stop eating ice cream
because a policy ended — so the denominator `model.py` argues for is intact.
What changes is that a claim on a post-lapse event is refused with a new,
fourth adjudication rule:

```python
adjudicate(..., policy_in_force=False)   # -> "Policy lapsed", pays 0.00
```

Checked **before** the annual cap, because a claimant is owed the reason that
actually applies. It lives in `brainfreeze.adjudication`, not the generator, so
the app, the agent and the sample data cannot disagree about it. The parameter
defaults to `True`, so every existing call reads as it did.

This shifted the RNG stream, so the whole claims table is new:

| | before | after |
| --- | --- | --- |
| events | 5,017 | 4,993 |
| claims | 2,239 | 2,172 |
| approved | 1,959 | 1,691 |
| paid | $62,461.02 | $54,671.44 |
| loss ratio | 0.678 | 0.594 |
| brain-freeze events | 3,854 | 3,730 |

`policyholders.csv` did **not** move: every pre-existing column is unchanged,
because the lapse draws happen after all policy attributes are settled. Only
`claims.csv` and the two new columns are different.

254 claims are now refused for `Policy lapsed`, making it the most common
denial reason in the book — ahead of the annual cap's 183.

### The exemplar changed: BF-100023 → **BF-100539**

BF-100023 came out of the regeneration thin: 4 events, 1 claim, $55 paid, no
cap refusal, no longer loses money. Every mockup was drawn from it.

BF-100539 replaces it, and is a better subject than the original was — its
history runs through every rule in order, in date order, on one screen:

```
CLM-001285  2026-07-28  Approved  $34.19
CLM-001286  2026-08-29  Approved  $35.78
CLM-001287  2026-09-12  Approved  $55.00
CLM-001288  2026-12-05  Approved  $55.00
CLM-001289  2027-02-13  Denied    Exceeded annual claim limit
CLM-001290  2027-02-21  Denied    Exceeded annual claim limit
            2027-04-17            (not claimed)
CLM-001291  2027-04-20  Denied    Policy lapsed
CLM-001292  2027-05-14  Denied    Policy lapsed
```

Standard plan, Medium band 65.2, $98.10 premium, $179.97 paid, loss ratio
1.83, lapsed 2027-03-10. `mockups/build_c.py`, the hand-maintained
`DirectionB.dc.html` and `mockups/README.md` are all updated and regenerated;
no stale figure survives anywhere in `mockups/`.

One honesty fix went with it: the History screen used to close by saying the
no-headache events were on the table. All nine of BF-100539's treats caused
one, so it now points at the unclaimed 17 April episode and cites the book-wide
1,263 of 4,993 instead.

### Still open in the dataset

`FileClaim.dc.html` shows BF-100539 with "3 of 4 claims used", which is
honestly the moment before CLM-001288 was filed and flows into the approved
Decision card. But the policy is lapsed by the end of its own history, so if
the app ever lets you file against it live, it will refuse. Either pick an
Active policy for that screen or make the refusal the point.

---

## Decisions still open

These need a human. Do not guess them.

1. **The repo and its visibility.** Still open — public
   `GemTalk/brain-freeze-insurance`, new-but-private until the FR-8.4 naming
   gate clears, or a directory inside `GemDB_Code`.

   As of 2026-09-07 `origin` is
   `git@github.com:srbaker/brain-freeze-insurance-demo.git` — a personal repo,
   not the `GemTalk` org, and **nothing has been pushed**. `main` has no
   upstream set, so a bare `git push` does nothing by accident. Treat that
   remote as a placeholder rather than the answer: it does not settle where
   this ends up living, and the naming gate still applies.
2. **What CUJ-4 demonstrates.** Grail keeps Python attributes in *dynamic*
   instance variables, so adding `flavour` is not a class version and there is
   nothing to migrate — FR-7.2 and FR-7.3 are satisfied vacuously. Either own
   that ("this is what a schemaless object database means", and the one real
   lesson is the class-level default) or manufacture a contrast by modelling
   claims as a Smalltalk class with declared instVars. The mockups and
   `Claim.flavour = None` currently assume the first. **Read "Editing a class
   does not update the database" first** — the vacuous-migration story holds,
   but only because those defaults were on the class before it was ever
   committed, which is a narrower claim than "schema changes are free".
3. ~~**The random base.**~~ **Settled 2026-09-07: recorded as a column.** See
   "The dataset regeneration" below. FR-5.3 is now satisfiable — a quote taken
   from an existing policyholder's answers reproduces that policy's score and
   tier exactly, and `tests/test_seed.py` pins it for all 900.
4. **Whether the claim form warns when the annual cap is spent.** Right now
   the only way to find out is to file and be refused. Note this now has a
   sibling: the form does not warn when the *policy has lapsed* either, and
   that refusal is the more confusing one to receive silently.

---

## Work items, in order

### 1. Seed against a real database — **DONE (2026-09-07)**

Both halves pass; the findings are written up under "The class-identity check"
above. A fresh session reads `BF-100539.total_paid` as `179.97`, importing the
package binds to the same class as the committed instances, and a second
`gemdb seed.py` replaces rather than doubles.

Nothing here blocks work item 2 any more.

### 2. The Flask app — **DONE (2026-09-08)**

`gemdb app.py` serves seven routes on :5000. A quote is taken end to end, a
policy created, a claim filed and adjudicated, and both persist. Verified over
real HTTP, not just the test client:

```
POST /quote      -> 75.0, High, $171.00, with the breakdown
POST /policies   -> BF-100901, committed, "Nothing yet" history
POST .../claims  -> CLM-002176: assessed $73.00, -$13.00 to the $60 cap,
                    -$5.00 deductible, "$55.00 is yours"
same, lapsed     -> warned first, then "Not this time / Policy lapsed"
```

Every figure is `brainfreeze`'s: `assess_amount(8, 300)` is 73.00, and
`adjudicate` does the rest. `tests/test_app.py` has 18 tests through Flask's
test client, run by `gemdb run_app_tests.py`; under CPython the module skips
itself so `python3 -m unittest discover` stays green.

**Five things worth knowing before touching it.**

*The `__main__` guard has to be the last thing in the file.* `gemdb app.py`
executes top to bottom, so a guard next to `main()` starts the server before
the template constants exist and every route raises `NameError`. Importing the
module hides this completely -- an import finishes the file before any route
runs -- so the test suite passed while the server was broken. Run it, do not
just test it.

*Grail's logging masks the real error.* When a view raises, Flask's handler
calls `Logger.error(..., exc_info=...)`, and Grail's Logger has no `exc_info`,
so the console shows `TypeError: Logger.error() got an unexpected keyword
argument 'exc_info'` and the actual exception is further up the log. Scroll
past the last traceback to the first.

*Rendering 900 rows takes about a minute.* Grail renders each Jinja template
in a forked green thread and 900 table rows is not what that is for. The
picker pages 25 at a time with a lookup box, and answers in ~1.6s. The count
is the point, not the scroll.

*`policy_status` is not "is there cover today".* The sample book's terms run
either side of the present: of 217 policies marked Lapsed, only 53 have
actually reached their lapse date. A screen reading the stored status calls a
policy lapsed while it is still paying claims, so `app.cover_state()` compares
against the date and says "Active", "Lapses <date>" or "Lapsed <date>".

*A package submodule can go stale where a top-level module does not.* Editing
`tests/test_app.py` had no effect run after run -- `from tests import
test_app` kept returning the previously compiled module -- while edits to
top-level `app.py` in the same tree took effect immediately. `run_app_tests.py`
therefore reads the file and execs it rather than importing it. This is the
same family as "Editing a class does not update the database", and the
difference between the two cases is not yet explained; it is worth pinning
down before CUJ-4 asks anyone to edit a module and watch the database notice.

**Still open:** the claim form warns for both the cap and the lapse (decision
4, settled), and the demo's two exemplars are BF-100092 (Active, one approval
left) and BF-100746 (lapsed 2026-07-12, cap not spent, so its refusal is
unambiguous). BF-100539 remains the mockups' policy but lapses in 2027, so it
cannot demonstrate a live lapse refusal.

### 3. The notebook

Schema introspection, load the book, at least three aggregates (tier
distribution, loss ratio by tier, claim severity distribution) and one chart.
FR-3.2 is already free — GemDB registers a Jupyter kernel against VS Code's
built-in notebook type, so the connection step is "pick GemDB in the kernel
picker".

Then script **the refresh beat** as a deliberate act, not a footnote: file a
claim in the web app, re-run the notebook cell, see nothing, call refresh, see
it. Every notebook, the app and each MCP client gets its own gem and its own
transaction; §5 of the PRD currently promises cross-surface visibility just
works, and it does not. This is the moment that proves the objects are shared
*and* transactional.

A good aggregate to include, because the answer is surprising: loss ratio by
tier is **Low 0.41, Medium 0.73, High 0.50** (post-regeneration). The 1.9×
High loading over-prices it, so the riskiest customers are the most
profitable — Medium is the band losing money relative to its price. A second
one now worth showing beside it: loss ratio by `policy_status`, since lapsed
policies keep paying premium and stop being able to claim.

**Done when:** the pre-built cells run clean on a seeded database and the
refresh beat is written into the README as a sequence of steps.

### 4. MCP

The offered tool surface is code-level, not data-level: `eval_python`,
`compile_python`, `execute_code`, `commit`/`abort`/`refresh`/`status`,
browsing and search. **There is no tool that knows about policyholders.** An
agent answers "loss ratio by risk tier" by writing Python and running it
through `eval_python`.

That works, and it is the better story, but it needs help. **The helpers are
done (2026-09-08)**: `brainfreeze/analysis.py` gives the agent named questions
to compose rather than derive -- `book_summary`, `loss_ratio_by_tier`,
`loss_ratio_by_plan`, `least_profitable_plan`, `claim_approval_rate`,
`denial_reasons`, `top_n_by_expected_claims`, `top_n_by_loss_ratio`. All
exported from `brainfreeze`, standard-library only, 15 tests pinned to figures
read out of `data/` by a separate script, and verified running inside the
database against the live book rather than only under CPython.

Two choices in there an agent deriving the same thing would get wrong, which
is the argument for shipping them at all. Group loss ratios sum premium and
payout and then divide, rather than averaging ratios -- averaging weights a
$45 policy the same as a $342 one. And `top_n_by_expected_claims` takes a
`min_events` floor, because a policy with two cold treats and two approved
claims scores 1.0; without the floor the ranking is a list of the shortest
histories in the book. Quote the floor along with the answer.

Rates come back `None` rather than 0.0 when there is nothing to divide by. The
app creates policies with no events, so an empty book is reachable, and 0.0
would assert that every claim was refused.

**Still to do here:** ship the list of questions the demo promises will work,
and verify each one against `tests/test_seed.py`'s figures.

Connection: the server forks with the database and appears in VS Code agent
mode on its own. For any other client the whole step is
`http://127.0.0.1:8787/mcp` (Streamable HTTP, loopback, no auth). Claude Code
takes that directly; **Claude Desktop probably needs an `mcp-remote` shim —
verify before documenting it.**

**Watch the session budget.** The ceiling is ten: the MCP front end takes one,
each connected client one, each open notebook one, each GemDB Shell one, the
Flask app one, and the seed script one while it runs. A user mid-CUJ-4 with
two notebooks open sits around six.

**Done when:** at least four representative questions return correct,
data-grounded answers, and the answers can be checked against
`tests/test_seed.py`'s figures.

### 5. CUJ-4

Add `flavour` (string) and `toppings` (list) to the claim capture flow;
`mockups/ClaimV2.dc.html` is the target screen. `Claim.flavour = None` and
`Claim.toppings = ()` are already class attributes in `brainfreeze/model.py`
— that is the entire migration, and the reason is worth stating in the docs:
a claim written before the fields existed has no slot of its own, so without
the class-level default, reading `claim.flavour` raises `AttributeError`.

Then answer FR-7.5 honestly by observation: what do the notebook and the MCP
surface actually do when the schema changes underneath them? Write down what
happened, including "nothing".

**Part of this is already answered, and it is not "nothing".** Changing
`model.py` under a live database was done accidentally during the
regeneration, and the observed behaviour is in "Editing a class does not
update the database": committed instances keep answering, a new method is
simply absent, and an import from a directory that cannot see the source hands
back the stale class without complaint. Reproduce it deliberately for the
demo — it is more interesting than the field-addition it was meant to
illustrate, and an evaluator who edits a file and sees no change will hit it
whether or not it is scripted.

**Done when:** new claims carry flavour and toppings, the 2,239 existing
claims still read, and the finding is documented.

### 6. README and the PRD edits

`README.md` sequences CUJ-0 → 4 with copy-pasteable commands (FR-8.2).
`docs/demo-rabbit-in-the-hat.md` in `GemDB_Code` is the house style: every
command and every line of output was run against a real database, and where
something surprised the author it is noted rather than tidied away. Hold this
demo to that.

**The PRD needs five corrections.** They are not cosmetic — an agent building
to the PRD as written will build the wrong thing:

- **FR-2.1 – FR-2.4 (CSV import) are obsolete.** `seed.py` is the whole
  mechanism; there is no import tool, no idempotency question beyond "it
  replaces", and no separate smoke-test step.
- **FR-4.5 "read-only by default" is not achievable.** `readOnly: true` drops
  both Python tools (`McpGrailToolset` inherits an empty
  `readOnlySafeToolNames`), which removes the reason to install it at all, and
  `commit`/`abort` are in the offered set. The honest claim is "we ship it no
  claim-filing tools, and it could still write anything; treat it like a
  shell." GemDB's own design spec says exactly this.
- **FR-4.1's "documented command" does not exist.** The server forks with the
  database and disappears when it stops.
- **FR-3.2 is already satisfied.** No connection step to document.
- **FR-5.2 should not ask for `sex`.** It is in the CSVs and carries no weight
  in the risk model, so the form would pose a question that changes nothing.
  The mockups leave it out.

~~Also worth fixing in the dataset while you are there: `policy_status`...~~
**Done 2026-09-07** — policies carry `policy_lapse_date` and cover stops
there. See "The dataset regeneration".

---

## Conventions

- **Tests pin real data, not invented data.** Every figure in
  `tests/test_brainfreeze.py` and `tests/test_seed.py` was read out of the CSVs. Keep it
  that way — the tests exist to catch the app and the dataset drifting apart,
  and a test full of round numbers cannot do that.
- **`brainfreeze/` stays standard-library only.** No numpy, no pandas, no
  third-party anything. It runs inside the database.
- **The app never reimplements a rule.** If a handler computes a premium or a
  payout, that is a bug: two copies of "what does this claim pay" drift by the
  second demo, and CUJ-2 asks an agent to explain a refusal — an answer it
  cannot give if the app and the data disagree about the rules.
- **`mockups/build_c.py` generates the screens** from one set of design
  tokens. Change a colour or a type size there, not in ten HTML files.
- **The generator is an internal tool.** It is not part of the user journey;
  CUJ-0 is "clone, seed", not "generate". It lives in `datagen/` and writes to
  the repo root whatever directory it is run from, so a stray `python3 -m
  datagen` cannot quietly produce a dataset nothing loads.

## A note on the environment

The bridge this repo was built through cannot delete files, so `git` cannot
clear its own `index.lock` — a commit made from an agent session may need
`rm .git/index.lock` by hand first. Nothing in the repo depends on this; it is
just a thing that will waste ten minutes otherwise.
