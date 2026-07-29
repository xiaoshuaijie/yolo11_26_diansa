import subprocess
import unittest
from unittest.mock import patch

from scripts.maixpy_skill import discover


class DiscoverTests(unittest.TestCase):
    def test_parse_avahi_text_workstation_and_ssh_lines(self) -> None:
        stdout = "\n".join(
            [
                "+ wlp2s0 IPv4 maixcam2-4ea6 [38:7a:cc:92:15:f8] Workstation local",
                "+ wlp2s0 IPv4 maixcam-1f58 [38:7a:cc:94:3c:5c] Workstation local",
                "+ wlp2s0 IPv4 maixcam2-4ea6 SSH SSH Remote Terminal local",
            ]
        )

        devices = discover._parse_avahi_text(stdout)

        self.assertEqual(
            devices,
            [
                discover.DiscoveredDevice(
                    host="maixcam-1f58.local",
                    name="maixcam-1f58",
                    device_class="maixcam-pro",
                ),
                discover.DiscoveredDevice(
                    host="maixcam2-4ea6.local",
                    name="maixcam2-4ea6",
                    device_class="maixcam2",
                ),
            ],
        )

    def test_parse_avahi_text_prefers_resolved_address(self) -> None:
        stdout = "\n".join(
            [
                "= wlp2s0 IPv4 maixcam2-4ea6 SSH SSH Remote Terminal local",
                "   hostname = [maixcam2-4ea6.local]",
                "   address = [192.168.10.42]",
                "   port = [22]",
            ]
        )

        devices = discover._parse_avahi_text(stdout)

        self.assertEqual(
            devices,
            [
                discover.DiscoveredDevice(
                    host="192.168.10.42",
                    name="maixcam2-4ea6",
                    device_class="maixcam2",
                )
            ],
        )

    def test_parse_avahi_parseable_resolved_line(self) -> None:
        stdout = (
            "=;wlp2s0;IPv4;maixcam2-4ea6 SSH;_ssh._tcp;local;"
            "maixcam2-4ea6.local;192.168.10.42;22;"
        )

        devices = discover._parse_avahi_parseable(stdout)

        self.assertEqual(
            devices,
            [
                discover.DiscoveredDevice(
                    host="192.168.10.42",
                    name="maixcam2-4ea6",
                    device_class="maixcam2",
                )
            ],
        )

    def test_scan_uses_partial_avahi_stdout_after_timeout(self) -> None:
        partial_stdout = (
            "+;wlp2s0;IPv4;maixcam-1f58\\032\\09138\\0587a\\058cc\\05894\\0583c\\0585c\\093;"
            "Workstation;local\n"
        )

        with patch(
            "scripts.maixpy_skill.discover.subprocess.run",
            side_effect=subprocess.TimeoutExpired(
                ["avahi-browse", "-a", "-p", "-t"],
                timeout=4,
                output=partial_stdout,
            ),
        ):
            devices = discover._scan_with_avahi(timeout=4)

        self.assertEqual(
            devices,
            [
                discover.DiscoveredDevice(
                    host="maixcam-1f58.local",
                    name="maixcam-1f58",
                    device_class="maixcam-pro",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
