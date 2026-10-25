/**
 * P3 프로토타입 — 아침 브리핑 계산 엔진 (Office Scripts)
 *
 * Power Automate가 모은 원시 데이터(SharePoint Get items의 value 배열, Outlook 일정 V3의 value 배열)를
 * 그대로 받아 우선순위 점수 → Top 5 → Adaptive Card JSON 을 돌려준다.
 * 흐름에서는 정렬·그룹화 같은 복잡한 식을 쓰지 않고 이 스크립트 1회 호출로 끝낸다.
 * 실행 대상 통합 문서(P3_AutomationHost.xlsx)는 '계산 호스트'일 뿐이며 이 스크립트는 통합 문서를 수정하지 않는다.
 *
 * 규칙은 automation_assets/python/daily_brief.py 와 같다(로컬 교차 검증 테스트로 확인).
 *
 * TOP5 규칙(P0-3, 문서: START_HERE_V2.md '아침 브리핑 읽는 법')
 *  - 후보: 내 미결 할 일(기한 있음·없음 모두) + 내가 결정할 결정요청 + SLA 요청
 *  - 점수: 기한초과 100+5/일, SLA초과 90, 오늘마감 80, 결정대기 70+3/일, SLA임박 60, 회신대기 40+2/일,
 *          기한미정 30+2/등록 후 경과일(최대 +40)
 *  - 사용자 우선순위: '높음' +15, '낮음' −10 (모든 할 일에 적용)
 *  - 기한이 미래인(내일 이후) 할 일은 TOP5 후보가 아니다(오늘 할 일이 아님)
 *  - 기한 없는 할 일은 기한을 만들어 넣지 않는다. TOP5에 들지 못해도 '기한 없는 할 일' 칸에 따로 3건까지 보여 준다
 *  - 방치 경고: 기한 없이 14일 이상, 또는 우선순위 '높음'인데 기한 없이 7일 이상
 *  - 동점이면 번호 오름차순
 */

interface BriefItem {
  score: number;
  kind: string;
  id: string;
  text: string;
  url: string;
}

/** Power Automate 반환 스키마 호환을 위해 인덱스 시그니처 대신 고정 필드 사용 */
interface BriefCounts {
  overdue: number;
  dueToday: number;
  decisionWaiting: number;
  slaOverdue: number;
  slaDueSoon: number;
  replyWaiting: number;
  undated: number;
  neglectedUndated: number;
  proposalsToConfirm: number;
}

interface BriefResult {
  skip: boolean;
  reason: string;
  today: string;
  top: BriefItem[];
  counts: BriefCounts;
  undatedOpenActions: number;
  undatedTop: BriefItem[];
  neglected: BriefItem[];
  meetingCount: number;
  meetingHours: number;
  focusBlocks: string[];
  organizerWithoutAgenda: string[];
  cardJson: string;
  htmlSummary: string; // Teams 실패 시 대체 메일 본문
}

const SCORE_ACTION_OVERDUE = 100;
const SCORE_ACTION_OVERDUE_PER_DAY = 5;
const SCORE_REQUEST_OVERDUE = 90;
const SCORE_ACTION_DUE_TODAY = 80;
const SCORE_DECISION_WAITING = 70;
const SCORE_DECISION_WAITING_PER_DAY = 3;
const SCORE_REQUEST_DUE_SOON = 60;
const SCORE_REPLY_WAITING = 40;
const SCORE_REPLY_WAITING_PER_DAY = 2;
const SCORE_UNDATED = 30;
const SCORE_UNDATED_PER_DAY = 2;
const SCORE_UNDATED_AGE_CAP = 40;
const PRIORITY_BONUS_HIGH = 15;
const PRIORITY_BONUS_LOW = -10;
const NEGLECT_DAYS = 14;
const NEGLECT_DAYS_HIGH = 7;
const UNDATED_SHOW = 3;
const OPEN_ACTION: string[] = ["미착수", "진행중"];
const TOP_N = 5;
const SECTION_MAX = 8;
const WORK_START_MIN = 9 * 60;
const WORK_END_MIN = 18 * 60;
const FOCUS_MIN_MINUTES = 60;
const CARD_LIMIT_BYTES = 28 * 1024;
const KST_OFFSET_MS = 9 * 3600 * 1000;
const KINDS: string[] = ["기한초과", "오늘마감", "결정대기", "SLA초과", "SLA임박", "회신대기", "기한미정"];

function main(workbook: ExcelScript.Workbook, meEmail: string, todayKst: string, eventsJson: string,
  actionsJson: string, decisionsJson: string, requestsJson: string, holidaysJson: string,
  linksJson: string): BriefResult {
  return buildBrief(meEmail, todayKst, parseArray(eventsJson, "eventsJson"), parseArray(actionsJson, "actionsJson"),
    parseArray(decisionsJson, "decisionsJson"), parseArray(requestsJson, "requestsJson"),
    parseArray(holidaysJson, "holidaysJson"), parseLinks(linksJson));
}

type Raw = { [key: string]: unknown };

function parseArray(s: string, name: string): Raw[] {
  let v: unknown;
  try {
    v = JSON.parse(s && s.trim() !== "" ? s : "[]");
  } catch (e) {
    throw new Error(`${name}: JSON 형식 오류`);
  }
  if (!Array.isArray(v)) throw new Error(`${name}: 배열이 아닙니다`);
  return v as Raw[];
}

function parseLinks(s: string): { [k: string]: string } {
  try {
    const v = JSON.parse(s && s.trim() !== "" ? s : "{}") as { [k: string]: string };
    return v && typeof v === "object" ? v : {};
  } catch (e) {
    return {};
  }
}

/** SharePoint 선택 열({Value}), 사람 열({Email}) 또는 일반 값을 문자열로 */
function text(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "object") {
    const o = v as Raw;
    if (o["Value"] !== undefined) return String(o["Value"]);
    if (o["Email"] !== undefined) return String(o["Email"]);
    if (o["EMail"] !== undefined) return String(o["EMail"]);
    const ea = o["emailAddress"] as Raw | undefined;
    if (ea && ea["address"] !== undefined) return String(ea["address"]);
    return "";
  }
  return String(v);
}

function lower(v: unknown): string {
  return text(v).trim().toLowerCase();
}

/** 날짜 문자열 → KST 기준 'YYYY-MM-DD'. 'YYYY-MM-DD'는 그대로, 시간대 없는 일시는 UTC로 간주 */
function kstDate(v: unknown): string {
  const s = text(v).trim();
  if (s === "") return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  const t = toUtcMs(s);
  if (isNaN(t)) return "";
  return new Date(t + KST_OFFSET_MS).toISOString().substring(0, 10);
}

function toUtcMs(s: string): number {
  const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(s);
  const trimmed = s.replace(/(\.\d{3})\d+/, "$1");
  return Date.parse(hasZone ? trimmed : trimmed + "Z");
}

/** KST 기준 하루 중 분(0~1440) */
function kstMinutes(s: string): number {
  const d = new Date(toUtcMs(s) + KST_OFFSET_MS);
  return d.getUTCHours() * 60 + d.getUTCMinutes();
}

function daysBetween(a: string, b: string): number {
  return Math.round((Date.parse(b + "T00:00:00Z") - Date.parse(a + "T00:00:00Z")) / 86400000);
}

function hhmm(min: number): string {
  const h = Math.floor(min / 60);
  const m = min % 60;
  return `${h < 10 ? "0" + h : h}:${m < 10 ? "0" + m : m}`;
}

function isWeekend(day: string): boolean {
  const wd = new Date(day + "T00:00:00Z").getUTCDay();
  return wd === 0 || wd === 6;
}

function buildBrief(meEmail: string, today: string, events: Raw[], actions: Raw[], decisions: Raw[],
  requests: Raw[], holidays: Raw[], links: { [k: string]: string }): BriefResult {
  const me = meEmail.trim().toLowerCase();
  const tally: { [k: string]: number } = {};
  KINDS.forEach(k => { tally[k] = 0; });
  const empty: BriefResult = { skip: true, reason: "", today, top: [], counts: toCounts(tally, 0, 0), undatedOpenActions: 0,
    undatedTop: [], neglected: [], meetingCount: 0, meetingHours: 0, focusBlocks: [], organizerWithoutAgenda: [], cardJson: "", htmlSummary: "" };
  if (!/^\d{4}-\d{2}-\d{2}$/.test(today)) throw new Error(`todayKst 형식 오류: ${today}`);
  const holidaySet = holidays.map(h => kstDate(h["HolidayDate"] !== undefined ? h["HolidayDate"] : h["date"]));
  if (isWeekend(today)) { empty.reason = "주말"; return empty; }
  if (holidaySet.indexOf(today) >= 0) { empty.reason = "휴무일"; return empty; }

  const items: BriefItem[] = [];
  const undatedItems: BriefItem[] = [];
  const neglected: BriefItem[] = [];
  let proposals = 0;
  actions.forEach(a => {
    const owner = lower(a["Owner"]);
    if (owner !== "" && owner !== me) return;
    const status = text(a["Status"]);
    if (OPEN_ACTION.indexOf(status) < 0) return;
    const due = kstDate(a["DueDate"]);
    const id = text(a["ActionID"]) || `ID-${text(a["ID"])}`;
    const title = text(a["Title"]);
    const url = text(a["SourceLink"]);
    const prio = text(a["Priority"]);
    const bonus = prio === "높음" ? PRIORITY_BONUS_HIGH : prio === "낮음" ? PRIORITY_BONUS_LOW : 0;
    const mark = prio === "높음" ? " [높음]" : "";
    if (due === "") {
      const created = kstDate(a["Created"]);
      const age = created === "" ? 0 : Math.max(0, daysBetween(created, today));
      const it: BriefItem = { score: SCORE_UNDATED + Math.min(SCORE_UNDATED_AGE_CAP, SCORE_UNDATED_PER_DAY * age) + bonus,
        kind: "기한미정", id, text: `${title} (기한 없음 · 등록 ${age}일째)${mark}`, url };
      undatedItems.push(it);
      items.push(it);
      if (age >= NEGLECT_DAYS || (prio === "높음" && age >= NEGLECT_DAYS_HIGH)) neglected.push(it);
      return;
    }
    const late = daysBetween(due, today);
    if (text(a["ActionType"]) === "회신대기") {
      if (late >= 0) items.push({ score: SCORE_REPLY_WAITING + SCORE_REPLY_WAITING_PER_DAY * late + bonus, kind: "회신대기",
        id, text: `${title} (회신 대기 ${late}일)${mark}`, url });
    } else if (late > 0) {
      items.push({ score: SCORE_ACTION_OVERDUE + SCORE_ACTION_OVERDUE_PER_DAY * late + bonus, kind: "기한초과", id,
        text: `${title} (${late}일 초과)${mark}`, url });
    } else if (late === 0) {
      items.push({ score: SCORE_ACTION_DUE_TODAY + bonus, kind: "오늘마감", id, text: `${title}${mark}`, url });
    }
  });
  decisions.forEach(d => {
    if (text(d["Status"]) === "제안") { proposals++; return; }
    if (text(d["Status"]) !== "결정요청") return;
    const decider = lower(d["Decider"]);
    if (decider !== "" && decider !== me) return;
    const asked = kstDate(d["RequestedAt"]) || kstDate(d["Created"]);
    const age = asked === "" ? 0 : Math.max(0, daysBetween(asked, today));
    items.push({ score: SCORE_DECISION_WAITING + SCORE_DECISION_WAITING_PER_DAY * age, kind: "결정대기",
      id: text(d["DecisionID"]) || `ID-${text(d["ID"])}`, text: `${text(d["Title"])} (대기 ${age}일)`,
      url: text(d["SourceLink"]) });
  });
  requests.forEach(r => {
    const state = text(r["slaState"]);
    const id = text(r["RequestID"]) || text(r["id"]);
    const title = text(r["Title"]) || text(r["title"]);
    if (state === "overdue") items.push({ score: SCORE_REQUEST_OVERDUE, kind: "SLA초과", id, text: title, url: "" });
    else if (state === "due_soon") items.push({ score: SCORE_REQUEST_DUE_SOON, kind: "SLA임박", id, text: title, url: "" });
  });
  const byScore = (x: BriefItem, y: BriefItem) => (y.score - x.score) || (x.id < y.id ? -1 : x.id > y.id ? 1 : 0);
  items.sort(byScore);
  undatedItems.sort(byScore);
  neglected.sort(byScore);
  items.forEach(i => { tally[i.kind] = (tally[i.kind] || 0) + 1; });
  const counts = toCounts(tally, neglected.length, proposals);

  // 일정: KST 오늘 시작하는 종일이 아닌 일정만
  const todays = events.filter(e => e["isAllDay"] !== true && kstDate(e["start"]) === today)
    .map(e => ({
      subject: text(e["subject"]),
      startMin: kstMinutes(text(e["start"])),
      endMin: kstDate(e["end"]) === today ? kstMinutes(text(e["end"])) : 24 * 60,
      organizer: lower(e["organizer"]),
      hasAgenda: e["hasAttachments"] === true || /https?:\/\//.test(text(e["body"])) || e["hasAgendaLink"] === true,
    }))
    .sort((a, b) => a.startMin - b.startMin);
  const meetingHours = Math.round(todays.reduce((s, e) => s + (e.endMin - e.startMin), 0) / 6) / 10;
  const free: string[] = [];
  let cur = WORK_START_MIN;
  todays.forEach(e => {
    const s = Math.max(e.startMin, WORK_START_MIN);
    const en = Math.min(e.endMin, WORK_END_MIN);
    if (en <= WORK_START_MIN || s >= WORK_END_MIN) return;
    if (s - cur >= FOCUS_MIN_MINUTES) free.push(`${hhmm(cur)}~${hhmm(s)}`);
    cur = Math.max(cur, en);
  });
  if (WORK_END_MIN - cur >= FOCUS_MIN_MINUTES) free.push(`${hhmm(cur)}~${hhmm(WORK_END_MIN)}`);
  const noAgenda = todays.filter(e => e.organizer === me && !e.hasAgenda).map(e => e.subject).slice(0, SECTION_MAX);

  const result: BriefResult = {
    skip: false, reason: "", today, top: items.slice(0, TOP_N), counts, undatedOpenActions: undatedItems.length,
    undatedTop: undatedItems.slice(0, UNDATED_SHOW), neglected: neglected.slice(0, SECTION_MAX),
    meetingCount: todays.length, meetingHours, focusBlocks: free, organizerWithoutAgenda: noAgenda, cardJson: "",
    htmlSummary: "",
  };
  result.cardJson = toCard(result, todays.slice(0, SECTION_MAX).map(e => ({ time: hhmm(e.startMin), subject: e.subject })), links);
  result.htmlSummary = toHtml(result);
  return result;
}

function toCard(b: BriefResult, events: { time: string; subject: string }[], links: { [k: string]: string }): string {
  const body: Raw[] = [
    { type: "TextBlock", text: `아침 브리핑 · ${b.today}`, weight: "Bolder", size: "Medium" },
    { type: "TextBlock", wrap: true, spacing: "Small",
      text: `회의 ${b.meetingCount}건(${b.meetingHours}h) · 기한초과 ${b.counts.overdue} · 결정대기 ${b.counts.decisionWaiting} · SLA위험 ${b.counts.slaOverdue + b.counts.slaDueSoon}` },
    { type: "TextBlock", text: "오늘 먼저 처리할 5가지", weight: "Bolder", spacing: "Medium" },
  ];
  if (b.top.length > 0) body.push({ type: "FactSet", facts: b.top.map(i => ({ title: i.kind, value: cut(i.text, 120) })) });
  else body.push({ type: "TextBlock", text: "급한 미결 항목이 없습니다. 전략 과제에 시간을 쓰세요.", wrap: true });
  if (b.undatedOpenActions > 0) {
    body.push({ type: "TextBlock", text: `기한 없는 할 일 ${b.undatedOpenActions}건 (기한은 직접 정하세요)`, weight: "Bolder", spacing: "Medium" });
    body.push({ type: "FactSet", facts: b.undatedTop.map(i => ({ title: "기한미정", value: cut(i.text, 120) })) });
  }
  if (b.neglected.length > 0) {
    body.push({ type: "TextBlock", color: "Warning", wrap: true,
      text: `방치 경고 ${b.neglected.length}건: ` + b.neglected.slice(0, 3).map(i => cut(i.text, 60)).join(", ") + " — 기한을 정하거나 취소하세요." });
  }
  if (b.counts.proposalsToConfirm > 0) {
    body.push({ type: "TextBlock", wrap: true, isSubtle: true, size: "Small",
      text: `확정 대기 제안 ${b.counts.proposalsToConfirm}건 — 결정 레지스터에서 확정·보류를 정하세요.` });
  }
  body.push({ type: "TextBlock", text: `집중 가능 시간: ${b.focusBlocks.join(", ") || "없음(일정 재조정 검토)"}`, wrap: true, spacing: "Medium" });
  if (events.length > 0) body.push({ type: "FactSet", facts: events.map(e => ({ title: e.time, value: cut(e.subject, 80) })) });
  if (b.organizerWithoutAgenda.length > 0) {
    body.push({ type: "TextBlock", color: "Warning", wrap: true,
      text: "안건·사전자료가 없는 내 주관 회의: " + b.organizerWithoutAgenda.join(", ") });
  }
  const actions: Raw[] = [];
  if (links["myActions"]) actions.push({ type: "Action.OpenUrl", title: "내 액션 열기", url: links["myActions"] });
  if (links["decisionQueue"]) actions.push({ type: "Action.OpenUrl", title: "결정 대기열", url: links["decisionQueue"] });
  const card: Raw = { $schema: "http://adaptivecards.io/schemas/adaptive-card.json", type: "AdaptiveCard", version: "1.4", body };
  if (actions.length > 0) card["actions"] = actions;
  const json = JSON.stringify(card);
  if (utf8Bytes(json) > CARD_LIMIT_BYTES) throw new Error(`카드 크기 초과: ${utf8Bytes(json)}B`);
  return json;
}

function toCounts(t: { [k: string]: number }, neglected: number, proposals: number): BriefCounts {
  return { overdue: t["기한초과"], dueToday: t["오늘마감"], decisionWaiting: t["결정대기"],
    slaOverdue: t["SLA초과"], slaDueSoon: t["SLA임박"], replyWaiting: t["회신대기"], undated: t["기한미정"],
    neglectedUndated: neglected, proposalsToConfirm: proposals };
}

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function toHtml(b: BriefResult): string {
  const li = b.top.map(i => `<li><b>${esc(i.kind)}</b> ${esc(i.text)}</li>`).join("");
  return `<h3>아침 브리핑 ${esc(b.today)}</h3><p>회의 ${b.meetingCount}건(${b.meetingHours}h)</p>` +
    (li ? `<ol>${li}</ol>` : "<p>급한 미결 항목이 없습니다.</p>") +
    (b.undatedOpenActions > 0 ? `<p><b>기한 없는 할 일 ${b.undatedOpenActions}건</b></p><ul>` +
      b.undatedTop.map(i => `<li>${esc(i.text)}</li>`).join("") + "</ul>" : "") +
    (b.neglected.length > 0 ? `<p><b>방치 경고 ${b.neglected.length}건</b> — 기한을 정하거나 취소하세요.</p>` : "") +
    (b.counts.proposalsToConfirm > 0 ? `<p>확정 대기 제안 ${b.counts.proposalsToConfirm}건</p>` : "") +
    `<p>집중 가능 시간: ${esc(b.focusBlocks.join(", ") || "없음")}</p>`;
}

function cut(s: string, n: number): string {
  return s.length > n ? s.substring(0, n - 1) + "…" : s;
}

function utf8Bytes(s: string): number {
  let n = 0;
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    if (c < 0x80) n += 1;
    else if (c < 0x800) n += 2;
    else if (c >= 0xd800 && c <= 0xdbff) { n += 4; i++; }
    else n += 3;
  }
  return n;
}
