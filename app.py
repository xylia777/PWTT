import os
import sys
import numpy as np
from flask import Flask, render_template, request, jsonify, send_file
import ee
import geemap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# ====================== GEE 凭据复用（和你原有代码完全一致） ======================
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CRED_PATH = os.path.join(PROJECT_ROOT, '.gee', 'credentials')
if not os.path.exists(CRED_PATH):
    sys.exit('[!] 无凭据，请先运行: python gee_auth.py')
ee.oauth.get_credentials_path = lambda: CRED_PATH
PROJECT = os.environ.get('GEE_PROJECT', '你的GEE项目ID')
ee.Initialize(project=PROJECT)

# 导入你的PWTT算法
import pwtt

app = Flask(__name__)
# 临时图片缓存目录
IMG_CACHE = os.path.join(PROJECT_ROOT, "static", "cache")
os.makedirs(IMG_CACHE, exist_ok=True)

# 生成热力图函数（复用你原有绘图逻辑）
def generate_pwtt_img(bbox, war_start, inference_start, pre_interval, post_interval, threshold=3.3):
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
    return "cache/result.png"

# 首页：左右分栏页面
@app.route('/')
def index():
    return render_template("index.html")

# 接口：接收前端参数，生成图片
@app.route('/run_pwtt', methods=["POST"])
def run_pwtt():
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
    img_path = generate_pwtt_img(bbox, war_start, inference_start, pre_interval, post_interval, threshold)
    return jsonify({"img_url": img_path})

# 图片下载接口
@app.route('/download')
def download_img():
    path = os.path.join(IMG_CACHE, "result.png")
    return send_file(path, as_attachment=True, download_name="pwtt_result.png")

if __name__ == '__main__':
    # 启动后浏览器访问 http://127.0.0.1:5000
    app.run(debug=True)