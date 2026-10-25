// Office Scripts 로컬 테스트: tsc(strict)로 개별 컴파일 → vm에서 로드 → 모의 Workbook으로 main() 실행.
// 실행: node --test tests/office_scripts.test.js   (Node 18+, TypeScript tsc 필요). 실제 Excel/M365에 접속하지 않는다.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { execFileSync } = require("node:child_process");
const { MockWorkbook } = require("./mock_workbook");

const ROOT = path.resolve(__dirname, "..");
const BUILD = path.join(__dirname, "build");

function load(name, exportsList) {
  const out = path.join(BUILD, name);
  execFileSync("tsc", ["--strict", "--target", "ES2019", "--lib", "ES2019", "--rootDir", ROOT, "--outDir", out,
    path.join(__dirname, "excelscript-stub.d.ts"), path.join(ROOT, "office_scripts", `${name}.ts`)], { stdio: "inherit" });
  const js = fs.readFileSync(path.join(out, "office_scripts", `${name}.js`), "utf8");
  const ctx = vm.createContext({ JSON, Math, Date, Number, String, Array, Object, isNaN });
  vm.runInContext(`${js}\n;globalThis.__x = { ${exportsList.join(", ")} };`, ctx);
  return ctx.__x;
}

const V = load("ValidateSubmission", ["main", "validateRows", "COLUMNS"]);
const A = load("AppendToMaster", ["main", "contiguousRuns", "CONTRACT_COLUMNS", "SYSTEM_COLUMNS"]);
const X = load("BuildExceptionReport", ["main", "shiftWeek", "isoWeeksInYear"]);

const CONTRACT = JSON.parse(fs.readFileSync(path.join(ROOT, "data_contract.json"), "utf8"));
const COLS = CONTRACT.columns.map(c => c.name);
const SKUS = "SKU-1,SKU-2,SKU-3";

function row(o) {
  const base = { Week: "2026-W44", PlantCode: "PLT-A", SKU: "SKU-1", LineCode: "L1", BeginInv: 100, Production: 50,
    Receipt: 0, Shipment: 60, Adjustment: 0, EndInv: 90, PlanNextWeek: 55, RunHours: 80, AvailHours: 100, Remark: "" };
  const r = Object.assign(base, o);
  return COLS.map(c => r[c]);
}

function submissionBook(rows, header = COLS) {
  const wb = new MockWorkbook();
  wb.addMockTable("tblSubmit", header, rows);
  return wb;
}

test("계약 열 정의가 세 스크립트와 data_contract.json에서 동일", () => {
  assert.deepEqual(Array.from(V.COLUMNS), COLS);
  assert.deepEqual(Array.from(A.CONTRACT_COLUMNS), COLS);
  assert.deepEqual(Array.from(A.SYSTEM_COLUMNS), CONTRACT.systemColumns);
});

test("정상 제출은 통과하고 rowsJson을 반환", () => {
  const wb = submissionBook([row({}), row({ SKU: "SKU-2" }), COLS.map(() => "")]); // 빈 행은 무시
  const r = V.main(wb, "2026-W44", "PLT-A", SKUS);
  assert.equal(r.ok, true);
  assert.equal(r.rowCount, 2);
  assert.equal(r.errorCount, 0);
  assert.equal(r.submissionKey, "2026-W44|PLT-A");
  assert.equal(JSON.parse(r.rowsJson).length, 2);
});

test("오류 규칙 E02~E08 검출", () => {
  const wb = submissionBook([
    row({ Week: "2026-W43" }),                 // E03
    row({ PlantCode: "PLT-B", SKU: "SKU-2" }), // E04
    row({ SKU: "SKU-X" }),                     // E05
    row({ SKU: "SKU-3", Shipment: "abc" }),    // E06 (+ PSI)
    row({ LineCode: "L2", Production: -5 }),   // E06 음수 (+ PSI)
    row({}), row({}),                          // E07 중복 (첫 행은 정상)
    row({ SKU: "SKU-2", LineCode: "L9", EndInv: 80 }),  // E08
    row({ SKU: "SKU-3", LineCode: "L3", Remark: "", BeginInv: "" }), // E02
  ]);
  const r = V.main(wb, "2026-W44", "PLT-A", SKUS);
  assert.equal(r.ok, false);
  const codes = new Set(r.issues.map(i => i.code));
  for (const c of ["E02", "E03", "E04", "E05", "E06", "E07", "E08"]) assert.ok(codes.has(c), `missing ${c}`);
  assert.equal(r.rowsJson, "[]");
});

test("PSI 허용오차: 0.1% 이내는 통과", () => {
  // 유입 10000 → 허용 ±10. 차이 9는 통과, 11은 실패
  const ok = V.main(submissionBook([row({ BeginInv: 10000, Production: 0, Shipment: 0, EndInv: 9991 })]), "2026-W44", "PLT-A", SKUS);
  assert.equal(ok.ok, true);
  const ng = V.main(submissionBook([row({ BeginInv: 10000, Production: 0, Shipment: 0, EndInv: 9989 })]), "2026-W44", "PLT-A", SKUS);
  assert.equal(ng.ok, false);
});

test("경고 W01/W02는 통과를 막지 않음", () => {
  const r = V.main(submissionBook([row({ Adjustment: -5, EndInv: 85, RunHours: 120 })]), "2026-W44", "PLT-A", SKUS);
  assert.equal(r.ok, true);
  assert.deepEqual(Array.from(r.issues.map(i => i.code)).sort(), ["W01", "W02"]);
});

test("필수 열 누락·표 없음·SKU 마스터 없음은 파일 단위 오류(fail-closed)", () => {
  const noCol = V.main(submissionBook([row({})].map(r => r.slice(1)), COLS.slice(1)), "2026-W44", "PLT-A", SKUS);
  assert.equal(noCol.ok, false);
  assert.equal(noCol.issues[0].code, "E01");
  const noTable = V.main(new MockWorkbook(), "2026-W44", "PLT-A", SKUS);
  assert.equal(noTable.ok, false);
  const noSku = V.main(submissionBook([row({})]), "2026-W44", "PLT-A", "");
  assert.equal(noSku.ok, false);
  assert.ok(noSku.issues.some(i => i.code === "E05" && i.row === 0));
  const empty = V.main(submissionBook([]), "2026-W44", "PLT-A", SKUS);
  assert.equal(empty.ok, false);
});

test("검증 스크립트는 제출 파일을 수정하지 않음", () => {
  const wb = submissionBook([row({})]);
  const before = JSON.stringify(wb.tables.tblSubmit.rows);
  V.main(wb, "2026-W44", "PLT-A", SKUS);
  assert.equal(JSON.stringify(wb.tables.tblSubmit.rows), before);
  assert.deepEqual(wb.tables.tblSubmit.calls, []);
});

function masterBook(rows = []) {
  const wb = new MockWorkbook();
  wb.addMockTable("tblFact", COLS.concat(CONTRACT.systemColumns), rows);
  return wb;
}

test("contiguousRuns", () => {
  assert.deepEqual(JSON.parse(JSON.stringify(A.contiguousRuns([1, 2, 3, 7, 8, 10]))), [[1, 3], [7, 2], [10, 1]]);
  assert.deepEqual(JSON.parse(JSON.stringify(A.contiguousRuns([]))), []);
});

test("업서트는 멱등: 같은 제출을 두 번 반영해도 결과 동일", () => {
  const wb = masterBook();
  const other = row({ Week: "2026-W43" }).concat(["2026-W43|PLT-A", "t0", "x"]);
  wb.tables.tblFact.rows.push(other);
  const payload = JSON.stringify([row({}), row({ SKU: "SKU-2" })]);
  const r1 = A.main(wb, "2026-W44|PLT-A", payload, "flow");
  assert.equal(r1.ok, true);
  assert.equal(r1.insertedRows, 2);
  const snapshot = wb.tables.tblFact.rows.map(r => r.slice(0, COLS.length + 1));
  const r2 = A.main(wb, "2026-W44|PLT-A", payload, "flow");
  assert.equal(r2.deletedRows, 2);
  assert.equal(r2.totalRows, 3);
  assert.deepEqual(wb.tables.tblFact.rows.map(r => r.slice(0, COLS.length + 1)), snapshot);
  assert.deepEqual(wb.tables.tblFact.rows[0], other); // 다른 주차 데이터 보존
});

test("재제출 시 흩어진 기존 행도 모두 교체", () => {
  const k = "2026-W44|PLT-A";
  const mk = (sku, key) => row({ SKU: sku }).concat([key, "t0", "x"]);
  const wb = masterBook([mk("SKU-1", k), mk("SKU-9", "2026-W44|PLT-B"), mk("SKU-2", k), mk("SKU-3", k)]);
  const r = A.main(wb, k, JSON.stringify([row({ SKU: "SKU-3" })]), "flow");
  assert.equal(r.deletedRows, 3);
  assert.deepEqual(wb.tables.tblFact.rows.map(x => x[COLS.length]), ["2026-W44|PLT-B", k]);
});

test("업서트 방어: 잘못된 입력은 아무것도 바꾸지 않음", () => {
  const wb = masterBook([row({}).concat(["2026-W44|PLT-A", "t0", "x"])]);
  const before = JSON.stringify(wb.tables.tblFact.rows);
  assert.equal(A.main(wb, "2026-W44|PLT-A", "{bad", "f").ok, false);
  assert.equal(A.main(wb, "2026-W44|PLT-A", JSON.stringify([[1, 2]]), "f").ok, false);
  assert.equal(A.main(wb, "2026-W44|PLT-A", JSON.stringify([row({ PlantCode: "PLT-B" })]), "f").ok, false);
  assert.equal(JSON.stringify(wb.tables.tblFact.rows), before);
  const badHeader = new MockWorkbook();
  badHeader.addMockTable("tblFact", COLS, []);
  assert.equal(A.main(badHeader, "k", "[]", "f").ok, false);
});

test("ISO 주차 계산", () => {
  assert.equal(X.isoWeeksInYear(2026), 53);
  assert.equal(X.isoWeeksInYear(2025), 52);
  assert.equal(X.isoWeeksInYear(2020), 53);
  assert.equal(X.shiftWeek("2026-W44", -1), "2026-W43");
  assert.equal(X.shiftWeek("2027-W01", -1), "2026-W53");
  assert.equal(X.shiftWeek("2026-W01", -1), "2025-W52");
  assert.equal(X.shiftWeek("2026-W53", 1), "2027-W01");
});

test("예외 리포트 X01~X05 산출과 시트 기록", () => {
  const fact = (o) => row(o).concat([`${o.Week}|${o.PlantCode || "PLT-A"}`, "t", "f"]);
  const rows = [];
  for (const w of ["2026-W41", "2026-W42", "2026-W43"]) {
    rows.push(fact({ Week: w, SKU: "SKU-1", Shipment: 60, PlanNextWeek: 100, Production: 100, BeginInv: 50, EndInv: 90 }));
    rows.push(fact({ Week: w, SKU: "SKU-2", Shipment: 10, Production: 10, BeginInv: 1000, EndInv: 1000, PlanNextWeek: 10 }));
  }
  // 금주: SKU-1 기초재고 불일치(X01), 생산 급감(X02), 계획 대비 50%(X05), 재고 커버 부족(X04 High)
  rows.push(fact({ Week: "2026-W44", SKU: "SKU-1", BeginInv: 70, Production: 50, Shipment: 100, EndInv: 20, PlanNextWeek: 100, RunHours: 98, AvailHours: 100 }));
  // 금주: SKU-2 재고 과잉(X04 Medium)
  rows.push(fact({ Week: "2026-W44", SKU: "SKU-2", BeginInv: 1000, Production: 10, Shipment: 10, EndInv: 1000, PlanNextWeek: 10, RunHours: 0, AvailHours: 0 }));
  const wb = masterBook(rows);
  const s = X.main(wb, "2026-W44");
  assert.equal(s.ok, true);
  assert.equal(s.previousWeek, "2026-W43");
  assert.deepEqual(Array.from(s.plantsLoaded), ["PLT-A"]);
  for (const c of ["X01", "X02", "X03", "X04", "X05"]) assert.ok(s.counts[c] >= 1, `missing ${c}`);
  assert.equal(s.top[0].severity, "High");
  const sheet = wb.sheets["Exceptions"].cells;
  assert.equal(sheet[0][0], "Week");
  assert.equal(sheet.length, s.totalExceptions + 1);
  // 재실행해도 시트가 누적되지 않음
  X.main(wb, "2026-W44");
  assert.equal(wb.sheets["Exceptions"].cells.length, s.totalExceptions + 1);
});

test("예외 없는 정상 주차는 침묵", () => {
  const fact = (o) => row(o).concat([`${o.Week}|PLT-A`, "t", "f"]);
  const rows = ["2026-W41", "2026-W42", "2026-W43", "2026-W44"].map(w =>
    fact({ Week: w, BeginInv: 100, Production: 50, Shipment: 50, EndInv: 100, PlanNextWeek: 50, RunHours: 50, AvailHours: 100 }));
  const s = X.main(masterBook(rows), "2026-W44");
  assert.equal(s.totalExceptions, 0);
});

test("교차 검증: Office Scripts 결과 == Python 검증기 결과(sample_data/expected_issues.json)", () => {
  const sd = path.join(ROOT, "sample_data");
  const expected = JSON.parse(fs.readFileSync(path.join(sd, "expected_issues.json"), "utf8"));
  const skus = fs.readFileSync(path.join(sd, "sku_master.txt"), "utf8").split(/\s+/).filter(Boolean).join(",");
  for (const [file, codes] of Object.entries(expected)) {
    const lines = fs.readFileSync(path.join(sd, file), "utf8").replace(/^﻿/, "").trim().split(/\r?\n/);
    const parseLine = l => (l.match(/("([^"]|"")*"|[^,]*)(,|$)/g) || []).slice(0, -1)
      .map(c => c.replace(/,$/, "").replace(/^"|"$/g, "").replace(/""/g, '"'));
    const header = parseLine(lines[0]);
    const rows = lines.slice(1).map(parseLine);
    const plant = file.split("_")[0];
    const r = V.main(submissionBook(rows, header), "2026-W44", plant, skus);
    const got = Array.from(r.issues.map(i => `${i.code}@${i.row}`)).sort();
    assert.deepEqual(got, codes, file);
  }
});
