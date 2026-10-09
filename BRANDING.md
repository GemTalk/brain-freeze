# Branding

The web app's whole look is three files in `web/templates/`. Swap them and
the app is someone else's: no Python changes, no restart (an edited template
is live on the next request).

| File | What it holds |
|---|---|
| `brand.css` | The tokens: colours, fonts, radii, as CSS custom properties. `app.css` styles every page with these names and nothing else. |
| `_brand.html` | The marks and the brand's data, as Jinja macros and variables: the app's `name`, the `icon`, the `lockup`, the `badge` and `favicon`, the plans' scoop `stack`, the `fonts_url`, and the ID card's `colorways`. |
| `id_card.svg` | The ID card, an SVG template over the fields `pages.id_card()` provides. |

This branch's brand is Ice Cream Brain Freeze Insurance, from the GemDB brand
guidelines: the "Micro brand" slide (the logo, the "Brain Freeze Insurance
Co" wordmark, the cone icon and the icon-only badge, the single scoops, red
`#FF3700` / yellow `#FFE200` / blue `#0F9EE1` on GemDB's ink `#0D1321` and
paper `#F2F5F4`) and the "Insurance Cards" slide.

## Making a brand of your own

These are written for a person or an agent working in this repo. An
agent can also use the `rebrand` skill in `.claude/skills/`, which follows
them.

1. **Tokens.** In `brand.css`, set the colours. Keep every name: `app.css`
   uses all of them. Fills (`--red`, `--blue`, `--yellow`) can be any
   colour. The `-text` shades and `--muted` must read at 4.5:1 or better on
   `--paper` and `--surface`, because they are used for small text.
   Buttons put `--ink` on `--blue`, so check that pair too.
   `python3 .claude/skills/rebrand/contrast.py` checks every pair this
   branch's `app.css` puts together.
2. **Fonts.** Put one Google Fonts css2 URL in `fonts_url` in `_brand.html`
   (Google Fonts serves CSS cross-origin, so the card's PNG export can
   inline the fonts). Name the families in `--font`, `--display` and
   `--mono`, in `wordmark_font` and `mono_font` in `_brand.html` (the
   logo's type), and in the `.bfc-sans` rule in `id_card.svg`.
3. **Name.** Set `name` and `short_name` in `_brand.html`. Page titles,
   the header, the footer, the home page and the card read them from there.
   The startup banner in `web/serving.py` is the one other place the name is
   written out.
4. **Marks.** `cone_paths` draws the icon in a 73 × 179 box, and
   `lockup_shapes` sets it beside the wordmark in a 311 × 179 box: the logo,
   which the header and the ID card both draw. Replace the paths and the
   text, and the `viewBox` in `icon`, `badge` and `lockup`, with your own
   SVG. Write shapes that don't overlap: drop the gaps into the paths
   rather than masking them, so the icon stays one colour per shape and
   draws the same inline, in the downloaded SVG and in the PNG. `badge` is
   the icon only, on a disc, and `favicon` is it as a data URL.
   `scoop_paths` and `stack` draw the plans' one, two and three scoops.
5. **The ID card.** `id_card.svg` is 1200 × 640, near the 1.91:1 that X,
   LinkedIn, Bluesky and Threads show uncropped. Colour it only through
   `var(--bf-bg)`, `--bf-ink` and `--bf-s1`…`--bf-s3` (the icon's three
   shapes, top down), by class, so the card page can recolour it without
   asking the server. Define each colourway in `colorways` and list it in
   `colorway_order`; `plan_colorways` picks a plan's default.
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

`bfi-visual-rebrand` lives alongside `main` and is not merged. `main` keeps
its brand in the same three files, so this branch is `main` with those
files replaced, `app.css` restyled and the ID card's styles, name and
sharing added. To pick up `main`, rebase onto it. Conflicts will be in
`web/templates/`:

- `brand.css`, `_brand.html`, `id_card.svg`, `app.css` and `card.html`
  are this branch's own. Keep this branch's version, then bring across
  anything new on `main` that isn't brand: a new field, page or test hook,
  such as `.card.row`, `.big`, `#id-card svg` or `a[download$=".svg"]`.
- Other templates: take `main`'s content and structure, and keep this
  branch's classes and brand calls.
- `.claude/skills/rebrand/contrast.py`: keep this branch's `PAIRS`, which
  name this branch's tokens.
