# A Python runtime reinstall orphans every committed object

Measured on GemDB Code 1.5.0 against this repository's seeded book of 900
policies, not inferred from a single-class case.

## The question

Issue [#72](https://github.com/GemTalk/brain-freeze/issues/72):

> Does the canonical class registry survive a Python runtime reinstall?

**No.** An edited class keeps its identity (see `tests/test_class_identity.py`),
but that does not help here. A reinstall recreates Grail's own classes and
bumps its runtime generation, and the committed objects are left pointing at
classes nothing imports any more.

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

Same name, same module, different class object.

## Why it is easy to miss

The database looks fine.

```
BOOK_READ: ok
POLICY_COUNT: 902
POLICY_ID: BF-100539          <- still reads
POLICY_START:                 <- fails
```

The book is reachable, the policy count is right, and a string attribute reads
back. It breaks only when something touches a date, calls a method, or asks
`isinstance`, and then with this:

```
meta path spec for 'datetime.timedelta' has no loader
```

which names neither the class, nor the upgrade, nor the object. It does not
arrive as a Python exception, so a `try/except` around the call does not catch
it.

## Loading the code again does NOT fix it

Loading the code replaces the code; what is broken is the committed objects'
pointer to their class. (Measured with the redeploy script that
`tools/load.py` replaced.)

## What does fix it

```sh
gemdb tools/load.py         # the code
gemdb tools/seed.py         # the objects
```

After both, `ISINSTANCE_POLICY: True` and every figure matches a freshly
seeded book.

**This book can be rebuilt from `data/*.csv`.** A customer with real committed
data has no reseed to fall back on, and this is what an ordinary extension
update does to them by default.

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
- [Grail#1181](https://github.com/GemTalk/Grail/issues/1181) and
  [#72](https://github.com/GemTalk/brain-freeze/issues/72) — the Grail half.
