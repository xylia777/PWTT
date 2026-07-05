"""GEE 认证 + 初始化 —— 凭据强制写入 D 盘，绝不碰 C 盘。

背景：earthengine-api 把凭据硬编码写到 ~/.config/earthengine/credentials（C 盘）。
本脚本用 monkey-patch 重定向到项目内 .gee/。
（官方测试 oauth_test.py 也是 patch.object(oauth,'get_credentials_path') 覆盖的。）

用法（在已激活 .venv 的终端里）：
  PowerShell:
    $env:GEE_PROJECT = "你的谷歌云项目ID"
    python gee_auth.py
  Git Bash:
    export GEE_PROJECT="你的谷歌云项目ID"
    python gee_auth.py

首次 ee.Authenticate() 会打开浏览器，用 Google 账号授权一次即可。
"""
import os
import sys

# 1. 凭据重定向到项目内 .gee/（必须在 import ee 后、任何 ee 调用前 patch）
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
GEE_DIR = os.path.join(PROJECT_ROOT, '.gee')
CRED_PATH = os.path.join(GEE_DIR, 'credentials')
os.makedirs(GEE_DIR, exist_ok=True)

import ee
import ee.oauth
ee.oauth.get_credentials_path = lambda: CRED_PATH  # 覆盖硬编码的 C 盘路径

# 2. 项目名从环境变量读（避免硬编码/泄露）
PROJECT = os.environ.get('GEE_PROJECT')
if not PROJECT:
    print('[!] 未设置 GEE_PROJECT 环境变量。')
    print('    PowerShell:  $env:GEE_PROJECT = "你的项目ID"')
    print('    Git Bash:    export GEE_PROJECT="你的项目ID"')
    sys.exit(1)

print(f'[*] 凭据路径: {CRED_PATH}')
print(f'[*] GEE 项目: {PROJECT}')

# 3. 认证（仅首次）
if not os.path.exists(CRED_PATH):
    print('[*] 未检测到凭据，启动浏览器认证（授权一次即可）...')
    ee.Authenticate()
else:
    print('[*] 已有凭据，跳过认证。')

# 4. 初始化并验证连通性
ee.Initialize(project=PROJECT)
_probe = ee.ImageCollection('COPERNICUS/S1_GRD_FLOAT').limit(1).size().getInfo()
print(f'[OK] GEE 初始化成功，Sentinel-1 可访问（size={_probe}）')

# 5. 确认凭据落点（守住 C 盘铁律）
_home_cred = os.path.expanduser('~/.config/earthengine/credentials')
print(f'[OK] D 盘凭据存在: {os.path.exists(CRED_PATH)}   (应 True)')
print(f'[{"OK" if not os.path.exists(_home_cred) else "WARN"}] C 盘凭据存在: {os.path.exists(_home_cred)}   (应 False)')
