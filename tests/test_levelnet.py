"""levelnet 标准库 unittest 测试。"""

import csv
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from levelnet.__main__ import main  # noqa: E402
from levelnet.adjustment import adjust  # noqa: E402
from levelnet.errors import InputError  # noqa: E402
from levelnet.reader import read_network  # noqa: E402


EXAMPLES = os.path.join(ROOT, "examples")


def load_example(name: str):
    return read_network(
        os.path.join(EXAMPLES, name, "observations.csv"),
        os.path.join(EXAMPLES, name, "controls.json"),
    )


class ClosedLoopTests(unittest.TestCase):
    def test_closed_loop(self):
        result = adjust(load_example("closed_loop"))
        by_name = {p.name: p for p in result.points}
        self.assertEqual(by_name["A"].height, 10.0)
        self.assertEqual(by_name["A"].std_dev, 0.0)
        # 法方程: 未知点改正数加权残差正交
        heights = {p.name: p.height for p in result.points}
        net = load_example("closed_loop")
        for name in ("B", "C"):
            total = 0.0
            for obs in net.observations:
                est = heights[obs.to_point] - heights[obs.from_point]
                v = est - obs.delta_h
                w = 1.0 / obs.std_dev ** 2
                sign = 0.0
                if obs.to_point == name:
                    sign = 1.0
                elif obs.from_point == name:
                    sign = -1.0
                total += sign * w * v
            self.assertLess(abs(total), 1e-9)
        # 自由度 = 4 观测 - 2 未知
        self.assertEqual(result.degrees_of_freedom, 2)
        # 点位按名称排序
        self.assertEqual(
            [p.name for p in result.points], sorted(p.name for p in result.points)
        )

    def test_unknown_std_single_point(self):
        # 单未知点 B, 由 A->B 两次重复测量加权平均
        with tempfile.TemporaryDirectory() as tmp:
            obs_p = os.path.join(tmp, "o.csv")
            ctl_p = os.path.join(tmp, "c.json")
            with open(obs_p, "w", encoding="utf-8", newline="") as f:
                f.write("id,from,to,delta_h,std_dev\n")
                f.write("X1,A,B,2.0,0.004\n")
                f.write("X2,A,B,2.1,0.003\n")
            with open(ctl_p, "w", encoding="utf-8") as f:
                json.dump({"A": 5.0}, f)
            result = adjust(read_network(obs_p, ctl_p))
        w1, w2 = 1 / 0.004**2, 1 / 0.003**2
        expected_h = 5.0 + (2.0 * w1 + 2.1 * w2) / (w1 + w2)
        expected_std = 1 / math.sqrt(w1 + w2)
        b = next(p for p in result.points if p.name == "B")
        self.assertLess(abs(b.height - expected_h), 1e-10)
        self.assertLess(abs(b.std_dev - expected_std), 1e-12)


class ConflictingControlsTests(unittest.TestCase):
    def test_conflicting_controls_nonzero_residuals(self):
        result = adjust(load_example("conflicting_controls"))
        # A=10, D=12 固定, 但观测链路给出约 1.995 与 2.010, 必有残差
        self.assertGreater(result.wrss, 0.0)
        by_id = {r.obs_id: r for r in result.residuals}
        # 残差定义 = 估计高差 - 观测高差
        for r in result.residuals:
            self.assertLess(
                abs(r.residual - (r.estimated - r.observed)), 1e-12
            )
            self.assertLess(
                abs(r.normalized_residual - r.residual / r.std_dev), 1e-12
            )
        self.assertEqual(by_id["M1"].residual, by_id["M1"].estimated - 1.005)
        self.assertEqual(result.degrees_of_freedom, 2)  # 3 观测 - 1 未知


class OrderIndependenceTests(unittest.TestCase):
    def test_shuffled_rows_same_result(self):
        net = load_example("closed_loop")
        r1 = adjust(net)
        import random

        obs = list(net.observations)
        random.Random(42).shuffle(obs)
        from levelnet.models import NetworkInput

        r2 = adjust(NetworkInput(tuple(obs), dict(net.controls)))
        for p1, p2 in zip(r1.points, r2.points):
            self.assertEqual(p1.name, p2.name)
            self.assertLess(abs(p1.height - p2.height), 1e-12)
            self.assertLess(abs(p1.std_dev - p2.std_dev), 1e-12)
        ids1 = [r.obs_id for r in r1.residuals]
        ids2 = [r.obs_id for r in r2.residuals]
        self.assertEqual(ids1, ids2)
        self.assertEqual(ids1, sorted(ids1))
        for a, b in zip(r1.residuals, r2.residuals):
            self.assertLess(abs(a.residual - b.residual), 1e-12)
        self.assertLess(abs(r1.wrss - r2.wrss), 1e-12)


class AllControlsTests(unittest.TestCase):
    def test_all_control_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_p = os.path.join(tmp, "o.csv")
            ctl_p = os.path.join(tmp, "c.json")
            with open(obs_p, "w", encoding="utf-8", newline="") as f:
                f.write("id,from,to,delta_h,std_dev\n")
                f.write("K1,A,B,1.01,0.01\n")
                f.write("K2,B,A,-0.98,0.02\n")
            with open(ctl_p, "w", encoding="utf-8") as f:
                json.dump({"A": 0.0, "B": 1.0}, f)
            result = adjust(read_network(obs_p, ctl_p))
        self.assertEqual(result.unknown_count, 0)
        self.assertEqual(result.degrees_of_freedom, 2)
        self.assertTrue(all(p.std_dev == 0.0 for p in result.points))
        r = {x.obs_id: x for x in result.residuals}
        self.assertLess(abs(r["K1"].residual - (-0.01)), 1e-12)
        self.assertLess(abs(r["K2"].residual - (-0.02)), 1e-12)


class InputValidationTests(unittest.TestCase):
    def _make(self, tmp, obs_text, controls='{"A": 0.0}'):
        obs_p = os.path.join(tmp, "o.csv")
        ctl_p = os.path.join(tmp, "c.json")
        with open(obs_p, "w", encoding="utf-8", newline="") as f:
            f.write(obs_text)
        with open(ctl_p, "w", encoding="utf-8") as f:
            f.write(controls)
        return obs_p, ctl_p

    def test_duplicate_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_p, ctl_p = self._make(
                tmp,
                "id,from,to,delta_h,std_dev\n"
                "D1,A,B,1,0.01\nD1,B,C,1,0.01\n",
                '{"A": 0, "C": 2}',
            )
            with self.assertRaisesRegex(InputError, "第 3 行"):
                read_network(obs_p, ctl_p)

    def test_same_endpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_p, ctl_p = self._make(
                tmp,
                "id,from,to,delta_h,std_dev\nD1,A,A,1,0.01\n",
            )
            with self.assertRaisesRegex(InputError, "起点与终点相同"):
                read_network(obs_p, ctl_p)

    def test_nonpositive_std(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_p, ctl_p = self._make(
                tmp,
                "id,from,to,delta_h,std_dev\nD1,A,B,1,0\n",
            )
            with self.assertRaisesRegex(InputError, "标准差必须为正"):
                read_network(obs_p, ctl_p)

    def test_non_finite(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_p, ctl_p = self._make(
                tmp,
                "id,from,to,delta_h,std_dev\nD1,A,B,nan,0.01\n",
            )
            with self.assertRaisesRegex(InputError, "有限数值"):
                read_network(obs_p, ctl_p)

    def test_component_without_control(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_p, ctl_p = self._make(
                tmp,
                "id,from,to,delta_h,std_dev\n"
                "D1,A,B,1,0.01\nD2,C,D,1,0.01\n",
            )
            with self.assertRaisesRegex(InputError, "连通分量"):
                adjust(read_network(obs_p, ctl_p))

    def test_control_not_observed(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_p, ctl_p = self._make(
                tmp,
                "id,from,to,delta_h,std_dev\nD1,A,B,1,0.01\n",
                '{"A": 0, "Z": 9}',
            )
            with self.assertRaisesRegex(InputError, "未出现在任何观测"):
                read_network(obs_p, ctl_p)

    def test_missing_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_p, ctl_p = self._make(
                tmp, "id,from,to,delta_h\nD1,A,B,1\n"
            )
            with self.assertRaisesRegex(InputError, "std_dev"):
                read_network(obs_p, ctl_p)


class CliAndAtomicityTests(unittest.TestCase):
    def test_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            p_out = os.path.join(tmp, "points.csv")
            r_out = os.path.join(tmp, "residuals.csv")
            s_out = os.path.join(tmp, "summary.json")
            code = main([
                "-o", os.path.join(EXAMPLES, "closed_loop", "observations.csv"),
                "-c", os.path.join(EXAMPLES, "closed_loop", "controls.json"),
                "--points-out", p_out,
                "--residuals-out", r_out,
                "--summary-out", s_out,
            ])
            self.assertEqual(code, 0)
            with open(p_out, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 3)
            with open(s_out, encoding="utf-8") as f:
                summary = json.load(f)
            self.assertEqual(summary["observation_count"], 4)
            self.assertEqual(summary["unknown_count"], 2)
            self.assertEqual(summary["degrees_of_freedom"], 2)
            self.assertFalse(summary["posterior_scale_applied"])

    def test_failure_leaves_no_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            p_out = os.path.join(tmp, "points.csv")
            r_out = os.path.join(tmp, "residuals.csv")
            s_out = os.path.join(tmp, "summary.json")
            bad_obs = os.path.join(tmp, "bad.csv")
            ctl = os.path.join(tmp, "c.json")
            with open(bad_obs, "w", encoding="utf-8", newline="") as f:
                f.write("id,from,to,delta_h,std_dev\nD1,A,A,1,0.01\n")
            with open(ctl, "w", encoding="utf-8") as f:
                json.dump({"A": 0.0}, f)
            code = main([
                "-o", bad_obs, "-c", ctl,
                "--points-out", p_out,
                "--residuals-out", r_out,
                "--summary-out", s_out,
            ])
            self.assertEqual(code, 1)
            for path in (p_out, r_out, s_out):
                self.assertFalse(os.path.exists(path))

    def test_module_invocation(self):
        env = dict(os.environ, PYTHONPATH=ROOT)
        proc = subprocess.run(
            [sys.executable, "-m", "levelnet", "--help"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
