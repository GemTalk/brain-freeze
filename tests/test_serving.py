"""The serving concerns: who holds the port, what a newcomer is told, and
whether an exception in a view ever reaches a human.

    python3 -m unittest tests.test_serving -v      # most of it
    gemdb -m unittest tests.test_serving -v        # all of it

WHY MOST OF THIS RUNS UNDER CPYTHON

`web/serving.py` defers its `werkzeug`/`flask` imports into the two functions
that need them, so `port_holder`, `preflight` and `banner` are importable and
testable without a database. They are the parts a newcomer meets first and the
parts most likely to rot, and putting them behind `gemdb` would have hidden
them from `python3 -m unittest discover`, which is the command everyone runs.
"""

import os
import socket
import sys
import unittest

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
if WEB not in sys.path:
    sys.path.insert(0, WEB)

import serving

try:
    import gemdb
except ImportError:
    gemdb = None


def a_listening_socket():
    """A bound, listening socket on a free port, and that port."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    probe.listen(1)
    return probe, probe.getsockname()[1]


def a_free_port():
    """A port nothing is listening on. Bound and closed, so it is really free."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


class WhoHoldsThePort(unittest.TestCase):
    def test_a_free_port_has_no_holder(self):
        self.assertIsNone(serving.port_holder("127.0.0.1", a_free_port()))

    def test_a_held_port_names_this_process(self):
        probe, port = a_listening_socket()
        try:
            holder = serving.port_holder("127.0.0.1", port)
            self.assertIsNotNone(holder, "a listening socket has a holder")
            self.assertEqual(holder["pid"], os.getpid())
        finally:
            probe.close()


class Preflight(unittest.TestCase):
    def test_a_free_port_is_allowed(self):
        self.assertIsNone(serving.preflight("127.0.0.1", a_free_port()))

    def test_a_held_port_is_refused(self):
        probe, port = a_listening_socket()
        try:
            with self.assertRaises(serving.PortBusy):
                serving.preflight("127.0.0.1", port)
        finally:
            probe.close()

    def test_the_refusal_names_the_address(self):
        probe, port = a_listening_socket()
        try:
            serving.preflight("127.0.0.1", port)
        except serving.PortBusy as refusal:
            self.assertIn(str(port), str(refusal))
        else:
            self.fail("a held port was not refused")
        finally:
            probe.close()


class WhatTheRefusalSays(unittest.TestCase):
    """Formatted apart from the detecting, because the two branches differ in
    the one way that matters and only one of them can be provoked by a test
    holding its own socket."""

    def test_one_of_ours_is_named_with_the_command_that_stops_it(self):
        said = serving.refusal("127.0.0.1", 5000,
                               {"pid": 4242, "command": "topaz"})
        self.assertIn("4242", said)
        self.assertIn("kill 4242", said)

    def test_somebody_elses_server_is_named_but_not_killed(self):
        """Telling a newcomer to kill a process they did not start is bad
        advice, and the likeliest holder of :5000 on a Mac is AirPlay."""
        said = serving.refusal("127.0.0.1", 5000,
                               {"pid": 4821, "command": "ControlCenter"})
        self.assertIn("4821", said)
        self.assertIn("ControlCenter", said)
        self.assertNotIn("kill 4821", said)

    def test_an_unnamed_holder_still_refuses_and_says_how_to_look(self):
        said = serving.refusal("127.0.0.1", 5000,
                               {"pid": None, "command": None})
        self.assertIn("5000", said)
        self.assertIn("lsof", said)


class TheBanner(unittest.TestCase):
    def test_it_names_the_address_a_newcomer_should_open(self):
        self.assertIn("http://127.0.0.1:5000/", serving.banner("127.0.0.1", 5000))

    def test_it_follows_the_port_it_is_given(self):
        self.assertIn("http://127.0.0.1:9090/", serving.banner("127.0.0.1", 9090))

    def test_it_says_how_to_stop_it(self):
        self.assertIn("Ctrl-C", serving.banner("127.0.0.1", 5000))

    def test_it_says_requests_will_appear(self):
        """The line that ends 'silence means hang'. A newcomer who is not told
        what to expect reads an idle terminal as a broken one."""
        self.assertIn("below", serving.banner("127.0.0.1", 5000).lower())


@unittest.skipIf(gemdb is None, "needs the database -- run under gemdb")
class WhatTheAppSaysWhileItRuns(unittest.TestCase):
    """The access log and the error report, which is the half that needs Flask.

    Both hang off Flask rather than off Grail's serving: `log_request` is
    defined there and never called (run_wsgi uses send_response_only), so a
    handler override would be dead code. Measured before this was written.
    """

    def build(self):
        from flask import Flask
        from werkzeug.exceptions import NotFound
        app = Flask("serving_under_test")
        serving.install_reporting(app)

        @app.route("/ok")
        def ok():
            return "ok"

        @app.route("/boom")
        def boom():
            raise ValueError("the exception the view actually raised")

        @app.route("/missing")
        def missing():
            raise NotFound()

        return app

    def drive(self, path):
        """Return (status, whatever the app printed while answering)."""
        import contextlib, io
        app = self.build()
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            response = app.test_client().get(path)
        return response.status_code, said.getvalue()

    def test_a_request_is_logged_with_its_method_path_and_status(self):
        status, said = self.drive("/ok")
        self.assertEqual(status, 200)
        self.assertIn("GET", said)
        self.assertIn("/ok", said)
        self.assertIn("200", said)

    def test_an_http_exception_keeps_its_status(self):
        """Returning it, never re-raising: re-raising sends Flask into the
        reporting path that trips finding 7, and the client gets a dead
        connection instead of a 404. Measured."""
        status, _ = self.drive("/missing")
        self.assertEqual(status, 404)

    def test_a_real_exception_is_reported_and_answered_as_500(self):
        status, said = self.drive("/boom")
        self.assertEqual(status, 500)
        self.assertIn("the exception the view actually raised", said,
                      "the exception itself has to reach a human")
        self.assertIn("Traceback", said)

    def test_the_report_does_not_go_through_logging(self):
        """`logging` is the thing that breaks here -- Logger.error(exc_info=)
        raises a TypeError over the top of what it was called to report
        (finding 7). The traceback has to be printed."""
        _, said = self.drive("/boom")
        self.assertNotIn("exc_info", said)


if __name__ == "__main__":
    unittest.main()
