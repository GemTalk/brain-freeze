# Adding a feature, with an agent

The demo line is *"I didn't write any code — I told the agent to add toppings
and flavours."*

That is a claim about working with a coding agent against this codebase, and
without this file it rests on the agent guessing right. The guess usually fails
in the same two places: the agent puts the field somewhere reasonable and never
learns that the database is still running last week's module, or it adds the
field to a class whose instances were committed months ago and gets an
`AttributeError` in front of whoever it was demonstrating to.

Neither of those is a Python problem, so no amount of good CPython habit
prevents them. They are consequences of one fact — Grail compiles your code
into the database and keeps it — worked out into a procedure.

This document is the procedure. Its two companions are
[`writing-python-for-gemdb.md`](writing-python-for-gemdb.md), which is what the
runtime will do to the code you write, and
[`dataset-for-agents.md`](dataset-for-agents.md), which is what the objects are
called and what is in them. Read this one when you are about to **change** this
repository. It does not repeat either of them; where a fact belongs to one of
them it is linked, not restated.

---

## This is not the MCP server's job

Worth saying before anything else, because conflating the two is what makes
this demo hard to explain.

**MCP is how you talk to GemDB.** The surface is code-level — `eval_python`,
`execute_code`, `commit`/`abort`/`refresh`, browsing and search — so you answer
a question by writing Python and running it inside the database. There is no
tool in it that opens a file, and there is no file in this repository it can
edit. See §1 of [`dataset-for-agents.md`](dataset-for-agents.md) for what that
surface actually offers.

**Modifying Python source is ordinary coding-agent work.** A checkout, an
editor, a shell, `git`. Nothing on this page needs the MCP server running, and
an agent doing this work needs the repository rather than a connection.

The two meet at exactly one point, and it is §4 below: once the source has
changed, something has to make the database run it. That something is a `gemdb`
command in a shell. It is not an MCP call.

---

## 1. What "add a field" actually cost, twice

Two real instances, in this repository's history, with different costs. The
contrast is the lesson, so both are here rather than a rule.

### The free one: `flavour` and `toppings` (CUJ-4)

The claim form now asks which flavour it was and what was on top. New claims
carry both; the 2,172 claims loaded from the CSVs read `None` and `()`.

What the commit that did it (`d3c62cb`) actually touched:

```
 PLAN.md           | 89 ++++++-----
 app.py            | 31 +++++-
 tests/test_app.py | 50 ++++++
```

**No change to `brainfreeze/model.py` at all.** `Claim.flavour` and
`Claim.toppings` had been on the class since the first model commit
(`adac376`), before anything was ever committed to the database:

```python
class Claim:
    flavour = None
    toppings = ()
```

So the work was a form, a template, a handler and four tests. And because
`app.py` is a top-level script rather than a module inside a package, restarting
`gemdb app.py` was the whole of the deployment:

```sh
# stop the running app, then
gemdb app.py
python3 -m unittest discover
gemdb run_db_tests.py
```

Note what did *not* have to happen: no `gemdb redeploy.py`, because no package
module changed, and no `gemdb seed.py`, because every existing claim reads the
default through the class it was made under.

That is the honest version of the demo line. It is not "edit the model and the
database just knows". It is that a schemaless object database lets you declare
optional fields up front and pay nothing for them later — a claim about
foresight, and true.

### The expensive one: `SavedQuote` and `Book.quotes` (#53)

`POST /quote` used to price a quote, render it, and post the five answers back
to the browser as hidden fields so that buying could work them out again. A
quote had nowhere in the book to live. Giving it somewhere took three commits
(`2c9ad81`, `2677516`, `76579e8`) and touched:

```
 brainfreeze/model.py      | +125    SavedQuote, Book.quotes, Book.add_quote
 brainfreeze/__init__.py   |   +3    export SavedQuote
 app.py                    | +129    the routes
 redeploy.py               |  +28    the ORDER check
 tests/test_brainfreeze.py | +101
 tests/test_app.py         | +113
 tests/test_api.py         |  +10
 tests/test_quote_flow.py  | +145    new
 README.md                 |  +13
```

This one paid both costs, and they are separate costs with separate fixes.

**Cost one: `model.py` is inside a package, so the database was still serving
the old compiled copy.** `gemdb redeploy.py` is the fix — §4.

**Cost two: `Book.quotes` is a new field on an object that was already
committed.** The book in `gemdb.root["brainfreeze"]` was built before `quotes`
existed. A class-level default declared now does not reach it: editing a class
compiles a *different* class, and instances keep the one they were made under
(§3). So the fix is `gemdb seed.py`, which rebuilds every object from the new
code.

The order matters and the app says so out loud. From `app.py`:

```python
    def _quotes(the_book):
        try:
            return the_book.quotes
        except AttributeError:
            abort(500, "This book was committed before quotes had a class of "
                       "their own. Run `gemdb redeploy.py` to give the "
                       "database the current brainfreeze package, then "
                       "`gemdb seed.py` to rebuild the book under it.")
```

Two things about that handler are worth copying rather than admiring. It lets
the `AttributeError` happen instead of reaching for `getattr(the_book,
"quotes", {})`, which would have quietly started a second store on the side and
lost every quote written into it. And the message names the two commands,
because the reader who meets a bare `AttributeError` here will otherwise
reasonably conclude the code is broken. `Book.add_quote`'s docstring says the
same thing for a reader coming from the model rather than from the browser.

### The third shape, and the one to expect: `Claim.rule` (#49)

A refusal now records *which rule* refused it, as a stable identifier, beside
the English sentence in `reason`. Same one-line class default as `flavour`:

```python
class Claim:
    rule = None
```

But it was declared **after** 2,172 claims were committed, and those claims were
not going to be rebuilt — they are the sample history, and reseeding is the
demo's reset button rather than a step in a feature. So the migration was
written as a *read* instead of a write. From `brainfreeze/analysis.py`:

```python
        rule = getattr(claim, "rule", None)
```

with a fallback through `adjudication.rule_for_reason(claim.reason)` for a claim
that predates the field. `analysis.denial_rules` does both, and §3 of
[`dataset-for-agents.md`](dataset-for-agents.md) tells an agent reading the book
to do the same.

So there are three answers to "how much does a field cost", not two: nothing,
one reseed, or every read of it going through `getattr` forever. Choose
deliberately and say which one you chose.

---

## 2. The two questions to ask about any change

Everything above collapses into these.

**Is the file you edited inside `brainfreeze/`?** Then the database is serving a
compiled copy of it and your edit is not live. Run `gemdb redeploy.py`.
Top-level scripts — `app.py`, `seed.py`, `run_db_tests.py`, `lapse.py`,
`verify_book.py` — are read from disk each time `gemdb` runs them, so restarting
is enough for those. `findings/08_script_imports.py` measures the difference and
is blunt about where it comes from: writing an `__init__.py` beside a module is
the whole of it.

**Does the change add or alter a field on a class whose instances are already
committed?** Then a class-level default will not reach those instances. Either
`gemdb seed.py` to rebuild them, or read the field through
`getattr(record, "field", default)` everywhere, forever. There is no third
option that this repository has measured.

`gemdb seed.py` replaces `gemdb.root["brainfreeze"]` wholesale. It throws away
every policy bought and every claim filed since the last seed. That is fine
before a demo and rude in the middle of one.

---

## 3. Where a new field goes, and why the default is free only once

A new field on a model goes in `brainfreeze/model.py`, on the class, **as a
class attribute with a default, above `__init__`**. `Claim` is the worked
example:

```python
class Claim:
    flavour = None
    toppings = ()

    def __init__(self, claim_id, requested, approved, status, reason=None,
                 flavour=None, toppings=None, rule=None):
        ...
        if flavour is not None:
            self.flavour = flavour
        if toppings is not None:
            self.toppings = tuple(toppings)
```

The load-bearing part is the two lines above `__init__`. An instance with no
slot of its own reads the default through its class, so a claim written before
the field existed answers `None` rather than raising. That is the entire
migration, and `app.py` says so where the form constants are defined.

**Why that is the only moment a default is free.** Editing a class and importing
the edited source compiles a *different* class. Measured, and reproduced by
[`findings/03_class_identity.py`](../findings/03_class_identity.py):

```
imported Claim             : <class 'brainfreeze.model.Claim'> 1947956
persisted claim's class    : <class 'brainfreeze.model.Claim'>  309322
SAME CLASS OBJECT?         : False
an existing claim reads it : AttributeError
a NEW claim reads it       : None
```

Instances committed under the old class keep their data, raise `AttributeError`
for the new field, and are no longer `type(record) is TheClass`. On Grail
`c875e56` they are not `isinstance(record, TheClass)` either — which is a
version difference rather than a settled fact, and finding 3 prints what your
build does. `type(obj).__name__` survives either way, which is why the rule is
to find records by index rather than by `isinstance` (§5 of
[`dataset-for-agents.md`](dataset-for-agents.md)).

So a default declared before the first commit costs nothing and one declared
afterwards reaches only new objects. `docs/prd-corrections.md` correction 5 is
the long form of this, and it is the correction to make to anyone who reads
FR-7.2 as "no migration, ever".

**`seed.py` hides this.** Seeding rebuilds every object from the new class, so
no instance is left holding the old one and a source edit *looks* like it
propagated. It did not; the objects were replaced. Do not conclude from a green
run after a reseed that the edit reached anything.

Three more things about where a value goes, all from the model as it stands:

- **Money goes through `usd()`**, which refuses a float outright. Money enters
  the model at `Claim`, at `Policyholder` and at `SavedQuote`, and nowhere else
  — those three calls are the whole guarantee that none of it is a float. A
  ratio is not money and stays a float. `brainfreeze/money.py` and the money
  section of [`writing-python-for-gemdb.md`](writing-python-for-gemdb.md) say
  what you may and may not do with a `Decimal` in here; two of the obvious
  spellings take the session down rather than raising.
- **Derived values are properties, not stored fields.**
  `Policyholder.underwriting_risk_score` is recomputed from the recorded
  answers, so changing a weight moves it rather than leaving a number frozen at
  seed time.
- **Except when the value is a promise made on a date.** `SavedQuote` stores all
  twelve prices rather than deriving them, because a customer must be sold what
  they were shown. The docstring on the class argues it out. If you are adding
  something, decide which of those two it is and write down why.

---

## 4. A change is not live until the package is redeployed

Issue #62 called this "the crux and still open". **It is settled and has been
since [`findings/08_script_imports.py`](../findings/08_script_imports.py) was
written.** What remains open is a different question — see the end of this
section.

Grail compiles the Python you run into the database, as a repository write.
Committing is what makes the database *keep* the compiled copy and hand it to
every later session. So once `brainfreeze` has been imported and committed once,
it is deployed: a brand-new session, a new process, an edited file on disk, and
`import brainfreeze` still returns what the database compiled. Nothing reports
the difference.

That cost the whole of the money work — the database went on returning
`31.499999999999996` from a float `annual_premium` for an hour after the file on
disk returned exact `Decimal`, with every test passing against rules that were
no longer anywhere on disk.

The commit is the mechanism, and it is not optional either: the first draft of
finding 8 had no `commit()` in it and concluded there was no problem, and
`findings/class-identity/` establishes that you *must* commit after your imports
or instances you write are stranded on a class the next session will not
recognise. Both pieces of advice are right. Freezing your code is the price of
stabilising your classes.

The escape:

```sh
gemdb redeploy.py
```

It is `importlib.reload` in dependency order, then a commit. Two details are
load-bearing. Order matters, because reloading a module re-executes it and while
that happens the modules importing it cannot resolve it — reload a leaf first,
or the dependent raises `ImportError: module ... is canonical (deployed)`. And
each reloaded module has to be put back into `sys.modules` by hand, because
`reload` leaves a deployed module absent from it. Deleting from `sys.modules` is
not a substitute and makes it worse: the module cannot be imported again for the
rest of the session.

**If you add a new module to `brainfreeze/`, add it to `ORDER` in
`redeploy.py`.** You will be told: `unlisted_modules()` compares `ORDER` against
the directory and refuses to run until they agree. That check exists because
`brainfreeze.wire` arrived with the JSON API and sat unlisted, so anyone editing
it and redeploying would have kept the old compiled copy with nothing to say so
— the exact failure the script prevents, reintroduced one module at a time.

`redeploy.py` prints `annual_premium('Basic','Low')` and whether it is exact
money at the end, which is a real check rather than a reassurance: if that line
says otherwise, the database is still running older code.

**What redeploy does not do is migrate anything.** Objects already committed keep
the class they were made with. That is why the pair is two commands and not one:
`gemdb redeploy.py` changes the rules, `gemdb seed.py` rebuilds the data those
rules made.

**What is still open** is issue #59: whether there is a recipe that re-binds
*already committed instances* to an edited class without rebuilding them. Nobody
has measured one. `findings/class-identity/` has the two arms that would answer
it and has not been pointed at the question. Until that changes, "migration"
here means a reseed or a `getattr`, and saying otherwise in front of an
evaluator is a guess.

---

## 5. Entry points must not be named `main`

Every script runs as `__main__`, `__main__` is compiled into the database and
kept, and a new script therefore starts with the accumulated globals of every
script this database has ever run — across sessions and across processes
([finding 2](../findings/02_main_namespace.py)).

Combined with the second half: **Grail dispatches by argument count, and default
values do not disambiguate.** A function declared `main(host="...", port=5000)`
and called as `main()` is a zero-argument call, and can resolve to a *different*
script's zero-argument `main`. That is not hypothetical — `gemdb app.py` once
failed with `name 'PREAMBLE' is not defined`, a global belonging to
`make_mcp_questions.py`, because `app.py`'s `main()` reached the question
generator's `main` and died inside it.

So: **give a script's entry point a name the file owns.** In use here:
`serve()`, `generate()`, `refresh()`, `seed_database()`, `redeploy()`,
`lapse()`, `verify_book()`, `run_db_tests()`, and one per findings script.

Two qualifications, both real:

- **The rule is about code the database runs.** `datagen/dataset.py` still has
  `def main()` and is right to: `datagen` is the CPython-only generator, run as
  `python3 -m datagen`, and never enters the database at all.
- **Nothing checks this.** There is no test for it — `tests/test_packaging.py`
  pins the import boundary, not entry-point names. Renaming them also did not
  clean the database: finding 2 still reports a zero-argument `main` inherited
  from the versions that ran before the rename, and it will stay until the
  extent is rebuilt. The namespace is repository state, not process state.

While you are near the bottom of a script: **the `if __name__ == "__main__":`
guard goes at the very end of the file.** `gemdb app.py` executes top to bottom,
so a guard sitting next to `serve()` starts the server before the templates
below it exist and every route raises `NameError` — and importing the module for
a test hides it completely.

---

## 6. How to run the tests, and why there are two of them

```sh
python3 -m unittest discover        # under CPython
gemdb run_db_tests.py               # the same files, inside the database
gemdb run_notebook_check.py         # every notebook cell, in order
.venv-acceptance/bin/behave         # the acceptance suite, in a real browser
```

Measured in this checkout on 2026-09-10, the first is `Ran 251 tests ... OK
(skipped=57)`. The 57 skips are the tests that need a database, so they skip
themselves under CPython and the run stays green; the second command runs those
too, which is why it reports 194. (Issue #62's "22 of them" is stale — that was
before the JSON API, the quote flow and the rule identifiers arrived.)

**Running the same suite twice is not belt-and-braces.** It is the demo's central
claim reduced to a check: one set of rules, two runtimes, identical answers. It
matters most for money, where `round()` is half-up inside the database and
banker's outside it, and `int(Decimal)` floors here and truncates there. A suite
that only runs under CPython proves nothing about the runtime the application
ships on; a suite that only runs in the database cannot tell you the two agree.

`run_db_tests.py` reads each test module from disk and `exec`s it into a fresh
namespace rather than importing it, because of §4: the database serves a stale
compiled copy of an imported module, and `tests/` is a package. A runner that
silently tests the previous version of the tests is worse than no runner.
`gemdb run_db_tests.py money seed` runs a subset.

**The acceptance suite** (`features/`) drives the real app in a real browser and
leaves screenshots in `artifacts/`. It needs its own virtualenv because it
carries a browser:

```sh
python3 -m venv .venv-acceptance
.venv-acceptance/bin/pip install behave playwright
.venv-acceptance/bin/playwright install chromium
```

It owns its whole environment: it reseeds the book, starts `gemdb app.py`, runs
the scenarios, stops the app, and **fails the run if port 5000 is still open
afterwards**. Three things follow for anyone adding a feature.

- It refuses to start if something is already listening on 5000 rather than
  reusing it, so **stop your own app first**. A run that silently tested a stale
  server would be worse than no run.
- A leaked app is a leaked GemStone session and the stone allows ten. Do not
  start a second app "just to check".
- It reseeds, so anything you were demonstrating is gone.

If you add a user-visible feature, it belongs in a `.feature` file. The
screenshots are evidence of a run, not documentation — the app renders today's
date, so identical passing runs differ tomorrow. The feature files are the
documentation, and every scenario in there was checked by breaking the thing it
exists to catch.

---

## 7. The surfaces that have to stay in agreement

The demo's argument is one dataset, several surfaces, one answer. A change that
moves one of them and not the others breaks that in front of an audience rather
than in a test.

| surface | what it is | what pins it |
| --- | --- | --- |
| the web app | `app.py` — HTML routes and inline templates | `tests/test_app.py`, `features/*.feature` |
| the JSON API | `brainfreeze/wire.py` serialises; `app.py` routes it | `tests/test_api.py` |
| the notebook | generated by `make_notebook.py` — **never edit `brain-freeze.ipynb` by hand** | `gemdb run_notebook_check.py` |
| the MCP answers | `docs/mcp-questions.md`, generated by `gemdb make_mcp_questions.py` | `python3 refresh_mcp.py --verify` replays it over the transport |
| the dataset description | `docs/dataset-for-agents.md`, `docs/csv-schema.md` | by hand — nothing checks these |
| the seeded figures | `data/*.csv` | `tests/test_seed.py`, `tests/test_analysis.py`, `EXPECTED` in `verify_book.py`, and the answers printed in `docs/mcp-questions.md` |
| the package boundary | `brainfreeze/` imports nothing Grail lacks | `tests/test_packaging.py` |

The figures a freshly seeded book returns — 900 policies, 4,993 events, 2,172
claims, 1,691 approved, `$92,081.22` premium, `$54,671.44` paid, loss ratio
`0.594` — appear in all four of the places on that "seeded figures" row. Every
one of them was read out of `data/*.csv` by a separate script rather than taken
from what the functions returned. If you change the model's arithmetic, expect
to move all four, and expect `verify_book.py` to be the one that catches you,
because it reads the committed graph from a session that has never seen a CSV.

Two cautions about regenerating:

- **`gemdb make_mcp_questions.py` re-seeds first, deliberately.** The answers
  have to describe a freshly seeded database rather than whatever the last demo
  left behind. It is not a step to run casually.
- `docs/mcp-questions.md` publishes `analysis.denial_reasons`' exact output,
  which is why #49 added `denial_rules` as a sibling rather than changing that
  function's shape. A published answer is a promise; adding beside it is cheap
  and moving it is not.

**Not every change touches every surface.** `flavour` and `toppings` never
reached the notebook or the MCP questions, and nothing was wrong with that —
they are a claim-capture detail, not an analysis one. Check the list rather than
dutifully editing all of it.

---

## What this document does not know

Said plainly, because a confident wrong answer here is expensive.

- **Whether committed instances can be re-bound to an edited class.** Nobody has
  measured a recipe. That is issue #59, and it is the only part of #62 that was
  genuinely blocked. Until it is measured, a "migration" here is a reseed or a
  `getattr`.
- **Whether `isinstance` survives a class edit on your Grail.** It does not on
  `c875e56`; the parallel demo measured it surviving on `46c2a68`. Run
  [finding 3](../findings/03_class_identity.py) rather than trusting either.
- **Whether the `if flavour is not None:` guard in a constructor buys anything
  beyond consistency.** For an object built after the field exists, assigning
  `None` outright and letting the class default stand read the same. The class
  attribute above `__init__` is what is load-bearing; the guard's cost or
  benefit in stored form was not measured.
- **What a redeploy costs on a database with a lot of compiled history.**
  `redeploy.py` has only ever been run against this repository's seven modules.
- **Whether anything checks the entry-point rule.** Nothing does. It is applied
  by hand, and finding 2 shows the residue of the last time it was not.

---

## Where the evidence is

| | what it shows |
| --- | --- |
| [`findings/03_class_identity.py`](../findings/03_class_identity.py) | editing a class compiles a different class; run it twice |
| [`findings/08_script_imports.py`](../findings/08_script_imports.py) | the database keeps a compiled module and serves it forever; the commit is the mechanism |
| [`findings/02_main_namespace.py`](../findings/02_main_namespace.py) | `__main__` is shared by every script; dispatch is by arity |
| [`findings/class-identity/`](../findings/class-identity/README.md) | committing after imports is what keeps class identity |
| [`redeploy.py`](../redeploy.py) | the escape, with its reasoning in the module docstring |
| [`docs/prd-corrections.md`](prd-corrections.md) | correction 5 on FR-7.2, correction 10 on what "redeploy" means |

And the two companions, again, because most of what an agent needs is in one of
them rather than here:
[`writing-python-for-gemdb.md`](writing-python-for-gemdb.md) for the runtime,
[`dataset-for-agents.md`](dataset-for-agents.md) for the objects.
