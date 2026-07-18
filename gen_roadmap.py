"""生成四模块技术路线图 PNG（纯 matplotlib，缓存重定向 D 盘，不写 C 盘）。

四模块（对应 local_scripts 重构）：
  ① SAR 数据源适配与预处理  preprocess.py
  ② 损毁检测                detect.py
  ③ 检测结果分析            analyze.py
  ④ Web 业务研判展示        visualize.py + app.py
"""
import os
_tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.tmp')
os.makedirs(_tmp, exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', os.path.join(_tmp, 'matplotlib'))
os.environ.setdefault('TMP', _tmp)
os.environ.setdefault('TEMP', _tmp)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '技术路线图.png')

C1, C2, C3, C4 = '#2980b9', '#16a085', '#d35400', '#8e44ad'
INK, MUTE = '#243447', '#6b7c8c'

fig, ax = plt.subplots(figsize=(13, 14.5))
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis('off')
fig.patch.set_facecolor('white')

# 标题
ax.text(50, 97, '基础设施损毁智能检测系统 · 技术路线图', ha='center', fontsize=19, fontweight='bold', color='#1a3a5c')
ax.text(50, 93.5, 'SAR 数据源适配与预处理  →  损毁检测  →  检测结果分析  →  Web 业务研判展示',
        ha='center', fontsize=10.5, color=MUTE)


def rbox(x, y, w, h, fc, ec=None, lw=1.2, rs=0.8, z=2, alpha=1.0):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.02,rounding_size={rs}",
                 facecolor=fc, edgecolor=ec or fc, linewidth=lw, alpha=alpha, zorder=z))


def step(x, y, w, h, t, s, col):
    rbox(x, y, w, h, '#ffffff', ec=col, lw=1.5, rs=0.5)
    ax.text(x + w/2, y + h*0.63, t, ha='center', fontsize=9, fontweight='bold', color=INK)
    ax.text(x + w/2, y + h*0.30, s, ha='center', fontsize=7.5, color=MUTE)


def har(x1, x2, y, col='#bcc6d1'):
    ax.annotate('', xy=(x2, y), xytext=(x1, y), arrowprops=dict(arrowstyle='-|>', color=col, lw=1.6), zorder=5)


def var(i, label=''):
    y1 = ly(i)[1] - 0.2
    y2 = ly(i+1)[0] + 0.2
    ax.annotate('', xy=(50, y2), xytext=(50, y1), arrowprops=dict(arrowstyle='-|>', color='#bcc6d1', lw=2), zorder=5)
    if label:
        ax.text(51.8, (y1+y2)/2, label, fontsize=7.5, color=MUTE, va='center')


H, gap, ytop = 15, 4.5, 88
def ly(i):
    t = ytop - i*(H+gap)
    return t, t-H


def layer(i, col, num, name, script, core=False):
    top, bot = ly(i); x0, x1 = 4, 96
    rbox(x0, bot, x1-x0, H, '#ffffff', ec=col, lw=2.6 if core else 1.2, rs=1.0, z=1)
    if core:
        rbox(x0, bot, x1-x0, H, col, alpha=0.05, rs=1.0, z=0)
    lblw = 22
    rbox(x0+0.5, bot+0.5, lblw, H-1, col, ec=col, rs=0.9, z=2)
    cx = x0+0.5+lblw/2
    ax.text(cx, bot+H*0.72, num, ha='center', color='white', fontsize=9, zorder=3)
    ax.text(cx, bot+H*0.45, name, ha='center', color='white', fontsize=11, fontweight='bold', zorder=3)
    ax.text(cx, bot+H*0.18, script, ha='center', color='white', fontsize=8, style='italic', zorder=3)
    return x0+0.5+lblw+1.8, x1-1.5, top, bot


# ===== 模块 1：SAR 数据源适配与预处理 =====
xl, xr, top, bot = layer(0, C1, '模块 01', 'SAR数据源适配\n与预处理', 'preprocess.py')
s1 = [('数据源适配', '兼容 S1 境外/GF-3 国产'), ('Lee 滤波', '相干斑降噪 ENL=5'),
      ('掩膜过滤', '剔水体/农田'), ('标准时序输出', '统一格式')]
n = 4; sw = (xr-xl-(n-1)*1.2)/n; sy = bot+2.5; sh = H-5
for k, (t, s) in enumerate(s1):
    step(xl+k*(sw+1.2), sy, sw, sh, t, s, C1)
    if k < n-1:
        har(xl+k*(sw+1.2)+sw+0.1, xl+k*(sw+1.2)+sw+1.1, sy+sh/2)
var(0, '标准化时序影像')

# ===== 模块 2：损毁检测（核心）=====
xl, xr, top, bot = layer(1, C2, '模块 02', '损毁检测', 'detect.py', core=True)
s2 = [('时序分组', '灾前基线/灾后观测'), ('逐像素 Welch T 检验', '信噪比度量变化'), ('阈值筛选', '生成损毁栅格')]
n = 3; sw = (xr-xl-(n-1)*1.2)/n; sy = bot+2.5; sh = H-5
for k, (t, s) in enumerate(s2):
    step(xl+k*(sw+1.2), sy, sw, sh, t, s, C2)
    if k < n-1:
        har(xl+k*(sw+1.2)+sw+0.1, xl+k*(sw+1.2)+sw+1.1, sy+sh/2)
var(1, '损毁栅格 + T 统计量')

# ===== 模块 3：检测结果分析 =====
xl, xr, top, bot = layer(2, C3, '模块 03', '检测结果分析', 'analyze.py')
s3 = [('精度评估', '精确率/召回率/F1/IoU'), ('栅格转矢量', 'GeoJSON/SHP'),
      ('严重等级分级', '轻/中/重'), ('Excel 台账', '统计报表')]
n = 4; sw = (xr-xl-(n-1)*1.2)/n; sy = bot+2.5; sh = H-5
for k, (t, s) in enumerate(s3):
    step(xl+k*(sw+1.2), sy, sw, sh, t, s, C3)
    if k < n-1:
        har(xl+k*(sw+1.2)+sw+0.1, xl+k*(sw+1.2)+sw+1.1, sy+sh/2)
var(2, '指标 + 矢量 + 报表')

# ===== 模块 4：Web 业务研判展示 =====
xl, xr, top, bot = layer(3, C4, '模块 04', 'Web业务研判展示', 'visualize.py + app.py')
s4 = [('损毁热力图', '可视化展示'), ('地图框选/参数配置', '交互研判'),
      ('一键检测', '全流程自动'), ('结果导出', '报表/存档')]
n = 4; sw = (xr-xl-(n-1)*1.0)/n; sy = bot+2.5; sh = H-5
for k, (t, s) in enumerate(s4):
    step(xl+k*(sw+1.0), sy, sw, sh, t, s, C4)

# pipeline 标注 + 页脚
ax.text(50, 7.8, 'pipeline.py 一键串联  ①→②→③→④    ｜    每个模块均可独立命令行运行 / 被 import 封装',
        ha='center', fontsize=8, color='#334155', fontweight='bold')
ax.text(50, 3.5, '技术基线：Ballinger (2025), Remote Sensing of Environment 331:115025   |   '
        '内网离线优先 · 国产SAR适配 · 兼容 S1/国产两类数据源',
        ha='center', fontsize=8, color=MUTE)

plt.savefig(OUT, dpi=180, bbox_inches='tight', facecolor='white')
print('[OK] 技术路线图已生成:', OUT)
