"""
统一路径配置 - PWTT 本地离线业务链路

所有路径基于项目根目录，自动创建不存在的目录。
"""

import os

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 统一路径配置
PATHS = {
    # 输入数据
    'input': os.path.join(PROJECT_ROOT, 'data', 'input'),
    'pre': os.path.join(PROJECT_ROOT, 'data', 'input', 'pre'),           # 灾前时序影像
    'post': os.path.join(PROJECT_ROOT, 'data', 'input', 'post'),          # 灾后时序影像
    'ground_truth': os.path.join(PROJECT_ROOT, 'data', 'input', 'ground_truth'),  # 真值标注

    # 处理后数据
    'processed': os.path.join(PROJECT_ROOT, 'data', 'processed'),

    # 检测结果
    'damage': os.path.join(PROJECT_ROOT, 'results', 'damage'),

    # 量化分析
    'analysis': os.path.join(PROJECT_ROOT, 'results', 'analysis'),

    # Web 展示导出
    'export': os.path.join(PROJECT_ROOT, 'results', 'export'),

    # 临时缓存
    'cache': os.path.join(PROJECT_ROOT, 'cache'),
}

# 自动创建所有目录
def ensure_directories():
    """确保所有目录存在"""
    for path in PATHS.values():
        os.makedirs(path, exist_ok=True)
    print(f"[OK] 目录结构已创建: {len(PATHS)} 个目录")


# PWTT 检测参数默认值
PWTT_CONFIG = {
    'threshold': 3.3,           # T 统计量阈值
    'pre_interval': 12,         # 战前参考期月数
    'post_interval': 2,         # 战后观测期月数
    'chunk_size': 512,          # 分块大小（避免内存溢出）
    'lee_window': 5,            # Lee 滤波窗口大小
}

# 数据源配置
DATA_SOURCE = {
    'name': '航天宏图一号',
    'type': 'C-band SAR',
    'polarization': ['VV', 'VH'],  # VV/VH 极化
    'format': 'GeoTIFF',
    'download_url': 'https://engine.piesat.cn/',
}


if __name__ == '__main__':
    ensure_directories()
    print("\n=== 路径配置 ===")
    for key, path in PATHS.items():
        print(f"{key:15} -> {path}")