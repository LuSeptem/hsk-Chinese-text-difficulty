"""分级数据加载层。

数据来自《国际中文教育中文水平等级标准》(GF 0025-2021) 的公开整理版：
  - 汉字表 3000 字：300/300/300/300/300/300/1200（1~6 级 + 7—9 级）
  - 词汇表 11092 词：500/772/973/1000/1071/1140/5636
  - 语法等级大纲 572 条：48/81/81/76/71/67/148
级别统一映射：'1'..'6' -> 1..6，'7-9' -> 7。
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
RAW_DIR = DATA_DIR / "raw"

CHARS_CSV = RAW_DIR / "hsk30-chars.csv"
WORDS_CSV = RAW_DIR / "hsk30.csv"
GRAMMAR_CSV = RAW_DIR / "hsk30-grammar.csv"
GRAMMAR_RULES_JSON = DATA_DIR / "grammar_rules.json"

LEVEL_NAMES = {1: "一级", 2: "二级", 3: "三级", 4: "四级", 5: "五级", 6: "六级", 7: "七—九级"}
LEVEL_ALIAS = {"1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "7-9": 7, "7—9": 7}


def _norm_level(raw: str) -> Optional[int]:
    return LEVEL_ALIAS.get((raw or "").strip())


def _csv_rows(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@dataclass
class CharTable:
    """汉字 -> 级别"""

    level: Dict[str, int] = field(default_factory=dict)

    def get(self, ch: str) -> Optional[int]:
        return self.level.get(ch)

    def __len__(self) -> int:
        return len(self.level)


@dataclass
class WordTable:
    """词语 -> 级别（含词性）"""

    level: Dict[str, int] = field(default_factory=dict)
    pos: Dict[str, str] = field(default_factory=dict)

    def get(self, w: str) -> Optional[int]:
        return self.level.get(w)

    def __len__(self) -> int:
        return len(self.level)


@dataclass
class GrammarPoint:
    no: str
    level: int
    group: str
    category: str
    details: str
    content: str

    @property
    def label(self) -> str:
        parts = [p for p in (self.group, self.category, self.details) if p and p != "-"]
        return "／".join(dict.fromkeys(parts))


@dataclass
class GrammarRule:
    """一条可执行的语法点识别规则。"""

    no: str
    level: int
    label: str
    kind: str  # lex | pattern | affix | structural
    needles: List[str] = field(default_factory=list)  # kind=lex / affix：待匹配的表层形式
    pattern: str = ""  # kind=pattern：正则；kind=structural：detector 名
    position: str = ""  # kind=affix：prefix / suffix
    desc: str = ""  # 规则说明，用于结果展示


# --------------------------------------------------------------------------- #
# 载入
# --------------------------------------------------------------------------- #


def load_chars(path: Path = CHARS_CSV) -> CharTable:
    table = CharTable()
    for row in _csv_rows(path):
        hanzi = (row.get("Hanzi") or "").strip()
        lvl = _norm_level(row.get("Level", ""))
        if not hanzi or lvl is None:
            continue
        # 同一字若在多级出现（理论不应发生），取最低级
        if hanzi not in table.level or lvl < table.level[hanzi]:
            table.level[hanzi] = lvl
    return table


_DIGIT_TAIL = re.compile(r"[0-9０-９]+$")
_PAREN = re.compile(r"[（(][^）)]*[）)]")


def _clean_word(s: str) -> List[str]:
    """把一个词条展开成若干可用的简体表层形式。"""
    s = (s or "").strip()
    if not s:
        return []
    out: List[str] = []
    if s.startswith("["):  # Variants 是 JSON 数组
        try:
            for v in json.loads(s):
                w = (v.get("Simplified") or "").strip()
                if w and not v.get("Example"):
                    out.append(w)
        except Exception:
            pass
        return [w for w in out if w]

    # "爸爸|爸"、"零|〇" 之类
    for part in re.split(r"[|｜/／]", s):
        part = _PAREN.sub("", part).strip()
        part = _DIGIT_TAIL.sub("", part).strip()
        if part:
            out.append(part)
    return out


def load_words(path: Path = WORDS_CSV) -> WordTable:
    table = WordTable()
    for row in _csv_rows(path):
        lvl = _norm_level(row.get("Level", ""))
        if lvl is None:
            continue
        pos = (row.get("POS") or "").strip()
        forms = _clean_word(row.get("Simplified", ""))
        variants = row.get("Variants", "")
        if variants and variants.strip().startswith("["):
            forms += _clean_word(variants)
        for w in forms:
            # 词缀条目（Prefix/Suffix）单独成词意义不大，但单字词本身仍保留
            if w not in table.level or lvl < table.level[w]:
                table.level[w] = lvl
                if w not in table.pos:
                    table.pos[w] = pos
    return table


def load_grammar(path: Path = GRAMMAR_CSV) -> List[GrammarPoint]:
    points: List[GrammarPoint] = []
    for row in _csv_rows(path):
        lvl = _norm_level(row.get("Level", ""))
        if lvl is None:
            continue
        points.append(
            GrammarPoint(
                no=(row.get("No") or "").strip(),
                level=lvl,
                group=(row.get("Group") or "").strip(),
                category=(row.get("Category") or "").strip(),
                details=(row.get("Details") or "").strip(),
                content=(row.get("Content") or "").strip(),
            )
        )
    return points


def load_grammar_rules(path: Path = GRAMMAR_RULES_JSON) -> List[GrammarRule]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    out: List[GrammarRule] = []
    for grp in raw:
        for r in grp.get("rules", []):
            out.append(
                GrammarRule(
                    no=grp.get("no", ""),
                    level=int(grp.get("level", 1)),
                    label=grp.get("label", ""),
                    kind=r.get("kind", "lex"),
                    needles=r.get("needles", []),
                    # structural 规则把 detector 名放在 pattern 字段
                    pattern=r.get("pattern", "") or r.get("detector", ""),
                    position=r.get("position", ""),
                    desc=r.get("desc", "") or grp.get("label", ""),
                )
            )
    return out
