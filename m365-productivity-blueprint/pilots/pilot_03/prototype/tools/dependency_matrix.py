"""흐름별 의존성 매트릭스 생성·검사 → DEPENDENCY_MATRIX.md (P0-1)

흐름 정의(flows/*.flow.json)에서 목록·열·커넥터·스크립트를 뽑고, 아래 STAGES(구축 순서)와 대조해
'선행 조건이 준비되지 않은 단계에서 흐름을 만들라고 안내하는' 일이 없는지 검사한다.
실행: python3 tools/dependency_matrix.py        → 문서 생성 + 검사(위반 시 종료코드 1)
      python3 tools/dependency_matrix.py --check → 검사만
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 구축 순서(START_HERE_V2.md 와 같은 원본). 각 단계에서 새로 만드는 것만 적는다(누적).
STAGES = [
    ("1주차 · A안 최소 구성", {
        "lists": ["ActionItems", "FlowErrorLog"], "scripts": [], "files": [],
        "flows": ["P3A-1", "P3A-2", "P3P-F3"]}),
    ("2주차 · 결정 기록·스크립트 브리핑(B안 전환)", {
        "lists": ["DecisionLog", "Holidays"], "files": ["P3_AutomationHost.xlsx"],
        "scripts": ["BuildDailyBrief", "BuildReminderDigest", "ParseDueHint"],
        "flows": ["P3P-F4", "P3P-F1", "P3P-F2", "P3P-F13", "P3P-F6", "P3P-F7"]}),
    ("3주차 · 회의 추출(Copilot) 검증", {
        "lists": ["MeetingIntake", "ActionCandidates", "TeamRoster"], "scripts": ["GuardExtraction"], "files": [],
        "flows": ["P3P-F8", "P3P-F9"]}),
    ("4주차 · 공장 자료·회의 준비·주간 정리", {
        "lists": ["FactorySenders", "FactoryInbox"], "scripts": ["BuildMeetingPrep", "BuildWeeklyDigest"], "files": [],
        "flows": ["P3P-F10", "P3P-F11", "P3P-F12"]}),
    ("보류 · 환경 조건 미충족", {"lists": [], "scripts": [], "files": [], "flows": ["P3P-F5"]}),
]

# JSON에서 뽑을 수 없는 사실(선행 흐름·환경 조건·대체 관계)
EXTRA = {
    "P3A-1": {"note": "2주차에 끄고 P3P-F1로 교체(같은 고유키라 중복 없음). P3P-F1과 동시에 켜지 않는다."},
    "P3A-2": {"note": "2주차에 P3P-F6이 안정되면 끈다(둘 다 켜 두면 아침 메일 2통)."},
    "P3P-F1": {"replaces": "P3A-1", "flows": ["P3P-F3", "P3P-F4"],
               "note": "범주 '결정요청'·'결정' 메일을 DecisionLog에 쓴다 → DecisionLog·F4(번호)가 먼저 있어야 한다."},
    "P3P-F2": {"flows": ["P3P-F3"]},
    "P3P-F4": {"note": "확정 시 빈 항목(결정권자·근거·후속조치) 표시."},
    "P3P-F5": {"blocked": "Teams 메시지 '추가 작업' 트리거는 Teams의 Workflows(Power Automate) 앱이 필요하다. "
                          "현재 테넌트에서 앱이 없으므로 만들지 않는다 — 대체: P3P-F1 + Outlook 범주.", "flows": ["P3P-F3", "P3P-F4"]},
    "P3P-F6": {"replaces": "P3A-2", "flows": ["P3P-F3"]},
    "P3P-F7": {"flows": ["P3P-F3"]},
    "P3P-F9": {"flows": ["P3P-F8", "P3P-F3", "P3P-F4"]},
    "P3P-F12": {"note": "FactoryInbox 목록이 없으면 조회 단계가 실패한다 → 4주차(목록 생성 후)에 만든다. 비어 있는 것은 괜찮다."},
    "P3P-F13": {"flows": ["P3P-F3"], "note": "트리거 조건에 '액션번호 있음'이 있어 F3가 번호를 붙인 뒤에만 실행된다(두 흐름이 같은 항목을 동시에 고치지 않게)."},
}
FIRST_TEST = {
    "P3A-1": "가상 메일 1통 플래그 → 할 일 1건 / 다시 플래그 → 늘지 않음",
    "P3A-2": "'테스트' 실행 → 본인 메일 1통(초과·임박·기한 없음 표)",
    "P3P-F1": "범주 '결정요청' 메일 플래그 → DecisionLog '결정요청' 1건, 할 일 0건",
    "P3P-F2": "보낸 편지함 메일 플래그 → '회신대기' 할 일(기한 +3일)",
    "P3P-F3": "할 일 1건 상태 변경 → 액션번호·완료일시 기록, 다른 열 그대로",
    "P3P-F4": "결정 1건 '확정'으로 변경 → 확정일·'확정 확인 필요' 표시",
    "P3P-F5": "(보류)",
    "P3P-F6": "'테스트' 실행 → 브리핑 메일(또는 카드) 1통, 기한 없는 할 일 칸 확인",
    "P3P-F7": "기한 지난 내 할 일 1건 → 리마인더 1통, 횟수 1",
    "P3P-F8": "샘플 추출 결과 붙여넣기 → 후보 생성, 할 일 0건",
    "P3P-F9": "후보 1건 '승인' → 그 1건만 등록",
    "P3P-F10": "공장 발신자 등록 후 가상 첨부 메일 → OneDrive 저장 + 대장 1줄",
    "P3P-F11": "내일 가상 회의 1건 → 준비 메일 1통",
    "P3P-F12": "'테스트' 실행 → 주간 정리 메일 1통",
    "P3P-F13": "'내일까지' 문구 메일 플래그 → 기한·근거 채워짐",
}
TRIGGER_CONNECTOR = {"Outlook": "Office 365 Outlook", "SharePoint": "SharePoint", "Teams": "Microsoft Teams", "Recurrence": "(일정)"}
PERMS = {
    "SharePoint": "해당 목록 편집 권한(본인 사이트)",
    "Office 365 Outlook": "본인 사서함·일정(위임 권한)",
    "Microsoft Teams": "Workflows 앱 허용 필요(채널=teams일 때만). 메일 모드에서는 조건의 Teams 분기를 비워 두면 Teams 연결 불필요",
    "Excel Online (Business)": "본인 OneDrive의 호스트 통합 문서·'문서/Office Scripts' 스크립트",
    "OneDrive for Business": "본인 OneDrive 쓰기",
    "Office 365 Users": "사용자 프로필 읽기(조직 기본 허용, 미확인 시 IT 확인)",
}


def walk(actions):
    for name, a in actions.items():
        yield name, a
        if "actions" in a:
            yield from walk(a["actions"])
        if "else" in a:
            yield from walk(a["else"]["actions"])


def analyze(f: dict) -> dict:
    lists: dict[str, set[str]] = {}
    fields: dict[str, set[str]] = {}
    connectors, scripts, notify_teams = set(), set(), False
    t = f["trigger"]
    tc = TRIGGER_CONNECTOR[t["kind"].split(".")[0]]
    if tc != "(일정)":
        connectors.add(tc)
    if "list" in t.get("inputs", {}):
        lists.setdefault(t["inputs"]["list"], set()).add("트리거")
        for c in t.get("conditions", []):
            fields.setdefault(t["inputs"]["list"], set()).update(re.findall(r"body/([A-Za-z]+)", c))
    for name, a in walk(f["actions"]):
        if a["type"] != "Connector":
            continue
        if a["connector"] == "Microsoft Teams":
            notify_teams = True
            continue
        connectors.add(a["connector"])
        i = a["inputs"]
        if a["connector"] == "SharePoint":
            mode = "쓰기" if a["operation"] in ("Create item", "Update item") else "읽기"
            lists.setdefault(i["list"], set()).add(mode)
            fs = fields.setdefault(i["list"], set())
            fs.update(k.split("/")[0] for k in i.get("item", {}))
            fs.update(re.findall(r"(?:^|\(|\s)([A-Z][A-Za-z]+)(?:/EMail)?\s+(?:eq|ne|lt|le|gt|ge)\s", i.get("filter", "")))
        if a["operation"] in ("Run script", "Run script from SharePoint library"):
            scripts.add(Path(i["script"].split("/")[-1]).stem)
    if f["trigger"]["kind"] == "Teams.ForASelectedMessage":
        connectors.add("Microsoft Teams")
    fields = {k: {c for c in v if c not in ("ID", "Created", "Modified", "Author", "Editor")} for k, v in fields.items()}
    return {"lists": lists, "fields": fields, "connectors": connectors, "scripts": scripts, "notify_teams": notify_teams}


def load():
    """구축 순서대로 정렬(단계에 없는 흐름은 뒤)."""
    order = [fid for _, st in STAGES for fid in st["flows"]]
    fl = {f["id"]: f for f in (json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "flows").glob("*.flow.json")))}
    return dict(sorted(fl.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else len(order)))


def check(flows: dict) -> list[str]:
    errs, have_lists, have_scripts, have_flows, seen = [], set(), set(), set(), []
    for stage, s in STAGES:
        have_lists |= set(s["lists"])
        have_scripts |= set(s["scripts"])
        stage_flows = set(s["flows"])
        for fid in s["flows"]:
            seen.append(fid)
            if fid not in flows:
                errs.append(f"{stage}: 정의 없는 흐름 {fid}")
                continue
            if EXTRA.get(fid, {}).get("blocked"):
                continue
            a = analyze(flows[fid])
            for lst in a["lists"]:
                if lst not in have_lists:
                    errs.append(f"{stage}: {fid} 가 아직 만들지 않은 목록 {lst} 사용")
            for sc in a["scripts"]:
                if sc not in have_scripts:
                    errs.append(f"{stage}: {fid} 가 아직 올리지 않은 스크립트 {sc} 사용")
            for pf in EXTRA.get(fid, {}).get("flows", []):
                if pf not in have_flows | stage_flows:
                    errs.append(f"{stage}: {fid} 의 선행 흐름 {pf} 이(가) 아직 없음")
                elif pf in stage_flows and s["flows"].index(pf) > s["flows"].index(fid):
                    errs.append(f"{stage}: {fid} 보다 선행 흐름 {pf} 를 먼저 만들어야 함(단계 안 순서)")
        have_flows |= stage_flows
    for fid in flows:
        if seen.count(fid) != 1:
            errs.append(f"흐름 {fid} 가 구축 단계에 {seen.count(fid)}번 나옴(정확히 1번이어야 함)")
    return errs


def render(flows: dict) -> str:
    stage_of = {fid: st for st, s in STAGES for fid in s["flows"]}
    out = ["# DEPENDENCY_MATRIX — 흐름별 선행 조건 (자동 생성)", "",
           "> `tools/dependency_matrix.py`가 `flows/*.flow.json`과 구축 순서(STAGES)에서 생성·검사한다. 직접 수정하지 말 것.",
           "> 규칙: **선행 조건이 하나라도 없으면 그 흐름을 만들지 않는다.** 이 표의 단계 배정은 생성 시 자동 검사된다(위반 시 오류).",
           "> 라이선스: 모든 흐름이 Microsoft 365에 포함된 Power Automate **표준 커넥터**만 쓴다(Premium 불필요 — 커넥터 문서의 표준 표시로 확인, 테넌트 정책은 미확인).",
           "> Copilot은 흐름이 아니라 사람이 회의록을 추출할 때만 쓴다(P3P-F8 입력). 회사 Copilot 정책 확인 전에는 실제 회의록을 넣지 않는다.", "",
           "## 1. 요약", "",
           "| 흐름 | 단계 | 목록(트리거·읽기·쓰기) | 커넥터(연결) | Office Scripts | 선행 흐름 | 첫 테스트 |", "|---|---|---|---|---|---|---|"]
    for fid, f in flows.items():
        a, x = analyze(f), EXTRA.get(fid, {})
        lists = "<br>".join(f"`{l}`({'·'.join(sorted(m))})" for l, m in a["lists"].items())
        conns = sorted(a["connectors"]) + (["Microsoft Teams(알림, 선택)"] if a["notify_teams"] and "Microsoft Teams" not in a["connectors"] else [])
        out.append(f"| **{fid}** | {stage_of.get(fid, '?')} | {lists} | {', '.join(conns)} | {', '.join(sorted(a['scripts'])) or '없음'} | "
                   f"{', '.join(x.get('flows', [])) or '없음'} | {FIRST_TEST.get(fid, '')} |")
    out += ["", "## 2. 단계별 준비 체크리스트(누적)", ""]
    for stage, s in STAGES:
        out += [f"### {stage}", ""]
        if s["lists"]:
            out.append(f"- [ ] 목록 만들기: {', '.join('`' + l + '`' for l in s['lists'])} (`LISTS_SETUP.md`)")
        if s["files"]:
            out.append(f"- [ ] 파일: {', '.join(s['files'])} → 본인 OneDrive `문서/P3/`")
        if s["scripts"]:
            out.append(f"- [ ] Office Scripts: {', '.join(s['scripts'])} → Excel 웹 › 자동화 › 새 스크립트 › 붙여넣기 › 저장(본인 OneDrive `문서/Office Scripts`에 저장됨)")
        for fid in s["flows"]:
            x = EXTRA.get(fid, {})
            if x.get("blocked"):
                out.append(f"- ⛔ {fid}: {x['blocked']}")
            else:
                out.append(f"- [ ] {fid} 만들기 → 첫 테스트: {FIRST_TEST.get(fid, '')}" + (f" · {x['note']}" if x.get("note") else ""))
        out.append("")
    out += ["## 3. 흐름별 사용 열(내부 이름) — 목록에 이 열이 없으면 흐름을 저장·실행할 수 없다", ""]
    for fid, f in flows.items():
        a = analyze(f)
        out.append(f"- **{fid}**: " + "; ".join(f"`{l}` ← {', '.join(sorted(c)) or '(열 지정 없음)'}" for l, c in a["fields"].items()))
    out += ["", "## 4. 연결(Connection)과 권한", "", "| 커넥터 | 필요한 권한·조건 |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in PERMS.items()]
    out += ["", "- Teams **Workflows 앱 사용 불가**와 **Teams 커넥터 사용 불가**는 다른 문제다. 앱이 없으면 Flow bot 게시·메시지 트리거가 막히고, "
            "커넥터 자체가 DLP로 막히면 Teams 액션이 들어간 흐름은 저장이 거부된다. 둘은 `APPROVALS.md` 확인 항목에서 따로 점검한다.", ""]
    return "\n".join(out) + "\n"


def main(argv) -> int:
    flows = load()
    errs = check(flows)
    for e in errs:
        print("FAIL", e)
    if "--check" not in argv:
        (ROOT / "DEPENDENCY_MATRIX.md").write_text(render(flows), encoding="utf-8")
        print("wrote DEPENDENCY_MATRIX.md")
    print(f"의존성 검사: {'통과' if not errs else f'위반 {len(errs)}건'} (흐름 {len(flows)}개, 단계 {len(STAGES)}개)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
