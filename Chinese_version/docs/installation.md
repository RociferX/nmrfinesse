# 安装

Linux 是目标运行平台；Windows 可用于编辑源码，但不属于支持的运行环境。Linux 桌面用户可直接使用
[NMRFinesse 1.0.10 Release](https://github.com/RociferX/nmrfinesse/releases/tag/v1.0.10) 中的 AppImage。
Python API 和命令行工具请按下方源码步骤单独安装。

## AppImage(Linux)

下载 `NMRFinesse-1.0.10-x86_64.AppImage` 与 `SHA256SUMS-v1.0.10.txt`，在同一目录校验并启动：

```bash
sha256sum -c SHA256SUMS-v1.0.10.txt
chmod +x NMRFinesse-1.0.10-x86_64.AppImage
./NMRFinesse-1.0.10-x86_64.AppImage --licenses
./NMRFinesse-1.0.10-x86_64.AppImage
```

它们捆绑 PySide6/Qt,这些库按 LGPL-3.0 随产物分发(许可与 NMRFinesse 源码的 Apache-2.0
并行有效);构建与验收信息以对应 Release 资产和说明为准。

## 源码安装

```bash
git clone https://github.com/RociferX/nmrfinesse.git
cd nmrfinesse
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[test]"
python main.py
```

`pip install .` 与 wheel 也包含运行资源(`nmrfinesse_data/config`、`nmrfinesse_data/presets`、
`gui/assets`、`ui_support/locales`)，源码检出与安装态的相对位置一致。真实处理需要另行安装
NMRPipe；NUS 重构还需要 SMILE。NMRFinesse 不下载或捆绑这两个工具。

## 开发者:可编辑源码安装

```bash
git clone <this repository>
cd nmrfinesse
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

可选依赖组(在 `pyproject.toml` 中声明):

```bash
pip install -e ".[test]"    # pytest
pip install -e ".[dev]"     # pytest + ruff
pip install -e ".[docs]"    # 文档工具链
```

`python main.py` 会在首次运行时创建本地 `nmrfinesse/` 虚拟环境,之后复用。
AppImage 使用随构建固定的内置入口。

可编辑安装会暴露一个命令行脚本:

| 命令 | 作用 |
| --- | --- |
| `nmrfinesse-viewer` | 独立谱图查看器(`python -m viewer` 也可以) |

主 GUI 在源码检出里用 `python main.py`；独立查看器也提供上面的命令行入口。
运行资源由 `nmrfinesse_data` 随包分发。

处理命令行在 `nmrfinesse_api` 包里:

```bash
python -m nmrfinesse_api --help
```

## 验证安装

```bash
python -m pytest -q                                       # 全量测试
python -m ruff check .                                    # 静态检查
python -c "import core, nmrfinesse_api, gui, viewer; print('imports ok')"
python examples/make_synthetic_dataset.py --out example_data/hsqc_2d
python examples/quickstart.py example_data/hsqc_2d
```

GUI 测试需要显示器,或者 offscreen 的 Qt 平台:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

## 升级与卸载

```bash
pip install -e .            # 改过 pyproject.toml 或入口点之后重跑
pip uninstall nmrfinesse      # 移除包与其命令行脚本
```

卸载永远不会删掉你的项目或研究:它们位于你自己选的目录里。
