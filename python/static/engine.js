/*!
 * 中文文本阅读难度分级引擎（浏览器版）
 *
 * 依据：程勇、董军、晋淑华《基于新标准的汉语二语文本阅读难度分级体系构建与应用》
 *      《世界汉语教学》2023 年第 1 期
 *
 *   文本难度 = (1/3) × Σ(n=1..7) n × [ r字(n) + r词(n) + r语法(n) ]
 *
 * 数据：《国际中文教育中文水平等级标准》(GF 0025-2021)
 *   汉字 3000 / 词汇 11092 / 语法 572
 *
 * 本文件不依赖任何外部库，可在浏览器与 Node 中直接运行。
 */
(function (root) {
  'use strict';

  var CJK = /^[\u4e00-\u9fff]+$/;
  var CJK_RUN = /[\u4e00-\u9fff]+/g;
  var SENT_SPLIT = /[^。！？!?；;\n]+[。！？!?；;]?/g;

  var LEVEL_NAMES = { 1: '一级', 2: '二级', 3: '三级', 4: '四级', 5: '五级', 6: '六级', 7: '七—九级' };

  // 论文表 8 的分级区间（下闭上开）
  var GRADE_BANDS = [
    [1.0, 1.4, 1, '一级'],
    [1.4, 1.75, 2, '二级'],
    [1.75, 2.0, 3, '三级'],
    [2.0, 2.3, 4, '四级'],
    [2.3, 2.55, 5, '五级'],
    [2.55, 2.7, 6, '六级'],
    [2.7, 7.01, 7, '七—九级']
  ];

  var HSK_REFERENCE = {
    1: 'HSK 一级（1 级）/ CEFR pre-A1',
    2: 'HSK 二级（2 级）/ CEFR A1',
    3: 'HSK 三级（3 级）/ CEFR A1—A2',
    4: 'HSK 四级（4 级）/ CEFR A2—B1',
    5: 'HSK 五级（5 级）/ CEFR B1—B2',
    6: 'HSK 六级（6 级）/ CEFR B2—C1',
    7: 'HSK 七—九级 / CEFR C1—C2'
  };

  var QUESTION_WORDS = ['吗', '呢', '吧', '什么', '谁', '哪', '哪儿', '哪里', '怎么', '怎么样', '为什么', '几', '多少', '多', '是否'];
  var IMPERATIVE_AT_START = ['请', '别', '不要', '不许', '请勿', '务必', '千万', '禁止', '快'];
  var ADVERB_TOKENS = ['很', '非常', '太', '最', '都', '也', '还', '就'];
  var COMPOUND_MARKERS = ['因为', '所以', '虽然', '但是', '如果', '就', '不但', '而且', '一边'];

  // --------------------------------------------------------------------- //
  // 引擎
  // --------------------------------------------------------------------- //
  function createEngine(data) {
    // 汉字：字 -> 级别
    var charLevel = new Map();
    Object.keys(data.chars).forEach(function (lv) {
      var s = data.chars[lv];
      for (var i = 0; i < s.length; i++) {
        var ch = s[i];
        if (!charLevel.has(ch)) charLevel.set(ch, +lv);
      }
    });

    // 词语：词 -> 级别
    var wordLevel = new Map();
    Object.keys(data.words).forEach(function (lv) {
      data.words[lv].forEach(function (w) {
        if (!wordLevel.has(w)) wordLevel.set(w, +lv);
      });
    });
    // 分词词典：等级词表 + 通用高频词库（lex）。
    // 只有等级词表里的词才参与难度计分，lex 仅用于切分，避免把
    // 「天地」「万物」这类未登录串拆成低级别单字。
    var segSet = new Set();
    wordLevel.forEach(function (v, k) { segSet.add(k); });
    // lex 按词长分组拼接成整串，减少体积：{"2":"天地万物…","3":"…"}
    var lex = data.lex || [];
    if (Array.isArray(lex)) {
      for (var li = 0; li < lex.length; li++) segSet.add(lex[li]);
    } else {
      Object.keys(lex).forEach(function (L) {
        var s = lex[L], n = +L;
        for (var i = 0; i + n <= s.length; i += n) segSet.add(s.substr(i, n));
      });
    }

    var maxWordLen = 1;
    segSet.forEach(function (w) { if (w.length > maxWordLen) maxWordLen = w.length; });

    // 语法规则
    var rules = data.rules.map(function (r) {
      var re = null;
      if (r.kind === 'pattern' && r.pattern) {
        try { re = new RegExp(r.pattern); } catch (e) { re = null; }
      }
      return {
        no: r.no, level: r.level, label: r.label, kind: r.kind,
        needles: r.needles || [], pattern: r.pattern || '',
        position: r.position || '', desc: r.desc || r.label || '', _re: re
      };
    });

    // ------------------------------------------------------------------ //
    // 分词：词典双向最大匹配（正向 / 反向取优）
    // ------------------------------------------------------------------ //
    // 供反向分词使用的倒序词典
    var revLevel = new Set();
    segSet.forEach(function (w) { revLevel.add(w.split('').reverse().join('')); });

    /**
     * 词典最大匹配（单向）。
     * 与 jieba 的处理保持一致：词典里查不到的连续片段整体作为一个未登录词，
     * 不再逐字切开——否则古典文、专名里的单字会被当成低级别单字词，把难度拉低。
     */
    function makeMatcher(dict, maxLen) {
      return function (s) {
        var out = [], i = 0, n = s.length, L, hit;
        while (i < n) {
          hit = null;
          for (L = Math.min(maxLen, n - i); L > 1; L--) {
            if (dict.has(s.substr(i, L))) { hit = s.substr(i, L); break; }
          }
          if (hit) { out.push(hit); i += hit.length; continue; }
          if (dict.has(s[i])) { out.push(s[i]); i += 1; continue; }
          // 未登录串：一直扩到下一个"能识别"的位置为止
          var j = i + 1, can;
          while (j < n) {
            if (dict.has(s[j])) break;
            can = false;
            for (L = Math.min(maxLen, n - j); L > 1; L--) {
              if (dict.has(s.substr(j, L))) { can = true; break; }
            }
            if (can) break;
            j++;
          }
          out.push(s.slice(i, j));
          i = j;
        }
        return out;
      };
    }

    var fwd = makeMatcher(segSet, maxWordLen);
    var bwdCore = makeMatcher(revLevel, maxWordLen);

    function fmm(s) { return fwd(s); }

    function bmm(s) {
      var rs = s.split('').reverse().join('');
      return bwdCore(rs).map(function (x) { return x.split('').reverse().join(''); }).reverse();
    }

    function cut(text) {
      var tokens = [];
      var runs = text.match(CJK_RUN) || [];
      for (var r = 0; r < runs.length; r++) {
        var s = runs[r];
        var f = fmm(s), b = bmm(s);
        var best;
        if (f.length !== b.length) {
          best = f.length < b.length ? f : b;
        } else {
          var sf = 0, sb = 0, k;
          for (k = 0; k < f.length; k++) if (f[k].length === 1) sf++;
          for (k = 0; k < b.length; k++) if (b[k].length === 1) sb++;
          best = sf <= sb ? f : b;
        }
        tokens = tokens.concat(best);
      }
      return tokens;
    }

    function splitSentences(text) {
      var out = [], m;
      SENT_SPLIT.lastIndex = 0;
      while ((m = SENT_SPLIT.exec(text)) !== null) {
        var s = m[0].trim();
        if (s) out.push(s);
      }
      return out;
    }

    // ------------------------------------------------------------------ //
    // 语法点识别
    // ------------------------------------------------------------------ //
    function detect(name, ctx) {
      var sents = ctx.sentences, text = ctx.text, tokens = ctx.tokens, i, s2;
      switch (name) {
        case 'ever': return sents.length > 0;
        case 'declarative': return text.indexOf('。') >= 0 || sents.length > 0;
        case 'interrogative':
          if (text.indexOf('？') >= 0 || text.indexOf('?') >= 0) return true;
          for (i = 0; i < QUESTION_WORDS.length; i++) if (text.indexOf(QUESTION_WORDS[i]) >= 0) return true;
          return false;
        case 'imperative':
          for (i = 0; i < sents.length; i++) {
            s2 = sents[i].replace(/^\s+/, '');
            for (var j = 0; j < IMPERATIVE_AT_START.length; j++) {
              if (s2.indexOf(IMPERATIVE_AT_START[j]) === 0) return true;
            }
          }
          return (text.indexOf('！') >= 0 || text.indexOf('!') >= 0) && sents.length <= 3;
        case 'exclamative': return text.indexOf('！') >= 0 || text.indexOf('!') >= 0;
        case 'attributive': return text.indexOf('的') >= 0;
        case 'adverbial':
          if (text.indexOf('地') >= 0) return true;
          for (i = 0; i < tokens.length; i++) if (ADVERB_TOKENS.indexOf(tokens[i]) >= 0) return true;
          return false;
        case 'compound':
          if (sents.length > 1) return true;
          for (i = 0; i < COMPOUND_MARKERS.length; i++) if (text.indexOf(COMPOUND_MARKERS[i]) >= 0) return true;
          return false;
        default: return false;
      }
    }

    function matchGrammar(text, tokens, sentences) {
      var ctx = { text: text, tokens: tokens, sentences: sentences };
      var tokenSet = new Set(tokens);
      var joined = tokens.join('');
      var hits = [], seen = new Set();
      for (var i = 0; i < rules.length; i++) {
        var r = rules[i];
        if (seen.has(r.no)) continue;
        var evidence = '';
        if (r.kind === 'lex') {
          for (var a = 0; a < r.needles.length; a++) {
            var nd = r.needles[a];
            if (tokenSet.has(nd)) { evidence = nd; break; }
            if (nd.length >= 2 && joined.indexOf(nd) >= 0) { evidence = nd; break; }
          }
        } else if (r.kind === 'pattern') {
          if (r._re) {
            var m = r._re.exec(joined);
            if (m) evidence = m[0];
          }
        } else if (r.kind === 'affix') {
          var isPrefix = r.position !== 'suffix';
          for (var b = 0; b < r.needles.length && !evidence; b++) {
            var needle = r.needles[b];
            for (var t = 0; t < tokens.length; t++) {
              var tok = tokens[t];
              if (tok.length <= needle.length) continue;
              if (isPrefix && tok.indexOf(needle) === 0) { evidence = tok; break; }
              if (!isPrefix && tok.lastIndexOf(needle) === tok.length - needle.length) { evidence = tok; break; }
            }
          }
        } else if (r.kind === 'structural') {
          if (detect(r.pattern, ctx)) evidence = '（结构性判定）';
        }
        if (evidence) {
          seen.add(r.no);
          hits.push({
            no: r.no, level: r.level, label: r.label,
            desc: (r.desc || r.label) + '（命中：' + evidence + '）',
            evidence: evidence
          });
        }
      }
      hits.sort(function (x, y) { return x.level - y.level || (x.no < y.no ? -1 : 1); });
      return hits;
    }

    // ------------------------------------------------------------------ //
    // 计分
    // ------------------------------------------------------------------ //
    function buildDimension(name, counts, outOfList, oovToTop) {
      counts = Object.assign({}, counts);
      if (oovToTop && outOfList.length) counts[7] = (counts[7] || 0) + outOfList.length;
      var total = 0, i;
      for (i = 1; i <= 7; i++) total += (counts[i] || 0);
      var ratios = {}, contribution = 0;
      for (i = 1; i <= 7; i++) {
        ratios[i] = total ? (counts[i] || 0) / total : 0;
        contribution += i * ratios[i];
      }
      var norm = {};
      for (i = 1; i <= 7; i++) norm[i] = counts[i] || 0;
      return {
        name: name, total: total, counts: norm, ratios: ratios,
        expectation: contribution, out_of_list_count: outOfList.length
      };
    }

    function gradeOf(score) {
      for (var i = 0; i < GRADE_BANDS.length; i++) {
        var b = GRADE_BANDS[i];
        if (score >= b[0] && score < b[1]) return { level: b[2], name: b[3], range: '[' + b[0] + ', ' + b[1] + ')' };
      }
      return { level: 7, name: LEVEL_NAMES[7], range: '[2.7, 7]' };
    }

    /** 把一次分析拆成 6 个阶段，便于界面显示实时进度。 */
    function buildJob(rawText, opts) {
      opts = opts || {};
      var st = {
        text: (rawText || '').trim(),
        oovCharsToTop: opts.oov_chars_to_top !== false,
        oovWordsToTop: opts.oov_words_to_top === true,
        detail: ''
      };

      var stages = [
        {
          name: '① 文本预处理：提取汉字、分句',
          run: function () {
            var hanzi = [], i, c;
            for (i = 0; i < st.text.length; i++) {
              c = st.text[i];
              if (c >= '\u4e00' && c <= '\u9fff') hanzi.push(c);
            }
            st.hanzi = hanzi;
            var seen = new Set(), types = [];
            for (i = 0; i < hanzi.length; i++) {
              if (!seen.has(hanzi[i])) { seen.add(hanzi[i]); types.push(hanzi[i]); }
            }
            st.charTypes = types;
            st.sentences = splitSentences(st.text);
            st.detail = '汉字 ' + hanzi.length + ' 个 · 字种 ' + types.length + ' · 句子 ' + st.sentences.length + ' 句';
          }
        },
        {
          name: '② 汉字维度：按 3000 字表统计字种级别',
          run: function () {
            var counts = {}, oov = [], i, lv;
            for (i = 0; i < st.charTypes.length; i++) {
              lv = charLevel.get(st.charTypes[i]);
              if (lv === undefined) oov.push(st.charTypes[i]); else counts[lv] = (counts[lv] || 0) + 1;
            }
            st.oovChars = oov;
            st.charDim = buildDimension('汉字', counts, oov, st.oovCharsToTop);
            st.detail = st.charDim.total + ' 个字种 · Σn×r(n) = ' + st.charDim.expectation.toFixed(3)
              + (oov.length ? ' · 表外字 ' + oov.length : '');
          }
        },
        {
          name: '③ 分词：词典双向最大匹配',
          run: function () {
            st.tokens = cut(st.text);
            st.detail = '切出 ' + st.tokens.length + ' 个词 token';
          }
        },
        {
          name: '④ 词汇维度：按 11092 词表统计词种级别',
          run: function () {
            var freq = new Map(), i, w, lv;
            for (i = 0; i < st.tokens.length; i++) freq.set(st.tokens[i], (freq.get(st.tokens[i]) || 0) + 1);
            var counts = {}, oov = [], adv = [];
            var keys = Array.from(freq.keys()).sort();
            for (i = 0; i < keys.length; i++) {
              w = keys[i];
              lv = wordLevel.get(w);
              if (lv === undefined) { oov.push(w); continue; }
              counts[lv] = (counts[lv] || 0) + 1;
              if (lv >= 5) adv.push({ word: w, level: lv, level_name: LEVEL_NAMES[lv], freq: freq.get(w) });
            }
            adv.sort(function (a, b) { return b.level - a.level || b.freq - a.freq; });
            st.oovWords = oov;
            st.advanced = adv;
            st.wordFreq = freq;
            st.wordDim = buildDimension('词汇', counts, oov, st.oovWordsToTop);
            st.detail = st.wordDim.total + ' 个词种 · Σn×r(n) = ' + st.wordDim.expectation.toFixed(3)
              + (oov.length ? ' · 表外词 ' + oov.length : '');
          }
        },
        {
          name: '⑤ 语法维度：匹配 ' + rules.length + ' 条语法规则',
          run: function () {
            st.hits = matchGrammar(st.text, st.tokens, st.sentences);
            var counts = {}, i;
            for (i = 0; i < st.hits.length; i++) counts[st.hits[i].level] = (counts[st.hits[i].level] || 0) + 1;
            st.gramDim = buildDimension('语法', counts, [], false);
            st.detail = '命中 ' + st.hits.length + ' 类语法点 · Σn×r(n) = ' + st.gramDim.expectation.toFixed(3);
          }
        },
        {
          name: '⑥ 按论文公式合成难度分与评级',
          run: function () {
            var dims = [st.charDim, st.wordDim, st.gramDim];
            var valid = [], i;
            for (i = 0; i < dims.length; i++) if (dims[i].total > 0) valid.push(dims[i]);
            var score = 0, grade = null, note = '';
            if (!valid.length) {
              note = '文本中没有可分析的汉字';
            } else {
              var sum = 0;
              for (i = 0; i < valid.length; i++) sum += valid[i].expectation;
              score = Math.round(sum / valid.length * 10000) / 10000;
              grade = gradeOf(score);
              if (valid.length < dims.length) {
                var missing = [];
                for (i = 0; i < dims.length; i++) if (dims[i].total <= 0) missing.push(dims[i].name);
                note = '以下维度未识别到内容，已按剩余 ' + valid.length + ' 个维度平均：' + missing.join('、');
              }
            }

            st.out = {
              score: score,
              grade: grade,
              grade_reference: grade ? (HSK_REFERENCE[grade.level] || '') : '',
              note: note,
              dimensions: { '汉字': st.charDim, '词汇': st.wordDim, '语法': st.gramDim },
              per_dimension: {
                '汉字': st.charDim.expectation, '词汇': st.wordDim.expectation, '语法': st.gramDim.expectation
              },
              stats: {
                text_length: st.text.length,
                hanzi_count: st.hanzi.length,
                char_types: st.charTypes.length,
                word_tokens: st.tokens.length,
                word_types: st.wordFreq.size,
                sentence_count: st.sentences.length,
                grammar_point_types: st.hits.length,
                oov_char_types: st.oovChars.length,
                oov_word_types: st.oovWords.length
              },
              details: {
                grammar_hits: st.hits.map(function (h) {
                  return { level: h.level, label: h.label, desc: h.desc, evidence: h.evidence };
                }),
                advanced_words: st.advanced,
                out_of_list_chars: st.oovChars.slice(0, 200),
                out_of_list_words: st.oovWords.slice(0, 200)
              }
            };
            st.detail = '难度 ' + score + ' → ' + (grade ? grade.name : '—');
          }
        }
      ];

      return { stages: stages, st: st, result: function () { return st.out; } };
    }

    /** 同步分析（脚本 / Node 用）。onStep 可选。 */
    function analyze(text, opts, onStep) {
      var job = buildJob(text, opts);
      for (var i = 0; i < job.stages.length; i++) {
        if (onStep) onStep({ index: i, total: job.stages.length, name: job.stages[i].name, phase: 'start' });
        job.stages[i].run();
        if (onStep) {
          onStep({ index: i, total: job.stages.length, name: job.stages[i].name, detail: job.st.detail, phase: 'done' });
        }
      }
      return job.result();
    }

    /** 异步分析：每个阶段之间让出主线程，界面可实时显示进度。 */
    function analyzeAsync(text, opts, onStep, delay) {
      delay = delay == null ? 120 : delay;
      var now = (root.performance && root.performance.now)
        ? function () { return root.performance.now(); } : function () { return Date.now(); };
      return new Promise(function (resolve, reject) {
        var job;
        try { job = buildJob(text, opts); } catch (e) { reject(e); return; }
        var i = 0;
        function next() {
          if (i >= job.stages.length) { resolve(job.result()); return; }
          var s = job.stages[i], idx = i, t0 = now();
          if (onStep) onStep({ index: idx, total: job.stages.length, name: s.name, phase: 'start' });
          try { s.run(); } catch (e) { reject(e); return; }
          if (onStep) {
            onStep({
              index: idx, total: job.stages.length, name: s.name,
              detail: job.st.detail, phase: 'done', ms: Math.round((now() - t0) * 100) / 100
            });
          }
          i++;
          setTimeout(next, delay);
        }
        setTimeout(next, 0);
      });
    }

    function stageNames() {
      return buildJob('', {}).stages.map(function (s) { return s.name; });
    }

    return {
      analyze: analyze,
      analyzeAsync: analyzeAsync,
      stageNames: stageNames,
      meta: {
        char_count: charLevel.size,
        word_count: wordLevel.size,
        seg_count: segSet.size,
        rule_count: rules.length,
        formula: '难度 = (1/3) × Σ(n=1..7) n × [r字(n) + r词(n) + r语法(n)]',
        source: '程勇、董军、晋淑华《基于新标准的汉语二语文本阅读难度分级体系构建与应用》，《世界汉语教学》2023 年第 1 期'
      }
    };
  }

  var api = { create: createEngine, GRADE_BANDS: GRADE_BANDS, HSK_REFERENCE: HSK_REFERENCE, LEVEL_NAMES: LEVEL_NAMES };
  root.DifficultyEngine = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
