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

Every `gemdb` command here runs from the repo root. If your shell prints
`gemdb: command not found`, run `../bin/gemdb` instead (step 6 has the one
exception). Install Brain Freeze Demo puts this checkout at
`<rootPath>/brain-freeze`, so GemDB's `bin/` is next door.

How a model change works here, whatever the class or field:

- **The code is the schema.** A stored object is an instance of its class
  in `brainfreeze/`, and reads whatever that class says now.
- **A class-level default is the migration.** Objects from before the
  change have no value of their own and read the class's.
- **Loading is the deploy.** `gemdb tools/load.py` rebuilds the changed
  modules in place, and the app serves them on its next request. Routes
  and `web/app.py` are the exception: they need a restart.
- **Find the layers from the code, not from a list.** Grep for an existing
  field of the class you're changing and follow it through `web/`.

The docstrings of `tools/load.py` and `web/routes.py` say what loading does
and doesn't reach. README step 3 and `features/answers/step3.patch` are one
worked example, an additive change to `Claim`. Read them to see the layers a
field passes through, not as a shape to copy.

## 1. Work out what kind of change it is

- **Additive**: a new field, a new property or method, or a rule that
  reads fields already stored. It's code only: edit, load, done. Most
  requests are this kind.
- **Reshaping**: renaming or removing a field, changing its type, units or
  meaning, or moving it to another class. The objects already stored still
  hold the old shape, and loading code doesn't touch them. That usually
  still needs no migration script: read both shapes, and upgrade objects as
  they're written (step 5). Agree the plan with the person before you start.
- **A new route, or a change to `web/app.py`**: the app builds those once,
  when it starts, so they need a restart. Tell the person.

Also work out who the change is for:

- **The reader doing the tutorial** (README step 3, or step 5's "ask it to
  make the change from step 3"): make the change in their working tree and
  load it. Don't write or run tests, and don't commit it. The tutorial and its acceptance suite need
  `main` without it.
- **A lasting change to this repo**: work on a branch, with tests, and
  open a PR (steps 6 and 7).

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

For `Claim`, the step 3 patch touches each of these. Another class has its
own form, view and page, or none: find them by grepping for one of its
existing fields.

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
won't update.

## 4. Load it and look

```sh
gemdb tools/load.py        # or, if gemdb is not found: ../bin/gemdb tools/load.py
```

```console
Loaded <the modules that changed>. Committed.
Reload the page: the running app serves what you loaded.
```

- If it prints "Nothing had changed", the file wasn't saved, or the code
  isn't in `brainfreeze/` or `web/`.
- Leave the app running. Check the change by reloading pages
  (http://127.0.0.1:5050/), not by restarting. One look of each is enough:
  - the form, or `curl` it, shows the new inputs;
  - an object from before the change still loads and shows the default,
    for example claim CLM-001285 at `/policies/BF-100539/claims/CLM-001285`;
  - it reads the same from a fresh session, for the step 3 change:
    `gemdb -c 'import gemdb; c = gemdb.root["brainfreeze"]["BF-100539"].claims[0]; print(c.claim_id, c.flavour)'`
    (`../bin/gemdb -c ...` if gemdb is not found).
- Filing a claim or buying a policy to test writes into the person's book.
  Ask first, or let them do it.
- A notebook, or any other open session, sees loaded code after
  `gemdb.refresh()`.
- If something's wrong, fix the file and load again. Don't run test suites
  while you're iterating: loading and reloading the page is the whole loop.
- Show the person the result and check it's what they wanted before going
  further.

## 5. Reshape stored data

Adding a field never needs this: the class default from step 2 is enough.
This step is for renaming or removing a field, or changing its type, units
or meaning. Loading never rewrites stored objects, so there are three ways
to handle the objects that already exist. Agree which one with the person.

### Default: read both shapes, upgrade on write

Leave old objects as they are. Store the new shape under a new name with a
class default of `None`, and put a property in front of it that reads the
new shape, or works it out from the old one when an object predates the
change. Renaming `Claim.reason` to `explanation`, for example:

```python
class Claim:
    #: The new shape, on claims written since the change. A claim from
    #: before has none of its own and reads None here.
    _explanation = None

    @property
    def explanation(self):
        if self._explanation is not None:
            return self._explanation
        return getattr(self, "reason", None)    # a claim from before

    def __init__(self, ..., explanation=None):
        ...
        if explanation is not None:
            self._explanation = explanation
```

- Every reader uses the property: views, templates, `wire.py`,
  `analysis.py` and the notebook. Code that reads the stored attribute
  directly sees whichever shape that object happens to have.
- Any code that writes an object for its own reasons writes the new shape,
  so the objects people actually change move over as they're changed. That
  costs no extra transaction and no script.
- Leave the old value where it is. Nothing needs `del`, and removing an
  attribute from a stored object is only tested under CPython here.
- Objects nobody writes keep the old shape, so the old-shape branch of the
  property stays for as long as one of them exists. That's fine while only
  a few places read the field. If you want one shape and simpler code,
  sweep the rest with a migration script (below), then delete the branch.
- Test both shapes. Build an old object by setting the old attribute and
  leaving the new one unset, then check every reader through the property.

### Never upgrade an object when it's read

Rewriting the object inside the getter looks like the same idea, but it
turns every read into a write:

- **In the app**, a page view leaves uncommitted work behind, and
  `take_new_view()` commits it at the start of that instance's next
  request (`web/app.py`). Two instances that upgrade the same object
  conflict, and the loser's abort throws its upgrade away.
- **In a notebook or an agent's session**, reading the book leaves
  uncommitted work, and `gemdb.refresh()` refuses while there is any, so
  browsing the data would break refresh.
- **Analysis over the whole book** would upgrade every object in one
  unplanned transaction: a migration nobody chose to run.

### When you want one shape: a migration script

`tools/migrate_<what>.py`, in the shape of `tools/lapse.py`: one session
that walks `gemdb.root["brainfreeze"]`, rewrites each object that still has
the old shape, prints what it changed, and commits. Make it safe to run
twice. Do it in this order:

1. Load code that reads both shapes, as above.
2. Run the migration.
3. Remove the old-shape reading in a later change.

If the app writes the same objects in the meantime, the commit raises
`gemdb.ConflictError`. Abort and run it again.

### Last resort: reseed

`gemdb tools/seed.py` (`../bin/gemdb tools/seed.py` if gemdb is not found)
rebuilds the book from `data/*.csv` and replaces
`gemdb.root["brainfreeze"]` wholesale. That discards every policy, quote
and claim the app has written. Run it only with the person's explicit
go-ahead.

If the field belongs in the sample data too, the CSV columns,
`tools/seed.py` and `data/generate.py` change with it.

## 6. Test it

Only once the person agrees the change is the one they wanted.

- **The tutorial, or any change left in their working tree**: skip this
  step. Say the tests are there if they want them.
- **A lasting change**: ask before you run anything.

- Add unit tests in `tests/`:
  - a new object carries the field;
  - an object from before the change reads the default (simulate one with
    `del obj.field`, as the `serials` test does, if the constructor always
    sets it);
  - the wire payload has the key;
  - the form and the page show it.
- Run the modules the change touches first, such as
  `python3 -m unittest tests.test_brainfreeze tests.test_api`, and inside
  the database `gemdb tools/run_db_tests.py brainfreeze api`.
- Run the full suites once, just before you open the PR:
  `python3 -m unittest discover`, and `gemdb tools/run_db_tests.py`. If gemdb
  is not found, put GemDB's `bin/` on the PATH for that one command, because
  the runner starts each test module with a bare `gemdb` and `../bin/gemdb`
  alone fails: `PATH="$(cd .. && pwd)/bin:$PATH" gemdb tools/run_db_tests.py`.
- `tests/test_tutorial_answer.py` checks that `features/answers/step3.patch`
  still applies. A lasting change near the lines it touches, even a
  reworded comment, can stop it applying. If so, make step 3 again on top
  of your change and write the patch out afresh, with
  `git diff -- brainfreeze web > features/answers/step3.patch`. Do this on
  a scratch copy, and take the step 3 change back out afterwards.

## 7. Undo, or finish

- **Undo**: revert the files and run `gemdb tools/load.py` again (or
  `../bin/gemdb tools/load.py`). The
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
