# 第三方数据与代码声明

本项目包含来自以下开源项目的数据，均以 MIT 许可证分发。
按 MIT 许可证要求，原始版权声明在此完整保留。

---

## 1. ivankra/hsk30

- 来源：<https://github.com/ivankra/hsk30>
- 许可证：MIT
- 本项目使用的文件：`hsk30-chars.csv`、`hsk30.csv`、`hsk30-grammar.csv`
- 用途：分级汉字表（3000）、分级词汇表（11092）、语法等级大纲（572）

```
MIT License

Copyright (c) 2023 Ivan Krasilnikov
Copyright (c) 2021 Shawky
Copyright (c) 2021 Pleco Inc.

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

数据内容本身源于《国际中文教育中文水平等级标准》(GF 0025-2021)，
由中外语言交流合作中心制定，其知识产权属于原制定方。

---

## 2. jieba

- 来源：<https://github.com/fxsjy/jieba>
- 许可证：MIT
- 本项目使用的部分：词典中的词条与词频（提取为通用分词词表，约 6 万条）
- 用途：浏览器离线版无法运行 Python，切词时用这份词表做双向最大匹配。
  **仅用于正确切分词语，不参与难度计分。**

```
The MIT License (MIT)

Copyright (c) 2013 Sun Junyi

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

---

## 3. 学术成果

难度公式与分级阈值来自：

> 程勇、董军、晋淑华（2023）基于新标准的汉语二语文本阅读难度分级体系构建与应用，
> 《世界汉语教学》2023 年第 1 期。

本工具只是将该方法工程化为可运行的网页，方法论贡献属于原作者。
论文原文未随本仓库分发。
