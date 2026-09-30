"""How this app starts, what it says while it runs, and what it says when it
breaks. The factory is `app.py`; this is everything about serving it.

The werkzeug and flask imports are deferred into the functions that need
them, so the rest -- port, preflight, banner -- imports under CPython and is
tested by `python3 -m unittest discover`.
"""

import re
import socket
import subprocess


#: Not Flask's 5000: on a stock Mac, AirPlay Receiver holds that one.
DEFAULT_PORT = 5050

#: Set this to serve somewhere else. The acceptance suite reads it through
#: `configured_port` too, so it probes the port the app will actually open.
PORT_VARIABLE = "BRAINFREEZE_PORT"


def configured_port(environ):
    """The port to serve on: `BRAINFREEZE_PORT` if it is set, else 5050.

    Raises ValueError, worded for a person, if it is set to something that is
    not a port -- a typo should stop the app, not quietly serve on 5050 while
    whoever set it looks somewhere else.
    """
    said = environ.get(PORT_VARIABLE, "").strip()
    if not said:
        return DEFAULT_PORT
    try:
        port = int(said)
    except ValueError:
        port = 0
    if not 0 < port < 65536:
        raise ValueError("%s=%r is not a port. Use a number from 1 to 65535, "
                         "or unset it for %d." % (PORT_VARIABLE, said,
                                                  DEFAULT_PORT))
    return port


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
                  "That isn't Brain Freeze, so don't kill it without looking."]
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

    Both hang off Flask rather than the request handler: Grail's
    `werkzeug.serving` never calls `log_request` (`run_wsgi` uses
    `send_response_only`), so overriding it would be dead code.
    """
    from werkzeug.exceptions import HTTPException

    @app.after_request
    def say_what_was_asked(response):
        print("%-5s %-34s %s"
              % (request_method(), request_path(), response.status_code))
        return response

    @app.errorhandler(Exception)
    def report(error):
        """Return an HTTPException, so Flask answers with it; print anything
        else, traceback and all, to the terminal running the app."""
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
