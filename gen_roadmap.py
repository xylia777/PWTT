"""生成 PWTT 项目四层技术架构图 PNG（纯 matplotlib，不依赖 GEE）。

所有缓存（matplotlib 字体缓存、临时文件）重定向到项目内 .tmp/，不写 C 盘。
输出：技术路线图.png
"""
import os
# --- 必须在 import matplotlib 之前重定向缓存到 D 盘 ---
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
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis('off')
fig.patch.set_facecolor('white')

# 标题
ax.text(50, 97, '基础设施损毁智能检测系统 · 技术架构图', ha='center', fontsize=19, fontweight='bold', color='#1a3a5c')
ax.text(50, 93.5, '基于 PWTT 像素级 T 检验算法  ·  内网离线全流程四层架构', ha='center', fontsize=10.5, color=MUTE)


def rbox(x, y, w, h, fc, ec=None, lw=1.2, rs=0.8, z=2, alpha=1.0):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                 boxstyle=f"round,pad=0.02,rounding_size={rs}",
                 facecolor=fc, edgecolor=ec or fc, linewidth=lw, alpha=alpha, zorder=z))


def step(x, y, w, h, t, s, col):
    rbox(x, y, w, h, '#ffffff', ec=col, lw=1.5, rs=0.5)
    ax.text(x + w/2, y + h*0.63, t, ha='center', fontsize=9, fontweight='bold', color=INK)
    ax.text(x + w/2, y + h*0.30, s, ha='center', fontsize=7.5, color=MUTE)


def har(x1, x2, y, col='#bcc6d1'):
    ax.annotate('', xy=(x2, y), xytext=(x1, y),
                arrowprops=dict(arrowstyle='-|>', color=col, lw=1.6), zorder=5)


def var(i, label=''):
    y1 = ly(i)[1] - 0.2
    y2 = ly(i+1)[0] + 0.2
    ax.annotate('', xy=(50, y2), xytext=(50, y1),
                arrowprops=dict(arrowstyle='-|>', color='#bcc6d1', lw=2), zorder=5)
    if label:
        ax.text(51.8, (y1+y2)/2, label, fontsize=7.5, color=MUTE, va='center')


H, gap, ytop = 15, 4.5, 88
def ly(i):
    t = ytop - i*(H+gap); return t, t-H


def layer(i, col, num, name, tag, core=False):
    top, bot = ly(i); x0, x1 = 4, 96
    rbox(x0, bot, x1-x0, H, '#ffffff', ec=col, lw=2.6 if core else 1.2, rs=1.0, z=1)
    if core:
        rbox(x0, bot, x1-x0, H, col, alpha=0.05, rs=1.0, z=0)
    lblw = 21
    rbox(x0+0.5, bot+0.5, lblw, H-1, col, ec=col, rs=0.9, z=2)
    cx = x0+0.5+lblw/2
    ax.text(cx, bot+H*0.72, num, ha='center', color='white', fontsize=8.5, zorder=3)
    ax.text(cx, bot+H*0.46, name, ha='center', color='white', fontsize=11, fontweight='bold', zorder=3)
    ax.text(cx, bot+H*0.18, tag, ha='center', color='white', fontsize=7.3, style='italic', zorder=3)
    return x0+0.5+lblw+1.8, x1-1.5, top, bot


# ===== 第一层 数据源 =====
xl, xr, top, bot = layer(0, C1, 'LAYER 01', '多源SAR\n数据源适配层', '数据入口·双模式隔离')
cw = (xr-xl)/2 - 1
rbox(xl, bot+1.2, cw, H-2.4, '#f3f8fb', ec='#cfe0ec', lw=1, rs=0.5)
ax.text(xl+cw/2, bot+H-2.6, '内网业务数据源（正式业务·断网可用）', ha='center', fontsize=8.6, fontweight='bold', color=C1)
for j, t in enumerate(['国产高分三号、陆地一号 SAR 时序影像', '自然资源卫星中心公益申领标准栅格', '本地/内网存储，全程数据不出域']):
    ax.text(xl+1.2, bot+H-4.6-j*2.0, '· ' + t, fontsize=7.8, color='#3a4a5a')
rbox(xl+cw+2, bot+1.2, cw, H-2.4, '#fdf3ee', ec='#f0cdb6', lw=1, rs=0.5)
ax.text(xl+cw+2+cw/2, bot+H-2.6, '外网演示预留接口（仅算法验证）', ha='center', fontsize=8.6, fontweight='bold', color='#b5481a')
for j, t in enumerate(['预留 GEE 平台对接通道', '调取 Sentinel-1 境外卫星影像', '仅加沙/顿巴斯演示，正式部署可关闭']):
    ax.text(xl+cw+2+1.2, bot+H-4.6-j*2.0, '· ' + t, fontsize=7.8, color='#3a4a5a')
var(0, '统一数据标准转换 → 标准化时序影像')

# ===== 第二层 预处理 =====
xl, xr, top, bot = layer(1, C2, 'LAYER 02', '影像全自动\n预处理引擎', '前置降噪提纯·无人值守')
ax.text(xl, bot+H-2.2, '批量导入后全自动流水线，无需人工操作', fontsize=8.2, color=C2, fontweight='bold')
s2 = [('① 观测角度统一', '消除多角度偏差'), ('② 斑点噪声去除', 'Lee滤波·建筑清晰'),
      ('③ 非监测区筛除', '剔除水体/农田等'), ('④ 标准化输出', '送入分析核心')]
n = 4; sw = (xr-xl-(n-1)*1.2)/n; sy = bot+1.4; sh = H-6
for k, (t, s) in enumerate(s2):
    sx = xl+k*(sw+1.2); step(sx, sy, sw, sh, t, s, C2)
    if k < n-1:
        har(sx+sw+0.1, sx+sw+1.1, sy+sh/2)
var(1, '净化后时序影像')

# ===== 第三层 分析内核（核心）=====
xl, xr, top, bot = layer(2, C3, 'LAYER 03·核心', 'PWTT建筑损毁\n分析内核', '纯本地离线·无GEE依赖', core=True)
ax.text(xl, bot+H-2.2, '像素级 T 检验 · 信噪比度量均值显著变化 · 不依赖云端算力', fontsize=8.0, color=C3, fontweight='bold')
s3 = [('① 时序分组', '灾前基线/灾后观测'), ('② 逐像素时序对比', '雷达反射特征变化'),
      ('③ PWTT统计识别', '判定坍塌损毁')]
n = 3; sw = (xr-xl-(n-1)*1.2)/n; sy = bot+1.4; sh = H-6
for k, (t, s) in enumerate(s3):
    sx = xl+k*(sw+1.2); step(sx, sy, sw, sh, t, s, C3)
    if k < n-1:
        har(sx+sw+0.1, sx+sw+1.1, sy+sh/2)
var(2, '成果：全域损毁热力栅格 + 分区域量化统计 → 推送 Web')

# ===== 第四层 Web 应用 =====
xl, xr, top, bot = layer(3, C4, 'LAYER 04', '轻量化Web\n可视化应用', '浏览器即用·面向业务人员')
s4 = [('区域框选', '地图选监测区'), ('参数配置', '时间/灵敏度'), ('一键启动', '全流程自动'),
      ('实时展示', '热力图+统计'), ('一键导出', '报表/存档')]
n = 5; sw = (xr-xl-(n-1)*1.0)/n; sy = bot+2.5; sh = H-5
for k, (t, s) in enumerate(s4):
    step(xl+k*(sw+1.0), sy, sw, sh, t, s, C4)

# 页脚
ax.text(50, 2.5, '技术基线：Ballinger (2025), Remote Sensing of Environment 331:115025   |   '
        '内网离线优先 · 国产SAR适配 · 全自动流水线 · 浏览器交付',
        ha='center', fontsize=8, color=MUTE)

plt.savefig(OUT, dpi=180, bbox_inches='tight', facecolor='white')
print('[OK] 架构图已生成:', OUT)
