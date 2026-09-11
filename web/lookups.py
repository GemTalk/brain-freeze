"""Finding the objects a request is about, and refusing when they are not there.

Shared by both surfaces, because "which policy is this, and what if there
isn't one" is the same question whether the answer will be rendered or
serialised. Only the shape of the refusal differs, and that stays with the
surface that has to produce it.

There is no ORM and no session to open. `book()` is the whole data-access
layer, and it is one dictionary lookup.

A top-level module, deliberately. Grail keeps a committed PACKAGE module
compiled in the database and serves that copy to every later session; a
top-level module is recompiled from disk each run. Measured, because it
decides whether editing this file needs a `redeploy.py` first. It does not.
"""

from flask import abort

import gemdb

#: The one key in `gemdb.root` this whole application uses.
ROOT_KEY = "brainfreeze"


def book():
    return gemdb.root[ROOT_KEY]


def quotes(the_book):
    """The book's quotes, or a 500 that says what to do about it.

    `Book.quotes` did not exist when the sample book was committed, and a
    class-level default declared now would not reach it: editing a class
    compiles a DIFFERENT class and instances keep the one they were made
    under. So an old book raises AttributeError here rather than quietly
    starting a second store on the side, and the message names the two
    commands that fix it -- because the reader who meets this will otherwise
    reasonably conclude the code is broken.

    `abort` here is Flask's. `gemdb.abort()` must never appear in this
    application; see `take_new_view` in app.py.
    """
    try:
        return the_book.quotes
    except AttributeError:
        abort(500, "This book was committed before quotes had a class of "
                   "their own. Run `gemdb tools/redeploy.py` to give the database "
                   "the current brainfreeze package, then `gemdb tools/seed.py` to "
                   "rebuild the book under it.")


def policy_or_404(policy_id):
    try:
        return book()[policy_id]
    except KeyError:
        abort(404)


def quote_or_404(quote_id):
    try:
        return quotes(book())[quote_id]
    except KeyError:
        abort(404)


def next_id(existing, prefix, width, start):
    """The next free identifier in a series, given the ones already used.

    Verbatim from the single-file app. It tolerates an identifier that does
    not parse rather than raising, and floors at `start - 1` so an empty
    series begins at `start` -- both of which are load-bearing and neither of
    which is obvious, so this was moved rather than rewritten.
    """
    highest = start - 1
    for identifier in existing:
        try:
            highest = max(highest, int(identifier.split("-")[1]))
        except (IndexError, ValueError):
            continue
    return "%s-%0*d" % (prefix, width, highest + 1)
