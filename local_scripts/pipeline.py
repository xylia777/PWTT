"""
PWTT 本地离线完整业务链路（一键编排）— pipeline.py

串联四模块：①预处理 → ②检测 → ③分析 → ④可视化
用法：python local_scripts/pipeline.py

作者：xylia777
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PATHS, PWTT_CONFIG, ensure_directories
from local_scripts.preprocess import SARPreprocessor
from local_scripts.detect import PWDetector
from local_scripts.analyze import ResultAnalyzer
from local_scripts.visualize import DamageVisualizer


def run_full_pipeline(pre_dir: str, post_dir: str,
                      ground_truth_path: str = None, threshold: float = 3.3,
                      source: str = 'auto'):
    """完整流程：预处理 → 检测 → 分析 → 可视化"""
    print("=" * 60)
    print(" PWTT 本地离线完整业务链路")
    print("=" * 60)
    print(f" 时间: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f" 灾前: {pre_dir}\n 灾后: {post_dir}\n 阈值: {threshold} 数据源: {source}")

    # ① 预处理（数据源适配 + Lee 滤波）
    print("\n[步骤 1] SAR 数据预处理（数据源适配 + Lee 滤波）")
    pre = SARPreprocessor()
    pre_out = os.path.join(PATHS['processed'], 'pre')
    post_out = os.path.join(PATHS['processed'], 'post')
    pre.process_batch(pre_dir, pre_out, source=source)
    pre.process_batch(post_dir, post_out, source=source)

    # ② PWTT 损毁检测
    print("\n[步骤 2] PWTT 损毁检测")
    det = PWDetector()
    damage = det.run_detection(pre_out, post_out, threshold)

    # ③ 检测结果分析
    print("\n[步骤 3] 检测结果分析（精度 + 矢量 + Excel）")
    ana = ResultAnalyzer()
    analysis = ana.run_analysis(damage['damage'], ground_truth_path)

    # ④ 结果可视化
    print("\n[步骤 4] 结果可视化（损毁热力图）")
    viz = DamageVisualizer()
    viz.plot_from_files(damage['t_statistic'], damage['n_pre'], threshold=threshold)

    print("\n" + "=" * 60)
    print(" 流程完成!")
    print("=" * 60)
    return {'damage': damage, 'analysis': analysis}


def main():
    """命令行入口"""
    ensure_directories()
    pre_dir = os.path.join(PATHS['input'], 'pre')
    post_dir = os.path.join(PATHS['input'], 'post')
    ground_truth = os.path.join(PATHS['input'], 'ground_truth', 'ground_truth.tif')

    if not os.path.exists(pre_dir) or not os.listdir(pre_dir):
        print(f"[ERROR] 灾前目录不存在或为空: {pre_dir}")
        print("请先把 SAR 时序放进 data/input/pre/ 和 data/input/post/")
        return
    if not os.path.exists(post_dir) or not os.listdir(post_dir):
        print(f"[ERROR] 灾后目录不存在或为空: {post_dir}")
        return

    try:
        run_full_pipeline(pre_dir, post_dir, ground_truth, PWTT_CONFIG['threshold'])
        print("\n[OK] 完整流程执行成功!")
    except KeyboardInterrupt:
        print("\n[!] 用户中断")
    except Exception as e:
        print(f"\n[ERROR] 执行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
