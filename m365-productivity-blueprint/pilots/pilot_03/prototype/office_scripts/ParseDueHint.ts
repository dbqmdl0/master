/**
 * 추가 기능 A — 메일 문구에서 기한·긴급도 추정 (Office Scripts)
 *
 * '내일까지', '10/30까지', '이번 주 중', '금요일까지', '긴급' 같은 표현을 찾아 기한(YYYY-MM-DD)을 제안한다.
 * 기한 표지(까지·마감·중·전·due·by)가 붙은 날짜만 기한으로 본다 → 회의 날짜·수량(1.2만)을 기한으로 오인하지 않는다.
 * 후보가 여럿이면 가장 이른 날짜(보수적)를 고르고, 근거 문구를 함께 돌려준다(목록에 '기한 근거'로 표시).
 * 통합 문서는 수정하지 않는다.
 */

interface DueHint {
  dueDate: string;   // "" = 찾지 못함
  phrase: string;    // 근거 문구
  rule: string;      // explicit | relative | weekday | week | none
  priority: string;  // 높음 | ""
}

const KST_OFFSET_MS = 9 * 3600 * 1000;
const DEADLINE = "(?:\\s*(?:까지|마감|중으로|중에|중|전까지|전|이내|due|by))";
const URGENT = /(긴급|시급|급히|급건|ASAP|asap|urgent|URGENT)/;
const WEEKDAYS: string[] = ["일", "월", "화", "수", "목", "금", "토"];

function main(workbook: ExcelScript.Workbook, text: string, receivedKst: string, holidaysJson: string): DueHint {
  return parseDueHint(text, receivedKst, parseHolidays(holidaysJson));
}

function parseHolidays(s: string): string[] {
  try {
    const v = JSON.parse(s && s.trim() !== "" ? s : "[]") as { [k: string]: unknown }[];
    if (!Array.isArray(v)) return [];
    return v.map(h => kstDate(String(h["HolidayDate"] !== undefined ? h["HolidayDate"] : h["date"] || ""))).filter(x => x !== "");
  } catch (e) {
    return [];
  }
}

function kstDate(s: string): string {
  const t = (s || "").trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(t)) return t;
  const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(t);
  const ms = Date.parse(hasZone ? t : t + "Z");
  return isNaN(ms) ? "" : new Date(ms + KST_OFFSET_MS).toISOString().substring(0, 10);
}

function addDays(d: string, n: number): string {
  return new Date(Date.parse(d + "T00:00:00Z") + n * 86400000).toISOString().substring(0, 10);
}

function weekday(d: string): number {
  return new Date(d + "T00:00:00Z").getUTCDay();
}

function isBusinessDay(d: string, holidays: string[]): boolean {
  const w = weekday(d);
  return w !== 0 && w !== 6 && holidays.indexOf(d) < 0;
}

function addBusinessDays(d: string, n: number, holidays: string[]): string {
  let cur = d;
  let added = 0;
  while (added < n) {
    cur = addDays(cur, 1);
    if (isBusinessDay(cur, holidays)) added++;
  }
  return cur;
}

function validDate(y: number, m: number, d: number): string {
  if (m < 1 || m > 12 || d < 1 || d > 31) return "";
  const s = `${y}-${m < 10 ? "0" + m : m}-${d < 10 ? "0" + d : d}`;
  const dt = new Date(s + "T00:00:00Z");
  return !isNaN(dt.getTime()) && dt.toISOString().substring(0, 10) === s ? s : "";
}

function parseDueHint(textRaw: string, received: string, holidays: string[]): DueHint {
  const none: DueHint = { dueDate: "", phrase: "", rule: "none", priority: "" };
  if (!/^\d{4}-\d{2}-\d{2}$/.test(received)) throw new Error(`receivedKst 형식 오류: ${received}`);
  const text = (textRaw || "").replace(/\s+/g, " ");
  none.priority = URGENT.test(text) ? "높음" : "";
  const cands: { date: string; phrase: string; rule: string }[] = [];
  const year = Number(received.substring(0, 4));
  const pushExplicit = (m: number, d: number, phrase: string) => {
    let s = validDate(year, m, d);
    if (s === "") return;
    // 받은 날보다 60일 넘게 이전이면 내년으로 본다(예: 12월에 받은 '1/5까지')
    if (Date.parse(s) < Date.parse(received) - 60 * 86400000) s = validDate(year + 1, m, d);
    if (s !== "") cands.push({ date: s, phrase, rule: "explicit" });
  };

  // 1) 명시 날짜 + 기한 표지: "10/30까지", "11월 3일까지", "10/30(금) 마감"
  const reSlash = new RegExp(`(\\d{1,2})\\s*/\\s*(\\d{1,2})(?:\\s*\\([월화수목금토일]\\))?${DEADLINE}`, "g");
  const reKor = new RegExp(`(\\d{1,2})\\s*월\\s*(\\d{1,2})\\s*일(?:\\s*\\([월화수목금토일]\\))?${DEADLINE}`, "g");
  let m: RegExpExecArray | null;
  while ((m = reSlash.exec(text)) !== null) pushExplicit(Number(m[1]), Number(m[2]), m[0].trim());
  while ((m = reKor.exec(text)) !== null) pushExplicit(Number(m[1]), Number(m[2]), m[0].trim());

  // 2) 상대 표현
  const rel: { re: RegExp; date: () => string }[] = [
    { re: /(오늘|금일|당일|today)\s*(?:까지|중으로|중에|중|내로|내)|\bEOD\b/i, date: () => received },
    { re: /(내일|명일|tomorrow)\s*(?:까지|중으로|중에|중|오전|오후|내로|내)?/i, date: () => addBusinessDays(received, 1, holidays) },
    { re: /모레\s*(?:까지|중)?/, date: () => addBusinessDays(received, 2, holidays) },
  ];
  rel.forEach(r => {
    const x = text.match(r.re);
    if (x) cands.push({ date: r.date(), phrase: x[0].trim(), rule: "relative" });
  });

  // 3) 이번 주 / 다음 주 → 해당 주 금요일
  const wd = weekday(received);
  const thisFri = addDays(received, (5 - wd + 7) % 7); // 금요일이면 오늘, 주말이면 다음 금요일
  const w1 = text.match(/(이번\s*주|금주|this week)\s*(?:까지|중으로|중에|중|내로|내)/i);
  if (w1) cands.push({ date: thisFri, phrase: w1[0].trim(), rule: "week" });
  const w2 = text.match(/(다음\s*주|차주|next week)\s*(?:까지|중으로|중에|중|내로|내|초)?/i);
  if (w2) cands.push({ date: wd === 6 || wd === 0 ? thisFri : addDays(thisFri, 7), phrase: w2[0].trim(), rule: "week" });

  // 4) 요일 + 까지: "금요일까지" → 오늘 포함 가장 가까운 그 요일
  const reDay = /([월화수목금])요일\s*(?:까지|중|오전|오후|마감)/g;
  while ((m = reDay.exec(text)) !== null) {
    const target = WEEKDAYS.indexOf(m[1]);
    cands.push({ date: addDays(received, (target - wd + 7) % 7), phrase: m[0].trim(), rule: "weekday" });
  }

  const valid = cands.filter(c => c.date >= received);
  if (valid.length === 0) return none;
  valid.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
  return { dueDate: valid[0].date, phrase: valid[0].phrase, rule: valid[0].rule, priority: none.priority };
}
