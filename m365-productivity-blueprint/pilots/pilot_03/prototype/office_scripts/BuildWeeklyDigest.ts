/**
 * 추가 기능 C — 주간 정리(주간보고 초안) (Office Scripts)
 *
 * 이번 주(월~오늘) 목록 데이터에서 자동으로 만든다 — 사람이 다시 타이핑하지 않는다.
 *   완료한 일 · 새로 생긴 일 · 기한 초과 · 다음 주 마감 · 확정된 결정 · 결정 대기 · 회신 대기 초과
 *   + 공장 자료 수신 패턴(이번 주 공장별 건수, 최근 4주 요일별 분포) → Pilot 02(데이터 계약) 재설계 근거
 * 결과 HTML을 본인 메일로 받아, 그대로 전달하거나 고쳐서 주간보고로 쓴다.
 * 통합 문서는 수정하지 않는다.
 */

interface WeeklyCounts {
  completed: number;
  created: number;
  overdue: number;
  dueNextWeek: number;
  decided: number;
  waitingDecisions: number;
  replyOverdue: number;
  factoryMails: number;
  factoryFiles: number;
}

interface WeeklyResult {
  week: string;
  weekStart: string;
  counts: WeeklyCounts;
  htmlSummary: string;
}

const KST_OFFSET_MS = 9 * 3600 * 1000;
const OPEN: string[] = ["미착수", "진행중"];
const MAX_LINES = 8;
const WD: string[] = ["일", "월", "화", "수", "목", "금", "토"];

type Raw = { [key: string]: unknown };

function main(workbook: ExcelScript.Workbook, meEmail: string, todayKst: string, actionsJson: string,
  decisionsJson: string, inboxJson: string): WeeklyResult {
  return build(meEmail, todayKst, arr(actionsJson, "actionsJson"), arr(decisionsJson, "decisionsJson"), arr(inboxJson, "inboxJson"));
}

function arr(s: string, name: string): Raw[] {
  let v: unknown;
  try { v = JSON.parse(s && s.trim() !== "" ? s : "[]"); } catch (e) { throw new Error(`${name}: JSON 형식 오류`); }
  if (!Array.isArray(v)) throw new Error(`${name}: 배열이 아닙니다`);
  return v as Raw[];
}

function text(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "object") {
    const o = v as Raw;
    if (o["Value"] !== undefined) return String(o["Value"]);
    if (o["Email"] !== undefined) return String(o["Email"]);
    if (o["EMail"] !== undefined) return String(o["EMail"]);
    return "";
  }
  return String(v);
}

function kstDate(v: unknown): string {
  const s = text(v).trim();
  if (s === "") return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(s);
  const t = s.replace(/(\.\d{3})\d+/, "$1");
  const ms = Date.parse(hasZone ? t : t + "Z");
  return isNaN(ms) ? "" : new Date(ms + KST_OFFSET_MS).toISOString().substring(0, 10);
}

function addDays(d: string, n: number): string {
  return new Date(Date.parse(d + "T00:00:00Z") + n * 86400000).toISOString().substring(0, 10);
}

function dayDiff(a: string, b: string): number {
  return Math.round((Date.parse(b + "T00:00:00Z") - Date.parse(a + "T00:00:00Z")) / 86400000);
}

function isoWeek(d: string): string {
  const dt = new Date(d + "T00:00:00Z");
  const wd = (dt.getUTCDay() + 6) % 7; // 월=0
  const thu = new Date(dt.getTime() + (3 - wd) * 86400000);
  const y = thu.getUTCFullYear();
  const jan4 = new Date(Date.UTC(y, 0, 4));
  const wk = 1 + Math.round(((thu.getTime() - jan4.getTime()) / 86400000 - 3 + ((jan4.getUTCDay() + 6) % 7)) / 7);
  return `${y}-W${wk < 10 ? "0" + wk : wk}`;
}

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function list(title: string, rows: string[]): string {
  if (rows.length === 0) return `<h4>${esc(title)} (0)</h4>`;
  return `<h4>${esc(title)} (${rows.length})</h4><ul>` + rows.slice(0, MAX_LINES).map(r => `<li>${r}</li>`).join("") +
    (rows.length > MAX_LINES ? `<li>외 ${rows.length - MAX_LINES}건</li>` : "") + "</ul>";
}

function build(meEmail: string, today: string, actions: Raw[], decisions: Raw[], inbox: Raw[]): WeeklyResult {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(today)) throw new Error(`todayKst 형식 오류: ${today}`);
  const me = meEmail.trim().toLowerCase();
  const wd = (new Date(today + "T00:00:00Z").getUTCDay() + 6) % 7;
  const start = addDays(today, -wd);              // 이번 주 월요일
  const nextMon = addDays(start, 7);
  const nextFri = addDays(start, 11);
  const inWeek = (d: string) => d !== "" && d >= start && d <= today;
  const mine = actions.filter(a => { const o = text(a["Owner"]).trim().toLowerCase(); return o === "" || o === me; });
  const label = (a: Raw) => `${esc(text(a["ActionID"]))} ${esc(text(a["Title"]))}`;

  const completed = mine.filter(a => text(a["Status"]) === "완료" && inWeek(kstDate(a["CompletedAt"])));
  const created = mine.filter(a => inWeek(kstDate(a["Created"])));
  const open = mine.filter(a => OPEN.indexOf(text(a["Status"])) >= 0);
  const overdue = open.filter(a => text(a["ActionType"]) !== "회신대기" && kstDate(a["DueDate"]) !== "" && kstDate(a["DueDate"]) < today);
  const nextWeek = open.filter(a => { const d = kstDate(a["DueDate"]); return d >= nextMon && d <= nextFri; });
  const replyOver = open.filter(a => text(a["ActionType"]) === "회신대기" && kstDate(a["DueDate"]) !== "" && kstDate(a["DueDate"]) <= today);
  const decided = decisions.filter(d => text(d["Status"]) === "확정" && inWeek(kstDate(d["DecidedAt"])));
  const waiting = decisions.filter(d => text(d["Status"]) === "결정요청");

  const thisWeekInbox = inbox.filter(m => inWeek(kstDate(m["ReceivedAt"])));
  const byPlant: { [p: string]: { mails: number; files: number } } = {};
  thisWeekInbox.forEach(m => {
    const p = text(m["PlantCode"]) || "(미상)";
    if (!byPlant[p]) byPlant[p] = { mails: 0, files: 0 };
    byPlant[p].mails++;
    byPlant[p].files += Number(text(m["FileCount"])) || 0;
  });
  const fourWeeks = inbox.filter(m => { const d = kstDate(m["ReceivedAt"]); return d !== "" && dayDiff(d, today) < 28 && d <= today; });
  const byDay = [0, 0, 0, 0, 0, 0, 0];
  fourWeeks.forEach(m => { byDay[new Date(kstDate(m["ReceivedAt"]) + "T00:00:00Z").getUTCDay()]++; });

  const counts: WeeklyCounts = { completed: completed.length, created: created.length, overdue: overdue.length,
    dueNextWeek: nextWeek.length, decided: decided.length, waitingDecisions: waiting.length, replyOverdue: replyOver.length,
    factoryMails: thisWeekInbox.length, factoryFiles: Object.keys(byPlant).reduce((s, k) => s + byPlant[k].files, 0) };
  const week = isoWeek(today);
  const h: string[] = [`<h3>주간 정리 초안 — ${week} (${start} ~ ${today})</h3>`,
    `<p>완료 ${counts.completed} · 신규 ${counts.created} · 기한초과 ${counts.overdue} · 다음 주 마감 ${counts.dueNextWeek} · ` +
    `확정 결정 ${counts.decided} · 결정 대기 ${counts.waitingDecisions} · 회신 대기 초과 ${counts.replyOverdue}</p>`,
    "<p><small>목록 데이터에서 자동 생성한 초안입니다. 그대로 전달하거나 고쳐서 주간보고로 쓰세요.</small></p>",
    list("이번 주 완료", completed.map(label)),
    list("확정된 결정", decided.map(d => `${esc(text(d["DecisionID"]))} ${esc(text(d["Title"]))}`)),
    list("기한 초과(도움·조정 필요)", overdue.map(a => `${label(a)} — ${dayDiff(kstDate(a["DueDate"]), today)}일 초과`)),
    list("결정 대기", waiting.map(d => { const r = kstDate(d["RequestedAt"]); return `${esc(text(d["DecisionID"]))} ${esc(text(d["Title"]))} — 대기 ${r ? dayDiff(r, today) : "?"}일`; })),
    list("회신 대기 초과", replyOver.map(label)),
    list("다음 주 마감", nextWeek.map(a => `${label(a)} — ${kstDate(a["DueDate"])}`)),
  ];
  const plants = Object.keys(byPlant).sort();
  h.push(`<h4>공장 자료 수신 (이번 주 ${counts.factoryMails}통 · 파일 ${counts.factoryFiles}개)</h4>`);
  if (plants.length) h.push("<ul>" + plants.map(p => `<li>${esc(p)}: 메일 ${byPlant[p].mails} · 파일 ${byPlant[p].files}</li>`).join("") + "</ul>");
  h.push(`<p><small>최근 4주 요일별 수신: ${[1, 2, 3, 4, 5, 6, 0].map(i => `${WD[i]} ${byDay[i]}`).join(" · ")} — 특정 요일에 몰리면 그 자료부터 정기 제출(데이터 계약)로 전환 검토</small></p>`);
  return { week, weekStart: start, counts, htmlSummary: h.join("") };
}
