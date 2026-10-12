# Branding

The web app's whole look is three files in `web/templates/`. Swap them and
the app is someone else's: no Python changes, no restart (an edited template
is live on the next request).

| File | What it holds |
|---|---|
| `brand.css` | The tokens: colors, fonts, radii, as CSS custom properties. `app.css` styles every page with these names and nothing else. |
| `_brand.html` | The marks and the brand's data, as Jinja macros and variables: the app's `name`, the `icon`, the `lockup`, the `badge` and `favicon`, the plans' scoop `stack`, the `fonts_url`, and the ID card's `colorways`. |
| `id_card.svg` | The ID card, an SVG template over the fields `pages.id_card()` provides. |

The ID card's PNG is drawn with the TTFs in `web/fonts/`, so a brand with
new fonts puts them there too (step 2).

This branch's brand is Ice Cream Brain Freeze Insurance, from the GemDB brand
guidelines: the "Micro brand" slide (the logo, the "Brain Freeze Insurance
Co" wordmark, the cone icon and the icon-only badge, the single scoops, red
`#FF3700` / yellow `#FFE200` / blue `#0F9EE1` on GemDB's ink `#0D1321` and
paper `#F2F5F4`) and the "Insurance Cards" slide.

## Making a brand of your own

These are written for a person or an agent working in this repo. An
agent can also use the `rebrand` skill in `.claude/skills/`, which follows
them.

1. **Tokens.** In `brand.css`, set the colors. Keep every name: `app.css`
   uses all of them. Fills (`--red`, `--blue`, `--yellow`) can be any
   color. The `-text` shades and `--muted` must read at 4.5:1 or better on
   `--paper` and `--surface`, because they are used for small text.
   Buttons put `--ink` on `--blue`, so check that pair too.
   `python3 .claude/skills/rebrand/contrast.py` checks every pair this
   branch's `app.css` puts together.
2. **Fonts.** Put one Google Fonts css2 URL in `fonts_url` in `_brand.html`:
   the pages and `card.svg` load it. Name the families in `--font`,
   `--display` and `--mono`, in `wordmark_font` and `mono_font` in
   `_brand.html` (the logo's type), and in the `.bfc-sans` rule in
   `id_card.svg`. Then put each weight the card uses into `web/fonts/` as a
   static TTF, with the family's licence beside it: `resvg` draws the
   card's PNG with those files and no others, so a missing weight falls
   back to another one in the PNG only. The same css2 URL fetched with a
   non-browser user agent (`curl -A curl/8 '<url>'`) lists a static TTF for
   each weight. Check them with
   `resvg --skip-system-fonts --use-fonts-dir web/fonts --list-fonts`.
3. **Name.** Set `name` and `short_name` in `_brand.html`. Page titles,
   the header, the footer, the home page and the card read them from there.
   The startup banner in `web/serving.py` is the one other place the name is
   written out.
4. **Marks.** `cone_paths` draws the icon in a 73 × 179 box, and
   `lockup_shapes` sets it beside the wordmark in a 311 × 179 box: the logo,
   which the header and the ID card both draw. Replace the paths and the
   text, and the `viewBox` in `icon`, `badge` and `lockup`, with your own
   SVG. Write shapes that don't overlap: drop the gaps into the paths
   rather than masking them, so the icon stays one color per shape and
   draws the same inline, in `card.svg` and in the PNG. `badge` is
   the icon only, on a disc, and `favicon` is it as a data URL.
   `scoop_paths` and `stack` draw the plans' one, two and three scoops.
5. **The ID card.** `id_card.svg` is 1200 × 640, near the 1.91:1 that X,
   LinkedIn, Bluesky and Threads show uncropped. Color it only through
   `var(--bf-bg)`, `--bf-ink` and `--bf-s1`…`--bf-s3` (the icon's three
   shapes, top down), by class, so the card page can recolor it without
   asking the server. Define each colorway in `colorways` and list it in
   `colorway_order`; `default_colorway` is the one a card starts in.
   - Keep `id="bfc-subscriber"` on the name's `<text>`: the card page writes
     the typed name into it.
   - Keep both branches of the `<style>` element. With `raster` set (the
     copy `card.png` hands to `resvg`, which reads neither `var()` nor
     `@import`) it writes the colorway's colors straight into the
     `.bfc-*` rules; otherwise it imports `fonts_url` and colors through
     the variables. A new class colored by a `--bf-*` variable needs its
     line in both.
   - Print the policy id, plan name, cover, deductible and premium:
     `tests/test_app.py` and the acceptance suite look for them.
   - Keep inside the canvas. The longest text is the subscriber name, up to
     24 characters, which shrinks past 16.
6. **Check it.** Run the app (`gemdb web/app.py`) and look at `/`,
   `/quote`, `/policies/BF-100539` and `/policies/BF-100539/card` at desktop
   and phone widths. On the card page, try every colorway with a long name,
   then **Download image** and confirm the PNG matches the page, fonts
   included. The PNG is drawn by `resvg` (`brew install resvg` on a Mac).
   Then run `python3 -m unittest discover`.

## Sharing the card

**Share** on the card page shares a link to the card, and each network shows
the card as the link's preview.

- **The link is the card page as it stands**: `/policies/<id>/card?style=&name=`
  pins down one card, so a different card is a different URL and a
  network's cached preview is never the wrong picture.
- **The preview is `/policies/<id>/card.png`**, `id_card.svg` drawn by
  `resvg` (web/cards.py). It is drawn once per card and kept on disk under
  the hash of the SVG, in `BRAINFREEZE_CARD_CACHE` (by default a folder in
  the system's temporary directory). **Download image** saves the same file.
  Without `resvg` on the PATH it answers 503.
- **The card page's `<head>`** carries `og:` and `twitter:` tags pointing at
  that PNG. Networks need absolute HTTPS URLs, and behind a proxy the app
  can't tell its own address, so set `BRAINFREEZE_PUBLIC_URL` (for example
  `https://brainfreeze.example.com`) wherever the app is public. Unset, the
  tags use the address the request came to.
- **The buttons are plain links**: `x.com/intent/post?text=&url=`,
  `bsky.app/intent/compose?text=`, `threads.com/intent/post?text=` (the
  link at the end of the text) and `linkedin.com/sharing/share-offsite/?url=`
  (LinkedIn takes no text). **Copy link** copies the URL, and where the
  browser has `navigator.share` (phones, mostly), **Share link…** opens the
  device's share sheet with it. The post's text names no other link, because
  Bluesky builds its card from the first link in a post.
- **Previews need a public address.** On `127.0.0.1` the links still work
  but no network can fetch the preview. LinkedIn's Post Inspector refreshes
  a cached preview; the others can't be refreshed.

The name on a card is the reader's own and the app doesn't store it, but a
shared link carries it, and so does the preview: the card page says so
beside the name field. The name and the colorway ride in the URL
(`?name=&style=`), so a reload, **Download image** and a shared link all draw
the same card.

## Keeping this branch

`bfi-visual-rebrand` lives alongside `main` and is not merged. `main` keeps
its brand in the same three files, so this branch is `main` with those
files replaced, `app.css` restyled and the ID card's styles, name and
sharing added. To pick up `main`, rebase onto it. Conflicts will be in
`web/templates/`:

- `brand.css`, `_brand.html`, `id_card.svg`, `app.css` and `card.html`
  are this branch's own. Keep this branch's version, then bring across
  anything new on `main` that isn't brand: a new field, page or test hook,
  such as `.card.row`, `.big`, `#id-card svg` or `a[download$=".png"]`.
- Other templates: take `main`'s content and structure, and keep this
  branch's classes and brand calls.
- `.claude/skills/rebrand/contrast.py`: keep this branch's `PAIRS`, which
  name this branch's tokens.
