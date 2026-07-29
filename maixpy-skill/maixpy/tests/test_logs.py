import unittest
from pathlib import Path

from scripts.maixpy_skill.logs import parse_image_markers, run_dir


class LogsTests(unittest.TestCase):
    def test_parse_image_markers(self) -> None:
        stdout = "hello\nMAIXPY_SKILL_IMAGE /tmp/maixpy_skill/1/artifacts/current.jpg\n"
        self.assertEqual(parse_image_markers(stdout), ["/tmp/maixpy_skill/1/artifacts/current.jpg"])

    def test_run_dir_uses_current_maixpy_directory(self) -> None:
        self.assertEqual(run_dir("run-1", Path("/tmp/project")), Path("/tmp/project/.maixpy/runs/run-1"))


if __name__ == "__main__":
    unittest.main()
