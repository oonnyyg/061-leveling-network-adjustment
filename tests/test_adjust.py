import math
import unittest

from levelnet.adjust import adjust
from levelnet.errors import LevelNetError
from levelnet.model import Observation


def obs(obs_id: str, start: str, end: str, dh: float, sd: float) -> Observation:
    return Observation(obs_id, start, end, dh, sd)


LEVELING_LOOP = [
    obs("o1", "A", "B", 1.001, 0.001),
    obs("o2", "B", "C", 2.002, 0.002),
    obs("o3", "A", "C", 3.005, 0.002),
]


class AdjustmentMathTests(unittest.TestCase):
    def test_known_loop_values(self) -> None:
        result = adjust(LEVELING_LOOP, {"A": 10.0})
        heights = {p.name: p.height for p in result.points}
        self.assertAlmostEqual(heights["A"], 10.0, places=12)
        self.assertAlmostEqual(heights["B"], 11.00122222222222, places=10)
        self.assertAlmostEqual(heights["C"], 13.00411111111111, places=10)

        by_id = {r.obs_id: r for r in result.residuals}
        self.assertAlmostEqual(by_id["o1"].residual, 0.00022222222222, places=12)
        self.assertAlmostEqual(by_id["o2"].residual, 0.00088888888889, places=12)
        self.assertAlmostEqual(by_id["o3"].residual, -0.00088888888889, places=12)
        # 标准化残差 = 残差 / 原观测标准差
        for r in result.residuals:
            self.assertAlmostEqual(
                r.standardized_residual, r.residual / r.sd, places=12
            )
        self.assertAlmostEqual(result.wrss, 0.444444444444, places=10)
        self.assertEqual(result.degrees_of_freedom, 1)

    def test_row_order_independence(self) -> None:
        shuffled = [LEVELING_LOOP[i] for i in (2, 0, 1)]
        r1 = adjust(LEVELING_LOOP, {"A": 10.0})
        r2 = adjust(shuffled, {"A": 10.0})
        self.assertEqual(
            [p.height for p in r1.points], [p.height for p in r2.points]
        )
        self.assertEqual(
            [r.residual for r in r1.residuals],
            [r.residual for r in r2.residuals],
        )
        # 观测输出始终按编号排序
        self.assertEqual(
            [r.obs_id for r in r1.residuals], ["o1", "o2", "o3"]
        )
        # 点位输出始终按名称排序
        self.assertEqual(
            [p.name for p in r1.points], sorted(p.name for p in r1.points)
        )

    def test_repeated_measurements(self) -> None:
        observations = [
            obs("r1", "A", "B", 1.000, 0.004),
            obs("r2", "A", "B", 1.004, 0.004),
            obs("r3", "A", "B", 1.002, 0.004),
        ]
        result = adjust(observations, {"A": 0.0})
        height_b = {p.name: p.height for p in result.points}["B"]
        # 等权重复测量取均值
        self.assertAlmostEqual(height_b, 1.002, places=12)
        self.assertAlmostEqual(result.wrss, 0.5, places=10)
        self.assertEqual(result.degrees_of_freedom, 2)

    def test_exact_consistent_network_zero_residuals(self) -> None:
        observations = [
            obs("e1", "A", "B", 2.0, 0.01),
            obs("e2", "B", "C", 3.0, 0.01),
            obs("e3", "A", "C", 5.0, 0.01),
        ]
        result = adjust(observations, {"A": 10.0})
        for r in result.residuals:
            self.assertEqual(r.residual, 0.0)
        self.assertEqual(result.wrss, 0.0)

    def test_all_control_points_network(self) -> None:
        observations = [
            obs("k1", "A", "B", 1.001, 0.01),
            obs("k2", "B", "C", 1.999, 0.01),
        ]
        result = adjust(observations, {"A": 0.0, "B": 1.0, "C": 3.0})
        self.assertEqual(result.n_unknown, 0)
        self.assertEqual(result.degrees_of_freedom, 2)
        self.assertTrue(all(p.is_control for p in result.points))
        self.assertTrue(all(p.sd == 0.0 for p in result.points))
        by_id = {r.obs_id: r for r in result.residuals}
        self.assertAlmostEqual(by_id["k1"].residual, -0.001, places=12)
        self.assertAlmostEqual(by_id["k2"].residual, 0.001, places=12)

    def test_standard_deviation_from_normal_matrix(self) -> None:
        # 单未知点：N = sum(1/sd^2)，sd(H) = 1/sqrt(N)
        observations = [
            obs("s1", "A", "X", 5.0, 0.02),
            obs("s2", "A", "X", 5.1, 0.05),
        ]
        result = adjust(observations, {"A": 0.0})
        point_x = next(p for p in result.points if p.name == "X")
        expected = 1.0 / math.sqrt(1.0 / 0.02**2 + 1.0 / 0.05**2)
        self.assertAlmostEqual(point_x.sd, expected, places=14)
        # 控制点标准差为零
        point_a = next(p for p in result.points if p.name == "A")
        self.assertEqual(point_a.sd, 0.0)

    def test_component_without_control(self) -> None:
        observations = [
            obs("w1", "A", "B", 1.0, 0.01),
            obs("w2", "C", "D", 1.0, 0.01),
        ]
        with self.assertRaisesRegex(LevelNetError, "连通分量"):
            adjust(observations, {"A": 0.0})

    def test_control_not_in_observations(self) -> None:
        with self.assertRaisesRegex(LevelNetError, "控制点必须出现在观测中"):
            adjust(LEVELING_LOOP, {"A": 10.0, "Z": 5.0})

    def test_two_components_each_with_control(self) -> None:
        observations = [
            obs("t1", "A", "B", 1.0, 0.01),
            obs("t2", "C", "D", 2.0, 0.02),
        ]
        result = adjust(observations, {"A": 0.0, "C": 10.0})
        heights = {p.name: p.height for p in result.points}
        self.assertAlmostEqual(heights["B"], 1.0, places=12)
        self.assertAlmostEqual(heights["D"], 12.0, places=12)
        self.assertEqual(result.degrees_of_freedom, 0)


if __name__ == "__main__":
    unittest.main()
