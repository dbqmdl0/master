/**
 * 추가 기능 B — 다음 영업일 회의 준비 자료 (Office Scripts)
 *
 * 내일(다음 영업일) 회의마다 참석자 기준으로
 *   ① 참석자가 담당인 미결 할 일(기한초과 우선)  ② 참석자가 결정권자·요청자인 '결정요청'
 *   ③ 최근 14일 참석자가 내린 결정  ④ 안건 제안 한 줄 · 안건 없는 내 주관 회의 경고
 * 를 모아 메일 1통(HTML)으로 만든다. 회의 중 "그거 어떻게 됐지?"를 미리 없애 회의를 '결정'에 쓰게 한다.
 * 통합 문서는 수정하지 않는다.
 */

interface MeetingPrepItem {
  subject: string;
  time: string;
  attendeeCount: number;
  overdueActions: number;
  openActions: number;
  pendingDecisions: number;
}

interface MeetingPrepResult {
  skip: boolean;
  reason: string;
  targetDate: string;
  meetingCount: number;
  meetings: MeetingPrepItem[];
  htmlSummary: string;
}

const KST_OFFSET_MS = 9 * 3600 * 1000;
const OPEN: string[] = ["미착수", "진행중"];
const MAX_ACTIONS = 6;
const MAX_DECISIONS = 3;
const RECENT_DAYS = 14;

type Raw = { [key: string]: unknown };

function main(workbook: ExcelScript.Workbook, meEmail: string, todayKst: string, eventsJson: string,
  actionsJson: string, decisionsJson: string, holidaysJson: string): MeetingPrepResult {
  return build(meEmail, todayKst, arr(eventsJson, "eventsJson"), arr(actionsJson, "actionsJson"),
    arr(decisionsJson, "decisionsJson"), arr(holidaysJson, "holidaysJson"));
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
    const ea = o["emailAddress"] as Raw | undefined;
    if (ea && ea["address"] !== undefined) return String(ea["address"]);
    return "";
  }
  return String(v);
}

function toUtcMs(s: string): number {
  const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(s);
  const t = s.replace(/(\.\d{3})\d+/, "$1");
  return Date.parse(hasZone ? t : t + "Z");
}

function kstDate(v: unknown): string {
  const s = text(v).trim();
  if (s === "") return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  const ms = toUtcMs(s);
  return isNaN(ms) ? "" : new Date(ms + KST_OFFSET_MS).toISOString().substring(0, 10);
}

function kstTime(s: string): string {
  return new Date(toUtcMs(s) + KST_OFFSET_MS).toISOString().substring(11, 16);
}

function addDays(d: string, n: number): string {
  return new Date(Date.parse(d + "T00:00:00Z") + n * 86400000).toISOString().substring(0, 10);
}

function dayDiff(a: string, b: string): number {
  return Math.round((Date.parse(b + "T00:00:00Z") - Date.parse(a + "T00:00:00Z")) / 86400000);
}

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function emails(v: unknown): string[] {
  if (Array.isArray(v)) return (v as unknown[]).map(x => text(x).trim().toLowerCase()).filter(x => x.indexOf("@") > 0);
  return text(v).split(/[;,]/).map(x => x.trim().toLowerCase()).filter(x => x.indexOf("@") > 0);
}

function build(meEmail: string, today: string, events: Raw[], actions: Raw[], decisions: Raw[],
  holidays: Raw[]): MeetingPrepResult {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(today)) throw new Error(`todayKst 형식 오류: ${today}`);
  const me = meEmail.trim().toLowerCase();
  const hol = holidays.map(h => kstDate(h["HolidayDate"]));
  let target = addDays(today, 1);
  while ([0, 6].indexOf(new Date(target + "T00:00:00Z").getUTCDay()) >= 0 || hol.indexOf(target) >= 0) target = addDays(target, 1);
  const res: MeetingPrepResult = { skip: true, reason: "", targetDate: target, meetingCount: 0, meetings: [], htmlSummary: "" };
  const todayIsWork = [0, 6].indexOf(new Date(today + "T00:00:00Z").getUTCDay()) < 0 && hol.indexOf(today) < 0;
  if (!todayIsWork) { res.reason = "오늘은 휴무일"; return res; }

  const meetings = events
    .filter(e => e["isAllDay"] !== true && e["isCancelled"] !== true && kstDate(e["start"]) === target)
    .sort((a, b) => toUtcMs(text(a["start"])) - toUtcMs(text(b["start"])));
  if (meetings.length === 0) { res.reason = "회의 없음"; return res; }

  const openActs = actions.filter(a => OPEN.indexOf(text(a["Status"])) >= 0);
  const parts: string[] = [`<h3>회의 준비 — ${esc(target)} (회의 ${meetings.length}건)</h3>`,
    "<p>참석자 기준으로 미결 할 일·결정 대기를 모았습니다. 회의 시간은 '현황 확인'이 아니라 '결정'에 쓰세요.</p>"];
  meetings.forEach(e => {
    const organizer = text(e["organizer"]).trim().toLowerCase();
    const people = emails(e["requiredAttendees"]).concat(emails(e["optionalAttendees"]), organizer ? [organizer] : [], [me]);
    const uniq = people.filter((p, i) => people.indexOf(p) === i);
    const acts = openActs.filter(a => uniq.indexOf(text(a["Owner"]).trim().toLowerCase()) >= 0)
      .map(a => ({ a, due: kstDate(a["DueDate"]) }))
      .sort((x, y) => (x.due === "" ? 1 : 0) - (y.due === "" ? 1 : 0) || (x.due < y.due ? -1 : x.due > y.due ? 1 : 0));
    const overdue = acts.filter(x => x.due !== "" && x.due < target);
    const pend = decisions.filter(d => text(d["Status"]) === "결정요청" &&
      (uniq.indexOf(text(d["Decider"]).trim().toLowerCase()) >= 0 || uniq.indexOf(text(d["RequestedBy"]).trim().toLowerCase()) >= 0));
    const recent = decisions.filter(d => text(d["Status"]) === "확정" && uniq.indexOf(text(d["Decider"]).trim().toLowerCase()) >= 0 &&
      kstDate(d["DecidedAt"]) !== "" && dayDiff(kstDate(d["DecidedAt"]), today) <= RECENT_DAYS);
    const noAgenda = organizer === me && e["hasAttachments"] !== true && !/https?:\/\//.test(text(e["body"]));
    res.meetings.push({ subject: text(e["subject"]), time: kstTime(text(e["start"])), attendeeCount: uniq.length,
      overdueActions: overdue.length, openActions: acts.length, pendingDecisions: pend.length });

    parts.push(`<h4>${esc(kstTime(text(e["start"])))} ${esc(text(e["subject"]))} · 참석 ${uniq.length}명</h4>`);
    const hints: string[] = [];
    if (overdue.length) hints.push(`기한 초과 ${overdue.length}건 원인·새 기한 확정`);
    if (pend.length) hints.push(`결정요청 ${pend.length}건 결정`);
    parts.push(`<p><b>안건 제안:</b> ${esc(hints.join(" · ") || "미결 사항 없음 — 회의를 짧게 하거나 생략 검토")}</p>`);
    if (noAgenda) parts.push(`<p style="color:#b45309">⚠ 내 주관 회의인데 안건·자료 링크가 없습니다. 오늘 안에 초대에 안건을 붙이세요.</p>`);
    if (acts.length) {
      parts.push("<ul>" + acts.slice(0, MAX_ACTIONS).map(x => {
        const late = x.due !== "" && x.due < target ? ` <b style="color:#b91c1c">(${dayDiff(x.due, target)}일 초과)</b>` : "";
        return `<li>[할 일] ${esc(text(x.a["ActionID"]) || "")} ${esc(text(x.a["Title"]))} — ${esc(text(x.a["Owner"]))}, 기한 ${esc(x.due || "미정")}${late}</li>`;
      }).join("") + (acts.length > MAX_ACTIONS ? `<li>외 ${acts.length - MAX_ACTIONS}건</li>` : "") + "</ul>");
    }
    if (pend.length) {
      parts.push("<ul>" + pend.slice(0, MAX_DECISIONS).map(d => {
        const asked = kstDate(d["RequestedAt"]);
        return `<li>[결정요청] ${esc(text(d["DecisionID"]))} ${esc(text(d["Title"]))} — 대기 ${asked ? dayDiff(asked, today) : "?"}일</li>`;
      }).join("") + "</ul>");
    }
    if (recent.length) {
      parts.push("<p><small>최근 결정: " + recent.slice(0, MAX_DECISIONS).map(d => esc(`${text(d["DecisionID"])} ${text(d["Title"])}`)).join(" / ") + "</small></p>");
    }
  });
  res.skip = false;
  res.meetingCount = meetings.length;
  res.htmlSummary = parts.join("");
  return res;
}
