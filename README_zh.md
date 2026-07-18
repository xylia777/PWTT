# 基础设施损毁智能检测系统 · PWTT

> 基于 [Pixel-Wise T-Test (PWTT)](https://github.com/oballinger/PWTT) 算法的建筑损毁检测项目。
> 采用**内网离线优先**的四模块架构：SAR 数据源适配与预处理 → 损毁检测 → 检测结果分析 → Web 业务研判展示。

![技术架构图](技术路线图.png)

## 📌 项目简介

本项目利用合成孔径雷达（SAR）卫星影像，通过**像素级 T 检验（PWTT）**算法自动识别冲突/灾害区域的建筑损毁。相比深度学习方法，PWTT 轻量、可泛化、无 domain shift，在未见区域优于 SOTA DL 模型。

**技术参考**：Ballinger, O. (2025). *Open access battle damage detection via Pixel-Wise T-Test on Sentinel-1 imagery*. *Remote Sensing of Environment*, 331, 115025. [DOI](https://doi.org/10.1016/j.rse.2025.115025)

## 🔧 与上游 PWTT 的关系

本项目 Fork 自 [oballinger/PWTT](https://github.com/oballinger/PWTT)（MIT License），在原基础上增强：

- **🐛 Bug 修复**：默认 `stouffer` 方法的 `make_orbit_s1` 未定义名 Bug（→ `make_group_collection`），修复后默认方法可正常运行（见 `pwtt/__init__.py`）。
- **🔑 安全认证**：新增 `gee_auth.py`，把 GEE 凭据从 C 盘默认路径 monkey-patch 重定向到项目内 `.gee/`，避免敏感信息写入系统盘。
- **📈 可视化与诊断**：新增 `view_result.py`（损毁热力图 + `n_pre` 参考期诊断，并排出图）。
- **🧪 复现测试**：新增 `test_detect.py`（最小用例验证默认 stouffer 算法可跑通）。
- **🗺 本地离线四模块（已完成重构）**：`local_scripts/` 拆为 `preprocess`（数据源适配 S1/国产 GF-3/LT-1 + Lee 滤波 + 掩膜）/ `detect`（PWTT 检测）/ `analyze`（精度+矢量+Excel 台账）/ `visualize` 四个独立脚本，脱离 GEE 内网离线运行。
- **🌐 Web 应用**：`app.py` + `templates/` + `static/` 构建轻量化可视化前端（第四层）。

## 🏗 技术架构（四模块）

| 模块 | 名称 | 职责 | 对应脚本 |
|---|---|---|---|
| 01 | SAR 数据源适配与预处理 | 数据源适配（兼容 S1 / 国产 GF-3/LT-1）+ Lee 滤波 + 掩膜 | `local_scripts/preprocess.py` |
| 02 | **损毁检测**（核心） | PWTT 像素级 T 检验（逐像素 Welch） | `local_scripts/detect.py` |
| 03 | 检测结果分析 | 精度（P/R/F1/IoU）、栅格转矢量、Excel 台账 | `local_scripts/analyze.py` |
| 04 | Web 业务研判展示 | 损毁热力图 / 地图叠加 / 交互研判 / 报表导出 | `local_scripts/visualize.py` + `app.py` |

详见 [技术路线图.png](技术路线图.png)。

## 🚀 快速开始

### 1. 环境要求
- Python 3.10+
- **云端模式**：Google Earth Engine 账号 + 云项目（访问 Sentinel-1）；依赖 `earthengine-api`、`geemap`（`pip install -e .` 自动装）
- **本地离线模式**：额外依赖 `rasterio` / `scipy` / `scikit-image` / `geopandas` / `shapely` / `openpyxl`（`python local_scripts/install_local_deps.py` 一键装）

### 2. 安装
```bash
git clone https://github.com/xylia777/PWTT.git
cd PWTT
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
pip install -e .
python local_scripts/install_local_deps.py   # 本地离线模式依赖（云端模式可跳过）
```

### 3. GEE 认证（首次，云端模式需要）
```powershell
$env:GEE_PROJECT = "pwtt-academic-2026"     # 你的谷歌云项目ID
python gee_auth.py   # 浏览器授权一次，凭据存 .gee/（已 gitignore，不写 C 盘）
```

### 4. 启动 Web 服务（日常使用）
```powershell
powershell -ExecutionPolicy RemoteSigned      # 首次放开执行策略（仅 PowerShell 需要）
.\.venv\Scripts\Activate.ps1                  # ① 激活 venv（退出用 deactivate）
$env:GEE_PROJECT = "pwtt-academic-2026"       # ② 设 GEE 项目名（云端模式需要）
python app.py                                 # ③ 启动 Web 服务 → 浏览器开 http://127.0.0.1:5000
```
> 提示：新开终端窗口需重新 ① 激活 venv + ② 设 GEE_PROJECT（环境变量是会话级）。也可在项目根 `.env` 写 `GEE_PROJECT=pwtt-academic-2026`，`app.py` 启动时自动读取，省去 ②。

### 5. 其他运行方式
```bash
python test_detect.py             # 云端最小复现：验证默认 stouffer 跑通
python view_result.py             # 云端：Gaza 损毁热力图 + n_pre 诊断图
python local_scripts/pipeline.py  # 本地离线一键全流程（预处理→检测→分析→可视化）
python data/download_test_data.py # 下载小区域 S1 测试数据（走 GEE）
```

## 📂 目录结构
```
PWTT/
├── pwtt/__init__.py     # 核心算法（detect_damage / ttest / lee_filter ...）
├── code/                # 上游辅助脚本（eval, cusum, threshold_curves ...）
├── gee_auth.py          # GEE 认证（凭据重定向到 .gee/）
├── test_detect.py       # 最小复现
├── view_result.py       # 热力图 + n_pre 诊断
├── gen_roadmap.py       # 技术架构图生成
├── 技术路线图.png        # 四层技术架构图
├── app.py               # Web 应用入口（第四层）
├── templates/ static/   # Web 前端
├── pyproject.toml       # 包配置
├── local_scripts/       # 本地离线模块（见下节详解）
├── config.py            # 全局配置（路径 / 算法参数 / 数据源）
├── .gitignore           # 忽略 .venv/ .gee/ memory/ 等
└── readme.md            # 上游英文 README
```

## 🔧 本地离线模块（local_scripts/）

`local_scripts/` 是**脱离 GEE 的内网离线处理链**（对应四层架构的第二、三层本地化），全程不依赖外网。各文件职责：

重构为**四模块独立脚本**（每个既能被 `pipeline.py` 串联，也能独立命令行运行 / 被 import 封装成工具）：

| 脚本 | 核心类 / 功能 | 对应架构层 | 独立命令行 |
|---|---|---|---|
| `preprocess.py` | `SARPreprocessor`：**数据源适配**（兼容 S1 / GF-3 / LT-1）+ Lee 滤波 + 掩膜 | 第二层 · 预处理 | `python local_scripts/preprocess.py --input ... --output ... --source s1\|gf3\|lt1` |
| `detect.py` | `PWDetector`：**Welch T 检验**（逐像素）、分块算 T 图、阈值筛选 | 第三层 · PWTT 内核 | `python local_scripts/detect.py --pre ... --post ... --threshold 3.3` |
| `analyze.py` | `ResultAnalyzer`：精度（P/R/F1/IoU）、栅格转矢量、Excel 台账 | 第三层 + 第四层（报表） | `python local_scripts/analyze.py --damage ... [--ground_truth ...]` |
| `visualize.py` | `DamageVisualizer`：损毁热力图（离线形态；Web 形态见 `app.py`） | 第四层 · 可视化 | `python local_scripts/visualize.py --t_stat ... [--n_pre ...]` |
| `pipeline.py` | 一键串联 ①预处理→②检测→③分析→④可视化 | 编排 | `python local_scripts/pipeline.py` |
| `install_local_deps.py` | 安装本地依赖 | 环境准备 | `python local_scripts/install_local_deps.py` |

**配置依赖**：根目录 `config.py`（`PATHS` 路径、`PWTT_CONFIG` 算法参数、`DATA_SOURCE` 数据源、`ensure_directories` 建目录）。

**运行方式**：
```bash
python local_scripts/install_local_deps.py   # 1. 装本地依赖（首次）
python local_scripts/pipeline.py             # 2. 一键跑全流程（预处理→检测→分析→可视化）
# 或单独跑某个模块，例如只做检测：
python local_scripts/detect.py --pre data/processed/pre --post data/processed/post
```
- 输入：`data/input/pre/`、`data/input/post/`（灾前/灾后 SAR 时序 GeoTIFF，S1 或国产 SAR 均可）
- 输出：`results/damage/`（损毁栅格）、`results/analysis/`（指标 JSON / 矢量 / Excel 台账 / 热力图）

> ⚠️ 本模块依赖 rasterio / scipy / scikit-image / geopandas 等本地库（`install_local_deps.py` 一键安装），完整跑通后即与 `app.py` 的"本地离线"模式对接。

## 🤝 协作流程

欢迎贡献！推荐 GitHub Flow：

```bash
# 1. 同步最新
git pull

# 2. 新建功能分支
git checkout -b feature/你的功能

# 3. 改代码并提交
git add <文件>
git commit -m "feat: 简述改动"

# 4. 推送
git push -u origin feature/你的功能

# 5. 在 GitHub 发起 Pull Request，团队 review 后合并到 main
```

**提交信息约定**：`feat:` 新功能 / `fix:` 修复 / `docs:` 文档 / `refactor:` 重构 / `chore:` 杂项。

## 📄 许可

MIT License —— 继承自上游 [oballinger/PWTT](https://github.com/oballinger/PWTT)。

## 🙏 致谢

- 算法与基础代码：[Ollie Ballinger](https://github.com/oballinger) 的 PWTT 项目与论文
- 建筑损毁标注：联合国卫星中心 UNOSAT
- 卫星影像：ESA Copernicus Sentinel-1、Google Earth Engine
