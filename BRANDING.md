# Branding

The web app's look is three files in `web/templates/`. Swap them and the app
is someone else's: no Python changes, no restart (an edited template is live
on the next request).

| File | What it holds |
|---|---|
| `brand.css` | The tokens: colours, fonts, radii and shadows, as CSS custom properties. `app.css` takes every colour, font, radius and shadow from these names. |
| `_brand.html` | The name and the marks, as Jinja variables and macros: the app's `name` and `short_name`, the `fonts_url`, the `mark_path`, the `icon`, the header's `lockup` and the `favicon`. |
| `id_card.svg` | The ID card, an SVG template over the fields `pages.id_card()` provides. |

`app.css` is the layout and the shape of every component, written only in
the token names. A brand that needs different shapes, not just different
colours, type and marks, restyles `app.css` too. That is a bigger job, and
the three files above are still where the brand itself lives.

The brand on `main` is Brain Freeze Insurance: ice blue `#2a8bd8` on a cool
white, Plus Jakarta Sans and JetBrains Mono, and a snowflake for a mark.

For a worked example, the `bfi-visual-rebrand` branch rebrands the app as Ice
Cream Brain Freeze Insurance from a set of brand guidelines. It goes further
than this guide: it restyles `app.css` and adds styles and sharing to the
ID card.

## Making a brand of your own

These steps are written for a person or an agent working in this repo. An
agent can also use the `rebrand` skill in `.claude/skills/`, which follows
them.

1. **Tokens.** In `brand.css`, set the colours. Keep every name: `app.css`
   uses them all. The names are roles, not colours: `--ice` is the brand's
   main colour, whatever it is, and `--mint`, `--berry` and `--amber-*` say
   yes, no and careful.
   - `--ice-deep`, `--mint`, `--berry`, `--amber-ink`, `--muted` and
     `--ink-2` are used for small text. Aim for 4.5:1 or better on `--bg`
     and `--surface`, the contrast WCAG asks for text that size.
   - Buttons put `--on-ice` on `--ice`, and on `--ice-hover` under the
     pointer. Check that pair too.
   - `python3 .claude/skills/rebrand/contrast.py` prints every pair the
     pages use and flags those under 4.5:1. The stock brand has five:
     `--mint` and `--muted` on `--bg`, `--mint` on `--mint-soft`, and
     the white button text on `--ice` (3.6:1) and `--ice-hover`. Don't
     copy them.
2. **Fonts.** Put one Google Fonts css2 URL in `fonts_url` in `_brand.html`
   and name its families in `--font` and `--mono` in `brand.css`. The ID
   card can't use them (see step 5).
3. **Name.** Set `name` and `short_name` in `_brand.html`. Page titles, the
   header, the footer, the home page and the card read them from there.
   The startup banner in `web/serving.py` is the one other place the name
   is written out, and `features/steps/app_steps.py` checks the banner's
   words: change both, or neither.
4. **Marks.** `mark_path` is the mark as one stroked path on a 24 × 24
   grid. `icon` draws it in the text colour: in the header's tile (`.mark`
   in `app.css`) and as the big faint mark behind the home page's hero.
   `lockup` is the header's mark plus the name, and `favicon` is the mark
   on a tile, as a data URL. The tile's colour is written into `favicon`
   as hex, because a data URL can't read `brand.css`, so update it with
   `--ice`.
   - For a filled or many-coloured logo, rewrite `icon` with your own SVG.
     Keep its `size` argument and `aria-hidden`, and draw the favicon and
     the card's two marks from the same shapes.
5. **The ID card.** `id_card.svg` is 856 × 540, a payment card's
   proportions. It reads the `card` fields from `pages.id_card()`:
   `policy_id`, `plan`, `member`, `cover`, `deductible`, `premium`,
   `risk_tier`, `valid_from`, `valid_to`, `claims_a_year` and `status`.
   The card page shows it, **Download image** draws it to a PNG, and
   `/policies/<id>/card.svg` serves it on its own.
   - Write its colours into the SVG. It is served on its own, so it can't
     read `brand.css`.
   - Use system fonts only. **Download image** draws the SVG onto a
     canvas, and an SVG drawn that way cannot fetch a web font, so the PNG
     would not match the page.
   - Keep `<svg` as the first thing it outputs: put anything before it in
     Jinja comments, or tags that trim their whitespace (`{%- ... -%}`).
   - Print the policy id, plan name, cover, deductible and premium:
     `tests/test_app.py` and the acceptance suite look for them.
   - Keep everything inside the canvas. If you change its size, change the
     `viewBox`, the `clipPath` and the corner radius on `.idcard svg` in
     `app.css`, which is a percentage of a 856 × 540 card.
6. **Check it.** Run the app (`gemdb web/app.py`) and look at `/`,
   `/quote`, `/policies`, `/claims`, `/policies/BF-100539` and
   `/policies/BF-100539/card` at desktop and phone widths. On the card
   page, **Download image** and check the PNG matches the page. Then run
   `python3 -m unittest discover` and `gemdb tools/run_db_tests.py`.
