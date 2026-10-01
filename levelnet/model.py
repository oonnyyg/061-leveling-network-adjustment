"""观测模型、输入文件解析与数据校验。"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

from .errors import LevelNetError

REQUIRED_COLUMNS = ("id", "from", "to", "dh", "sd")


@dataclass(frozen=True)
class Observation:
    """一条有向高差观测：dh = H(to) - H(from)，单位米。"""

    obs_id: str
    start: str
    end: str
    dh: float
    sd: float


def _parse_finite_float(value: str, where: str) -> float:
    text = value.strip()
    if text == "":
        raise LevelNetError(f"{where}: 数值不能为空")
    try:
        number = float(text)
    except ValueError as exc:
        raise LevelNetError(f"{where}: 无法解析为数值 {text!r}") from exc
    if not math.isfinite(number):
        raise LevelNetError(f"{where}: 数值必须有限，得到 {text!r}")
    return number


def read_observations(path: str | Path) -> list[Observation]:
    """从 CSV 读取观测并完成单行层面的校验。"""
    path = Path(path)
    try:
        handle = open(path, "r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise LevelNetError(f"无法读取观测文件 {path}: {exc}") from exc

    observations: list[Observation] = []
    seen_ids: set[str] = set()
    with handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise LevelNetError(f"观测文件 {path}: 缺少表头")
        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise LevelNetError(
                f"观测文件 {path}: 表头缺少列 {', '.join(missing)}"
            )
        for row in reader:
            where = f"观测文件 {path} 第 {reader.line_num} 行"
            extra_cols = [
                key
                for key in row
                if key is not None and key not in reader.fieldnames
            ]
            if None in row or extra_cols:
                raise LevelNetError(f"{where}: 列数多于表头")
            obs_id = (row.get("id") or "").strip()
            start = (row.get("from") or "").strip()
            end = (row.get("to") or "").strip()
            if not obs_id:
                raise LevelNetError(f"{where}: id 不能为空")
            if not start:
                raise LevelNetError(f"{where}: from 点名为空")
            if not end:
                raise LevelNetError(f"{where}: to 点名为空")
            if obs_id in seen_ids:
                raise LevelNetError(f"{where}: 观测编号 {obs_id!r} 重复")
            seen_ids.add(obs_id)
            if start == end:
                raise LevelNetError(
                    f"{where}: 观测 {obs_id!r} 起点与终点相同（{start!r}）"
                )
            dh = _parse_finite_float(row.get("dh", ""), f"{where} 列 dh")
            sd = _parse_finite_float(row.get("sd", ""), f"{where} 列 sd")
            if sd <= 0.0:
                raise LevelNetError(
                    f"{where} 列 sd: 标准差必须为正数，得到 {sd}"
                )
            observations.append(Observation(obs_id, start, end, dh, sd))

    if not observations:
        raise LevelNetError(f"观测文件 {path}: 至少需要一条观测")
    return observations


def read_control_points(path: str | Path) -> dict[str, float]:
    """从 JSON 读取固定控制点高程 {"点名": 高程米}。"""
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise LevelNetError(f"无法读取控制点文件 {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LevelNetError(
            f"控制点文件 {path}: JSON 解析失败（第 {exc.lineno} 行"
            f"第 {exc.colno} 列）: {exc.msg}"
        ) from exc
    if not isinstance(data, dict):
        raise LevelNetError(
            f"控制点文件 {path}: 顶层必须是点名到高程的 JSON 对象"
        )
    controls: dict[str, float] = {}
    for name, value in data.items():
        if not isinstance(name, str) or not name.strip():
            raise LevelNetError(
                f"控制点文件 {path}: 点名必须是非空字符串，得到 {name!r}"
            )
        where = f"控制点文件 {path} 控制点 {name!r}"
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise LevelNetError(f"{where}: 高程必须是数值")
        number = float(value)
        if not math.isfinite(number):
            raise LevelNetError(f"{where}: 高程必须有限，得到 {value!r}")
        controls[name.strip()] = number
    if not controls:
        raise LevelNetError(f"控制点文件 {path}: 至少需要一个控制点")
    return controls
