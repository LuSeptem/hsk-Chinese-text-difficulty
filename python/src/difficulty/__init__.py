"""汉语二语文本阅读难度自动分级。

实现依据：程勇、董军、晋淑华《基于新标准的汉语二语文本阅读难度分级体系
构建与应用》，《世界汉语教学》2023 年第 1 期。
"""

from .pipeline import AnalysisResult, DifficultyAnalyzer  # noqa: F401
from .scoring import GRADE_BANDS, HSK_REFERENCE  # noqa: F401

__all__ = ["DifficultyAnalyzer", "AnalysisResult", "GRADE_BANDS", "HSK_REFERENCE"]
