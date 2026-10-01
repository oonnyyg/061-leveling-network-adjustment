"""加权最小二乘平差核心。"""

from dataclasses import dataclass

from .errors import InputError
from .linalg import cholesky_solve_inverse
from .models import NetworkInput, Observation
from .network import check_components


@dataclass(frozen=True)
class PointResult:
    name: str
    height: float
    std_dev: float
    is_control: bool


@dataclass(frozen=True)
class ResidualResult:
    obs_id: str
    from_point: str
    to_point: str
    observed: float
    estimated: float
    residual: float
    std_dev: float
    normalized_residual: float


@dataclass(frozen=True)
class AdjustmentResult:
    points: tuple[PointResult, ...]
    residuals: tuple[ResidualResult, ...]
    wrss: float
    degrees_of_freedom: int
    observation_count: int
    unknown_count: int
    control_count: int


def adjust(net: NetworkInput) -> AdjustmentResult:
    check_components(net)

    observed_points: set[str] = set()
    for obs in net.observations:
        observed_points.add(obs.from_point)
        observed_points.add(obs.to_point)

    unknowns = sorted(observed_points - set(net.controls))
    index = {name: i for i, name in enumerate(unknowns)}
    n_unknown = len(unknowns)
    n_obs = len(net.observations)

    normal = [[0.0] * n_unknown for _ in range(n_unknown)]
    rhs = [0.0] * n_unknown

    for obs in net.observations:
        weight = 1.0 / (obs.std_dev * obs.std_dev)
        f_idx = index.get(obs.from_point)
        t_idx = index.get(obs.to_point)
        fixed_h = (
            net.controls.get(obs.from_point, 0.0)
            if f_idx is None
            else 0.0
        )
        if t_idx is None:
            fixed_h -= net.controls[obs.to_point]

        # l = 观测高差 - (固定终点 - 固定起点)
        l_value = obs.delta_h + fixed_h

        if f_idx is not None:
            normal[f_idx][f_idx] += weight
            rhs[f_idx] -= weight * l_value
        if t_idx is not None:
            normal[t_idx][t_idx] += weight
            rhs[t_idx] += weight * l_value
        if f_idx is not None and t_idx is not None:
            normal[f_idx][t_idx] -= weight
            normal[t_idx][f_idx] -= weight

    inverse = cholesky_solve_inverse(normal, unknowns)
    corrections = [0.0] * n_unknown
    for i in range(n_unknown):
        total = 0.0
        for j in range(n_unknown):
            total += inverse[i][j] * rhs[j]
        corrections[i] = total

    heights: dict[str, float] = dict(net.controls)
    for i, name in enumerate(unknowns):
        heights[name] = corrections[i]

    point_results: list[PointResult] = []
    for name in sorted(observed_points):
        is_control = name in net.controls
        if is_control:
            std_dev = 0.0
        else:
            i = index[name]
            std_dev = inverse[i][i] ** 0.5
        point_results.append(
            PointResult(name, heights[name], std_dev, is_control)
        )

    residual_results: list[ResidualResult] = []
    wrss = 0.0
    for obs in net.observations:
        estimated = heights[obs.to_point] - heights[obs.from_point]
        residual = estimated - obs.delta_h
        normalized = residual / obs.std_dev
        wrss += (residual / obs.std_dev) ** 2
        residual_results.append(
            ResidualResult(
                obs.obs_id,
                obs.from_point,
                obs.to_point,
                obs.delta_h,
                estimated,
                residual,
                obs.std_dev,
                normalized,
            )
        )
    residual_results.sort(key=lambda r: r.obs_id)

    dof = n_obs - n_unknown
    if dof < 0:
        raise InputError(
            f"观测数 ({n_obs}) 少于未知点数 ({n_unknown}), 自由度为负"
        )

    return AdjustmentResult(
        points=tuple(point_results),
        residuals=tuple(residual_results),
        wrss=wrss,
        degrees_of_freedom=dof,
        observation_count=n_obs,
        unknown_count=n_unknown,
        control_count=len(net.controls),
    )
