/**
 * Pilot 02 — 공장 주간 제출 파일 검증 (Office Scripts)
 * 데이터 계약 v1.0 (data_contract.json) 규칙 E01~E08, W01~W02 를 검사한다.
 *
 * Power Automate: Excel Online (Business) > "Run script from SharePoint library" 로 제출 파일에 대해 실행.
 *   expectedWeek  : 제출 대상 주차 (예: 2026-W44)
 *   plantCode     : 제출 폴더가 의미하는 공장코드 (예: PLT-A)
 *   validSkusCsv  : 유효 SKU 목록(쉼표 구분). Flow가 SKU 마스터에서 읽어 전달한다.
 * 반환값(JSON)으로 Flow가 합격/반려를 분기한다. 이 스크립트는 제출 파일을 수정하지 않는다(읽기 전용).
 */

interface Issue {
  code: string;
  severity: string; // "Error" | "Warning"
  row: number;      // 표 기준 데이터 행 번호(1부터). 0 = 파일 전체
  column: string;
  message: string;
}

interface ValidationResult {
  ok: boolean;
  contractVersion: string;
  submissionKey: string;
  rowCount: number;
  errorCount: number;
  warningCount: number;
  issues: Issue[];
  issuesTruncated: boolean;
  rowsJson: string; // 계약 열 순서의 정규화된 행 배열(JSON). ok=true일 때 AppendToMaster로 전달
}

const CONTRACT_VERSION = "1.0";
const TABLE_NAME = "tblSubmit";
const COLUMNS: string[] = ["Week", "PlantCode", "SKU", "LineCode", "BeginInv", "Production", "Receipt",
  "Shipment", "Adjustment", "EndInv", "PlanNextWeek", "RunHours", "AvailHours", "Remark"];
const REQUIRED: string[] = ["Week", "PlantCode", "SKU", "LineCode", "BeginInv", "Production", "Receipt",
  "Shipment", "EndInv", "PlanNextWeek", "RunHours", "AvailHours"];
const NON_NEGATIVE: string[] = ["BeginInv", "Production", "Receipt", "Shipment", "EndInv", "PlanNextWeek",
  "RunHours", "AvailHours"];
const NUMERIC: string[] = ["BeginInv", "Production", "Receipt", "Shipment", "Adjustment", "EndInv",
  "PlanNextWeek", "RunHours", "AvailHours"];
const WEEK_PATTERN = /^\d{4}-W\d{2}$/;
const MAX_ISSUES = 200;

function main(workbook: ExcelScript.Workbook, expectedWeek: string, plantCode: string,
  validSkusCsv: string): ValidationResult {
  const skus = validSkusCsv.split(",").map(s => s.trim()).filter(s => s.length > 0);
  const table = workbook.getTable(TABLE_NAME);
  if (!table) {
    return validateRows([], [], expectedWeek, plantCode, skus,
      `표 '${TABLE_NAME}'을(를) 찾을 수 없습니다. 표준 템플릿을 사용했는지 확인하세요.`);
  }
  const header = table.getHeaderRowRange().getValues()[0].map(v => String(v).trim());
  const body = table.getRowCount() > 0 ? table.getRangeBetweenHeaderAndTotal().getValues() : [];
  return validateRows(header, body, expectedWeek, plantCode, skus, "");
}

function isBlank(v: string | number | boolean): boolean {
  return v === null || v === undefined || String(v).trim() === "";
}

function toNumber(v: string | number | boolean): number {
  if (typeof v === "number") return v;
  if (typeof v === "boolean") return NaN;
  const s = String(v).trim();
  return /^-?\d+(\.\d+)?$/.test(s) ? Number(s) : NaN;
}

function validateRows(header: string[], body: (string | number | boolean)[][], expectedWeek: string,
  plantCode: string, validSkus: string[], fatalMessage: string): ValidationResult {
  const issues: Issue[] = [];
  let errorCount = 0;
  let warningCount = 0;
  const add = (code: string, severity: string, row: number, column: string, message: string) => {
    if (severity === "Error") errorCount++; else warningCount++;
    if (issues.length < MAX_ISSUES) issues.push({ code, severity, row, column, message });
  };
  const submissionKey = `${expectedWeek}|${plantCode}`;
  const result = (rowCount: number, rows: (string | number)[][]): ValidationResult => ({
    ok: errorCount === 0,
    contractVersion: CONTRACT_VERSION,
    submissionKey,
    rowCount,
    errorCount,
    warningCount,
    issues,
    issuesTruncated: errorCount + warningCount > issues.length,
    rowsJson: errorCount === 0 ? JSON.stringify(rows) : "[]",
  });

  if (fatalMessage) {
    add("E01", "Error", 0, "", fatalMessage);
    return result(0, []);
  }
  if (validSkus.length === 0) {
    // 안전 측 실패(fail-closed): 마스터가 비면 모든 SKU를 통과시키지 않는다
    add("E05", "Error", 0, "SKU", "SKU 마스터 목록이 전달되지 않았습니다(Flow 설정 확인)");
  }
  if (!WEEK_PATTERN.test(expectedWeek)) {
    add("E03", "Error", 0, "Week", `제출 대상 주차 형식 오류: '${expectedWeek}' (예: 2026-W44)`);
  }

  const idx: { [name: string]: number } = {};
  header.forEach((h, i) => { idx[h] = i; });
  const missing = REQUIRED.filter(c => idx[c] === undefined);
  if (missing.length > 0) {
    add("E01", "Error", 0, missing.join(","), `필수 열 누락: ${missing.join(", ")}`);
    return result(0, []);
  }

  const skuSet: { [sku: string]: boolean } = {};
  validSkus.forEach(s => { skuSet[s] = true; });
  const seen: { [key: string]: number } = {};
  const rows: (string | number)[][] = [];
  let dataRow = 0;

  body.forEach(raw => {
    if (raw.every(v => isBlank(v))) return; // 빈 행 무시
    dataRow++;
    const get = (c: string): string | number | boolean => (idx[c] === undefined ? "" : raw[idx[c]]);
    let rowHasError = false;
    const err = (code: string, col: string, msg: string) => { rowHasError = true; add(code, "Error", dataRow, col, msg); };

    REQUIRED.forEach(c => { if (isBlank(get(c))) err("E02", c, `필수 값 공란: ${c}`); });

    const week = String(get("Week")).trim();
    if (!isBlank(week) && week !== expectedWeek) err("E03", "Week", `주차 '${week}' ≠ 제출 대상 '${expectedWeek}'`);
    const plant = String(get("PlantCode")).trim();
    if (!isBlank(plant) && plant !== plantCode) err("E04", "PlantCode", `공장코드 '${plant}' ≠ 제출 폴더 공장 '${plantCode}'`);
    const sku = String(get("SKU")).trim();
    if (!isBlank(sku) && validSkus.length > 0 && !skuSet[sku]) err("E05", "SKU", `마스터에 없는 SKU: '${sku}'`);

    const n: { [c: string]: number } = {};
    NUMERIC.forEach(c => {
      const v = get(c);
      if (isBlank(v)) { n[c] = 0; return; }
      const x = toNumber(v);
      if (isNaN(x)) { err("E06", c, `숫자가 아님: '${String(v)}'`); n[c] = 0; return; }
      if (NON_NEGATIVE.indexOf(c) >= 0 && x < 0) err("E06", c, `음수 불가: ${x}`);
      n[c] = x;
    });

    const line = String(get("LineCode")).trim();
    const key = `${week}|${plant}|${sku}|${line}`;
    if (seen[key]) err("E07", "SKU", `중복 행(${seen[key]}행과 동일 키): ${key}`);
    else seen[key] = dataRow;

    const inflow = n["BeginInv"] + n["Production"] + n["Receipt"];
    const diff = inflow - n["Shipment"] + n["Adjustment"] - n["EndInv"];
    const tol = Math.max(1, inflow * 0.001);
    if (Math.abs(diff) > tol) err("E08", "EndInv", `PSI 수지 불일치: 차이 ${Math.round(diff * 100) / 100} (허용 ±${Math.round(tol * 100) / 100})`);

    const remark = isBlank(get("Remark")) ? "" : String(get("Remark")).trim();
    if (n["Adjustment"] !== 0 && remark === "") add("W01", "Warning", dataRow, "Remark", "재고조정 사유(비고) 없음");
    if (n["AvailHours"] <= 0 || n["RunHours"] > n["AvailHours"]) {
      add("W02", "Warning", dataRow, "RunHours", `가동 ${n["RunHours"]}h / 가용 ${n["AvailHours"]}h`);
    }

    if (!rowHasError) {
      rows.push([week, plant, sku, line, n["BeginInv"], n["Production"], n["Receipt"], n["Shipment"],
        n["Adjustment"], n["EndInv"], n["PlanNextWeek"], n["RunHours"], n["AvailHours"], remark]);
    }
  });

  if (dataRow === 0) add("E02", "Error", 0, "", "데이터 행이 없습니다");
  return result(dataRow, rows);
}
