"""下载极小区域 Sentinel-1 测试数据 —— 乌克兰马里乌波尔战区（47°N 38°E，0.1°×0.1°）

灾前 5 景（2021-03 ~ 2022-02，war 2022-02-24 前 12 月）+ 灾后 5 景（2022-03 ~ 2022-05）
→ data/input/pre/ + data/input/post/，供 local_scripts 跑通「预处理→检测→分析→可视化」全链路。

体积小：0.1°×0.1° ≈ 7×11 km，scale=20m，单景 ~350×550 像素 × 2 波段(VV+VH)，每景几十 KB~MB。

用法（设了 GEE_PROJECT 的终端）：
  python data/download_test_data.py

注：走 GEE 下载，需 GEE 可用（凭据在 .gee/）。配额受限模式可能限流，失败就等重置重跑。
"""
import os
import sys

PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ_ROOT)

CRED = os.path.join(PROJ_ROOT, '.gee', 'credentials')
import ee
import ee.oauth
ee.oauth.get_credentials_path = lambda: CRED
PROJECT = os.environ.get('GEE_PROJECT', 'pwtt-academic-2026')
ee.Initialize(project=PROJECT)
import geemap

# ===== 可调参数 =====
# AOI：乌克兰马里乌波尔附近战区 0.1°×0.1°（[west, south, east, north]）
AOI = ee.Geometry.Rectangle([37.90, 47.00, 38.00, 47.10])
PRE_N, POST_N = 5, 5          # 灾前/灾后各取几景（PWTT 最低 pre>=3 post>=2；越多越稳）
SCALE = 20                     # 分辨率（米），S1 IW 约 20m
# ====================


def fetch(date_start, date_end, n, out_dir, prefix):
    """取一个时间窗口的 S1 时序，导出每景为 GeoTIFF（VV+VH，log dB）"""
    os.makedirs(out_dir, exist_ok=True)
    col = (ee.ImageCollection('COPERNICUS/S1_GRD_FLOAT')
           .filterBounds(AOI)
           .filterDate(date_start, date_end)
           .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
           .filter(ee.Filter.eq('instrumentMode', 'IW'))
           .select(['VV', 'VH'])
           .limit(n))
    n_actual = min(col.size().getInfo(), n)
    print(f'[*] {prefix}: {n_actual} 景  ({date_start} ~ {date_end})')
    imgs = col.toList(n_actual)
    for i in range(n_actual):
        out = os.path.join(out_dir, f'{prefix}_{i:02d}.tif')
        print(f'    [{i+1}/{n_actual}] 导出 → {out}')
        # .log() 转 dB（与 PWTT GEE 版 detect_damage 内部 image.log() 一致）
        geemap.ee_export_image(ee.Image(imgs.get(i)).log(),
                               filename=out, region=AOI, scale=SCALE)
    return n_actual


if __name__ == '__main__':
    print('=== AOI ===')
    print('    乌克兰马里乌波尔战区 37.90–38.00°E · 47.00–47.10°N (0.1°×0.1°)')
    print('    war_start = 2022-02-24（俄乌冲突）')

    print('\n=== 下载灾前时序（基线）===')
    n1 = fetch('2021-03-01', '2022-02-23', PRE_N,
               os.path.join(PROJ_ROOT, 'data', 'input', 'pre'), 's1_pre')
    print('\n=== 下载灾后时序 ===')
    n2 = fetch('2022-03-01', '2022-05-31', POST_N,
               os.path.join(PROJ_ROOT, 'data', 'input', 'post'), 's1_post')

    print(f'\n[OK] 完成：灾前 {n1} 景 + 灾后 {n2} 景，已放 data/input/pre + data/input/post')
    print('    下一步：python local_scripts/pipeline.py  一键跑通全链路')
