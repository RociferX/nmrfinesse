# NMRFinesse 实测证据

## 自动谱图处理

表中为匹配对数与参考候选峰数。三维结果按 HN、HC、NC 投影分别统计。

| 处理路径 | 候选峰匹配 | 对照图 | 统计 |
| --- | --- | --- | --- |
| 2D 均匀采样 | HN 121/126 | [谱图](../../../docs/evidence/figures/uniform2d.png) | [JSON](../../../docs/evidence/statistics/uniform2d-comparison.json) |
| 受控 2D NUS | HN 123/126 | [谱图](../../../docs/evidence/figures/nus75.png) | [JSON](../../../docs/evidence/statistics/nus75-comparison.json) |
| 3D 均匀采样 | HN 82/84、HC 74/81、NC 65/71 | [投影](../../../docs/evidence/figures/uniform3d.png) | [JSON](../../../docs/evidence/statistics/uniform3d-comparison.json) |
| 实采 3D NUS | HN 89/89、HC 93/93、NC 79/79 | [投影](../../../docs/evidence/figures/acquired3d.png) | [JSON](../../../docs/evidence/statistics/acquired3d-comparison.json) |

[处理参数与脚本](../../../docs/evidence/statistics/processing.json) · [未匹配候选核查](../../../docs/evidence/statistics/local-response-audit.json)

## 与 POKY/iPick 的选峰结果对照

NMRFinesse 与 POKY/iPick 的 UCSFtool 路径都采用阈值筛选、邻域局部极大值检测和逐轴三点抛物线定位。使用等效阈值比较二维正峰时，24 张峰表的候选数全部一致，5,175 条候选记录均在每轴一个网格步内唯一配对。坐标差典型值约为 0.00025 ppm，最大约为 0.00050 ppm。

[峰表统计](../../../docs/evidence/ipick/table_comparison.csv) · [候选峰配对](../../../docs/evidence/ipick/candidate_pairs.csv) · [核验脚本](../../../docs/evidence/ipick/verify_tables.py)
