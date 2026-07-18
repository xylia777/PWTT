# PWTT 本地离线完整业务链路实现计划

---

## ⚠️ 数据源问题说明（重要）

### MSAR-1.0 数据集实际情况
**位置**：`MSAR-1.0 dataset/`

**格式**：
- JPEG 256x256 图片（不是 TIFF）
- XML 边界框标注（船只检测）

**任务**：
- SAR 船只目标检测（单帧）

**问题**：
| 需求 | MSAR-1.0 | 结论 |
|-----|---------|------|
| 时序数据 | ❌ 单帧切片 | 不支持 |
| 损毁检测 | ❌ 船只检测 | 任务不符 |
| 地理参考 | ❌ 无地理信息 | 无法定位 |
| 数据格式 | ❌ JPEG | 需 TIFF |

### 数据源调研
**数据源确认：航天宏图一号（国产 C 波段 SAR）**
- ✅ C 波段 SAR，VV/VH 极化（与 Sentinel-1 同波段）
- ✅ 时序 TIFF 格式（带地理参考）
- ✅ 免费下载：https://engine.piesat.cn/
- **下载进度**：准备下载中
- **时序范围**：待确认（下载后验证）

---

## 1. 背景与问题

### 当前架构
- **完全依赖 GEE 云端**：所有 PWTT 计算在 Google Earth Engine 上执行
- **受限环境**：无法在无外网/内网环境下运行
- **数据源单一**：仅支持 Sentinel-1，不支持国产 SAR 数据

### 目标
构建**完全本地离线**的 PWTT 损毁检测业务链路，支持：
- 国产 SAR 数据（高分三号等）离线处理
- 内网环境运行，彻底解绑 GEE
- 与原有 GEE 云端模式共存，前端可切换
- 完整的量化分析（精确率、召回率、F1、矢量提取）

**数据源**：航天宏图一号（国产 C 波段 SAR，VV/VH 极化）
- **入口**：https://engine.piesat.cn/ → 首页【免费数据专区】→ SAR 时序样例下载
- **格式**：TIFF 时序影像（带地理参考）
- **兼容性**：C 波段与 Sentinel-1 同波段，PWTT 算法完全兼容

---

## 2. 核心设计原则

### 2.1 模块解耦
4 个脚本完全独立，支持：
- **单独调用**：每个脚本可独立运行
- **串行执行**：一键运行完整流程
- **标准化接口**：统一的输入输出路径约定

### 2.2 数据流设计

```
本地 SAR TIFF (MSAR-1.0) → sar_process.py → 标准时序影像文件夹
                                                    ↓
                                            pwtt_detect.py → 损毁检测 TIFF
                                                    ↓
                                            result_analysis.py → 矢量 + 统计
                                                    ↓
                                            app.py (改造) → Web 展示
```

### 2.3 路径标准化
```python
# 统一输入输出路径结构（基于项目根目录）
PROJECT_ROOT = d:\VScodeProjects\PWTT

PROJECT_ROOT/
├── data/
│   ├── input/           # 原始 SAR 数据输入（MSAR-1.0）
│   │   ├── pre/         # 灾前时序影像
│   │   └── post/        # 灾后时序影像
│   ├── ground_truth/    # 真值标注（二值栅格 TIFF 0/1）
│   └── processed/       # 标准化处理后影像
├── results/
│   ├── damage/          # 损毁检测结果
│   ├── analysis/        # 量化分析结果
│   └── export/          # Web 展示导出
└── cache/               # 临时缓存
```

---

## 3. 四个脚本详细设计

### 脚本 1：sar_process.py — SAR 数据获取与处理工具

**输入**：
- 本地高分三号 TIFF/MSAR-1.0 开源切片数据集
- 可选：真值标注文件（二值栅格 TIFF，0=无损毁，1=损毁）

**核心功能**：
1. **多源影像读取**：支持标准 GeoTIFF（带地理参考）
2. **相干斑降噪**：Lee 滤波（复用 GEE 版本的逻辑）
3. **掩膜过滤**：水体、农田掩膜（基于阈值或外部掩膜文件）
4. **时序统一归档**：按时间序列组织文件夹结构
5. **真值加载**：读取二值栅格真值数据

**输出**：
- `data/processed/pre/` - 标准化灾前时序影像（降噪后）
- `data/processed/post/` - 标准化灾后时序影像（降噪后）
- `data/processed/ground_truth.tif` - 统一格式的真值栅格

**关键函数**：
```python
class SARProcessor:
    def read_tiff(self, path) -> Tuple[np.ndarray, dict]  # 读取影像+元数据
    def lee_filter(self, image, window_size=5) -> np.ndarray  # Lee 降噪
    def apply_mask(self, image, mask_type) -> np.ndarray  # 掩膜过滤
    def process_batch(self, input_dir, output_dir, time_range) -> None  # 批处理
    def load_ground_truth(self, path) -> np.ndarray  # 加载真值
```

**依赖库**：
- `rasterio` / `gdal`：TIFF 读取
- `numpy`：数组运算
- `scipy`：滤波算法

---

### 脚本 2：pwtt_detect.py — PWTT 时序损毁检测工具（纯本地）

**输入**：
- `data/processed/pre/` - 灾前时序影像文件夹
- `data/processed/post/` - 灾后时序影像文件夹

**核心逻辑**（复用 GEE 版本算法）：
1. **逐像素提取时序散射样本**：从时序影像中提取每个像素的时间序列
2. **Welch 不等方差 T 检验**：逐像素计算 T 值
   ```python
   t = (mean_post - mean_pre) / sqrt(var_pre/n_pre + var_post/n_post)
   ```
3. **自由度计算**：Welch-Satterthwaite 公式
   ```python
   df = (var_pre/n_pre + var_post/n_post)² / (var_pre²/(n_pre²*(n_pre-1)) + var_post²/(n_post²*(n_post-1)))
   ```
4. **显著性阈值筛选**：T > threshold 判定为损毁
5. **分块处理**：避免大区域内存溢出

**输出**：
- `results/damage/pwtt_damage.tif` - 像素级损毁检测结果（二值栅格）
- `results/damage/pwtt_t_statistic.tif` - T 统计量栅格
- `results/damage/pwtt_n_pre.tif` - 参考期观测数量
- `results/damage/metadata.json` - 元数据（阈值、时间范围、统计信息）

**关键函数**：
```python
class LocalPWTT:
    def extract_timeseries(self, pre_dir, post_dir, bbox) -> Dict  # 提取时序样本
    def welch_ttest(self, pre_samples, post_samples) -> Tuple[float, float]  # Welch 检验
    def compute_tmap(self, pre_data, post_data, chunk_size) -> np.ndarray  # 分块计算 T 图
    def apply_threshold(self, t_map, threshold) -> np.ndarray  # 阈值筛选
    def run_detection(self, config) -> str  # 完整检测流程
```

**分块计算策略**：
```python
def chunked_detection(image_shape, chunk_size=512):
    for i in range(0, image_shape[0], chunk_size):
        for j in range(0, image_shape[1], chunk_size):
            chunk = image[i:i+chunk_size, j:j+chunk_size]
            # 处理 chunk...
```

**依赖库**：
- `numpy`：数组运算
- `scipy.stats`：统计检验
- `rasterio`：TIFF 写入

---

### 脚本 3：result_analysis.py — 检测结果量化分析工具

**输入**：
- `results/damage/pwtt_damage.tif` - 损毁检测结果
- `data/processed/ground_truth.tif` - 真值标注（可选）

**核心功能**：
1. **像素比对计算**：
   - 精确率（Precision）：TP / (TP + FP)
   - 召回率（Recall）：TP / (TP + FN)
   - F1 分数：2 * (Precision * Recall) / (Precision + Recall)
   - IoU（交并比）：TP / (TP + FP + FN)

2. **栅格转矢量**：损毁区域边界提取
   - 连通区域标记
   - 多边形化
   - 属性计算（面积、严重等级）

3. **分区统计**：
   - 按损毁等级划分（轻微/中等/严重）
   - 区域面积统计
   - 空间分布分析

4. **指标统计**：生成 Excel 台账

**输出**：
- `results/analysis/metrics.json` - 量化指标（精确率、召回率、F1、IoU）
- `results/analysis/damage_vectors.shp` - 损毁矢量边界（Shapefile）
- `results/analysis/damage_vectors.geojson` - GeoJSON 格式
- `results/analysis/statistics.xlsx` - 分区统计 Excel

**关键函数**：
```python
class ResultAnalyzer:
    def compute_metrics(self, prediction, ground_truth) -> Dict  # 计算评估指标
    def raster_to_vector(self, raster_path) -> gpd.GeoDataFrame  # 栅格转矢量
    def compute_area_stats(self, vectors) -> gpd.GeoDataFrame  # 区域面积统计
    def classify_severity(self, t_statistic, bins=[3.3, 4.0, 5.0]) -> np.ndarray  # 严重等级分类
    def export_statistics(self, metrics, vectors, output_path) -> None  # 导出 Excel
    def run_analysis(self, damage_path, ground_truth_path=None) -> Dict  # 完整分析流程
```

**依赖库**：
- `numpy`：数组运算
- `scikit-image`：连通区域标记
- `geopandas`：矢量数据处理
- `shapely`：几何计算
- `openpyxl`：Excel 写入

---

### 脚本 4：app.py（改造）— Web 业务研判平台工具

**保留原有功能**：
- GEE 云端检测接口 `/run_pwtt`（完全不变）
- Leaflet 前端交互

**新增功能**：
1. **算力模式切换**：
   - 路由参数 `?mode=cloud|local`
   - 前端按钮切换模式
   - 不同模式显示不同参数界面

2. **本地离线计算路由**：
   - `/run_pwtt_local` - 本地 PWTT 检测
   - `/analyze_local` - 本地量化分析
   - `/export_local` - 导出本地结果

3. **结果展示**：
   - 读取本地生成的损毁栅格（TIFF 转 PNG）
   - 矢量数据加载（GeoJSON → Leaflet 图层）
   - 指标可视化（ECharts 图表）

4. **离线研判报表**：
   - PDF 报告生成
   - 统计表格

**改造内容**：
```python
# 新增路由
@app.route('/run_pwtt_local', methods=["POST"])
def run_pwtt_local():
    # 调用 pwtt_detect.py
    pass

@app.route('/analyze_local', methods=["POST"])
def analyze_local():
    # 调用 result_analysis.py
    pass

@app.route('/get_local_metrics')
def get_local_metrics():
    # 返回本地指标 JSON
    pass

@app.route('/get_local_vectors')
def get_local_vectors():
    # 返回 GeoJSON 矢量
    pass

@app.route('/export_local_report')
def export_local_report():
    # 生成 PDF 报告
    pass

# 工具函数
def tiff_to_png(tiff_path, output_path) -> str
def geodataframe_to_geojson(gdf) -> dict
```

**前端改造**（templates/index.html）：
```html
<!-- 新增算力模式切换按钮 -->
<div class="mode-switch">
    <button class="mode-btn active" data-mode="cloud">云端 GEE</button>
    <button class="mode-btn" data-mode="local">本地离线</button>
</div>

<!-- 本地模式专用参数面板（默认隐藏） -->
<div id="local-params" style="display:none;">
    <label>灾前影像目录</label>
    <input type="text" name="pre_dir">
    <label>灾后影像目录</label>
    <input type="text" name="post_dir">
</div>
```

**依赖库**（新增）：
- `subprocess`：调用本地脚本
- `Pillow`：图像转换
- `reportlab`：PDF 生成
- `echarts-python`：图表生成

---

## 4. 统一代码要求

### 4.1 模块化设计
每个脚本按功能分层封装：
```python
# 脚本结构示例
"""
[脚本名称] — [功能描述]

依赖库：xxx

作者：xylia777
日期：2026-07-07
"""

import ...

class [主类名]:
    """核心功能类"""

    def __init__(self, config):
        pass

    # 核心方法
    def [核心方法](self, ...):
        pass

    # 工具方法
    def _private_method(self, ...):
        pass


def main():
    """命令行入口"""
    pass


if __name__ == "__main__":
    main()
```

### 4.2 路径配置统一
```python
# config.py - 统一路径配置
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

PATHS = {
    'input': os.path.join(PROJECT_ROOT, 'data', 'input'),
    'pre': os.path.join(PROJECT_ROOT, 'data', 'input', 'pre'),
    'post': os.path.join(PROJECT_ROOT, 'data', 'input', 'post'),
    'ground_truth': os.path.join(PROJECT_ROOT, 'data', 'input', 'ground_truth'),
    'processed': os.path.join(PROJECT_ROOT, 'data', 'processed'),
    'damage': os.path.join(PROJECT_ROOT, 'results', 'damage'),
    'analysis': os.path.join(PROJECT_ROOT, 'results', 'analysis'),
    'cache': os.path.join(PROJECT_ROOT, 'cache'),
}

# 自动创建目录
for path in PATHS.values():
    os.makedirs(path, exist_ok=True)
```

### 4.3 一键串行运行
```python
# pipeline.py - 完整流程编排
"""
PWTT 本地离线完整业务链路 — 一键运行
"""
from sar_process import SARProcessor
from pwtt_detect import LocalPWTT
from result_analysis import ResultAnalyzer
from config import PATHS

def run_full_pipeline(config):
    """完整流程：处理 → 检测 → 分析"""

    # 1. SAR 数据处理
    processor = SARProcessor(config)
    processor.run()

    # 2. PWTT 检测
    detector = LocalPWTT(config)
    damage_path = detector.run_detection()

    # 3. 量化分析
    analyzer = ResultAnalyzer(config)
    analyzer.run_analysis(damage_path)

    return {
        'damage': damage_path,
        'analysis': analyzer.output_path
    }


if __name__ == "__main__":
    config = {...}
    results = run_full_pipeline(config)
    print(f"[OK] 完整流程完成: {results}")
```

### 4.4 注释规范
```python
def welch_ttest(self, pre_samples, post_samples) -> Tuple[float, float]:
    """
    Welch 不等方差 T 检验

    原理：当两组样本方差不等时，Welch 检验比标准 T 检验更稳健
    公式：t = (μ2 - μ1) / sqrt(s1²/n1 + s2²/n2)

    Args:
        pre_samples (np.ndarray): 灾前时序样本 [time, height, width]
        post_samples (np.ndarray): 灾后时序样本 [time, height, width]

    Returns:
        Tuple[float, float]: (t_statistic, degrees_of_freedom)
            - t_statistic: T 统计量
            - degrees_of_freedom: 自由度（Welch-Satterthwaite 公式）
    """
```

---

## 5. 双模式兼容设计

### 5.1 GEE 云端模式（原有）
```python
# app.py - 原有路由保持不变
@app.route('/run_pwtt', methods=["POST"])
def run_pwtt():
    """GEE 云端检测（原有功能）"""
    # 使用 pwtt.detect_damage() - 调用 GEE
    pass
```

### 5.2 本地离线模式（新增）
```python
# app.py - 新增本地路由
@app.route('/run_pwtt_local', methods=["POST"])
def run_pwtt_local():
    """本地离线检测（新增功能）"""
    # 调用 pwtt_detect.py 的 LocalPWTT
    pass
```

### 5.3 前端模式切换
```javascript
// index.html - 模式切换逻辑
const modeBtns = document.querySelectorAll('.mode-btn');
modeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        // 切换激活状态
        modeBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const mode = btn.dataset.mode;

        // 显示/隐藏对应参数面板
        document.getElementById('cloud-params').style.display =
            mode === 'cloud' ? 'block' : 'none';
        document.getElementById('local-params').style.display =
            mode === 'local' ? 'block' : 'none';

        // 修改表单提交路由
        form.action = mode === 'cloud' ? '/run_pwtt' : '/run_pwtt_local';
    });
});
```

---

## 6. 测试与验证方案

### 6.1 单元测试
```python
# tests/test_sar_process.py
def test_lee_filter():
    """测试 Lee 滤波效果"""

def test_read_tiff():
    """测试 TIFF 读取"""

# tests/test_pwtt_detect.py
def test_welch_ttest():
    """测试 Welch T 检验正确性"""

def test_chunked_detection():
    """测试分块检测"""

# tests/test_result_analysis.py
def test_compute_metrics():
    """测试指标计算"""

def test_raster_to_vector():
    """测试栅格转矢量"""
```

### 6.2 集成测试
```python
# tests/test_pipeline.py
def test_full_pipeline():
    """测试完整流程"""
    # 使用 MSAR-1.0 模拟数据运行完整链路
    pass
```

### 6.3 端到端测试
1. 准备测试数据：MSAR-1.0 小型 TIFF 影像 + 模拟真值
2. 运行完整流程：`python pipeline.py`
3. 验证输出：
   - 检测结果 TIFF 存在
   - 矢量数据可加载
   - Excel 统计正确
4. Web 端测试：
   - 启动 Flask：`python app.py`
   - 测试本地模式接口
   - 验证前端展示

---

## 7. 新增依赖库清单

```toml
# pyproject.toml - 新增依赖
dependencies = [
    # 原有依赖
    "earthengine-api",
    "geemap",

    # 新增本地处理依赖
    "rasterio>=1.3.0",        # TIFF 读写
    "numpy>=1.24.0",          # 数组运算
    "scipy>=1.10.0",          # 统计检验、滤波
    "scikit-image>=0.21.0",   # 图像处理
    "geopandas>=0.13.0",      # 矢量数据处理
    "shapely>=2.0.0",         # 几何计算
    "openpyxl>=3.1.0",        # Excel 写入
    "Pillow>=10.0.0",         # 图像转换
    "reportlab>=4.0.0",       # PDF 生成
    "flask>=2.3.0",           # Web 框架
    "matplotlib>=3.7.0",      # 绘图
]
```

---

## 8. 实施步骤

### Phase 1：基础架构（优先级：高）
1. 创建 `config.py` - 统一路径配置
2. 创建 `pipeline.py` - 流程编排框架
3. 更新 `pyproject.toml` - 添加依赖

### Phase 2：脚本 1 - sar_process.py
1. 实现基础类 `SARProcessor`
2. 实现 TIFF 读取功能
3. 实现 Lee 滤波算法
4. 实现掩膜过滤
5. 实现批量处理函数
6. 编写单元测试

### Phase 3：脚本 2 - pwtt_detect.py
1. 实现基础类 `LocalPWTT`
2. 实现时序样本提取
3. 实现 Welch T 检验
4. 实现分块计算策略
5. 实现 T 图生成
6. 编写单元测试

### Phase 4：脚本 3 - result_analysis.py
1. 实现基础类 `ResultAnalyzer`
2. 实现指标计算（Precision/Recall/F1/IoU）
3. 实现栅格转矢量
4. 实现面积统计
5. 实现 Excel 导出
6. 编写单元测试

### Phase 5：脚本 4 - app.py 改造
1. 新增本地路由接口
2. 实现 TIFF → PNG 转换
3. 实现矢量数据服务
4. 实现指标可视化
5. 实现报表导出
6. 前端增加模式切换按钮

### Phase 6：测试与优化
1. 集成测试
2. 性能优化（分块大小调整）
3. 文档完善
4. 示例数据准备

---

## 9. 关键文件清单

### 新增文件
```
新增文件（5 个）：
├── config.py                  # 统一配置
├── sar_process.py             # 脚本 1：SAR 数据处理
├── pwtt_detect.py             # 脚本 2：本地 PWTT 检测
├── result_analysis.py         # 脚本 3：结果分析
├── pipeline.py                # 流程编排

新增目录：
├── data/
│   ├── input/
│   ├── processed/
├── results/
│   ├── damage/
│   ├── analysis/
└── tests/                     # 单元测试
```

### 修改文件
```
修改文件（3 个）：
├── app.py                     # 新增本地路由
├── templates/index.html       # 新增模式切换
├── pyproject.toml             # 添加依赖
```

---

## 10. 风险与应对

| 风险 | 应对策略 |
|-----|---------|
| 内存溢出（大区域） | 分块处理，chunk_size 可配置 |
| 性能问题（CPU 计算） | 多进程并行，可选 GPU 加速 |
| 数据格式兼容性 | MSAR-1.0 标准化，支持标准 GeoTIFF，预留扩展接口 |
| 前后端对接复杂 | 先实现核心功能，后完善 UI 交互 |
| 真值数据缺失 | 分析功能支持无真值模式（仅统计，无评估） |

---

## 11. 成功标准

- ✅ 4 个脚本独立可运行
- ✅ 支持串行完整流程
- ✅ 本地离线 PWTT 检测结果与 GEE 版本结果趋势一致
- ✅ 量化分析指标计算正确
- ✅ Web 端可切换云端/本地模式
- ✅ 支持 MSAR-1.0 数据
- ✅ 代码注释完整，易于维护