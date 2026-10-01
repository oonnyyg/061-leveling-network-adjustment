# levelnet — 水准网加权最小二乘平差

仅依赖 Python 3.12+ 标准库，单位统一为米。

## 用法

```bash
python -m levelnet \
  --observations observations.csv \
  --controls controls.json \
  --points-out points.csv \
  --residuals-out residuals.csv \
  --summary-out summary.json
```

## 输入

观测 CSV 表头必须包含 `id,from,to,delta_h,std_dev`：

- `delta_h` 为终点高程减起点高程；同一对点允许重复测量。
- `id` 必须唯一；`from` 与 `to` 不得相同；`std_dev` 必须为正。
- 所有数值必须有限，错误信息会注明文件与行号。

控制点 JSON 为名称到高程的映射。控制点必须出现在观测中；
每个无向连通分量至少含一个控制点，否则报错。

## 输出

- 点位 CSV：按名称排序，含高程、标准差（控制点为 0）与类型。
- 残差 CSV：按观测编号排序，含估计高差、残差（估计 − 观测）
  及残差除以原观测标准差。
- 汇总 JSON：观测数、未知点数、控制点数、自由度、
  加权残差平方和（WRSS）。不做后验方差缩放。

自由度 = 观测数 − 未知点数；全部点位均为控制点时自由度等于观测数。
结果与输入行序无关。法矩阵采用 Cholesky 分解，近似奇异时
给出涉及点位的明确诊断。任何失败都不会留下部分输出文件。

## 示例

- `examples/closed_loop`：单控制点闭合水准回路。
- `examples/conflicting_controls`：两端控制点与观测链路存在冲突。

## 测试

```bash
python -m unittest discover -s tests
```
