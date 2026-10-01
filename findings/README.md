# Findings

Reproductions of GemDB and Grail bugs that are **still live** on GemDB Code
1.5.3 (Grail `84821c1`). Each is here until the bug is fixed, or until an
upstream issue carries its reproduction. Then it goes: git keeps it.

Run any of them with `gemdb findings/<name>`. Fixed findings were removed on
2026-09-30; the old write-ups are in the history before that date.

| Finding | What it shows | Upstream |
|---|---|---|
| [`06_statistics_decimal.py`](06_statistics_decimal.py) | `statistics.mean` and `median` over Decimals end the session instead of raising | not yet filed |
