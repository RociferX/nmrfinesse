# 快速开始

本页介绍 1.0.11 的安装与首次处理。Linux 桌面用户可从 [1.0.11 Release](https://github.com/RociferX/nmrfinesse/releases/tag/v1.0.11) 下载 AppImage；源码安装见下方步骤。公开 API 版本为 v1.1.5。

## 路线 A —— 源码安装与 GUI

```bash
git clone https://github.com/RociferX/nmrfinesse.git
cd nmrfinesse
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -e ".[test]"
python main.py
```

真实处理需要在同一台机器上安装 NMRPipe;SMILE 随它提供。NMRFinesse 不捆绑、也不下载这两个
引擎。如果它们不在,数据检查仍然可用,程序会明确报出处理能力不可用。

第一次打开程序,先看 **`帮助 → 使用教程`**:一份从导入数据走到峰表的完整走查,界面语言换了正文也跟着换。

## 路线 B —— 开发者:不装 NMRPipe 也能检查数据集

这一步全用纯 Python:Bruker 参数解析、维度判定、实验判定、采样判定,以及读取时域数据。
不需要安装 NMRPipe。

```bash
git clone <this repository>
cd nmrfinesse
pip install -e ".[test]"
```

造一个小合成数据集(文件头加一段合成 FID,明确标注不是真实数据),
或者把走查脚本指向你自己的某个 Bruker 数据集目录:

```bash
python examples/make_synthetic_dataset.py --out example_data/hsqc_2d
python examples/quickstart.py example_data/hsqc_2d
```

走查脚本会按顺序打印:

1. 找到了哪些参数文件(`acqus`/`acqu2s`/`acqu3s`);
2. 维度数,以及逐维的核、角色、TD 与扫宽;
3. 判定出的实验类型及依据;
4. 采样判定(uniform / NUS / uncertain)及依据;
5. 后端将使用的时域存储布局;
6. 是否找到 NMRPipe 与 SMILE,以及接下来该跑的确切命令。

如果第 6 步报「NMRPipe NOT FOUND」,那么处理暂时不可用 —— 但数据理解与 QC 仍然可用。
这条边界是有意为之:NMRFinesse 拒绝假装自己能在没有引擎的情况下处理。
想看维度处理与 NUS 判定,可以试 3D 例子:

```bash
python examples/make_synthetic_dataset.py --out example_data/hnca_3d --ndim 3 --nuclei 13C,15N,1H --nus
python examples/quickstart.py example_data/hnca_3d
```

## 配置 NMRPipe

后端按这个顺序查找 NMRPipe(`backend/nmrpipe_finder.py`):

1. 配置里的 `backend.nmrpipe.path`(一个目录或一个可执行文件);
2. `backend.nmrpipe.nmrpipe_bin`;
3. `PATH`;
4. `csh` 环境,也就是终端 source 过 NMRPipe 环境之后的样子;
5. 常见安装位置。

`nmrfinesse_data/config/nmrfinesse.yaml` 保存默认值;要做机器本地覆盖,就把它复制成
`nmrfinesse_data/config/nmrfinesse.local.yaml`(该文件被 git 忽略,因此机器路径永远不会进仓库):

```yaml
backend:
  nmrpipe:
    path: /opt/NMRPipe/nmrbin.linux212_64
```

## 跑处理路径

开发者可以在命令行驱动同一套引擎;完整参考见
[external-api/04-cli-reference.md](external-api/04-cli-reference.md):

```bash
python -m nmrfinesse_api init      --study ./study --dataset /path/to/bruker/dataset
python -m nmrfinesse_api reference --study ./study
python -m nmrfinesse_api peaks     --study ./study
python -m nmrfinesse_api sweep     --study ./study --grid grid.yaml --reference study/reference.json
```

一个「study」是一个自包含的根目录。参考谱、它的脚本与峰表只冻结一次;
此后参数组合都以该参考为基准评估,每个组合各自保留自己的脚本、候选谱、峰表、运行记录与告警。

## 结果在哪里

- [external-api/06-outputs-and-records.md](external-api/06-outputs-and-records.md) ——
  研究目录布局:`manifest.json`、`runs.json`、`peak_positions.csv`、`uncertainty.csv`、
  逐运行的脚本与谱图。
- [qc-system.md](qc-system.md) —— 质量指标的含义,以及怎么读报告。
- [processing-model.md](processing-model.md) —— 处理方案是怎么构建出来的。

## 当前源码界面

`帮助 → 使用教程` 提供九个分区的可点击目录；主分区与操作小节有独立标题层级。
实验页上方横排单个、分段和批量三个导入区，按钮在上、说明在下，样品数据表在导入区下面。
批量导入的“导入并成组”默认关闭；批量处理限 2D，3D 请单独处理。
UCSF 复制入口在 `工具 → 导出 UCSF 文件…`，打开项目后可用；目标目录可在设置中自动寻找或手动指定。
`工具` 也提供只读 FID 诊断，以及 2D/3D 均匀采样异常 FID 的自动检测、手动勾选和 NUS 副本导出。
后者保留输入目录，删除完整采样点的相位组，在新目录写入采样表与转换报告。

窗口默认以 1080p 工作区为基准、窗口化打开；小屏使用滚动条，大屏保持基准窗口。
自动字号在最大化/全屏时调整，普通拖动窗口大小不改变字号。
1D 默认 Aspect 为 0.02；2D/3D 的 1D 切片需按住左键移动，顶部与右侧切片独立调相。
比对十字线按显示 ppm 联动，重叠比对保留等高线配置；文件和颜色悬浮提示包含 title。
待更新状态会给出缺失路径或变化文件；旧记录证据不足时会说明无法细分原因。
拾取峰表和导入峰表可切换、各自保留指认；CSV 用于完整恢复，GUI 的 `.list` 只导出指认和坐标。

这些说明对应当前源码。现有 v1.0.11 AppImage 不会因源码更新而自动改变；本次不重建安装包。
完整操作见 [GUI 指南](gui.md)。

## 下一步

- [installation.md](installation.md) —— Linux AppImage 与源码安装两条路
- [external-dependencies.md](external-dependencies.md) —— NMRPipe/SMILE
- [troubleshooting.md](troubleshooting.md) | [faq.md](faq.md)
