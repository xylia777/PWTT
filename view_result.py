"""出图：Gaza PWTT 损毁热力图（T_statistic 波段）。

把 detect_damage 的 T_statistic 从 GEE 拉到本地 numpy，用 matplotlib 画热力图。
配色对齐 README：yellow→red→purple，vmin=3 / vmax=5，>3.3 视为损毁。
PNG 存项目根目录（D 盘），不依赖 Google Drive。

前置：已运行 python gee_auth.py 完成认证。
用法：
  PowerShell:  $env:GEE_PROJECT="你的项目ID"; python view_result.py
  Git Bash:    export GEE_PROJECT="你的项目ID"; python view_result.py
"""
import os
import sys

import numpy as np

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
import geemap
import matplotlib
matplotlib.use('Agg')  # 无界面后端，直接存文件
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# ---- 1. 算（默认 stouffer，Bug 已修复）----
BBOX = [34.21, 31.21, 34.57, 31.60]  # Gaza [w, s, e, n]
gaza = ee.Geometry.Rectangle(BBOX)
print('[*] detect_damage（默认 stouffer）...')
img = pwtt.detect_damage(
    aoi=gaza,
    war_start='2023-10-10',
    inference_start='2024-07-01',
    pre_interval=12,
    post_interval=1,
)

# ---- 2. 一次性拉 T_statistic + n_pre 到本地（多波段，省一次 GEE 请求）----
print('[*] 下载 T_statistic + n_pre 到本地（scale=100m）...')
stack = geemap.ee_to_numpy(img.select(['T_statistic', 'n_pre']), region=gaza, scale=100)
arr = np.ma.masked_where(stack[:, :, 0] <= 0, stack[:, :, 0])   # T_statistic
npre = np.ma.masked_where(stack[:, :, 1] <= 0, stack[:, :, 1])  # 参考期观测数
valid = int(arr.count())
print(f'[*] shape={stack.shape}, 有效像素={valid}')
print(f'[*] n_pre 范围: {float(npre.min()):.0f}~{float(npre.max()):.0f}  (参考期每像素观测数)')

damaged = int((arr > 3.3).sum())
if valid:
    print(f'[*] T>3.3 像素: {damaged}/{valid} = {100*damaged/valid:.1f}% (像素级，非建筑级)')

# ---- 3. 并排画 T_statistic + n_pre，诊断紫条真伪 ----
extent = [BBOX[0], BBOX[2], BBOX[1], BBOX[3]]  # [w, e, s, n]

cmap_t = LinearSegmentedColormap.from_list('pwtt', ['yellow', 'red', 'purple'])
cmap_t.set_bad('#dddddd')
cmap_n = plt.get_cmap('viridis').copy()
cmap_n.set_bad('#dddddd')

fig, (axT, axN) = plt.subplots(1, 2, figsize=(15, 8))
imT = axT.imshow(arr, cmap=cmap_t, vmin=3, vmax=5, extent=extent)
axT.set_title('T_statistic  (>3.3 = damaged)')
axT.set_xlabel('Longitude'); axT.set_ylabel('Latitude')
fig.colorbar(imT, ax=axT, label='T_statistic')

imN = axN.imshow(npre, cmap=cmap_n, vmin=0, vmax=max(30, float(npre.max())), extent=extent)
axN.set_title('n_pre  (reference-period obs count)\n(purple band on low n_pre (<5) => artifact, not real damage)')
axN.set_xlabel('Longitude'); axN.set_ylabel('Latitude')
fig.colorbar(imN, ax=axN, label='n_pre')

fig.suptitle('Gaza PWTT  war_start=2023-10-10  inference=2024-07-01', y=0.98)
out = os.path.join(PROJECT_ROOT, 'gaza_damage_T.png')
plt.tight_layout()
plt.savefig(out, dpi=150)
print(f'[OK] 并排诊断图已保存: {out}')
