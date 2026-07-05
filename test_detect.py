"""最小复现：Gaza 小区域 + 默认 stouffer 方法。

前置：先运行 python gee_auth.py 完成认证（凭据在 .gee/credentials）。
验证：默认 stouffer 路径（修复 make_orbit_s1 -> make_group_collection 后）能正常出图。
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CRED_PATH = os.path.join(PROJECT_ROOT, '.gee', 'credentials')

if not os.path.exists(CRED_PATH):
    sys.exit('[!] 无凭据，请先运行: python gee_auth.py')

import ee
import ee.oauth
ee.oauth.get_credentials_path = lambda: CRED_PATH

PROJECT = os.environ.get('GEE_PROJECT')
if not PROJECT:
    sys.exit('[!] 请设置 GEE_PROJECT 环境变量（同 gee_auth.py）')
ee.Initialize(project=PROJECT)

import pwtt

# 论文示例：Gaza，战前 12 月参考期 + 1 月推理窗口
gaza = ee.Geometry.Rectangle([34.21, 31.21, 34.57, 31.60])
print('[*] detect_damage（默认 stouffer）开始，首次较慢（GEE 拉数据）...')
img = pwtt.detect_damage(
    aoi=gaza,
    war_start='2023-10-10',
    inference_start='2024-07-01',
    pre_interval=12,
    post_interval=1,
    viz=False,
)
bands = img.bandNames().getInfo()
print(f'[OK] 输出波段: {bands}')
print('[OK] 默认 stouffer 路径可用，Bug 修复验证通过')
