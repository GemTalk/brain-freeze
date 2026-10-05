# Branding

The web app's whole look is three files in `web/templates/`. Swap them and
the app is someone else's: no Python changes, no restart (an edited template
is live on the next request).

| File | What it holds |
|---|---|
| `brand.css` | The tokens: colours, fonts, radii, as CSS custom properties. `app.css` styles every page with these names and nothing else. |
| `_brand.html` | The marks and the brand's data, as Jinja macros and variables: the app's `name`, the `icon`, the `lockup`, the `favicon`, the `fonts_url`, and the ID card's `colorways`. |
| `id_card.svg` | The ID card, an SVG template over the fields `pages.id_card()` provides. |

This branch's brand is Ice Cream Brain Freeze Insurance, from the GemDB brand
guidelines: the "Micro brand" slide (the one-two-three scoop icon, the
wordmark, red `#FF3700` / yellow `#FFE200` / blue `#0F9EE1` on GemDB's ink
`#0D1321` and paper `#F2F5F4`) and the "Insurance Cards" slide.

## Making a brand of your own

These are written for a person or an agent working in this repo.

1. **Tokens.** In `brand.css`, set the colours. Keep every name: `app.css`
   uses all of them. Fills (`--red`, `--blue`, `--yellow`) can be any
   colour. The `-text` shades and `--muted` must read at 4.5:1 or better on
   `--paper` and `--surface`, because they are used for small text.
   Buttons put `--ink` on `--blue`, so check that pair too.
2. **Fonts.** Put one Google Fonts css2 URL in `fonts_url` in `_brand.html`
   (Google Fonts serves CSS cross-origin, so the card's PNG export can
   inline the fonts). Name the families in `--font`, `--display`, `--wordmark`
   and `--mono`, and in the `.bfc-*` font rules in `id_card.svg`.
3. **Name.** Set `name` and `short_name` in `_brand.html`. Page titles,
   the header, the footer, the home page and the card read them from there.
   The startup banner in `web/serving.py` is the one other place the name is
   written out.
4. **Marks.** `scoop_paths` draws the icon in a 182 × 122 box. Replace the
   paths, and the `viewBox` in `icon` and `stack`, with your own SVG.
   Write shapes that don't overlap: drop the gaps into the paths rather
   than masking them, so the icon stays one colour per shape and draws the
   same inline, in the downloaded SVG and in the PNG. `favicon` is a data
   URL; `lockup` is the header's mark plus wordmark.
5. **The ID card.** `id_card.svg` is 1200 × 640, near the 1.91:1 that X,
   LinkedIn, Bluesky and Threads show uncropped. Colour it only through
   `var(--bf-bg)`, `--bf-ink` and `--bf-s1`…`--bf-s3`, by class, so the
   card page can recolour it without asking the server. Define each
   colourway in `colorways` and list it in `colorway_order`;
   `plan_colorways` picks a plan's default.
   - Keep `id="bfc-subscriber"` on the name's `<text>`: the card page writes
     the typed name into it.
   - Keep a `<style>` element whose first rule is
     `@import url("{{ brand.fonts_url }}");`: the PNG export swaps that line
     for the inlined fonts.
   - Print the policy id, plan name, cover, deductible and premium:
     `tests/test_app.py` and the acceptance suite look for them.
   - Keep inside the canvas. The longest text is the subscriber name, up to
     24 characters, which shrinks past 16.
6. **Check it.** Run the app (`gemdb web/app.py`) and look at `/`,
   `/quote`, `/policies/BF-100539` and `/policies/BF-100539/card` at desktop
   and phone widths. On the card page, try every colourway with a long name,
   then **Download image** and confirm the PNG matches the page, fonts
   included. Then run `python3 -m unittest discover`.

## Sharing the card

**Share** on the card page posts the card's PNG with editable text.

- **Phones** (and any browser where `navigator.canShare({files})` is true)
  get **Share image…**, which opens the device's share sheet with the
  picture attached.
- **X, Bluesky, Threads and LinkedIn** have no way to take a picture through
  a link. Their buttons copy the PNG to the clipboard (or download it, where
  the browser won't copy), then open the network's composer with the text
  filled in, so the reader pastes the picture into the post. The composer
  links are `x.com/intent/post`, `bsky.app/intent/compose`,
  `threads.com/intent/post` and `linkedin.com/feed/?shareActive=true`, all
  with `text=`.
- A link preview (an `og:image`) would need the card on a public URL. The
  app runs on `127.0.0.1`, so the picture travels with the post instead.

The name on a card is the reader's own and is never stored. It and the
colourway ride in the URL (`?name=&style=`), so a reload and **Download
SVG** draw the same card.

## Keeping this branch

`bfi-visual-rebrand` lives alongside `main` and is not merged. To pick up
`main`, merge it in. Conflicts will be in `web/templates/`. Take `main`'s
content and structure (new fields, pages, test hooks such as `.card.row`,
`.big`, `#id-card svg`, `a[download$=".svg"]`) and keep this branch's
classes, brand imports and the `brand.name` titles.
