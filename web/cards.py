"""The ID card as a PNG, and the card page's address as the world sees it.

A shared link's preview is a PNG: X, LinkedIn, Facebook and the rest do not
take an SVG. So `/policies/<id>/card.png` hands id_card.svg, drawn in its
raster mode, to `resvg`, an external program -- the app is standard library
only under Grail, and `subprocess` works there. Each PNG is drawn once and
kept on disk under the hash of what drew it, so a crawler's second visit, or
the hundredth network's first, is a file read.

SETTINGS, read on each request

    BRAINFREEZE_CARD_CACHE   where the PNGs are kept. Default: a folder in the
                             system's temporary directory. Instances behind
                             one proxy can share it: a PNG is written under a
                             temporary name, then renamed into place.
    BRAINFREEZE_PUBLIC_URL   the site's origin, https://brainfreeze.example.com,
                             for the absolute URLs in a page's link-preview
                             tags. Behind a proxy the app cannot know it.
                             Default: the address the request came to.

`resvg` must be on the PATH (`resvg --version`). Without it a card's PNG is a
503 and nothing else breaks. The fonts it draws with are the TTFs in
web/fonts/, and only those, so the PNG looks the same on every machine.
"""

import hashlib
import os
import subprocess
import tempfile

from flask import current_app, request, url_for

#: Where the fonts folder's path lives on the app: `app.extensions[FONTS]`.
FONTS = "brainfreeze.fonts"

CACHE_VARIABLE = "BRAINFREEZE_CARD_CACHE"
PUBLIC_URL_VARIABLE = "BRAINFREEZE_PUBLIC_URL"

#: The card's width, as id_card.svg draws it.
WIDTH = 1200

#: Long enough for the slowest first draw, short enough that a stuck
#: `resvg` does not hold an instance that answers one request at a time.
TIMEOUT = 20


class Unavailable(Exception):
    """`resvg` is missing, or failed to draw the card."""


def cache_folder(environ=os.environ):
    """Where the PNGs are kept: `BRAINFREEZE_CARD_CACHE`, or a temporary
    folder."""
    return (environ.get(CACHE_VARIABLE)
            or os.path.join(tempfile.gettempdir(), "brainfreeze-cards"))


def command(fonts, out):
    """The `resvg` command that draws stdin's SVG to `out`."""
    return ["resvg", "--skip-system-fonts", "--use-fonts-dir", fonts,
            "--sans-serif-family", "Inter", "--width", str(WIDTH), "-", out]


def png(svg, environ=os.environ):
    """The PNG of `svg`, an id_card.svg drawn with `raster=True`, as bytes.

    Kept under the sha256 of the SVG and of the command, so a new font or a
    new flag draws afresh rather than serving the old picture.
    """
    fonts = current_app.extensions[FONTS]
    folder = cache_folder(environ)
    digest = hashlib.sha256(
        ("\0".join(command(fonts, "")) + "\0" + svg).encode("utf-8"))
    path = os.path.join(folder, digest.hexdigest() + ".png")
    if not os.path.exists(path):
        os.makedirs(folder, exist_ok=True)
        partial = "%s.%d.part" % (path, os.getpid())
        try:
            subprocess.run(command(fonts, partial), input=svg.encode("utf-8"),
                           capture_output=True, check=True, timeout=TIMEOUT)
            os.replace(partial, path)
        except (OSError, subprocess.SubprocessError) as failure:
            if os.path.exists(partial):
                os.remove(partial)
            raise Unavailable(describe(failure))
    with open(path, "rb") as handle:
        return handle.read()


def describe(failure):
    """What went wrong, in a line for the log."""
    if isinstance(failure, FileNotFoundError):
        return "resvg is not installed (not on the PATH)"
    stderr = getattr(failure, "stderr", None)
    if stderr:
        return "resvg failed: %s" % stderr.decode("utf-8", "replace").strip()
    return "resvg failed: %s" % failure


def public_url(endpoint, environ=os.environ, **arguments):
    """An absolute URL for `endpoint`, on the site's public origin."""
    origin = environ.get(PUBLIC_URL_VARIABLE, "").rstrip("/")
    if origin:
        return origin + url_for(endpoint, **arguments)
    return request.host_url.rstrip("/") + url_for(endpoint, **arguments)
