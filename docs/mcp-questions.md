# Questions this demo promises to answer

GemDB's MCP surface is code-level, not data-level: it offers `eval_python`,
`execute_code`, `commit`/`abort`/`refresh`, browsing and search. **There is
no tool that knows what a policyholder is.** An agent answers these by
writing Python that runs inside the database.

Every answer below was produced by running the snippet beside it, not typed
in, against a **freshly seeded** database -- the state CUJ-0 starts from and
the figures `tests/test_seed.py` pins. Regenerate with `gemdb
make_mcp_questions.py` after any change to the data or the rules; if an
answer moves, either the change was wrong or this file is the record of what
the demo now promises.

Each snippet assumes this preamble:

```python
import gemdb
import brainfreeze
from brainfreeze import analysis
book = gemdb.root["brainfreeze"]
```

---

## 1. How big is this book, and is it making money?

The one-liner an agent should open with. `loss_ratio` under 1.0 means the
book is profitable overall.

```python
analysis.book_summary(book)
```

```
{'policies': 900, 'events': 4993, 'brain_freeze_events': 3730, 'claims': 2172, 'approved': 1691, 'premium': 92081.22, 'paid': 54671.44, 'loss_ratio': 0.594}
```

## 2. What is the loss ratio by risk tier?

The demo's punchline. The 1.9x loading on High over-prices the risk, so the
customers the underwriter fears most are the most profitable, and the middle
of the book is where the money leaks.

```python
analysis.loss_ratio_by_tier(book)
```

```
{'Medium': 0.729, 'High': 0.501, 'Low': 0.409}
```

## 3. Which coverage plan is least profitable?

Returned as (name, ratio) so the agent can quote both.

```python
analysis.least_profitable_plan(book)
```

```
('Standard', 0.771)
```

## 4. What share of claims get paid, and why are the rest refused?

Refusal reasons come from `brainfreeze.adjudication`, not from the app, so
this answer and the claim screen cannot disagree.

```python
(analysis.claim_approval_rate(book), analysis.denial_reasons(book))
```

```
(0.7785, [('Policy lapsed', 254), ('Exceeded annual claim limit', 183), ('Pre-existing headache condition exclusion', 15), ('Claim amount exceeds per-incident coverage limit', 10), ('Insufficient severity documented', 10), ('Filed outside claim window', 9)])
```

## 5. Why was CLM-001291 refused?

CUJ-2. The refusal is not a stored string an agent has to trust -- the event
date, the lapse date and the in-force test are all there, so the reason can
be checked rather than repeated.

```python
[(e.claim.claim_id, e.claim.reason, e.event_date, p.policy_lapse_date, p.is_in_force_on(e.event_date))
 for p in book for e in p.events
 if e.claim is not None and e.claim.claim_id == 'CLM-001291']
```

```
[('CLM-001291', 'Policy lapsed', datetime.date(2027, 4, 20), datetime.date(2027, 3, 10), False)]
```

## 6. Why is BF-100539 in the Medium band?

Only answerable because the drawn base is recorded. Before that column
existed the score could not be reproduced from the answers beside it, and
this question had no honest answer.

```python
brainfreeze.score_breakdown(
    book['BF-100539'].age,
    book['BF-100539'].migraine_history,
    book['BF-100539'].tension_type_headache_history,
    book['BF-100539'].typical_consumption_speed,
    book['BF-100539'].favourite_trigger,
    base=book['BF-100539'].underwriting_base)
```

```
[('Everyone starts here', 43.23695935480873), ('Eats at a normal pace', 0.0), ('Age 9', 10.0), ('Favourite treat: slushie', 12.000000000000002)]
```

## 7. Which policies are we underpricing?

Above 1.0 the policy has cost more than it brought in.

```python
[(p.policy_id, p.plan_name, p.risk_tier, ratio)
 for p, ratio in analysis.top_n_by_loss_ratio(book, 5)]
```

```
[('BF-100813', 'Standard', 'Low', 2.728), ('BF-100367', 'Standard', 'Medium', 2.383), ('BF-100495', 'Standard', 'Medium', 2.353), ('BF-100792', 'Standard', 'Medium', 2.315), ('BF-100165', 'Standard', 'Low', 2.224)]
```

## 8. How often does a cold treat actually cause brain freeze?

Only computable because the events that hurt nobody are stored too. A model
that kept claims alone would have thrown the denominator away and this
question could not be asked at all.

```python
{'events': len(book.events),
 'caused a headache': len([e for e in book.events if e.brain_freeze]),
 'rate': round(len([e for e in book.events if e.brain_freeze])
               / len(book.events), 3)}
```

```
{'events': 4993, 'caused a headache': 3730, 'rate': 0.747}
```

## 9. Which customers claim most often?

Quote the `min_events` floor with the answer: without it the ranking is a
list of the shortest histories in the book, not the likeliest claimants.

```python
[(p.policy_id, rate) for p, rate in analysis.top_n_by_expected_claims(book, 5)]
```

```
[('BF-100052', 0.8), ('BF-100083', 0.8), ('BF-100098', 0.8), ('BF-100179', 0.8), ('BF-100272', 0.8)]
```
