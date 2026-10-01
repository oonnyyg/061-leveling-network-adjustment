"""加权最小二乘水准网平差核心。

为保证结果与输入行序无关且浮点绝对误差远小于 1e-7，全部法方程
系数采用 :class:`fractions.Fraction` 精确表示并求解，输出时再转 float。
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .errors import LevelNetError
from .model import Observation


@dataclass(frozen=True)
class PointResult:
    name: str
    height: float
    sd: float
    is_control: bool


@dataclass(frozen=True)
class ResidualResult:
    obs_id: str
    start: str
    end: str
    observed_dh: float
    adjusted_dh: float
    residual: float
    sd: float
    standardized_residual: float


@dataclass(frozen=True)
class AdjustmentResult:
    points: list[PointResult]
    residuals: list[ResidualResult]
    wrss: float
    degrees_of_freedom: int
    n_observations: int
    n_points: int
    n_unknown: int
    n_control: int


def _components(
    nodes: set[str], observations: list[Observation]
) -> list[set[str]]:
    adjacency: dict[str, set[str]] = {node: set() for node in nodes}
    for obs in observations:
        adjacency[obs.start].add(obs.end)
        adjacency[obs.end].add(obs.start)
    components: list[set[str]] = []
    visited: set[str] = set()
    for root in sorted(nodes):
        if root in visited:
            continue
        stack = [root]
        component: set[str] = set()
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            component.add(node)
            stack.extend(adjacency[node] - visited)
        components.append(component)
    return components


def _solve_inverse(
    matrix: list[list[Fraction]], size: int
) -> list[list[Fraction]]:
    """高斯-若尔当消元（部分主元），返回矩阵的逆。"""
    n = size
    aug = [row[:] + [Fraction(1 if i == j else 0) for j in range(n)]
           for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(
            range(col, n),
            key=lambda r: (abs(aug[r][col]), -r),
        )
        if aug[pivot][col] == 0:
            raise LevelNetError(
                "法方程矩阵奇异：未知点高程无法唯一确定（可能存在"
                "无控制点的独立尺度自由度或退化结构）"
            )
        if pivot != col:
            aug[col], aug[pivot] = aug[pivot], aug[col]
        pivot_value = aug[col][col]
        aug[col] = [value / pivot_value for value in aug[col]]
        for row in range(n):
            if row == col:
                continue
            factor = aug[row][col]
            if factor != 0:
                aug[row] = [
                    value - factor * pivot_row_value
                    for value, pivot_row_value in zip(aug[row], aug[col])
                ]
    return [row[n:] for row in aug]


def adjust(
    observations: list[Observation], controls: dict[str, float]
) -> AdjustmentResult:
    """执行平差。

    残差定义为 估计高差 - 观测高差；权重 w = 1 / sd**2，相互独立。
    """
    observed_points = {obs.start for obs in observations}
    observed_points.update(obs.end for obs in observations)

    unused_controls = sorted(set(controls) - observed_points)
    if unused_controls:
        raise LevelNetError(
            "控制点必须出现在观测中，未被任何观测引用的控制点: "
            + ", ".join(repr(name) for name in unused_controls)
        )

    components = _components(observed_points, observations)
    for component in components:
        if not component.intersection(controls):
            names = ", ".join(sorted(component))
            raise LevelNetError(
                "每个无向连通分量都必须包含控制点，缺少控制点的连通"
                f"分量包含点位: {names}"
            )

    unknown_names = sorted(observed_points - controls.keys())
    index = {name: i for i, name in enumerate(unknown_names)}
    n = len(unknown_names)

    normal = [[Fraction(0) for _ in range(n)] for _ in range(n)]
    rhs = [Fraction(0) for _ in range(n)]
    # 同时保存每条观测的精确信息，供残差与 WRSS 计算。
    exact_obs: list[tuple[Observation, Fraction]] = []
    for obs in observations:
        dh = Fraction(obs.dh)
        sd = Fraction(obs.sd)
        weight = 1 / (sd * sd)
        exact_obs.append((obs, weight))
        # l = dh - (H_end_fixed - H_start_fixed) 形式的常数项由两端
        # 控制点贡献；统一写成 A x - l = r，逐端累加法方程。
        const = Fraction(0)
        if obs.end in controls:
            const += Fraction(controls[obs.end])
        if obs.start in controls:
            const -= Fraction(controls[obs.start])
        # 观测方程: v = s_end*H_end - s_start*H_start - dh
        #         = A x + const - dh
        coeffs: dict[int, Fraction] = {}
        if obs.end in index:
            coeffs[index[obs.end]] = Fraction(1)
        if obs.start in index:
            coeffs[index[obs.start]] = Fraction(-1)
        for i, ai in coeffs.items():
            rhs[i] += weight * ai * (dh - const)
            for j, aj in coeffs.items():
                normal[i][j] += weight * ai * aj

    if n > 0:
        # 求 N 的逆；解 x = N^-1 b 通过逆矩阵乘 b 得到，保证单一求解路径。
        inverse = _solve_inverse(normal, n)
        heights_exact = {
            name: sum(
                inverse[index[name]][j] * rhs[j] for j in range(n)
            )
            for name in unknown_names
        }
        diag = [inverse[i][i] for i in range(n)]
        if any(value <= 0 for value in diag):
            raise LevelNetError(
                "数值退化：法矩阵逆的对角元非正，高程精度无法计算"
            )
    else:
        inverse = []
        heights_exact = {}
        diag = []

    heights: dict[str, Fraction] = {
        name: Fraction(value) for name, value in controls.items()
    }
    heights.update(heights_exact)

    residuals: list[ResidualResult] = []
    wrss = Fraction(0)
    for obs, weight in exact_obs:
        adjusted = heights[obs.end] - heights[obs.start]
        residual = adjusted - Fraction(obs.dh)
        wrss += weight * residual * residual
        residuals.append(
            ResidualResult(
                obs_id=obs.obs_id,
                start=obs.start,
                end=obs.end,
                observed_dh=obs.dh,
                adjusted_dh=float(adjusted),
                residual=float(residual),
                sd=obs.sd,
                standardized_residual=float(residual / Fraction(obs.sd)),
            )
        )
    residuals.sort(key=lambda item: item.obs_id)

    point_results = [
        PointResult(
            name=name,
            height=float(heights[name]),
            sd=(
                0.0
                if name in controls
                else _sqrt_fraction(diag[index[name]])
            ),
            is_control=name in controls,
        )
        for name in sorted(observed_points)
    ]

    return AdjustmentResult(
        points=point_results,
        residuals=residuals,
        wrss=float(wrss),
        degrees_of_freedom=len(observations) - n,
        n_observations=len(observations),
        n_points=len(observed_points),
        n_unknown=n,
        n_control=len(set(controls) & observed_points),
    )


def _sqrt_fraction(value: Fraction) -> float:
    if value < 0:
        raise LevelNetError(
            "数值退化：法矩阵逆对角元为负，无法计算点位标准差"
        )
    return float(value) ** 0.5
