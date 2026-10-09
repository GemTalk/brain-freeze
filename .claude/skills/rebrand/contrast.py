"""Check the brand's colour pairs for contrast, as BRANDING.md asks.

    python3 .claude/skills/rebrand/contrast.py [path/to/brand.css]

Reads the hex colours out of brand.css (web/templates/brand.css by default)
and prints each pair the pages put together, its contrast ratio, and
whether it reaches 4.5:1, what WCAG asks for text at these sizes. Exits 1
if any pair falls short, or names a token brand.css doesn't define as a
hex colour, so it can gate a change. main's stock brand falls short;
this branch's passes.
"""
import re
import sys

#: (text, ground, where the pages use it). These are this branch's: its
#: app.css is its own, so its pairs are too. A brand that restyles app.css
#: lists the pairs its own app.css puts together.
PAIRS = [
    ("--ink", "--paper", "body text"),
    ("--ink-2", "--paper", "secondary text"),
    ("--muted", "--paper", "small print"),
    ("--muted", "--surface", "small print on cards"),
    ("--blue-text", "--paper", "links"),
    ("--red-text", "--paper", "eyebrows"),
    ("--blue-text", "--blue-soft", "approved tags"),
    ("--red-text", "--red-soft", "declined tags"),
    ("--ink", "--yellow", "the most-chosen tag, the current step"),
    ("--yellow", "--ink", "the home page's eyebrow"),
    ("--ink", "--blue", "buttons"),
    ("--paper", "--ink", "buttons under the pointer, the footer, the nav"),
    ("--ink", "--wash", "table rows under the pointer"),
]


def luminance(hex_colour):
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
               for c in channels]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def main(path):
    css = open(path).read()
    tokens = {}
    for name, value in re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{3,6})\b", css):
        if len(value) == 4:
            value = "#" + "".join(c * 2 for c in value[1:])
        tokens[name] = value
    short = unknown = 0
    for text, ground, where in PAIRS:
        if text not in tokens or ground not in tokens:
            unknown += 1
            print("  ?     %-11s on %-12s %s: not a hex colour in %s"
                  % (text, ground, where, path))
            continue
        r = ratio(tokens[text], tokens[ground])
        ok = r >= 4.5
        short += not ok
        print("  %s %5.2f %-11s on %-12s %s"
              % ("ok  " if ok else "LOW ", r, text, ground, where))
    if unknown:
        print("%d of %d pairs not checked: name them in PAIRS as brand.css"
              " does" % (unknown, len(PAIRS)))
    print("%d of %d pairs under 4.5:1" % (short, len(PAIRS)) if short
          else "every pair checked reaches 4.5:1")
    return 1 if short or unknown else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1
                  else "web/templates/brand.css"))
