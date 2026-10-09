---
name: rebrand
description: Apply a new brand to the Brain Freeze web app, meaning its name, colours, fonts, logo or mark, favicon and ID card. Use it when someone wants the app to look like their company or product, gives you brand guidelines, a logo, a palette or fonts to apply, or asks to rebrand, re-skin or white-label the app.
---

# Rebrand the web app

`BRANDING.md` at the repo root is the source of truth. Read it in full
before you change anything. This skill is the working order for an agent.
It doesn't replace that guide.

The brand is three files in `web/templates/`: `brand.css` (tokens),
`_brand.html` (name, fonts, marks, favicon) and `id_card.svg` (the ID
card). A rebrand changes those three. Touch `app.css` only if the person
asks for different shapes or layout, not just a different look. Touch
Python only for the startup banner, and see BRANDING.md step 3 for that.

## 1. Gather the brand

Work out what you have and ask once for what's missing. Don't invent a
brand they didn't give you.

- **Name**: the full name for sentences and titles, and the short one the
  header and card set large.
- **Colours**: a main colour, plus the ink and ground, and colours for
  yes, no and careful if they have them. If they don't, derive tints from
  the main colour and keep the stock mint, berry and amber.
- **Fonts**: they must be on Google Fonts, or have a Google Fonts stand-in
  you name to the person. The ID card uses system fonts regardless.
- **Mark**: an SVG is best. If you only have a PNG, or a logo in a deck or
  a PDF, redraw it as SVG paths rather than embedding the raster. Trace its
  geometry, then overlay your paths on the original to check the fit.
- **ID card**: keep the stock layout recoloured unless they give you a
  design.

If they hand you brand guidelines (a deck, a PDF, images), pull these from
them, show the person what you found, and confirm before applying it.

## 2. Work on a branch

Create a branch for the brand. Don't rebrand `main` in place.

## 3. Apply it

Follow BRANDING.md's steps 1 to 5 in order: tokens, fonts, name, marks,
card. Keep every token name in `brand.css`. The names are roles (`--ice`
is the main colour, whatever its hue), and `app.css` uses all of them.

## 4. Check it

- Contrast: run `python3 .claude/skills/rebrand/contrast.py`. It prints
  each text-on-ground pair the pages use and flags those under 4.5:1. Fix
  what you can. Report any pair you leave short, and say why.
- Pages: run the app (`gemdb web/app.py`, on http://127.0.0.1:5050/) and
  look at every page BRANDING.md step 6 lists, at desktop and phone widths.
  If you can drive a headless browser, take screenshots and look at them.
  Check the header lockup, the favicon, the home hero and the ID card.
- The card: open `/policies/BF-100539/card.svg` on its own, and check
  **Download image** gives a PNG that matches the page.
- Tests: `python3 -m unittest discover`, then `gemdb tools/run_db_tests.py`.

## 5. Report

Tell the person what changed and what you substituted, such as a font
stand-in or a redrawn logo. Name any contrast pair still under 4.5:1, and
anything you left alone. Include screenshots if you took them.
