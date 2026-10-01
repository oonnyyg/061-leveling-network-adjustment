"""python -m levelnet 命令行入口。"""

import argparse
import sys

from .adjustment import adjust
from .errors import LevelNetError
from .reader import read_network
from .writer import write_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="levelnet",
        description="水准网加权最小二乘平差 (单位: 米)",
    )
    parser.add_argument(
        "--observations", "-o", required=True,
        help="高差观测 CSV (列: id, from, to, delta_h, std_dev)",
    )
    parser.add_argument(
        "--controls", "-c", required=True,
        help="控制点高程 JSON (名称到高程的映射)",
    )
    parser.add_argument(
        "--points-out", required=True, help="点位结果 CSV 输出路径",
    )
    parser.add_argument(
        "--residuals-out", required=True, help="观测残差 CSV 输出路径",
    )
    parser.add_argument(
        "--summary-out", required=True, help="汇总 JSON 输出路径",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        net = read_network(args.observations, args.controls)
        result = adjust(net)
        write_outputs(
            result, args.points_out, args.residuals_out, args.summary_out
        )
    except LevelNetError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"错误: 文件不存在: {exc.filename}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
