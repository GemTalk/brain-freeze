"""Finding 7: an exception in a view is invisible, because reporting it fails.

    gemdb findings/07_logging_stub.py

A Flask view raises. Flask catches it and calls its logger to say so:

    self.logger.error("Exception on %s [%s]", path, method, exc_info=True)

Grail's `logging` is a hand-written stub, and its `Logger.error` took only
`*args`. So the call that exists to report the exception raises one of its own,
and what reaches the log is a `TypeError` about `exc_info` -- with the real
exception somewhere further up, if it is anywhere at all.

**The failure replaces the diagnosis.** That is the whole finding, and it is
the same shape as finding 5 and as the `str.replace` crash behind finding 6:
in each, the code that exists to explain a problem is the code that breaks.

This script writes nothing and changes nothing. It reports which behaviour
*your* Grail has, because there is a fix on `fix/logging-exc-info` in the Grail
repository which is not merged, so the two are both in circulation.
"""

import sys

#: Not `__doc__` -- `__main__` is shared under Grail; see finding 2.
TITLE = "Finding 7: reporting a view's exception is what fails."

SENTINEL = "the exception the view actually raised"


def logging_stub():
    import logging

    print(TITLE)
    print("-" * 70)

    logger = logging.getLogger("finding07")

    print("\n  1. Does Logger.error accept exc_info at all?\n")
    try:
        logger.error("a message", exc_info=True)
        accepts = True
        print("      logger.error(msg, exc_info=True)      accepted")
    except TypeError as error:
        accepts = False
        print("      logger.error(msg, exc_info=True)      TypeError")
        print("        %s" % str(error)[:70])

    print("\n  2. And through Flask, which is where it bit.\n")
    from flask import Flask

    app = Flask(__name__)
    app.config["TESTING"] = False          # let Flask handle it, not the client

    @app.route("/boom")
    def boom():
        raise ValueError(SENTINEL)

    client = app.test_client()
    try:
        response = client.get("/boom")
        status = response.status_code
        body = response.data.decode()
        print("      the request returned              %s" % status)
        blames_logging = "exc_info" in body or "unexpected keyword" in body
        names_the_cause = SENTINEL in body
        print("      the response names the real error  %s" % names_the_cause)
        print("      the response blames logging        %s" % blames_logging)
    except TypeError as error:
        print("      the request RAISED instead of returning 500:")
        print("        %s: %s" % (type(error).__name__, str(error)[:60]))
        blames_logging, names_the_cause = True, False

    print()
    if accepts and not blames_logging:
        print("  Your Grail takes `exc_info`. The view's exception is reported")
        print("  as itself, which is what CPython does. Either the fix on")
        print("  `fix/logging-exc-info` is in this build, or the stub was")
        print("  replaced -- worth recording which.")
        return 0

    print("  Reproduced. `Logger.error` refuses the `exc_info` keyword that")
    print("  Flask's own error handler passes, so the report about the")
    print("  exception fails and the exception goes unreported. Debugging a")
    print("  view here means adding print statements, because the framework's")
    print("  own reporting cannot run.")
    print()
    print("  The fix is two lines, on `fix/logging-exc-info` in the Grail")
    print("  repository, unmerged. `LoggerAdapter.error` in the same file")
    print("  already takes `**kwargs`, so the signature is the only thing")
    print("  standing between this and a working traceback.")
    return 0


if __name__ == "__main__":
    sys.exit(logging_stub())
