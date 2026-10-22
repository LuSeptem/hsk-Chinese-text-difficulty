"""语法点识别。

依据《等级标准·语法等级大纲》572 条生成的可执行规则库（data/grammar_rules.json）
在文本中匹配语法点，返回"命中的语法点类型"及其级别。

规则类型：
  lex        —— 表层词命中
  pattern    —— 正则句式
  affix      —— 词缀（前缀/后缀）
  structural —— 结构性判定（句类、句子成分等）
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Set

from .loader import GrammarRule

QUESTION_WORDS = {"吗", "呢", "吧", "什么", "谁", "哪", "哪儿", "哪里", "怎么", "怎么样",
                  "为什么", "几", "多少", "多", "是否"}
# 祈使标记：要求出现在句首附近，避免「我叫大卫」里的「叫」被误判
IMPERATIVE_MARKERS = ("请", "别", "不要", "不许", "不要", "请勿", "务必", "千万", "禁止", "快点", "快")
IMPERATIVE_AT_START = ("请", "别", "不要", "不许", "请勿", "务必", "千万", "禁止", "快")


@dataclass
class GrammarHit:
    no: str
    level: int
    label: str
    desc: str
    evidence: str  # 命中的表层证据


class GrammarMatcher:
    def __init__(self, rules: List[GrammarRule]):
        self.rules = rules
        self._compiled: Dict[str, re.Pattern] = {}
        for r in rules:
            if r.kind == "pattern" and r.pattern:
                try:
                    self._compiled[r.no] = re.compile(r.pattern)
                except re.error:
                    pass

    # ------------------------------------------------------------------ #
    # structural detectors
    # ------------------------------------------------------------------ #
    def _detect(self, detector: str, ctx: dict) -> bool:
        sents: List[str] = ctx["sentences"]
        text: str = ctx["text"]
        tokens: List[str] = ctx["tokens"]

        if detector == "ever":
            return bool(sents)
        if detector == "declarative":
            return "。" in text or bool(sents)
        if detector == "interrogative":
            if "？" in text or "?" in text:
                return True
            return any(w in text for w in QUESTION_WORDS)
        if detector == "imperative":
            # 句首标记，或句末感叹号
            for s in sents:
                s2 = s.lstrip()
                if any(s2.startswith(m) for m in IMPERATIVE_AT_START):
                    return True
            return "！" in text and len(sents) <= 3
        if detector == "exclamative":
            return "！" in text or "!" in text
        if detector == "attributive":
            return "的" in text
        if detector == "adverbial":
            return "地" in text or any(t in ("很", "非常", "太", "最", "都", "也", "还", "就") for t in tokens)
        if detector == "compound":
            # 复句：含关联词语或多于一个分句
            return len(sents) > 1 or any(
                w in text for w in ("因为", "所以", "虽然", "但是", "如果", "就", "不但", "而且", "一边")
            )
        return False

    # ------------------------------------------------------------------ #
    def match(self, text: str, tokens: List[str], sentences: List[str]) -> List[GrammarHit]:
        ctx = {"text": text, "tokens": tokens, "sentences": sentences}
        token_set: Set[str] = set(tokens)
        joined = "".join(tokens)
        hits: List[GrammarHit] = []
        seen: Set[str] = set()

        for r in self.rules:
            if r.no in seen:
                continue
            evidence = ""
            if r.kind == "lex":
                for needle in r.needles:
                    if needle in token_set:
                        evidence = needle
                        break
                    if len(needle) >= 2 and needle in joined:
                        evidence = needle
                        break
            elif r.kind == "pattern":
                pat = self._compiled.get(r.no)
                if pat is not None:
                    m = pat.search(joined)
                    if m:
                        evidence = m.group(0)
            elif r.kind == "affix":
                pos = r.position or "prefix"
                for needle in r.needles:
                    hit = None
                    for tok in tokens:
                        if pos == "prefix" and tok.startswith(needle) and len(tok) > len(needle):
                            hit = tok
                            break
                        if pos == "suffix" and tok.endswith(needle) and len(tok) > len(needle):
                            hit = tok
                            break
                    if hit:
                        evidence = hit
                        break
            elif r.kind == "structural":
                if self._detect(r.pattern or "", ctx):
                    evidence = "（结构性判定）"

            if evidence:
                seen.add(r.no)
                hits.append(
                    GrammarHit(
                        no=r.no,
                        level=r.level,
                        label=r.label,
                        desc=self._desc_of(r, evidence),
                        evidence=evidence,
                    )
                )
        return hits

    @staticmethod
    def _desc_of(r: GrammarRule, evidence: str) -> str:
        base = r.desc or r.label
        return f"{base}（命中：{evidence}）"


def hits_by_level(hits: List[GrammarHit]) -> Dict[int, List[GrammarHit]]:
    out: Dict[int, List[GrammarHit]] = {i: [] for i in range(1, 8)}
    for h in hits:
        out[h.level].append(h)
    return out
