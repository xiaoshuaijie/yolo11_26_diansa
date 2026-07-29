import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from scripts.maixpy_skill import cli
from scripts.maixpy_skill.config import ConfigError, Device
from scripts.maixpy_skill.discover import DiscoveredDevice
from scripts.maixpy_skill.ssh import CommandResult


class CliTests(unittest.TestCase):
    def test_device_check_without_config_prints_setup_prompt(self) -> None:
        devices = [
            DiscoveredDevice(host="maixcam2-4ea6.local", name="maixcam2-4ea6", device_class="maixcam2")
        ]

        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("scripts.maixpy_skill.cli.get_device", side_effect=ConfigError("no current device configured")):
            with patch("scripts.maixpy_skill.cli.discover.scan_candidates", return_value=devices):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = cli.main(["device", "check"])

        self.assertEqual(code, 2)
        self.assertIn("ERROR: no current device configured", stderr.getvalue())
        self.assertIn("maixcam2-4ea6", stdout.getvalue())
        self.assertIn("请输入你的设备(IP/设备名)", stdout.getvalue())
        self.assertIn("请输入你的账户名(默认为:root)", stdout.getvalue())
        self.assertIn("请输入你的密码(默认为:root)", stdout.getvalue())
        self.assertIn("请输入你的密码(默认为:sipeed)", stdout.getvalue())

    def test_device_check_success_prompts_for_feature_request(self) -> None:
        stdout = io.StringIO()
        device = Device(host="maixcam2-4ea6.local", user="root", device_class="maixcam2")
        with patch("scripts.maixpy_skill.cli.get_device", return_value=device):
            with patch(
                "scripts.maixpy_skill.cli.run_ssh",
                return_value=CommandResult(0, "connected\nLinux maixcam\n", ""),
            ):
                with redirect_stdout(stdout):
                    code = cli.main(["device", "check"])

        self.assertEqual(code, 0)
        self.assertIn("connected", stdout.getvalue())
        self.assertIn("配置完成, 请描述你的功能", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
