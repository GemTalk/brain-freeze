# contextvars holds the current Context in committed state

A fix plan for Grail. Written to be handed to someone working in
`GemTalk/Grail`; nothing in it needs the Brain Freeze repository, though that
is where it was found.

Checked against `origin/main` at `9f46b86c` (2026-09-24). **Not fixed there.**

**The last of three.** Three Grail bugs were found together. The logging one
(`Logger.error` refusing `exc_info=`) merged as `b8bdeb76` on 2026-09-24; the
deployed-module one turned out to be fixed already, in `bcedc68a`. This is the
one still open.

## The bug

`src/python/stdlib/contextvars.py` ends with:

```python
_top_context = Context()
_current_context = _top_context
```

Both are module-level globals in a committed module, so every gem shares one
`Context` object and one `_data` dict. Anything a library stores in a
`ContextVar` is therefore shared across sessions and persists in the
repository, and any two sessions that mutate it collide on commit.

`Context.run()` also rebinds the global (`global _current_context`, line 99),
which writes the committed module dict in its own right.

## How it shows up

`decimal` is the loudest case, because `getcontext()` stores its `Context` in a
`ContextVar` and *every* arithmetic operation that rounds or loses precision
mutates that context's `flags` dict.

Two sessions doing ordinary decimal arithmetic conflict. Caught from a real
`ConflictError` (`gemdb.commit()` raising, conflicts printed):

```
Write-Write (5 objects):
  re.compile('50*$')                                   SrePattern
  re.compile('0*$')                                    SrePattern
  {<class '_pydecimal.Clamped'>: 0, ...,
   <class '_pydecimal.Inexact'>: 1,
   <class '_pydecimal.Rounded'>: 1, ...}               dict
  [0, 1]                                               PyDictCollisionBucket
  [0, 1, 0, 0]                                         PyDictCollisionBucket
```

The dict is a decimal `Context.flags`. A GemStone Write-Write needs the *same*
object, so the two sessions are sharing one `Context` — which they can only
reach through the committed `contextvars` globals.

What it cost downstream: a Flask app serving from inside the database stopped
answering permanently. It commits before each request to take a new view; once
another session committed its half of the flags dict, the app's commit
conflicted, and it could not abort (that would discard its own compiled
handlers), so the pending write stayed pending and every later request failed
identically.

## Why this is Grail's to fix, and the shape it should take

`docs/Concurrency.md` already states the rule:

> mutable state that changes during normal Python execution must live in
> `SessionTemps`, not in classInstVars.

and the stdlib has had this applied before: `#'___GrailRandomGenerator___'`
(`random`), `#'___GrailSecretsGenerator___'` (`secrets`), and
`re._cache = SessionDict("re._cache")`. `contextvars` is the same problem,
unmigrated. It is strictly smaller than the monkey-patch migration in
`03d51ac3`.

Fixing it fixes `decimal` without touching `_pydecimal`, and every other
library built on `ContextVar` with it.

## The change

Use the existing facade, `SessionDict` from `_grail_session`, which re-fetches
`gemstone.sessionDict(name)` on every access and imports `gemstone` lazily so an
importer's module body is not perturbed. `re/__init__.py` and `jinja2/lexer.py`
are the precedents.

Replace the two globals with a per-session holder and an accessor pair:

```python
from _grail_session import SessionDict

_state = SessionDict("contextvars")

def _current():
    ctx = _state.get("current")
    if ctx is None:
        ctx = Context()          # this session's top context, made on demand
        _state["current"] = ctx
    return ctx

def _set_current(ctx):
    _state["current"] = ctx
```

There is no module-level `_top_context` afterwards: the top context is created
per session, lazily, the first time that session asks.

### Every site that touches the globals

Nine references, five call sites. Line numbers re-checked against
`origin/main` at `9f46b86c` and unchanged from `1f2f5ed1`.

| Line(s) | Site | Change |
| --- | --- | --- |
| 99–106 | `Context.run()` | drop `global`; `self._prev = _current()`, `_set_current(self)`, and `_set_current(self._prev)` in the `finally` |
| 175 | `ContextVar.get()` | `_current()._data.get(...)` |
| 185 | `ContextVar.set()` | `ctx = _current()` |
| 203–208 | `ContextVar.reset()` | `_current()` in the identity check and both `_data` mutations |
| 218–219 | module body | delete; replaced by `_state` |
| 229 | `copy_context()` | `return _current().copy()` |
| 232–234 | `_get_current_context()` | `return _current()` |

`Context._entered` and `Context._prev` are instance state and need no change
once the contexts themselves are per-session.

## Acceptance

Three tests, and the first is the regression that matters.

1. **Two sessions setting the same `ContextVar` both commit cleanly, and
   neither sees the other's value.** This is the bug, reduced.
2. **Two sessions performing `Decimal` arithmetic that sets `Inexact` and
   `Rounded` both commit cleanly.** This is the bug as it was met, and it
   should pass without `_pydecimal` being touched.
3. **A fresh session starts with clean decimal flags** — no state inherited
   from whatever ran last week.

Follow the naming already used for this class of regression, e.g.
`ImportlibTestCase >> testCompilationCountersLiveInSessionTempsNotCommitted`.

Also:

- Add the new key to the SessionTemps registry table in `docs/Concurrency.md`,
  and move `contextvars` out of any "acceptable as committed" reading.
- `contextvars` underpins `asyncio` and `decimal`; run those suites.

## Out of scope, but found with it

**The two `SrePattern` objects in the conflict set.** `re._cache` is already a
`SessionDict` in this very build, so the cache is not what conflicted — the
compiled pattern objects themselves were written by both sessions. That is a
separate question (are patterns interned persistently? is something on the
pattern mutated on use?) and wants its own investigation before it is written
up as one item or two. Fixing `contextvars` alone will not clear it.

**`Logger.error` used to take only `*args`.** Unrelated as a cause, and the
reason this cost a week: every occurrence surfaced as a `TypeError` about
`exc_info` instead of the `ConflictError` underneath. Fixed in `b8bdeb76`
(2026-09-24), so the next person to hit this conflict will at least see it.

## Reproduction

Any two sessions will do:

```python
# session A -- leave it pending, do not commit
from decimal import Decimal
Decimal(1) / Decimal(3)          # sets Inexact, Rounded

# session B -- same arithmetic, then commit
# session A -- commit now: ConflictError, Write-Write on the flags dict
```

A packaged version against a live web app is in the Brain Freeze repository at
`findings/10_shared_session_state.py`, with the reasoning in
`findings/README.md`.
