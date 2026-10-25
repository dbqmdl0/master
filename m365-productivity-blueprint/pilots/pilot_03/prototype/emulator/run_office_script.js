// Office Scripts 로컬 실행 브리지 (테스트 전용)
// 사용: echo '{"script":"BuildDailyBrief","params":{...}}' | node run_office_script.js
// - office_scripts/<script>.ts 를 tsc(strict, ES2017)로 컴파일(변경 시에만) → vm에서 main(workbook, ...params) 실행
// - 매개변수는 main() 시그니처의 이름 순서대로 전달(Power Automate 'Run script'와 같은 방식: 이름으로 매핑)
// - 결과: {"ok":true,"result":...} 또는 {"ok":false,"error":"..."} (스크립트 예외 = Run script 액션 실패)
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { execFileSync } = require("node:child_process");

const ROOT = path.resolve(__dirname, "..");
const BUILD = path.join(ROOT, "tests", "build");

function compile(name) {
  const src = path.join(ROOT, "office_scripts", `${name}.ts`);
  const out = path.join(BUILD, name, "office_scripts", `${name}.js`);
  if (!fs.existsSync(out) || fs.statSync(out).mtimeMs < fs.statSync(src).mtimeMs) {
    execFileSync("tsc", ["--strict", "--target", "ES2017", "--lib", "ES2017", "--rootDir", ROOT,
      "--outDir", path.join(BUILD, name), path.join(ROOT, "tests", "excelscript-stub.d.ts"), src], { stdio: "pipe" });
  }
  return { js: fs.readFileSync(out, "utf8"), ts: fs.readFileSync(src, "utf8") };
}

function paramNames(ts) {
  const m = ts.match(/function main\(workbook: ExcelScript\.Workbook,?([\s\S]*?)\)\s*:/);
  return m ? [...m[1].matchAll(/(\w+)\s*:/g)].map(x => x[1]) : [];
}

function run(req) {
  const { js, ts } = compile(req.script);
  const names = paramNames(ts);
  const missing = names.filter(n => !(n in req.params));
  if (missing.length) return { ok: false, error: `필수 매개변수 누락: ${missing.join(", ")}` };
  const ctx = vm.createContext({ JSON, Math, Date, Number, String, Array, Object, isNaN, Error });
  vm.runInContext(js, ctx);
  const workbook = {}; // 계산 전용 스크립트는 통합 문서를 사용하지 않는다(접근 시 TypeError → 테스트 실패)
  try {
    const result = ctx.main(workbook, ...names.map(n => req.params[n]));
    return { ok: true, result: JSON.parse(JSON.stringify(result)) };
  } catch (e) {
    return { ok: false, error: String(e && e.message ? e.message : e) };
  }
}

if (require.main === module) {
  const input = fs.readFileSync(0, "utf8");
  process.stdout.write(JSON.stringify(run(JSON.parse(input))));
}

module.exports = { run, paramNames };
