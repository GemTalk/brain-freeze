# A Python runtime reinstall orphans every committed object

**Measured 2026-09-24** on GemDB Code 1.5.0, engine 4.0.0.a2, Grail `9a0b0fc`,
against this repository's own seeded book of 900 policies. Not inferred from
the single-class case, and not the same answer.

## The question this settles

Issue [#72](https://github.com/GemTalk/brain-freeze/issues/72) named it as the
one that decides everything:

> Does the canonical class registry survive a Python runtime reinstall?

**No.** Identity reuse for an edited class — which does now work, see
[`../class-identity/`](../class-identity/README.md) — does not help here. A
reinstall recreates Grail's own classes and bumps its runtime generation, and
the committed objects are left pointing at classes nothing imports any more.

## What it looks like

Running `resources/install-grail.sh` (what the extension runs when
`reinstallPythonOnUpdate` fires) against a database holding the seeded book:

```
=== A POLICYHOLDER
Policyholder   committed <class 'brainfreeze.model.Policyholder'>
               live      <class 'brainfreeze.model.Policyholder'>
               same object: False
               isinstance: False
```

Same name, same module, different class object — the finding 3 signature, at
whole-runtime scale and all at once.

## Why it is easy to miss, which is the real point

The database looks fine.

```
BOOK_READ: ok
POLICY_COUNT: 902
POLICY_ID: BF-100539          <- still reads
POLICY_START:                 <- fails
```

The book is reachable, the policy count is right, and a string attribute reads
back correctly. It is only when something touches a date, or calls a method, or
asks `isinstance`, that it breaks — and it breaks with this:

```
meta path spec for 'datetime.timedelta' has no loader
```

which names neither the class, nor the upgrade, nor the object. There is no
traceback: it does not arrive as a Python exception at all, so a `try/except`
around the call does not catch it and a handler that would have logged it never
runs. This repository's through-line again — *the code that exists to report a
problem is the code that breaks.*

## A redeploy does NOT fix it

Measured, because it is the obvious first thing to try and it is the wrong
tree. `gemdb tools/redeploy.py` runs clean, reports every module reloaded, and
the orphaning is unchanged: redeploy replaces the CODE, and what is broken is
the committed objects' pointer to their class.

## What does fix it

```sh
gemdb tools/redeploy.py     # the code
gemdb tools/seed.py         # the objects
```

Verified: after both, `ISINSTANCE_POLICY: True`, every figure matches a freshly
seeded book, and all suites pass — 349 CPython tests, 8 in-database modules.

**We can do that because our book is rebuildable from `data/*.csv`. That is
the whole reason this repository is the one filing it.** A customer with real
committed data has no reseed to fall back on, and this is what an ordinary
extension update does to them by default.

## Check your own database

[`survives_upgrade.py`](survives_upgrade.py) reads only and commits nothing.
Run it either side of an upgrade and diff:

```sh
gemdb findings/runtime-reinstall/survives_upgrade.py > before.txt
# ... let the update happen ...
gemdb findings/runtime-reinstall/survives_upgrade.py > after.txt
diff before.txt after.txt
```

Identical output means the upgrade was clean.

## Filed

- [GemDB_Code#31](https://github.com/GemTalk/GemDB_Code/issues/31) — an update
  must not do this silently. `reinstallPythonOnUpdate` defaults to `true`.
- [#72](https://github.com/GemTalk/brain-freeze/issues/72) — the Grail half.
