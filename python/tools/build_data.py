"""打包分级数据，并构建可离线使用的单文件网页。

产出：
  1. static/data.js            —— 供本地服务版页面加载（window.DifficultyData）
  2. dist/中文阅读难度测试.html  —— 数据 + 引擎 + 界面全部内嵌，双击即可离线使用

用法：
    .venv/Scripts/python.exe tools/build_data.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from difficulty.loader import load_chars, load_grammar_rules, load_words  # noqa: E402

STATIC = ROOT / "static"
DIST = ROOT / "dist"

# 通用分词词库取 jieba 高频词的前 N 条（仅用于切分，不参与难度计分）
LEX_TOP_N = int(os.environ.get("LEX_TOP_N", "60000"))
LEX_MIN_LEN, LEX_MAX_LEN = 2, 6
_CJK_WORD = re.compile(r"^[\u4e00-\u9fff]+$")


def find_jieba_dict() -> Path | None:
    """定位 jieba 自带的 dict.txt。"""
    env = os.environ.get("JIEBA_DICT")
    if env and Path(env).exists():
        return Path(env)
    spec = importlib.util.find_spec("jieba")
    if spec and spec.origin:
        p = Path(spec.origin).parent / "dict.txt"
        if p.exists():
            return p
    return None


def build_lex() -> dict[str, str]:
    """读取 jieba 词典，取高频的纯中文词，按词长分组拼接。"""
    path = find_jieba_dict()
    if path is None:
        print("提示：未找到 jieba 词典，离线版将只用等级词表分词（对文言、专名略敏感）")
        return {}

    rows: list[tuple[str, int]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                w = parts[0]
                if LEX_MIN_LEN <= len(w) <= LEX_MAX_LEN and _CJK_WORD.match(w):
                    rows.append((w, int(parts[1])))
    rows.sort(key=lambda x: -x[1])

    picked = sorted({w for w, _ in rows[:LEX_TOP_N]})
    grouped: dict[str, str] = {}
    for w in picked:
        grouped.setdefault(str(len(w)), "")
        grouped[str(len(w))] += w
    return grouped


def _safe_json(obj) -> str:
    """JSON 序列化，并转义 </ 以避免内联到 HTML 时提前闭合 script 标签。"""
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return text.replace("</", "<\\/")


def build_payload() -> dict:
    chars = load_chars()
    words = load_words()

    by_level_chars: dict[str, str] = {}
    for ch, lv in sorted(chars.level.items(), key=lambda kv: (kv[1], kv[0])):
        by_level_chars.setdefault(str(lv), "")
        by_level_chars[str(lv)] += ch

    by_level_words: dict[str, list[str]] = {}
    for w, lv in sorted(words.level.items(), key=lambda kv: (kv[1], kv[0])):
        by_level_words.setdefault(str(lv), []).append(w)

    rules = [
        {
            "no": r.no,
            "level": r.level,
            "label": r.label,
            "kind": r.kind,
            "needles": r.needles,
            "pattern": r.pattern,
            "position": r.position,
            "desc": r.desc,
        }
        for r in load_grammar_rules()
    ]

    payload = {"chars": by_level_chars, "words": by_level_words, "rules": rules, "lex": build_lex()}
    if payload["lex"]:
        print(f"通用分词词库 {sum(len(v) // int(k) for k, v in payload['lex'].items())} 条")
    return payload


def main() -> None:
    payload = build_payload()
    n_chars = sum(len(v) for v in payload["chars"].values())
    n_words = sum(len(v) for v in payload["words"].values())

    # ---------- 1. static/data.js ----------
    STATIC.mkdir(exist_ok=True)
    (STATIC / "data.js").write_text(
        "/* 自动生成，请勿手改；源数据见 data/raw/ 与 data/grammar_rules.json */\n"
        "window.DifficultyData = " + _safe_json(payload) + ";\n",
        encoding="utf-8",
    )

    # ---------- 2. 单文件离线版 ----------
    DIST.mkdir(exist_ok=True)
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    engine = (STATIC / "engine.js").read_text(encoding="utf-8")
    ui = (STATIC / "ui.js").read_text(encoding="utf-8")

    data_script = "<script>window.DifficultyData = " + _safe_json(payload) + ";</script>"
    html = html.replace('<script src="data.js"></script>', data_script)
    html = html.replace('<script src="engine.js"></script>', "<script>\n" + engine + "\n</script>")
    html = html.replace('<script src="ui.js"></script>', "<script>\n" + ui + "\n</script>")

    if 'src="data.js"' in html or 'src="engine.js"' in html or 'src="ui.js"' in html:
        raise RuntimeError("内联替换未完全生效，请检查 index.html 的 script 标签")

    out = DIST / "中文阅读难度测试.html"
    out.write_text(html, encoding="utf-8")

    print(f"汉字 {n_chars} / 词汇 {n_words} / 语法规则 {len(payload['rules'])}")
    print(f"已生成 {out.relative_to(ROOT)}  （{out.stat().st_size / 1024:.0f} KB，可离线双击打开）")
    print(f"已生成 static/data.js  （{(STATIC / 'data.js').stat().st_size / 1024:.0f} KB）")


if __name__ == "__main__":
    main()
