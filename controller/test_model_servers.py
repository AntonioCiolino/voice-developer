import socket
import unittest
from unittest.mock import patch

from controller.model_servers import (
    lan_opt_in, resolve_server, server_names, validate_server_url,
)
from controller.providers import PlannerConfigurationError

GAI = "controller.model_servers.socket.getaddrinfo"


def answer(*addresses):
    return lambda host, port, family=0: [(family, 1, 6, "", (a, port or 0)) for a in addresses]


def servers(**extra):
    return {"ALLOW_LAN_MODEL_SERVERS": "on", "MODEL_SERVERS": "mini", "MODEL_SERVER_MINI_KIND": "lmstudio",
            "MODEL_SERVER_MINI_URL": "http://192.168.1.20:1234", **extra}


class ValidateUrlTests(unittest.TestCase):
    def ok(self, url, allow=True):
        return validate_server_url(url, "MODEL_SERVER_MINI_URL", allow)

    def bad(self, url, allow=True, text=None):
        with self.assertRaises(PlannerConfigurationError) as raised:
            self.ok(url, allow)
        message = str(raised.exception)
        self.assertIn("MODEL_SERVER_MINI_URL" if text is None else text, message)
        self.assertNotIn(url, message)
        self.assertNotIn("192.168.1.20", message)
        return message

    def test_private_ip_literals(self):
        for host in ("10.1.2.3", "172.16.0.1", "172.31.255.1", "192.168.1.20"):
            self.assertEqual(self.ok(f"http://{host}:1234/v1/"), (f"http://{host}:1234", True))

    def test_loopback_needs_no_opt_in(self):
        for url in ("http://localhost:1234", "http://127.0.0.1:1234/v1", "http://[::1]:1234"):
            self.assertEqual(self.ok(url, False)[1], False)

    def test_lan_needs_opt_in(self):
        self.assertIn("ALLOW_LAN_MODEL_SERVERS", self.bad("http://192.168.1.20:1234", False))
        with patch(GAI, answer("192.168.1.9")):
            self.assertIn("ALLOW_LAN_MODEL_SERVERS", self.bad("http://r2m2-mini.local:1234", False))

    def test_rejections(self):
        for url in ("http://8.8.8.8:1234", "http://0.0.0.0:1234", "http://169.254.1.1:1234",
                    "http://172.32.0.1:1234", "http://[fe80::1]:1234", "http://[2001:db8::1]:1234",
                    "http://127.1:1234", "http://example.com:1234", "http://mini:1234",
                    "ftp://192.168.1.20", "http://user:pw@192.168.1.20:1234",
                    "http://192.168.1.20:1234?a=1", "http://192.168.1.20:1234#x",
                    "http://192.168.1.20:99999", "192.168.1.20:1234", "http://r2m2.local.:1234"):
            with self.subTest(url=url):
                self.bad(url)

    def test_local_name_is_pinned(self):
        with patch(GAI, answer("192.168.1.9")):
            self.assertEqual(self.ok("http://R2M2-Mini.local:1234/v1"), ("http://192.168.1.9:1234", True))
            self.assertEqual(self.ok("http://r2m2-mini.local")[0], "http://192.168.1.9")

    def test_local_name_must_resolve_privately(self):
        for addresses in (("8.8.8.8",), ("192.168.1.9", "8.8.8.8"), ()):
            with self.subTest(addresses=addresses), patch(GAI, answer(*addresses)):
                self.bad("http://r2m2-mini.local:1234")
        with patch(GAI, side_effect=socket.gaierror):
            self.bad("http://r2m2-mini.local:1234")

    def test_local_name_https_rejected(self):
        with patch(GAI, answer("192.168.1.9")):
            self.bad("https://r2m2-mini.local:1234")
        self.assertEqual(self.ok("https://192.168.1.20:1234"), ("https://192.168.1.20:1234", True))

    def test_resolution_times_out(self):
        import controller.model_servers as ms
        with patch.object(ms, "RESOLVE_TIMEOUT_SECONDS", 0.05), patch(GAI, lambda *a: __import__("time").sleep(1)):
            self.assertIn("in time", self.bad("http://r2m2-mini.local:1234"))


class ServerConfigTests(unittest.TestCase):
    def test_opt_in_values(self):
        for value, expected in (("on", True), ("1", True), ("off", False), ("0", False), ("", False)):
            self.assertEqual(lan_opt_in({"ALLOW_LAN_MODEL_SERVERS": value}), expected)
        self.assertFalse(lan_opt_in({}))
        with self.assertRaises(PlannerConfigurationError) as raised:
            lan_opt_in({"ALLOW_LAN_MODEL_SERVERS": "yes"})
        self.assertIn("ALLOW_LAN_MODEL_SERVERS", str(raised.exception))

    def test_names(self):
        self.assertEqual(server_names({}), [])
        self.assertEqual(server_names({"MODEL_SERVERS": " Mini, studio-2 "}), ["mini", "studio-2"])
        for bad in ("mini,,studio", "Bad Name", "1abc", "mini,mini", "openai", "ollama", "lmstudio", "a" * 25):
            with self.subTest(bad=bad), self.assertRaises(PlannerConfigurationError):
                server_names({"MODEL_SERVERS": bad})

    def test_resolve_server(self):
        server = resolve_server(servers(), "mini")
        self.assertEqual((server.name, server.kind, server.base, server.lan),
                         ("mini", "lmstudio", "http://192.168.1.20:1234", True))
        self.assertEqual(resolve_server({**servers(), "ALLOW_LAN_MODEL_SERVERS": "off",
                                         "MODEL_SERVER_MINI_URL": "http://localhost:1234"}, "mini").lan, False)

    def test_resolve_server_errors(self):
        for values, text in (
            (servers(ALLOW_LAN_MODEL_SERVERS="off"), "ALLOW_LAN_MODEL_SERVERS"),
            (servers(MODEL_SERVER_MINI_KIND="openai"), "MODEL_SERVER_MINI_KIND"),
            (servers(MODEL_SERVER_MINI_KIND=""), "MODEL_SERVER_MINI_KIND"),
            (servers(MODEL_SERVER_MINI_URL=""), "MODEL_SERVER_MINI_URL"),
            (servers(MODEL_SERVER_MINI_URL="http://8.8.8.8:1"), "MODEL_SERVER_MINI_URL"),
        ):
            with self.subTest(text=text, values=values), self.assertRaises(PlannerConfigurationError) as raised:
                resolve_server(values, "mini")
            self.assertIn(text, str(raised.exception))
            self.assertNotIn("8.8.8.8", str(raised.exception))
        with self.assertRaises(PlannerConfigurationError):
            resolve_server(servers(), "other")

    def test_hyphenated_name_variables(self):
        values = {"MODEL_SERVERS": "my-mac", "MODEL_SERVER_MY_MAC_KIND": "ollama",
                  "MODEL_SERVER_MY_MAC_URL": "http://127.0.0.1:11434"}
        self.assertEqual(resolve_server(values, "my-mac").kind, "ollama")

    def test_local_name_resolved_on_every_call(self):
        values = servers(MODEL_SERVER_MINI_URL="http://r2m2-mini.local:1234")
        with patch(GAI, answer("192.168.1.9")):
            self.assertEqual(resolve_server(values, "mini").base, "http://192.168.1.9:1234")
        with patch(GAI, answer("192.168.1.77")):
            self.assertEqual(resolve_server(values, "mini").base, "http://192.168.1.77:1234")
        with patch(GAI, answer("8.8.4.4")), self.assertRaises(PlannerConfigurationError):
            resolve_server(values, "mini")


class PhoneUiTests(unittest.TestCase):
    def test_phone_ui_names_the_three_locations(self):
        from controller.ui import render_phone_ui
        html = render_phone_ui("Tester", False)
        for text in ("Local network", "This machine", "uses_lan"):
            self.assertIn(text, html)
if __name__ == "__main__":
    unittest.main()
