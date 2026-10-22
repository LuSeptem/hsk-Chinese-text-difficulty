/**
 * 用真实 DOM（jsdom）加载页面，模拟"输入文本 → 点击开始分析 → 读取结果"。
 * 同时检查页面内的脚本错误。
 *
 *   NODE_PATH=<jsdom 安装目录>/node_modules node tools/test_page.mjs [html 路径]
 */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

// jsdom 装在托管工作区里，用绝对路径加载（ESM 不认 NODE_PATH）
const JS_HOME = process.env.JSDOM_HOME
  || 'C:/Users/Septem/.workbuddy/binaries/node/workspace/node_modules';
const { JSDOM } = createRequire(path.join(JS_HOME, 'index.cjs'))('jsdom');

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const target = process.argv[2] || path.join(ROOT, 'dist/中文阅读难度测试.html');
const html = fs.readFileSync(target, 'utf8');

console.log('测试页面：' + path.relative(ROOT, target));

// 以 file:// 作为 URL，模拟"双击本地文件打开"的场景
const dom = new JSDOM(html, {
  url: pathToFileURL(target).href,
  runScripts: 'dangerously',
  pretendToBeVisual: true
});
const { window } = dom;
const doc = window.document;

const errors = [];
window.addEventListener('error', e => errors.push(String(e.message || e.error)));
const origErr = window.console.error;
window.console.error = (...a) => { errors.push(a.join(' ')); origErr(...a); };

await new Promise(r => setTimeout(r, 300));

const has = s => !!doc.querySelector(s);
console.log('  元素齐全：' + ['#text', '#run', '#out', '#result', '#optChars', '#optWords']
  .map(s => s + '=' + has(s)).join(' '));
console.log('  引擎就绪：' + (typeof window.DifficultyEngine !== 'undefined'));
console.log('  数据就绪：' + (typeof window.DifficultyData !== 'undefined'));
console.log('  数据提示：' + (doc.querySelector('#engineInfo')?.textContent || '').slice(0, 80));

// ---- 模拟一次真实点击 ----
const text = '随着生活水平的提高，越来越多的人开始关注健康问题。'
  + '有人认为，只要坚持锻炼，就能保持身体健康；也有人觉得，合理的饮食更加重要。';
const ta = doc.querySelector('#text');
ta.value = text;
ta.dispatchEvent(new window.Event('input'));
console.log('  字数统计：' + doc.querySelector('#counter').textContent);

doc.querySelector('#run').dispatchEvent(new window.Event('click'));

// 点击后应立刻出现进度面板
await new Promise(r => setTimeout(r, 60));
const steps = doc.querySelectorAll('#out .step');
console.log('  进度面板：' + steps.length + ' 个阶段，'
  + [...steps].map(e => e.className.replace('step ', '')).join(','));
if (steps.length !== 6) { console.log('  ✗ 进度面板未出现，点击没生效'); process.exit(1); }
console.log('  按钮状态：' + (doc.querySelector('#run').disabled ? '已禁用(分析中)' : '未禁用'));

// 等待分步执行完毕
await new Promise(r => setTimeout(r, 2500));

const result = doc.querySelector('#result');
const out = doc.querySelector('#out');
// 注意：必须看「计算样式」。只看 result.style.display 是行内样式，
// 若样式表里有 #result{display:none}，行内置空反而会退回到隐藏状态，
// 之前正是因此漏判（内容都渲染了，卡片却不可见）。
const computed = window.getComputedStyle(result).display;
const shown = result && computed !== 'none';
console.log('  结果区显示：' + shown + '（计算样式 display=' + computed + '）');
if (!shown) {
  console.log('  ✗ 点击后结果不可见，页面内容：' + out.innerHTML.slice(0, 300));
  process.exit(1);
}
const score = out.querySelector('.score-num')?.textContent?.trim();
const grade = out.querySelector('.grade-badge')?.textContent?.trim();
const bars = out.querySelectorAll('.bar-row').length;
console.log('  得分：' + score + '   评级：' + grade + '   分布条：' + bars + ' 行');
console.log('  维度卡：' + [...out.querySelectorAll('.dim .vl')].map(e => e.textContent).join(' / '));
console.log('  统计行：' + [...out.querySelectorAll('.stats span')].map(e => e.textContent).join(' '));

if (errors.length) {
  console.log('  ✗ 页面脚本错误：' + errors.join(' | '));
  process.exit(1);
}
if (!score || !grade || bars < 21) {
  console.log('  ✗ 渲染不完整');
  process.exit(1);
}
console.log('  ✓ 页面渲染正常，无脚本错误');
