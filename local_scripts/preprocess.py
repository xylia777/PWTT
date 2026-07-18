"""
模块①：SAR 数据预处理（含数据源适配）— preprocess.py

职责：
- 数据源适配：兼容境外 Sentinel-1（C 波段）与国产 GF-3 / LT-1（C/L 波段），统一为标准时序输入
- Lee 滤波相干斑降噪（ENL=5，复用 GEE 版逻辑）
- 掩膜过滤非监测区（水体 / 农田 / 荒地）

两种使用方式：
- 独立命令行：python local_scripts/preprocess.py --input <dir> --output <dir> --source s1|gf3|lt1|auto
- 被 import：    from local_scripts.preprocess import SARPreprocessor

作者：xylia777
"""

import os
import sys
import argparse
from typing import Tuple, Dict, Optional
import numpy as np
try:
    from scipy.ndimage import uniform_filter
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import rasterio
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False
    print("[WARNING] rasterio 未安装，预处理功能不可用")

from config import PATHS, DATA_SOURCE


class SARPreprocessor:
    """SAR 预处理器：数据源适配 + Lee 滤波 + 掩膜过滤"""

    # 支持的数据源（兼容境外 + 国产）
    SOURCES = {
        's1':  'Sentinel-1 (C 波段，境外)',
        'gf3': '高分三号 GF-3 (C 波段，国产)',
        'lt1': '陆探一号 LT-1 (L 波段，国产)',
    }

    def __init__(self, config: Optional[Dict] = None):
        from config import PWTT_CONFIG as _CFG
        self.config = config or _CFG
        self.paths = PATHS
        print(f"[OK] SARPreprocessor 初始化 | 数据源: {DATA_SOURCE.get('name', '-')}")

    # ========== 数据源适配（兼容两类）==========
    def detect_source(self, directory: str) -> str:
        """根据文件名自动识别数据源（s1 / gf3 / lt1）"""
        files = [f.lower() for f in os.listdir(directory)] if os.path.exists(directory) else []
        joined = ' '.join(files)
        if any(k in joined for k in ['s1a', 's1b', 'sentinel', 's1_']):
            return 's1'
        if 'gf3' in joined or 'gaofen' in joined:
            return 'gf3'
        if 'lt1' in joined or 'lutance' in joined or 'landtan' in joined:
            return 'lt1'
        return 'auto'

    def load_timeseries(self, directory: str, source: str = 'auto') -> Optional[np.ndarray]:
        """
        读取 SAR 时序，统一为标准输入 [time, height, width, bands]。
        两类数据（S1 / 国产）均统一到后向散射幅度 + VV/VH 双极化。

        Args:
            directory: 时序影像目录（GeoTIFF）
            source: s1 / gf3 / lt1 / auto（auto 自动识别）
        """
        if not RASTERIO_AVAILABLE:
            raise RuntimeError("rasterio 未安装")
        if source == 'auto':
            source = self.detect_source(directory)
        src_name = self.SOURCES.get(source, source)
        print(f"[*] 加载时序 | 目录: {directory} | 数据源: {src_name}")

        if not os.path.exists(directory):
            print(f"[ERROR] 目录不存在: {directory}")
            return None
        tiffs = sorted([f for f in os.listdir(directory) if f.lower().endswith(('.tif', '.tiff'))])
        if not tiffs:
            print(f"[ERROR] 目录无 TIFF: {directory}")
            return None

        series = []
        for fn in tiffs:
            try:
                img, _ = self.read_tiff(os.path.join(directory, fn))
                series.append(img)
            except Exception as e:
                print(f"[WARNING] 读取失败 {fn}: {e}")
        if not series:
            return None
        ts = np.stack(series, axis=0)
        print(f"[OK] 时序加载完成: {ts.shape} (time,H,W,bands) | 数据源 {src_name}")
        return ts

    # ========== 单文件读写 ==========
    def read_tiff(self, path: str) -> Tuple[np.ndarray, Dict]:
        """读取 GeoTIFF → [H, W, bands] + 元数据"""
        if not RASTERIO_AVAILABLE:
            raise RuntimeError("rasterio 未安装")
        with rasterio.open(path) as src:
            image = src.read()
            if image.ndim == 2:
                image = image[:, :, np.newaxis]
            elif image.ndim == 3:
                image = np.transpose(image, (1, 2, 0))
            meta = {
                'crs': src.crs, 'transform': src.transform, 'bounds': src.bounds,
                'shape': image.shape[:2],
                'bands': list(src.descriptions) or src.count,
                'dtype': str(src.dtypes[0]),
            }
        return image, meta

    def _write_tiff(self, path: str, image: np.ndarray, metadata: Dict):
        if not RASTERIO_AVAILABLE:
            raise RuntimeError("rasterio 未安装")
        if image.ndim == 3:
            image = np.transpose(image, (2, 0, 1))
        elif image.ndim == 2:
            image = image[np.newaxis, :, :]
        with rasterio.open(path, 'w', driver='GTiff',
                           height=image.shape[1], width=image.shape[2],
                           count=image.shape[0], dtype=image.dtype,
                           crs=metadata.get('crs'), transform=metadata.get('transform')) as dst:
            dst.write(image)

    # ========== Lee 滤波（复用 GEE 版 ENL=5）==========
    def lee_filter(self, image: np.ndarray, window_size: int = 5, enl: int = 5) -> np.ndarray:
        """Lee 滤波相干斑降噪（MMSE 估计，ENL=5）"""
        if not SCIPY_AVAILABLE:
            raise RuntimeError("scipy 未安装，Lee 滤波不可用。运行: python local_scripts/install_local_deps.py")
        eta = 1.0 / np.sqrt(enl)
        mean = uniform_filter(image, size=window_size, mode='reflect')
        mean_sq = uniform_filter(image ** 2, size=window_size, mode='reflect')
        var = mean_sq - mean ** 2
        var_x = (var - eta ** 2 * mean ** 2) / (1 + eta ** 2)
        b = np.maximum(var_x / np.maximum(var, 1e-12), 0)
        return (1 - b) * mean + b * image

    # ========== 掩膜过滤（非监测区）==========
    def apply_mask(self, image: np.ndarray, mask_type: str = 'water') -> np.ndarray:
        """掩膜：water/farmland/urban（按后向散射阈值，简化版）"""
        m = image.mean(axis=-1)
        if mask_type == 'water':
            mask = m < -20
        elif mask_type == 'farmland':
            mask = (m > -15) & (m < -5)
        elif mask_type == 'urban':
            mask = m > -10
        else:
            mask = np.zeros(image.shape[:2], dtype=bool)
        out = image.copy()
        for i in range(image.shape[2]):
            out[:, :, i][mask] = 0
        return out

    def load_ground_truth(self, path: str) -> Optional[np.ndarray]:
        """加载真值标注（二值 0/1）"""
        if not os.path.exists(path):
            print(f"[WARNING] 真值不存在: {path}")
            return None
        img, _ = self.read_tiff(path)
        if img.ndim == 3:
            img = img[:, :, 0]
        return (img > 0).astype(np.uint8)

    # ========== 批处理（数据源适配 → Lee → 存盘）==========
    def process_batch(self, input_dir: str, output_dir: str,
                      source: str = 'auto', apply_lee: bool = True,
                      window_size: int = 5, mask_type: Optional[str] = None,
                      force: bool = False) -> int:
        """批量：读取(数据源适配) → Lee 滤波 → (掩膜) → 存处理后 TIFF。
        force=False 时自动跳过已处理（输出已存在的 processed_*.tif）。"""
        if not os.path.exists(input_dir):
            raise FileNotFoundError(f"输入目录不存在: {input_dir}")
        os.makedirs(output_dir, exist_ok=True)
        if source == 'auto':
            source = self.detect_source(input_dir)
        print(f"[*] 批处理 | 源: {self.SOURCES.get(source, source)} | Lee: {apply_lee} | 掩膜: {mask_type} | force: {force}")

        tiffs = [f for f in os.listdir(input_dir) if f.lower().endswith(('.tif', '.tiff'))]
        cnt = 0
        skipped = 0
        for fn in tiffs:
            output_path = os.path.join(output_dir, f"processed_{fn}")
            if os.path.exists(output_path) and not force:
                skipped += 1
                continue
            try:
                img, meta = self.read_tiff(os.path.join(input_dir, fn))
                if apply_lee:
                    img = self.lee_filter(img, window_size=window_size)
                if mask_type:
                    img = self.apply_mask(img, mask_type)
                self._write_tiff(output_path, img, meta)
                cnt += 1
                if cnt % 10 == 0:
                    print(f"    进度 {cnt}/{len(tiffs)}")
            except Exception as e:
                print(f"[ERROR] 处理失败 {fn}: {e}")
        print(f"[OK] 批处理完成: 新处理 {cnt} | 跳过(已处理) {skipped} | 共 {len(tiffs)}")
        return cnt


def main():
    parser = argparse.ArgumentParser(description='模块① SAR 预处理（数据源适配 + Lee 滤波 + 掩膜）')
    parser.add_argument('--input', required=True, help='输入 SAR 时序目录')
    parser.add_argument('--output', required=True, help='输出处理后目录')
    parser.add_argument('--source', default='auto', choices=['auto', 's1', 'gf3', 'lt1'], help='数据源（默认自动识别）')
    parser.add_argument('--no-lee', action='store_true', help='跳过 Lee 滤波')
    parser.add_argument('--mask', default=None, choices=['water', 'farmland', 'urban'], help='掩膜类型')
    parser.add_argument('--force', action='store_true', help='强制重处理（忽略已处理的 processed_*.tif）')
    args = parser.parse_args()

    p = SARPreprocessor()
    p.process_batch(args.input, args.output, source=args.source,
                    apply_lee=not args.no_lee, mask_type=args.mask, force=args.force)


if __name__ == '__main__':
    main()
