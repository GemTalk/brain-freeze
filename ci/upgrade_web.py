"""Drive the running web app the way a reader's browser does, for ci/upgrade.sh.

    python3 ci/upgrade_web.py buy   BASE_URL
    python3 ci/upgrade_web.py claim BASE_URL POLICY FLAVOUR TOPPING...
    python3 ci/upgrade_web.py check BASE_URL POLICY CLAIM [FLAVOUR TOPPING...]

`buy` gets a quote, takes the Sundae plan and files a claim on the new policy,
as step 2 of the README does; it prints `POLICY <id>` and `CLAIM <id>`.
`claim` files a claim that answers step 3's two questions and prints
`CLAIM <id>`. `check` opens a claim's page and its JSON and, given a flavour,
requires both to name it and the toppings. Exits non-zero, saying why, on
anything else.

The same form posts the pages make -- the HTML routes are the only ones that
write; the JSON surface is read-only by design. Standard library only.
"""

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT_S = 120


def post(url, fields):
    """POST a form, follow the app's redirect, return (final url, body)."""
    data = urllib.parse.urlencode(fields, doseq=True).encode("utf-8")
    with urllib.request.urlopen(urllib.request.Request(url, data=data),
                                timeout=TIMEOUT_S) as response:
        return response.geturl(), response.read().decode("utf-8")


def get(url):
    with urllib.request.urlopen(url, timeout=TIMEOUT_S) as response:
        return response.read().decode("utf-8")


def found(pattern, text, what):
    match = re.search(pattern, text)
    if not match:
        sys.exit("upgrade_web: no %s in %r" % (what, text[:300]))
    return match.group(1)


def file_claim(base, policy, extra=()):
    fields = [("trigger", "ice cream"), ("duration", "Longer than ten"),
              ("pain", "9")] + list(extra)
    url, body = post("%s/policies/%s/claims" % (base, policy), fields)
    claim = found(r"/claims/(CLM-\d+)$", url, "claim id in %s" % url)
    return claim, body


def buy(base):
    url, _ = post(base + "/quote", {
        "age": "9", "migraine_history": "no",
        "tension_type_headache_history": "no",
        "typical_consumption_speed": "fast"})
    quote = found(r"/quote/(QTE-\d+)$", url, "quote id in %s" % url)
    url, _ = post("%s/quote/%s/accept" % (base, quote), {"plan": "Sundae"})
    policy = found(r"/policies/(BF-\d+)/card$", url, "policy id in %s" % url)
    claim, _ = file_claim(base, policy)
    print("QUOTE %s" % quote)
    print("POLICY %s" % policy)
    print("CLAIM %s" % claim)


def claim(base, policy, flavour, toppings):
    extra = [("flavour", flavour)] + [("toppings", t) for t in toppings]
    claim_id, body = file_claim(base, policy, extra)
    subtitle = found(r'(?s)<p class="sub[^"]*">(.*?)</p>', body, "decision subtitle")
    if flavour not in subtitle:
        sys.exit("upgrade_web: the decision for %s does not name %r: %r"
                 % (claim_id, flavour, subtitle))
    print("CLAIM %s" % claim_id)


def check(base, policy, claim_id, flavour=None, toppings=()):
    page = get("%s/policies/%s/claims/%s" % (base, policy, claim_id))
    if claim_id not in page:
        sys.exit("upgrade_web: the page for %s does not show it" % claim_id)
    subtitle = found(r'(?s)<p class="sub[^"]*">(.*?)</p>', page, "decision subtitle")
    try:
        api = json.loads(get("%s/api/claim/%s" % (base, claim_id)))
    except urllib.error.HTTPError as refused:
        sys.exit("upgrade_web: /api/claim/%s answered %d" % (claim_id, refused.code))
    said = api.get("claim", api)
    if flavour:
        if flavour not in subtitle or any(t.lower() not in subtitle.lower() for t in toppings):
            sys.exit("upgrade_web: the page for %s does not name %s with %s: %r"
                     % (claim_id, flavour, toppings, subtitle))
        if said.get("flavour") != flavour or said.get("toppings") != list(toppings):
            sys.exit("upgrade_web: /api/claim/%s says flavour=%r toppings=%r"
                     % (claim_id, said.get("flavour"), said.get("toppings")))
    print("OK %s %s %s" % (policy, claim_id, " ".join(subtitle.split())))


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    command, base = argv[1], argv[2].rstrip("/")
    if command == "buy":
        buy(base)
    elif command == "claim" and len(argv) >= 5:
        claim(base, argv[3], argv[4], argv[5:])
    elif command == "check" and len(argv) >= 5:
        check(base, argv[3], argv[4], argv[5] if len(argv) > 5 else None, argv[6:])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
