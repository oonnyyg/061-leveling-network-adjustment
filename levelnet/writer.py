"""点位、残差 CSV 与汇总 JSON 的原子化输出。"""

import csv
import json
import os
import tempfile

from .adjustment import AdjustmentResult


def write_outputs(result: AdjustmentResult, points_path: str,
                  residuals_path: str, summary_path: str) -> None:
    files: list[tuple[str, object]] = [
        (points_path, "points"),
        (residuals_path, "residuals"),
        (summary_path, "summary"),
    ]
    # 先全部写入临时文件, 再一次性替换, 保证失败时不留下半份输出。
    staged: list[tuple[str, str]] = []
    try:
        for path, kind in files:
            directory = os.path.dirname(os.path.abspath(path))
            os.makedirs(directory, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                dir=directory, prefix=".levelnet-", suffix=".tmp"
            )
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                if kind == "points":
                    _write_points(handle, result)
                elif kind == "residuals":
                    _write_residuals(handle, result)
                else:
                    _write_summary(handle, result)
            staged.append((tmp_name, path))
        for tmp_name, path in staged:
            os.replace(tmp_name, path)
    except BaseException:
        for tmp_name, _path in staged:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
        raise


def _write_points(handle, result: AdjustmentResult) -> None:
    writer = csv.writer(handle)
    writer.writerow(["name", "height_m", "std_dev_m", "type"])
    for p in result.points:
        writer.writerow([
            p.name,
            repr(p.height),
            repr(p.std_dev),
            "control" if p.is_control else "unknown",
        ])


def _write_residuals(handle, result: AdjustmentResult) -> None:
    writer = csv.writer(handle)
    writer.writerow([
        "id", "from", "to", "observed_m", "estimated_m",
        "residual_m", "std_dev_m", "residual_over_std",
    ])
    for r in result.residuals:
        writer.writerow([
            r.obs_id, r.from_point, r.to_point,
            repr(r.observed), repr(r.estimated),
            repr(r.residual), repr(r.std_dev),
            repr(r.normalized_residual),
        ])


def _write_summary(handle, result: AdjustmentResult) -> None:
    summary = {
        "units": "meters",
        "observation_count": result.observation_count,
        "unknown_count": result.unknown_count,
        "control_count": result.control_count,
        "degrees_of_freedom": result.degrees_of_freedom,
        "weighted_residual_sum_of_squares": result.wrss,
        "posterior_scale_applied": False,
    }
    json.dump(summary, handle, ensure_ascii=False, indent=2, sort_keys=True)
    handle.write("\n")
