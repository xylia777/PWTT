"""
模块②：PWTT 损毁检测 — detect.py

纯本地离线，无 GEE 依赖。核心：逐像素 Welch 不等方差 T 检验。
- 独立命令行：python local_scripts/detect.py --pre <灾前目录> --post <灾后目录> --threshold 3.3
- 被 import：    from local_scripts.detect import PWDetector

作者：xylia777
"""

import os
import sys
import argparse
import json
from typing import Tuple, Dict, Optional
import numpy as np
try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import rasterio
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False

from config import PATHS, PWTT_CONFIG


class PWDetector:
    """PWTT 损毁检测器（本地离线）"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or PWTT_CONFIG
        self.paths = PATHS
        print(f"[OK] PWDetector 初始化 | 阈值: {self.config['threshold']} | 分块: {self.config['chunk_size']}")

    def welch_ttest(self, pre_samples: np.ndarray, post_samples: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Welch 不等方差 T 检验（逐像素）"""
        pre_mean = np.nanmean(pre_samples, axis=0)
        post_mean = np.nanmean(post_samples, axis=0)
        pre_var = np.nanvar(pre_samples, axis=0, ddof=1)
        post_var = np.nanvar(post_samples, axis=0, ddof=1)
        n_pre = pre_samples.shape[0]
        n_post = post_samples.shape[0]
        pre_var = np.maximum(pre_var, 1e-10)
        post_var = np.maximum(post_var, 1e-10)
        var_pre_n = pre_var / n_pre
        var_post_n = post_var / n_post
        denom = np.sqrt(var_pre_n + var_post_n)
        t_statistic = np.abs(post_mean - pre_mean) / denom
        df_num = (var_pre_n + var_post_n) ** 2
        df_den = (var_pre_n ** 2 / (n_pre - 1)) + (var_post_n ** 2 / (n_post - 1))
        degrees_of_freedom = df_num / np.maximum(df_den, 1e-10)
        degrees_of_freedom = np.clip(degrees_of_freedom, 1, 10000)
        return t_statistic, degrees_of_freedom

    def two_tailed_pvalue(self, t_statistic: np.ndarray, degrees_of_freedom: np.ndarray) -> np.ndarray:
        """双尾 p 值（正态近似，df>30）"""
        if not SCIPY_AVAILABLE:
            raise RuntimeError("scipy 未安装，p 值不可算。运行: python local_scripts/install_local_deps.py")
        p_values = 2 * (1 - stats.norm.cdf(t_statistic))
        return np.maximum(p_values, 1e-10)

    def compute_tmap(self, pre_data: np.ndarray, post_data: np.ndarray,
                     chunk_size: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """分块计算 T 图（防爆内存）。支持 [time,H,W] 单波段 或 [time,H,W,bands] 多波段（各波段取 max）"""
        if chunk_size is None:
            chunk_size = self.config['chunk_size']
        single = (pre_data.ndim == 3)
        bands = 1 if single else pre_data.shape[-1]
        height, width = pre_data.shape[1], pre_data.shape[2]
        t_statistic = np.zeros((height, width))
        degrees_of_freedom = np.zeros((height, width))
        n_pre = np.full((height, width), pre_data.shape[0])
        print(f"[*] 分块计算 T 图: chunk={chunk_size} | 影像 {height}x{width} | 波段 {bands}")
        cnt = 0
        for i in range(0, height, chunk_size):
            for j in range(0, width, chunk_size):
                i_end, j_end = min(i + chunk_size, height), min(j + chunk_size, width)
                t_max, df_first = None, None
                for b in range(bands):
                    pc = pre_data[:, i:i_end, j:j_end] if single else pre_data[:, i:i_end, j:j_end, b]
                    qc = post_data[:, i:i_end, j:j_end] if single else post_data[:, i:i_end, j:j_end, b]
                    t_b, df_b = self.welch_ttest(pc, qc)
                    t_max = t_b if t_max is None else np.maximum(t_max, t_b)
                    if b == 0:
                        df_first = df_b
                t_statistic[i:i_end, j:j_end] = t_max
                degrees_of_freedom[i:i_end, j:j_end] = df_first
                cnt += 1
                if cnt % 10 == 0:
                    print(f"    进度: {cnt} 块")
        print(f"[OK] T 图完成: {cnt} 块")
        return t_statistic, degrees_of_freedom, n_pre

    def apply_threshold(self, t_statistic: np.ndarray, threshold: Optional[float] = None,
                        n_pre: Optional[np.ndarray] = None, min_obs: int = 3) -> Tuple[np.ndarray, np.ndarray]:
        """阈值筛选生成损毁掩膜"""
        if threshold is None:
            threshold = self.config['threshold']
        damage_mask = (t_statistic > threshold).astype(np.uint8)
        if n_pre is not None:
            damage_mask = damage_mask * (n_pre >= min_obs).astype(np.uint8)
        p_value = self.two_tailed_pvalue(t_statistic, n_pre)
        print(f"[OK] 阈值筛选 | T>{threshold} 损毁: {damage_mask.sum()}/{damage_mask.size} "
              f"({100*damage_mask.sum()/damage_mask.size:.2f}%)")
        return damage_mask, p_value

    def load_timeseries(self, directory: str) -> Optional[np.ndarray]:
        """加载处理后时序 TIFF → [time, H, W, bands]"""
        if not RASTERIO_AVAILABLE:
            raise RuntimeError("rasterio 未安装")
        if not os.path.exists(directory):
            print(f"[ERROR] 目录不存在: {directory}")
            return None
        tiffs = sorted([f for f in os.listdir(directory) if f.lower().endswith(('.tif', '.tiff'))])
        if not tiffs:
            print(f"[ERROR] 目录无 TIFF: {directory}")
            return None
        print(f"[*] 加载时序: {len(tiffs)} 个 | {directory}")
        series = []
        for fn in tiffs:
            try:
                with rasterio.open(os.path.join(directory, fn)) as src:
                    image = src.read()
                    if image.ndim == 2:
                        image = image[:, :, np.newaxis]
                    elif image.ndim == 3:
                        image = np.transpose(image, (1, 2, 0))
                    series.append(image)
            except Exception as e:
                print(f"[WARNING] 读取失败 {fn}: {e}")
        if not series:
            return None
        # 各景尺寸可能略不同（S1 不同切片/时间），crop 到最小公共 shape 再 stack
        min_h = min(s.shape[0] for s in series)
        min_w = min(s.shape[1] for s in series)
        if any(s.shape[:2] != (min_h, min_w) for s in series):
            print(f"[!] 各景尺寸不一，裁到最小公共 {min_h}x{min_w}")
            series = [s[:min_h, :min_w] for s in series]
        ts = np.stack(series, axis=0)
        print(f"[OK] 时序加载: {ts.shape}")
        return ts

    def run_detection(self, pre_dir: str, post_dir: str, threshold: Optional[float] = None) -> Dict[str, str]:
        """完整检测流程：加载 → T 图 → 阈值 → 存结果"""
        if not RASTERIO_AVAILABLE:
            raise RuntimeError("rasterio 未安装")
        print("\n=== PWTT 损毁检测 ===")
        pre_data = self.load_timeseries(pre_dir)
        post_data = self.load_timeseries(post_dir)
        if pre_data is None or post_data is None:
            raise RuntimeError("时序加载失败")

        t_statistic, _, n_pre = self.compute_tmap(pre_data, post_data)
        damage_mask, _ = self.apply_threshold(t_statistic, threshold, n_pre)

        output_dir = self.paths['damage']
        os.makedirs(output_dir, exist_ok=True)
        damage_path = os.path.join(output_dir, 'pwtt_damage.tif')
        t_stat_path = os.path.join(output_dir, 'pwtt_t_statistic.tif')
        n_pre_path = os.path.join(output_dir, 'pwtt_n_pre.tif')
        self._write_tiff(damage_path, damage_mask, pre_data.shape[1:3])
        self._write_tiff(t_stat_path, t_statistic, pre_data.shape[1:3])
        self._write_tiff(n_pre_path, n_pre, pre_data.shape[1:3])

        metadata = {
            'threshold': self.config['threshold'], 'pre_interval': self.config['pre_interval'],
            'post_interval': self.config['post_interval'], 'chunk_size': self.config['chunk_size'],
            'shape': list(pre_data.shape[1:3]),
            'pre_files': os.listdir(pre_dir) if os.path.exists(pre_dir) else [],
            'post_files': os.listdir(post_dir) if os.path.exists(post_dir) else [],
            'timestamp': datetime.now().isoformat(),
            'statistics': {
                'total_pixels': int(damage_mask.size),
                'damage_pixels': int(damage_mask.sum()),
                'damage_ratio': float(damage_mask.sum() / damage_mask.size),
                'mean_t_statistic': float(t_statistic.mean()),
                'max_t_statistic': float(t_statistic.max()),
            }
        }
        metadata_path = os.path.join(output_dir, 'metadata.json')
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"[OK] 检测完成 → {damage_path}")
        return {'damage': damage_path, 't_statistic': t_stat_path, 'n_pre': n_pre_path, 'metadata': metadata_path}

    def _write_tiff(self, path: str, data: np.ndarray, shape: Tuple[int, int]):
        if data.ndim == 2:
            data = data[np.newaxis, :, :]
        with rasterio.open(path, 'w', driver='GTiff', height=shape[0], width=shape[1],
                           count=data.shape[0], dtype=data.dtype, crs='EPSG:4326',
                           transform=rasterio.transform.from_bounds(0, 0, shape[1], shape[0], shape[1], shape[0])) as dst:
            dst.write(data)


def main():
    parser = argparse.ArgumentParser(description='模块② PWTT 损毁检测（本地离线）')
    parser.add_argument('--pre', required=True, help='灾前处理后时序目录')
    parser.add_argument('--post', required=True, help='灾后处理后时序目录')
    parser.add_argument('--threshold', type=float, default=3.3, help='损毁判定阈值')
    args = parser.parse_args()
    d = PWDetector()
    r = d.run_detection(args.pre, args.post, args.threshold)
    print('[OK] 输出:', r)


if __name__ == '__main__':
    main()
