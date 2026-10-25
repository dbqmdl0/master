"""흐름 정의 정적 검사(lint). 실행: python3 tools/lint_flows.py  → 문제 있으면 종료코드 1

검사 항목
 L1 모든 식이 구문 분석되고 지원 함수만 사용
 L2 body()/outputs()/actions() 가 존재하는 액션을, result() 가 Scope를, items() 가 감싸는 Foreach를,
    variables() 가 초기화된 변수를 가리킴
 L3 runAfter 대상이 같은 범위에 존재
 L4 변수 초기화는 최상위에만, Terminate는 Apply to each 안에 두지 않음(Power Automate 제약)
 L5 SharePoint 목록·열이 스키마에 존재, Create/Update item 에 필수 열이 모두 입력, 리터럴 선택지 값이 유효
 L6 Run script 매개변수 == Office Script main() 시그니처
 L7 트리거 목록·트리거 조건 열이 스키마에 존재
 L8 Try/Catch 골격: Catch 실행 조건이 Try 실패·시간초과, Catch 마지막은 Terminate(Failed)
 L9 자리표시자는 허용 목록만
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "emulator"))
from wdl import FUNCTIONS, ExprError, Parser, iter_expressions  # noqa: E402

SPECIAL = {"if", "and", "or", "triggerOutputs", "triggerBody", "body", "outputs", "actions", "variables", "items", "item",
           "result", "workflow", "utcNow", "addDays", "addHours", "addMinutes", "formatDateTime", "convertFromUtc",
           "convertToUtc", "dayOfWeek"}
PLACEHOLDERS = {"{{SITE_URL}}", "{{ME}}", "{{HOST_WORKBOOK}}", "{{SCRIPT_FOLDER}}", "{{VIEW_MY_ACTIONS}}",
                "{{VIEW_DECISION_QUEUE}}", "{{VIEW_CANDIDATES}}", "{{NOTIFY_CHANNEL}}", "{{FACTORY_FOLDER}}"}
SYSTEM = {"ID", "Created", "Modified", "Author", "Editor", "{Link}"}


def schema():
    d = json.loads((ROOT / "lists/lists_schema.json").read_text(encoding="utf-8"))
    return {l["name"]: {c["internalName"]: c for c in l["columns"]} for l in d["lists"]}


def script_params(name):
    src = (ROOT / "office_scripts" / f"{name}.ts").read_text(encoding="utf-8")
    m = re.search(r"function main\(workbook: ExcelScript\.Workbook,?([\s\S]*?)\)\s*:", src)
    return re.findall(r"(\w+)\s*:", m.group(1)) if m else None


def calls(node, out):
    if node[0] == "call":
        out.append((node[1], node[2]))
        for a in node[2]:
            calls(a, out)
    elif node[0] == "get":
        calls(node[1], out)
        calls(node[2], out)
    return out


def walk(actions, path=(), loops=()):
    for name, a in actions.items():
        yield name, a, path, loops
        inner_loops = loops + ((name,) if a["type"] == "Foreach" else ())
        for key in ("actions",):
            if key in a:
                yield from walk(a[key], path + (name,), inner_loops)
        if "else" in a:
            yield from walk(a["else"]["actions"], path + (name,), inner_loops)


def lint_flow(f, lists) -> list[str]:
    errs = []
    fid = f["id"]
    allacts = {n: (a, p, l) for n, a, p, l in walk(f["actions"])}
    variables = {a["inputs"]["name"] for n, (a, p, l) in allacts.items() if a["type"] == "InitializeVariable"}
    raw = json.dumps(f, ensure_ascii=False)
    for ph in set(re.findall(r"\{\{[A-Z_]+\}\}", raw)) - PLACEHOLDERS:
        errs.append(f"L9 알 수 없는 자리표시자 {ph}")

    def check_exprs(value, where, loops):
        for src in iter_expressions(value):
            try:
                node = Parser(src).parse()
            except ExprError as e:
                errs.append(f"L1 {where}: {e}")
                continue
            for fn, args in calls(node, []):
                if fn not in FUNCTIONS and fn not in SPECIAL:
                    errs.append(f"L1 {where}: 지원하지 않는 함수 {fn}()")
                lit = args[0][1] if args and args[0][0] == "lit" else None
                if fn in ("body", "outputs", "actions") and lit not in allacts:
                    errs.append(f"L2 {where}: {fn}('{lit}') 대상 액션 없음")
                if fn == "result" and (lit not in allacts or allacts[lit][0]["type"] != "Scope"):
                    errs.append(f"L2 {where}: result('{lit}') 는 Scope 여야 함")
                if fn == "items" and lit not in loops:
                    errs.append(f"L2 {where}: items('{lit}') 가 해당 Apply to each 밖에서 사용됨")
                if fn == "variables" and lit not in variables:
                    errs.append(f"L2 {where}: 초기화되지 않은 변수 {lit}")

    trig = f["trigger"]
    for c in trig.get("conditions", []):
        check_exprs(c, f"{fid}.trigger", ())
        tl = trig.get("inputs", {}).get("list")
        for col in re.findall(r"body/([A-Za-z]+)", c):
            if tl and col not in lists.get(tl, {}) and col not in SYSTEM:
                errs.append(f"L7 {fid} 트리거 조건 열 없음: {tl}.{col}")
    if trig.get("inputs", {}).get("list") and trig["inputs"]["list"] not in lists:
        errs.append(f"L7 {fid} 트리거 목록 없음: {trig['inputs']['list']}")

    def scope_check(actions, top):
        for name, a in actions.items():
            for dep in a.get("runAfter", {}):
                if dep not in actions:
                    errs.append(f"L3 {fid}.{name}: runAfter '{dep}' 가 같은 범위에 없음")
            if a["type"] == "InitializeVariable" and not top:
                errs.append(f"L4 {fid}.{name}: 변수 초기화는 최상위에서만")
            for k in ("actions",):
                if k in a:
                    scope_check(a[k], False)
            if "else" in a:
                scope_check(a["else"]["actions"], False)
    scope_check(f["actions"], True)

    for name, (a, path, loops) in allacts.items():
        where = f"{fid}.{name}"
        check_exprs({k: v for k, v in a.items() if k not in ("actions", "else", "note")}, where, loops)
        if a["type"] == "Terminate" and loops:
            errs.append(f"L4 {where}: Terminate 를 Apply to each 안에 둘 수 없음")
        if a["type"] == "Connector" and a["connector"] == "SharePoint":
            lst = a["inputs"]["list"]
            if lst not in lists:
                errs.append(f"L5 {where}: 목록 없음 {lst}")
                continue
            cols = lists[lst]
            item = a["inputs"].get("item", {})
            for k, v in item.items():
                col = k.split("/")[0]
                if col not in cols:
                    errs.append(f"L5 {where}: 열 없음 {lst}.{col}")
                    continue
                if cols[col]["type"] == "Choice" and isinstance(v, str) and not v.startswith("@") and "@{" not in v:
                    if v not in cols[col]["choices"]:
                        errs.append(f"L5 {where}: 선택지 아님 {lst}.{col}={v!r}")
            if a["operation"] in ("Create item", "Update item"):
                given = {k.split("/")[0] for k in item}
                need = [c for c, d in cols.items() if d.get("required") and c not in given]
                if need:
                    errs.append(f"L5 {where}: 필수 열 입력 누락 {need}")
            flt = a["inputs"].get("filter", "")
            for col in re.findall(r"(?:^|\(|\s)([A-Z][A-Za-z]+)(?:/EMail)?\s+(?:eq|ne|lt|le|gt|ge)\s", flt):
                if col not in cols and col not in SYSTEM:
                    errs.append(f"L5 {where}: 필터 열 없음 {lst}.{col}")
        if a["type"] == "Connector" and a["operation"] == "Run script from SharePoint library":
            sname = Path(a["inputs"]["script"].split("/")[-1]).stem
            want = script_params(sname)
            if want is None:
                errs.append(f"L6 {where}: 스크립트 없음 {sname}")
            elif set(want) != set(a["inputs"]["parameters"]):
                errs.append(f"L6 {where}: 매개변수 불일치 기대 {want} / 실제 {list(a['inputs']['parameters'])}")

    acts = f["actions"]
    if "Try" not in acts or "Catch" not in acts:
        errs.append(f"L8 {fid}: Try/Catch 골격 없음")
    else:
        if set(acts["Catch"].get("runAfter", {}).get("Try", [])) != {"Failed", "TimedOut"}:
            errs.append(f"L8 {fid}: Catch 실행 조건은 Try 실패·시간초과")
        last = list(acts["Catch"]["actions"].values())[-1]
        if last["type"] != "Terminate" or last["inputs"]["runStatus"] != "Failed":
            errs.append(f"L8 {fid}: Catch 마지막은 Terminate(Failed)")
    return errs


def main(paths=None) -> int:
    lists = schema()
    files = paths or sorted((ROOT / "flows").glob("*.flow.json"))
    total = 0
    for p in files:
        f = json.loads(Path(p).read_text(encoding="utf-8"))
        errs = lint_flow(f, lists)
        total += len(errs)
        exprs = sum(1 for _ in iter_expressions(f))
        print(f"{'PASS' if not errs else 'FAIL'} {f['id']} (식 {exprs}개)")
        for e in errs:
            print("   ", e)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
