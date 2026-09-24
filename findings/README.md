# Findings, as scripts you can run

Ten things about running Python inside GemDB that cost real time while
building this demo, each reduced to a script that reproduces it on your own
database rather than asking you to believe a transcript.

[`docs/writing-python-for-gemdb.md`](../docs/writing-python-for-gemdb.md) is
these turned into advice, with the rest of what this repo learned folded
in. Read that if you are about to write code; read this if you want to see it
happen on your own database.

```sh
export PATH="$HOME/GemDB/bin:$PATH"     # not needed in a VS Code terminal
gemdb findings/01_shim_missing.py
gemdb findings/02_main_namespace.py
gemdb findings/03_class_identity.py     # run this one twice
gemdb findings/04_dirty_session.py
gemdb findings/05_module_monkeypatch.py
gemdb findings/06_decimal_money.py
gemdb findings/07_logging_stub.py
gemdb findings/08_script_imports.py     # run this one twice
gemdb findings/09_imported_module_sys.py  # run this one twice
gemdb findings/10_shared_session_state.py # needs the app running; stops it
```

`class-identity/` is a fourth-and-a-half: four scripts in two arms, inherited from the demo being retired. See
[`class-identity/README.md`](class-identity/README.md).

All of them leave your data alone. Only 03 writes to `gemdb.root`, and it
removes what it wrote; 05 patches the `gemdb` module and puts it back; 08 and
09 write a throwaway module under `findings/` and remove it. 09 commits, which
is the whole point of it, and so leaves one small compiled module in the
database. **10 is the exception to "safe": it deliberately stops a running app
answering.** Nothing in the book changes; restart the app.

**Last audited 2026-09-23 against engine 4.0.0.a2 with Grail `9a0b0fc`**, by
running every one of them. First measured 2026-09-08 against GemStone/S 3.7.5
with Grail `c875e56` — and the gap between those two lines is the point: three
findings changed behaviour across it and said nothing, because nothing recorded
what they had been measured against. Each script now carries its own
"last verified against" line. When you run one and it disagrees with its prose,
the prose is what is out of date.

What the 2026-09-23 audit found:

| | Then | Now |
| --- | --- | --- |
| 03 class identity | identity lost on edit | **fixed** — identity survives, and the new attribute reads through the class |
| 05 patched module | dirties the session for good | still true here, **fixed upstream** in Grail `03d51ac3`, which is not in this build |
| 06 decimal | `quantize`, `//`, `%`, `divmod`, `format(spec)`, `round()` all missing or fatal | **all work**; only `statistics.mean`/`median` on a Decimal still ends the gem |
| everything else | | unchanged, and re-reproduced |

**Two of them disagree with the same findings reached independently in
[the parallel demo](https://github.com/GemTalk/GemDB_Code/blob/c9c261ac017fd7831cd29aa71b79da4ee8c1ed9b/docs/demo/brain-freeze/) (pinned at `c9c261a`), which measured Grail `46c2a68`.** Where
they disagree, the scripts say so and print what *your* Grail does. If yours
matches theirs rather than ours, that is the more interesting result and the
Grail team should hear it.

| | What it shows | Also seen elsewhere? |
| --- | --- | --- |
| `01_shim_missing.py` | whether this database can run a web framework at all | **not documented anywhere** |
| `02_main_namespace.py` | `__main__` is shared by every script, dispatch is by arity | sharper form of their finding 5 |
| `03_class_identity.py` | editing a class compiles a different class | **contradicts their rule 2** |
| `04_dirty_session.py` | running any code dirties the session, so `refresh()` refuses | **partly contradicts their rule 4** |
| `05_module_monkeypatch.py` | a patched module dirties the session for good | **not documented anywhere** |
| `06_decimal_money.py` | `decimal` works; the operators around it do not | **corrects our own older note** |
| `07_logging_stub.py` | an exception in a view is invisible | shared with their finding 4 |
| `08_script_imports.py` | what a script can import, and what the database keeps | **the stale half is ours** |
| `09_imported_module_sys.py` | a path helper works until something commits | **not documented anywhere** |
| `10_shared_session_state.py` | stdlib state in the repository stops a running app for good | **not documented anywhere** |
| `class-identity/` | committing after imports is what keeps class identity | **theirs, and it reproduces here** |

---

## 1. A database can be installed without the regex engine

The one worth checking first, because it costs the most and is documented
nowhere. An extent installed without the CPython shim starts, runs Python,
seeds a 900-policy book and passes every test in this repo — then cannot
`import re`. Werkzeug's routing, Jinja2's lexer and all header parsing need it,
so every web framework fails together behind an error naming `_sre`.

`install-grail.sh` blanks `SHIM_LIB_PATH` when the library is not present at
the moment it looks, and installs anyway with a warning to a log. Nothing
afterwards says the database is in that state.

The fix is one assignment and a commit, **not** a reinstall — a reinstall
recreates the Python runtime classes with new identity and orphans everything
already committed.

## 2. `__main__` is one shared namespace

Every script runs as `__main__`, and `__main__` is compiled into the database
and kept. A new script starts with the accumulated globals of every script this
database has ever run. Combined with dispatch by argument count — defaults do
not disambiguate — a call to `main()` can land in a different file's `main`.

That is not hypothetical: `gemdb web/app.py` failed with `name 'PREAMBLE' is not
defined`, a global belonging to `make_mcp_questions.py`. **Do not name a
script's entry point `main`.** Name it something the file owns, so that no two
of them are the same zero-argument selector. Every script here does:
`serve()`, `generate()`, `refresh()`, `seed_database()`, `check_shim()`,
`main_namespace()`, `class_identity()`, `dirty_session()`,
`module_monkeypatch()` — including all five scripts in this directory, three
of which used to define a zero-argument `main` and so collided with each other
through the very namespace they document.

**Renaming them did not clean the database.** Run `02` here now and it still
reports `a zero-argument main inherited from elsewhere: yes` — left behind by
the versions that ran before the rename, and it will stay until someone
removes it or the extent is rebuilt. That is the finding restated in its
sharpest form: the namespace is *repository state*, not process state, so
fixing your source fixes what you compile next and nothing you compiled
before. The same run lists names from scripts that were written, run once and
deleted.

## 3. Editing a class compiles a different class — fixed since first measured

Run it twice — a genuine re-import needs a genuine new session. A record
committed under the old class keeps its data, raises `AttributeError` for the
new field, and is no longer `type(record) is TheClass`.

On `c875e56` it is not `isinstance(record, TheClass)` either. Their rule 2
records `isinstance` continuing to work on `46c2a68`. Both are reproducible, so
this looks like a change between those versions that nobody noticed.

Either way `type(obj).__name__` survives, which is why their rule 3 — find
records by index, not by `isinstance` — is the right advice, and on this Grail
it is not merely tidier but necessary.

**What CUJ-4 should claim.** Adding `flavour` and `toppings` cost nothing here
because they were declared on the class *before anything was committed*. That
is what a schemaless object database buys you, and it is a claim about
foresight rather than magic.

**Re-measured 2026-09-23 on Grail `9a0b0fc`: this no longer reproduces.** Run 2
now reports `type(record) is C` and `isinstance(record, C)` both True, and the
record reads the attribute added after it was committed, through the class.
Identity survives the edit entirely — which matches neither the original
measurement here nor the parallel demo's. The finding is kept because the
advice it produced is still the right advice (find records by index, not by
`isinstance`; declare optional fields up front), and because a reader on an
older Grail will still meet it. The script prints what *your* build does.

## 4. A read-only session is not clean

`needs_commit()` is already `True` before a script does anything, because
running it compiled it into the database — which is exactly what every notebook
cell does. So `gemdb.refresh()`, the obvious way to see another surface's
commit, **refuses**:

```
refresh() would discard uncommitted changes; commit() to keep them
or abort() to discard them first
```

`gemdb.abort()` also takes a new view and is the wrong tool: it discards this
session's uncommitted work, including functions defined in earlier cells.

The recipe is `gemdb.commit()` then `gemdb.refresh()`.

Their rule 4 attributes the dirtiness to *calling* a function for the first
time. On `c875e56` that did not reproduce — a first call to a
never-before-compiled function left `needs_commit()` `False`. The dirtiness
here comes from running the code at all. The script measures both so you can
see which your Grail does.

---

## 5. A patched module stays dirty, and commit will not clear it — fixed upstream

Found by a test that could not work. The web app was made to `commit()`
then `refresh()` before each request, and the obvious test wraps both to
record the order:

```python
for name in ("commit", "refresh", "abort"):
    setattr(gemdb, name, recorded(name))
```

Every such test fails inside the code under test, not at an assertion, so it
reads as though the fix is broken. It is not. Rebinding an attribute on an
imported module leaves the session dirty in a way `commit()` does **not**
clear -- two commits do not clear it either -- and every later `refresh()`
raises `PendingChangesError`.

Wrapping the same functions in ordinary local variables is fine. The
difference is the assignment onto the module, which Grail compiles into the
database and treats as persistent, and a function object is not something it
can write there.

So inside the database, monkeypatching is not a technique you have. Introspect
something that is not a persistent module instead: `tests/test_refresh.py`
reads `app.py`'s syntax tree under CPython, and `tests/test_app.py` asks Flask
for its own `before_request_funcs`.

For the product, this wants a better error. "refresh() would discard
uncommitted changes" is true and points nowhere near a `setattr` three lines
earlier.

**Fixed upstream, and not in this build.** Grail `03d51ac3` (2026-09-23, "A
monkey-patch is session state") moves patched methods from persistent
compilation to transient session methods, naming the same symptom this finding
reports: *"commit conflicts between patching sessions"*. The installed build is
`9a0b0fc`, which predates it, so the script still reproduces here. Re-run it
after the next Grail update; if it stops reproducing, that is why.

---

## 6. `decimal` works, and everything you reach for next does not — mostly landed

The one that changed this repo's mind. Money was float, and the repo carried a
note saying `Decimal` was unusable on Grail. **That note was stale.**
`Decimal("19.99") * 3` returns `59.97`; sums, products and terminating
divisions are exact; and a `Decimal` survives a commit intact. So money here is
`decimal.Decimal` — the standard library, doing exact arithmetic inside a
GemStone database.

What is missing is the apparatus around it, and two of the gaps are not
exceptions but hard VM errors with no traceback and no line number:

- `round(Decimal, 2)` — **takes the VM down**, `a Decimal does not understand #'*'`
- `statistics.mean` or `median` over Decimals — **takes the VM down**,
  `a Decimal does not understand #'_generality'`
- no `quantize`, no `as_tuple`, no `//`, no `%`, no `divmod`, and
  `format(d, '.2f')` raises — though `'%.2f' % d` is fine, which is the
  opposite of what this file said at first

And three that succeed with a *different answer* than CPython, which is worse,
because nothing fails until two surfaces disagree in front of an audience:
`int(Decimal)` floors here and truncates there; a `Decimal` compares equal to a
float that is not equal to it; and `str()` drops trailing zeros, so `$170.10`
prints as `170.1`.

`brainfreeze/money.py` is the answer to all of it, and `gemdb tools/run_db_tests.py`
running the same suite in both runtimes is what keeps it honest.

**Re-measured 2026-09-23 on Grail `9a0b0fc`: most of this has landed.**
`quantize`, `as_tuple`, `//`, `%`, `divmod`, `format(d, '.2f')` and
`round(Decimal, n)` all work now — the last of those was listed here as
*fatal*, and it returns `Decimal('1.00')`. Upstream `6c13e852` ("Make
ScaledDecimal's Decimal dunders exact: str/repr, \*, /, \*\*, quantize") is
the change.

What survives: **`statistics.mean` and `statistics.median` on Decimals still
end the gem**, with `a Decimal does not understand #'_generality'` and no
Python exception to catch. That one is unchanged and still the reason to
compute aggregates by hand.

The script's section labels are older than its measurements, which is exactly
the trap this whole file is about; read the values it prints, not the headings
over them, until it is rewritten.

## 7. Reporting a view's exception is what fails — fixed upstream

A Flask view raises. Flask calls its logger to say so, with `exc_info=True`.
Grail's `logging` is a hand-written stub whose `Logger.error` took only
`*args`, so the call that exists to report the exception raises one of its
own — and what reaches the log is a `TypeError` about `exc_info`, with the real
exception somewhere further up if it is anywhere at all.

**The failure replaces the diagnosis.** That is the same shape as finding 5 and
as the crash behind finding 6: in each one, the code that exists to explain a
problem is the code that breaks. It is the single most consistent thing this
repo has to say about Grail.

**Fixed upstream 2026-09-24**, in Grail `b8bdeb76` — a branch that had sat
unmerged since 2026-09-08 and 907 commits behind their main, rebased, squashed
and landed. It was more than the two lines this file used to claim: the record
carries the traceback, the formatter renders it, and every `Logger` method
gains `**kwargs`, with tests. `LoggerAdapter.error` already took `**kwargs`, so
the module had been disagreeing with its own signature.

Not in the build here (`9a0b0fc`), so the script still reproduces — like
findings 5 and 9, it stops the moment you update.

## 8. A script's neighbours, and modules the database will not let go of

Two halves, and the second is the expensive one.

`sys.path[0]` is the script's directory, so a script can import the module
beside it. Grail issue #847 was that it could not; that is fixed and the script
reports which behaviour your build has.

The half that is still live: **the database keeps a compiled copy of a module
and serves it in preference to the file on disk.** `tests/test_app.py` was
edited over and over with no effect, while edits to top-level `app.py` in the
same tree took effect immediately — which is why `run_db_tests.py` reads and
`exec`s its test modules rather than importing them.

**What actually deploys a module is the commit**, and that is the part worth
carrying away. The first version of this script had no `commit()` in run 1 and
found nothing wrong. Add it and the staleness appears every time. So the rule
in `class-identity/` — commit after your imports, or instances are stranded on
a class the next session will not recognise — is also the rule that freezes
your code in place. Both pieces of advice are correct and they pull against
each other, which is worth knowing before it costs you an afternoon.

At package scale it cost an afternoon: the database went on running a float
`annual_premium` for an hour after the file returned exact `Decimal`, with the
whole suite passing against rules that were no longer on disk. Nothing reports
the divergence. `redeploy.py` is the answer, and it is only obvious once you
know the failure exists.

## 9. A path helper works until something commits — fixed upstream

`gemdb tools/seed.py` puts the **script's** directory on `sys.path`, not the
repository, so every entry point in a subdirectory has to say where the model
is before it can import it. Nine scripts, three lines each — and the obvious
tidy-up is one module beside them, imported for the side effect.

It works. The seeder ran, the redeploy ran, and the redeploy *committed*.
Every run after that failed with `No module named 'brainfreeze'`, from scripts
whose first statement was the thing meant to prevent exactly that.

The helper still runs afterwards and its constants are still right. What
changes is that the `sys` it inserts into stops being the caller's `sys`.
Nothing raises; the insert lands somewhere nobody is looking.

This is finding 8 with a sharper edge. There, a committed module is served
stale. Here it is not stale at all — fresh source, correct values — and still
is not the module you wrote. The asymmetry is worth keeping: a path inserted
by the *running script* is visible to everything it imports, before and after
a commit alike, which is why a test runner can put a directory on the path and
then execute tests that import from it.

**Put the path lines in each entry point.** Duplication is cheaper than a
helper that silently does not help.

**It was not only `sys`, and it is now fixed.** A deployed module whose body is
`import sys, os, json, re` handed a fresh session a different `sys`, `os` and
`json` than the caller had — but the same `re`. Grail `bcedc68a` (2026-09-23,
"A deployed module stays coherent with what it imported") makes every native
module subclass `NativeModule`, one committed instance answered in every
session, and on current main all four are the caller's. That also explains
`re`: it never needed the fix; the native modules did.

`bcedc68a` landed one day after the build this was measured on, which is why it
looked open. D8 of Grail's `docs/Persistent_Modules_and_Classes.md` describes
the seam it closes.

---

## 10. Stdlib state lives in the repository, and it stops a running app

`gemdb findings/10_shared_session_state.py`, with the app running. It will stop
the app answering; that is the demonstration.

A Flask app serving from inside the database takes a new view before every
request, and `take_new_view()` has to commit first, so between requests it is
always holding uncommitted work. Let another session commit and the app's next
commit can be a Write-Write conflict. It cannot abort out of it — that would
discard its own compiled handlers — so the work stays uncommitted, the next
request re-attempts the same commit, and fails identically. **The server does
not degrade. It stops answering and stays stopped.**

The interesting part is what they fight over. Catching the `ConflictError` and
printing `conflicts` names five objects: two `SrePattern`s, a `decimal`
`Context.flags` dict carrying `Inexact: 1, Rounded: 1`, and that dict's
collision buckets.

A GemStone Write-Write needs the **same object**, so both sessions are sharing
one decimal `Context`. They reach it through Grail's `contextvars`, which ends:

```python
_top_context = Context()
_current_context = _top_context
```

Module-level globals in a committed module. Anything any library puts in a
`ContextVar` is shared across every session and persists in the repository. And
this is a money application, so every request rounds something.

**This finding said something else first, and it was wrong.** It said "two
sessions compiling the same callable", inferred from black-box experiments:
calling a function the app had also called killed it, calling one it had not
did not. The experiments were sound and the inference over them was not. `/`
formats money but does not *set* `Inexact`/`Rounded`; `/api/stats` aggregates
and does. "The app had called that function" was really "the app had set those
flags" — and the old wording pointed a reader at compilation, which is not what
conflicts.

Finding 7 is why it took a week: Flask reports the exception through
`Logger.error(..., exc_info=True)`, which raises a `TypeError` over the top of
the `ConflictError`. The log shows the reporting failure, not the failure.

**The fix belongs in Grail**, which has done this migration three times already
— `random`, `secrets`, and `re._cache` all hold per-session state now, and
`docs/Concurrency.md` states the rule. `contextvars` has not had it. A plan
written to be handed to someone working in that repository is in
[`docs/grail-contextvars-session-state.md`](../docs/grail-contextvars-session-state.md).
Confirmed not fixed on Grail `origin/main` at `1f2f5ed1` (2026-09-23). Tracked
as issue #83.

The acceptance suite works around it — the steps that run something in a
session of their own check the app afterwards and restart it if it is gone. The
demo has no harness, which is why DEMO.md's first trap tells the presenter to
reload the browser after the notebook beat.

Still unexplained: the two `SrePattern` objects. `re._cache` is already a
`SessionDict` in this build, so the cache is not what conflicted — the pattern
objects themselves were written by both sessions. Fixing `contextvars` will not
clear that.

---

## What to do with these

The four shared findings — class identity, dirty sessions, Flask's logging stub
and `sys.path` — were reached twice, independently, from different code. That
is the strongest argument either demo makes that **these are GemDB's to fix or
document, not each demo's to work around.**

Finding 1 is the one to raise first: it is undocumented, it produces a database
that looks healthy in every other respect, and the error message points nowhere
useful.
