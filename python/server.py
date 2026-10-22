"""汉语二语文本阅读难度分级 —— 本地 Web 服务。

启动：
    uv run python server.py
    （或）uv run uvicorn server:app --port 8000

浏览器打开 http://127.0.0.1:8000
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from difficulty.pipeline import DifficultyAnalyzer  # noqa: E402
from difficulty.scoring import GRADE_BANDS, HSK_REFERENCE  # noqa: E402

STATIC_DIR = ROOT / "static"

app = FastAPI(title="中文文本难度分级", version="1.0.0")

_analyzer: DifficultyAnalyzer | None = None


def get_analyzer() -> DifficultyAnalyzer:
    global _analyzer
    if _analyzer is None:
        print("正在载入《国际中文教育中文水平等级标准》字表 / 词表 / 语法表 …", flush=True)
        _analyzer = DifficultyAnalyzer(verbose=True)
        print("载入完成。", flush=True)
    return _analyzer


class AnalyzeRequest(BaseModel):
    text: str = Field(..., description="待分析的中文文本")
    oov_chars_to_top: bool = Field(True, description="表外字是否计入第 7 级")
    oov_words_to_top: bool = Field(False, description="表外词是否计入第 7 级")


class AnalyzeResponse(BaseModel):
    ok: bool = True


@app.on_event("startup")
def _warmup() -> None:
    get_analyzer()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    """供前端探测：有 Python 后端时网页自动改用 jieba 分词计算。"""
    analyzer = get_analyzer()
    return {
        "ok": True,
        "engine": "python",
        "segmenter": "jieba",
        "meta": {
            "char_count": len(analyzer.chars),
            "word_count": len(analyzer.words),
            "rule_count": len(analyzer.rules),
        },
    }


@app.get("/api/meta")
def meta():
    return {
        "formula": "难度 = (1/3) × Σ(n=1..7) n × [r_char(n) + r_word(n) + r_grammar(n)]",
        "source": "程勇、董军、晋淑华《基于新标准的汉语二语文本阅读难度分级体系构建与应用》"
                  "，《世界汉语教学》2023 年第 1 期",
        "bands": [
            {"lo": lo, "hi": hi, "level": lvl, "name": name}
            for lo, hi, lvl, name in GRADE_BANDS
        ],
        "hsk_reference": HSK_REFERENCE,
    }


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="请输入要分析的中文文本")
    if len(text) > 200_000:
        raise HTTPException(status_code=400, detail="文本过长（上限 20 万字符）")

    analyzer = get_analyzer()
    result = analyzer.analyze(
        text,
        oov_chars_to_top=req.oov_chars_to_top,
        oov_words_to_top=req.oov_words_to_top,
    )
    payload = analyzer.to_dict(result, include_details=True)
    payload["ok"] = True
    return JSONResponse(payload)


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=False), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
