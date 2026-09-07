# Mockups

Static screen mockups for the web app, in "Direction C" — rounded, bright,
oversized type. Every figure on them is real: read out of
`data/policyholders.csv` and `data/claims.csv`, or computed by the
`brainfreeze` package.

The screens, in flow order:

| File | Screen |
| --- | --- |
| `Picker.dc.html` | 0 · Who are you today? — stands in for a sign-in the demo does not have |
| `Main.dc.html` | 1 · Get a quote |
| `Plans.dc.html` | 2 · Compare plans, with the score explained |
| `Accepted.dc.html` | 3 · You're covered — creates BF-100900 |
| `FileClaim.dc.html` | 4 · File a claim |
| `Decision.dc.html` | 5 · The decision, approved and refused |
| `History.dc.html` | 6 · Policy history for BF-100539 |
| `EmptyHistory.dc.html` | 6b · A policy with no events yet |
| `ClaimV2.dc.html` | CUJ-4 · The claim form after flavour and toppings |
| `DirectionB.dc.html` | A sketch of the insurer's view — a second audience, not an alternative look |

`build_c.py` generates all of them from one set of design tokens; edit that
rather than the HTML if a colour, radius or type size needs to change for
every screen at once. `canvas.json` is the layout (frame sizes and positions)
used when they are published together as a pan/zoom canvas.

These are `.dc.html` files: ordinary self-contained HTML apart from the
`<x-dc>` and `<helmet>` wrappers, which the canvas editor uses. Open one in a
browser and it renders as a normal page.

## Decisions visible in the screens

- **No `sex` on the quote form.** It is in the CSVs but carries no weight in
  the risk model, so asking would be theatre.
- **Temperature and portion are bands, not readings.** Nobody has a
  thermometer in a slushie, and adjudication only needs the band.
- **The claimant never enters an amount.** Severity determines it, which is
  how the generator works — see `brainfreeze.assess_amount`.
- **A policy is identified by number alone.** The CSVs carry no names, and
  inventing a field the dataset lacks seemed worse than the alternative.
- **The quote is one form, not one question per screen.** Five round trips to
  price a policy drags in a demo you walk someone through in fifteen minutes.

## Known gap

The quote flow cannot reproduce a score already in the dataset. The generator
draws each policyholder's starting point from `normal(45, 15)` and does not
record it, so an applicant who matches an existing row can land in a different
tier. `brainfreeze.risk_score` takes `base` as a parameter so that recording
it is a one-column change.
