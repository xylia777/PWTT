"""
快速安装本地离线依赖

用法：
    python install_local_deps.py

作者：xylia777
日期：2026-07-07
"""

import sys
import subprocess

LOCAL_DEPS = [
    "rasterio>=1.3.0",
    "numpy>=1.24.0",
    "scipy>=1.10.0",
    "scikit-image>=0.21.0",
    "geopandas>=0.13.0",
    "shapely>=2.0.0",
    "openpyxl>=3.1.0",
    "Pillow>=10.0.0",
]

def install():
    print("=" * 60)
    print(" 安装本地离线依赖")
    print("=" * 60)

    # 尝试安装每个依赖
    for dep in LOCAL_DEPS:
        print(f"\n[*] 安装 {dep}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
            print(f"[OK] {dep} 安装成功")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] {dep} 安装失败: {e}")
            continue

    print("\n" + "=" * 60)
    print(" 安装完成!")
    print("=" * 60)
    print("\n 现在可以运行:")
    print("  python pipeline.py")
    print("  python app.py")


if __name__ == "__main__":
    install()