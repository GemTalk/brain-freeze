# Findings, as scripts you can run

Five things about running Python inside GemDB that cost real time while
building this demo, each reduced to a script that reproduces it on your own
database rather than asking you to believe a transcript.

```sh
export PATH="$HOME/GemDB/bin:$PATH"     # not needed in a VS Code terminal
gemdb findings/01_shim_missing.py
gemdb findings/02_main_namespace.py
gemdb findings/03_class_identity.py     # run this one twice
gemdb findings/04_dirty_session.py
gemdb findings/05_module_monkeypatch.py
```

`class-identity/` is a fourth-and-a-half: four scripts in two arms, inherited from the demo being retired. See
[`class-identity/README.md`](class-identity/README.md).

All five are safe. Only 03 writes to `gemdb.root`, and it removes what it
wrote; 05 patches the `gemdb` module and puts it back.

Measured on 2026-09-08 against GemStone/S 3.7.5 with Grail `c875e56`. **Two of
them disagree with the same findings reached independently in
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

That is not hypothetical: `gemdb app.py` failed with `name 'PREAMBLE' is not
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

## 3. Editing a class compiles a different class

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
foresight rather than magic. Editing a model live in front of an evaluator
shows them an `AttributeError`.

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

## 5. A patched module stays dirty, and commit will not clear it

Found by a test that could not work. Issue #47 made the web app `commit()`
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

---

## What to do with these

The four shared findings — class identity, dirty sessions, Flask's logging stub
and `sys.path` — were reached twice, independently, from different code. That
is the strongest argument either demo makes that **these are GemDB's to fix or
document, not each demo's to work around.**

Finding 1 is the one to raise first: it is undocumented, it produces a database
that looks healthy in every other respect, and the error message points nowhere
useful.
