# Logger.error(..., exc_info=True) raises over the exception it was called to report

A fix plan for Grail. Written to be handed to someone working in
`GemTalk/Grail`; nothing in it needs the Brain Freeze repository.

Checked against `origin/main` at `9f46b86c` (2026-09-24). **Not fixed there.**

**The set.** Three Grail bugs were found together and are handed over together,
this one among them. Each is independent; they interact, and this is the order
worth doing them in:

| | | |
| --- | --- | --- |
| `docs/grail-logging-exc-info.md` | `Logger.error(..., exc_info=True)` raises | do first — it makes the others findable |
| `docs/grail-contextvars-session-state.md` | the current Context is committed state | design settled, ready to write |
| `docs/grail-deployed-module-bindings.md` | a deployed module keeps another session's modules | ~~open~~ — fixed upstream in `bcedc68a` |

## The bug

`src/python/stdlib/logging/__init__.py` declares

```python
def error(self, msg, *args):
```

with no `**kwargs`, so `logger.error(msg, exc_info=True)` raises `TypeError:
Logger.error() got an unexpected keyword argument 'exc_info'`.

That call is not exotic. It is what Flask does when a view raises:

```python
self.logger.error("Exception on %s [%s]", path, method, exc_info=True)
```

So the code that exists to report an exception raises one of its own, and the
`TypeError` lands in the log **standing over the real exception**, which is
never recorded anywhere.

`LoggerAdapter.error` in the same file already takes `**kwargs`, so the two
halves of the module disagree with each other.

## Why it is worth doing first

It is a small fix that makes other bugs findable. A write-write conflict in a
long-running app (brain-freeze issue #83) took a week to diagnose because every
occurrence showed up as this `TypeError` instead of the `ConflictError`
underneath it. Whatever the next hard bug in a served application turns out to
be, this is the thing standing between the reporter and it.

## The fix is already written

Branch `fix/logging-exc-info`, one commit `5a07f235`, by Steven R. Baker,
2026-09-08. It is **909 commits behind `origin/main`** and `git merge-tree`
reports **no conflicts** against it.

```
 src/python/stdlib/logging/__init__.py              | 143 +++++++++++++++------
 tests/.../PythonTests/FlaskScaffoldingTestCase.gs  | 100 ++++++++++++++
 tests/python/pkg_scaffolding/use_logging.py        | 125 ++++++++++++++++++
```

What it does:

* `LogRecord.__init__` gains `exc_info=None`, and stores both `exc_info` and a
  rendered `exc_text`. The commit explains the divergence from CPython: CPython
  keeps the triple and lets the Formatter render it, this renders eagerly,
  because losing the traceback is worse than formatting it early.
* A new `_format_exc_info` accepts the three things callers pass in the wild —
  `True`, a `(type, value, traceback)` triple, and a bare exception — and
  returns `None` rather than raising, on the principle that logging must not
  raise.
* `Logger._log` gains `exc_info=None`; `debug`, `info`, `warning`, `error`,
  `critical` and `exception` all gain `**kwargs`; the module-level functions
  follow.
* The `Formatter` appends `exc_text` when present.

## The plan

1. Rebase `fix/logging-exc-info` onto `origin/main`. No conflicts are expected;
   909 commits have landed under it, so expect churn around it rather than in it.
2. Re-read the diff as if new. It was written against a much older tree and has
   never been reviewed.
3. Check three things the original may not have covered, each of which is the
   kind of thing 909 commits could have changed:
   * `LoggerAdapter` parity — it already took `**kwargs`; does it now forward
     `exc_info` to the underlying logger, or swallow it?
   * `stack_info` and `stacklevel`, the other two keywords CPython's signature
     carries. Accepting and ignoring them is fine; raising on them is the same
     bug in a different coat.
   * Whether anything downstream reads `LogRecord.exc_info` expecting CPython's
     triple rather than the rendered text.
4. Run the tests it ships (`FlaskScaffoldingTestCase`), plus the logging suite.
5. Open the PR. Someone should also find out why a finished, tested branch sat
   unmerged for two weeks — if it was a deliberate hold, that reason still applies.

## Acceptance

1. `logger.error("boom", exc_info=True)` inside an `except` block emits the
   message **and** the traceback, and raises nothing.
2. The same with a `(type, value, traceback)` triple, and with a bare exception.
3. `logger.error("boom", exc_info=True)` with **no** active exception emits the
   message and no "NoneType: None" noise.
4. A Flask view that raises produces a log entry naming the view's exception,
   not a `TypeError` about `exc_info`. This is the one that matters; the other
   three are how you get there.
