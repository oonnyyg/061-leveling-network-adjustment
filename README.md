# leveling-network-adjustment（levelnet）

仅使用 Python 标准库的水准网加权最小二乘平差工具，把含误差的
有向高差观测协调为可核查的点位高程，统一使用米。

## 运行

```powershell
python -m levelnet `
  --observations observations.csv `
  --controls controls.json `
  --points-out points.csv `
  --residuals-out residuals.csv `
  --summary-out summary.json
```

参数也可分别简写为 `-o`、`-c`。

## 输入

观测 CSV（必须含表头，允许 BOM）：

| 列 | 含义 |
| --- | --- |
| `id` | 唯一观测编号，不可重复 |
| `from` | 起点点名 |
| `to` | 终点点名，不允许与起点相同 |
| `dh` | 观测高差 = H(to) − H(from)，米 |
| `sd` | 已知观测标准差，米，必须为正数 |

同一对点允许重复测量。所有数值必须有限。

控制点 JSON 为点名到固定高程的对象：

```json
{ "BM1": 100.0, "BM2": 102.88 }
```

## 平差约定

- 控制点高程作为硬约束保持不变（标准差输出为 0），其余点做
  加权最小二乘估计，权重 `w = 1 / sd²`，观测相互独立。
- 残差统一定义为 **估计高差 − 观测高差**，逐条输出残差及
  `residual / sd`。
- 未知点标准差取法矩阵逆矩阵对角元的平方根，**不**按残差做
  后验缩放。
- 汇总输出加权残差平方和（WRSS）；自由度 = 观测数 − 未知点数，
  支持全部点位均为控制点的网。
- 点位按名称排序、观测按编号排序；法方程以精确有理数求解，
  结果与输入行序无关。

## 校验与诊断

- 每个无向连通分量都必须包含控制点；控制点必须出现在观测中。
- 输入错误消息注明文件名、CSV 行号或 JSON 行列位置。
- 三份输出先写临时文件再原子替换，任何失败都不会留下半份输出。
- 法方程退化时给出明确的奇异性诊断。

## 示例与测试

示例见 `examples/`（闭合回路、冲突控制点）。

```powershell
python -m unittest discover -s tests
```
