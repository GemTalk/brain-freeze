"""How this app starts, what it says while it runs, and what it says when it
breaks. The factory is `app.py`; this is everything about *serving* it.

WHY THIS IS A SEPARATE MODULE

`app.py` says of itself that it is "the factory and the entry point, and
nothing else". Preflight, a banner, an access log and error reporting are none
of those, and putting them there would make that docstring false.

WHY THE werkzeug/flask IMPORTS ARE DEFERRED

`port_holder`, `preflight` and `banner` are ordinary Python and need no
database. Importing werkzeug at module scope would make this file unimportable
under CPython and push their tests behind `gemdb`, out of
`python3 -m unittest discover` -- which is the command everyone actually runs,
and these are the parts a newcomer meets first.
"""

import re
import socket
import subprocess


class PortBusy(Exception):
    """Something already holds the address we were told to serve on.

    Carries the whole refusal, formatted for a person: `serve()` prints it and
    exits non-zero, so the `gemdb` wrapper's status file gets a real code.
    """


def port_holder(host, port, timeout=1.0):
    """Who is listening on `host:port`, or None.

    Returns a dict with `pid` and `command`. `pid` can be None: `lsof` may be
    absent or may refuse to name another user's process, and a refusal that
    cannot name the holder still beats a bind error nobody can read.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(timeout)
        if probe.connect_ex((host, port)) != 0:
            return None

    try:
        finished = subprocess.run(
            ["lsof", "-nP", "-iTCP:%d" % port, "-sTCP:LISTEN"],
            capture_output=True, text=True)
    except Exception:
        return {"pid": None, "command": None}

    for line in finished.stdout.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 2:
            continue
        try:
            return {"pid": int(fields[1]), "command": fields[0]}
        except ValueError:
            continue
    return {"pid": None, "command": None}


#: A holder whose command looks like this app rather than somebody else's
#: server. `gemdb` execs topaz, so that is the name that shows up.
OURS = re.compile(r"topaz|gemdb", re.IGNORECASE)


def refusal(host, port, holder):
    """The whole refusal, as a person should read it.

    Kept apart from `preflight` because the two branches below differ in the
    one way that matters -- whether it is safe to tell the reader to kill the
    thing -- and only one of them can be provoked by a test holding its own
    socket.
    """
    lines = ["Brain Freeze can't start: something is already using %s:%d."
             % (host, port), ""]

    pid, command = holder["pid"], holder["command"]
    if pid is None:
        lines += ["Nothing here could say what has it -- `lsof` did not "
                  "answer.", "",
                  "Find it with:", "",
                  "    lsof -nP -iTCP:%d -sTCP:LISTEN" % port]
    elif command and OURS.search(command):
        lines += ["  PID %d   %s" % (pid, command), "",
                  "That looks like an earlier run of this app that didn't "
                  "shut down.", "Stop it and try again:", "",
                  "    kill %d" % pid]
    else:
        lines += ["  PID %d   %s" % (pid, command or "?"), "",
                  "That isn't Brain Freeze, so don't kill it without looking.",
                  "On macOS, AirPlay Receiver uses port 5000 --",
                  "System Settings > General > AirDrop & Handoff."]
    return "\n".join(lines)


def preflight(host, port):
    """Return if the address is free; raise `PortBusy` if it is not."""
    holder = port_holder(host, port)
    if holder is None:
        return None
    raise PortBusy(refusal(host, port, holder))


def banner(host, port):
    """What a newcomer reads when the app starts.

    The last line is doing as much work as the URL: a server that prints
    nothing is indistinguishable from a hung one, and someone who has not been
    told what to expect reads an idle terminal as a broken one.
    """
    return "\n".join([
        "Brain Freeze Insurance is running.",
        "",
        "  Open:  http://%s:%d/" % (host, port),
        "  Stop:  Ctrl-C",
        "",
        "Requests appear below as they arrive.",
    ])


def install_reporting(app):
    """Give the app an access log and make a view's exception visible.

    Both hang off Flask rather than off Grail's serving layer, because that is
    where the hooks actually fire. Grail ships its own `werkzeug.serving` in
    which `log_request` is defined and never called -- `run_wsgi` uses
    `send_response_only`, which, unlike `send_response`, does not log -- so
    overriding the handler's `log_request` would be dead code. Measured.
    """
    from werkzeug.exceptions import HTTPException

    @app.after_request
    def say_what_was_asked(response):
        print("%-5s %-34s %s"
              % (request_method(), request_path(), response.status_code))
        return response

    @app.errorhandler(Exception)
    def report(error):
        """Return an HTTPException; print anything else.

        **Never re-raise an HTTPException here.** Re-raising sends Flask into
        the path that reports the exception with
        `Logger.error(..., exc_info=True)`, and Grail's `logging` does not
        accept `exc_info`, so a TypeError lands on top of the real exception
        and the client gets a closed connection instead of its 404. Returning
        it preserves the status -- measured at 404, 403 and a routing 404.

        And the traceback is PRINTED rather than logged, for the same reason:
        `logging` is the thing that breaks here (finding 7).
        """
        if isinstance(error, HTTPException):
            return error
        import traceback
        print(traceback.format_exc())
        return "Something went wrong. The terminal running this app has the "\
               "traceback.", 500

    return app


def request_method():
    from flask import request
    return request.method


def request_path():
    from flask import request
    return request.full_path.rstrip("?") if request.query_string else request.path
