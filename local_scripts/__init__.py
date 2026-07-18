"""
local_scripts —— PWTT 本地离线工具链（四模块）

模块对应：
  preprocess  ① SAR 数据预处理（含数据源适配 S1/国产 + Lee 滤波 + 掩膜）
  detect      ② PWTT 损毁检测（逐像素 Welch T 检验）
  analyze     ③ 检测结果分析（精度/矢量/Excel 台账）
  visualize   ④ 结果可视化（损毁热力图）
  pipeline     一键串联 ①→②→③→④

每个模块既可独立命令行运行，也可被 import 封装为工具。
"""

from .preprocess import SARPreprocessor
from .detect import PWDetector
from .analyze import ResultAnalyzer
from .visualize import DamageVisualizer

__all__ = ['SARPreprocessor', 'PWDetector', 'ResultAnalyzer', 'DamageVisualizer']
