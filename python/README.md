# 中文文本阅读难度分级 —— Python 版

依据程勇、董军、晋淑华（2023）的难度公式，用 **jieba 分词 + 语法规则库** 计算汉语二语文本的阅读难度。

同一仓库根目录的 `index.html` 是纯浏览器版（打开即用、可离线、无需安装）；
这个 `python/` 目录是**本地服务版**，用 Python 计算，分词更接近论文做法。

---

## 快速开始

### Windows

双击 **`start.bat`**。首次运行会自动建虚拟环境、装依赖，之后启动服务。

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python server.py
```

然后浏览器打开 **<http://127.0.0.1:8000>**

> 首次启动要载入字表、词表并初始化 jieba，约 **20 秒**，之后每次分析都在 100 毫秒内。
> 窗口别关，关掉服务就停了。

也可以用 [uv](https://github.com/astral-sh/uv)：

```bash
uv venv && uv pip install -r requirements.txt && uv run python server.py
```

---

## 两个版本的区别

|  | 浏览器版（根目录 `index.html`） | Python 版（本目录） |
| --- | --- | --- |
| 要装东西吗 | 不用，双击即用 | 要 Python 3.10+ |
| 能离线吗 | 能 | 不能（服务在本机，其实也不需要外网） |
| 分词方式 | 词典双向最大匹配 + 6 万条通用词 | jieba，更接近论文 |
| 分数 | 略偏高 | 略低（见下） |

实测三段文本的差异：

| 文本 | Python 版 | 浏览器版 |
| --- | --- | --- |
| 大学课文（我上大学的时候…） | 1.460 二级 | 1.535 二级 |
| 书面语（在全球化的背景下…） | 2.497 五级 | 2.679 六级 |
| 文言（夫天地者…） | 3.193 七—九级 | 3.210 七—九级 |

差别来自分词口径：jieba 倾向把「文化交流」「日益频繁」整体切成一个表外短语（不计分），
浏览器版会切成「文化+交流」「日益+频繁」，都是词表内的中高级词，词汇维度因而偏高。

**做研究、要报数，建议用 Python 版**（口径更贴近论文的「分词 + 词性标注」）；
**日常快速看看、想随手分享，用浏览器版更方便。**

> 页面会自动识别：通过 `python server.py` 打开时走 Python 计算，
> 直接双击 HTML 文件时走浏览器计算，顶部会注明当前用的是哪个引擎。

---

## 目录结构

```
python/
├── start.bat                  Windows 一键启动
├── server.py                  FastAPI 服务（/、/api/health、/api/analyze、/api/meta）
├── requirements.txt           依赖
├── src/difficulty/
│   ├── loader.py              字表 / 词表 / 语法规则加载
│   ├── segment.py             jieba 分词与预处理
│   ├── grammar.py             语法点匹配
│   ├── scoring.py             难度公式与分级（论文表 8）
│   └── pipeline.py            分析流水线
├── static/                    前端（页面会自动判断走不走后端）
├── data/
│   ├── raw/                   分级数据 CSV（汉字 3000 / 词汇 11092 / 语法 572）
│   └── grammar_rules.json     由大纲编译出的 523 条识别规则
└── tools/
    ├── build_grammar_rules.py 重新生成语法规则库
    ├── build_data.py          打包数据、构建离线单文件版
    ├── validate.py            Python 版回归校验（7 段分级样本）
    ├── validate_js.mjs        浏览器版回归校验
    └── inspect_grammar.mjs    查看任意文本的语法点命中明细
```

---

## 接口

`POST /api/analyze`

```jsonc
// 请求
{ "text": "……", "oov_chars_to_top": true, "oov_words_to_top": false }

// 响应（节选）
{
  "score": 1.4605,
  "grade": { "level": 2, "name": "二级", "range": "[1.4, 1.75)" },
  "grade_reference": "HSK 二级（2 级）/ CEFR A1",
  "dimensions": { "汉字": {…}, "词汇": {…}, "语法": {…} },
  "details": { "grammar_hits": [...], "advanced_words": [...], "out_of_list_chars": [...] }
}
```

另外：

- `GET /api/health` —— 前端用它判断要不要走 Python（返回 `engine: "python"`）
- `GET /api/meta` —— 公式、分级阈值、HSK/CEFR 对照

---

## 数据与许可

分级数据取自 [`ivankra/hsk30`](https://github.com/ivankra/hsk30)（MIT 许可），
原标准为《国际中文教育中文水平等级标准》(GF 0025-2021)。

代码以 MIT 发布，第三方数据的原始版权声明见上级目录的
[THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md)。

方法来自：程勇、董军、晋淑华（2023）基于新标准的汉语二语文本阅读难度分级体系构建与应用，
《世界汉语教学》2023 年第 1 期。
