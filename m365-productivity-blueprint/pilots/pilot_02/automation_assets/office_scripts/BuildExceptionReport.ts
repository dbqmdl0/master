/**
 * Pilot 02 — 주간 예외 리포트 생성 (Office Scripts, 마스터 파일에서 실행)
 * 정상은 침묵, 예외만 보고(Management by Exception). 규칙 X01~X05 (data_contract.json exceptionRules)
 *
 * 결과: 'Exceptions' 시트를 다시 쓰고(이 시트 외 데이터는 변경하지 않음), 요약 JSON을 반환 →
 *       Flow가 Teams 채널에 예외 요약 카드 1장을 게시한다.
 */

interface ExceptionItem {
  week: string;
  code: string;
  severity: string; // High | Medium
  plantCode: string;
  lineCode: string;
  sku: string;
  metric: number;
  detail: string;
}

interface ReportSummary {
  ok: boolean;
  week: string;
  previousWeek: string;
  plantsLoaded: string[];
  totalExceptions: number;
  counts: { [code: string]: number };
  top: ExceptionItem[];
  message: string;
}

const FACT_TABLE = "tblFact";
const OUTPUT_SHEET = "Exceptions";
const TOP_N = 15;
const SWING_RATIO = 0.3;
const SWING_MIN_BASE = 100;
const UTIL_LIMIT = 0.95;
const COVER_MAX_WEEKS = 8;
const COVER_MIN_WEEKS = 1;
const ATTAIN_LOW = 0.9;
const ATTAIN_HIGH = 1.1;

function main(workbook: ExcelScript.Workbook, week: string): ReportSummary {
  const table = workbook.getTable(FACT_TABLE);
  if (!table) return emptySummary(week, `표 '${FACT_TABLE}'이(가) 없습니다`);
  const header = table.getHeaderRowRange().getValues()[0].map(v => String(v));
  const body = table.getRowCount() > 0 ? table.getRangeBetweenHeaderAndTotal().getValues() : [];
  const summary = buildExceptions(header, body, week);
  writeSheet(workbook, summary.items);
  return summary.summary;
}

function emptySummary(week: string, message: string): ReportSummary {
  return { ok: false, week, previousWeek: "", plantsLoaded: [], totalExceptions: 0, counts: {}, top: [], message };
}

function isoWeeksInYear(y: number): number {
  const p = (yy: number) => (yy + Math.floor(yy / 4) - Math.floor(yy / 100) + Math.floor(yy / 400)) % 7;
  return p(y) === 4 || p(y - 1) === 3 ? 53 : 52;
}

function shiftWeek(week: string, delta: number): string {
  let y = Number(week.substring(0, 4));
  let w = Number(week.substring(6));
  w += delta;
  while (w < 1) { y -= 1; w += isoWeeksInYear(y); }
  while (w > isoWeeksInYear(y)) { w -= isoWeeksInYear(y); y += 1; }
  return `${y}-W${w < 10 ? "0" + w : String(w)}`;
}

interface FactRow {
  week: string; plant: string; sku: string; line: string;
  begin: number; prod: number; ship: number; end: number; planNext: number; run: number; avail: number;
}

function buildExceptions(header: string[], body: (string | number | boolean)[][], week: string):
  { summary: ReportSummary; items: ExceptionItem[] } {
  const ix: { [c: string]: number } = {};
  header.forEach((h, i) => { ix[h] = i; });
  const num = (r: (string | number | boolean)[], c: string): number => Number(r[ix[c]]) || 0;
  const str = (r: (string | number | boolean)[], c: string): string => String(r[ix[c]]).trim();

  const prevWeek = shiftWeek(week, -1);
  const window: string[] = [week, prevWeek, shiftWeek(week, -2), shiftWeek(week, -3)];
  const rows: FactRow[] = body
    .filter(r => window.indexOf(str(r, "Week")) >= 0)
    .map(r => ({
      week: str(r, "Week"), plant: str(r, "PlantCode"), sku: str(r, "SKU"), line: str(r, "LineCode"),
      begin: num(r, "BeginInv"), prod: num(r, "Production"), ship: num(r, "Shipment"), end: num(r, "EndInv"),
      planNext: num(r, "PlanNextWeek"), run: num(r, "RunHours"), avail: num(r, "AvailHours"),
    }));

  const cur = rows.filter(r => r.week === week);
  const prevByKey: { [k: string]: FactRow } = {};
  rows.filter(r => r.week === prevWeek).forEach(r => { prevByKey[`${r.plant}|${r.sku}|${r.line}`] = r; });

  const items: ExceptionItem[] = [];
  const push = (code: string, severity: string, r: { plant: string; line: string; sku: string },
    metric: number, detail: string) =>
    items.push({ week, code, severity, plantCode: r.plant, lineCode: r.line, sku: r.sku,
      metric: Math.round(metric * 1000) / 1000, detail });

  cur.forEach(r => {
    const p = prevByKey[`${r.plant}|${r.sku}|${r.line}`];
    if (!p) return;
    const tol = Math.max(1, p.end * 0.001);
    if (Math.abs(r.begin - p.end) > tol) {
      push("X01", "High", r, r.begin - p.end, `기초재고 ${r.begin} ≠ 전주 기말 ${p.end}`);
    }
    const base = Math.max(r.prod, p.prod);
    if (base >= SWING_MIN_BASE && p.prod > 0 && Math.abs(r.prod - p.prod) / p.prod > SWING_RATIO) {
      push("X02", "Medium", r, (r.prod - p.prod) / p.prod, `생산 ${p.prod} → ${r.prod}`);
    }
    if (p.planNext > 0) {
      const att = r.prod / p.planNext;
      if (att < ATTAIN_LOW || att > ATTAIN_HIGH) {
        push("X05", "Medium", r, att, `계획 ${p.planNext} 대비 실적 ${r.prod} (${Math.round(att * 100)}%)`);
      }
    }
  });

  // X03 가동률: 공장·라인 단위 합산
  const util: { [k: string]: { plant: string; line: string; run: number; avail: number } } = {};
  cur.forEach(r => {
    const k = `${r.plant}|${r.line}`;
    if (!util[k]) util[k] = { plant: r.plant, line: r.line, run: 0, avail: 0 };
    util[k].run += r.run;
    util[k].avail += r.avail;
  });
  Object.keys(util).sort().forEach(k => {
    const u = util[k];
    const rate = u.avail > 0 ? u.run / u.avail : 0;
    if (rate > UTIL_LIMIT) {
      push("X03", rate > 1 ? "High" : "Medium", { plant: u.plant, line: u.line, sku: "" }, rate,
        `가동률 ${Math.round(rate * 1000) / 10}% (가동 ${u.run}h / 가용 ${u.avail}h)`);
    }
  });

  // X04 재고 커버: 공장·SKU 단위(라인 합산), 최근 4주 평균 출하 기준
  const inv: { [k: string]: { plant: string; sku: string; end: number; ship: number[] } } = {};
  rows.forEach(r => {
    const k = `${r.plant}|${r.sku}`;
    if (!inv[k]) inv[k] = { plant: r.plant, sku: r.sku, end: 0, ship: [0, 0, 0, 0] };
    const wi = window.indexOf(r.week);
    inv[k].ship[wi] += r.ship;
    if (r.week === week) inv[k].end += r.end;
  });
  Object.keys(inv).sort().forEach(k => {
    const v = inv[k];
    if (!cur.some(r => r.plant === v.plant && r.sku === v.sku)) return;
    const avgShip = v.ship.reduce((a, b) => a + b, 0) / 4;
    if (avgShip <= 0) return;
    const cover = v.end / avgShip;
    if (cover > COVER_MAX_WEEKS) {
      push("X04", "Medium", { plant: v.plant, line: "", sku: v.sku }, cover, `재고 ${Math.round(cover * 10) / 10}주분(과잉)`);
    } else if (cover < COVER_MIN_WEEKS) {
      push("X04", "High", { plant: v.plant, line: "", sku: v.sku }, cover, `재고 ${Math.round(cover * 10) / 10}주분(결품 위험)`);
    }
  });

  const counts: { [code: string]: number } = {};
  items.forEach(i => { counts[i.code] = (counts[i.code] || 0) + 1; });
  const sevRank = (s: string) => (s === "High" ? 0 : 1);
  const sorted = items.slice().sort((a, b) =>
    sevRank(a.severity) - sevRank(b.severity) || a.code.localeCompare(b.code) ||
    Math.abs(b.metric) - Math.abs(a.metric) || a.plantCode.localeCompare(b.plantCode) || a.sku.localeCompare(b.sku));
  const plants: string[] = [];
  cur.forEach(r => { if (plants.indexOf(r.plant) < 0) plants.push(r.plant); });
  plants.sort();

  return {
    summary: {
      ok: true, week, previousWeek: prevWeek, plantsLoaded: plants, totalExceptions: items.length,
      counts, top: sorted.slice(0, TOP_N), message: cur.length === 0 ? "해당 주차 데이터 없음" : "OK",
    },
    items: sorted,
  };
}

function writeSheet(workbook: ExcelScript.Workbook, items: ExceptionItem[]) {
  let ws = workbook.getWorksheet(OUTPUT_SHEET);
  if (!ws) ws = workbook.addWorksheet(OUTPUT_SHEET);
  const used = ws.getUsedRange();
  if (used) used.clear();
  const data: (string | number)[][] = [["Week", "Code", "Severity", "PlantCode", "LineCode", "SKU", "Metric", "Detail"]];
  items.forEach(i => data.push([i.week, i.code, i.severity, i.plantCode, i.lineCode, i.sku, i.metric, i.detail]));
  ws.getRange("A1").getResizedRange(data.length - 1, data[0].length - 1).setValues(data);
}
