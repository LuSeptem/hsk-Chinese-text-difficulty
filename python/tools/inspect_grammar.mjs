import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
globalThis.window = globalThis;
vm.runInThisContext(fs.readFileSync(path.join(ROOT, 'static/data.js'), 'utf8'));
vm.runInThisContext(fs.readFileSync(path.join(ROOT, 'static/engine.js'), 'utf8'));

const engine = globalThis.DifficultyEngine.create(globalThis.DifficultyData);
const text = '我上大学的时候，每天都要学习汉语。有时候在家看书，有时候听录音，有时候跟同学练习口语。'
  + '学习的时候，我认识了好朋友小王。他汉语很好，英语不好；我英语很好，汉语不好。'
  + '我们互相帮助，他辅导我汉语，我辅导他英语。';
const r = engine.analyze(text);
const g = r.dimensions['语法'];

console.log('语法维度 Σn×r(n) =', g.expectation.toFixed(3));
console.log('各级命中类型数:', JSON.stringify(g.counts));
const hits = r.details.grammar_hits;
console.log('命中语法点类型总数:', hits.length);
console.log();

const by = {};
hits.forEach(h => { (by[h.level] = by[h.level] || []).push(h); });
Object.keys(by).sort().forEach(lv => {
  console.log('--- ' + lv + '级（' + by[lv].length + ' 类）---');
  by[lv].forEach(h => {
    console.log('   ' + h.label + '   ⟵ 「' + h.evidence + '」');
  });
  console.log();
});

// 规则库构成
const rules = globalThis.DifficultyData.rules;
const kinds = {};
rules.forEach(x => { kinds[x.kind] = (kinds[x.kind] || 0) + 1; });
console.log('规则库构成:', JSON.stringify(kinds), ' 总计', rules.length);
const byLv = {};
rules.forEach(x => { byLv[x.level] = (byLv[x.level] || 0) + 1; });
console.log('规则按级别分布:', JSON.stringify(byLv));
