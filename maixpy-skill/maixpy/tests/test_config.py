from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.maixpy_skill.config import ConfigError, get_device, normalize_device_class, save_config, set_device


class ConfigTests(unittest.TestCase):
    def test_normalizes_maixcam_to_pro_class(self) -> None:
        self.assertEqual(normalize_device_class("maixcam"), "maixcam-pro")
        self.assertEqual(normalize_device_class("maixcam pro"), "maixcam-pro")
        self.assertEqual(normalize_device_class("maixcam_pro"), "maixcam-pro")
        self.assertEqual(normalize_device_class("maixcam2"), "maixcam2")

    def test_set_device_stores_no_password(self) -> None:
        with TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            set_device("192.168.1.2", "root", device_class="maixcam", cwd=cwd)
            device = get_device(cwd=cwd)
            self.assertEqual(device.host, "192.168.1.2")
            self.assertEqual(device.user, "root")
            self.assertEqual(device.device_class, "maixcam-pro")
            self.assertNotIn("password", (cwd / ".maixpy" / "config.json").read_text())

    def test_rejects_secret_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ConfigError):
                save_config({"devices": {"default": {"host": "x", "password": "nope"}}}, Path(tmp))

    def test_get_device_merges_password_from_skill_credentials(self) -> None:
        with TemporaryDirectory() as tmp:
            cwd = Path(tmp) / "project"
            (cwd / ".maixpy").mkdir(parents=True)
            (cwd / ".maixpy" / "device_credentials.local.json").write_text(
                '{"devices": {"default": {"password": "local-secret"}}}',
                encoding="utf-8",
            )

            set_device("192.168.1.2", "root", device_class="maixcam", cwd=cwd)
            device = get_device(cwd=cwd)

            self.assertEqual(device.password, "local-secret")
            self.assertNotIn("password", device.public_dict())


if __name__ == "__main__":
    unittest.main()
