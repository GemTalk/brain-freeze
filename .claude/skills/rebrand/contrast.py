"""Check the brand's colour pairs for contrast, as BRANDING.md asks.

    python3 .claude/skills/rebrand/contrast.py [path/to/brand.css]

Reads the hex colours out of brand.css (web/templates/brand.css by default)
and prints each pair the pages put together, its contrast ratio, and
whether it reaches 4.5:1, what WCAG asks for text at these sizes. Exits 1
if any pair falls short, or names a token brand.css doesn't define as a
hex colour, so it can gate a change; the stock brand falls short.
"""
import re
import sys

#: (text, ground, where the pages use it)
PAIRS = [
    ("--ink", "--bg", "body text"),
    ("--ink-2", "--bg", "secondary text"),
    ("--muted", "--bg", "small print"),
    ("--muted", "--surface", "small print on cards"),
    ("--ice-deep", "--bg", "links and eyebrows"),
    ("--ice-deep", "--ice-soft", "tags and the current nav item"),
    ("--mint", "--bg", "yes"),
    ("--mint", "--mint-soft", "approved tags"),
    ("--berry", "--berry-soft", "declined tags"),
    ("--amber-ink", "--amber-soft", "warnings"),
    ("--on-ice", "--ice", "buttons"),
    ("--on-ice", "--ice-hover", "buttons under the pointer"),
    ("--on-ink", "--ink", "the chosen filter"),
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
