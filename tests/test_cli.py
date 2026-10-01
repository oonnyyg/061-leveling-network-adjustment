import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.obs = self.dir / "obs.csv"
        self.ctrl = self.dir / "ctrl.json"
        self.points = self.dir / "points.csv"
        self.residuals = self.dir / "residuals.csv"
        self.summary = self.dir / "summary.json"
        self.obs.write_text(
            "id,from,to,dh,sd\n"
            "o1,A,B,1.001,0.001\n"
            "o2,B,C,2.002,0.002\n"
            "o3,A,C,3.005,0.002\n",
            encoding="utf-8",
        )
        self.ctrl.write_text('{"A": 10.0}', encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "levelnet",
                "-o",
                str(self.obs),
                "-c",
                str(self.ctrl),
                "--points-out",
                str(self.points),
                "--residuals-out",
                str(self.residuals),
                "--summary-out",
                str(self.summary),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

    def test_success_outputs(self) -> None:
        proc = self._run()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.points.exists())
        self.assertTrue(self.residuals.exists())
        summary = json.loads(self.summary.read_text(encoding="utf-8"))
        self.assertEqual(summary["n_observations"], 3)
        self.assertEqual(summary["n_unknown_points"], 2)
        self.assertEqual(summary["degrees_of_freedom"], 1)
        self.assertEqual(summary["units"], "meter")

    def test_error_leaves_no_partial_output(self) -> None:
        # 重复编号导致校验失败：三个目标文件都不应存在。
        self.obs.write_text(
            "id,from,to,dh,sd\n"
            "o1,A,B,1,0.01\n"
            "o1,B,C,1,0.01\n",
            encoding="utf-8",
        )
        proc = self._run()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("重复", proc.stderr)
        self.assertFalse(self.points.exists())
        self.assertFalse(self.residuals.exists())
        self.assertFalse(self.summary.exists())

    def test_missing_control_component_error(self) -> None:
        self.obs.write_text(
            "id,from,to,dh,sd\n"
            "o1,A,B,1,0.01\n"
            "o2,C,D,1,0.01\n",
            encoding="utf-8",
        )
        proc = self._run()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("连通分量", proc.stderr)
        self.assertFalse(self.points.exists())


if __name__ == "__main__":
    unittest.main()
