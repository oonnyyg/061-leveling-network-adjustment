"""平差结果输出：点位 CSV、残差 CSV 与汇总 JSON。

三个文件先各自写入同目录下的临时文件，全部成功后再原子替换，
确保任何失败都不会留下半份输出。
"""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from pathlib import Path

from .adjust import AdjustmentResult
from .errors import LevelNetError


def _format_float(value: float) -> str:
    # repr(float) 为往返最短表示，精度无损且格式稳定。
    return repr(value)


def points_csv(result: AdjustmentResult) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["name", "height_m", "sd_m", "type"])
    for point in result.points:
        writer.writerow(
            [
                point.name,
                _format_float(point.height),
                _format_float(point.sd),
                "control" if point.is_control else "unknown",
            ]
        )
    return buffer.getvalue()


def residuals_csv(result: AdjustmentResult) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [
            "id",
            "from",
            "to",
            "observed_dh_m",
            "adjusted_dh_m",
            "residual_m",
            "sd_m",
            "residual_over_sd",
        ]
    )
    for item in result.residuals:
        writer.writerow(
            [
                item.obs_id,
                item.start,
                item.end,
                _format_float(item.observed_dh),
                _format_float(item.adjusted_dh),
                _format_float(item.residual),
                _format_float(item.sd),
                _format_float(item.standardized_residual),
            ]
        )
    return buffer.getvalue()


def summary_json(result: AdjustmentResult) -> str:
    summary = {
        "units": "meter",
        "n_observations": result.n_observations,
        "n_points": result.n_points,
        "n_control_points": result.n_control,
        "n_unknown_points": result.n_unknown,
        "degrees_of_freedom": result.degrees_of_freedom,
        "weighted_residual_sum_of_squares": result.wrss,
    }
    return json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)


def write_outputs(
    result: AdjustmentResult,
    points_path: str | Path,
    residuals_path: str | Path,
    summary_path: str | Path,
) -> None:
    """原子地写入三份输出，失败时不留下任何临时或半份文件。"""
    targets = [
        (Path(points_path), points_csv(result)),
        (Path(residuals_path), residuals_csv(result)),
        (Path(summary_path), summary_json(result)),
    ]
    staged: list[tuple[Path, Path]] = []
    try:
        for target, content in targets:
            parent = target.parent if str(target.parent) else Path(".")
            parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                prefix=f".{target.name}.", suffix=".tmp", dir=str(parent)
            )
            temp_path = Path(tmp_name)
            staged.append((target, temp_path))
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                    handle.write(content)
            except OSError as exc:
                raise LevelNetError(
                    f"写入临时文件失败 {temp_path}: {exc}"
                ) from exc
        for target, temp_path in staged:
            try:
                os.replace(temp_path, target)
            except OSError as exc:
                raise LevelNetError(
                    f"无法生成输出文件 {target}: {exc}"
                ) from exc
        staged.clear()
    finally:
        for _, temp_path in staged:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
