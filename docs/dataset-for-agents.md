# The dataset, for an agent

GemDB's MCP server tells you how to talk to the database. It does not tell you
what is in this one. There is no tool that knows what a policyholder is, and
that is by design: the surface is code-level — `eval_python`, `execute_code`,
`commit`/`abort`/`refresh`, browsing and search — so you answer a question by
writing Python and running it inside the database.

Which makes this file the interface. Without it the failure mode is not an
error, it is plausible Python: `p.favorite_trigger`, `c.amount`,
`p.coverage_limit_per_incident_usd`. Every one of those is a name that exists
somewhere in this repository and on none of the objects you will be holding.

Read this once, bind the preamble below, and then compose. The answers
themselves — nine questions with the exact figures a freshly seeded book
returns — are in [`mcp-questions.md`](mcp-questions.md); this is the map, that
is the pinned expectation.

This file is for **reading** the data over MCP. Changing the Python that
defines it is a different job with a different toolset — not MCP's — and
[`adding-a-feature.md`](adding-a-feature.md) is that one: where a new field
goes, which commands make it live, and why `Claim.rule` has to be read through
`getattr` while `Claim.flavour` does not.

Everything here was read out of `brainfreeze/`, `seed.py`, `data/*.csv` and
the findings scripts. Where a figure is date-dependent or was measured on one
particular build, it says so.

---

## 1. Bind a preamble once

```python
import sys
sys.path.insert(0, "/path/to/brain-freeze")   # the repository checkout
import gemdb, brainfreeze
from brainfreeze import analysis
book = gemdb.root["brainfreeze"]
```

Two things in there are not obvious.

**The `sys.path` line is required over MCP and only over MCP.** A worker gem's
working directory is the stone's, not the repository's, so `brainfreeze` is not
importable until you put the checkout on the path. A notebook or a `gemdb
script.py` run already has that directory on `sys.path`, which is why the
preamble printed at the top of `mcp-questions.md` omits it — that document's
snippets are written to be runnable both ways. `refresh_mcp.py` adds the path
itself before replaying them over the transport. If your first `import
brainfreeze` raises `ModuleNotFoundError`, this is why, and the fix is the path
and not the package.

**Names persist between calls, so binding once is worth doing.** Measured
2026-09-09 against MCP server `0.7.0` (`3c08dde`): the `eval_python` tool's own
description says names bound in a call persist "for the rest of this session, as
in a REPL", and they do — `marker = 4993` in one call read back `4993` in the
next. So `book` stays bound, and question after question composes against it.

That corrects older notes. `main`'s `docs/mcp-server.md` upstream, and earlier
drafts of this repo's own `PLAN.md` and `docs/gemdb-code-tasks.md`, say each
tool call is a clean slate and therefore that a write and its commit must go in
one call. On 0.7.0 that is measured false. It is not known which earlier server
versions behave the other way, so a demo written against one and run against the
other silently loses its preamble. **Check rather than assume**: evaluate `book`
on its own. A `NameError` means this server does not keep names and the preamble
has to be prefixed to every call.

Three more things about the tool, worth knowing before you are surprised by
them:

- `eval_python` returns the `printString` of the value and nothing else — no
  `print()` capture, no traceback shaping. Make the last expression the thing
  you want to see; a `print()` inside the snippet is output you will not get
  back.
- **Do not call `abort()`.** It discards this session's uncommitted work, and
  under Grail that includes compiled code — in the notebook, a helper defined
  three cells earlier stops answering after an `abort()`. By the same mechanism
  it should take your preamble with it, though that has not been measured over
  MCP specifically.
- **Do not run `seed.py` or `make_mcp_questions.py`.** Both replace
  `gemdb.root["brainfreeze"]` wholesale. That is the demo's reset button, not
  an analysis step, and someone else may be looking at the book.

## 2. One lookup, and everything hangs off it

```python
gemdb.root["brainfreeze"]            # a Book -- the only key seed.py writes
    .policies["BF-100539"]           # a Policyholder, by policy id
        .events                      # every cold treat, oldest first
            [0].claim                # a Claim, or None
```

`"brainfreeze"` is the whole of this demo's footprint in the root. Other keys
may exist from other work; `findings/03_class_identity.py` writes and then
deletes `"__finding_03__"`, for instance. Nothing in `brainfreeze/` reads
anything but its own key.

**`Policyholder.events` is the list, and `claims` is derived from it.** That is
the one modelling decision worth understanding, because it is the reason half
these questions are answerable. The obvious model — a policyholder holding a
list of claims — throws away every cold treat that hurt nobody, and those are
the denominator. 2,821 of the 4,993 event rows never became a claim. Keep only
the claims and "how often does a slushie cause brain freeze" stops being a
question the data can answer.

## 3. The four classes

Defined in `brainfreeze/model.py`. Standard library only — these are
instantiated inside the database, where numpy and pandas do not exist.

### `Book`

One object, holding one dict.

| | |
| --- | --- |
| `policies` | `{policy_id: Policyholder}` — the index. Stored. |
| `book[pid]`, `len(book)`, `iter(book)` | `__getitem__` on policy id, count of policies, iteration over policyholders (**not** over ids) |
| `events` | every `Event` in the book, flattened. Derived. |
| `claims` | every `Claim` in the book, flattened. Derived. |
| `total_premium`, `total_paid` | rounded sums. Derived. |
| `loss_ratio` | `total_paid / total_premium`, rounded to 3, or `None` |

`for p in book` yields policyholders. If you want ids, `book.policies` is the
dict.

### `Policyholder`

Fifteen attributes are stored — the fourteen constructor arguments and
`events`. Everything else is a property computed on the spot, which is why none
of them can drift out of step with the data.

Stored:

| name | type | notes |
| --- | --- | --- |
| `policy_id` | `str` | `"BF-100539"` |
| `age` | `int` | 5 to 19 in the seeded book |
| `sex` | `str` | `"F"`, `"M"`, `"Nonbinary/Other"` |
| `migraine_history` | `bool` | |
| `tension_type_headache_history` | `bool` | |
| `typical_consumption_speed` | `str` | `"slow"`, `"moderate"`, `"fast"` |
| `favourite_trigger` | `str` | one of the six trigger types — **British spelling** |
| `underwriting_base` | `float` | the starting point the generator drew for this person |
| `plan_name` | `str` | `"Basic"`, `"Standard"`, `"Premium"` |
| `annual_premium` | `float` | |
| `policy_start_date` | `date` | |
| `policy_term_months` | `int` | 12 for every policy in the seeded book |
| `policy_status` | `str` | `"Active"` or `"Lapsed"` — see §7, this is a trap |
| `policy_lapse_date` | `date` or `None` | |
| `events` | `list[Event]` | oldest first — sorted by `seed.py` on the way in, ties by `event_id` |

Derived:

| name | what it is |
| --- | --- |
| `plan` | the `Plan` namedtuple from `COVERAGE_PLANS` |
| `coverage_limit`, `deductible` | read off the plan, never stored twice |
| `underwriting_risk_score` | recomputed from the answers and `underwriting_base`, rounded to 1 |
| `risk_tier` | `"Low"`, `"Medium"` or `"High"` from that score |
| `monthly_premium` | `annual_premium / 12`, rounded to 2 |
| `policy_end_date` | `policy_start_date + 30 * policy_term_months` days |
| `is_in_force_on(when)` | `True` when there is no lapse date, else `when <= policy_lapse_date` — **inclusive** |
| `claims` | `[e.claim for e in events if e.claim]`, oldest first |
| `approved_claims` | of those, the ones with `status == "Approved"` |
| `brain_freeze_events` | events where `brain_freeze` is true |
| `total_paid` | sum of `approved` over approved claims, rounded to 2 |
| `claims_remaining_this_year` | `max(0, 4 - len(approved_claims))` |
| `brain_freeze_rate` | headaches per cold treat, or `None` with no events |
| `loss_ratio` | `total_paid / annual_premium`, rounded to 3, or `None` |

`is_in_force_on` tests the lapse date only. It does not check that `when` is
after `policy_start_date`, so it answers `True` for a date before the policy
existed.

### `Event`

One cold treat, whether or not it caused anything. All thirteen attributes are
stored; `claimed` is the only property.

| name | type | notes |
| --- | --- | --- |
| `event_id` | `str` | |
| `event_date` | `date` | |
| `trigger` | `str` | `"ice cream"`, `"slushie"`, `"popsicle"`, `"iced soda"`, `"smoothie"`, `"cold plunge"` |
| `temperature_c` | `float` | |
| `portion_ml` | `float` or `None` | |
| `consumption_speed` | `str` | `"slow"`, `"moderate"`, `"fast"` |
| `brain_freeze` | `bool` | **the denominator flag** |
| `onset_sec` | `float` or `None` | `None` when there was no headache |
| `duration_sec` | `float` or `None` | |
| `pain_intensity` | `float` or `None` | NRS scale |
| `pain_location` | `str` or `None` | `forehead`, `temple`, `occipital`, `whole head` |
| `pain_quality` | `str` or `None` | `stabbing`, `pulling`, `dull/pressing` |
| `claim` | `Claim` or `None` | |
| `claimed` | property | `claim is not None` |

### `Claim`

| name | type | notes |
| --- | --- | --- |
| `claim_id` | `str` | `"CLM-001291"` |
| `requested` | `float` | |
| `approved` | `float` | what was paid; `0.0` when denied |
| `status` | `str` | `"Approved"` or `"Denied"` — nothing else reaches an object |
| `reason` | `str` or `None` | why it was refused, in English; `None` when approved |
| `rule` | `str` or `None` | which rule refused it, as an identifier; `None` when approved |
| `flavour` | `str` or `None` | class default `None` |
| `toppings` | `tuple` | class default `()` |
| `is_approved` | property | `status == "Approved"` |

`flavour` and `toppings` were added in CUJ-4, after the sample data was
committed. They are **class** attributes as well as instance ones on purpose: a
claim written before the fields existed has no slot of its own and reads the
default through the class. Reading them on a seeded claim is safe and gives
`None` and `()`; 2,172 of them do.

`rule` was added later still, and the difference matters. A default declared
after records are committed is **not** visible to those records — editing the
class compiles a different class, and the 2,172 seeded claims keep the one they
were created under. Read it as `getattr(claim, "rule", None)`, never
`claim.rule`, and fall back to `adjudication.rule_for_reason(claim.reason)`
for a claim that predates it. `analysis.denial_rules` does both.

The CSV has a third `claim_status`, `"Not Filed"`, on 2,821 rows. Those rows
have no claim id, so `seed.py` gives the event `claim=None` and no `Claim`
object is ever built. **Do not filter for `"Not Filed"`; filter for
`e.claim is None`.**

### `Decision` is not in the database

`brainfreeze.adjudication.Decision` is a `NamedTuple` — `status`, `amount`,
`reason`, `assessed`, `capped_by_limit`, `deductible_applied`, `rule`, plus an
`approved` property — returned by `adjudicate()` when a claim is being decided.
It is the app's working object. Nothing stores one. A claim in the book carries
the *outcome* of a decision (`status`, `approved`, `reason`), not the decision.
If you want the breakdown for a historical claim you have to re-run
`adjudicate()`, and you will not reproduce the generator's jitter.

## 3a. Money is `Decimal`, and the usual operators are traps

Every money value on these objects — `annual_premium`, `monthly_premium`,
`total_paid`, a claim's `requested` and `approved`, a plan's `coverage_limit`
and `deductible` — is a `decimal.Decimal`. Not a float. A float cannot hold
most of them, and this book once shipped 23 monthly premiums that disagreed
with their own annual figure because two libraries rounded a float differently.

Import the helpers rather than reaching for the language:

```python
from brainfreeze.money import ZERO, format_usd, round_cents, usd
```

- `usd("170.10")` builds money from text or an int. **It raises on a float**,
  deliberately: by then the value is already gone.
- `round_cents(x)` rounds half-up to the cent.
- `format_usd(x)` gives `"$170.10"`. Use it for anything a person reads.

Five things that will bite you if you treat it as a number, all measured
inside this database:

| What you would write | What happens |
| --- | --- |
| `round(amount, 2)` | **brings the VM down**, no Python traceback |
| `statistics.mean(amounts)` | **brings the VM down** — sum and divide yourself |
| `amount // 10` | `TypeError` — no floor division, nor `%`, nor `divmod` |
| `format(amount, ".2f")` | `TypeError` — and so is `"{:.2f}".format(amount)` |
| `str(amount)` | `170.1`, not `170.10` — trailing zeros are dropped |

`"%.2f" % amount` does work, and so does `"{}".format(amount)` with no format
spec. It is `format()` with a spec that has no implementation. Use
`format_usd` anyway: it is the only one that also handles `None`.

One quieter difference: `int(Decimal)` **floors** here where CPython
truncates toward zero, so anything you write over a signed value disagrees
between the two.

Comparison is *not* one of them, contrary to an earlier draft of this file.
`Decimal("92081.22") == 92081.22` is `False` in both, correctly — that float
is not that number. Never pin money against a float literal, but the reason is
that the literal is wrong, not that the runtimes disagree.

Sums are exact, which is the whole reason for it: `sum(amounts, ZERO)` over
900 premiums is exact, not 900 roundings deep.

That is what you need to *read* money here. If you are going to *write* code
that runs in the database — a helper, a script, anything committed —
[`writing-python-for-gemdb.md`](writing-python-for-gemdb.md) is the rest of it:
the same money traps with their workarounds, plus the ones about compiled code,
deployed modules and the shared `__main__` that this file does not cover.

Ratios are **not** money. `loss_ratio`, approval rates and the values from
`analysis` come back as plain floats.

## 4. The CSV column names are not the attribute names

This is the single most likely way to write code that looks right and is not.
`data/*.csv` is the generator's output and uses one set of names; `seed.py`
translates them into another. Only the objects exist in the database.

| CSV column | attribute |
| --- | --- |
| `favorite_trigger` | `favourite_trigger` (British) |
| `coverage_plan` | `plan_name` |
| `annual_premium_usd` | `annual_premium` |
| `trigger_type` | `trigger` |
| `item_temperature_c` | `temperature_c` |
| `portion_size_ml` | `portion_ml` |
| `brain_freeze_occurred` | `brain_freeze` |
| `onset_time_sec` | `onset_sec` |
| `pain_intensity_nrs` | `pain_intensity` |
| `claim_amount_requested_usd` | `requested` |
| `claim_amount_approved_usd` | `approved` |
| `claim_status` | `status` |
| `denial_reason` | `reason` |
| `claim_filed` | *(nothing — use `event.claim is None`)* |

And four CSV columns are recomputed rather than loaded, so there is no
attribute holding the stored value at all:
`underwriting_risk_score`, `risk_tier`, `monthly_premium_usd` and both
`coverage_limit_per_incident_usd` / `deductible_per_incident_usd`. They come
back from `underwriting.py` and `COVERAGE_PLANS` every time you ask. Change a
weight there and the object moves; the CSV does not.

The table above is only the part that catches people out. The full column
dictionary — all 19 columns of each file, their types, which can be empty and
what they mean — is [`csv-schema.md`](csv-schema.md). You need it if you are
reading the CSVs directly or mapping them to classes; for writing Python
against a seeded book, this document is enough.

## 5. Find records by index, not by `isinstance`

The index is `book.policies`. Reach everything else by walking from it.

```python
# a policy
book["BF-100539"]

# a claim, by walking -- there is no claim index
[(p.policy_id, e.claim) for p in book for e in p.events
 if e.claim is not None and e.claim.claim_id == "CLM-001291"]
```

There is no dictionary keyed by claim id or event id, and building one costs a
full walk of 4,993 events. If you are going to ask about claims repeatedly,
build the index once and keep it — names persist, so that is a real saving:

```python
claims = {e.claim.claim_id: (p, e) for p in book for e in p.events if e.claim}
```

**Do not find records by class.** Not `isinstance`, not a class extent, not a
scan for "every `Policyholder` in the database". Grail compiles a Python class
into a real GemStone class, and editing the source compiles a *different* class.
Instances already committed keep the one they were created under: same name,
same module, different object. Measured on Grail `c875e56`
(`findings/03_class_identity.py`), a record committed under the old class is no
longer `type(record) is TheClass` **and no longer `isinstance(record,
TheClass)` either**. The parallel demo measured `isinstance` still holding on
Grail `46c2a68`, so this changed between versions and you cannot rely on either
answer. `type(obj).__name__` survives both, if you need a last resort.

So on this Grail, finding by index is not tidier — it is the only thing that
keeps working after someone edits `model.py`. Reachability from
`gemdb.root["brainfreeze"]` is unaffected by any of it, which is why the whole
model hangs off one key.

## 6. The named questions

`brainfreeze/analysis.py`, all exported from `brainfreeze` and imported by the
preamble as `analysis`. They exist so you compose rather than derive — two of
the choices inside them are ones an agent re-deriving the aggregation would get
wrong quietly.

| call | returns |
| --- | --- |
| `book_summary(book)` | dict: `policies`, `events`, `brain_freeze_events`, `claims`, `approved`, `premium`, `paid`, `loss_ratio` |
| `loss_ratio_by_tier(book)` | `{tier: ratio}` |
| `loss_ratio_by_plan(book)` | `{plan_name: ratio}` |
| `least_profitable_plan(book)` | `(name, ratio)`, or `None` on an empty book |
| `claim_approval_rate(book)` | float to 4 places, or `None` if no claims were filed |
| `denial_reasons(book)` | `[(reason, count)]`, commonest first, ties alphabetical |
| `denial_rules(book)` | `[(rule_id, count)]`, same order; identifiers, not prose |
| `top_n_by_expected_claims(book, n=10, min_events=5)` | `[(policyholder, rate)]`, highest first, ties by policy id |
| `top_n_by_loss_ratio(book, n=10)` | `[(policyholder, ratio)]`, highest first, ties by policy id |

The two `top_n` functions return **policyholder objects**, not ids. Project what
you want out of them before quoting.

### Trap one: a group loss ratio is not an average of ratios

`_loss_ratio_grouped` sums premium and payout per group and then divides.
Averaging each policy's own ratio would weight a $45 Basic policy the same as a
$342 Premium one, and would give a different — wrong — answer. If you write your
own grouping, sum then divide.

### Trap two: `top_n_by_expected_claims` needs its floor, and you must quote it

The score is approvals per cold treat. A policy with two treats and two approved
claims scores 1.0 and tells you nothing, so without `min_events` the ranking is
just a list of the shortest histories in the book. The default floor of 5 drops
**336 of the 900 policies** (read out of `data/claims.csv`; every policy in the
seeded book has between 2 and 9 events).

The floor is a judgement, not a fact, so it belongs in the answer:
*"highest approvals-per-event among policies with at least 5 recorded events"*,
not *"most likely to claim"*. Change `min_events` and the ranking changes.

There is a second reason to say it out loud here. The annual cap is 4 approvals,
so at a floor of 5 events the highest achievable score is 4/5 = 0.8 — and
**12 policies are tied at exactly 0.8**. `top_n_by_expected_claims(book, 5)`
returns five of those twelve, chosen by alphabetical policy id. It is a slice of
a tie, not a top five. Quote it as one.

### Rates are `None`, never `0.0`

Every rate in the model and in `analysis` returns `None` when there is nothing
to divide by: `claim_approval_rate` on a book with no claims, `loss_ratio` on a
zero premium, `brain_freeze_rate` on a policyholder with no events,
`least_profitable_plan` on an empty book.

This is deliberate and it matters for how you report. An empty book has no
approval rate. Saying `0.0` would assert that every claim was refused, which is
a different fact and a false one. And the empty case is reachable, not
hypothetical — the web app's quote flow creates a policyholder with no events at
all, so the first thing a new policy answers to `brain_freeze_rate` is `None`.

Handle `None` explicitly. `if rate:` treats a genuine 0.0 and an unanswerable
`None` the same way, which is the bug this design exists to prevent.

## 7. What the seeded book looks like

Freshly seeded, before anyone files a claim through the app. These are the
figures `tests/test_seed.py` and `tests/test_analysis.py` pin, all read out of
`data/*.csv` rather than out of the functions being tested.

```
900 policies   4,993 events   3,730 with brain freeze   2,172 claims   1,691 approved
premium $92,081.22   paid $54,671.44   loss ratio 0.594   approval rate 0.7785
```

- **By tier**: Low 137 policies, Medium 497, High 266. Loss ratios
  `{'Low': 0.409, 'Medium': 0.729, 'High': 0.501}`.
- **By plan**: Basic 419 policies, Standard 345, Premium 136. Loss ratios
  `{'Basic': 0.493, 'Standard': 0.771, 'Premium': 0.455}`. Standard is the least
  profitable.
- **The result worth a second look**: the tier loading is 1.9× on High and 0.7×
  on Low, which over-prices High. The customers the underwriter fears most are
  the most profitable, and the money leaks out of the middle of the book. If you
  are asked "which customers are expensive", that is the answer, and it is not
  the one the risk score implies.
- Ages 5 to 19. Every policy is a 12-month term. Start dates run
  2026-01-01 to 2026-10-27; event dates run 2026-01-03 to 2027-10-17, so parts
  of the book are in the future relative to today.

The rules those figures came out of, from `underwriting.py` and
`adjudication.py`:

| | |
| --- | --- |
| plans (base premium / per-incident limit / deductible) | Basic 45/25/10, Standard 90/60/5, Premium 180/150/0 |
| tier loading on the base premium | Low 0.7, Medium 1.0, High 1.9 |
| tier bands on the score | below 34.0 Low, below 67.0 Medium, else High |
| approved claims allowed per policy per year | 4 (`ANNUAL_CLAIM_LIMIT`) |
| adjudication order | cover, then the annual cap, then the per-incident limit, then the deductible |

### `policy_status` does not mean "in force today"

217 policies are marked `Lapsed` and all 217 carry a lapse date — but the
book's terms run either side of the present, so most of those dates have not
arrived. On 2026-09-08, only **53** were actually out of cover. That number
changes every day and there is no stored field that tracks it.

Use the date:

```python
from datetime import date
today = date.today()
[p.policy_id for p in book if not p.is_in_force_on(today)]
```

Cover runs to the lapse date **inclusive** — someone who lapses on the 12th is
still covered for the treat they ate that morning — which is exactly the
difference between the 53 above and the 54 you get from a naive `<=` comparison
on that date. Any answer built on `policy_status` will call policies lapsed
while they are still paying claims.

### Four of the six denial reasons do not come from the rules

`adjudication.py` can return five, identified as `policy-lapsed`,
`event-outside-term`, `annual-claim-count-cap`, `below-deductible` and
`per-incident-limit`. The seeded book contains six wordings, of which only two
are the rules':

```
Policy lapsed                                  254
Exceeded annual claim limit                    183
Pre-existing headache condition exclusion       15
Claim amount exceeds per-incident coverage limit 10
Insufficient severity documented                10
Filed outside claim window                       9
```

The bottom four come from `datagen`'s `UNMODELLED_DENIAL_RATE` — a 4% chance of
a refusal for a reason the rules do not model, added so the sample history looks
lived-in. They belong to the generator, not to the model, and the app does not
reproduce them.

So: a refusal you can check against the rules is one of the top two. A claim
refused for one of the bottom four cannot be re-derived from
`adjudicate()`, and saying "the rules produced this" of one of them would be
wrong. `"Claim amount below deductible"` is a reason the code can return that
nothing in this dataset actually hit, and so are the two wordings added since
this book was generated.

**Group by the identifier, not by the sentence.** `analysis.denial_rules(book)`
returns the same 481 refusals keyed by rule id, with the 44 that no rule
produced under `unclassified` (and a refusal that stored no reason at all under
`unrecorded`). Neither of those is a rule. Two traps it saves you from: the
generator's `"Claim amount exceeds per-incident coverage limit"` reads like the
`per-incident-limit` rule and is **not** it, and the generator also picks the
real `"Exceeded annual claim limit"` wording for some of its unmodelled
refusals, so the 183 under `annual-claim-count-cap` are an upper bound on how
many the cap actually refused. Wording alone cannot tell those apart — which is
the argument for storing the identifier at the source.

### A refusal is checkable, not just quotable

`reason` is a stored string, and the point of CUJ-2 is that you do not have to
trust it. The event date, the lapse date and the in-force test are all reachable:

```python
[(e.claim.claim_id, e.claim.reason, e.event_date,
  p.policy_lapse_date, p.is_in_force_on(e.event_date))
 for p in book for e in p.events
 if e.claim is not None and e.claim.claim_id == "CLM-001291"]
```

```
[('CLM-001291', 'Policy lapsed', datetime.date(2027, 4, 20), datetime.date(2027, 3, 10), False)]
```

The same goes for a risk score: `score_breakdown()` in `underwriting.py` returns
`[(label, points)]` and reproduces the score from the recorded
`underwriting_base` plus the answers, so "why is this policy High tier?" has an
arithmetic answer rather than an assertion. Pass
`base=p.underwriting_base`; the default `BASE_RISK` of 45.0 is what the app uses
for a new quote and will *not* reproduce a seeded policy's score.

## 8. If you write something

The demo is meant to be written to — the web app creates policies and claims in
the same object graph you are reading.

- A write is an ordinary assignment: build the object, attach it, `gemdb.commit()`.
  There is no ORM, no schema and no migration.
- Your changes are invisible to every other surface until you commit, and theirs
  are invisible to you until you take a new view. Each surface holds its own
  session and sees the repository as of its last transaction boundary. Your
  analysis does not shift under you mid-question, which is a feature and will
  look like a bug the first time it bites.
- To pick up someone else's commit the recipe is **`gemdb.commit()` then
  `gemdb.refresh()`**. `refresh()` alone will usually refuse with *"refresh()
  would discard uncommitted changes"* — not because you changed data, but
  because Grail compiles the code you ran into the database, so merely having
  run anything leaves `needs_commit()` returning `True`
  (`findings/04_dirty_session.py`).
- `abort()` also takes a new view and is the wrong tool. See §1.
- Old advice said to put a write and its commit in the same tool call, because
  each call was believed to be a clean slate. On 0.7.0 that is not required.
  Committing deliberately still is: an uncommitted write is invisible to
  everyone else and blocks your own `refresh()`.

## 9. What this document does not know

Said plainly, because guessing here is how a wrong answer gets written
confidently.

- **Which server versions keep names between calls.** Measured true on `0.7.0`
  (`3c08dde`), 2026-09-09. Upstream documentation for other versions says the
  opposite. Nobody has established where the behaviour changed. §1 says how to
  check in one call.
- **Whether `abort()` discards a preamble over MCP.** It discards compiled work
  in a notebook session; the same mechanism should apply, but it was not
  measured through the transport.
- **The tool list.** It varies by build and by settings — 40 tools were offered
  on `3c08dde`, and a read-only configuration can hide `eval_python` itself,
  which would leave no way to answer anything here. Call `tools/list` rather
  than assuming.
- **Anything about a book that is not freshly seeded.** Every figure in §7 is
  the state after `gemdb seed.py`. The app writes to the same book, so a
  database someone has been demonstrating on will have more policies and more
  claims. Run `analysis.book_summary(book)` first and compare; if it does not
  match, the figures here are history and the ones you computed are the truth.
