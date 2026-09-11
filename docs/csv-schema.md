# The two CSVs, column by column

`data/policyholders.csv` and `data/claims.csv` are the only input this demo
has. `seed.py` reads them and builds the object graph that goes into
`gemdb.root["brainfreeze"]`, and it names every field as it goes — which until
now was the only place a reader could find out what a column holds or what type
it becomes. This file is that dictionary written down: every column in both
files, its type, whether it can be empty, what it means, and which attribute it
turns into.

It exists so the mapping to GemDB classes can be checked rather than inferred.
There is no schema to declare and no mapping file — the mapping is thirty-odd
lines of `seed.py` — so the risk is not that a migration fails, it is that
someone reads `claim_status` and believes `"Not Filed"` is a claim.

**Read this beside [`dataset-for-agents.md`](dataset-for-agents.md), not
instead of it.** That document is the map for someone holding the objects: what
`book` answers to, which names exist, which aggregations are traps. Its §4 warns
that the CSV names are *not* the attribute names and lists the ones that catch
people out. This document is the other direction — the files on disk, in full,
including the columns nothing loads. If you are writing Python against a seeded
book, start there. If you are mapping the files to classes, regenerating them,
or wondering whether a column can be blank, start here.

Every count and range below was read out of the committed CSVs on 2026-09-09.
The generator is deterministic — `python3 -m datagen` writes the same bytes
every run — so these figures hold for as long as `data/` is what is in git.

---

## How the files are written

`datagen/dataset.py` writes both with pandas' `to_csv(index=False)`, which
fixes some things worth knowing before parsing:

- **A missing value is an empty field**, never `NA`, `NaN` or `null`. `seed.py`
  turns those back into `None` by hand — `_float`, `_int` and `_text` each
  return `None` for `""`.
- **A boolean is the word `True` or `False`**, capitalised, so `_bool(text)` is
  `text == "True"`. Anything else in that column would read as `False`.
- **A date is ISO `YYYY-MM-DD`**, and `_date` splits on `-` rather than parsing
  a format. An empty date field crashes it, which is why `policy_lapse_date` is
  guarded at the call site and `policy_start_date` and `event_date` are not.
- **Money is a plain float with trailing zeros dropped.** `170.1` is $170.10,
  not $170.01. Every money column carries one or two decimal places and no
  currency symbol; the unit is USD throughout, recorded in the `_usd` suffix.
- No field in either file contains a comma or a quote, so nothing is quoted.
  Header row, LF line endings, ASCII.
- `datagen` drops its `_risk_score_raw` working column before writing, so
  neither file has an index column or a leading blank.

**The type a column becomes is the loader's, not the text's.** `age` is read
with `int()`, `portion_size_ml` with `_float()`, `migraine_history` with
`_bool()`. A column that looks like an integer is a float in the database if
`seed.py` read it with `float()` — `coverage_limit_per_incident_usd` writes
`25.0` and `portion_size_ml` writes `119.0`, and neither is an int anywhere.

---

## `data/policyholders.csv` — one row per policy

900 rows. `policy_id` is the key: unique, never empty, `BF-100000` through
`BF-100899`. Each row becomes one `brainfreeze.model.Policyholder`, added to
the `Book` under that id.

| column | type in the CSV | can be empty | becomes | what it is |
| --- | --- | --- | --- | --- |
| `policy_id` | `str` | no | `policy_id` (`str`) | the key, `"BF-100539"`. Also the key in `book.policies`. |
| `age` | `int` | no | `age` (`int`) | 5 to 19. Years, at the time the policy was written. |
| `sex` | `str` | no | `sex` (`str`) | `F`, `M`, `Nonbinary/Other`. Not used in pricing. |
| `migraine_history` | `bool` | no | `migraine_history` (`bool`) | a migraine diagnosis. Worth 22 points on the risk score. |
| `tension_type_headache_history` | `bool` | no | `tension_type_headache_history` (`bool`) | 10 points. Never `True` on the same row as `migraine_history` — the generator only draws it for people without one. |
| `typical_consumption_speed` | `str` | no | `typical_consumption_speed` (`str`) | `slow`, `moderate`, `fast`. How this person usually eats, which is not how they ate at any given event. |
| `favorite_trigger` | `str` | no | **`favourite_trigger`** (`str`) | their usual cold treat, one of the six. **The spelling changes**: American in the file, British on the object. |
| `underwriting_base` | `float` | no | `underwriting_base` (`float`) | 4.81 to 90.38, written at full precision on purpose. The starting point the generator drew for this person, before their answers moved it. Recording it is what makes a seeded score reproducible. |
| `underwriting_risk_score` | `float`, 1 dp | no | **nothing — derived** | 1.0 to 100.0, clamped at both ends (2 rows sit at 1.0, 21 at 100.0). The object recomputes it; see [stored versus derived](#stored-versus-derived). |
| `risk_tier` | `str` | no | **nothing — derived** | `Low`, `Medium`, `High`. 137 / 497 / 266. |
| `coverage_plan` | `str` | no | **`plan_name`** (`str`) | `Basic`, `Standard`, `Premium`. 419 / 345 / 136. |
| `coverage_limit_per_incident_usd` | `float` | no | **nothing — derived** | 25.0 / 60.0 / 150.0, one per plan. Read off `COVERAGE_PLANS` instead. |
| `deductible_per_incident_usd` | `float` | no | **nothing — derived** | 10.0 / 5.0 / 0.0, one per plan. |
| `annual_premium_usd` | `float`, USD | no | **`annual_premium`** (`float`) | $27.81 to $374.18. The plan's base premium, loaded for the tier, times a little noise. |
| `monthly_premium_usd` | `Decimal`, USD | no | **nothing — derived** | `annual_premium_usd / 12`, half-up. Agrees with `p.monthly_premium` on all 900; see [stored versus derived](#stored-versus-derived). |
| `policy_start_date` | ISO date | no | `policy_start_date` (`date`) | 2026-01-01 to 2026-10-27. |
| `policy_term_months` | `int` | no | `policy_term_months` (`int`) | 12 on every row. `policy_end_date` is start plus 30 days a month, so a term is 360 days, not a calendar year. |
| `policy_status` | `str` | no | `policy_status` (`str`) | `Active` (683) or `Lapsed` (217). **This is a fate over the whole term, not "in force today"** — most of those lapse dates have not arrived. Use `is_in_force_on(date)`. |
| `policy_lapse_date` | ISO date | **yes — 683 rows** | `policy_lapse_date` (`date` or `None`) | 2026-02-04 to 2027-09-23, always 30 to 358 days after the start. Empty on exactly the 683 `Active` rows and present on all 217 `Lapsed` ones: the two columns never disagree. Cover runs to this date inclusive. |

## `data/claims.csv` — one row per cold-treat event

4,993 rows, and the name is a misnomer worth stating plainly: **most rows are
not claims.** 2,821 of them are a cold treat that hurt nobody or that nobody
filed on. Those rows are the denominator, and throwing them away is what stops
"how often does a slushie cause brain freeze" being answerable.

Each row becomes one `Event`, appended to its policyholder's `events`. A row
with a `claim_id` also gets a `Claim`, hung off that event as `event.claim`;
the other 2,821 get `claim=None`.

| column | type in the CSV | can be empty | becomes | what it is |
| --- | --- | --- | --- | --- |
| `event_id` | `str` | no | `Event.event_id` (`str`) | `EVT-000001` to `EVT-004993`, unique. There is no index on it. |
| `claim_id` | `str` | **yes — 2,821 rows** | `Claim.claim_id` (`str`) | `CLM-000001` to `CLM-002172`, unique. **Empty means no `Claim` object is built at all.** |
| `policy_id` | `str` | no | **nothing — becomes structure** | the foreign key into `policyholders.csv`. See [the relationship](#the-relationship-between-the-two-files). An `Event` has no `policy_id` attribute; it hangs off its policyholder instead. |
| `event_date` | ISO date | no | `Event.event_date` (`date`) | 2026-01-03 to 2027-10-17. Always inside its policy's term, and often after its lapse date. |
| `trigger_type` | `str` | no | **`trigger`** (`str`) | `ice cream`, `slushie`, `popsicle`, `iced soda`, `smoothie`, `cold plunge`. What was eaten this time, not the favourite. |
| `item_temperature_c` | `float`, 1 dp, °C | no | **`temperature_c`** (`float`) | −18.0 to 18.0, drawn from a range fixed per trigger: popsicle −18 to −10, ice cream −15 to −8, slushie −6 to −2, smoothie −2 to 4, iced soda 0 to 4, cold plunge 10 to 18. |
| `portion_size_ml` | `float`, ml | no | **`portion_ml`** (`float` or `None`) | 30.0 to 378.0. Never empty in this dataset, though `seed.py` reads it with `_float` and the model's `None` is reachable if a future dataset leaves it blank. |
| `consumption_speed` | `str` | no | `consumption_speed` (`str`) | `slow`, `moderate`, `fast`, for *this* treat. Drawn conditional on the policyholder's typical speed, so it frequently differs from it. |
| `brain_freeze_occurred` | `bool` | no | **`brain_freeze`** (`bool`) | `True` on 3,730 rows. The flag every rate in the demo divides by. |
| `onset_time_sec` | `float`, 1 dp, seconds | **yes — 1,263 rows** | **`onset_sec`** (`float` or `None`) | 5.0 to 274.3. How long after the first mouthful it started. |
| `duration_sec` | `float`, 1 dp, seconds | **yes — 1,263 rows** | `duration_sec` (`float` or `None`) | 3.0 to 900.0, bimodal: a short episode most of the time, a long one on about a fifth of them (533 run over 300 seconds). |
| `pain_intensity_nrs` | `float`, 1 dp | **yes — 1,263 rows** | **`pain_intensity`** (`float` or `None`) | 0.0 to 10.0 on the numeric rating scale. Five events record a brain freeze at 0.0 — the generator clips a normal draw and does not exclude the floor. |
| `pain_location` | `str` | **yes — 1,263 rows** | `pain_location` (`str` or `None`) | `forehead`, `temple`, `occipital`, `whole head`. |
| `pain_quality` | `str` | **yes — 1,263 rows** | `pain_quality` (`str` or `None`) | `stabbing`, `pulling`, `dull/pressing`. |
| `claim_filed` | `bool` | no | **nothing — nothing reads it** | `True` on exactly the 2,172 rows with a `claim_id`, so it carries no information the id does not. Ask `event.claim is None`. |
| `claim_amount_requested_usd` | `float`, USD | no | **`Claim.requested`** (`float`) | **`0.0`, not empty, on the 2,821 rows that are not claims.** $8.02 to $116.26 where a claim was filed. Derived by `assess_amount()` from the episode plus the generator's jitter — the claimant never names a figure. |
| `claim_amount_approved_usd` | `float`, USD | no | **`Claim.approved`** (`float`) | what was actually paid. `0.0` on every denied row and every unfiled one, never above the requested amount. Sums to $54,671.44 against $92,081.22 of premium. |
| `claim_status` | `str` | no | **`Claim.status`** (`str`) | `Approved` (1,691), `Denied` (481), `Not Filed` (2,821). **`"Not Filed"` never reaches an object** — those rows have no claim id, so there is nothing to carry it. Filter on `e.claim is None`, not on the string. |
| `denial_reason` | `str` | **yes — 4,512 rows** | **`Claim.reason`** (`str` or `None`) | present on exactly the 481 `Denied` rows and nowhere else. Six distinct reasons, of which only two — `Policy lapsed` (254) and `Exceeded annual claim limit` (183) — come from `adjudication.py`; the other four are the generator's unmodelled 4%. |

The five episode columns — `onset_time_sec`, `duration_sec`,
`pain_intensity_nrs`, `pain_location`, `pain_quality` — are empty on exactly
the same 1,263 rows, the ones where `brain_freeze_occurred` is `False`. There
is no row with a duration and no headache, or a headache and no duration, so an
`Event` either has all five or has `None` in all five.

## The relationship between the two files

`policy_id` is the whole of it. It is the primary key of
`policyholders.csv` and a foreign key in `claims.csv`.

**One policy to many events, and every event to exactly one policy.** In the
committed dataset that is 4,993 events over 900 policies, between 2 and 9 each,
with no orphan on either side: every `policy_id` in `claims.csv` exists in
`policyholders.csv`, and every policy has at least one event. Neither is
guaranteed by anything but the generator. `seed.py` checks the first — an event
naming a policy that is not in the book raises `SystemExit` telling you the two
files are out of step — and does not check the second, because a policy with no
events is perfectly legal. The web app creates one every time somebody takes
out a policy.

**One event to zero or one claim, in the same row.** There is no third file.
The claim columns are either all filled in or, for the 2,821 unfiled rows,
blank-or-zero. So a policy has zero to nine claims, reached by walking its
events.

The join disappears when the data is loaded. `Policyholder.events` is a list,
`Event.claim` is an object or `None`, and neither carries the id it was joined
on: an `Event` has no `policy_id` and a `Claim` has no `event_id`. The foreign
key becomes containment, which is the point of the exercise — there is no join
to write, and no index to maintain, because reaching a policy's claims is
reaching them.

**Order matters and the loader is what enforces it.** `policyholder.events`
is oldest first because `attach_events` sorts by `event_date` and then by
`event_id`, not because the rows happen to arrive that way — they do, but that
is now a coincidence rather than the guarantee. The tiebreak is
load-bearing: 37 policies record two treats on the same day, and a date-only
sort would hand those pairs back in file order, which is the same bug wearing a
sort. So a hand-edited, re-sorted or regenerated `claims.csv` loads into the
same object graph as long as the rows themselves are the same; the row order
decides nothing. `tests/test_seed.py` asserts it against a deliberately
shuffled copy of the file, which is the only input that can tell a loader that
sorts from one that got lucky.

For the record, all four of the properties the file used to be relied on for
still hold across the committed data: the rows are grouped by policy,
contiguous, in the same policy order as `policyholders.csv`, and ascending by
`event_date` within each group. Nothing reads them any more.

## Stored versus derived

Six columns are written by the generator and never loaded. They are not missing
from the object model — they are *questions the object answers*, and having
them in the file as well is a convenience for anyone reading the CSV with
pandas, not a source of truth.

| column in the CSV | how to get it from the object |
| --- | --- |
| `underwriting_risk_score` | `p.underwriting_risk_score` — recomputed by `risk_score()` from `underwriting_base` plus the answers, rounded to 1 dp |
| `risk_tier` | `p.risk_tier` — the band that score falls in |
| `coverage_limit_per_incident_usd` | `p.coverage_limit` — off `COVERAGE_PLANS[p.plan_name]` |
| `deductible_per_incident_usd` | `p.deductible` — likewise |
| `monthly_premium_usd` | `p.monthly_premium` — `round_cents(annual_premium / 12)` |
| `claim_filed` | `event.claim is not None` |

Deriving rather than storing is what keeps the numbers from drifting: change a
weight in `underwriting.py` and every score moves with it, where a stored column
would quietly go on disagreeing.

Two of these are worth checking rather than trusting.

**`underwriting_risk_score` agrees exactly.** Recomputing it for all 900 rows
reproduces the stored column to the last decimal, and `risk_tier` agrees with
the band on every row. That is not luck — `tests/test_seed.py` reads the column
and asserts it, and it is the only use anything in the repo makes of it. It is
the drift detector for the whole underwriting path.

**`monthly_premium_usd` agrees on all 900 rows — since 2026-09-09.**

It did not when this document was written, and the reason is worth keeping.
The generator rounded `annual / 12` with numpy and the model rounded it with
Python's `round`, and where the exact quotient ends in a half they landed a
cent apart on 23 rows. Neither was wrong. Both were floats: `170.10 / 12` is
`14.174999999999999`, so Python respected the float and rounded down while
numpy scaled by 100 and carried it up.

Money is now `decimal.Decimal` everywhere — see `brainfreeze/money.py` — and
both sides round half-up through the same function, so there is one answer.
Fixing it moved **36** monthly premiums, not 23: those were the rows where the
two libraries disagreed with each other, while the full set of exact halves
is 36 and both had been rounding all of them down. `annual_premium_usd` did
not move, and `claims.csv` is byte-identical.

`tests/test_seed.py` now asserts the stored and derived values agree for all
900, so it cannot drift back.

## What changes if the dataset is regenerated

Every figure above is a fact about the committed files, not about the code.
`python3 -m datagen` is seeded and byte-identical run to run, so regenerating
without changing the generator changes nothing — and changing the generator
changes all of it at once, including numbers pinned in `tests/`, `mockups/` and
`docs/mcp-questions.md`. The README says to say so loudly if that happens. The
column list, the types and the relationship are the parts that should survive;
the counts and ranges are the parts to re-read.
