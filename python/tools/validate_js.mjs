/**
 * 浏览器版引擎校验：与 Python 版跑同一批样本（tools/samples.json），对比打分结果。
 *
 *   node tools/validate_js.mjs
 */
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

globalThis.window = globalThis;
vm.runInThisContext(fs.readFileSync(path.join(ROOT, 'static/data.js'), 'utf8'), { filename: 'data.js' });
vm.runInThisContext(fs.readFileSync(path.join(ROOT, 'static/engine.js'), 'utf8'), { filename: 'engine.js' });

const engine = globalThis.DifficultyEngine.create(globalThis.DifficultyData);
const samples = JSON.parse(fs.readFileSync(path.join(ROOT, 'tools/samples.json'), 'utf8'));

console.log(`\n引擎内置：汉字 ${engine.meta.char_count} / 词汇 ${engine.meta.word_count} / 语法规则 ${engine.meta.rule_count}\n`);
console.log('标注'.padEnd(10) + '得分'.padStart(8) + '  ' + '评级'.padEnd(10) + '字'.padStart(7) + '词'.padStart(7) + '语法'.padStart(7));
console.log('-'.repeat(56));

let prev = -1, monotonic = true;
for (const s of samples) {
  const r = engine.analyze(s.text);
  const g = r.grade || {};
  if (r.score < prev) monotonic = false;
  prev = r.score;
  console.log(
    s.label.padEnd(10) +
    r.score.toFixed(3).padStart(8) + '  ' +
    (g.name || '-').padEnd(10) +
    r.dimensions['汉字'].expectation.toFixed(2).padStart(7) +
    r.dimensions['词汇'].expectation.toFixed(2).padStart(7) +
    r.dimensions['语法'].expectation.toFixed(2).padStart(7)
  );
}
console.log('\n单调性：' + (monotonic ? '通过（难度随标注等级递增）' : '未通过'));
