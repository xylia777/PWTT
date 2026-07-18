"""
模块④：结果可视化 / 研判展示 — visualize.py

读取检测结果的 T 统计量栅格 → matplotlib 热力图（本地离线形态；Web 交互形态见 app.py）。
- 独立命令行：python local_scripts/visualize.py --t_stat <t_statistic.tif> [--n_pre <n_pre.tif>] [--output <png>]
- 被 import：    from local_scripts.visualize import DamageVisualizer

作者：xylia777
"""

import os
import sys
import argparse

# matplotlib 缓存重定向到项目内（不写 C 盘）
_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_tmp = os.path.join(_PROJ, '.tmp')
os.makedirs(_tmp, exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', os.path.join(_tmp, 'matplotlib'))

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

sys.path.insert(0, _PROJ)

try:
    import rasterio
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False

from config import PATHS


class DamageVisualizer:
    """检测结果可视化器（本地热力图 + 诊断）"""

    def __init__(self):
        plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
        plt.rcParams['axes.unicode_minus'] = False

    def plot_t_heatmap(self, t_stat: np.ndarray, n_pre=None,
                       output='damage_heatmap.png', threshold: float = 3.3):
        """画 T 统计量热力图（可选并排 n_pre 诊断图）"""
        arr_t = np.ma.masked_where(t_stat <= 0, t_stat)
        cmap_t = LinearSegmentedColormap.from_list('pwtt', ['yellow', 'red', 'purple'])
        cmap_t.set_bad('#dddddd')

        if n_pre is not None:
            arr_n = np.ma.masked_where(n_pre <= 0, n_pre)
            fig, (axT, axN) = plt.subplots(1, 2, figsize=(14, 6))
            imT = axT.imshow(arr_t, cmap=cmap_t, vmin=3, vmax=5)
            axT.set_title('T_statistic 损毁热力图')
            fig.colorbar(imT, ax=axT, label='T (>3.3 = damaged)')
            cmap_n = plt.get_cmap('viridis').copy()
            cmap_n.set_bad('#dddddd')
            imN = axN.imshow(arr_n, cmap=cmap_n, vmin=0, vmax=max(30, float(arr_n.max())))
            axN.set_title('n_pre 参考期观测数')
            fig.colorbar(imN, ax=axN, label='n_pre')
        else:
            fig, axT = plt.subplots(figsize=(8, 7))
            imT = axT.imshow(arr_t, cmap=cmap_t, vmin=3, vmax=5)
            axT.set_title('T_statistic 损毁热力图')
            fig.colorbar(imT, ax=axT, label='T (>3.3 = damaged)')

        valid = int(arr_t.count())
        damaged = int((arr_t > threshold).sum())
        ratio = 100 * damaged / valid if valid else 0
        fig.suptitle(f'PWTT 损毁检测 | T>{threshold} 损毁 {damaged}/{valid} ({ratio:.1f}%)', y=0.98)
        plt.tight_layout()
        plt.savefig(output, dpi=150)
        plt.close()
        print(f'[OK] 热力图: {output} | 损毁 {damaged}/{valid} ({ratio:.1f}%)')
        return output

    def plot_from_files(self, t_stat_path: str, n_pre_path: str = None,
                        output: str = None, threshold: float = 3.3):
        """从检测结果文件出图"""
        if not RASTERIO_AVAILABLE:
            raise RuntimeError("rasterio 未安装")
        with rasterio.open(t_stat_path) as src:
            t_stat = src.read(1)
        n_pre = None
        if n_pre_path and os.path.exists(n_pre_path):
            with rasterio.open(n_pre_path) as src:
                n_pre = src.read(1)
        if output is None:
            output = os.path.join(PATHS.get('analysis', '.'), 'damage_heatmap.png')
        return self.plot_t_heatmap(t_stat, n_pre, output, threshold)

    def read_tif_bounds(self, path: str):
        """读 GeoTIFF 经纬度范围 → [west, south, east, north]"""
        from rasterio.warp import transform_bounds
        with rasterio.open(path) as src:
            w, s, e, n = transform_bounds(src.crs, 'EPSG:4326', *src.bounds)
        return [w, s, e, n]

    def plot_damage_overlay(self, damage_path: str, output: str):
        """损毁栅格叠加图：damage>0 像素红色、背景透明（RGBA PNG，供 imageOverlay 叠底图）"""
        with rasterio.open(damage_path) as src:
            dmg = src.read(1)
        rgba = np.zeros((*dmg.shape, 4), dtype=np.uint8)
        rgba[dmg > 0] = [255, 71, 87, 200]   # 红色 半透明
        plt.imsave(output, rgba)
        print(f"[OK] 损毁叠加图: {output} | 损毁像素 {int((dmg>0).sum())}")
        return output


def main():
    parser = argparse.ArgumentParser(description='模块④ 结果可视化（本地损毁热力图）')
    parser.add_argument('--t_stat', required=True, help='T 统计量 t_statistic.tif')
    parser.add_argument('--n_pre', default=None, help='参考期观测 n_pre.tif（可选，出诊断图）')
    parser.add_argument('--output', default=None, help='输出 PNG 路径')
    parser.add_argument('--threshold', type=float, default=3.3, help='损毁阈值')
    args = parser.parse_args()
    v = DamageVisualizer()
    out = v.plot_from_files(args.t_stat, args.n_pre, args.output, args.threshold)
    print('[OK] 输出:', out)


if __name__ == '__main__':
    main()
