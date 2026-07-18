import os
import sys
import json
import numpy as np
from flask import Flask, render_template, request, jsonify, send_file
from PIL import Image
import ee
import geemap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# ====================== 本地离线模块 ======================
try:
    from local_scripts import SARPreprocessor, PWDetector, ResultAnalyzer, DamageVisualizer
    from config import PATHS
    import rasterio
    LOCAL_AVAILABLE = True
except ImportError:
    LOCAL_AVAILABLE = False

# ====================== GEE 凭据复用（和你原有代码完全一致） ======================
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CRED_PATH = os.path.join(PROJECT_ROOT, '.gee', 'credentials')

# 从项目内 .env 读取环境变量（不依赖终端 $env:，运行按钮/任何启动方式都生效）
_env_path = os.path.join(PROJECT_ROOT, '.env')
if os.path.exists(_env_path):
    with open(_env_path, encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

try:
    if os.path.exists(CRED_PATH):
        ee.oauth.get_credentials_path = lambda: CRED_PATH
        PROJECT = os.environ.get('GEE_PROJECT', '你的GEE项目ID')
        ee.Initialize(project=PROJECT)
        import pwtt
        GEE_AVAILABLE = True
    else:
        GEE_AVAILABLE = False
        print("[!] 未找到 GEE 凭据文件，仅支持本地模式")
except Exception as e:
    print(f"[!] GEE 初始化失败: {e}")
    GEE_AVAILABLE = False

app = Flask(__name__)
# 临时图片缓存目录
IMG_CACHE = os.path.join(PROJECT_ROOT, "static", "cache")
os.makedirs(IMG_CACHE, exist_ok=True)

# 生成热力图函数（复用你原有绘图逻辑）
def generate_pwtt_img(bbox, war_start, inference_start, pre_interval, post_interval, threshold=3.3, use_s2_base=False):
    # 修复中文方框乱码
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
    plt.rcParams["axes.unicode_minus"] = False

    w, s, e, n = bbox
    aoi = ee.Geometry.Rectangle(bbox)
    # 1. 执行PWTT计算
    img = pwtt.detect_damage(
        aoi=aoi,
        war_start=war_start,
        inference_start=inference_start,
        pre_interval=pre_interval,
        post_interval=post_interval
    )
    # 2. 拉取双波段numpy
    stack = geemap.ee_to_numpy(img.select(['T_statistic', 'n_pre']), region=aoi, scale=100)
    arr_t = np.ma.masked_where(stack[:, :, 0] <= 0, stack[:, :, 0])
    arr_npre = np.ma.masked_where(stack[:, :, 1] <= 0, stack[:, :, 1])
    extent = [w, e, s, n]

    # 3. 绘图配色
    cmap_t = LinearSegmentedColormap.from_list('pwtt', ['yellow', 'red', 'purple'])
    cmap_t.set_bad('#dddddd')
    cmap_n = plt.get_cmap('viridis').copy()
    cmap_n.set_bad('#dddddd')

    fig, (axT, axN) = plt.subplots(1, 2, figsize=(16, 7))
    imT = axT.imshow(arr_t, cmap=cmap_t, vmin=3, vmax=5, extent=extent)
    axT.set_title(f"T_statistic (threshold={threshold} = damaged)")
    axT.set_xlabel("Longitude"); axT.set_ylabel("Latitude")
    fig.colorbar(imT, ax=axT, label="T_statistic")

    imN = axN.imshow(arr_npre, cmap=cmap_n, vmin=0, vmax=80, extent=extent)
    axN.set_title("n_pre 参考期观测样本数量")
    axN.set_xlabel("Longitude"); axN.set_ylabel("Latitude")
    fig.colorbar(imN, ax=axN, label="n_pre")

    fig.suptitle(f"PWTT Result | war_start={war_start} inference={inference_start}", y=0.98)
    save_path = os.path.join(IMG_CACHE, "result.png")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    # 统计损毁像素（像素级，非建筑级）
    valid = int(arr_t.count())
    damaged = int((arr_t > threshold).sum())
    ratio = damaged / valid if valid else 0
    stats = {
        "damage_pixels": damaged,
        "total_pixels": valid,                 # 有效观测像素总量
        "damage_ratio": ratio,
        "image_count": int(arr_npre.max()) if arr_npre.count() else 0,    # 时序样本数（n_pre 最大值）
    }
    # PWTT 损毁瓦片（GEE getMapId，前端叠加用）
    try:
        vis = {'min': 3, 'max': 5, 'palette': ['yellow', 'red', 'purple']}
        tile_url = img.select('T_statistic').getMapId(vis)['tile_fetcher'].url_format
    except Exception as ex:
        tile_url = None
        print(f"[!] 损毁瓦片获取失败: {ex}")
    # Sentinel-2 灾后真彩色底图（可选，默认关省 GEE 配额；与检测同时相）
    base_tile_url = None
    if use_s2_base:
        try:
            post_s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                .filterBounds(aoi)
                .filterDate(inference_start, ee.Date(inference_start).advance(post_interval, 'month'))
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
                .select(['B4', 'B3', 'B2'])
                .median())
            base_tile_url = post_s2.getMapId({'bands': ['B4','B3','B2'], 'min': 0, 'max': 3000})['tile_fetcher'].url_format
        except Exception as ex:
            base_tile_url = None
            print(f"[!] S2 底图瓦片获取失败: {ex}")
    return "cache/result.png", stats, tile_url, base_tile_url

# 首页：左右分栏页面
@app.route('/')
def index():
    return render_template("index.html")

# 接口：接收前端参数，生成图片
@app.route('/run_pwtt', methods=["POST"])
def run_pwtt():
    if not GEE_AVAILABLE:
        return jsonify({"error": "GEE 模式不可用，请切换到本地离线模式"})

    data = request.form
    # 读取前端表单参数
    bbox = [
        float(data["west"]),
        float(data["south"]),
        float(data["east"]),
        float(data["north"])
    ]
    war_start = data["war_start"]
    inference_start = data["inference_start"]
    pre_interval = int(data["pre_interval"])
    post_interval = int(data["post_interval"])
    threshold = float(data["threshold"])
    try:
        use_s2_base = data.get("s2_base") == "on"
        img_path, stats, tile_url, base_tile_url = generate_pwtt_img(bbox, war_start, inference_start, pre_interval, post_interval, threshold, use_s2_base=use_s2_base)
        return jsonify({
            "img_url": img_path,
            "tile_url": tile_url,            # 损毁图层瓦片
            "base_tile_url": base_tile_url,  # 灾后 Sentinel-2 真彩色底图瓦片
            "bbox": bbox,                    # [west, south, east, north] 前端地图定位
            **stats,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        msg = str(e)
        hint = "（疑似网络问题：访问 GEE 服务器被重置，请检查 VPN/代理后重试）" if ("Connection" in msg or "initialized" in msg or "10054" in msg or "EEException" in msg) else ""
        return jsonify({"error": f"GEE 计算失败：{msg} {hint}"})

# 图片下载接口
@app.route('/download')
def download_img():
    path = os.path.join(IMG_CACHE, "result.png")
    return send_file(path, as_attachment=True, download_name="pwtt_result.png")


# ====================== 本地离线模式接口 ======================

@app.route('/run_pwtt_local', methods=["POST"])
def run_pwtt_local():
    """本地离线 PWTT 检测"""
    if not LOCAL_AVAILABLE:
        return jsonify({"error": "本地模块未安装，请先安装依赖：pip install rasterio scipy scikit-image geopandas shapely openpyxl"})

    try:
        data = request.form
        pre_dir = data.get("pre_dir", os.path.join(PROJECT_ROOT, "data", "input", "pre"))
        post_dir = data.get("post_dir", os.path.join(PROJECT_ROOT, "data", "input", "post"))
        threshold = float(data.get("threshold", 3.3))
        steps = {}

        # ① 预处理（数据源适配 + Lee 滤波）
        pre = SARPreprocessor()
        pre_out = os.path.join(PATHS['processed'], 'pre')
        post_out = os.path.join(PATHS['processed'], 'post')
        pre.process_batch(pre_dir, pre_out)
        pre.process_batch(post_dir, post_out)
        pre_total = len([f for f in os.listdir(pre_out) if f.lower().endswith(('.tif', '.tiff'))])
        post_total = len([f for f in os.listdir(post_out) if f.lower().endswith(('.tif', '.tiff'))])
        steps['preprocess'] = f'完成（灾前 {pre_total} 景 / 灾后 {post_total} 景）'

        # ② 损毁检测
        det = PWDetector()
        damage = det.run_detection(pre_out, post_out, threshold)
        steps['detect'] = '完成（输出损毁栅格 + T 统计量）'

        # ③ 检测结果分析
        ana = ResultAnalyzer()
        ana.run_analysis(damage['damage'])
        steps['analyze'] = '完成（指标 + 矢量 + Excel 台账）'

        # ④ 可视化（输出到 static/cache 供前端访问）
        viz = DamageVisualizer()
        img_path = os.path.join(IMG_CACHE, "damage_result.png")
        viz.plot_from_files(damage['t_statistic'], damage['n_pre'], output=img_path, threshold=threshold)
        steps['visualize'] = '完成（损毁热力图）'

        return jsonify({
            "img_url": "cache/damage_result.png",
            "steps": steps,
            "metadata": _read_local_metadata(damage['metadata']),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/analyze_local', methods=["POST"])
def analyze_local():
    """本地量化分析"""
    if not LOCAL_AVAILABLE:
        return jsonify({"error": "本地模块未安装"})

    try:
        data = request.form
        damage_path = data.get("damage_path", os.path.join(PROJECT_ROOT, "results", "damage", "pwtt_damage.tif"))
        ground_truth_path = data.get("ground_truth_path")

        # 调用分析器
        analyzer = analyze.ResultAnalyzer()
        results = analyzer.run_analysis(damage_path, ground_truth_path)

        return jsonify({"results": results})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_local_metrics')
def get_local_metrics():
    """获取本地指标"""
    try:
        metadata_path = os.path.join(PROJECT_ROOT, "results", "damage", "metadata.json")
        metrics_path = os.path.join(PROJECT_ROOT, "results", "analysis", "metrics.json")

        metadata = {}
        metrics = {}

        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

        if os.path.exists(metrics_path):
            with open(metrics_path, 'r', encoding='utf-8') as f:
                metrics = json.load(f)

        return jsonify({
            "metadata": metadata,
            "metrics": metrics
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_local_vectors')
def get_local_vectors():
    """获取本地矢量数据"""
    try:
        geojson_path = os.path.join(PROJECT_ROOT, "results", "analysis", "damage_vectors.geojson")

        if not os.path.exists(geojson_path):
            return jsonify({"error": "矢量文件不存在"}), 404

        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson = json.load(f)

        return jsonify(geojson)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ====================== 工具函数 ======================

def _generate_local_visualization(results: dict, output_path: str):
    """生成本地结果可视化（TIFF 转 PNG）"""
    try:
        t_stat_path = results['t_statistic']

        with rasterio.open(t_stat_path) as src:
            t_stat = src.read(1)

        # 设置中文字体
        plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
        plt.rcParams["axes.unicode_minus"] = False

        # 绘图
        fig, ax = plt.subplots(figsize=(12, 10))
        im = ax.imshow(t_stat, cmap='hot', vmin=3, vmax=5)
        ax.set_title("PWTT 损毁检测结果（本地离线）")
        ax.set_xlabel("像素 X")
        ax.set_ylabel("像素 Y")
        fig.colorbar(im, ax=ax, label="T 统计量")

        plt.tight_layout()
        plt.savefig(output_path, dpi=100)
        plt.close()

    except Exception as e:
        print(f"[ERROR] 可视化生成失败: {e}")


def _read_local_metadata(metadata_path: str) -> dict:
    """读取本地元数据"""
    try:
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except:
        return {}

if __name__ == '__main__':
    # 启动后浏览器访问 http://127.0.0.1:5000
    app.run(debug=True)