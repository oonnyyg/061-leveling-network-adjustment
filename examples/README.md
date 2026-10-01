# levelnet 示例

所有高程与高差单位均为米。运行：

```powershell
python -m levelnet `
  -o examples/closed_loop/observations.csv `
  -c examples/closed_loop/controls.json `
  --points-out out/points.csv `
  --residuals-out out/residuals.csv `
  --summary-out out/summary.json
```

## closed_loop（闭合回路）

两个已知水准点 `BM1=100.000`、`BM2=102.880` 之间有多条水准路线，
构成多个闭合环。观测含微小闭合差，平差后残差按权重分配，
`summary.json` 给出加权残差平方和与自由度（观测数减未知点数）。

## conflicting_controls（冲突控制点）

控制点高程是硬约束。本例 `BM1=50.0` 与 `BM2=60.5` 隐含高差
10.5 m，而直接观测只有约 10.010 m，互相矛盾。
程序不会拒绝该输入，而是让矛盾暴露在残差中：
残差 `residual_m` 与标准化残差 `residual_over_sd` 显著偏大
（绝对值远超 3），据此可核查控制点或观测是否存在粗差。

## 输入错误会被直接拒绝

例如：编号重复、起终点相同、标准差非正、数值非有限、
某连通分量没有控制点、控制点未出现在任何观测中等，
均会输出带文件名与行号的错误信息且不生成输出文件。
