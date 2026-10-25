/**
 * P3 프로토타입 — AI(Copilot) 회의 추출 결과 검증 가드 (Office Scripts)
 *
 * Copilot이 만든 결정·액션 JSON을 회의록 원문·팀 명부와 기계적으로 대조한다(환각 방지).
 *   G1 스키마  G2 근거 문장이 원문에 실제로 존재  G3 담당자는 명부에서만 매핑(이메일 생성 금지)
 *   G4 기한 근거 표현·범위  G5 중복 제거  G6 결정 참조 유효성
 * 결과는 '후보' 목록일 뿐이다. 등록은 사람이 ActionCandidates 목록에서 '승인'으로 바꾼 항목만 된다.
 * 규칙은 automation_assets/python/extraction_guard.py 와 같다(로컬 교차 검증 테스트로 확인).
 * 통합 문서는 수정하지 않는다.
 */

interface Candidate {
  kind: string;        // 결정 | 액션
  ref: number;         // 추출 JSON 안의 순번(1부터)
  title: string;
  ownerName: string;
  ownerEmail: string;  // 명부에서 찾은 경우만, 아니면 ""
  dueDate: string;     // YYYY-MM-DD 또는 ""
  dueMissing: boolean;
  decisionRef: number; // 0 = 없음
  evidence: string;
  verdict: string;     // 추천 | 검토필요
  reasons: string;     // '; ' 구분
}

interface GuardResult {
  ok: boolean;
  parseError: string;
  schemaErrors: string[];
  recommendedCount: number;
  reviewCount: number;
  candidates: Candidate[];
}

const MIN_EVIDENCE_CHARS = 8;
const MAX_DUE_DAYS = 180;

type Raw = { [key: string]: unknown };

interface Person { name: string; email: string; aliases: string[] }

function main(workbook: ExcelScript.Workbook, transcript: string, rosterJson: string, extractionJson: string,
  meetingDate: string): GuardResult {
  return guard(transcript, rosterJson, extractionJson, meetingDate);
}

function norm(s: string): string {
  return (s || "").replace(/\s+/g, " ").trim();
}

/** 공백·문장부호를 제거하고 소문자화(한글·영문·숫자만 남김). Python 판의 [\s\W_]+ 제거와 동등 */
function key(s: string): string {
  return (s || "").toLowerCase().replace(/[\s!-\/:-@\[-`{-~·•…“”‘’「」『』（），。、]+/g, "");
}

/** Copilot 응답에 붙는 ```json 코드 블록 표시·앞뒤 설명을 제거하고 첫 JSON 객체만 추출 */
function stripFences(s: string): string {
  const t = (s || "").trim();
  const fence = t.match(/```(?:json)?\s*([\s\S]*?)```/);
  const body = fence ? fence[1] : t;
  const a = body.indexOf("{");
  const b = body.lastIndexOf("}");
  return a >= 0 && b > a ? body.substring(a, b + 1) : body;
}

function parseRoster(s: string): Person[] {
  let v: unknown;
  try { v = JSON.parse(s || "[]"); } catch (e) { throw new Error("rosterJson: JSON 형식 오류"); }
  if (!Array.isArray(v)) throw new Error("rosterJson: 배열이 아닙니다");
  return (v as Raw[]).map(p => {
    // SharePoint TeamRoster 항목(Title/Email/Aliases) 또는 {name,email,aliases} 모두 허용
    const name = String(p["name"] !== undefined ? p["name"] : (p["Title"] !== undefined ? p["Title"] : ""));
    const email = String(p["email"] !== undefined ? p["email"] : (p["Email"] !== undefined ? p["Email"] : ""));
    const al = p["aliases"] !== undefined ? p["aliases"] : p["Aliases"];
    const aliases = Array.isArray(al) ? (al as unknown[]).map(x => String(x))
      : String(al || "").split(/[;,]/).map(x => x.trim()).filter(x => x.length > 0);
    return { name, email, aliases };
  });
}

function resolveOwner(name: string, roster: Person[]): Person | null {
  if (!name) return null;
  const n = key(name);
  const hits = roster.filter(p => key(p.name) === n || p.aliases.some(a => key(a) === n));
  return hits.length === 1 ? hits[0] : null;
}

function validIsoDate(s: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const d = new Date(s + "T00:00:00Z");
  return !isNaN(d.getTime()) && d.toISOString().substring(0, 10) === s;
}

function dayDiff(a: string, b: string): number {
  return Math.round((Date.parse(b + "T00:00:00Z") - Date.parse(a + "T00:00:00Z")) / 86400000);
}

function str(v: unknown): string {
  return v === null || v === undefined ? "" : String(v);
}

function guard(transcript: string, rosterJson: string, extractionJson: string, meetingDate: string): GuardResult {
  const out: GuardResult = { ok: false, parseError: "", schemaErrors: [], recommendedCount: 0, reviewCount: 0, candidates: [] };
  if (!validIsoDate(meetingDate)) { out.parseError = `meetingDate 형식 오류: ${meetingDate}`; return out; }
  if (norm(transcript).length === 0) { out.parseError = "회의록(transcript)이 비어 있습니다"; return out; }
  const roster = parseRoster(rosterJson);
  let ex: Raw;
  try {
    ex = JSON.parse(stripFences(extractionJson)) as Raw;
  } catch (e) {
    out.parseError = "추출 결과가 JSON이 아닙니다(Copilot 응답 전체를 다시 붙여넣으세요)";
    return out;
  }
  const decisions = ex ? ex["decisions"] : undefined;
  const actions = ex ? ex["actions"] : undefined;
  if (!Array.isArray(decisions) || !Array.isArray(actions)) {
    out.schemaErrors.push("decisions/actions 배열이 필요합니다");
    return out;
  }
  const text = norm(transcript);
  const evidenceOk = (ev: string) => { const e = norm(ev); return e.length >= MIN_EVIDENCE_CHARS && text.indexOf(e) >= 0; };
  const validRefs: number[] = [];

  (decisions as unknown[]).forEach((dv, i0) => {
    const i = i0 + 1;
    const d = (dv && typeof dv === "object" ? dv : {}) as Raw;
    if (!dv || typeof dv !== "object" || !d["text"]) { out.schemaErrors.push(`decision[${i}] text 누락`); return; }
    const reasons: string[] = [];
    if (!evidenceOk(str(d["evidence"]))) reasons.push("G2 근거 문장이 회의록에 없음");
    const decider = str(d["decided_by"]);
    const p = decider ? resolveOwner(decider, roster) : null;
    if (decider && !p) reasons.push("G3 결정자 명부 불일치");
    out.candidates.push({ kind: "결정", ref: i, title: str(d["text"]), ownerName: decider, ownerEmail: p ? p.email : "",
      dueDate: "", dueMissing: false, decisionRef: 0, evidence: str(d["evidence"]),
      verdict: reasons.length ? "검토필요" : "추천", reasons: reasons.join("; ") });
    validRefs.push(i);
  });

  const seen: string[] = [];
  (actions as unknown[]).forEach((av, i0) => {
    const i = i0 + 1;
    const a = (av && typeof av === "object" ? av : {}) as Raw;
    if (!av || typeof av !== "object" || !a["title"]) { out.schemaErrors.push(`action[${i}] title 누락`); return; }
    const k = key(str(a["title"]));
    if (seen.indexOf(k) >= 0) return; // G5
    seen.push(k);
    const reasons: string[] = [];
    if (!evidenceOk(str(a["evidence"]))) reasons.push("G2 근거 문장이 회의록에 없음");
    const owner = resolveOwner(str(a["owner_name"]), roster);
    if (!owner) reasons.push("G3 담당자 미확정(명부에 없거나 모호)");
    const due = str(a["due_date"]);
    const dueText = norm(str(a["due_text"]));
    if (due) {
      if (!validIsoDate(due)) {
        reasons.push("G4 기한 형식 오류(YYYY-MM-DD)");
      } else {
        const diff = dayDiff(meetingDate, due);
        if (diff < 0 || diff > MAX_DUE_DAYS) reasons.push("G4 기한 범위 이상");
        if (!dueText || text.indexOf(dueText) < 0) reasons.push("G4 기한 근거 표현이 회의록에 없음(추정 금지)");
      }
    }
    const refRaw = a["decision_ref"];
    const ref = typeof refRaw === "number" ? refRaw : 0;
    if (refRaw !== null && refRaw !== undefined && validRefs.indexOf(ref) < 0) reasons.push("G6 존재하지 않는 결정 참조");
    out.candidates.push({ kind: "액션", ref: i, title: str(a["title"]), ownerName: str(a["owner_name"]),
      ownerEmail: owner ? owner.email : "", dueDate: due && validIsoDate(due) ? due : "", dueMissing: !due,
      decisionRef: ref, evidence: str(a["evidence"]), verdict: reasons.length ? "검토필요" : "추천",
      reasons: reasons.join("; ") });
  });

  out.ok = true;
  out.recommendedCount = out.candidates.filter(c => c.verdict === "추천").length;
  out.reviewCount = out.candidates.length - out.recommendedCount;
  return out;
}
