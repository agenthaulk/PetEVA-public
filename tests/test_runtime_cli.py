from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RuntimeCliTest(unittest.TestCase):
    def test_wrapper_enable_status_disable_run_disabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            switch_file = Path(temp_dir) / "pet-enabled.json"

            missing = run_runtime_cli("status", "--switch-file", str(switch_file))
            enabled = run_runtime_cli("enable", "--switch-file", str(switch_file))
            status = run_runtime_cli("status", "--switch-file", str(switch_file))
            disabled = run_runtime_cli("disable", "--switch-file", str(switch_file))
            stopped = run_runtime_cli(
                "run",
                "--switch-file",
                str(switch_file),
                "--backend",
                "macos",
                "--move-ms",
                "180",
                "--step-pixels",
                "12",
            )

        self.assertIn("disabled", missing.stdout)
        self.assertIn("enabled eva-02", enabled.stdout)
        self.assertIn("enabled unit=eva-02", status.stdout)
        self.assertIn("disabled eva-02", disabled.stdout)
        self.assertIn("PetEVA runtime stopped", stopped.stdout)

    def test_explicit_unit_overrides_config_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            switch_file = Path(temp_dir) / "pet-enabled.json"

            enabled = run_runtime_cli(
                "enable",
                "--switch-file",
                str(switch_file),
                "--unit",
                "eva-01",
            )
            status = run_runtime_cli("status", "--switch-file", str(switch_file))

        self.assertIn("enabled eva-01", enabled.stdout)
        self.assertIn("enabled unit=eva-01", status.stdout)


def run_runtime_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(ROOT / "scripts" / "peteva-runtime"), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


if __name__ == "__main__":
    unittest.main()
