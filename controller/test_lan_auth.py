import os
import subprocess
import unittest
from unittest.mock import patch

from controller import auth


class PrivateLanAddressTests(unittest.TestCase):
    def test_private_ipv4_addresses_qualify(self):
        for value in ("192.168.5.77", "192.168.5.33", "10.0.0.8", "172.16.4.1", "172.31.255.254", " 192.168.1.2 "):
            self.assertEqual(auth.private_lan_address(value), value.strip(), value)

    def test_everything_else_is_refused(self):
        for value in ("0.0.0.0", "127.0.0.1", "169.254.1.1", "8.8.8.8", "172.32.0.1", "100.64.0.1",
                      "::1", "fe80::1", "r2m2.local", "", None, "192.168.5"):
            self.assertIsNone(auth.private_lan_address(value), value)

    def test_client_network_follows_the_bind_address(self):
        self.assertEqual(str(auth.lan_client_network("192.168.5.77")), "192.168.4.0/22")
        self.assertEqual(str(auth.lan_client_network("192.168.5.33")), "192.168.4.0/22")
        self.assertEqual(str(auth.lan_client_network("10.1.2.3")), "10.1.0.0/22")


class ValidateLanConfigTests(unittest.TestCase):
    def validate(self, host, lan=True):
        env = {"VOICE_DEVELOPER_HOST": host}
        with patch.dict(os.environ, env), patch.object(auth, "LOCAL_AUTH", True), \
                patch.object(auth, "LAN_LOCAL_AUTH", lan):
            auth.validate_auth_config()

    def test_lan_mode_accepts_any_private_address(self):
        self.validate("192.168.5.77")
        self.validate("10.0.0.5")

    def test_lan_mode_rejects_wildcard_loopback_and_public_hosts(self):
        for host in ("0.0.0.0", "127.0.0.1", "8.8.8.8", "r2m2.local"):
            with self.assertRaisesRegex(RuntimeError, "private LAN address"):
                self.validate(host)

    def test_without_the_opt_in_local_auth_still_needs_loopback(self):
        self.validate("127.0.0.1", lan=False)
        with self.assertRaisesRegex(RuntimeError, "127.0.0.1"):
            self.validate("192.168.5.77", lan=False)


class DetectHostTests(unittest.TestCase):
    """start.sh --detect-host reads the Mac's address from ipconfig and never launches anything."""

    def detect(self, addresses, extra_env=None):
        import pathlib
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fake = pathlib.Path(tmp) / "ipconfig"
            cases = "\n".join(f'  {iface}) echo "{addr}";;' for iface, addr in addresses.items())
            fake.write_text(f'#!/bin/sh\ncase "$2" in\n{cases}\n  *) exit 1;;\nesac\n')
            fake.chmod(0o755)
            env = {**os.environ, "PATH": f"{tmp}:{os.environ['PATH']}", **(extra_env or {})}
            script = os.path.join(os.path.dirname(__file__), "..", "start.sh")
            return subprocess.run(["bash", script, "--detect-host"], env=env,
                                  capture_output=True, text=True, timeout=20)

    def test_uses_the_first_interface_with_a_private_address(self):
        result = self.detect({"en0": "", "en1": "169.254.9.9", "en2": "10.4.5.6", "en3": "192.168.1.9"})
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "10.4.5.6"))

    def test_follows_a_changed_address(self):
        self.assertEqual(self.detect({"en0": "192.168.5.33"}).stdout.strip(), "192.168.5.33")
        self.assertEqual(self.detect({"en0": "192.168.5.77"}).stdout.strip(), "192.168.5.77")

    def test_public_or_missing_addresses_are_not_used(self):
        for addresses in ({"en0": "8.8.8.8"}, {"en0": "127.0.0.1"}, {}):
            result = self.detect(addresses)
            self.assertEqual(result.returncode, 1, addresses)
            self.assertEqual(result.stdout.strip(), "", addresses)
            self.assertIn("No private LAN address", result.stderr)

    def test_lan_mode_without_a_host_and_no_address_refuses_to_start(self):
        import pathlib
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fake = pathlib.Path(tmp) / "ipconfig"
            fake.write_text("#!/bin/sh\nexit 1\n")
            fake.chmod(0o755)
            env = {k: v for k, v in os.environ.items() if k != "VOICE_DEVELOPER_HOST"}
            env.update({"PATH": f"{tmp}:{os.environ['PATH']}", "VOICE_DEVELOPER_LOCAL_AUTH_LAN": "1"})
            script = os.path.join(os.path.dirname(__file__), "..", "start.sh")
            result = subprocess.run(["bash", script], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 1)
        self.assertIn("could not find this Mac's private LAN address", result.stdout)


class StartScriptTests(unittest.TestCase):
    """start.sh refuses a non-private host in LAN mode before launching anything."""

    def run_start(self, host, lan="1"):
        env = {**os.environ, "VOICE_DEVELOPER_HOST": host, "VOICE_DEVELOPER_LOCAL_AUTH_LAN": lan}
        script = os.path.join(os.path.dirname(__file__), "..", "start.sh")
        return subprocess.run(["bash", script], env=env, capture_output=True, text=True, timeout=20)

    def test_refuses_non_private_hosts(self):
        for host in ("0.0.0.0", "8.8.8.8", "127.0.0.1", "172.32.0.1"):
            result = self.run_start(host)
            self.assertEqual(result.returncode, 1, host)
            self.assertIn("private LAN address", result.stdout, host)


if __name__ == "__main__":
    unittest.main()
