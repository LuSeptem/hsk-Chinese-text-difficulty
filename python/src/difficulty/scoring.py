"""难度计算与分级。

论文公式（程勇、董军、晋淑华，2023）：

    文本难度 = (1/3) × Σ_{n=1..7}  n × [ r_char(n) + r_word(n) + r_grammar(n) ]

其中
    r_char(n)    = n 级字种数 / 总字种数
    r_word(n)    = n 级词种数 / 总词种数
    r_grammar(n) = n 级语法点类型数 / 总语法点类型数

分级阈值取自论文表 8：
    [1, 1.4)     一级
    [1.4, 1.75)  二级
    [1.75, 2)    三级
    [2, 2.3)     四级
    [2.3, 2.55)  五级
    [2.55, 2.7)  六级
    [2.7, 7]     七—九级
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .loader import LEVEL_NAMES

MAX_LEVEL = 7

# 论文表 8 的分级区间（下闭上开）
GRADE_BANDS: List[tuple] = [
    (1.0, 1.4, 1, "一级"),
    (1.4, 1.75, 2, "二级"),
    (1.75, 2.0, 3, "三级"),
    (2.0, 2.3, 4, "四级"),
    (2.3, 2.55, 5, "五级"),
    (2.55, 2.7, 6, "六级"),
    (2.7, 7.01, 7, "七—九级"),
]

# HSK 3.0 / CEFR 参考映射（辅助说明用，非论文内容）
HSK_REFERENCE: Dict[int, str] = {
    1: "HSK 一级（1 级）/ CEFR pre-A1",
    2: "HSK 二级（2 级）/ CEFR A1",
    3: "HSK 三级（3 级）/ CEFR A1—A2",
    4: "HSK 四级（4 级）/ CEFR A2—B1",
    5: "HSK 五级（5 级）/ CEFR B1—B2",
    6: "HSK 六级（6 级）/ CEFR B2—C1",
    7: "HSK 七—九级 / CEFR C1—C2",
}


@dataclass
class DimensionResult:
    """一个维度（字 / 词 / 语法）的统计结果。"""

    name: str
    total: int  # 分母（字种数 / 词种数 / 语法点类型数）
    counts: Dict[int, int] = field(default_factory=dict)  # 级别 -> 数量
    ratios: Dict[int, float] = field(default_factory=dict)  # 级别 -> 比例
    out_of_list: List[str] = field(default_factory=list)  # 超纲项
    contribution: float = 0.0  # Σ n × r(n)

    @property
    def expectation(self) -> float:
        return self.contribution


def build_dimension(name: str, counts: Dict[int, int], out_of_list: List[str],
                    oov_to_top: bool = True) -> DimensionResult:
    """按级别计数构造维度结果。

    oov_to_top=True：超纲项（不在等级表中的字/词）计入第 7 级，
    保证 Σ r(n) = 1，与论文"总字种数 / 总词种数"的分母口径一致。
    """
    counts = dict(counts)
    if oov_to_top and out_of_list:
        counts[MAX_LEVEL] = counts.get(MAX_LEVEL, 0) + len(out_of_list)
    total = sum(counts.values())
    ratios = {i: (counts.get(i, 0) / total if total else 0.0) for i in range(1, MAX_LEVEL + 1)}
    contribution = sum(i * ratios.get(i, 0.0) for i in range(1, MAX_LEVEL + 1))
    return DimensionResult(
        name=name,
        total=total,
        counts={i: counts.get(i, 0) for i in range(1, MAX_LEVEL + 1)},
        ratios=ratios,
        out_of_list=out_of_list,
        contribution=contribution,
    )


def grade_of(score: float) -> Dict:
    for lo, hi, lvl, name in GRADE_BANDS:
        if lo <= score < hi:
            return {"level": lvl, "name": name, "range": f"[{lo:g}, {hi:g})"}
    # 兜底
    return {"level": MAX_LEVEL, "name": LEVEL_NAMES[MAX_LEVEL], "range": "[2.7, 7]"}


def compute_score(dims: List[DimensionResult]) -> Dict:
    """按论文公式合成难度分。

    若某一维度完全无数据（例如文本过短、未识别到任何语法点），
    则只在有效维度间重新归一化，避免把总分无端拉低。
    """
    valid = [d for d in dims if d.total > 0]
    if not valid:
        return {"score": 0.0, "grade": None, "used": [], "note": "文本中没有可分析的汉字"}

    mean = sum(d.contribution for d in valid) / len(valid)
    score = round(mean, 4)
    grade = grade_of(score)
    note = ""
    if len(valid) < len(dims):
        missing = [d.name for d in dims if d.total <= 0]
        note = f"以下维度未识别到内容，已按剩余 {len(valid)} 个维度平均：{'、'.join(missing)}"
    return {
        "score": score,
        "grade": grade,
        "used": [d.name for d in valid],
        "note": note,
        "per_dimension": {d.name: round(d.contribution, 4) for d in dims},
    }
