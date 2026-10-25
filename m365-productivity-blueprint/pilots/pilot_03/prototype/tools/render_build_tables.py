"""흐름 정의(flows/*.flow.json) → 디자이너 입력표(BUILD_TABLES.md) 생성.
테스트를 통과한 정의와 같은 원본에서 만들므로 '문서와 실제 로직이 다른' 일이 생기지 않는다.
실행: python3 tools/render_build_tables.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = {l["name"]: {c["internalName"]: c for c in l["columns"]}
          for l in json.loads((ROOT / "lists/lists_schema.json").read_text(encoding="utf-8"))["lists"]}

UI = {
    "Compose": "데이터 작업 › **작성(Compose)**",
    "InitializeVariable": "변수 › **변수 초기화(Initialize variable)**",
    "AppendToArrayVariable": "변수 › **배열 변수에 추가(Append to array variable)**",
    "If": "컨트롤 › **조건(Condition)**",
    "Scope": "컨트롤 › **범위(Scope)**",
    "Foreach": "컨트롤 › **각각에 적용(Apply to each)**",
    "FilterArray": "데이터 작업 › **배열 필터링(Filter array)**",
    "Select": "데이터 작업 › **선택(Select)**",
    "Terminate": "컨트롤 › **종료(Terminate)**",
}
TRIGGER_UI = {
    "Outlook.WhenAnEmailIsFlaggedV4": "Office 365 Outlook › **When an email is flagged (V4)** (전자 메일에 플래그가 지정된 경우)",
    "SharePoint.WhenAnItemIsCreatedOrModified": "SharePoint › **When an item is created or modified** (항목을 만들거나 수정한 경우)",
    "SharePoint.WhenAnItemIsCreated": "SharePoint › **When an item is created** (항목을 만든 경우)",
    "Teams.ForASelectedMessage": "Microsoft Teams › **For a selected message** (선택한 메시지에 대해)",
    "Recurrence": "일정 › **Recurrence(되풀이)**",
}
FIELD_UI = {"site": "사이트 주소(Site Address) — '사용자 지정 값 입력'", "list": "목록 이름(List Name) — '사용자 지정 값 입력'",
            "filter": "필터 쿼리(Filter Query)", "top": "상위 개수(Top Count)", "id": "ID",
            "poster": "게시자(Post as)", "location": "게시 위치(Post in)", "recipient": "받는 사람(Recipient)",
            "card": "Adaptive Card", "message": "메시지(Message)", "workbook": "통합 문서(Workbook) 위치·파일",
            "script": "스크립트(Script) 위치·파일", "user": "사용자(UPN)", "calendarId": "일정 ID(Calendar id)",
            "startTime": "시작 시간(Start Time)", "endTime": "종료 시간(End Time)", "to": "받는 사람(To)",
            "subject": "제목(Subject)", "body": "본문(Body)"}


def show(v) -> str:
    if isinstance(v, bool):
        return "`true`(식 탭)" if v else "`false`(식 탭)"
    if isinstance(v, (int, float)):
        return f"`{v}`"
    if v is None:
        return "`null`(식 탭)"
    if isinstance(v, (dict, list)):
        return "`" + json.dumps(v, ensure_ascii=False).replace("|", "\\|") + "`"
    s = str(v).replace("|", "\\|")
    if s.startswith("@") and not s.startswith("@{"):
        return f"**fx** `{s[1:]}`"
    if "@{" in s:
        return f"`{s}`"
    return f"`{s}`" if s else "(비움)"


def field_label(lst, key):
    col = key.split("/")[0]
    meta = SCHEMA.get(lst, {}).get(col)
    disp = f"{meta['displayName']}" if meta else col
    suffix = {"Value": " (선택 값)", "Claims": " (사람: 이메일)"}.get(key.split("/")[-1], "") if "/" in key else ""
    return f"{disp} `{col}`{suffix}"


def run_after(a) -> str:
    ra = a.get("runAfter", {})
    odd = {k: v for k, v in ra.items() if v != ["Succeeded"]}
    if not odd:
        return ""
    return "; ".join(f"**실행 후 구성**: '{k}' 이(가) {', '.join({'Succeeded': '성공함', 'Failed': '실패함', 'TimedOut': '시간 초과됨', 'Skipped': '건너뜀'}[s] for s in v)}"
                     for k, v in odd.items())


def rows(actions, prefix, out, depth=0):
    for i, (name, a) in enumerate(actions.items(), 1):
        num = f"{prefix}{i}"
        t = a["type"]
        what = UI.get(t) or f"{a['connector']} › **{a['operation']}**"
        cfg = []
        if t == "Connector":
            lst = a["inputs"].get("list")
            for k, v in a["inputs"].items():
                if k == "item":
                    for fk, fv in v.items():
                        cfg.append(f"{field_label(lst, fk)}: {show(fv)}")
                elif k == "parameters":
                    for pk, pv in v.items():
                        cfg.append(f"매개변수 `{pk}`: {show(pv)}")
                else:
                    cfg.append(f"{FIELD_UI.get(k, k)}: {show(v)}")
        elif t == "Compose":
            cfg.append(f"입력(Inputs): {show(a['inputs'])}")
        elif t in ("InitializeVariable", "AppendToArrayVariable"):
            cfg.append(f"이름 `{a['inputs']['name']}`" + (f", 형식 {a['inputs'].get('type')}" if "type" in a["inputs"] else "")
                       + f", 값 {show(a['inputs'].get('value'))}")
        elif t == "If":
            cfg.append(f"왼쪽 값: **fx** `{a['expression'][1:]}` · 연산자 **같음(is equal to)** · 오른쪽 값: **fx** `true`")
        elif t == "Foreach":
            cfg.append(f"이전 단계에서 출력 선택: **fx** `{a['foreach'][1:]}` · 설정 › 동시성 제어 **켬, 병렬 처리 수준 1**")
        elif t == "FilterArray":
            cfg.append(f"보낸 사람(From): {show(a['inputs']['from'])} · '고급 모드에서 편집' 후: `{a['inputs']['where']}`")
        elif t == "Terminate":
            i_ = a["inputs"]
            st = {"Succeeded": "성공함(Succeeded)", "Failed": "실패함(Failed)", "Cancelled": "취소됨"}[i_["runStatus"]]
            cfg.append(f"상태: {st}" + (f" · 코드 `{i_['runError']['code']}` · 메시지 {show(i_['runError']['message'])}"
                                         if i_["runStatus"] == "Failed" else ""))
        ra = run_after(a)
        if ra:
            cfg.append(ra)
        note = a.get("note", "")
        out.append(f"| {num} | {'　' * depth}`{name}` | {what} | {'<br>'.join(cfg) or '-'} | {note} |")
        if t in ("If",):
            out.append(f"| {num}.예 | {'　' * (depth + 1)}**'True(예)' 분기** | | | |")
            rows(a.get("actions", {}), f"{num}.예.", out, depth + 1)
            if "else" in a:
                out.append(f"| {num}.아니요 | {'　' * (depth + 1)}**'False(아니요)' 분기** | | | |")
                rows(a["else"]["actions"], f"{num}.아니요.", out, depth + 1)
        elif "actions" in a:
            rows(a["actions"], f"{num}.", out, depth + 1)


def render():
    lines = ["# Pilot 03 프로토타입 — 흐름별 디자이너 입력표 (자동 생성)", "",
             "> 이 파일은 `tools/render_build_tables.py`가 `flows/*.flow.json`에서 생성한다. **직접 수정하지 말 것.**",
             "> 사용법은 `BUILD_GUIDE.md` 3장. 표의 '액션 이름'은 액션 카드의 **… › 이름 바꾸기(Rename)** 로 똑같이 바꾼다 — 식이 이 이름을 참조한다.",
             "> **fx** 표시 값은 입력란의 **식(fx)** 탭에 붙여넣는다. `@{...}`가 섞인 값은 입력란에 그대로 붙여넣는다(식 토큰으로 바뀌지 않으면 fx 탭에 중괄호 안 식만).",
             "> `{{...}}` 자리표시자는 `BUILD_GUIDE.md` 1장 값으로 바꾼다.", ""]
    for p in sorted((ROOT / "flows").glob("*.flow.json")):
        f = json.loads(p.read_text(encoding="utf-8"))
        t = f["trigger"]
        lines += [f"## {f['name']}", "", f"**목적:** {f['purpose']}", "",
                  f"**만들기:** {'자동화된 클라우드 흐름' if t['kind'] not in ('Recurrence', 'Teams.ForASelectedMessage') else ('예약된 클라우드 흐름' if t['kind'] == 'Recurrence' else '인스턴트 클라우드 흐름')} · 흐름 이름 `{f['name']}`", "",
                  f"**트리거:** {TRIGGER_UI[t['kind']]}", ""]
        ins = t.get("inputs", {})
        if "site" in ins:
            lines.append(f"- 사이트 주소: `{ins['site']}` · 목록 이름: `{ins['list']}`")
        if "folder" in ins:
            lines.append(f"- 폴더(Folder): `{ins['folder']}`")
        if "inputCard" in ins:
            lines.append(f"- Adaptive Card: `{ins['inputCard']}` 파일 내용을 붙여넣기")
        if t["kind"] == "Recurrence":
            r = t["recurrence"]
            lines.append(f"- 간격 1 / 빈도 **주(Week)** · 표준 시간대 **(UTC+09:00) Seoul** · 요일 월~금 · 시간 {r['schedule']['hours'][0]} · 분 {r['schedule']['minutes'][0]}")
        for c in t.get("conditions", []):
            lines.append(f"- 트리거 카드 **… › 설정(Settings) › 트리거 조건(Trigger conditions) › + 추가**: `{c}`")
        if t.get("concurrency") == 1:
            lines.append("- 트리거 **설정 › 동시성 제어(Concurrency control) 켬 › 병렬 처리 수준 1** (한 번 켜면 되돌리려면 트리거를 다시 만들어야 함)")
        lines += ["", "| 단계 | 액션 이름(이름 바꾸기) | 추가할 액션 | 설정값 | 비고 |", "|---|---|---|---|---|"]
        rows(f["actions"], "", lines)
        lines.append("")
    (ROOT / "BUILD_TABLES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote BUILD_TABLES.md", len(lines), "lines")


if __name__ == "__main__":
    render()


TYPE_UI = {"Text": "한 줄 텍스트", "Note": "여러 줄 텍스트", "Number": "숫자", "DateTime": "날짜 및 시간",
           "Choice": "선택(Choice)", "User": "사람(Person)", "Boolean": "예/아니요"}


def render_lists():
    d = json.loads((ROOT / "lists/lists_schema.json").read_text(encoding="utf-8"))
    out = ["# Pilot 03 프로토타입 — 목록 열 설정표 (자동 생성)", "",
           "> `tools/render_build_tables.py`가 `lists/lists_schema.json`에서 생성. 직접 수정하지 말 것. 절차는 `BUILD_GUIDE.md` 2장.",
           "> **내부 이름**으로 먼저 만들고(영문) 표시 이름은 나중에 한글로 바꾼다. 흐름의 식이 내부 이름을 쓴다.", ""]
    for l in d["lists"]:
        out += [f"## {l['name']} — {l['displayName']}", "", l.get("purpose", ""), "",
                "| 내부 이름 | 표시 이름 | 형식 | 필수 | 선택지 / 기본값 | 인덱스 | 입력 양식에서 숨김 |", "|---|---|---|---|---|---|---|"]
        for c in l["columns"]:
            typ = TYPE_UI[c["type"]] + (" (날짜만)" if c.get("dateOnly") else "") + (" (시간 포함)" if c["type"] == "DateTime" and not c.get("dateOnly") else "")
            ch = ", ".join(c.get("choices", []))
            if "default" in c:
                ch += f" / 기본값 `{c['default']}`"
            out.append(f"| `{c['internalName']}` | {c['displayName']} | {typ} | {'예' if c.get('required') else ''} | {ch} | "
                       f"{'예' if c.get('indexed') or c.get('unique') else ''} | {'예' if c.get('hidden') else ''} |")
        if l.get("views"):
            out += ["", "보기: " + "; ".join(f"**{v['name']}**" + (f" — 필터 {v['filter']}" if v.get("filter") else "") for v in l["views"])]
        out += ["", f"권한: {l.get('permissions', '')}", ""]
    (ROOT / "LISTS_SETUP.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("wrote LISTS_SETUP.md")


if __name__ == "__main__":
    render_lists()
