# Finding 1: committing after the imports is what keeps class identity

**Not ours.** These six scripts come from the parallel Brain Freeze demo that
lived in `GemDB_Code`, pinned at
[`c9c261a`](https://github.com/GemTalk/GemDB_Code/tree/c9c261ac017fd7831cd29aa71b79da4ee8c1ed9b/docs/demo/brain-freeze/class-identity).
They are kept because that demo is being retired and this is the one finding it
scripted more rigorously than we did — four processes, two arms differing in a
single token.

Run them in order, each in its own session:

```sh
gemdb findings/class-identity/commit_write.py
gemdb findings/class-identity/commit_read.py
gemdb findings/class-identity/abort_write.py
gemdb findings/class-identity/abort_read.py
```

`commit_write.py` and `abort_write.py` differ only in `gemdb.commit()` versus
`gemdb.abort()`, and in which of two identical sample modules they import. The
finding is the difference in what the *reading* scripts print.

## It reproduces here

Measured 2026-09-09 on GemStone/S 3.7.5, Grail `c875e56`:

```
commit arm:   isinstance True    type(record) is Sample True    id 2653000 both sessions
abort  arm:   isinstance False   type(record) is Sample False   ids differ
```

So **their rule 1 holds on our Grail exactly as they describe it.** Importing a
module is a write; committing it keeps that compiled class, and a later session
importing the same unchanged source gets the same class object back. Aborting
throws it away and the next session compiles a throwaway.

That matters for reading the disagreement recorded in
[`../README.md`](../README.md): we do **not** contradict them about class
identity in general. We contradict their *rule 2* specifically — whether
`isinstance` survives when the class **source is edited** — which
[`../03_class_identity.py`](../03_class_identity.py) measures and they measured
on Grail `46c2a68`.

## Cleanup

Unlike our own findings scripts, these leave their records behind. Remove them
when you are done:

```sh
gemdb -c 'import gemdb
for key in ("finding1_committed", "finding1_aborted"):
    if key in gemdb.root:
        del gemdb.root[key]
gemdb.commit()
print("cleaned:", sorted(gemdb.root.keys()))'
```
