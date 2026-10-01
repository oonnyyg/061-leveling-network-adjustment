"""levelnet 命令行入口。"""

from __future__ import annotations

import argparse
import sys

from .adjust import adjust
from .errors import LevelNetError
from .model import read_control_points, read_observations
from .report import write_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="levelnet",
        description=(
            "水准网加权最小二乘平差：将带误差的高差观测协调为"
            "点位高程（单位：米）。"
        ),
    )
    parser.add_argument(
        "--observations",
        "-o",
        required=True,
        help="观测 CSV：列 id, from, to, dh, sd（dh=H(to)-H(from)）",
    )
    parser.add_argument(
        "--controls",
        "-c",
        required=True,
        help="控制点 JSON：{点名: 高程米}",
    )
    parser.add_argument(
        "--points-out",
        required=True,
        help="输出点位 CSV 路径",
    )
    parser.add_argument(
        "--residuals-out",
        required=True,
        help="输出观测残差 CSV 路径",
    )
    parser.add_argument(
        "--summary-out",
        required=True,
        help="输出汇总 JSON 路径",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        observations = read_observations(args.observations)
        controls = read_control_points(args.controls)
        result = adjust(observations, controls)
        write_outputs(
            result,
            args.points_out,
            args.residuals_out,
            args.summary_out,
        )
    except LevelNetError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    print(
        f"平差完成：{result.n_observations} 条观测，"
        f"{result.n_unknown} 个未知点，"
        f"自由度 {result.degrees_of_freedom}，"
        f"加权残差平方和 {result.wrss!r}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
