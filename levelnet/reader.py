"""CSV 观测与 JSON 控制点的读取和校验。"""

import csv
import json
import math

from .errors import InputError
from .models import NetworkInput, Observation

REQUIRED_COLUMNS = ("id", "from", "to", "delta_h", "std_dev")


def _parse_float(value: str, what: str, where: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise InputError(f"{where}: {what} 不是合法数字: {value!r}") from None
    if not math.isfinite(number):
        raise InputError(f"{where}: {what} 必须为有限数值, 得到 {value!r}")
    return number


def read_observations(path: str) -> tuple[Observation, ...]:
    try:
        handle = open(path, "r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise InputError(f"无法打开观测文件 {path}: {exc}") from None
    with handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise InputError(f"观测文件 {path} 为空或缺少表头")
        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise InputError(
                f"观测文件 {path} 表头缺少列: {', '.join(missing)}"
            )

        observations: list[Observation] = []
        seen_ids: set[str] = set()
        for line_no, raw in enumerate(reader, start=2):
            where = f"观测文件 {path} 第 {line_no} 行"
            values = {
                c: (raw.get(c) or "").strip() for c in REQUIRED_COLUMNS
            }
            for c in REQUIRED_COLUMNS:
                if not values[c]:
                    raise InputError(f"{where}: 列 {c!r} 为空")
            obs_id = values["id"]
            if obs_id in seen_ids:
                raise InputError(f"{where}: 观测编号 {obs_id!r} 重复")
            seen_ids.add(obs_id)
            from_point = values["from"]
            to_point = values["to"]
            if from_point == to_point:
                raise InputError(
                    f"{where}: 观测 {obs_id!r} 起点与终点相同 ({from_point!r})"
                )
            delta_h = _parse_float(values["delta_h"], "高差 delta_h", where)
            std_dev = _parse_float(values["std_dev"], "标准差 std_dev", where)
            if std_dev <= 0.0:
                raise InputError(
                    f"{where}: 观测 {obs_id!r} 标准差必须为正, 得到 {std_dev}"
                )
            observations.append(
                Observation(
                    obs_id=obs_id,
                    from_point=from_point,
                    to_point=to_point,
                    delta_h=delta_h,
                    std_dev=std_dev,
                    row=line_no,
                )
            )

    if not observations:
        raise InputError(f"观测文件 {path} 中没有任何观测")
    return tuple(observations)


def read_controls(path: str) -> dict[str, float]:
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except OSError as exc:
        raise InputError(f"无法打开控制点文件 {path}: {exc}") from None
    except json.JSONDecodeError as exc:
        raise InputError(
            f"控制点文件 {path} 不是合法 JSON (第 {exc.lineno} 行"
            f"第 {exc.colno} 列): {exc.msg}"
        ) from None

    if not isinstance(data, dict):
        raise InputError(f"控制点文件 {path}: 顶层必须为名称到高程的 JSON 对象")

    controls: dict[str, float] = {}
    for name, raw_h in data.items():
        where = f"控制点文件 {path} 控制点 {name!r}"
        if not isinstance(name, str) or not name:
            raise InputError(f"{where}: 控制点名称必须为非空字符串")
        if isinstance(raw_h, bool) or not isinstance(raw_h, (int, float)):
            raise InputError(f"{where}: 高程必须为数字, 得到 {raw_h!r}")
        height = float(raw_h)
        if not math.isfinite(height):
            raise InputError(f"{where}: 高程必须为有限数值, 得到 {raw_h!r}")
        controls[name] = height

    if not controls:
        raise InputError(f"控制点文件 {path} 中没有任何控制点")
    return controls


def read_network(obs_path: str, control_path: str) -> NetworkInput:
    observations = read_observations(obs_path)
    controls = read_controls(control_path)

    observed: set[str] = set()
    for obs in observations:
        observed.add(obs.from_point)
        observed.add(obs.to_point)
    for name in sorted(controls):
        if name not in observed:
            raise InputError(
                f"控制点 {name!r} 未出现在任何观测中, 无法约束该点"
            )
    return NetworkInput(observations=observations, controls=controls)
