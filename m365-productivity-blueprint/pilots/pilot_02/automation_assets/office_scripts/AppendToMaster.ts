/**
 * Pilot 02 — 검증 통과 데이터를 마스터(단일 원본) 표 tblFact 에 반영 (Office Scripts)
 *
 * 멱등(Idempotent) 업서트: 같은 SubmissionKey(주차|공장)의 기존 행을 지우고 새 행을 넣는다.
 *   → 공장이 같은 주차를 다시 제출하거나 Flow가 재시도되어도 중복 행이 생기지 않는다.
 * Power Automate: Excel Online (Business) > "Run script from SharePoint library" 로 마스터 파일에 대해 실행.
 *   Flow 동시성 제어(Concurrency) = 1 로 설정해 마스터에 동시 쓰기가 일어나지 않게 한다.
 */

interface AppendResult {
  ok: boolean;
  submissionKey: string;
  deletedRows: number;
  insertedRows: number;
  totalRows: number;
  message: string;
}

const FACT_TABLE = "tblFact";
const CONTRACT_COLUMNS: string[] = ["Week", "PlantCode", "SKU", "LineCode", "BeginInv", "Production", "Receipt",
  "Shipment", "Adjustment", "EndInv", "PlanNextWeek", "RunHours", "AvailHours", "Remark"];
const SYSTEM_COLUMNS: string[] = ["SubmissionKey", "LoadedAtUtc", "LoadedBy"];
const MAX_ROWS_PER_CALL = 5000;

function main(workbook: ExcelScript.Workbook, submissionKey: string, rowsJson: string,
  loadedBy: string): AppendResult {
  const fail = (message: string): AppendResult =>
    ({ ok: false, submissionKey, deletedRows: 0, insertedRows: 0, totalRows: 0, message });

  const table = workbook.getTable(FACT_TABLE);
  if (!table) return fail(`표 '${FACT_TABLE}'이(가) 없습니다`);

  const header = table.getHeaderRowRange().getValues()[0].map(v => String(v));
  const expected = CONTRACT_COLUMNS.concat(SYSTEM_COLUMNS);
  if (header.join("|") !== expected.join("|")) {
    return fail(`tblFact 머리글이 계약과 다릅니다. 기대: ${expected.join(",")}`);
  }

  let incoming: (string | number)[][];
  try {
    incoming = JSON.parse(rowsJson) as (string | number)[][];
  } catch (e) {
    return fail("rowsJson 파싱 실패");
  }
  if (!Array.isArray(incoming)) return fail("rowsJson 은 배열이어야 합니다");
  if (incoming.length > MAX_ROWS_PER_CALL) return fail(`한 번에 ${MAX_ROWS_PER_CALL}행 초과`);
  for (let i = 0; i < incoming.length; i++) {
    const r = incoming[i];
    if (!Array.isArray(r) || r.length !== CONTRACT_COLUMNS.length) return fail(`${i + 1}번째 행의 열 개수 오류`);
    if (`${r[0]}|${r[1]}` !== submissionKey) return fail(`${i + 1}번째 행이 SubmissionKey와 다릅니다`);
  }

  // 1) 같은 키의 기존 행 삭제 — SubmissionKey 열만 읽어 성능 확보, 아래쪽 블록부터 삭제해 인덱스 보존
  let deleted = 0;
  if (table.getRowCount() > 0) {
    const keys = table.getColumnByName("SubmissionKey").getRangeBetweenHeaderAndTotal().getValues()
      .map(r => String(r[0]));
    const runs = contiguousRuns(keys.map((k, i) => (k === submissionKey ? i : -1)).filter(i => i >= 0));
    for (let j = runs.length - 1; j >= 0; j--) {
      table.deleteRowsAt(runs[j][0], runs[j][1]);
      deleted += runs[j][1];
    }
  }

  // 2) 새 행 추가 (한 번의 호출로 일괄 추가)
  const now = new Date().toISOString();
  const values = incoming.map(r => r.concat([submissionKey, now, loadedBy]));
  if (values.length > 0) table.addRows(-1, values);

  return { ok: true, submissionKey, deletedRows: deleted, insertedRows: values.length,
    totalRows: table.getRowCount(), message: "OK" };
}

/** 정렬된 인덱스 목록 → [시작인덱스, 개수] 블록 목록 */
function contiguousRuns(indices: number[]): number[][] {
  const runs: number[][] = [];
  indices.forEach(i => {
    const last = runs.length > 0 ? runs[runs.length - 1] : null;
    if (last && last[0] + last[1] === i) last[1]++;
    else runs.push([i, 1]);
  });
  return runs;
}
