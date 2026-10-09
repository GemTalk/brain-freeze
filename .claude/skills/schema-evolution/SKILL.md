---
name: schema-evolution
description: Change the schema of the objects GemDB stores for Brain Freeze, meaning the classes in brainfreeze/ (Claim, Event, Policyholder, Book, SavedQuote), and carry the change through the web app, the JSON API and the running database without a migration or a restart. Use it when someone asks to add, rename or remove a field, record something new on a claim, policy or event, do step 3 of the README, or "change the schema", and when a change would alter what stored data means.
---

# Evolve the schema

The objects in the database are instances of the classes in `brainfreeze/`.
`gemdb tools/load.py` rebuilds a changed class in place, so the 2,172
claims committed before the change are still instances of `Claim` and read
its new definition. The app serves the new code on its next request. Adding
a field needs no migration, no reseed and no restart. Other changes do,
and this skill says which.

Read these first:

- README step 3, the change the tutorial makes.
- `features/answers/step3.patch`, the worked answer: `Claim.flavour` and
  `Claim.toppings` from the model to the form, the claim page and the
  JSON, end to end. Copy its shape.
- The docstrings of `tools/load.py` (what loading does and doesn't do)
  and `web/routes.py` (why loaded views are live, and what needs a
  restart).

## 1. Work out what kind of change it is

- **Additive**: a new field, a new property or method, or a rule that
  reads fields already stored. It's code only: edit, load, done. Most
  requests are this kind.
- **Reshaping**: renaming or removing a field, changing its type, units or
  meaning, or moving it to another class. The objects already stored still
  hold the old shape, and loading code doesn't touch them. See step 6, and
  agree the plan with the person before you start.
- **A new route, or a change to `web/app.py`**: the app builds those once,
  when it starts, so they need a restart. Tell the person.

Also work out who the change is for:

- **The reader doing the tutorial** (README step 3, or step 5's "ask it to
  make the change from step 3"): make the change in their working tree and
  load it. Don't commit it. The tutorial and its acceptance suite need
  `main` without it.
- **A lasting change to this repo**: work on a branch, with tests, and
  open a PR (steps 4 and 7).

## 2. Add the field to the class

Follow `Claim.rule`, `Book.serials` and the step 3 patch:

```python
class Claim:
    #: Added after claims were committed. A class attribute as well as an
    #: instance one, so a claim filed before it existed reads the default
    #: through the class.
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

- **The class-level default is the whole migration.** Every object
  committed before the change reads it, because it has no value of its own.
- **The default must be immutable**: `None`, a number, a string or a
  tuple. Never a list, dict or set: every old object would share that one
  object, and appending to it would write to all of them. If a field needs a
  mutable value, put `None` on the class and make the value the first time
  one object needs it, as `Book.issue` does for `serials`.
- **Add a constructor argument as a keyword with a default**, and keep the
  existing arguments where they are. Set the instance attribute only when a
  value is given.
- **Keep money in `usd()`**, as `Claim`, `Policyholder` and `SavedQuote`
  do. A float is refused.
- Code that walks the whole book from a session that might not have the
  new class yet, such as a notebook that hasn't refreshed, can read
  `getattr(obj, "field", default)`. `analysis.denial_rules` does this for
  `rule`.

## 3. Carry it through the app

For `Claim`, the patch touches each of these. Other classes have the same
layers.

- **Choices**: `web/forms.py`, as module-level lists.
- **The form**: `web/templates/claim_form.html`. Use `ui.chip` for one
  choice and a checkbox per option for several.
- **The view**: in `web/routes_html.py`, pass the choices to the form's
  render. Where the view builds the object, read the answer from
  `request.form`, with `.getlist()` for several values and `or None` for
  none.
- **The pages**: `decision.html`, and `policy.html` or `claims.html` if
  the field belongs there. An object with no value must read as "none" and
  never raise.
- **The JSON API and agents**: add the key in `web/wire.py`. Tuples go out
  as lists. A money field goes through `money()` and into `MONEY_KEYS`,
  and `tests/test_api.py` checks that list.
- **Analysis**: `brainfreeze/analysis.py`, if the field changes a figure.

In `web/`, reach another module through its name, as in `lookups.book()` or
`pages.render(...)`. `from module import name` takes a copy that loading
won't update. In scripts, import `brainfreeze` modules as
`import brainfreeze.module`, because the `from` form hands back the
committed copy without checking the file (GemTalk/Grail#1223).

## 4. Test it

- Add unit tests in `tests/`:
  - a new object carries the field;
  - an object from before the change reads the default (simulate one with
    `del obj.field`, as the `serials` test does, if the constructor always
    sets it);
  - the wire payload has the key;
  - the form and the page show it.
- Run `python3 -m unittest discover`.
- `tests/test_tutorial_answer.py` checks that `features/answers/step3.patch`
  still applies. A lasting change near the lines it touches, even a
  reworded comment, can stop it applying. If so, make step 3 again on top
  of your change and write the patch out afresh, with
  `git diff -- brainfreeze web > features/answers/step3.patch`. Do this on
  a scratch copy, and take the step 3 change back out afterwards.

## 5. Load it into the running app

```sh
gemdb tools/load.py
```

```console
Loaded <the modules that changed>. Committed.
Reload the page: the running app serves what you loaded.
```

- If it prints "Nothing had changed", the file wasn't saved, or the code
  isn't in `brainfreeze/` or `web/`.
- Leave the app running. Check the change by reloading pages
  (http://127.0.0.1:5050/), not by restarting:
  - the form, or `curl` it, shows the new inputs;
  - an object from before the change still loads and shows the default,
    for example claim CLM-001285 at `/policies/BF-100539/claims/CLM-001285`;
  - it reads the same from a fresh session:
    `gemdb -c 'import gemdb; c = gemdb.root["brainfreeze"]["BF-100539"].claims[0]; print(c.claim_id, c.flavour)'`.
- Filing a claim or buying a policy to test writes into the person's book.
  Ask first, or let them do it.
- A notebook, or any other open session, sees loaded code after
  `gemdb.refresh()`.
- Run the tests inside the database: `gemdb tools/run_db_tests.py`.

## 6. Reshape stored data

Loading never rewrites stored objects. There are two ways to do it, and
the person chooses.

- **A migration script**, `tools/migrate_<what>.py`, in the shape of
  `tools/lapse.py`: one session that walks `gemdb.root["brainfreeze"]`,
  rewrites each object that still has the old shape, prints what it
  changed, and commits. Make it safe to run twice. Do it in this order:
  1. Load code that reads both the old and the new shape.
  2. Run the migration.
  3. Remove the old-shape reading in a later change.

  If the app writes the same objects in the meantime, the commit raises
  `gemdb.ConflictError`. Abort and run it again.
- **`gemdb tools/seed.py`** rebuilds the book from `data/*.csv` and
  replaces `gemdb.root["brainfreeze"]` wholesale. That discards every
  policy, quote and claim the app has written. Run it only with the
  person's explicit go-ahead.

If the field belongs in the sample data too, the CSV columns,
`tools/seed.py` and `data/generate.py` change with it.

## 7. Undo, or finish

- **Undo**: revert the files and run `gemdb tools/load.py` again. The
  acceptance suite does this after step 3. Objects written while the change
  was live keep the values they were given, but nothing reads them once the
  code is gone.
- **Finish a lasting change**: commit on the branch and open a PR. Say in
  it what loading changed live, and anything that needs a restart or a
  migration.

## Report

Tell the person:

- what changed, layer by layer;
- whether it's loaded into the running app, and what you checked there;
- what an object from before the change now reads;
- anything that still needs a restart, a migration or their decision;
- whether it's committed, or left in their working tree.
