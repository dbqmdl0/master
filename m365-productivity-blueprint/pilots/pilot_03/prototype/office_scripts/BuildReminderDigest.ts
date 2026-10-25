/**
 * P3 프로토타입 — 액션 리마인더 다이제스트 (Office Scripts)
 *
 * ActionItems 원시 항목을 받아 담당자별 '하루 1장' 카드를 만든다(건별 알림 금지 → 알림 피로 방지).
 *   대상: 미착수/진행중 + 기한이 내일 이전(D-1·당일·초과) + 오늘 아직 알리지 않은 항목
 *   에스컬레이션 후보: 리마인더 3회 이상 + 기한 초과 (프로토타입은 목록으로만 반환, 발송은 하지 않음)
 * 반환값의 itemIds(SharePoint ID)로 흐름이 ReminderCount·LastRemindedAt 을 갱신한다.
 * 통합 문서는 수정하지 않는다.
 */

interface Digest {
  ownerEmail: string;
  itemCount: number;
  itemIds: number[];
  cardJson: string;
}

interface Escalation {
  itemId: number;
  actionId: string;
  ownerEmail: string;
  decisionId: string;
  daysOverdue: number;
  reminderCount: number;
}

interface DigestResult {
  skip: boolean;
  reason: string;
  digestCount: number;
  digests: Digest[];
  escalations: Escalation[];
}

const OPEN: string[] = ["미착수", "진행중"];
const ESCALATE_AFTER_REMINDERS = 3;
const MAX_LINES = 10;
const KST_OFFSET_MS = 9 * 3600 * 1000;

type Raw = { [key: string]: unknown };

function main(workbook: ExcelScript.Workbook, todayKst: string, actionsJson: string, holidaysJson: string,
  viewUrl: string): DigestResult {
  return buildDigests(todayKst, parse(actionsJson, "actionsJson"), parse(holidaysJson, "holidaysJson"), viewUrl);
}

function parse(s: string, name: string): Raw[] {
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
  const t = Date.parse(hasZone ? s.replace(/(\.\d{3})\d+/, "$1") : s.replace(/(\.\d{3})\d+/, "$1") + "Z");
  return isNaN(t) ? "" : new Date(t + KST_OFFSET_MS).toISOString().substring(0, 10);
}

function dayDiff(a: string, b: string): number {
  return Math.round((Date.parse(b + "T00:00:00Z") - Date.parse(a + "T00:00:00Z")) / 86400000);
}

function buildDigests(today: string, actions: Raw[], holidays: Raw[], viewUrl: string): DigestResult {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(today)) throw new Error(`todayKst 형식 오류: ${today}`);
  const res: DigestResult = { skip: false, reason: "", digestCount: 0, digests: [], escalations: [] };
  const wd = new Date(today + "T00:00:00Z").getUTCDay();
  if (wd === 0 || wd === 6) { res.skip = true; res.reason = "주말"; return res; }
  if (holidays.map(h => kstDate(h["HolidayDate"])).indexOf(today) >= 0) { res.skip = true; res.reason = "휴무일"; return res; }

  const byOwner: { [email: string]: { id: number; aid: string; title: string; late: number }[] } = {};
  actions.forEach(a => {
    if (OPEN.indexOf(text(a["Status"])) < 0) return;
    const due = kstDate(a["DueDate"]);
    const owner = text(a["Owner"]).trim().toLowerCase();
    if (due === "" || owner === "") return;
    const late = dayDiff(due, today); // 양수 = 초과일, 0 = 오늘, -1 = 내일
    if (late < -1) return;
    const id = Number(text(a["ID"]));
    const reminders = Number(text(a["ReminderCount"])) || 0;
    if (late > 0 && reminders >= ESCALATE_AFTER_REMINDERS) {
      res.escalations.push({ itemId: id, actionId: text(a["ActionID"]), ownerEmail: owner,
        decisionId: text(a["DecisionID"]), daysOverdue: late, reminderCount: reminders });
    }
    if (kstDate(a["LastRemindedAt"]) === today) return; // 같은 날 중복 알림 금지
    if (!byOwner[owner]) byOwner[owner] = [];
    byOwner[owner].push({ id, aid: text(a["ActionID"]) || `ID-${id}`, title: text(a["Title"]), late });
  });

  Object.keys(byOwner).sort().forEach(owner => {
    const list = byOwner[owner].sort((x, y) => (y.late - x.late) || (x.id - y.id));
    const label = (l: number) => (l > 0 ? `${l}일 초과` : l === 0 ? "오늘 마감" : "내일 마감");
    const body: Raw[] = [
      { type: "TextBlock", text: `액션 리마인더 · ${today}`, weight: "Bolder", size: "Medium" },
      { type: "TextBlock", wrap: true, spacing: "Small",
        text: `초과 ${list.filter(x => x.late > 0).length} · 오늘 ${list.filter(x => x.late === 0).length} · 내일 ${list.filter(x => x.late < 0).length}` },
      { type: "FactSet", facts: list.slice(0, MAX_LINES).map(x => ({ title: label(x.late), value: `${x.aid} ${x.title}` })) },
    ];
    if (list.length > MAX_LINES) body.push({ type: "TextBlock", text: `외 ${list.length - MAX_LINES}건`, isSubtle: true });
    body.push({ type: "TextBlock", text: "완료했으면 상태를 '완료'로, 어려우면 기한을 조정하고 사유를 남겨 주세요.", wrap: true, isSubtle: true, size: "Small" });
    const card: Raw = { $schema: "http://adaptivecards.io/schemas/adaptive-card.json", type: "AdaptiveCard", version: "1.4", body };
    if (viewUrl) card["actions"] = [{ type: "Action.OpenUrl", title: "내 액션 열기", url: viewUrl }];
    res.digests.push({ ownerEmail: owner, itemCount: list.length, itemIds: list.map(x => x.id), cardJson: JSON.stringify(card) });
  });
  res.digestCount = res.digests.length;
  res.escalations.sort((x, y) => x.itemId - y.itemId);
  return res;
}
