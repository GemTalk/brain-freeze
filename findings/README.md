# Findings

Reproductions of GemDB and Grail bugs that are **still live** on GemDB Code
1.5.2 (Grail `b86985f`). Each is here until the bug is fixed, or until an
upstream issue carries its reproduction. Then it goes: git keeps it.

Run any of them with `gemdb findings/<name>`. Fixed findings were removed on
2026-09-30; the old write-ups are in the history before that date.

| Finding | What it shows | Upstream |
|---|---|---|
| [`01_shim_missing.py`](01_shim_missing.py) | A database can be installed without the CPython shim; then `import re`, and so Flask and Jinja, fail | not yet filed |
| [`06_decimal_money.py`](06_decimal_money.py) | `decimal` works; `statistics.mean` and `median` over Decimals end the session instead of raising | not yet filed |
| [`08_script_imports.py`](08_script_imports.py) | What a script can import, and what the database keeps. The live part: `from package import module` returns the committed copy after an edit | [Grail#1223](https://github.com/GemTalk/Grail/issues/1223) |
| [`runtime-reinstall/`](runtime-reinstall/README.md) | A Python runtime reinstall orphans every committed object | [Grail#1181](https://github.com/GemTalk/Grail/issues/1181), [GemDB_Code#31](https://github.com/GemTalk/GemDB_Code/issues/31) |
