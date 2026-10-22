/* 页面交互：全部计算在本地浏览器完成，不联网、不依赖后端。 */
(function () {
  'use strict';

  var $ = function (s) { return document.querySelector(s); };
  var LEVEL_COLOR = ['lv1', 'lv2', 'lv3', 'lv4', 'lv5', 'lv6', 'lv7'];
  var GRADE_COLOR = { 1: '#7fb069', 2: '#a7c957', 3: '#f2c14e', 4: '#f4a259', 5: '#ef8354', 6: '#d95d63', 7: '#a2425c' };

  var SAMPLE = '随着生活水平的提高，越来越多的人开始关注健康问题。\n'
    + '有人认为，只要坚持锻炼，就能保持身体健康；也有人觉得，合理的饮食更加重要。\n'
    + '其实，这两方面都不可缺少。我们应该根据自己的实际情况，制定合适的计划，并且长期坚持下去，才会收到良好的效果。';

  // ------------------------------------------------------------------ //
  // 引擎（惰性初始化）
  // ------------------------------------------------------------------ //
  var ENGINE = null;
  function getEngine() {
    if (ENGINE) return ENGINE;
    if (typeof window.DifficultyData === 'undefined') {
      throw new Error('分级数据未加载：请确认 DATA.js 与本页在同一目录（离线单文件版数据已内嵌）。');
    }
    if (typeof window.DifficultyEngine === 'undefined') {
      throw new Error('分级引擎未加载：请确认 engine.js 与本页在同一目录。');
    }
    ENGINE = window.DifficultyEngine.create(window.DifficultyData);
    return ENGINE;
  }

  // ------------------------------------------------------------------ //
  // 后端探测
  //   服务版（python server.py）有 /api/health → 改用 Python + jieba 计算
  //   单文件版（file://）与 GitHub Pages 上没有后端 → 自动走本地 JS 引擎
  // ------------------------------------------------------------------ //
  var BACKEND_PROBE = Promise.resolve(null);

  function detectBackend() {
    try {
      if (typeof fetch !== 'function') return Promise.resolve(null);
      // file:// 下不发请求，直接走本地引擎
      if (location.protocol !== 'http:' && location.protocol !== 'https:') {
        return Promise.resolve(null);
      }
      return fetch('api/health', { cache: 'no-store' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (j) {
          return (j && j.ok === true && j.engine === 'python') ? j : null;
        })
        .catch(function () { return null; });
    } catch (e) {
      return Promise.resolve(null);
    }
  }

  function analyzeViaBackend(text) {
    return fetch('api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: text,
        oov_chars_to_top: $('#optChars').checked,
        oov_words_to_top: $('#optWords').checked
      })
    }).then(function (r) {
      return r.json().catch(function () { return null; }).then(function (j) {
        if (!r.ok) throw new Error((j && j.detail) ? j.detail : ('服务返回 ' + r.status));
        if (!j || !j.dimensions) throw new Error('服务返回的数据格式不正确');
        return j;
      });
    });
  }

  function showError(e) {
    var msg = (e && e.message) ? e.message : String(e);
    $('#out').innerHTML = '<div class="err"><b>分析失败：</b>' + escapeHtml(msg) + '</div>';
    $('#result').style.display = 'block';
    $('#placeholder').style.display = 'none';
  }

  function nowMs() {
    return (window.performance && window.performance.now) ? window.performance.now() : Date.now();
  }

  function resetBtn(btn) {
    btn.disabled = false;
    btn.textContent = '开始分析';
  }

  /** 先把 6 个阶段列出来（灰色待办），随后逐个点亮。 */
  function showProgress(names) {
    var html = '<div class="steps">'
      + names.map(function (n) {
        return '<div class="step"><span class="dot"></span><span class="sn">' + escapeHtml(n) + '</span>'
          + '<span class="sd">待执行</span></div>';
      }).join('')
      + '</div><div class="muted" style="margin-top:8px">正在分析，请稍候……</div>';
    $('#out').innerHTML = html;
    $('#result').style.display = 'block';
    $('#placeholder').style.display = 'none';
    scrollToResult();
  }

  function markStep(ev) {
    var rows = document.querySelectorAll('#out .step');
    var row = rows[ev.index];
    if (!row) return;
    var sd = row.querySelector('.sd');
    if (ev.phase === 'start') {
      row.className = 'step run';
      if (sd) sd.textContent = '进行中…';
    } else {
      row.className = 'step done';
      if (sd) sd.textContent = (ev.detail || '完成') + (ev.ms != null ? '（' + ev.ms + ' ms）' : '');
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // ------------------------------------------------------------------ //
  // 渲染
  // ------------------------------------------------------------------ //
  function barChart(title, dim) {
    var total = dim.total || 1;
    var rows = '';
    for (var i = 1; i <= 7; i++) {
      var c = dim.counts[i] || 0;
      var pct = c / total * 100;
      var name = i === 7 ? '七—九级' : ['一', '二', '三', '四', '五', '六'][i - 1] + '级';
      rows += '<div class="bar-row">'
        + '<div class="bar-lab">' + name + '</div>'
        + '<div class="bar-track"><div class="bar-fill ' + LEVEL_COLOR[i - 1] + '" style="width:' + pct.toFixed(1) + '%"></div></div>'
        + '<div class="bar-val">' + c + ' 项 · ' + pct.toFixed(1) + '%</div>'
        + '</div>';
    }
    var extra = dim.out_of_list_count
      ? '<div class="muted" style="margin-top:6px">另有表外项 ' + dim.out_of_list_count + ' 项未计入比例</div>' : '';
    return '<div class="chart"><div class="muted" style="margin-bottom:6px">' + title
      + '　共 ' + dim.total + ' 项　Σn×r(n) = ' + dim.expectation.toFixed(2) + '</div>' + rows + extra + '</div>';
  }

  function chipList(items, cls) {
    if (!items || !items.length) return '<div class="muted">无</div>';
    return '<div class="chips">' + items.map(function (x) {
      return '<span class="chip ' + (cls || '') + '">' + escapeHtml(x) + '</span>';
    }).join('') + '</div>';
  }

  function scrollToResult() {
    var card = $('#result');
    if (!card) return;
    try {
      card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) {
      // 部分老浏览器（含部分手机内置浏览器）不支持带参数的 scrollIntoView
      try { window.scrollTo(0, card.offsetTop - 12); } catch (e2) { /* 忽略 */ }
    }
  }

  function render(data, timing) {
    var g = data.grade || {};
    var color = GRADE_COLOR[g.level] || '#8b949e';
    var dims = data.dimensions;

    var html = ''
      + '<div class="score-hero">'
      + '<div><div class="score-num">' + data.score.toFixed(3) + '<small>分</small></div></div>'
      + '<div><span class="grade-badge" style="background:' + color + '">' + (g.name || '-') + '</span>'
      + '<div class="grade-ref">' + escapeHtml(data.grade_reference || '') + '</div></div>'
      + '</div>'
      + '<div class="bandbar"><div class="pin" style="left:'
      + Math.min(100, Math.max(0, (data.score - 1) / 3.5 * 100)) + '%"></div></div>'
      + '<div class="bandscale"><span>1.0</span><span>1.4</span><span>1.75</span><span>2.0</span>'
      + '<span>2.3</span><span>2.55</span><span>2.7</span><span>3.5+</span></div>'
      + '<div class="dims">'
      + dimCell('汉字维度', dims['汉字'])
      + dimCell('词汇维度', dims['词汇'])
      + dimCell('语法维度', dims['语法'])
      + '</div>';

    if (data.note) html += '<div class="note">' + escapeHtml(data.note) + '</div>';

    html += '<details open><summary>字／词／语法各级别分布</summary><div class="body">'
      + barChart('汉字', dims['汉字'])
      + '<div style="height:10px"></div>'
      + barChart('词汇', dims['词汇'])
      + '<div style="height:10px"></div>'
      + barChart('语法', dims['语法'])
      + '</div></details>';

    var d = data.details || {};
    if (d.advanced_words && d.advanced_words.length) {
      html += '<details><summary>高级别词语（五级及以上，共 ' + d.advanced_words.length + ' 个）</summary>'
        + '<div class="body"><table><thead><tr><th>词语</th><th>级别</th><th>出现次数</th></tr></thead><tbody>'
        + d.advanced_words.map(function (w) {
          return '<tr><td>' + escapeHtml(w.word) + '</td><td>' + w.level_name + '</td><td>' + w.freq + '</td></tr>';
        }).join('')
        + '</tbody></table></div></details>';
    }

    if (d.grammar_hits && d.grammar_hits.length) {
      html += '<details><summary>识别到的语法点（共 ' + d.grammar_hits.length + ' 类）</summary>'
        + '<div class="body"><table><thead><tr><th>级别</th><th>语法点</th><th>命中证据</th></tr></thead><tbody>'
        + d.grammar_hits.map(function (h) {
          return '<tr><td>' + (h.level === 7 ? '七—九' : h.level) + '</td><td>' + escapeHtml(h.label)
            + '</td><td>' + escapeHtml(h.evidence) + '</td></tr>';
        }).join('')
        + '</tbody></table></div></details>';
    }

    if ((d.out_of_list_chars && d.out_of_list_chars.length) || (d.out_of_list_words && d.out_of_list_words.length)) {
      html += '<details><summary>表外字 / 表外词</summary><div class="body">'
        + '<div class="muted" style="margin:6px 0">表外字（不在 3000 字表内，共 ' + d.out_of_list_chars.length + ' 个）</div>'
        + chipList(d.out_of_list_chars.slice(0, 150), 'hi')
        + '<div class="muted" style="margin:12px 0 6px">表外词（不在 11092 词表内，共 ' + d.out_of_list_words.length + ' 个）</div>'
        + chipList(d.out_of_list_words.slice(0, 150))
        + '</div></details>';
    }

    var s = data.stats;
    html += '<div class="stats">'
      + '<span>字符数 ' + s.text_length + '</span><span>汉字数 ' + s.hanzi_count + '</span>'
      + '<span>字种 ' + s.char_types + '</span><span>词种 ' + s.word_types + '</span>'
      + '<span>句数 ' + s.sentence_count + '</span><span>语法点 ' + s.grammar_point_types + ' 类</span>'
      + '</div>';

    if (timing) {
      html += '<div class="muted" style="margin-top:8px">分析完成：实际计算 '
        + timing.computeMs + ' ms（分步展示共 ' + timing.wallMs + ' ms，其中大部分是刻意留的展示间隔）</div>';
    }

    $('#out').innerHTML = html;
    $('#result').style.display = 'block';
    $('#placeholder').style.display = 'none';

    // 窄窗口下结果卡会排到输入区下方（屏幕外），自动滚过去，避免"点了没反应"的错觉
    scrollToResult();
  }

  function dimCell(name, dim) {
    var unit = { '汉字维度': '个字种', '词汇维度': '个词种', '语法维度': '类语法点' }[name];
    return '<div class="dim"><div class="nm">' + name + '</div>'
      + '<div class="vl">' + dim.expectation.toFixed(2) + '</div>'
      + '<div class="sub">' + dim.total + ' ' + unit + '</div></div>';
  }

  // ------------------------------------------------------------------ //
  // 事件
  // ------------------------------------------------------------------ //
  function updateCounter() { $('#counter').textContent = $('#text').value.length + ' 字'; }

  function bind() {
    $('#fillSample').onclick = function () { $('#text').value = SAMPLE; updateCounter(); };
    $('#clear').onclick = function () {
      $('#text').value = ''; updateCounter();
      $('#result').style.display = 'none'; $('#placeholder').style.display = '';
    };
    $('#text').oninput = updateCounter;

    // 支持 Ctrl / Cmd + Enter 直接分析
    $('#text').addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); $('#run').click(); }
    });

    $('#run').onclick = function () {
      var text = $('#text').value.trim();
      if (!text) { alert('请先输入中文文本'); return; }

      var btn = $('#run');
      var wall0 = nowMs();
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span>分析中';

      BACKEND_PROBE.then(function (backend) {
        return backend ? runBackend(text, btn, wall0) : runLocal(text, btn, wall0);
      }).catch(function (e) {
        showError(e);
        resetBtn(btn);
      });
    };

    // 有 Python 后端：交给服务器算（jieba 分词，与论文实现更接近）
    function runBackend(text, btn, wall0) {
      showProgress(['提交文本到 Python 服务', 'jieba 分词 + 语法匹配 + 按公式计分']);
      markStep({ index: 0, phase: 'start' });

      var t0 = nowMs();
      return analyzeViaBackend(text).then(function (data) {
        var ms = nowMs() - t0;
        markStep({ index: 0, phase: 'done', detail: '已提交 ' + text.length + ' 字' });
        markStep({ index: 1, phase: 'done', detail: '服务器耗时 ' + Math.round(ms) + ' ms' });
        render(data, {
          computeMs: Math.round(ms * 10) / 10,
          wallMs: Math.round((nowMs() - wall0) * 10) / 10
        });
      }).catch(function (e) {
        showError(e);
      }).then(function () {
        resetBtn(btn);
      });
    }

    // 无后端：浏览器本地计算（离线可用）
    function runLocal(text, btn, wall0) {
      var computeMs = 0;
      var engine;
      try {
        engine = getEngine();
        showProgress(engine.stageNames());
      } catch (e) {
        resetBtn(btn);
        showError(e);
        return Promise.resolve();
      }

      return engine.analyzeAsync(
        text,
        { oov_chars_to_top: $('#optChars').checked, oov_words_to_top: $('#optWords').checked },
        function (ev) {
          if (ev.phase === 'done' && ev.ms != null) computeMs += ev.ms;
          markStep(ev);
        },
        140
      ).then(function (data) {
        render(data, { computeMs: Math.round(computeMs * 100) / 100, wallMs: Math.round((nowMs() - wall0) * 10) / 10 });
      }).catch(function (e) {
        showError(e);
      }).then(function () {
        resetBtn(btn);
      });
    }

    // 先显示本地引擎就绪状态（单文件版立即可见）
    var el = document.getElementById('engineInfo');
    try {
      var m = getEngine().meta;
      if (el) {
        el.innerHTML = '<span class="ok-dot"></span><b class="ok">分级引擎已就绪</b>　'
          + '内置汉字 ' + m.char_count + ' / 词汇 ' + m.word_count + ' / 语法规则 ' + m.rule_count
          + '；全部计算在浏览器本地完成，无需联网。';
      }
    } catch (e) {
      if (el) { el.innerHTML = '<span style="color:#a2425c">数据未能加载：' + escapeHtml(e.message) + '</span>'; }
    }

    // 再探测有没有 Python 后端；有就改口径，让用户知道当前用的是哪个引擎
    BACKEND_PROBE = detectBackend();
    BACKEND_PROBE.then(function (backend) {
      if (!backend || !el) return;
      var bm = backend.meta || {};
      el.innerHTML = '<span class="ok-dot"></span><b class="ok">分级引擎已就绪（Python 后端 · jieba 分词）</b>　'
        + '汉字 ' + bm.char_count + ' / 词汇 ' + bm.word_count + ' / 语法规则 ' + bm.rule_count
        + '；由 FastAPI 服务计算，结果以服务器为准。';
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
