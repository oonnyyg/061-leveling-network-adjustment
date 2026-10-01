"""仅依赖标准库的正定对称矩阵 Cholesky 工具。"""

import math

from .errors import LevelNetError


def cholesky_solve_inverse(
    matrix: list[list[float]], labels: list[str]
) -> list[list[float]]:
    """求正定对称矩阵的逆; 退化时抛出带点位信息的错误。

    采用 Cholesky 分解 A = L L^T, 再逐列前代/回代求逆。
    """
    n = len(matrix)
    if n == 0:
        return []

    # 用最大对角元做尺度, 判定数值退化。
    max_diag = max(matrix[i][i] for i in range(n))
    if max_diag <= 0.0 or not math.isfinite(max_diag):
        raise LevelNetError("法矩阵无效: 对角元存在非正或非有限值")
    pivot_tol = max_diag * n * 1e-15

    lower = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            total = matrix[i][j]
            for k in range(j):
                total -= lower[i][k] * lower[j][k]
            if i == j:
                diag = total
                if diag <= pivot_tol:
                    raise LevelNetError(
                        "法矩阵数值退化 (近似奇异), 无法可靠估计点位 "
                        f"{labels[i]!r} 及其相关未知点; 请检查该点是否"
                        "得到足够观测约束, 或观测标准差量级是否极端"
                    )
                lower[i][j] = math.sqrt(diag)
            else:
                lower[i][j] = total / lower[j][j]

    inverse = [[0.0] * n for _ in range(n)]
    for col in range(n):
        rhs = [0.0] * n
        rhs[col] = 1.0
        # 前代 L y = rhs
        y = [0.0] * n
        for i in range(n):
            total = rhs[i]
            for k in range(i):
                total -= lower[i][k] * y[k]
            y[i] = total / lower[i][i]
        # 回代 L^T x = y
        x = [0.0] * n
        for i in range(n - 1, -1, -1):
            total = y[i]
            for k in range(i + 1, n):
                total -= lower[k][i] * x[k]
            x[i] = total / lower[i][i]
        for i in range(n):
            inverse[i][col] = x[i]
    return inverse
