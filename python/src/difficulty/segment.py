"""中文分词与文本预处理。

分词采用 jieba，并把《等级标准》词汇表（长度 ≥ 2 的词）注入用户词典，
以提高等级词的召回率——这与论文用 LTP 分词的做法思路一致，只是工程上更轻量。
"""

from __future__ import annotations

import re
from typing import Iterable, List, Tuple

import jieba
import jieba.posseg as pseg

CJK = re.compile(r"^[一-鿿]+$")
# 句子终结符
SENT_SPLIT = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?")
# 非汉字（用于提取字种时过滤）
NON_HAN = re.compile(r"[^一-鿿]")


class Segmenter:
    def __init__(self, words: Iterable[str] | None = None, verbose: bool = False):
        if words:
            n = 0
            for w in words:
                # 只注入多字词，避免干扰 jieba 的单字切分
                if len(w) >= 2 and CJK.match(w):
                    jieba.add_word(w, freq=200)
                    n += 1
            if verbose:
                print(f"[segment] 注入等级词 {n} 条")
        self.ready = True

    def cut(self, text: str) -> List[str]:
        """返回词 token 列表（已过滤空白与纯标点）。"""
        out = []
        for tok in jieba.cut(text):
            tok = tok.strip()
            if not tok:
                continue
            if CJK.match(tok):
                out.append(tok)
        return out

    def cut_pos(self, text: str) -> List[Tuple[str, str]]:
        out = []
        for w, flag in pseg.cut(text):
            w = w.strip()
            if w and CJK.match(w):
                out.append((w, flag))
        return out


def split_sentences(text: str) -> List[str]:
    return [s.strip() for s in SENT_SPLIT.findall(text) if s.strip()]


def extract_hanzi(text: str) -> List[str]:
    """提取全部汉字序列（去标点、数字、英文字母）。"""
    return [c for c in text if CJK.match(c)]
