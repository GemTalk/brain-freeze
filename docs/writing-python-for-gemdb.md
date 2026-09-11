# Writing Python that runs inside GemDB

Claude writes good Python. It writes good *CPython*, and this is not that.

Grail is the Python implementation inside a GemStone database. It is close
enough to CPython that ordinary code usually runs, and different enough that the
places it diverges are not the places anyone guards. Everything below cost real
time while building this demo. None of it is obscure, and none of it is a matter
of taste.

This is the document to read **before writing code that will run in the
database**. Its companion, [`dataset-for-agents.md`](dataset-for-agents.md), is
the document to read before **querying this demo's data** — the object model,
the real field names, the questions and their traps. The two do not overlap on
purpose: that one tells you what a `Policyholder` is, this one tells you what
the runtime will do to the code you write about it.

A third, [`adding-a-feature.md`](adding-a-feature.md), turns this one into a
procedure for **changing this repository** — where a field goes, which commands
deploy it, what the tests are and which surfaces move together. It links back
here for every fact rather than restating one, so read this first and that one
when you are about to edit something.

The evidence is [`findings/`](../findings/): eight scripts that reproduce these
on your own database rather than asking you to believe a transcript. Where this
file states a fact, the finding that measured it is named.

**Measured** 2026-09-08 and 2026-09-09, against GemStone/S 3.7.5 carrying Grail
`c875e56` with one method patched in
([Grail#895](https://github.com/GemTalk/Grail/pull/895)) — `GRAIL_VERSION` on
that database reads `grail=c875e56+gemtalk-grail-pr895`. Grail moves fast and
several of these behaviours have already changed between shas, so **check your
own sha before trusting a fixed answer here**; the findings scripts print what
*your* build does.

---

## The through-line: the code that reports the problem is the code that breaks

Read this first, because it is the most useful thing this repository learned and
it explains the *shape* of nearly everything below.

- **A Flask view raises, and the exception vanishes.** Flask catches it and
  calls `self.logger.error(..., exc_info=True)` to say so. Grail's `logging` is
  a hand-written stub whose `Logger.error` took only `*args`, so the call that
  exists to report the exception raises one of its own. What reaches the console
  is a `TypeError` about `exc_info`; the real exception is somewhere further up,
  if it is anywhere at all
  ([finding 7](../findings/07_logging_stub.py)).
- **A template error killed the gem.** An unknown Jinja filter raised, and
  jinja2's error reporting called `code.replace(co_name=...)`. Grail answers a
  `compile()` result as source text, so that landed on `str.replace` called by
  keyword, which read past the end of an empty array and ended the session with
  `OffsetError 2003` — no traceback, no line number, uncatchable. *Reporting*
  the template error was what killed the process. That one is fixed and pinned
  (`docs/grail-improvements.md`, "This database is no longer stock c875e56").
- **A test destroyed what it was measuring.** The obvious way to check that the
  web app commits before it refreshes is to wrap `gemdb.commit` and
  `gemdb.refresh` and record the order. Rebinding an attribute on an imported
  module leaves the session dirty in a way `commit()` does not clear, so every
  later `refresh()` raises — and the test fails *inside the code under test*,
  which reads exactly like the fix being broken
  ([finding 5](../findings/05_module_monkeypatch.py)).
- **Two money operations end the session instead of raising.**
  `round(Decimal, 2)` and `statistics.mean` over Decimals do not give you an
  exception to catch, a traceback, or a line number. They give you a dead gem
  ([finding 6](../findings/06_decimal_money.py)).
- **Exceptions carry no `__traceback__` at all**, so `traceback.format_exc()`
  can never report a frame
  ([Grail#849](https://github.com/GemTalk/Grail/issues/849)).

Three consequences follow, and they are worth adopting as habits:

1. **Do not trust the first error you see.** It is at least as likely to be the
   reporting machinery failing as the thing you did. Look for what was being
   reported.
2. **Debug with `print`.** The framework's own reporting cannot be relied upon
   to run. That is not a stylistic preference here; it is the channel that is
   known to work.
3. **A dead session is worse than a wrong answer**, because a wrong answer is
   recoverable. Where there is a choice, prefer the operation that raises to the
   one that might not.

---

## Before you write anything: can this database run a web framework?

An extent installed without the CPython shim starts, runs Python, seeds a
900-policy book and passes every test in this repository — and then cannot
`import re`. Werkzeug's routing, Jinja2's lexer and all header parsing need it,
so every web framework fails together behind an error naming `_sre`.

```sh
gemdb -c 'import re; print("re works:", bool(re.match(r"a+", "aaa")))'
```

If that fails, stop and read [finding 1](../findings/01_shim_missing.py). The
fix is one assignment and a commit. **It is not a reinstall** — a reinstall
recreates the Python runtime classes with new identity and orphans every object
already committed.

### The standard library is a moving target, per sha

Grail ships a partial standard library, and which part depends on the sha. Do
not work from a remembered list; two of this repository's own written lists were
wrong (`random.choices` was recorded as missing in `PLAN.md` and is implemented
— `random.gs:402`, weights and all).

What this repository does instead is enforce a boundary in a test:
[`tests/test_packaging.py`](../tests/test_packaging.py) parses every module in
`brainfreeze/` and fails if it imports anything outside the set the database was
observed to have. That allowlist is a record of one afternoon's measurement, not
a specification — read it as the current answer, and re-measure rather than
extend it from memory. `docs/grail-improvements.md` item 13 asks the product for
a generated manifest so nobody has to keep a private guess at all.

---

## Money

Money must not be a float. `0.1 * 3` is not `0.3`, ten dimes are not a dollar,
and this repository shipped 23 monthly premiums that disagreed by a cent with
their own annual figure because the generator rounded with numpy and the model
rounded with Python, and the two disagree on halves.

**`decimal` works inside the database.** That contradicts an older note in this
repository, which is why [finding 6](../findings/06_decimal_money.py) is a script
and not a paragraph:

```
Decimal("0.1") * 3          ->  Decimal("0.3")     exactly
ten times Decimal("0.1")    ->  Decimal("1.0")     exactly
Decimal("170.10") / 12      ->  Decimal("14.175")  exactly
Decimal("19.99") * 3        ->  Decimal("59.97")   exactly
```

A `Decimal` survives a commit with its value, ordering and equality intact.

What is missing is the apparatus you reach for *next*.

### The two that end the session

Neither of these raises. Both take the gem down, with no Python exception, no
traceback and no line number.

| What you would write | What happens |
| --- | --- |
| `round(amount, 2)` | `a Decimal does not understand #'*'` — session gone |
| `statistics.mean(amounts)`, and `median` with it | `a Decimal does not understand #'_generality'` — session gone |

Both are the obvious thing to reach for, which is what makes them expensive. Sum
and divide yourself; round with `brainfreeze.money.round_cents`.

### The ones that raise

Catchable, and each has a workaround.

| What you would write | What happens |
| --- | --- |
| `amount // 10`, `amount % 10`, `divmod(...)` | `TypeError` — use `int(x / 10)` for banding |
| `format(amount, ".2f")`, `"{:.2f}".format(amount)` | `TypeError` — it is specifically a format *spec* that has no implementation |
| `amount.quantize(...)` | missing — the single most valuable gap to close |
| `amount.as_tuple()` | missing |

Two spellings that **do** work, and are worth knowing precisely because they
look like they should not: **`'%.2f' % amount` works** — printf on a Decimal is
fine — and `'{}'.format(amount)` with no spec works. This repository claimed the
opposite for a few hours; do not reintroduce that.

### The ones that succeed with a different answer

These are worse than the failures, because nothing goes wrong until two surfaces
disagree in front of an audience.

- **`int(Decimal)` floors here and truncates toward zero in CPython.**
  `int(Decimal("-14.5"))` is `-15` in the database and `-14` outside it, so any
  rounding written over a signed value gives two answers. Round a magnitude and
  reapply the sign — that is what `money.round_half_up` does.
- **`str()` drops trailing zeros**, before and after a commit:
  `Decimal("170.10")` reads back as `Decimal("170.1")`, so `$170.10` prints as
  `170.1`. Values and arithmetic are unaffected; no display string may come from
  `str()`.
- **Non-terminating division degrades to about 16 significant digits.**
  `Decimal(1) / Decimal(3)` is `0.3333333333333333` where CPython gives 28.
  Money divisions here terminate and are rounded to cents immediately.

**Comparison is not one of them.** `Decimal("92081.22") == 92081.22` is `False`
in both runtimes, correctly — that float is not that number. An earlier draft of
this repository claimed the runtimes disagreed about it. They do not. Never pin
money against a float literal, but the reason is that the literal is wrong.

### `round()` itself disagrees between the runtimes

Independent of Decimal: **bare `round()` is half-up inside the database and
banker's outside it.** `round(2.5)` is `3` here and `2` there. A loss ratio of
`0.0625` prints as `0.063` in the web app and `0.062` in the notebook. This is
quieter than anything else on this page and it attacks the demo's central claim
— one dataset, three surfaces, one answer — rather than merely annoying you.

### So: import the helpers, do not reach for the language

```python
from brainfreeze.money import ZERO, format_usd, round_cents, usd
```

[`brainfreeze/money.py`](../brainfreeze/money.py) is the answer to all of the
above and its docstrings are the long form of this section. `usd()` builds money
from text or an int and **raises on a float**, deliberately, because by the time
a float reaches you the value it was meant to carry is already gone.
`round_cents()` is half-up, written in Decimal arithmetic with no float in it
and no `int()` applied to a negative. `format_usd()` restores the trailing zero
and renders `None` as `--`, because a field with no money recorded should not
read as free.

Ratios are **not** money. A loss ratio is a measurement and is honestly a float.

---

## The session: running code is a repository write

This is the fact the next two sections hang off.

**Grail compiles the Python you run into the database.** Not stores its output —
compiles the code itself, as a repository write. So:

- `gemdb.needs_commit()` is already `True` before your script does anything of
  its own, because running it compiled it
  ([finding 4](../findings/04_dirty_session.py)).
- Every notebook cell you have run has done the same thing.
- A session can be dirty with nothing of its own stored, having read no record
  and written none.

### To see another surface's commit: `commit()` then `refresh()`

A GemStone session sees the repository as of its last transaction boundary, so
another surface's commit is invisible until this session takes a new view. The
obvious call **refuses**:

```
refresh() would discard uncommitted changes; commit() to keep them
or abort() to discard them first
```

The recipe is:

```python
gemdb.commit()     # keep this session's compiled code
gemdb.refresh()    # then take the new view
```

**`gemdb.abort()` is not the alternative, and reaching for it is the mistake
worth naming.** It does take a new view, which is why it looks like it works. It
also discards this session's uncommitted work — and under Grail that *includes
compiled Python*. In a notebook, the helper you defined three cells ago stops
existing. In the web app, `abort()` in an exception handler would throw away the
running server's own handlers. There is no rollback to reach for here; "abort on
exception" is wrong, and dangerously so.

The web app runs `commit()` then `refresh()` at the start of every request —
`take_new_view()` in [`app.py`](../web/app.py), whose docstring explains why the
commit is unconditional rather than guarded by `needs_commit()`. The notebook
deliberately does *not*, because an analysis that shifted under you mid-cell
would be worse than one that waits to be told.

*(One attribution is unsettled.
[Grail#851](https://github.com/GemTalk/Grail/issues/851) blames the dirtiness on
the **first call** to a function. On `c875e56` that did not reproduce — a first
call to a never-before-compiled function left `needs_commit()` `False`, and the
dirtiness came from running the code at all. Finding 4 measures both, so you can
see which yours does.)*

---

## Code is data, and that changes four things

Because compiling is a write and committing keeps what was compiled, your code
is repository state. Four consequences, and the first is the expensive one.

### 1. A committed module is deployed, and the database serves it forever

Once `brainfreeze` has been imported and committed once, it is *deployed*. A
brand-new session, a new process, an edited file on disk — and
`import brainfreeze` returns what the database compiled. **Nothing reports the
difference.**

This cost the whole of the money work: the database went on returning
`31.499999999999996` from a float `annual_premium` for an hour after the file on
disk returned exact `Decimal`, with every test passing against rules that were no
longer anywhere on disk. At smaller scale it ate an afternoon on
`tests/test_app.py`, which was edited over and over with no effect while edits
to `app.py` in the same tree took effect immediately
([finding 8](../findings/08_script_imports.py)).

There is a second face of this that is harder to see, because nothing about it
looks stale. A module whose only job was to put the repository on `sys.path`
for the scripts beside it worked — until a redeploy committed, after which
every script that leaned on it failed with `No module named 'brainfreeze'`.
The helper still ran, and its constants were still right; what changed is that
the `sys` it inserted into stopped being the caller's. **A module cannot fix
its importer's `sys.path` once it has been committed.** Put those lines in each
entry point ([finding 9](../findings/09_imported_module_sys.py)). A path
inserted by the *running script* is not affected and reaches everything it
goes on to import.

**The commit is the mechanism.** The first draft of finding 8 had no `commit()`
in run 1 and concluded there was no problem. Compiling a module is a repository
write; *committing* it is what makes the database keep the compiled copy and hand
it to every later session.

Which puts two pieces of correct advice in direct conflict.
[`findings/class-identity/`](../findings/class-identity/README.md) establishes
that you **must** commit after your imports, or instances you write are stranded
on a class the next session will not recognise. That rule is right. This is its
price: the same commit that stabilises your classes freezes your code.

**The escape is [`redeploy.py`](../tools/redeploy.py)**, and it is not obvious:

```sh
gemdb tools/redeploy.py
```

It is `importlib.reload` in dependency order, then a commit, and both details are
load-bearing. *Order matters*, because reloading a module re-executes it and
while that happens the modules importing it cannot resolve it — reload a leaf
first, or the dependent raises `ImportError: module ... is canonical
(deployed)`. And *each reloaded module must be put back into `sys.modules` by
hand*, because `reload` leaves a deployed module absent from it and the next
module up imports by name.

**Deleting from `sys.modules` is not a substitute, and makes it worse.** A
deployed module removed that way cannot be imported again for the rest of the
session:

```
ImportError: module 'brainfreeze' is canonical (deployed); it was removed from
sys.modules in this session. Use importlib.reload() to re-execute it, or assign
a replacement into sys.modules to substitute it.
```

`redeploy.py` does not migrate anything. Objects already committed keep the class
they were made with, which is the next item.

### 2. Editing a class compiles a *different* class

A record committed under the old class keeps its data, raises `AttributeError`
for the new field, and is no longer `type(record) is TheClass`. On `c875e56` it
is not `isinstance(record, TheClass)` either
([finding 3](../findings/03_class_identity.py)).

That last part is a version difference, not a settled fact: the parallel demo
measured `isinstance` continuing to work on Grail `46c2a68`, and both
measurements are reproducible. If finding 3 prints `isinstance: True` on your
build, that is the interesting result and the Grail team should hear it.

`type(obj).__name__` survives either way, which is why the right rule is **find
records by index, not by `isinstance`** — see §5 of
[`dataset-for-agents.md`](dataset-for-agents.md) for how this demo's indexes are
shaped.

The honest version of "add a field to a live database": it costs nothing when the
attribute was declared on the class *before anything was committed*, because an
instance with no slot of its own reads the default through the class. That is
what a schemaless object database buys you, and it is a claim about foresight
rather than magic. Editing a model live in front of an evaluator shows them an
`AttributeError`.

`seed.py` hides this, which is worth knowing before you conclude that a source
edit propagated: seeding rebuilds every object from the new class, so no instance
is left holding the old one.

### 3. `__main__` is one namespace shared by every script the database has run

Every script runs as `__main__`, `__main__` is compiled into the database and
kept, and a new script therefore starts with the accumulated globals of every
script this database has ever run, across sessions and across processes
([finding 2](../findings/02_main_namespace.py)).

Combined with the second half: **Grail dispatches by argument count, and default
values do not disambiguate.** A function declared `main(host="...", port=5000)`
and called as `main()` is a zero-argument call, and can resolve to a *different*
script's zero-argument `main`.

That is not hypothetical. `gemdb web/app.py` failed with
`name 'PREAMBLE' is not defined` — a global belonging to
`make_mcp_questions.py` — because `app.py`'s `main()` reached the question
generator's `main` and died inside it.

> **Do not name a script's entry point `main`.** Give it a name the file owns, so
> no two of them can be the same zero-argument selector.

Every script here does: `serve()`, `generate()`, `refresh()`, `seed_database()`,
`redeploy()`, `check_shim()`, `main_namespace()`, `class_identity()`,
`dirty_session()`, `module_monkeypatch()`, `script_imports()`, `run_db_tests()`.

**Renaming them did not clean the database.** Finding 2 still reports a
zero-argument `main` inherited from elsewhere, left behind by the versions that
ran before the rename, and it will stay until someone removes it or the extent is
rebuilt. That is the sharpest form of the finding: the namespace is *repository
state, not process state*, so fixing your source fixes what you compile next and
nothing you compiled before. The same run lists names from scripts that were
written, run once and deleted.

Also: pick names that are yours. The findings scripts define a `TITLE` constant
rather than reading `__doc__`, because `__doc__` in a shared `__main__` is
whatever the last script left there — finding 1 printed `object`'s docstring the
first time it ran.

### 4. You cannot monkeypatch a module

Rebinding an attribute on an imported module — `setattr(gemdb, "commit", spy)`,
the ordinary way to spy on a function in a test — leaves the session dirty in a
way `commit()` does **not** clear. Two commits do not clear it either, and every
later `refresh()` raises `PendingChangesError`
([finding 5](../findings/05_module_monkeypatch.py)).

Note precisely what is *not* the cause. Defining a closure and calling it is
fine. Wrapping a bound function in an ordinary local variable is fine. The
difference is the assignment **onto the module object**, which Grail compiles
into the database and therefore treats as persistent — and a function object is
not something it can write there.

So inside the database, monkeypatching is not a technique you have. Introspect
something that is not a persistent module instead:

- [`tests/test_refresh.py`](../tests/test_refresh.py) reads `app.py`'s syntax
  tree under plain CPython to pin the call order.
- [`tests/test_app.py`](../tests/test_app.py) asks Flask for its own
  `before_request_funcs`.

Both answer the same question without touching `gemdb`.

---

## Scripts

**`sys.path[0]` is the script's directory** — so a script can import the module
beside it, and Grail#847 (that it could not) is fixed as of `8c8f503e`,
2026-08-29.

**But it is a *relative* path**, where CPython puts an absolute one. It resolves
only while the process stays where it started. Anything that changes directory —
and a test runner reasonably might — silently takes the script's own neighbours
off the path. Finding 8 prints yours and whether it is absolute.

The consequence is a rule with teeth: **start scripts from the project
directory.** An import that cannot find `brainfreeze/` on disk does not fail. It
resolves out of the database to whatever class was last compiled there, silently
— which is items 1 and 2 above arriving together. `gemdb web/app.py` run from `/tmp`
runs against last week's model and says nothing.

Over MCP the same problem has a different shape, because a worker gem's working
directory is the stone's: §1 of
[`dataset-for-agents.md`](dataset-for-agents.md) has the `sys.path.insert` line a
worker gem needs and a notebook does not.

Three more, smaller:

- **`import x.y as m` fails** with `local variable referenced before assignment`,
  and plain `import x.y` leaves the name unbound. **`from x.y import Thing` is
  the form that works.** (Worth re-measuring — the `sys.path` work in `8c8f503e`
  may have moved it.)
- **There is no `strptime`.** Both this demo and the parallel one parse ISO dates
  by hand; `seed.py`'s `_date()` is three lines and is all it takes.
- **`os.remove` on a path containing `$` deletes the shell-expanded path**
  ([Grail#861](https://github.com/GemTalk/Grail/issues/861)). Data-loss shaped.

---

## Web apps

Five things have to be right, and the failure when one is wrong does not point at
it.

1. **`threaded=False`.** Grail renders each Jinja template in a forked green
   thread, and the dev server's per-request `contextvars.ContextVar` cannot span
   that boundary, so `url_for` inside a template cannot see the active request.
   One CPU per gem means threading buys nothing anyway.
2. **One request per connection.** A single-threaded server parked reading a
   kept-alive connection cannot accept the next one, so a second tab or a favicon
   fetch hangs everything. `app.py`'s `CloseAfterResponseHandler` closes the
   connection after each response.
3. **Inline templates only.** `render_template_string` is exercised in Grail's
   own suite; file-based `render_template` and `FileSystemLoader` are not. Keep
   templates as module constants. A `templates/` directory would make you the
   first to try it.
4. **`commit()` then `refresh()` at the start of every request**, or a server
   started an hour ago answers every request from the book as it was an hour ago
   — and that looks like a caching bug rather than a transaction one.
5. **The `if __name__ == "__main__":` guard goes at the very end of the file.**
   This one is not Grail's fault — it is ordinary Python — but it is load-bearing
   here and the failure is confusing: `gemdb web/app.py` executes top to bottom, so a
   guard sitting next to `serve()` starts the server before the templates below
   it exist, and every route raises `NameError`. Importing the module for a test
   hides it completely, because an import finishes the file before any route
   runs.

### No custom Jinja filters or globals

`app.jinja_env.filters["usd"] = format_usd` does not work, and the reason has
nothing to do with the filter. **Flask's `jinja_env` is a `cached_property`, and
Grail realises `cached_property` without caching**, so
`app.jinja_env is app.jinja_env` is `False`. Every read builds a fresh
`Environment` and your registration goes into one that is immediately discarded.
`jinja_env.globals` is lost the same way, which is why it appears to be silently
ignored.

Pass helpers in the **context** instead. `app.py`'s `render()` is
`render_template_string(template, usd=format_usd, **context)` — one wrapper, and
every template gets money formatting.

*(This is the one whose reporting used to kill the gem: the unknown filter
raised, and jinja2's error path hit the `str.replace` bug. Fixed and pinned as of
2026-09-09, so on a stock `c875e56` expect a dead session rather than an error
message.)*

### Render throughput: page your tables

**900 table rows through `render_template_string` take about a minute**, which is
why this app pages at 25.

The mechanism is known and the cause is not, and the difference matters. Grail
implements **every Python generator as a forked `GsProcess` with a two-semaphore
handshake per `yield`** (`PythonGenerator.gs`). Jinja compiles a template to a
generator function and `render()` is `''.join(root_render_func(ctx))`, so the
whole page comes out through that handshake, several yields per row. But a few
thousand semaphore round-trips does not obviously cost sixty seconds, and two
other candidates are at least as likely: interpreted attribute access
(`environment.getattr`, `Context.resolve`, `Markup` escaping, roughly 15 per row
× 900), and Grail#851 — the first render compiles the template's generated
Python, which is a repository write.

Until someone measures it (render 900 rows, then 90, then 9; a linear curve
points at per-yield cost, a fixed head at compilation), the practical advice is
the same either way: **assume rendering is expensive per row, and page.**

### Debugging a view

Re-read the through-line. A view's exception is invisible on an unfixed build,
because Flask's own reporting is what fails. Add `print` statements.
[Finding 7](../findings/07_logging_stub.py) tells you which behaviour your build
has; the fix is two lines on `fix/logging-exc-info` in the Grail repository,
unmerged, and `LoggerAdapter.error` in the same file already takes `**kwargs`.

---

## Run your tests in both runtimes

```sh
python3 -m unittest discover        # under CPython
gemdb tools/run_db_tests.py               # the same files, inside the database
```

**This is not belt-and-braces. It is the only way to catch the class of bug this
whole page is about.** Every difference listed above — `round()`'s tie-breaking,
`int(Decimal)`'s sign handling, `str(Decimal)`'s trailing zero — is a way for one
set of rules to give two answers on two surfaces of the same application. A suite
that only runs under CPython proves nothing about the runtime the application
ships on; a suite that only runs in the database cannot tell you the two agree.

Two details in [`run_db_tests.py`](../tools/run_db_tests.py) are there for reasons from
this page:

- **It reads each test module from disk and `exec`s it into a fresh namespace
  rather than importing it**, because the database serves a stale compiled copy
  of an imported module (§1 above) and a runner that silently tests the previous
  version of the tests is worse than no runner.
- **Its entry point is `run_db_tests()`, not `main()`** (§3 above).

Tests that need a database skip themselves under CPython, so
`unittest discover` stays green — 27 of the 133 here.

---

## What this document does not know

Said plainly, because guessing here is how a confident wrong answer gets written.

- ~~**Whether a script can read its own arguments.**~~ **Settled 2026-09-09: it
  can.** [Grail#850](https://github.com/GemTalk/Grail/issues/850) says
  `sys.argv` is the host topaz command line and `sys.argv[1]` is `-L`, and
  `docs/grail-improvements.md` repeated it. Measured on `c875e56`,
  `gemdb script.py one --two` gives `['/path/to/script.py', 'one', '--two']`.
  The issue was taken on an older sha. `seed.py --dry-run`,
  `run_db_tests.py money seed` and `verify_book.py BF-100539` were not
  untested carry-over after all; they work.

---

## Where the evidence is

| | What it shows |
| --- | --- |
| [`findings/01_shim_missing.py`](../findings/01_shim_missing.py) | whether this database can run a web framework at all |
| [`findings/02_main_namespace.py`](../findings/02_main_namespace.py) | `__main__` is shared by every script; dispatch is by arity |
| [`findings/03_class_identity.py`](../findings/03_class_identity.py) | editing a class compiles a different class |
| [`findings/04_dirty_session.py`](../findings/04_dirty_session.py) | running any code dirties the session, so `refresh()` refuses |
| [`findings/05_module_monkeypatch.py`](../findings/05_module_monkeypatch.py) | a patched module dirties the session for good |
| [`findings/06_decimal_money.py`](../findings/06_decimal_money.py) | `decimal` works; the operators around it do not |
| [`findings/07_logging_stub.py`](../findings/07_logging_stub.py) | an exception in a view is invisible |
| [`findings/08_script_imports.py`](../findings/08_script_imports.py) | what a script can import, and what the database keeps |
| [`findings/class-identity/`](../findings/class-identity/README.md) | committing after imports is what keeps class identity |

[`grail-improvements.md`](grail-improvements.md) is the same material addressed
to the Grail team, prioritised by what it costs and carrying the issue numbers.
Read it if you want to know whether something here is filed, stale, or about to
be fixed.
