"""Finding the objects a request is about, and refusing when they are not there.

Shared by both surfaces, because "which policy is this, and what if there
isn't one" is the same question whether the answer will be rendered or
serialised. Only the shape of the refusal differs, and that stays with the
surface that has to produce it.

There is no ORM and no session to open. `book()` is the whole data-access
layer, and it is one dictionary lookup.
"""

# Flask's. `gemdb.abort()` appears in this app only after a commit has
# already failed: see conflicts.py, and `take_new_view` in app.py.
from flask import abort

import gemdb
import pages

#: The one key in `gemdb.root` this whole application uses.
ROOT_KEY = "brainfreeze"


def book():
    return gemdb.root[ROOT_KEY]


def quotes(the_book):
    """The book's quotes, or a 500 that says what to do about it.

    A book committed before `Book.quotes` existed has no quotes store. This
    refuses with the commands that fix it rather than quietly starting a
    second store on the side.
    """
    try:
        return the_book.quotes
    except AttributeError:
        pages.refuse(500, "This book was committed before quotes had a class of "
                   "their own. Run `gemdb tools/load.py` to give the database "
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

