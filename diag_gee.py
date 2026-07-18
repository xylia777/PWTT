"""诊断 GEE 连接：为什么 app.py 里 GEE_AVAILABLE=False？

用法（在【设了 GEE_PROJECT 的那个终端】里跑）：
  python diag_gee.py
然后把输出全部贴回来。
"""
import os
import sys
import traceback

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CRED_PATH = os.path.join(PROJECT_ROOT, '.gee', 'credentials')

print('=' * 55)
print('[1] 凭据文件检查')
print(f'    路径: {CRED_PATH}')
print(f'    存在: {os.path.exists(CRED_PATH)}')

import ee
import ee.oauth
ee.oauth.get_credentials_path = lambda: CRED_PATH

PROJECT = os.environ.get('GEE_PROJECT')
print('=' * 55)
print('[2] GEE_PROJECT 环境变量')
print(f'    值: {PROJECT!r}')
if not PROJECT:
    print('    [!] 未设置！app.py 会拿占位默认值去 Initialize，必然失败。')
    print('        PowerShell:  $env:GEE_PROJECT = "你的真实项目ID"')
    print('        Git Bash:    export GEE_PROJECT="你的真实项目ID"')
    sys.exit(1)
if PROJECT in ('你的GEE项目ID', '你的项目ID', 'YOUR-PROJECT'):
    print('    [!] 这是占位字符串，不是真实项目ID！换成你 Google Cloud 的真实项目ID。')

print('=' * 55)
print('[3] 凭据内容（不显示 token）')
try:
    import json
    with open(CRED_PATH) as f:
        cred = json.load(f)
    print(f'    project 字段: {cred.get("project")!r}')
    print(f'    refresh_token: {"有" if cred.get("refresh_token") else "无"}')
    print(f'    client_id: {"有" if cred.get("client_id") else "无"}')
except Exception as e:
    print(f'    读凭据失败: {e}')

print('=' * 55)
print(f'[4] 尝试 ee.Initialize(project={PROJECT!r}) ...')
try:
    ee.Initialize(project=PROJECT)
    print('    [OK] Initialize 成功！')
    n = ee.ImageCollection('COPERNICUS/S1_GRD_FLOAT').limit(1).size().getInfo()
    print(f'    [OK] 探针成功，Sentinel-1 可访问 (size={n})')
    print('    => GEE 本身没问题。若 app.py 仍报"云端不可用"，')
    print('       唯一可能：启动 app.py 的那个终端没设 GEE_PROJECT。')
except Exception as e:
    print(f'    [FAIL] Initialize 抛异常，完整 traceback：')
    traceback.print_exc()
    print()
    print('    常见原因对照：')
    print('    - "Project ... not found"           → 项目ID拼错')
    print('    - "not authorized" / 403            → 该项目没启用 Earth Engine API，')
    print('                                          或账号没在 earthengine.google.com 注册该项目')
    print('    - "invalid_grant" / refresh_token   → 凭据过期，重跑 python gee_auth.py')
    print('    - 网络超时                          → 访问 googleapis.com 受限')
print('=' * 55)
