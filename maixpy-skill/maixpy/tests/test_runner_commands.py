import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.maixpy_skill.config import Device
from scripts.maixpy_skill.runner import collect_remote_log_command, remote_run_command, run_file
from scripts.maixpy_skill.ssh import CommandResult


class RunnerCommandTests(unittest.TestCase):
    def test_remote_run_exports_run_dir_and_uses_timeout_when_available(self) -> None:
        command = remote_run_command("run-1", 60)
        self.assertIn("export MAIXPY_SKILL_RUN_DIR='/tmp/maixpy_skill/run-1'", command)
        self.assertIn("export MAIXPY_DEBUG_IMAGES='0'", command)
        self.assertIn("command -v timeout", command)
        self.assertIn("main.py", command)

    def test_remote_run_can_enable_debug_images(self) -> None:
        command = remote_run_command("run-1", 60, debug_images=True)
        self.assertIn("export MAIXPY_DEBUG_IMAGES='1'", command)

    def test_collect_command_finds_images(self) -> None:
        command = collect_remote_log_command("run-1")
        self.assertIn("/maixapp/tmp/last_run.log", command)
        self.assertIn("*.jpg", command)
        self.assertIn("*.png", command)

    def test_run_file_enters_development_mode_and_stops_apps_before_run(self) -> None:
        commands: list[list[str]] = []

        def fake_run(command: list[str], *, check: bool = True, env: dict[str, str] | None = None) -> CommandResult:
            commands.append(command)
            return CommandResult(0, "ok\n", "")

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "main.py"
            source.write_text("print('hello')\n", encoding="utf-8")
            device = Device(host="maixcam2.local", user="root", device_class="maixcam2")

            with patch("scripts.maixpy_skill.runner.logs.new_run_id", return_value="run-1"):
                with patch("scripts.maixpy_skill.runner._run_local", side_effect=fake_run):
                    with patch("scripts.maixpy_skill.runner._pull_optional"):
                        with patch("scripts.maixpy_skill.runner._pull_artifacts"):
                            out_dir = run_file(device, source, cwd=root)

            self.assertTrue((out_dir / "development-mode.log").exists())
            self.assertTrue((out_dir / "maixapp-stop.log").exists())

        self.assertIn("development_mode=entered", commands[0][-1])
        self.assertIn("display_refreshed=ok", commands[0][-1])
        self.assertIn("/maixapp/apps/", commands[1][-1])
        self.assertIn("maixapp_apps=stopped", commands[1][-1])
        self.assertIn("mkdir -p", commands[2][-1])
        self.assertIn("/tmp/maixpy_skill/run-1", commands[2][-1])
        self.assertIn("artifacts", commands[2][-1])


if __name__ == "__main__":
    unittest.main()
