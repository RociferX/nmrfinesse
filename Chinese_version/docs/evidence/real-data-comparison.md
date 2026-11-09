# NMRFinesse 实测证据

## 自动谱图处理

表中为匹配对数与参考候选峰数。三维结果按 HN、HC、NC 投影分别统计。

| 处理路径 | 候选峰匹配 | 对照图 |
| --- | --- | --- |
| 2D 均匀采样 | HN 121/126 | [谱图对照](../../../docs/evidence/figures/uniform2d.png) |
| 受控 2D NUS | HN 123/126 | [谱图对照](../../../docs/evidence/figures/nus75.png) |
| 3D 均匀采样 | HN 82/84、HC 74/81、NC 65/71 | [投影对照](../../../docs/evidence/figures/uniform3d.png) |
| 实采 3D NUS | HN 89/89、HC 93/93、NC 79/79 | [投影对照](../../../docs/evidence/figures/acquired3d.png) |

## 与 POKY/iPick 的选峰结果对照

NMRFinesse 与 POKY/iPick 的 UCSFtool 路径都采用阈值筛选、邻域局部极大值检测和逐轴三点抛物线定位。使用等效阈值比较二维正峰时，24 张峰表的候选数全部一致，5,175 条候选记录均在每轴一个网格步内唯一配对。坐标差典型值约为 0.00025 ppm，最大约为 0.00050 ppm。
