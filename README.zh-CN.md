<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/figurecraft-wordmark-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="docs/images/figurecraft-wordmark-light.svg">
  <img src="docs/images/figurecraft-wordmark-light.svg" width="360" alt="FigureCraft — Deterministic figures for agents">
</picture>

### 面向 AI 编程 Agent 的确定性科研图表与技术图示工具集

将结构化的 **FigureSpec**、数据或清晰的自然语言需求，转换为可检查、可复现的专业图件，
而不是一次性的生成图片。

[English](README.md) · **简体中文**

[快速开始](#快速开始) · [示例](#示例) · [文档](#文档) · [开发](#开发)

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Install checks](https://github.com/Zchary1106/figurecraft/actions/workflows/install-platforms.yml/badge.svg)](https://github.com/Zchary1106/figurecraft/actions/workflows/install-platforms.yml)

</div>

> **它是什么：**一套可移植的 Agent Skill，支持 Claude Code、GitHub Copilot 和 OpenAI Codex。它以确定性布局、校验、溯源信息和可编辑源文件，渲染科研图表与技术图示。
>
> **它不是什么：**它不是图片生成包装器，也不是托管的在线画布。定量图表由 Matplotlib 渲染；技术图示由 SVG-first 布局与布线路径引擎渲染。

## 一眼了解

| 你的需求 | FigureCraft 提供的能力 |
| --- | --- |
| **科研图表** | 折线、柱状、散点、误差线、直方、箱线与热力图，并支持单位、不确定性与数据检查。 |
| **技术图示** | 系统架构、Agent 系统、流程图、泳道图、甘特图、研究框架、系统全景与神经网络图。 |
| **可靠产物** | Schema 校验、实测字体排版、确定性布局、结构化 SVG lint、溯源信息与哈希。 |
| **可用交付** | SVG 源图、可选 PNG/PDF、可编辑 Draw.io、输入 FigureSpec、manifest 与预览页。 |
| **安全迭代** | 可控修订可以保持已确认的几何结构；导出失败不会覆盖此前完整交付。 |

## 快速开始

### 1. 安装

克隆或下载本仓库后，在仓库根目录运行一条命令。

**macOS**

```bash
bash ./install.sh
```

**Windows PowerShell**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

该安装程序会为 **Claude Code**、**GitHub Copilot** 和 **OpenAI Codex** 安装共享核心与全部六个专项 Skill，创建隔离的 Python runtime，并执行可用性检查。安装后请重启 Agent 或新开一个会话，让宿主发现新 Skill。

<details>
<summary><strong>只安装一个宿主、安装到单个项目，或升级已有安装</strong></summary>

```bash
# 只安装到一个宿主
bash ./install.sh --agent codex       # 也可使用：claude、copilot

# 只在一个项目中可用
bash ./install.sh --scope project --project "/path/to/project"

# 升级安装；自定义副本会被备份而不是直接覆盖
bash ./install.sh --force
```

</details>

### 2. 让 Agent 生成图件

```text
使用 FigureCraft，根据 results.csv 创建一张双栏科研误差线图。
横轴为 epoch，纵轴为 accuracy，误差值为标准差。
请交付 SVG、300 DPI PNG 和 PDF。
```

```text
使用 FigureCraft 绘制一个多 Agent 研究系统架构。
展示用户请求、规划器、研究 Agent、证据记录、审查者和最终报告。
请输出可编辑 Draw.io 文件和适合幻灯片的 PNG。
```

Agent 会自动选择合适的专项 Skill。你也可以在请求中明确指定 `figurecraft-charts`、`figurecraft-architecture` 或其他专项名称。

### 3. 检查交付物

一次常规渲染会生成图件、可编辑和可复现所需的源文件，以及本地预览页。

```text
output/
├── figure.svg                 # 主矢量图
├── figure.drawio              # 可编辑图示文件（按请求及图示类型提供）
├── figure.png / figure.pdf    # 可选的最终尺寸导出
├── figure-source.json         # 规范化 FigureSpec
├── figure-manifest.json       # 检查、溯源、哈希和环境元数据
└── index.html                 # 本地预览与交付索引
```

## 示例

下方每张图都由仓库内已提交的 FigureSpec 生成。点击图片可打开其输入文件。

| 科研图表 | 系统架构 | 研究框架 |
| --- | --- | --- |
| [![折线图](docs/images/line-chart.svg)](skills/figurecraft/assets/examples/line-chart.json) | [![证据驱动的 Agent 工作流](docs/images/agent-evidence-workflow.svg)](skills/figurecraft/assets/examples/agent-evidence-workflow.json) | [![研究框架](docs/images/research-framework.svg)](skills/figurecraft/assets/examples/research-framework.json) |

| 神经网络图板 | 流程与计划 | 密集系统全景 |
| --- | --- | --- |
| [![CNN 架构](docs/images/cnn-architecture.svg)](skills/figurecraft/assets/examples/cnn-architecture.json) | [![甘特图](docs/images/gantt.svg)](skills/figurecraft/assets/examples/gantt.json) | [![系统全景](docs/images/system-landscape.svg)](skills/figurecraft/assets/examples/system-landscape.json) |

全部已提交的输入文件位于 [`skills/figurecraft/assets/examples/`](skills/figurecraft/assets/examples/)。

## 选择合适的专项 Skill

| Skill | 最适合的场景 |
| --- | --- |
| [`figurecraft`](skills/figurecraft/SKILL.md) | 共享 FigureSpec 工作流、渲染、导出、校验与交付。 |
| [`figurecraft-charts`](skills/figurecraft-charts/SKILL.md) | 科研图表、坐标轴、单位、不确定性、标注与数据校验。 |
| [`figurecraft-architecture`](skills/figurecraft-architecture/SKILL.md) | 软件架构、系统全景、Agent 系统、接口与协议。 |
| [`figurecraft-neural-networks`](skills/figurecraft-neural-networks/SKILL.md) | 神经网络拓扑、张量形状、CNN 阶段、残差路径与模型图板。 |
| [`figurecraft-research-frameworks`](skills/figurecraft-research-frameworks/SKILL.md) | 研究方法、证据链、效度和多工作流研究框架矩阵。 |
| [`figurecraft-process-diagrams`](skills/figurecraft-process-diagrams/SKILL.md) | 流程图、算法图、泳道图与甘特图。 |
| [`figurecraft-visual-critic`](skills/figurecraft-visual-critic/SKILL.md) | 审查并改进信息层级、排版、连线、配色与可读性。 |

## 工作原理

[![FigureCraft 工作原理：定义图件、校验约束、组合视觉系统、确定性渲染并交付可审计包。](docs/images/how-it-works.svg)](skills/figurecraft/assets/examples/how-it-works.json)

FigureCraft 以 `FigureSpec` 为唯一事实来源。它记录内容、语义、输出格式、语言、最终尺寸介质、布局选项和溯源信息。相比只有位图的流程，这使图件更易复现、审查和安全地修订。

## 输出格式与依赖

| 输出 | 适用场景 | 依赖 |
| --- | --- | --- |
| **SVG** | 主矢量输出和技术图示 | 默认包含。 |
| **Draw.io** | 手动编辑已支持的技术图示 | 为受支持的技术图示类型默认生成。 |
| **PNG / PDF** | 论文、幻灯片与位图工作流 | 图表使用 Matplotlib；图示转换需要原生 Cairo。 |

使用中文标签时，请安装 CJK 字体，例如 PingFang SC、Microsoft YaHei 或 Noto Sans CJK SC。SVG 与 Draw.io 图示不依赖原生 Cairo。如需在安装时强制验证全部导出格式：

```bash
bash ./install.sh --require-export
```

在 macOS 上可使用以下命令安装图示导出依赖：

```bash
brew install cairo
```

关于运行时诊断、受支持的动态库路径、Windows 安装和安全升级，请阅读[安装与运行时就绪说明](skills/figurecraft/references/installation.md)。

## 直接使用 CLI

Agent 是标准使用路径；在 CI 或本地开发中，也可以直接调用 CLI。

```bash
# 检查某个目标渲染管线的运行环境
python3 skills/figurecraft/scripts/figure.py check-env \
  --format png --kind diagram.architecture --cjk

# 不渲染，只校验 FigureSpec
python3 skills/figurecraft/scripts/figure.py validate \
  skills/figurecraft/assets/examples/line-chart.json

# 渲染一张图
python3 skills/figurecraft/scripts/figure.py render \
  skills/figurecraft/assets/examples/agent-evidence-workflow.json \
  --output output/agent-evidence-workflow

# 渲染关联的总览/详情图组
python3 skills/figurecraft/scripts/figure.py render-set \
  skills/figurecraft/assets/examples/framework-matrix.json \
  --output output/framework
```

## 可靠性与边界

FigureCraft 的目标是让正确的工作流更容易实现，而不是宣称取代所有编辑判断。

- 渲染前会校验数值、单位、不确定性语义、甘特图依赖、声明的网络维度和 FigureSpec 结构。
- 文本会以已安装的 FreeType 字体实测；遇到缺字或无法容纳的布局会报告问题，而非静默裁切。
- 渲染采用事务化发布：导出或 lint 失败时会保留此前完整的交付物。
- 极其密集的图示仍可能需要拆分、增加详情图或由人类进行视觉审查。
- 在 Draw.io 中手动编辑的修改不会自动回写到 FigureSpec。
- 参考图片用于提取布局和视觉语言，不会按像素复制原始作品。

## 文档

- [FigureSpec 参考](skills/figurecraft/references/figure-spec.md)
- [安装与运行时就绪](skills/figurecraft/references/installation.md)
- [科研图表指南](skills/figurecraft/references/scientific-charts.md)
- [技术图示指南](skills/figurecraft/references/technical-diagrams.md)
- [论文与幻灯片的最终尺寸输出](skills/figurecraft/references/output-media.md)
- [可控修订](skills/figurecraft/references/controlled-edits.md)
- [语言与溯源](skills/figurecraft/references/language-and-provenance.md)
- [参考图蒸馏](skills/figurecraft/references/reference-distillation.md)
- [视觉审查量表](skills/figurecraft/references/critique-rubric.md)

## 开发

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[export]"

# 运行完整测试集
.venv/bin/python -m unittest discover -s tests -v

# 校验全部内置示例
for spec in skills/figurecraft/assets/examples/*.json; do
  .venv/bin/python skills/figurecraft/scripts/figure.py validate "$spec"
done
```

若 macOS 的 Python 无法发现 Homebrew 安装的 Cairo，请在运行导出测试时设置：

```bash
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
  .venv/bin/python -m unittest discover -s tests -v
```

## 仓库结构

```text
.
├── install.py / install.sh / install.ps1  跨平台安装程序
├── skills/                                 核心与六个专项 Skill
│   └── figurecraft/                        渲染器、Schema、示例、主题和参考文档
├── docs/images/                            已提交的示例输出与项目图标
├── tests/                                  渲染、安装、导出和安全性回归测试
└── .github/workflows/                      跨平台安装检查
```

## 许可证

[MIT License](LICENSE)
