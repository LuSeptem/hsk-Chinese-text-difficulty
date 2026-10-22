"""由《国际中文教育中文水平等级标准》语法等级大纲生成可执行的识别规则库。

用法：
    uv run python tools/build_grammar_rules.py

产物：data/grammar_rules.json

规则分为四类：
  lex        —— 表层词命中（词表类语法点，如能愿动词、量词、副词）
  pattern    —— 正则句式（复句关联词、固定格式）
  structural —— 结构性判定（句类、句子成分等，由 detector 命名函数实现）
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from difficulty.loader import load_grammar, GRAMMAR_RULES_JSON  # noqa: E402

# --------------------------------------------------------------------------- #
# 清洗工具
# --------------------------------------------------------------------------- #

# （1）（2）编号
_NUM_MARK = re.compile(r"[（(]\s*[0-9一二三四五六七八九十]+\s*[）)]")
# 括号内容
_PAREN_ANY = re.compile(r"[（(][^（()）]*[）)]")
# 数字尾巴：都1 / 还1 / 可1
_DIGIT_TAIL = re.compile(r"[0-9０-９]+$")
_CJK = re.compile(r"^[一-鿿]+$")
_LATIN_ONLY = re.compile(r"^[A-Za-z]+$")

# 语法范畴术语，不应作为表层词去匹配
CATEGORY_STOP = {
    "名词", "动词", "形容词", "副词", "代词", "数词", "量词", "介词", "连词", "助词",
    "叹词", "拟声词", "主语", "谓语", "宾语", "定语", "状语", "补语", "中心语",
    "名词性词语", "动词性词语", "形容词性词语", "名词性短语", "动词性短语", "形容词性短语",
    "其他成分", "数量短语", "关联词语", "单句", "复句", "其他结构类型", "复合量词",
    "名量词", "动量词", "借用量词", "方位名词", "时间", "处所", "对象", "方向", "路径",
    "无标记", "不用关联词语", "用关联词语", "表示存在", "表示领有", "表处置", "表致使",
    "表示等同或类属", "表示说明或特征", "表示评价、达到", "意念被动句",
    "表示前后动作先后发生", "前后两个动词性词语具有因果、转折、条件关系",
    "强调时间、地点、方式、动作者", "强调说话人的看法或态度",
    "表示等同或类属", "不用关联词语",
}

# 占位符：A / B / X / AA / ABAB / 动词（+宾语1）
_PLACEHOLDER = re.compile(r"^[A-Z]$|^(A|B|X)(A|B)?$|^(AA|ABAB|A一A|A了A)$")


def _is_placeholder(tok: str) -> bool:
    t = tok.strip()
    if not t:
        return True
    if _LATIN_ONLY.match(t):
        return True
    if _PLACEHOLDER.match(t):
        return True
    return False


def _clean_token(tok: str) -> list[str]:
    """把一个片段清洗成若干可匹配的字面形式（处理 '/' 并列）。"""
    tok = _PAREN_ANY.sub("", tok)
    tok = tok.replace("+", "").replace("～", "").replace("~", "")
    tok = tok.strip(" ：:，,、。.；;　\"'“”‘’")
    if not tok:
        return []
    out = []
    for alt in re.split(r"[/／]", tok):
        alt = _DIGIT_TAIL.sub("", alt.strip())
        alt = alt.strip(" ：:，,、。.；;　\"'“”‘’")
        if not alt:
            continue
        if _is_placeholder(alt):
            continue
        if alt in CATEGORY_STOP:
            continue
        if not _CJK.match(alt):
            continue
        if len(alt) > 6:  # 过长的多半是说明文字而非句式
            continue
        out.append(alt)
    return out


def _esc(s: str) -> str:
    return re.escape(s)


# --------------------------------------------------------------------------- #
# 由 Content 派生规则
# --------------------------------------------------------------------------- #

_ELLIPSIS = re.compile(r"…{1,4}|\.{2,6}|…")


def derive_from_content(content: str) -> list[dict]:
    """返回若干 rule 片段 dict：{'kind':'lex','needles':[...]} 或 {'kind':'pattern','pattern':...}"""
    rules: list[dict] = []
    text = (content or "").replace("……", "…").replace("。。", "。")
    if not text:
        return rules

    for seg in re.split(r"[；;]", text):
        seg = _NUM_MARK.sub("", seg)
        seg = seg.strip()
        if not seg:
            continue

        if "…" in seg:
            # 句式模式：先……，再/然后……
            parts = _ELLIPSIS.split(seg)
            literals: list[list[str]] = []
            for p in parts:
                p2 = p.strip(" ，,、：:。.;；　")
                # 去掉被逗号分隔的尾部说明
                alts = _clean_token(p2)
                literals.append(alts)
            # 过滤：至少有一个真实字面片段
            if not any(literals):
                continue
            pieces: list[str] = []
            for i, alts in enumerate(literals):
                if not alts:
                    pieces.append(r".{0,14}?")
                    continue
                grp = "|".join(_esc(a) for a in alts)
                pieces.append(f"(?:{grp})" if len(alts) > 1 else grp)
                pieces.append(r".{0,14}?")
            # 去掉末尾多余的通配
            while pieces and pieces[-1] == r".{0,14}?":
                pieces.pop()
            # 去掉开头多余的通配
            while pieces and pieces[0] == r".{0,14}?":
                pieces.pop(0)
            if not pieces:
                continue
            pat = "".join(pieces)
            if len(pat) < 2:
                continue
            rules.append({"kind": "pattern", "pattern": pat})

            # 只有单侧有字面片段时（如「越来越…」「…也好」），才额外登记词表规则。
            # 双侧都有的（如「先……，再……」）不能再退化成词表，否则单靠「了」「也」就会误命中。
            solid = [alts for alts in literals if alts]
            if len(solid) == 1:
                needles = sorted(set(solid[0]))
                if needles:
                    rules.append({"kind": "lex", "needles": needles})
        else:
            # 词表式：上、下、里、外…；或单个词
            needles: list[str] = []
            for piece in re.split(r"[、,，]", seg):
                needles.extend(_clean_token(piece))
            needles = sorted(set(needles))
            if needles:
                rules.append({"kind": "lex", "needles": needles})
    return rules


# --------------------------------------------------------------------------- #
# 结构化语法点的手写 detector
# --------------------------------------------------------------------------- #

# 只有能给出真实判定条件的句类/句子成分才做结构性判定。
# 无法判定的（如「句群」「特殊表达法」）宁可不覆盖，也不要无条件命中——
# 否则会把高级别语法点无端计入，显著抬高难度分。
STRUCTURAL_RULES: list[dict] = [
    # 句类
    dict(group="句子的类型", category="句类", details="陈述句",
         detector="declarative", desc="陈述句"),
    dict(group="句子的类型", category="句类", details="疑问句",
         detector="interrogative", desc="疑问句"),
    dict(group="句子的类型", category="句类", details="祈使句",
         detector="imperative", desc="祈使句"),
    dict(group="句子的类型", category="句类", details="感叹句",
         detector="exclamative", desc="感叹句"),
    # 句子成分（仅限一级，这些在任何句子里都成立）
    dict(group="句子成分", category="主语", levels=[1],
         detector="ever", desc="主语（名词、代词或名词性短语）"),
    dict(group="句子成分", category="谓语", levels=[1],
         detector="ever", desc="谓语（动词性/形容词性短语）"),
    dict(group="句子成分", category="宾语", levels=[1],
         detector="ever", desc="宾语"),
    dict(group="句子成分", category="定语", levels=[1],
         detector="attributive", desc="定语（“的”前修饰语）"),
    dict(group="句子成分", category="状语", levels=[1],
         detector="adverbial", desc="状语（副词/形容词作状语）"),
    # 句型
    dict(group="句子的类型", category="句型", details="单句", levels=[1],
         detector="ever", desc="单句"),
    dict(group="句子的类型", category="句型", details="复句",
         detector="compound", desc="复句（含关联词语或多分句）"),
    # 提问的方法
    dict(group="提问的方法", detector="interrogative", desc="提问表达"),
]


# 特殊表达法：按 Category 关键字给出真实的正则是可行的
EXPRESSION_PATTERNS: list[tuple[str, str, str]] = [
    ("钱数", r"[0-9０-９一二三四五六七八九十百千万]{1,8}(?:元|块钱|块|角|毛|分钱|分)", "钱数表示法"),
    ("时间", r"(?:[0-9０-９一二三四五六七八九十]{1,4}(?:年|月|日|号|点|点钟|分钟|小时|秒)|星期[一二三四五六日天]|周[一二三四五六日天])",
     "时间表示法"),
    ("序数", r"第[0-9０-９一二三四五六七八九十]{0,4}", "序数表示法"),
    ("概数", r"[0-9０-９一二三四五六七八九十]{1,4}(?:多|来|几|左右|上下|有余)", "概数表示法"),
    ("分数", r"[0-9０-９一二三四五六七八九十]{1,4}分之[0-9０-９一二三四五六七八九十]{1,4}", "分数表示法"),
    ("倍数", r"[0-9０-９一二三四五六七八九十]{1,4}倍", "倍数表示法"),
    ("小数", r"[0-9０-９]{1,4}\.[0-9０-９]{1,4}", "小数表示法"),
    ("百分数", r"[0-9０-９]{1,4}(?:\.[0-9０-９]{1,3})?%|百分之[0-9０-９一二三四五六七八九十]{1,4}", "百分数表示法"),
]


def match_expression(point) -> list[dict]:
    if point.group != "特殊表达法":
        return []
    text = (point.category or "") + (point.details or "")
    out = []
    for key, pat, desc in EXPRESSION_PATTERNS:
        if key in text:
            out.append({"kind": "pattern", "pattern": pat, "desc": desc})
    return out


def match_structural(point) -> dict | None:
    for r in STRUCTURAL_RULES:
        if r.get("group") and r["group"] != point.group:
            continue
        if r.get("category") and r["category"] != point.category:
            continue
        if r.get("details") and r["details"] not in point.details:
            continue
        if r.get("levels") and point.level not in r["levels"]:
            continue
        return r
    return None


# --------------------------------------------------------------------------- #
# 特殊句型的手写规则（Content 只给语义说明，没有表层标记）
# key = (Group, Category 子串, Details 子串)
# --------------------------------------------------------------------------- #

CURATED: list[dict] = [
    dict(group="句子的类型", category="特殊句型", details="“是”字句",
         kind="pattern", pattern="是", desc="“是”字句"),
    dict(group="句子的类型", category="特殊句型", details="“有”字句",
         kind="pattern", pattern="有", desc="“有”字句"),
    dict(group="句子的类型", category="特殊句型", details="“是……的”句",
         kind="pattern", pattern=r"是.{0,14}?的", desc="“是……的”句"),
    dict(group="句子的类型", category="特殊句型", details="“把”字句",
         kind="pattern", pattern=r"把.{0,16}?[的地得]?", desc="“把”字句"),
    dict(group="句子的类型", category="特殊句型", details="被动句",
         kind="pattern", pattern=r"被[^。！？；]{0,14}?(?:所)?", desc="被动句"),
    dict(group="句子的类型", category="特殊句型", details="比较句",
         kind="pattern", pattern=r"(?:比|跟|和|与)[^。！？；]{0,10}?(?:一样|相同|相比|差不多|更|还)",
         desc="比较句"),
    dict(group="句子的类型", category="特殊句型", details="兼语句",
         kind="pattern", pattern=r"(?:请|使|派|选|称|命令|要求)[^。！？；]{0,12}", desc="兼语句"),
    dict(group="句子的类型", category="特殊句型", details="双宾语句",
         kind="lex", needles=["送给", "告诉", "教给", "借给", "还给", "递给"], desc="双宾语句"),
    # 短语
    dict(group="短语", category="功能类型", details="名词性短语", kind="structural", detector="ever", desc="名词性短语"),
    dict(group="短语", category="功能类型", details="动词性短语", kind="structural", detector="ever", desc="动词性短语"),
    dict(group="短语", category="功能类型", details="形容词性短语", kind="structural", detector="ever", desc="形容词性短语"),
    dict(group="短语", category="其他结构类型", details="", kind="pattern",
         pattern=r"[0-9０-９一二三四五六七八九十百千]{1,6}[个本只件张条块杯瓶双对群片份年天岁块]",
         desc="数量短语"),
    dict(group="短语", category="固定短语", kind="lex", needles=["不一会儿", "什么的"], desc="固定短语"),
    dict(group="短语", category="数量重叠", kind="pattern",
         pattern=r"[0-9一二三四五六七八九十]{1,3}([个本只件张条]).{0,2}?[0-9一二三四五六七八九十]{1,3}\1",
         desc="数量重叠"),
    # 动作的态（按级别区分，避免「了」把所有态一次点满）
    dict(group="动作的态", details="完成态", kind="pattern", pattern=r"[一-鿿]{1,4}了", desc="完成态（了）"),
    dict(group="动作的态", details="变化态", kind="pattern", pattern=r"[一-鿿]{1,4}了", desc="变化态（了）"),
    dict(group="动作的态", details="进行态", kind="pattern",
         pattern=r"(?:正在|正|在)[一-鿿]{1,6}|[一-鿿]{1,6}呢", desc="进行态（正在/呢）"),
    dict(group="动作的态", details="持续态", kind="pattern", pattern=r"[一-鿿]{1,4}着", desc="持续态（着）"),
    dict(group="动作的态", details="经历态", kind="pattern", pattern=r"[一-鿿]{1,4}过", desc="经历态（过）"),
]


def match_curated(point) -> list[dict]:
    out: list[dict] = []
    for c in CURATED:
        if c.get("group") and c["group"] != point.group:
            continue
        if c.get("category") and c["category"] not in point.category:
            continue
        if c.get("details") and c["details"] not in point.details:
            continue
        rule = {"kind": c["kind"], "desc": c["desc"]}
        if c["kind"] == "pattern":
            rule["pattern"] = c["pattern"]
        elif c["kind"] == "lex":
            rule["needles"] = c["needles"]
        elif c["kind"] == "structural":
            rule["detector"] = c["detector"]
        out.append(rule)
    return out


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #


# 这些组的句式写在 Category 字段里（Content 为空）
PATTERN_IN_CATEGORY = {"固定格式", "口语格式", "强调的方法", "提问的方法", "特殊表达法"}
# 语素组的词缀写在 Details 字段里
AFFIX_GROUP = "语素"


def _extract_quoted(text: str) -> str:
    """提取 “……” 中的句式，如 用“连……也/都……”表示强调 -> 连……也/都……"""
    m = re.findall(r"[“\"]([^”\"]{1,40})[”\"]", text)
    return "；".join(m) if m else ""


def derive_for_point(p) -> list[dict]:
    """按字段优先级为单个语法点派生规则。"""
    if p.group == AFFIX_GROUP:
        return derive_affix(p)

    src = p.content or ""
    if not src.strip() and p.group in PATTERN_IN_CATEGORY:
        quoted = _extract_quoted(p.category or "")
        src = quoted if quoted else (p.category or "")
    if not src.strip():
        src = p.details or ""
    return derive_from_content(src)


def derive_affix(p) -> list[dict]:
    """语素：第-、老-、小- / -儿、-家、-们、-头、-子"""
    text = (p.details or "") + " " + (p.category or "")
    is_prefix = "前缀" in (p.category or "")
    chars = []
    for tok in re.split(r"[、,，;；:：]", text):
        tok = tok.strip().replace("-", "").replace("类前缀：", "").replace("类后缀：", "")
        tok = tok.strip()
        if _CJK.match(tok) and len(tok) <= 2:
            chars.append(tok)
    chars = sorted(set(chars))
    if not chars:
        return []
    return [
        {
            "kind": "affix",
            "position": "prefix" if is_prefix else "suffix",
            "needles": chars,
            "desc": ("词缀（前缀）" if is_prefix else "词缀（后缀）") + "：" + "、".join(chars),
        }
    ]


def build_family_floor(points) -> dict:
    """特殊句型的递进变体（“把”字句1…5、被动句1…5 等）在同一 label 下跨多个级别。

    正则难以可靠区分「被动句1」与「被动句3」，若全部计入会同时点亮 3~7 级，
    把难度分显著抬高。因此同一句型家族只保留**最低级**变体：
    文本出现被动句即记为 3 级语法点（该句型在标准中的引入级别）。
    """
    floor: dict[tuple, int] = {}
    for p in points:
        if p.group == "句子的类型" and p.category == "特殊句型":
            key = (p.group, p.category, p.details)
            floor[key] = min(floor.get(key, 99), p.level)
    return floor


def main() -> None:
    points = load_grammar()
    family_floor = build_family_floor(points)
    rules: list[dict] = []
    covered = 0
    merged = 0

    for p in points:
        if p.group == "句子的类型" and p.category == "特殊句型":
            if family_floor[(p.group, p.category, p.details)] < p.level:
                merged += 1
                continue

        label = p.label
        entry = {
            "no": p.no,
            "level": p.level,
            "label": label,
            "group": p.group,
            "category": p.category,
            "details": p.details,
            "rules": [],
        }

        st = match_structural(p)
        if st:
            entry["rules"].append(
                {"kind": "structural", "detector": st["detector"], "desc": st["desc"]}
            )
            covered += 1
        else:
            derived = match_curated(p) or match_expression(p) or derive_for_point(p)
            if derived:
                entry["rules"].extend(derived)
                covered += 1

        # 只保留有规则的条目
        if entry["rules"]:
            rules.append(entry)

    GRAMMAR_RULES_JSON.parent.mkdir(parents=True, exist_ok=True)
    with GRAMMAR_RULES_JSON.open("w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=1)

    # 统计
    by_kind: dict[str, int] = {}
    by_level: dict[int, int] = {}
    for e in rules:
        for r in e["rules"]:
            by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1
        by_level[e["level"]] = by_level.get(e["level"], 0) + 1

    total = len(points)
    print(f"语法点总数        : {total}")
    print(f"递进变体合并      : {merged} 条（同一句型只保留最低级变体）")
    print(f"生成规则条目数    : {len(rules)}  （覆盖 {len(rules)} / {total} = {len(rules) / total:.1%}）")
    print(f"按级别            : { {k: by_level.get(k, 0) for k in range(1, 8)} }")
    print(f"按规则类型        : {by_kind}")
    print(f"输出              : {GRAMMAR_RULES_JSON}")


if __name__ == "__main__":
    main()
