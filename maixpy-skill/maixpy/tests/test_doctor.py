import unittest

from scripts.maixpy_skill import doctor


class DoctorTests(unittest.TestCase):
    def test_reports_platform_and_python_options(self) -> None:
        result = doctor.check()
        self.assertIn("platform", result)
        self.assertIn("python", result["platform"])
        self.assertIn("python", result["tools"])
        self.assertIn("py", result["tools"])
        self.assertIn("python3", result["tools"])


if __name__ == "__main__":
    unittest.main()
