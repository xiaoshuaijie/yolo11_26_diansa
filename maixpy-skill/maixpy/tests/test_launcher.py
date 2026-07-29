import unittest

from scripts.maixpy_skill import launcher


class LauncherCommandTests(unittest.TestCase):
    def test_stop_launcher_app_excludes_daemon(self) -> None:
        command = launcher.stop_launcher_app_command()
        self.assertIn("grep -v ' daemon'", command)
        self.assertIn("xargs -r kill", command)

    def test_ensure_maixapp_apps_stopped_detects_and_rechecks(self) -> None:
        command = launcher.ensure_maixapp_apps_stopped_command()
        self.assertIn("/maixapp/apps/", command)
        self.assertIn("maixapp_apps=running", command)
        self.assertIn("kill $pids", command)
        self.assertIn("kill -9 $pids", command)
        self.assertIn("maixapp_apps=still_running", command)
        self.assertIn("maixapp_apps=stopped", command)
        self.assertIn("awk -v self=$$", command)
        self.assertIn("$1 != self", command)
        self.assertIn("$0 !~ /launcher daemon/", command)
        self.assertIn("$0 !~ /launcher_daemon/", command)

    def test_enter_stops_daemon_and_refreshes_display(self) -> None:
        command = launcher.enter_command()
        self.assertIn("pkill -f '/maixapp/apps/launcher/launcher[_]daemon'", command)
        self.assertIn("maixapp_apps=stopped", command)
        self.assertIn("display_refreshed=ok", command)
        self.assertIn("development_mode=entered", command)
        self.assertNotIn("nohup", command)

    def test_exit_starts_daemon_in_background(self) -> None:
        command = launcher.exit_command()
        self.assertIn("nohup", command)
        self.assertIn("/maixapp/apps/launcher/launcher_daemon", command)
        self.assertIn("&", command)
        self.assertIn("development_mode=exited", command)

    def test_refresh_display_uses_display_api_not_framebuffer(self) -> None:
        command = launcher.refresh_display_command()
        self.assertIn("display.Display()", command)
        self.assertIn("disp.show(img)", command)
        self.assertNotIn("/dev/fb", command)


if __name__ == "__main__":
    unittest.main()
