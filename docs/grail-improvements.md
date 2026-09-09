# What this demo needs from Grail

Grail is the Python implementation that runs inside the database, and every
surface in this demo is Python, so most of what cost time here is Grail's.
This is the list, prioritised by whether a surface works, whether the three
surfaces agree with each other, and everything else.

Written 2026-09-08. Evidence is in [`findings/`](../findings/) as scripts that
reproduce each item on your own database.

---

## Read this before adding anything to the list

**Three versions of Grail are in play and they behave differently.**

| Where | Sha | Date |
| --- | --- | --- |
| the database this demo runs on | `c875e56` | 2026-09-03 |
| what GemDB Code stages to bundle | `ac1e626` | 2026-09-04, 28 ahead of `c875e56` |
| Grail `main` | `0f9ac210` | 2026-09-07, 100 ahead of `c875e56` |
| what the open issues were measured on | `5e8fc42` | 2026-08-27, 321 behind `ac1e626` |

That spread has already produced wrong entries on both demos' lists, so the
first task is bookkeeping:

- **#847** — "a script cannot import the module next to it" — is **closed,
  fixed 2026-08-29 by `8c8f503e`, and the fix is in the Grail GemDB stages.**
  [the parallel demo](https://github.com/GemTalk/GemDB_Code/blob/c9c261ac017fd7831cd29aa71b79da4ee8c1ed9b/docs/demo/brain-freeze/) (pinned at `c9c261a`) still documents it as a live finding.
- **#848** — `sys.stdout`/`sys.stderr` are `None` — likewise closed and shipped.
- **`random.choices` is implemented** (`random.gs:402`, weights and all). An
  earlier note in this repo's PLAN.md said it was missing. It was wrong at this
  sha.
- **Class identity behaves differently between `46c2a68` and `c875e56`** —
  `isinstance` survives an edited class on the first and does not on the second.
  Both are reproducible. Nobody appears to have noticed, and nothing is filed.
  This is the most concrete thing either demo has to say to the Grail team.
  See `findings/03_class_identity.py`.

So: **re-measure at the sha GemDB actually ships before filing anything below
that is not already filed.** And GemDB should be able to tell a user which Grail
their database is carrying.

## What is already open

Fifteen issues, and this demo's work is most of the recent ones. The high
numbers are PRs; there have only ever been eighteen issues.

| # | Title |
| --- | --- |
| 851 | Compiling Python is a repository write at surprising times, and a first-call race can wedge a session's commits |
| 850 | `sys.argv` is the host topaz command line, not the script's |
| 849 | Exceptions carry no `__traceback__`, so `traceback.format_exc()` can never report a frame |
| 867 | `except ZeroDivisionError` does not catch `decimal.DivisionByZero` |
| 857 | Equal `Decimal` and `float` values hash differently |
| 856 | An unimported `Decimal(...)` constructs a GemStone `ScaledDecimal` |
| 846 | Re-represent `decimal.Decimal` as coefficient + exponent |
| 861 | `os.remove` on a path containing `$` deletes the shell-expanded path |
| 824 | `importlib` `removeKey` not working, subsequent `ImportError` |
| 855, 825 | CI gate message; `endPosition` past the end of a `def` |
| 20–23 | migrated from GitLab: Python tests, three demo proposals |

## P0 — a surface does not work

**1. Render throughput. Unfiled, and not yet diagnosed.**
900 table rows through `render_template_string` take about a minute, so this
demo pages 25 at a time. The mechanism is known and the cause is not, and the
difference matters:

- Grail implements **every Python generator as a forked `GsProcess` with a
  two-semaphore handshake per `yield`** (`PythonGenerator.gs`). Jinja compiles a
  template to a generator function and `render()` is `''.join(root_render_func(ctx))`,
  so the whole page comes out through that handshake, several yields per row.
- But a few thousand semaphore round-trips does not obviously cost sixty
  seconds. Two other candidates are at least as likely: interpreted attribute
  access (`environment.getattr`, `Context.resolve`, `Markup` escaping, ~15 per
  row × 900), and **#851** — the first render compiles the template's generated
  Python, which is a repository write.

**Measure before filing.** Render 900 rows, then 90, then 9: a linear curve
points at per-yield or per-lookup cost, a fixed head points at compilation. Then
the same template with the loop body reduced to a single literal, which splits
yields from lookups. Half an hour against a real stone decides whether this is a
scheduler fix, a Jinja-shaped fix, or #851 wearing a costume.

**2. #851 — compiling Python is a repository write at surprising times.**
Everything downstream of "a session is a unit of work" is undermined by it: a
clean session is dirty before the user's first line, `gemdb.transaction()`
cannot open a script, `refresh()` refuses, and a first-call race can fail an
*unrelated* session's commit. It is also the reason the notebook's refresh beat
needs two calls instead of one.

Note the attribution is not settled: #851 blames the **first call** to a
function, and on `c875e56` a first call to a never-before-compiled function left
`needs_commit()` `False` — the dirtiness came from running the code at all.
`findings/04_dirty_session.py` measures both.

**3. `logging.Logger.error(self, msg, *args)` rejects `exc_info=`. Unfiled.**
Grail's `logging` is a 437-line hand-written stub. Flask's own error handler
passes `exc_info=`, so the logger raises `TypeError` and buries the exception it
was called to report — an exception in a view becomes invisible, and the real
traceback is somewhere further up the log. The signature fix is two lines and
is the cheapest item on this page. (`LoggerAdapter.error` in the same file
already takes `**kwargs`.)

**4. #849 — exceptions carry no `__traceback__`.** Without it every Grail
application debugs the way item 3 describes: a true message, and nothing that
says where. In a web app serving a dozen routes that is the difference between a
thirty-second fix and an afternoon.

## P1 — the three surfaces have to agree with each other

**5. `round()` is half-up in Grail and banker's in CPython. Unfiled.**
`round(2.5)` is 3 inside the database and 2 outside it, so the same premium
computed in the notebook and in the web app can differ by a cent. This is
quieter than anything in P0 and it attacks the PRD's central claim — one
dataset, three surfaces, one answer — rather than merely annoying the developer.
Both demos independently worked around it: this repo pins every figure to a
seeded dataset, and theirs spells out `round_div` by hand and never calls
`round()`.

**6. The Decimal cluster — #846 first, then #856, #857, #867. Partly stale;
re-measured 2026-09-09 on `c875e56`.**

**`Decimal("19.99") * 3` no longer raises.** It returns `Decimal("59.97")`.
The entry above was written from an older sha and the advice that followed
from it — "integer cents everywhere" — is no longer the only option. This
repo now holds money as `decimal.Decimal` and it works: `0.1 * 3` is exactly
`0.3`, ten dimes sum to exactly `1.0`, and `170.10 / 12` is exactly `14.175`
where the float is `14.174999999999999`.

What is still missing or wrong, each of which cost time here and each of which
`brainfreeze/money.py` now works around:

- **No `Decimal.quantize`**, so rounding to the cent has to be hand-written.
  This is the single most valuable gap to close: it is the operation money
  code reaches for first.
- **No `Decimal.as_tuple`.**
- **`round(Decimal, n)` brings the VM down** with `MessageNotUnderstood ... a
  Decimal does not understand #'*'` — not a Python exception, no traceback, no
  line number. The builtin is the obvious thing to reach for and it is a trap.
- **`Decimal // int` raises `TypeError`.** `int(x / 10)` is the workaround.
- **`int(Decimal)` floors, where CPython truncates toward zero.** So
  `int(Decimal("-14.5"))` is `-15` here and `-14` there, and any rounding
  written over a signed value gives two different answers on two surfaces of
  the same application. Round a magnitude and reapply the sign.
- **Trailing zeros are not preserved**: `Decimal("170.10")` is `Decimal("170.1")`,
  before and after a commit. Values and arithmetic are unaffected, but no
  display string can come from `str()`.
- **Division that does not terminate degrades to ~16 significant digits**:
  `Decimal(1) / Decimal(3)` is `0.3333333333333333`, where CPython gives 28.
- **`statistics.median` and `statistics.mean` fail on Decimals.**
- **`Decimal` compares equal to a float** that is not exactly equal to it.
  Under CPython `Decimal("92081.22") == 92081.22` is `False`, correctly, and
  here it is `True` — so a test that pins money against a float literal passes
  in the database and fails outside it.

Persistence is sound: a `Decimal` committed to `gemdb.root` reads back as a
`Decimal` with its value, ordering and equality intact.

#846 is still the enabling change; #856, #857 and #867 still stand.

**7. Module staleness — a *deployed* package never picks up an edit. Unfiled,
and now understood; measured 2026-09-09.**

Editing a package submodule keeps returning the previously compiled module,
while a top-level module in the same tree picks up edits immediately. That much
was already recorded. What was not: **the mechanism has a name and an error
message that only appears if you fight it.**

Once `brainfreeze` has been imported once, it is *deployed*. A brand-new
session's `import brainfreeze` returns what the database compiled, not what the
file says, and nothing reports the difference. This cost the whole of the money
work: the database went on returning `31.499999999999996` from a float
`annual_premium` for an hour after the file on disk had returned exact Decimal,
with every test passing against the old rules.

The dead end to know about: deleting it from `sys.modules` and re-importing
does not reset it, it *bricks* it for the rest of the session —

```
ImportError: module 'brainfreeze' is canonical (deployed); it was removed from
sys.modules in this session. Use importlib.reload() to re-execute it, or assign
a replacement into sys.modules to substitute it.
```

`importlib.reload` does work, with two conditions nothing states. It must run
in dependency order, because reloading a module makes it briefly unresolvable
to anything that imports it; and each reloaded module must be put back into
`sys.modules` by hand, because `reload` leaves a deployed module absent from it
and the next module up imports by name. `redeploy.py` in this repo is those two
rules written down, and it is what FR-7.6's "redeploy" has to mean here.

What the product should offer: a command that redeploys a package and says what
changed, and — more important — **some way to know the code in the database is
not the code on disk**. Today nothing distinguishes them.

**8. `contextvars` do not span forked green threads. Unfiled.**
Grail renders each Jinja template in a forked green thread, and the threaded dev
server's per-request `ContextVar` cannot cross that boundary, so `url_for`
inside a template cannot see the active request. This is why a Flask app here
must run `threaded=False`. Same root as item 1's first candidate, and worth
measuring alongside it.

**9. #850 — `sys.argv` is topaz's command line.** `sys.argv[1]` is `-L`. Any
CLI-shaped script — an importer, a seeder taking a path — cannot read its own
arguments.

## P2 — worth having

**10. `import x.y as m` fails, and plain `import x.y` leaves the name unbound.**
`from x.y import Thing` is the form that works. Re-measure — the `sys.path` work
in `8c8f503e` may have moved it.

**11. No `strptime`.** Both demos parse ISO dates by hand.

**12. #861 — `os.remove` and `$`.** Data-loss shaped, and cheap.

**13. Publish what the bundled standard library actually contains, per sha.**
Both demos maintain private guesses at this. One of ours was already wrong
(`random.choices`), and this repo's packaging test encodes an allowlist that is
really a record of what Grail was observed to have on one afternoon. A
`grail.stdlib` report, or a generated manifest beside `GRAIL_VERSION`, would
retire the guessing.

---

## The argument for taking this seriously

Two independent implementations of the same PRD, written without knowledge of
each other, hit the same four walls: class identity after an edit, sessions that
are dirty before the user does anything, Flask's logging stub swallowing view
exceptions, and `sys.path` not containing the script's own directory. That is
not two teams being careless in the same way. It is the shape of the first week
of anyone building a Python application on this database.
