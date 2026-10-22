"""分析流水线：文本 -> 字/词/语法三维度统计 -> 难度分 + 评级。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .grammar import GrammarHit, GrammarMatcher
from .loader import (
    LEVEL_NAMES,
    CharTable,
    GrammarRule,
    WordTable,
    load_chars,
    load_grammar_rules,
    load_words,
)
from .scoring import DimensionResult, build_dimension, compute_score
from .segment import Segmenter, split_sentences

MIN_WORD_LEN_FOR_DICT = 2


@dataclass
class WordItem:
    word: str
    level: int
    freq: int


@dataclass
class AnalysisResult:
    score: float
    grade: Optional[dict]
    grade_reference: str
    chars: DimensionResult
    words: DimensionResult
    grammar: DimensionResult
    per_dimension: Dict[str, float]
    note: str
    stats: dict
    grammar_hits: List[GrammarHit] = field(default_factory=list)
    advanced_words: List[WordItem] = field(default_factory=list)
    out_of_list_chars: List[str] = field(default_factory=list)
    out_of_list_words: List[str] = field(default_factory=list)


class DifficultyAnalyzer:
    def __init__(self, verbose: bool = False):
        self.chars: CharTable = load_chars()
        self.words: WordTable = load_words()
        self.rules: List[GrammarRule] = load_grammar_rules()
        self.segmenter = Segmenter(
            [w for w in self.words.level if len(w) >= MIN_WORD_LEN_FOR_DICT], verbose=verbose
        )
        self.grammar_matcher = GrammarMatcher(self.rules)
        if verbose:
            print(f"[init] 汉字 {len(self.chars)} / 词语 {len(self.words)} / 语法规则 {len(self.rules)}")

    # ------------------------------------------------------------------ #
    def analyze(self, text: str,
                oov_chars_to_top: bool = True,
                oov_words_to_top: bool = False) -> AnalysisResult:
        text = (text or "").strip()

        # ---------- 汉字维度：字种 ----------
        hanzi = [c for c in text if "\u4e00" <= c <= "\u9fff"]
        char_types = set(hanzi)
        char_counts: Dict[int, int] = {i: 0 for i in range(1, 8)}
        oov_chars: List[str] = []
        for ch in sorted(char_types):
            lvl = self.chars.get(ch)
            if lvl is None:
                oov_chars.append(ch)
            else:
                char_counts[lvl] += 1
        # 汉字：等级字表 3000 字覆盖率很高，表外字通常是真正的难字，默认计入第 7 级
        char_dim = build_dimension("汉字", char_counts, oov_chars, oov_chars_to_top)

        # ---------- 词汇维度：词种 ----------
        tokens = self.segmenter.cut(text)
        sentences = split_sentences(text)
        word_freq = Counter(tokens)
        word_counts: Dict[int, int] = {i: 0 for i in range(1, 8)}
        oov_words: List[str] = []
        advanced: List[WordItem] = []
        for w in sorted(word_freq):
            lvl = self.words.get(w)
            if lvl is None:
                oov_words.append(w)
                continue
            word_counts[lvl] += 1
            if lvl >= 5:
                advanced.append(WordItem(word=w, level=lvl, freq=word_freq[w]))
        # 词汇：分词产生的表外词多半是专名、新词或切分碎片（如「我家」「喝茶」），
        # 并非等级难度信号，因此默认不计入比例，只单独列出。
        word_dim = build_dimension("词汇", word_counts, oov_words, oov_words_to_top)
        advanced.sort(key=lambda x: (-x.level, -x.freq))

        # ---------- 语法维度：语法点类型 ----------
        hits = self.grammar_matcher.match(text, tokens, sentences)
        gram_counts: Dict[int, int] = {i: 0 for i in range(1, 8)}
        for h in hits:
            gram_counts[h.level] += 1
        gram_dim = build_dimension("语法", gram_counts, [], False)

        # ---------- 合成 ----------
        res = compute_score([char_dim, word_dim, gram_dim])
        grade = res["grade"]
        from .scoring import HSK_REFERENCE

        ref = HSK_REFERENCE.get(grade["level"], "") if grade else ""

        return AnalysisResult(
            score=res["score"],
            grade=grade,
            grade_reference=ref,
            chars=char_dim,
            words=word_dim,
            grammar=gram_dim,
            per_dimension=res["per_dimension"],
            note=res.get("note", ""),
            stats={
                "text_length": len(text),
                "hanzi_count": len(hanzi),
                "char_types": len(char_types),
                "word_tokens": len(tokens),
                "word_types": len(word_freq),
                "sentence_count": len(sentences),
                "grammar_point_types": len(hits),
                "oov_char_types": len(oov_chars),
                "oov_word_types": len(oov_words),
            },
            grammar_hits=hits,
            advanced_words=advanced,
            out_of_list_chars=oov_chars,
            out_of_list_words=oov_words,
        )

    def to_dict(self, r: AnalysisResult, include_details: bool = True) -> dict:
        def dim(d: DimensionResult) -> dict:
            return {
                "name": d.name,
                "total": d.total,
                "counts": {str(k): v for k, v in d.counts.items()},
                "ratios": {str(k): round(v, 4) for k, v in d.ratios.items()},
                "expectation": round(d.contribution, 4),
                "out_of_list_count": len(d.out_of_list),
            }

        out = {
            "score": r.score,
            "grade": r.grade,
            "grade_reference": r.grade_reference,
            "dimensions": {d.name: dim(d) for d in (r.chars, r.words, r.grammar)},
            "per_dimension": r.per_dimension,
            "stats": r.stats,
            "note": r.note,
        }
        if include_details:
            out["details"] = {
                "grammar_hits": [
                    {"level": h.level, "label": h.label, "desc": h.desc, "evidence": h.evidence}
                    for h in sorted(r.grammar_hits, key=lambda x: (x.level, x.no))
                ],
                "advanced_words": [
                    {"word": w.word, "level": w.level, "level_name": LEVEL_NAMES[w.level], "freq": w.freq}
                    for w in r.advanced_words
                ],
                "out_of_list_chars": r.out_of_list_chars[:200],
                "out_of_list_words": r.out_of_list_words[:200],
            }
        return out
