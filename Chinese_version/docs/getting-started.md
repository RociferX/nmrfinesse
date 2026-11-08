# 快速开始

本页介绍 1.0.12 的安装与首次处理。Linux 桌面用户可从 [1.0.12 Release](https://github.com/RociferX/nmrfinesse/releases/tag/v1.0.12) 下载 AppImage；源码安装见下方步骤。公开 API 版本为 v1.1.6。

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

第一次打开程序,先看 **在「帮助 → 使用教程」或 [GUI 指南](gui.md) 中可按九个章节查找功能。每章说明入口、用途、操作步骤和结果位置。

首次可先建立项目和实验，单个导入一份 Bruker 数据，再运行「生成 FID → 生成谱图」，2D/3D 可继续「峰挑选」。同类数据共用脚本时使用「参考脚本处理」。批量列表首行 `All` 可勾选当前筛选结果供清除，「批量导入」使用整个筛选结果。

指南对应当前源码。使用安装包时，可从「帮助 → 关于」查看版本，并按发布说明核对功能。

## 下一步

- [installation.md](installation.md) —— Linux AppImage 与源码安装两条路
- [external-dependencies.md](external-dependencies.md) —— NMRPipe/SMILE
- [troubleshooting.md](troubleshooting.md) | [faq.md](faq.md)
