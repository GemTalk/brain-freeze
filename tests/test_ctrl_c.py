"""Ctrl-C stops the app, the way its banner and the README's step 2 say.

Run: python3 -m unittest tests.test_ctrl_c -v

It does not yet, and this is marked an expected failure so that the suite says
so without going red. On GemDB Code 1.5.4 a real Ctrl-C
-- `\\x03` through a terminal, not a signal from `kill` -- makes topaz report a
soft break (error 6003) and wait at its own `topaz 1>` prompt, still holding a
session, until someone types `exit`. It is GemDB's `gemdb` command, not the
app: any long-running `gemdb` script does the same.

When GemDB fixes it this reports an UNEXPECTED SUCCESS. That is the cue to take
the `expectedFailure` off -- and nothing in the README has to change, because
the README already says what should happen.

CPython-side, because it SPAWNS the app in a session of its own.
"""

import os
import pty
import select
import shutil
import signal
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Not the app's 5050: this must not collide with an app someone is running.
PORT = "6471"


def gemdb_command():
    found = shutil.which("gemdb")
    if found:
        return found
    default = os.path.join(os.path.expanduser("~"), "GemDB", "bin", "gemdb")
    return default if os.path.isfile(default) else None


def read_until(fd, wanted, seconds):
    seen = b""
    deadline = time.time() + seconds
    while time.time() < deadline and wanted not in seen:
        ready, _, _ = select.select([fd], [], [], 0.5)
        if ready:
            try:
                seen += os.read(fd, 4096)
            except OSError:
                break
    return seen


@unittest.skipUnless(gemdb_command(), "needs GemDB: no gemdb command here")
class CtrlCStopsTheApp(unittest.TestCase):

    @unittest.expectedFailure
    def test_ctrl_c_stops_it(self):
        pid, fd = pty.fork()
        if pid == 0:
            os.chdir(REPO)
            os.environ["BRAINFREEZE_PORT"] = PORT
            os.execv(gemdb_command(), ["gemdb", "web/app.py"])
        try:
            banner = read_until(fd, b"Ctrl-C", 300)
            self.assertIn(b"Ctrl-C", banner, "the app never said it was running")
            os.write(fd, b"\x03")
            for _ in range(40):
                done, _status = os.waitpid(pid, os.WNOHANG)
                if done:
                    return
                read_until(fd, b"\0", 0.5)       # keep the terminal drained
            self.fail("still running 20 seconds after Ctrl-C")
        finally:
            stop(pid, fd)


def stop(pid, fd):
    """Get the app, and topaz under it, out -- without ever waiting forever.

    `exit` is what leaves topaz's prompt today. Then the whole group: the
    child of a pty is a session leader, and signalling only the `gemdb`
    wrapper is not enough, because bash defers a SIGTERM until its
    foreground child -- topaz -- has finished.
    """
    try:
        os.write(fd, b"exit\n")
    except OSError:
        pass
    for sig in (None, signal.SIGTERM, signal.SIGKILL):
        if sig is not None:
            try:
                os.killpg(pid, sig)
            except OSError:
                pass
        for _ in range(20):
            try:
                done, _status = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                return
            if done:
                return
            time.sleep(0.25)


if __name__ == "__main__":
    unittest.main()
