"""Pilot 03 프로토타입 흐름 정의 생성기 → flows/*.flow.json

각 흐름은 '설정(Config) → Try 범위 → Catch 범위' 공통 골격을 쓴다.
생성된 JSON은 (1) 에뮬레이터가 그대로 실행해 테스트하고 (2) render_build_tables.py가 디자이너 입력표로 변환한다.
값의 {{...}} 자리표시자는 구축 시 실제 값(사이트 주소, 본인 이메일, 파일 경로, 보기 URL)으로 바꾼다.
실행: python3 tools/build_flows.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "flows"
SCHEMA = {l["name"]: l["columns"] for l in json.loads((ROOT / "lists/lists_schema.json").read_text(encoding="utf-8"))["lists"]}
TODAY = "convertFromUtc(utcNow(), 'Korea Standard Time', 'yyyy-MM-dd')"
SITE = "{{SITE_URL}}"
T = "triggerOutputs()?['body/{}']"

CONFIG = {"type": "Compose", "note": "설정값 모음. 샌드박스→운영 전환 시 이 값만 바꾼다(트리거의 사이트·목록은 직접 다시 선택).",
          "inputs": {"site": SITE, "me": "{{ME}}", "hostWorkbook": "{{HOST_WORKBOOK}}",
                     # scriptFolder: 팀 단계(SharePoint 라이브러리 실행)용. 개인 파일럿 'Run script'(OneDrive)는 쓰지 않음
                     "scriptFolder": "{{SCRIPT_FOLDER}}", "prototypeMode": True, "channel": "{{NOTIFY_CHANNEL}}",
                     "factoryFolder": "{{FACTORY_FOLDER}}",
                     "links": {"myActions": "{{VIEW_MY_ACTIONS}}", "decisionQueue": "{{VIEW_DECISION_QUEUE}}",
                               "candidates": "{{VIEW_CANDIDATES}}"}}}
CFG = "outputs('Config')"


def t(field):
    return T.format(field)


def chain(actions: dict) -> dict:
    """정의 순서대로 앞 액션 성공 후 실행되도록 runAfter 를 채운다(이미 지정된 경우 유지)."""
    prev = None
    for name, a in actions.items():
        if "runAfter" not in a:
            a["runAfter"] = {prev: ["Succeeded"]} if prev else {}
        prev = name
    return actions


def sp(op, lst, note="", runAfter=None, **kw):
    inputs = {"site": f"@{{{CFG}?['site']}}", "list": lst}
    inputs.update(kw)
    a = {"type": "Connector", "connector": "SharePoint", "operation": op, "inputs": inputs, "note": note}
    if runAfter is not None:
        a["runAfter"] = runAfter
    return a


def card_to_me(card_expr, html_expr, subject, recipient=None, note="본인에게 알림(카드 또는 메일)"):
    """알림 자리표시. expand_notify()가 '채널 설정(teams/email)' 조건으로 펼친다."""
    return {"type": "_Notify", "kind": "card", "card": card_expr, "html": html_expr, "subject": subject,
            "recipient": recipient or f"@{{{CFG}?['me']}}", "note": note}


def msg_to_me(text, subject="[P3 알림]", note="본인에게 알림(Teams 메시지 또는 메일)"):
    return {"type": "_Notify", "kind": "message", "text": text, "subject": subject,
            "recipient": f"@{{{CFG}?['me']}}", "note": note}


def _notify_if(name, n):
    """Workflows(Teams) 앱이 없으면 channel=email 로 두고 본인 메일로 받는다. 앱이 허용되면 teams 로 바꾼다."""
    if n["kind"] == "card":
        teams = {"type": "Connector", "connector": "Microsoft Teams", "operation": "Post card in a chat or channel",
                 "inputs": {"poster": "Flow bot", "location": "Chat with Flow bot", "recipient": n["recipient"], "card": n["card"]},
                 "note": "Teams Flow bot 카드", "runAfter": {}}
        body = n["html"]
    else:
        teams = {"type": "Connector", "connector": "Microsoft Teams", "operation": "Post message in a chat or channel",
                 "inputs": {"poster": "Flow bot", "location": "Chat with Flow bot", "recipient": n["recipient"], "message": n["text"]},
                 "note": "Teams Flow bot 메시지", "runAfter": {}}
        body = n["text"]
    email = {"type": "Connector", "connector": "Office 365 Outlook", "operation": "Send an email (V2)",
             "inputs": {"to": n["recipient"], "subject": n["subject"], "body": body},
             "note": "메일 알림(Workflows 앱 없을 때)", "runAfter": {}}
    a = {"type": "If", "expression": f"@equals({CFG}?['channel'], 'teams')",
         "actions": {f"{name}_teams": teams}, "else": {"actions": {f"{name}_email": email}},
         "note": n["note"] + " — 설정 channel 이 teams 면 Teams, 아니면 메일"}
    if "runAfter" in n:
        a["runAfter"] = n["runAfter"]
    return a


def expand_notify(actions: dict) -> dict:
    for name in list(actions):
        a = actions[name]
        if a.get("type") == "_Notify":
            actions[name] = _notify_if(name, a)
            continue
        if "actions" in a:
            expand_notify(a["actions"])
        if "else" in a:
            expand_notify(a["else"]["actions"])
    return actions


def script(name, params, note):
    """개인 파일럿 기본: Excel Online (Business) 'Run script'(OneDrive).
    - 통합 문서: 본인 OneDrive의 P3_AutomationHost.xlsx (위치 OneDrive for Business / 문서 라이브러리 OneDrive)
    - 스크립트: 본인 OneDrive '문서/Office Scripts' 폴더의 <name>.osts — 'Run script'는 이 기본 위치의 스크립트만 목록에 보여 준다
    팀 단계에서 스크립트를 SharePoint 라이브러리에 두면 'Run script from SharePoint library'로 바꾼다(START_HERE_V2 4주차, DEPENDENCY_MATRIX).
    반환값 경로 body('…')?['result'] 는 로컬 에뮬레이터 기준이며 실제 테넌트에서 1회 스모크 테스트로 확인한다(TEST_RESULTS T-OS1)."""
    return {"type": "Connector", "connector": "Excel Online (Business)", "operation": "Run script",
            "inputs": {"location": "OneDrive for Business", "documentLibrary": "OneDrive",
                       "file": f"@{{{CFG}?['hostWorkbook']}}", "script": name, "parameters": params},
            "note": note + " · 스크립트 위치: 본인 OneDrive 문서/Office Scripts"}


def preserve(lst, src, overrides, note=""):
    """Update item 안전 패턴(P0-5).
    방금 읽은 최신 값(src = Get item 결과 식)으로 목록의 **모든 열**을 다시 채우고, 바꿀 열만 덮어쓴다.
    '입력하지 않은 열은 유지된다'와 '비워 둔 입력은 값을 지운다'가 테넌트·커넥터 버전마다 확인되지 않았으므로 두 경우 모두에 안전하다.
    선택 열은 /Value, 사람 열은 /Claims, 날짜·숫자·예/아니요는 null을 그대로 넘긴다(문자열 보간 금지: null이 ''로 바뀌는 것 방지)."""
    item = {}
    for c in SCHEMA[lst]:
        n, ty = c["internalName"], c["type"]
        if ty == "Choice":
            item[f"{n}/Value"] = f"@{src}?['{n}']?['Value']"
        elif ty == "User":
            item[f"{n}/Claims"] = f"@{src}?['{n}']?['Claims']"
        else:
            item[n] = f"@{src}?['{n}']"
    for k, v in overrides.items():
        for kk in [x for x in item if x.split("/")[0] == k.split("/")[0]]:
            del item[kk]
        item[k] = v
    return item


def update_preserving(lst, id_expr, src, overrides, note, runAfter=None):
    a = sp("Update item", lst, note, runAfter=runAfter, id=id_expr, item=preserve(lst, src, overrides))
    a["preserve"] = {"from": src, "changed": list(overrides)}
    return a


def note_expr(src, text_expr):
    return (f"concat(coalesce({src}?['SyncNote'], ''), if(empty({src}?['SyncNote']), '', ' / '), "
            f"'[', {TODAY}, '] ', {text_expr})")


def append_note(src, text_expr):
    """동기화 메모에 '[오늘] 내용'을 덧붙인다(이전 메모 보존)."""
    return f"@{{{note_expr(src, text_expr)}}}"


def terminate(status, code, message):
    return {"type": "Terminate", "inputs": {"runStatus": status, "runError": {"code": code, "message": message}}}


def iff(expr, yes: dict, no: dict | None = None, note=""):
    a = {"type": "If", "expression": expr, "actions": chain(yes), "note": note}
    if no is not None:
        a["else"] = {"actions": chain(no)}
    return a


def catch(extra: dict | None = None) -> dict:
    """공통 Catch.
    - 실패·시간 초과 액션을 모두 추림. 비어 있어도(바깥 조건·반복의 일반 오류) '식별 불가'로 기록
    - 오류 로그에는 흐름 이름·실행 ID·실패 액션·오류 코드·메시지 앞 300자만 남긴다(메일 본문·회의록·카드 내용은 넣지 않음)
    - 오류 로그 기록마저 실패하면(목록 권한·연결 만료) 본인 메일로 직접 알림 — Teams를 거치지 않는다
    - 마지막은 항상 Terminate(Failed): 실행 기록에서 실패로 보이게 한다"""
    fa = "first(body('Failed_actions'))"
    acts = {
        "Failed_actions": {"type": "FilterArray", "note": "Try 안에서 실패·시간 초과된 액션만 추림",
                           "inputs": {"from": "@result('Try')",
                                      "where": "@or(equals(item()?['status'], 'Failed'), equals(item()?['status'], 'TimedOut'))"}},
        "Error_text": {"type": "Compose", "note": "오류 요약(민감 내용 없이 300자 이내). 조건·반복 안쪽 실패는 엔진이 상세를 올려 주지 않으므로 위치를 안내",
                       "inputs": "@{" + _cut(
                           f"if(empty(body('Failed_actions')), '실패 액션을 식별하지 못했습니다(실행 기록 링크 확인)', "
                           f"if(equals({fa}?['error']?['code'], 'ActionFailed'), concat('[', {fa}?['name'], '] 안쪽 단계가 실패했습니다 — 실행 기록 링크에서 빨간 단계의 오류를 확인하세요'), "
                           f"concat(coalesce({fa}?['error']?['code'], ''), ' ', coalesce({fa}?['error']?['message'], '상세 메시지 없음'))))", 300) + "}"},
        "Log_error": sp("Create item", "FlowErrorLog", "공통 오류 로그 기록", item={
            "Title": "@{workflow()?['tags']?['flowDisplayName']}",
            "FlowRunId": "@{workflow()?['run']?['name']}",
            "FailedAction": f"@{{coalesce({fa}?['name'], '(식별 불가)')}}",
            "ErrorMessage": "@{outputs('Error_text')}",
            "Severity/Value": "Critical", "Resolved": False,
            "RunUrl": "@{concat('https://make.powerautomate.com/environments/', workflow()?['tags']?['environmentName'], '/flows/', workflow()?['name'], '/runs/', workflow()?['run']?['name'])}"}),
        "Log_failed_email": {"type": "Connector", "connector": "Office 365 Outlook", "operation": "Send an email (V2)",
                             "runAfter": {"Log_error": ["Failed", "TimedOut"]},
                             "note": "오류 로그 기록 실패 시 본인 메일로 직접 알림(내용 없이 흐름 이름·실행 링크만)",
                             "inputs": {"to": f"@{{{CFG}?['me']}}",
                                        "subject": "@{concat('[P3 오류] ', workflow()?['tags']?['flowDisplayName'], ' — 오류 로그 기록도 실패')}",
                                        "body": "@{concat('실패 액션: ', coalesce(first(body('Failed_actions'))?['name'], '(식별 불가)'), '<br>FlowErrorLog 목록 권한·연결을 확인하세요.<br>실행 기록: https://make.powerautomate.com/environments/', workflow()?['tags']?['environmentName'], '/flows/', workflow()?['name'], '/runs/', workflow()?['run']?['name'])}"}},
    }
    prev = "Log_failed_email"
    for k, v in (extra or {}).items():
        if "runAfter" not in v:
            v["runAfter"] = {prev: ["Succeeded", "Failed", "Skipped", "TimedOut"]}
        acts[k] = v
        prev = k
    chain(acts)
    acts["Terminate_failed"] = {**terminate("Failed", "FlowFailed", "@{concat('실패 액션: ', coalesce(first(body('Failed_actions'))?['name'], '(식별 불가)'))}"),
                                "runAfter": {prev: ["Succeeded", "Failed", "Skipped", "TimedOut"]}}
    acts["Failed_actions"]["runAfter"] = {}
    return {"type": "Scope", "runAfter": {"Try": ["Failed", "TimedOut"]}, "actions": acts,
            "note": "실행 후 구성: Try가 '실패함'·'시간 초과됨'일 때"}


def flow(fid, name, trigger, try_actions, pre=None, catch_extra=None, purpose=""):
    top = {"Config": dict(CONFIG)}
    for k, v in (pre or {}).items():
        top[k] = v
    chain(top)
    last = list(top)[-1]
    top["Try"] = {"type": "Scope", "runAfter": {last: ["Succeeded"]}, "actions": chain(try_actions)}
    top["Catch"] = catch(catch_extra)
    expand_notify(top)
    return {"id": fid, "name": name, "purpose": purpose, "trigger": trigger, "actions": top}


def _cut(expr, n=255):
    return f"if(greater(length({expr}), {n}), substring({expr}, 0, {n}), {expr})"


def _note_existing(lst, find, get_name, msg_expr):
    """기존 항목의 동기화 메모에 한 줄 덧붙이기(최신 값 읽기 → 모든 열 보존 갱신)."""
    src = f"body('{get_name}')"
    return {
        get_name: sp("Get item", lst, "기존 항목 최신 값 읽기", id=f"@first(body('{find}')?['value'])?['ID']"),
        f"Note_{get_name}": update_preserving(lst, f"@first(body('{find}')?['value'])?['ID']", src,
                                              {"SyncNote": append_note(src, msg_expr)}, "동기화 메모만 덧붙임(다른 열 보존)"),
    }


def _verify_unique(lst, created, cancel_status, label):
    """사후 중복 점검(P0-2): 동시성 1은 같은 흐름의 실행 순서만 보장한다. 다른 흐름·재전송·켜고 끄기 중 생긴 중복은
    만든 직후 같은 고유키를 다시 조회해 가장 먼저 만든 항목(가장 작은 ID)이 아니면 스스로 '취소'로 표시한다(삭제하지 않음)."""
    src = f"body('Get_{created}')"
    return {
        f"Recheck_{created}": sp("Get items", lst, "같은 고유키 항목 다시 조회(사후 중복 점검)",
                                 filter="SourceKey eq '@{replace(outputs('Key'), '''', '''''')}'", orderBy="ID asc", top=10),
        f"If_dup_{created}": iff(f"@and(greater(length(body('Recheck_{created}')?['value']), 1), "
                                 f"not(equals(first(body('Recheck_{created}')?['value'])?['ID'], body('{created}')?['ID'])))", {
            f"Get_{created}": sp("Get item", lst, "방금 만든 항목 최신 값", id=f"@body('{created}')?['ID']"),
            f"Cancel_{created}": update_preserving(lst, f"@body('{created}')?['ID']", src, {
                "Status/Value": cancel_status,
                "SyncNote": append_note(src, f"concat('같은 메일로 {label}이 중복 생성되어 자동 취소 — 원본 항목 ID ', "
                                             f"string(first(body('Recheck_{created}')?['value'])?['ID']))")},
                "중복 생성분을 취소로 표시(삭제하지 않음)"),
        }, note="먼저 만든 항목이 따로 있으면 이 항목을 취소 처리"),
    }


def flag_flow(fid, folder, action_type, prefix, default_due_days, route_decisions=False, name=None):
    """메일 플래그 → 할 일(·결정) 등록. 멱등(idempotent) 설계 — P0-2.

    Outlook 'When an email is flagged (V4)'는 이미 플래그된 메일이 바뀔 때마다(읽음·범주·이동·기한 변경 등) 다시 실행될 수 있다.
    그래서 '처음 보는 메일이면 만들고, 이미 있으면 정해진 규칙으로만 맞춘다'로 처리한다.
      고유키 SourceKey = internetMessageId(있으면) 또는 발신자|수신시각|제목 지문. 메일 ID(SourceMessageId)는 폴더 이동 시 바뀌므로 보조 키로만 쓴다.
      ① 새 메일 → 생성 후 사후 중복 점검
      ② 이미 있는 할 일이 열려 있음 → 플래그 기한이 바뀌었고 사람이 목록 기한을 손대지 않았으면 기한 갱신, 손댔으면 메모만.
         메일 ID·링크가 바뀌었으면(폴더 이동) 갱신. 변화가 없으면 아무것도 쓰지 않는다.
      ③ 이미 있는 할 일이 완료·취소 → 자동으로 다시 열지 않는다. 메모 + 본인 알림(하루 1회)으로 확인 요청
      ④ Outlook에서 플래그 완료 → 목록을 자동 완료하지 않는다. 메모 + 본인 알림으로 확인 요청
      ⑤ (F1) 할 일이 있는 메일에 '결정요청'·'결정' 범주가 붙음 → 결정 레지스터에 연결 기록을 새로 만들고 할 일은 유지
         결정 기록만 있는 메일에서 범주를 떼도 할 일을 새로 만들지 않는다(자동 삭제·취소 없음)
    """
    tr_due = t('flag/dueDateTime/dateTime')
    default_due = ("''" if default_due_days is None else
                   f"formatDateTime(addDays(convertFromUtc(utcNow(), 'Korea Standard Time'), {default_due_days}), 'yyyy-MM-dd')")
    raw_key = (f"if(empty({t('internetMessageId')}), concat('fp|', toLower(coalesce({t('from')}, '')), '|', "
               f"coalesce({t('receivedDateTime')}, ''), '|', coalesce({t('subject')}, '')), concat('imid|', {t('internetMessageId')}))")
    msg_id = f"replace({t('id')}, '''', '''''')"
    key_q = "replace(outputs('Key'), '''', '''''')"
    ex = "body('Get_existing_action')"
    plan = "outputs('Sync_plan')"
    norm = lambda e: f"if(empty({e}), '', convertFromUtc({e}, 'Korea Standard Time', 'yyyy-MM-dd'))"
    preview = _cut(f"coalesce({t('bodyPreview')}, '')", 1000)
    ex_due, ex_fdue = norm(f"{ex}?['DueDate']"), norm(f"{ex}?['FlagDue']")
    conflict = "concat('플래그 기한이 ', outputs('FlagDue'), '(으)로 바뀌었지만 목록 기한을 직접 정해 두어 유지함')"
    pre = {
        "Key": {"type": "Compose", "note": "중복 방지 고유키(255자 이내)", "inputs": f"@{{{_cut(raw_key)}}}"},
        "FlagDue": {"type": "Compose", "note": "플래그 기한(없으면 빈 값)",
                    "inputs": f"@{{if(empty({tr_due}), '', formatDateTime({tr_due}, 'yyyy-MM-dd'))}}"},
        "Today": {"type": "Compose", "note": "오늘(KST)", "inputs": f"@{{{TODAY}}}"},
    }
    create_action = {
        "Title_text": {"type": "Compose", "note": "제목 없음 대비 + 접두어",
                       "inputs": f"@{{concat('{prefix}', if(empty({t('subject')}), '(제목 없음)', {t('subject')}))}}"},
        "Due_value": {"type": "Compose", "note": "플래그 기한 → 없으면 기본 기한" + ("(없음)" if default_due_days is None else f"(+{default_due_days}일)"),
                      "inputs": f"@{{if(empty(outputs('FlagDue')), {default_due}, outputs('FlagDue'))}}"},
        "Create_action": sp("Create item", "ActionItems", "할 일 등록", item={
            "Title": "@{if(greater(length(outputs('Title_text')), 250), substring(outputs('Title_text'), 0, 250), outputs('Title_text'))}",
            "Owner/Claims": f"@{{{CFG}?['me']}}",
            "Status/Value": "미착수", "ActionType/Value": action_type, "Source/Value": "이메일",
            "CreatedVia/Value": "Outlook 플래그", "Priority/Value": "보통",
            "SourceLink": f"@{{coalesce({t('webLink')}, '')}}",
            "Evidence": f"@{{{preview}}}",
            "SourceMessageId": f"@{{{t('id')}}}", "SourceKey": "@{outputs('Key')}",
            "DueDate": "@if(empty(outputs('Due_value')), null, outputs('Due_value'))",
            "FlagDue": "@if(empty(outputs('Due_value')), null, outputs('Due_value'))"}),
        **_verify_unique("ActionItems", "Create_action", "취소", "할 일"),
    }
    move_due = f"and({plan}?['dueChanged'], not({plan}?['userMovedDue']))"
    sync_action = {
        "Get_existing_action": sp("Get item", "ActionItems", "기존 할 일 최신 값",
                                  id="@first(body('Find_existing')?['value'])?['ID']"),
        "Sync_plan": {"type": "Compose", "note": "무엇이 바뀌었는지 판정(쓰기 전)", "inputs": {
            "closed": f"@or(equals({ex}?['Status']?['Value'], '완료'), equals({ex}?['Status']?['Value'], '취소'))",
            "flagDone": f"@equals({t('flag/flagStatus')}, 'complete')",
            "dueChanged": f"@and(not(empty(outputs('FlagDue'))), not(equals(outputs('FlagDue'), {ex_fdue})))",
            "userMovedDue": f"@not(equals({ex_due}, {ex_fdue}))",
            "idChanged": f"@not(equals(coalesce({ex}?['SourceMessageId'], ''), {t('id')}))",
            "noticeToday": f"@contains(coalesce({ex}?['SyncNote'], ''), concat('[', outputs('Today'), ']'))"}},
        "If_closed": iff(f"@{plan}?['closed']", {
            "If_not_noticed": iff(f"@not({plan}?['noticeToday'])", {
                "Note_closed": update_preserving("ActionItems", f"@{ex}?['ID']", ex, {
                    "SyncNote": append_note(ex, "'완료·취소된 할 일의 메일이 다시 플래그되었거나 바뀜 — 다시 하려면 상태를 미착수로 바꾸세요'")},
                    "자동으로 다시 열지 않고 메모만"),
                "Tell_closed": msg_to_me(f"@{{concat('완료(또는 취소)한 할 일의 메일이 다시 플래그되었습니다. 다시 할 일이면 목록에서 상태를 바꾸세요: ', {ex}?['Title'])}}",
                                         subject="[P3 확인 요청] 완료한 할 일 재플래그"),
            }, note="하루 1회만 알림"),
        }, {
            "If_flag_done": iff(f"@and({plan}?['flagDone'], not({plan}?['noticeToday']))", {
                "Note_flag_done": update_preserving("ActionItems", f"@{ex}?['ID']", ex, {
                    "SyncNote": append_note(ex, "'Outlook에서 플래그 완료 — 목록도 완료로 바꿀지 확인하세요(자동 완료하지 않음)'")},
                    "자동 완료하지 않고 메모만"),
                "Tell_flag_done": msg_to_me(f"@{{concat('Outlook에서 플래그를 완료했습니다. 목록의 할 일도 완료로 바꾸세요: ', {ex}?['Title'], ' ', {CFG}?['links']?['myActions'])}}",
                                            subject="[P3 확인 요청] 플래그 완료"),
            }, {
                "If_changed": iff(f"@or({plan}?['dueChanged'], {plan}?['idChanged'])", {
                    "Update_sync": update_preserving("ActionItems", f"@{ex}?['ID']", ex, {
                        "DueDate": f"@if({move_due}, outputs('FlagDue'), {ex}?['DueDate'])",
                        "FlagDue": f"@if({plan}?['dueChanged'], outputs('FlagDue'), {ex}?['FlagDue'])",
                        "SourceMessageId": f"@{{{t('id')}}}",
                        "SourceLink": f"@{{coalesce({t('webLink')}, {ex}?['SourceLink'], '')}}",
                        "SyncNote": f"@if(and({plan}?['dueChanged'], {plan}?['userMovedDue']), "
                                    f"{note_expr(ex, conflict)}, {ex}?['SyncNote'])"},
                        "플래그 기한·메일 위치 변화만 반영(사람이 정한 기한은 유지)"),
                }, {"Stop_no_change": terminate("Succeeded", "NoChange", "이미 등록된 메일 — 바뀐 것 없음")},
                    note="바뀐 것이 없으면 아무것도 쓰지 않음"),
            }, note="플래그 완료 여부"),
        }, note="완료·취소된 할 일인지"),
    }
    acts = {
        "Check_message_id": iff(f"@empty({t('id')})",
                                {"Stop_no_id": terminate("Failed", "InputMissing", "메일 ID가 없어 중복 확인을 할 수 없습니다")},
                                note="메일 ID 누락 방어"),
        "Find_existing": sp("Get items", "ActionItems", "같은 메일로 만든 할 일 찾기(고유키 또는 예전 메일 ID)",
                            filter=f"SourceKey eq '@{{{key_q}}}' or SourceMessageId eq '@{{{msg_id}}}'", orderBy="ID asc", top=5),
    }
    has_action = "greater(length(body('Find_existing')?['value']), 0)"
    action_branch = {"If_has_action": iff(f"@{has_action}", sync_action,
                                          ({"If_has_decision": iff("@greater(length(body('Find_existing_decision')?['value']), 0)",
                                                                   {"Stop_decision_only": terminate("Succeeded", "DecisionExists", "결정 기록만 있는 메일 — 할 일을 새로 만들지 않음")},
                                                                   create_action, note="결정 기록만 있으면 할 일을 만들지 않음")}
                                           if route_decisions else create_action),
                                          note="이미 있는 할 일이면 맞추기, 없으면 만들기")}
    if not route_decisions:
        acts.update(action_branch)
    else:
        cats = f"coalesce({t('categories')}, createArray())"
        subj = f"if(empty({t('subject')}), '(제목 없음)', {t('subject')})"
        acts["Find_existing_decision"] = sp("Get items", "DecisionLog", "같은 메일로 만든 결정 기록 찾기",
                                            filter=f"SourceKey eq '@{{{key_q}}}' or SourceMessageId eq '@{{{msg_id}}}'", orderBy="ID asc", top=5)
        acts["Kind"] = {"type": "Compose", "note": "Outlook 범주로 종류 판별: '결정요청'/'결정' 범주가 있으면 결정 기록, 없으면 할 일",
                        "inputs": f"@{{if(contains({cats}, '결정요청'), '결정요청', if(contains({cats}, '결정'), '결정', '액션'))}}"}
        create_decision = {
            "Create_decision": sp("Create item", "DecisionLog", "결정요청 또는 '제안'으로 기록 — 자동화는 '확정'을 만들지 않는다(P0-6)", item={
                "Title": f"@{{{_cut(subj, 250)}}}",
                "DecisionText": f"@{{concat({subj}, ' / 원문 미리보기: ', {preview})}}",
                "Status/Value": "@{if(equals(outputs('Kind'), '결정요청'), '결정요청', '제안')}",
                "RequestedBy/Claims": f"@{{{CFG}?['me']}}",
                "SourceLink": f"@{{coalesce({t('webLink')}, '')}}", "CreatedVia/Value": "Outlook 플래그",
                "SourceMessageId": f"@{{{t('id')}}}", "SourceKey": "@{outputs('Key')}",
                "SyncNote": f"@{{if({has_action}, concat('[', outputs('Today'), '] 할 일 ID ', string(first(body('Find_existing')?['value'])?['ID']), '이(가) 있는 메일에 범주가 붙어 연결 기록'), '')}}"}),
            **_verify_unique("DecisionLog", "Create_decision", "취소", "결정 기록"),
            "If_linked_action": iff(f"@{has_action}",
                                    _note_existing("ActionItems", "Find_existing", "Get_linked_action",
                                                   "concat('범주가 ', outputs('Kind'), '(으)로 바뀌어 결정 레지스터에 연결 기록(항목 ID ', string(body('Create_decision')?['ID']), ') — 할 일은 그대로 둠')"),
                                    note="기존 할 일에 연결 메모"),
        }
        acts["If_action"] = iff("@equals(outputs('Kind'), '액션')", action_branch, {
            "If_has_decision_record": iff("@greater(length(body('Find_existing_decision')?['value']), 0)",
                                          {"Stop_decision_exists": terminate("Succeeded", "NoChange", "이미 결정 기록이 있는 메일")},
                                          create_decision, note="결정 기록은 메일당 1건"),
        }, note="종류별 분기: 할 일 / 결정요청·제안")
    extra = " 범주 '결정요청'은 결정요청, '결정'은 '제안'으로 DecisionLog에 기록(확정은 사람이 목록에서)." if route_decisions else ""
    return flow(
        fid, name or f"{fid} 메일 플래그({folder}) → {action_type if not route_decisions else '할 일·결정'} 등록",
        {"kind": "Outlook.WhenAnEmailIsFlaggedV4", "inputs": {"folder": folder}, "concurrency": 1},
        acts, pre=pre,
        purpose=f"Outlook '{folder}' 폴더에서 플래그한 메일을 등록. 같은 메일의 재실행(재플래그·범주·이동·기한 변경)은 규칙에 따라 맞추고 새로 만들지 않음.{extra}")


def numbering_flow(fid, lst, id_col, prefix, extra, extra_condition=None, extra_stop=None):
    """번호 부여·상태 변경 기록. 트리거 값이 아니라 Get item으로 읽은 최신 값을 기준으로, 모든 열을 보존해 갱신한다(P0-5).
    extra(src) → {열: 식}  : 최신 값(src)으로 계산하는 추가 갱신 열
    extra_condition(t)    : 트리거 조건에 OR로 더할 식(예: 확정 확인 필요 표시가 바뀌어야 할 때)
    extra_stop(src)       : '이미 처리됨' 판정에 AND로 더할 식"""
    src = "body('Fresh')"
    over = {id_col: (f"@{{if(empty({src}?['{id_col}']), concat('{prefix}-', convertFromUtc({src}?['Created'], 'Korea Standard Time', 'yyyy'), "
                     f"'-', formatNumber({src}?['ID'], '00000')), {src}?['{id_col}'])}}")}
    over.update(extra(src))
    over["PrevStatus"] = f"@{{{src}?['Status']?['Value']}}"
    cond = f"or(empty({t(id_col)}), not(equals({t('Status/Value')}, coalesce({t('PrevStatus')}, ''))))"
    if extra_condition:
        cond = f"or({cond}, {extra_condition})"
    done = f"and(not(empty({src}?['{id_col}'])), equals({src}?['Status']?['Value'], coalesce({src}?['PrevStatus'], '')))"
    if extra_stop:
        done = f"and({done}, {extra_stop(src)})"
    return flow(
        fid, f"{fid} {lst} 번호·상태 기록",
        {"kind": "SharePoint.WhenAnItemIsCreatedOrModified", "inputs": {"site": SITE, "list": lst},
         "conditions": [f"@{cond}"]},
        {"Fresh": sp("Get item", lst, "최신 값 읽기(트리거 시점 값은 오래됐을 수 있음)", id=f"@{t('ID')}"),
         "If_handled": iff(f"@{done}", {"Stop_handled": terminate("Succeeded", "AlreadyHandled", "다른 실행이 이미 처리함")},
                           note="중복·지연 실행 방어"),
         "Update_item": update_preserving(lst, f"@{t('ID')}", src, over,
                                          "번호 부여·상태 변경 기록(모든 열 보존). PrevStatus를 현재 상태로 맞춰 자기 재실행을 막는다")},
        purpose=f"{lst} 새 항목에 {prefix}-연도-번호 부여, 상태 변경 시각 기록. 트리거 조건 + 최신 값 재확인으로 자기 수정·중복 실행 차단.")


def confirmation_gap(get):
    """DecisionLog 상태가 '확정'인데 비어 있는 확인 항목(결정권자·근거·후속 조치) — P0-6. get(열) → 식"""
    return (f"if(equals({get('Status')}, '확정'), trim(concat(if(empty({get('Decider')}), '결정권자 ', ''), "
            f"if(empty({get('Rationale')}), '근거 ', ''), if(empty({get('FollowUps')}), '후속조치 ', ''))), '')")


def build() -> list[dict]:
    flows = []
    flows.append(flag_flow("P3P-F1", "Inbox", "실행", "[메일] ", None, route_decisions=True))
    flows.append(flag_flow("P3P-F2", "Sent Items", "회신대기", "[회신대기] ", 3))

    flows.append(numbering_flow(
        "P3P-F3", "ActionItems", "ActionID", "ACT",
        lambda src: {"CompletedAt": f"@if(equals({src}?['Status']?['Value'], '완료'), coalesce({src}?['CompletedAt'], utcNow()), null)"}))
    today = TODAY
    tg = lambda c: t(f"{c}/Value") if c == "Status" else t(c)

    def sg(src):
        return lambda c: f"{src}?['{c}']?['Value']" if c == "Status" else f"{src}?['{c}']"

    flows.append(numbering_flow(
        "P3P-F4", "DecisionLog", "DecisionID", "DEC",
        lambda src: {
            "DecidedAt": f"@if(and(equals({src}?['Status']?['Value'], '확정'), empty({src}?['DecidedAt'])), {today}, {src}?['DecidedAt'])",
            "RequestedAt": f"@if(and(equals({src}?['Status']?['Value'], '결정요청'), empty({src}?['RequestedAt'])), {today}, {src}?['RequestedAt'])",
            "ConfirmationGap": "@{" + confirmation_gap(sg(src)) + "}"},
        extra_condition=f"not(equals(coalesce({t('ConfirmationGap')}, ''), {confirmation_gap(tg)}))",
        extra_stop=lambda src: f"equals(coalesce({src}?['ConfirmationGap'], ''), {confirmation_gap(sg(src))})"))

    co = "triggerBody()?['cardOutputs']"
    inp = "outputs('Inputs')"
    flows.append(flow(
        "P3P-F5", "P3P-F5 Teams 메시지 → 결정·액션 기록",
        {"kind": "Teams.ForASelectedMessage", "inputs": {"inputCard": "../automation_assets/cards/capture_decision_action.json"}},
        {
            "Content": {"type": "Compose", "note": "메시지 본문 앞 1,000자(근거로 저장)",
                        "inputs": "@{if(greater(length(coalesce(triggerBody()?['messagePayload']?['body']?['content'], '')), 1000), substring(triggerBody()?['messagePayload']?['body']?['content'], 0, 1000), coalesce(triggerBody()?['messagePayload']?['body']?['content'], ''))}"},
            "Inputs": {"type": "Compose", "note": "카드 입력값 정리(담당자 비면 나)", "inputs": {
                "kind": f"@{{coalesce({co}?['kind'], '액션')}}",
                "title": f"@{{trim(coalesce({co}?['title'], ''))}}",
                "owner": f"@{{toLower(if(empty({co}?['ownerEmail']), {CFG}?['me'], trim({co}?['ownerEmail'])))}}",
                "due": f"@{{coalesce({co}?['dueDate'], '')}}",
                "decisionId": f"@{{trim(coalesce({co}?['decisionId'], ''))}}",
                "messageId": "@{coalesce(triggerBody()?['messagePayload']?['id'], '')}",
                "link": "@{coalesce(triggerBody()?['linkToMessage'], '')}"}},
            "Validate_inputs": iff(f"@or(empty({inp}?['title']), empty({inp}?['messageId']))", {
                "Tell_missing": msg_to_me("기록하지 않았습니다: 제목 또는 메시지 정보가 비어 있습니다."),
                "Stop_missing": terminate("Failed", "InputMissing", "제목 또는 메시지 ID 누락")}, note="데이터 누락 방어"),
            "Check_owner": {"type": "Connector", "connector": "Office 365 Users", "operation": "Get user profile (V2)",
                            "inputs": {"user": f"@{{{inp}?['owner']}}"}, "note": "담당자 이메일이 실제 사용자인지 확인"},
            "If_action": iff(f"@equals({inp}?['kind'], '액션')", {
                "Find_dup_action": sp("Get items", "ActionItems", "같은 메시지 중복 확인",
                                      filter=f"SourceMessageId eq '@{{replace({inp}?['messageId'], '''', '''''')}}'", top=1),
                "If_dup_action": iff("@greater(length(body('Find_dup_action')?['value']), 0)", {
                    "Tell_dup_action": msg_to_me("이미 기록된 메시지입니다(중복 생성 안 함)."),
                    "Stop_dup_action": terminate("Succeeded", "Duplicate", "이미 기록됨")}),
                "Create_action": sp("Create item", "ActionItems", "액션 등록", item={
                    "Title": f"@{{{inp}?['title']}}", "Owner/Claims": f"@{{{inp}?['owner']}}",
                    "DueDate": f"@if(empty({inp}?['due']), null, {inp}?['due'])",
                    "Status/Value": "미착수", "ActionType/Value": "실행", "Source/Value": "Teams 메시지",
                    "CreatedVia/Value": "Teams 메시지", "Priority/Value": "보통",
                    "SourceLink": f"@{{{inp}?['link']}}", "Evidence": "@{outputs('Content')}",
                    "DecisionID": f"@{{{inp}?['decisionId']}}", "SourceMessageId": f"@{{{inp}?['messageId']}}"}),
            }, {
                "Find_dup_decision": sp("Get items", "DecisionLog", "같은 메시지 중복 확인",
                                        filter=f"SourceMessageId eq '@{{replace({inp}?['messageId'], '''', '''''')}}'", top=1),
                "If_dup_decision": iff("@greater(length(body('Find_dup_decision')?['value']), 0)", {
                    "Tell_dup_decision": msg_to_me("이미 기록된 메시지입니다(중복 생성 안 함)."),
                    "Stop_dup_decision": terminate("Succeeded", "Duplicate", "이미 기록됨")}),
                "Create_decision": sp("Create item", "DecisionLog", "결정요청 또는 '제안'으로 기록(확정은 사람이 목록에서 — P0-6)", item={
                    "Title": f"@{{{inp}?['title']}}",
                    "DecisionText": f"@{{concat({inp}?['title'], ' / 원문: ', outputs('Content'))}}",
                    "Status/Value": f"@{{if(equals({inp}?['kind'], '결정요청'), '결정요청', '제안')}}",
                    "Decider/Claims": f"@{{{inp}?['owner']}}", "RequestedBy/Claims": f"@{{{CFG}?['me']}}",
                    "SourceLink": f"@{{{inp}?['link']}}", "CreatedVia/Value": "Teams 메시지",
                    "SourceMessageId": f"@{{{inp}?['messageId']}}"}),
            }, note="종류별 분기: 액션 / 결정·결정요청"),
            "Tell_done": msg_to_me(f"@{{concat('기록됨(', if(equals({inp}?['kind'], '결정'), '결정 → 제안 상태, 확정은 목록에서', {inp}?['kind']), '): ', {inp}?['title'], ' — 번호는 잠시 후 목록에서 확인')}}"),
        },
        purpose="Teams 메시지 '추가 작업'에서 결정·결정요청·액션을 기록. 같은 메시지 두 번 기록 방지, 담당자 실존 확인."))

    pre_brief = {
        "Today": {"type": "Compose", "inputs": f"@{{{today}}}", "note": "오늘(KST)"},
        "DayStartUtc": {"type": "Compose", "inputs": "@{convertToUtc(concat(outputs('Today'), 'T00:00:00'), 'Korea Standard Time')}",
                        "note": "오늘 0시(KST)를 UTC로"},
    }
    flows.append(flow(
        "P3P-F6", "P3P-F6 아침 브리핑",
        {"kind": "Recurrence", "recurrence": {"frequency": "Week", "interval": 1, "timeZone": "Korea Standard Time",
                                             "schedule": {"weekDays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                                                          "hours": [7], "minutes": [40]}}},
        {
            "Get_holidays": sp("Get items", "Holidays", "휴무일", top=500),
            "Get_events": {"type": "Connector", "connector": "Office 365 Outlook", "operation": "Get calendar view of events (V3)",
                           "inputs": {"calendarId": "Calendar", "startTime": "@{outputs('DayStartUtc')}",
                                      "endTime": "@{addDays(outputs('DayStartUtc'), 1)}"}, "note": "오늘 일정"},
            "Get_my_actions": sp("Get items", "ActionItems", "내 미결 액션",
                                 filter=f"Owner/EMail eq '@{{{CFG}?['me']}}' and (Status eq '미착수' or Status eq '진행중')", top=500),
            "Get_my_decisions": sp("Get items", "DecisionLog", "내가 결정할 대기 건 + 내가 확정해야 할 제안",
                                   filter=f"(Status eq '결정요청' and Decider/EMail eq '@{{{CFG}?['me']}}') or (Status eq '제안' and Author/EMail eq '@{{{CFG}?['me']}}')",
                                   top=200),
            "Run_brief": script("BuildDailyBrief", {
                "meEmail": f"@{{{CFG}?['me']}}", "todayKst": "@{outputs('Today')}",
                "eventsJson": "@{string(body('Get_events')?['value'])}",
                "actionsJson": "@{string(body('Get_my_actions')?['value'])}",
                "decisionsJson": "@{string(body('Get_my_decisions')?['value'])}",
                "requestsJson": "[]", "holidaysJson": "@{string(body('Get_holidays')?['value'])}",
                "linksJson": f"@{{string({CFG}?['links'])}}"}, "점수 계산·카드 생성(Office Scripts)"),
            "If_skip": iff("@equals(body('Run_brief')?['result']?['skip'], true)",
                           {"Stop_skip": terminate("Succeeded", "Skip", "@{body('Run_brief')?['result']?['reason']}")},
                           note="주말·휴무일이면 게시 안 함"),
            "Post_card": card_to_me("@{body('Run_brief')?['result']?['cardJson']}", "@{body('Run_brief')?['result']?['htmlSummary']}",
                                    "@{concat('[아침 브리핑] ', outputs('Today'))}"),
        },
        pre=pre_brief,
        catch_extra={"If_teams_failed": iff(f"@and(equals(first(body('Failed_actions'))?['name'], 'Post_card'), equals({CFG}?['channel'], 'teams'))", {
            "Email_fallback": {"type": "Connector", "connector": "Office 365 Outlook", "operation": "Send an email (V2)",
                               "inputs": {"to": f"@{{{CFG}?['me']}}", "subject": "[아침 브리핑] Teams 게시 실패 — 메일로 대체",
                                          "body": "@{body('Run_brief')?['result']?['htmlSummary']}"},
                               "note": "Teams 카드 실패 시 본인 메일로 대체 발송"}}, note="Teams 실패 시 대체")},
        purpose="평일 07:40 본인에게 '오늘 먼저 처리할 5가지' 카드. 계산은 Office Scripts, Teams 실패 시 본인 메일로 대체."))

    dg = "items('For_each_digest')"
    flows.append(flow(
        "P3P-F7", "P3P-F7 액션 리마인더(담당자별 하루 1장)",
        {"kind": "Recurrence", "recurrence": {"frequency": "Week", "interval": 1, "timeZone": "Korea Standard Time",
                                             "schedule": {"weekDays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                                                          "hours": [8], "minutes": [30]}}},
        {
            "Get_holidays": sp("Get items", "Holidays", "휴무일", top=500),
            "Get_due_actions": sp("Get items", "ActionItems", "내일까지 기한인 미결 액션",
                                  filter="(Status eq '미착수' or Status eq '진행중') and DueDate le '@{addDays(outputs('Today'), 1, 'yyyy-MM-dd')}'",
                                  top=2000),
            "Run_digest": script("BuildReminderDigest", {
                "todayKst": "@{outputs('Today')}", "actionsJson": "@{string(body('Get_due_actions')?['value'])}",
                "holidaysJson": "@{string(body('Get_holidays')?['value'])}", "viewUrl": f"@{{{CFG}?['links']?['myActions']}}"},
                "담당자별 카드 생성(Office Scripts)"),
            "If_skip": iff("@equals(body('Run_digest')?['result']?['skip'], true)",
                           {"Stop_skip": terminate("Succeeded", "Skip", "@{body('Run_digest')?['result']?['reason']}")}),
            "For_each_digest": {"type": "Foreach", "foreach": "@body('Run_digest')?['result']?['digests']",
                                "note": "담당자별 반복(동시성 1)", "actions": chain({
                "If_allowed": iff(f"@or(not({CFG}?['prototypeMode']), equals(toLower({dg}?['ownerEmail']), toLower({CFG}?['me'])))", {
                    "Post_digest": card_to_me(f"@{{{dg}?['cardJson']}}", f"@{{{dg}?['htmlSummary']}}",
                                              "@{concat('[액션 리마인더] ', outputs('Today'))}",
                                              recipient=f"@{{{dg}?['ownerEmail']}}", note="담당자에게 하루 1장"),
                    "For_each_item": {"type": "Foreach", "foreach": f"@{dg}?['itemIds']", "note": "알린 항목 기록", "actions": chain({
                        "Get_action": sp("Get item", "ActionItems", "현재 값 읽기(Update 필수 입력용)", id="@items('For_each_item')"),
                        "Mark_reminded": update_preserving("ActionItems", "@items('For_each_item')", "body('Get_action')", {
                            "ReminderCount": "@add(coalesce(body('Get_action')?['ReminderCount'], 0), 1)",
                            "LastRemindedAt": "@{utcNow()}"}, "리마인더 횟수·시각만 갱신(모든 열 보존)"),
                    })},
                }, {"Remember_skipped": {"type": "AppendToArrayVariable", "inputs": {"name": "varSkipped", "value": f"@{dg}?['ownerEmail']"}}},
                    note="프로토타입 모드에서는 본인에게만 발송")})},
            "If_any_skipped": iff("@greater(length(variables('varSkipped')), 0)", {
                "Tell_skipped": msg_to_me("@{concat('프로토타입 모드: 다른 담당자 ', string(length(variables('varSkipped'))), '명에게는 발송하지 않았습니다.')}")}),
        },
        pre={**pre_brief, "Init_skipped": {"type": "InitializeVariable", "inputs": {"name": "varSkipped", "type": "Array", "value": []}}},
        purpose="평일 08:30 기한 D-1·당일·초과 액션을 담당자별 1장으로 알림. 같은 날 재알림 없음. 프로토타입 모드는 본인에게만."))

    ci = "items('Create_candidates')"
    g = "body('Run_guard')?['result']"
    flows.append(flow(
        "P3P-F8", "P3P-F8 Copilot 추출 결과 검증 → 후보 생성",
        {"kind": "SharePoint.WhenAnItemIsCreatedOrModified", "inputs": {"site": SITE, "list": "MeetingIntake"},
         "conditions": [f"@or(equals({t('Status/Value')}, '접수'), equals({t('Status/Value')}, '재검증요청'))"]},
        {
            "Get_intake": sp("Get item", "MeetingIntake", "접수 항목 최신 값", id=f"@{t('ID')}"),
            "If_already": iff("@not(or(equals(body('Get_intake')?['Status']?['Value'], '접수'), equals(body('Get_intake')?['Status']?['Value'], '재검증요청')))",
                              {"Stop_already": terminate("Succeeded", "AlreadyHandled", "이미 처리된 접수")}, note="중복·지연 실행 방어"),
            "Get_roster": sp("Get items", "TeamRoster", "팀 명부(담당자 매핑 근거)", top=500),
            "Run_guard": script("GuardExtraction", {
                "transcript": "@{body('Get_intake')?['Transcript']}", "rosterJson": "@{string(body('Get_roster')?['value'])}",
                "extractionJson": "@{body('Get_intake')?['ExtractionJson']}",
                "meetingDate": f"@{{formatDateTime({t('MeetingDate')}, 'yyyy-MM-dd')}}"}, "G1~G6 검증(Office Scripts)"),
            "Get_old_candidates": sp("Get items", "ActionCandidates", "재검증 시 이전 '제안' 후보",
                                     filter=f"IntakeID eq @{{{t('ID')}}} and Status eq '제안'", top=500),
            "Supersede_old": {"type": "Foreach", "foreach": "@body('Get_old_candidates')?['value']",
                              "note": "이전 후보는 삭제하지 않고 '기각' 처리(이력 보존)", "actions": {
                "Mark_superseded": update_preserving("ActionCandidates", "@items('Supersede_old')?['ID']", "items('Supersede_old')",
                                                     {"Status/Value": "기각"}, "기각(다른 열 보존)", runAfter={})}},
            "If_parsed": iff(f"@equals({g}?['ok'], true)", {
                "Create_candidates": {"type": "Foreach", "foreach": f"@{g}?['candidates']", "note": "후보 1건 = 1행", "actions": {
                    "Create_candidate": sp("Create item", "ActionCandidates", "후보 등록(상태: 제안)", runAfter={}, item={
                        "Title": f"@{{if(greater(length({ci}?['title']), 250), substring({ci}?['title'], 0, 250), {ci}?['title'])}}",
                        "Kind/Value": f"@{{{ci}?['kind']}}", "IntakeID": f"@{t('ID')}", "Ref": f"@{ci}?['ref']",
                        "MeetingName": f"@{{{t('Title')}}}", "MeetingDate": f"@{{formatDateTime({t('MeetingDate')}, 'yyyy-MM-dd')}}",
                        "OwnerName": f"@{{{ci}?['ownerName']}}", "OwnerEmail": f"@{{{ci}?['ownerEmail']}}",
                        "DueDate": f"@if(empty({ci}?['dueDate']), null, {ci}?['dueDate'])",
                        "Evidence": f"@{{{ci}?['evidence']}}", "Verdict/Value": f"@{{{ci}?['verdict']}}",
                        "Reasons": f"@{{{ci}?['reasons']}}", "Status/Value": "제안"})}},
                "Mark_intake_done": update_preserving("MeetingIntake", f"@{t('ID')}", "body('Get_intake')", {
                    "Status/Value": "검증완료",
                    "RecommendedCount": f"@{g}?['recommendedCount']", "ReviewCount": f"@{g}?['reviewCount']",
                    "ResultSummary": f"@{{concat('추천 ', string({g}?['recommendedCount']), '건 · 검토필요 ', string({g}?['reviewCount']), '건', if(empty({g}?['schemaErrors']), '', concat(' · 형식 오류: ', join({g}?['schemaErrors'], '; '))))}}",
                    "ProcessedAt": "@{utcNow()}"}, "접수 완료 표시(자기 재실행 차단, 원문 보존)"),
                "Tell_candidates": msg_to_me(f"@{{concat('회의 \"', {t('Title')}, '\" 후보 ', string(length({g}?['candidates'])), '건(추천 ', string({g}?['recommendedCount']), ') — 확인 후 승인하세요: ', {CFG}?['links']?['candidates'])}}"),
            }, {
                "Mark_intake_error": update_preserving("MeetingIntake", f"@{t('ID')}", "body('Get_intake')", {
                    "Status/Value": "오류", "ResultSummary": f"@{{{g}?['parseError']}}", "ProcessedAt": "@{utcNow()}"}, "오류 표시(원문 보존)"),
                "Tell_parse_error": msg_to_me(f"@{{concat('회의 \"', {t('Title')}, '\" 추출 결과를 읽지 못했습니다: ', {g}?['parseError'])}}"),
            }, note="JSON 해석 성공 여부"),
        },
        purpose="회의 추출 접수(MeetingIntake)에 Copilot 결과를 붙여넣으면 가드 검증 후 후보를 만든다. 등록은 하지 않는다."))

    rc = "body('Recheck')"
    flows.append(flow(
        "P3P-F9", "P3P-F9 승인된 후보 → 결정·액션 등록",
        {"kind": "SharePoint.WhenAnItemIsCreatedOrModified", "inputs": {"site": SITE, "list": "ActionCandidates"},
         "conditions": [f"@and(equals({t('Status/Value')}, '승인'), empty({t('CreatedItemID')}))"], "concurrency": 1},
        {
            "Recheck": sp("Get item", "ActionCandidates", "최신 값 재확인(동시 수정·중복 실행 방어)", id=f"@{t('ID')}"),
            "If_already": iff(f"@not(and(equals({rc}?['Status']?['Value'], '승인'), empty({rc}?['CreatedItemID'])))",
                              {"Stop_already": terminate("Succeeded", "AlreadyHandled", "이미 처리된 후보")}),
            "If_kind_action": iff(f"@equals({rc}?['Kind']?['Value'], '액션')", {
                "Validate_owner": {"type": "Connector", "connector": "Office 365 Users", "operation": "Get user profile (V2)",
                                   "inputs": {"user": f"@{{{rc}?['OwnerEmail']}}"}, "note": "담당자 실존 확인(비어 있으면 실패)"},
                "Create_action": sp("Create item", "ActionItems", "액션 등록", item={
                    "Title": f"@{{{rc}?['Title']}}", "Owner/Claims": "@{body('Validate_owner')?['mail']}",
                    "DueDate": f"@if(empty({rc}?['DueDate']), null, {rc}?['DueDate'])",
                    "Status/Value": "미착수", "ActionType/Value": "실행", "Source/Value": "회의", "Priority/Value": "보통",
                    "Evidence": f"@{{{rc}?['Evidence']}}", "CreatedVia/Value": "AI 제안 승인"}),
                "Mark_done_action": update_preserving("ActionCandidates", f"@{t('ID')}", rc, {
                    "Status/Value": "등록완료", "CreatedItemID": "@{string(body('Create_action')?['ID'])}"}, "등록완료 표시(다른 열 보존)"),
            }, {
                "Create_decision": sp("Create item", "DecisionLog", "AI 추출 결정은 '제안'으로 등록 — 결정권자·확정일은 비워 두고 사람이 확정(P0-6)", item={
                    "Title": f"@{{{rc}?['Title']}}",
                    "DecisionText": f"@{{concat({rc}?['Title'], ' / 회의록 근거: ', coalesce({rc}?['Evidence'], ''), if(empty({rc}?['OwnerName']), '', concat(' / AI 추정 관련자: ', {rc}?['OwnerName'], '(미확인)')))}}",
                    "Status/Value": "제안", "MeetingName": f"@{{coalesce({rc}?['MeetingName'], '')}}",
                    "MeetingDate": f"@if(empty({rc}?['MeetingDate']), null, {rc}?['MeetingDate'])",
                    "CreatedVia/Value": "AI 제안 승인"}),
                "Mark_done_decision": update_preserving("ActionCandidates", f"@{t('ID')}", rc, {
                    "Status/Value": "등록완료", "CreatedItemID": "@{string(body('Create_decision')?['ID'])}"}, "등록완료 표시(다른 열 보존)"),
            }, note="종류별 등록"),
        },
        catch_extra={"Get_candidate_now": sp("Get item", "ActionCandidates", "후보 최신 값", id=f"@{t('ID')}"),
                     "Mark_candidate_error": update_preserving("ActionCandidates", f"@{t('ID')}", "body('Get_candidate_now')", {
            "Status/Value": "오류",
            "Reasons": "@{concat(coalesce(body('Get_candidate_now')?['Reasons'], ''), ' / 등록 실패: ', outputs('Error_text'))}"},
            "후보에 오류 표시(사용자가 고쳐 다시 승인, 다른 열 보존)", runAfter={"Get_candidate_now": ["Succeeded"]})},
        purpose="사람이 ActionCandidates에서 '승인'으로 바꾼 후보만 등록. 최신 값 재확인으로 중복 등록 방지, 실패 시 후보에 사유 표시."))

    # ---------------- 추가 기능(기록 2026-10-25): 02_ADDITIONAL_AUTOMATIONS.md ----------------
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    msg_q = f"replace({t('id')}, '''', '''''')"
    recv_day = f"convertFromUtc({t('receivedDateTime')}, 'Korea Standard Time', 'yyyy-MM-dd')"
    flows.append(flow(
        "P3P-F10", "P3P-F10 공장 자료 메일 → 첨부 자동 저장·수신 대장",
        {"kind": "Outlook.WhenANewEmailArrivesV3",
         "inputs": {"folder": "Inbox", "includeAttachments": True, "onlyWithAttachments": True}, "concurrency": 1},
        {
            "Get_senders": sp("Get items", "FactorySenders", "공장 발신자 설정", top=500),
            "Match_sender": {"type": "FilterArray", "note": "발신자가 공장 발신자 목록에 있는지",
                             "inputs": {"from": "@body('Get_senders')?['value']",
                                        "where": f"@contains(toLower(coalesce({t('from')}, '')), toLower(item()?['SenderPattern']))"}},
            "If_not_factory": iff("@equals(length(body('Match_sender')), 0)",
                                  {"Stop_not_factory": terminate("Succeeded", "NotFactory", "공장 발신 메일 아님")},
                                  note="공장 메일이 아니면 즉시 종료(대부분의 메일은 여기서 끝)"),
            "Find_existing": sp("Get items", "FactoryInbox", "같은 메일 중복 저장 방지",
                                filter=f"SourceMessageId eq '@{{{msg_q}}}'", top=1),
            "If_duplicate": iff("@greater(length(body('Find_existing')?['value']), 0)",
                                {"Stop_duplicate": terminate("Succeeded", "Duplicate", "이미 저장된 메일")}),
            "Excel_files": {"type": "FilterArray", "note": "Excel·CSV 첨부만 저장",
                            "inputs": {"from": f"@coalesce({t('attachments')}, createArray())",
                                       "where": "@or(endsWith(item()?['name'], '.xlsx'), endsWith(item()?['name'], '.xlsm'), endsWith(item()?['name'], '.xls'), endsWith(item()?['name'], '.csv'))"}},
            "If_no_excel": iff("@equals(length(body('Excel_files')), 0)",
                               {"Stop_no_excel": terminate("Succeeded", "NoExcel", "Excel·CSV 첨부 없음")}),
            "Folder": {"type": "Compose", "note": "저장 폴더: 기본 폴더/공장코드/수신일(KST)",
                       "inputs": f"@{{concat({CFG}?['factoryFolder'], '/', first(body('Match_sender'))?['PlantCode'], '/', {recv_day})}}"},
            "Save_files": {"type": "Foreach", "foreach": "@body('Excel_files')", "note": "첨부마다 저장(파일 이름 앞에 수신 시각)", "actions": {
                "Create_file": {"type": "Connector", "connector": "OneDrive for Business", "operation": "Create file",
                                "note": "OneDrive에 저장", "runAfter": {},
                                "inputs": {"folderPath": "@{outputs('Folder')}",
                                           "name": f"@{{concat(convertFromUtc({t('receivedDateTime')}, 'Korea Standard Time', 'HHmm'), '_', items('Save_files')?['name'])}}",
                                           "body": "@base64ToBinary(items('Save_files')?['contentBytes'])"}}}},
            "File_names": {"type": "Select", "note": "저장한 파일 이름 목록",
                           "inputs": {"from": "@body('Excel_files')", "select": "@item()?['name']"}},
            "Log_inbox": sp("Create item", "FactoryInbox", "수신 대장 기록", item={
                "Title": f"@{{if(empty({t('subject')}), '(제목 없음)', if(greater(length({t('subject')}), 250), substring({t('subject')}, 0, 250), {t('subject')}))}}",
                "PlantCode": "@{first(body('Match_sender'))?['PlantCode']}",
                "Sender": f"@{{coalesce({t('from')}, '')}}",
                "ReceivedAt": f"@{{{t('receivedDateTime')}}}",
                "FileCount": "@length(body('Excel_files'))",
                "FileNames": "@{join(body('File_names'), ', ')}",
                "SavedFolder": "@{outputs('Folder')}",
                "SourceMessageId": f"@{{{t('id')}}}"}),
        },
        purpose="공장 발신자(FactorySenders)의 첨부 메일이 오면 Excel·CSV 첨부를 OneDrive '공장코드/날짜' 폴더에 자동 저장하고 수신 대장에 기록. 다운로드·이름 바꾸기·폴더 정리·수신 확인 제거, 수신 패턴 자동 축적."))

    pre_day = {"Today": {"type": "Compose", "inputs": f"@{{{today}}}", "note": "오늘(KST)"},
               "DayStartUtc": {"type": "Compose", "inputs": "@{convertToUtc(concat(outputs('Today'), 'T00:00:00'), 'Korea Standard Time')}",
                               "note": "오늘 0시(KST)를 UTC로"}}
    prep = "body('Run_prep')?['result']"
    flows.append(flow(
        "P3P-F11", "P3P-F11 다음 영업일 회의 준비 메일",
        {"kind": "Recurrence", "recurrence": {"frequency": "Week", "interval": 1, "timeZone": "Korea Standard Time",
                                             "schedule": {"weekDays": weekdays, "hours": [16], "minutes": [30]}}},
        {
            "Get_holidays": sp("Get items", "Holidays", "휴무일", top=500),
            "Get_events": {"type": "Connector", "connector": "Office 365 Outlook", "operation": "Get calendar view of events (V3)",
                           "inputs": {"calendarId": "Calendar", "startTime": "@{addDays(outputs('DayStartUtc'), 1)}",
                                      "endTime": "@{addDays(outputs('DayStartUtc'), 5)}"},
                           "note": "내일~4일 뒤 일정(주말·휴무 건너 다음 영업일을 스크립트가 고름)"},
            "Get_open_actions": sp("Get items", "ActionItems", "미결 할 일(전체 담당자)",
                                   filter="Status eq '미착수' or Status eq '진행중'", top=2000),
            "Get_decisions": sp("Get items", "DecisionLog", "결정 대기 + 최근 14일 확정",
                                filter="Status eq '결정요청' or (Status eq '확정' and DecidedAt ge '@{addDays(outputs('Today'), -14, 'yyyy-MM-dd')}')",
                                top=1000),
            "Run_prep": script("BuildMeetingPrep", {
                "meEmail": f"@{{{CFG}?['me']}}", "todayKst": "@{outputs('Today')}",
                "eventsJson": "@{string(body('Get_events')?['value'])}",
                "actionsJson": "@{string(body('Get_open_actions')?['value'])}",
                "decisionsJson": "@{string(body('Get_decisions')?['value'])}",
                "holidaysJson": "@{string(body('Get_holidays')?['value'])}"}, "회의별 참석자 기준 자료 정리(Office Scripts)"),
            "If_skip": iff(f"@equals({prep}?['skip'], true)",
                           {"Stop_skip": terminate("Succeeded", "Skip", f"@{{{prep}?['reason']}}")},
                           note="회의가 없거나 휴무일이면 보내지 않음"),
            "Send_prep": msg_to_me(f"@{{{prep}?['htmlSummary']}}",
                                   subject=f"@{{concat('[회의 준비] ', {prep}?['targetDate'], ' · ', string({prep}?['meetingCount']), '건')}}"),
        },
        pre=pre_day,
        purpose="평일 16:30, 다음 영업일 회의마다 참석자의 미결 할 일·결정 대기·최근 결정과 안건 제안을 본인에게 메일 1통으로."))

    wk = "body('Run_weekly')?['result']"
    flows.append(flow(
        "P3P-F12", "P3P-F12 주간 정리(주간보고 초안)",
        {"kind": "Recurrence", "recurrence": {"frequency": "Week", "interval": 1, "timeZone": "Korea Standard Time",
                                             "schedule": {"weekDays": ["Friday"], "hours": [16], "minutes": [0]}}},
        {
            "Get_my_actions": sp("Get items", "ActionItems", "내 미결 + 최근 35일 변경",
                                 filter=f"Owner/EMail eq '@{{{CFG}?['me']}}' and (Status eq '미착수' or Status eq '진행중' or Modified ge '@{{outputs('Since')}}')",
                                 top=2000),
            "Get_decisions": sp("Get items", "DecisionLog", "결정 대기 + 최근 35일 변경",
                                filter="Status eq '결정요청' or Modified ge '@{outputs('Since')}'", top=1000),
            "Get_inbox": sp("Get items", "FactoryInbox", "최근 35일 공장 자료 수신", filter="ReceivedAt ge '@{outputs('Since')}'", top=2000),
            "Run_weekly": script("BuildWeeklyDigest", {
                "meEmail": f"@{{{CFG}?['me']}}", "todayKst": "@{outputs('Today')}",
                "actionsJson": "@{string(body('Get_my_actions')?['value'])}",
                "decisionsJson": "@{string(body('Get_decisions')?['value'])}",
                "inboxJson": "@{string(body('Get_inbox')?['value'])}"}, "주간 집계·초안 생성(Office Scripts)"),
            "Send_weekly": msg_to_me(f"@{{{wk}?['htmlSummary']}}", subject=f"@{{concat('[주간 정리] ', {wk}?['week'], ' 초안')}}"),
        },
        pre={"Today": pre_day["Today"], "Since": {"type": "Compose", "inputs": "@{addDays(outputs('Today'), -35, 'yyyy-MM-dd')}",
                                                  "note": "조회 시작일(35일 전)"}},
        purpose="금요일 16:00 이번 주 완료·신규·기한초과·결정·회신 대기·공장 자료 수신 패턴을 자동 집계한 주간보고 초안을 본인에게."))

    rk = "body('Recheck')"
    hint = "body('Run_hint')?['result']"
    flows.append(flow(
        "P3P-F13", "P3P-F13 메일 문구로 기한 자동 제안",
        {"kind": "SharePoint.WhenAnItemIsCreatedOrModified", "inputs": {"site": SITE, "list": "ActionItems"},
         "conditions": [f"@and(not(empty({t('ActionID')})), empty({t('DueDate')}), empty({t('DueHintChecked')}), equals({t('CreatedVia/Value')}, 'Outlook 플래그'))"]},
        {
            "Recheck": sp("Get item", "ActionItems", "최신 값 재확인(중복 실행 방어)", id=f"@{t('ID')}"),
            "If_already": iff(f"@not(and(empty({rk}?['DueDate']), empty({rk}?['DueHintChecked']), not(equals({rk}?['Status']?['Value'], '완료')), not(equals({rk}?['Status']?['Value'], '취소'))))",
                              {"Stop_already": terminate("Succeeded", "AlreadyHandled", "이미 기한이 있거나 추정 완료")}),
            "Get_holidays": sp("Get items", "Holidays", "휴무일(내일·모레 계산용)", top=500),
            "Run_hint": script("ParseDueHint", {
                "text": f"@{{concat({rk}?['Title'], ' ', coalesce({rk}?['Evidence'], ''))}}",
                "receivedKst": f"@{{convertFromUtc({rk}?['Created'], 'Korea Standard Time', 'yyyy-MM-dd')}}",
                "holidaysJson": "@{string(body('Get_holidays')?['value'])}"}, "기한·긴급도 추정(Office Scripts)"),
            "Update_hint": update_preserving("ActionItems", f"@{t('ID')}", rk, {
                "DueDate": f"@if(empty({hint}?['dueDate']), null, {hint}?['dueDate'])",
                "FlagDue": f"@if(empty({hint}?['dueDate']), null, {hint}?['dueDate'])",
                "Priority/Value": f"@{{if(equals({hint}?['priority'], '높음'), '높음', coalesce({rk}?['Priority']?['Value'], '보통'))}}",
                "DueHint": f"@{{if(empty({hint}?['phrase']), '근거 없음 — 직접 입력', concat('메일 문구 [', {hint}?['phrase'], ']에서 추정'))}}",
                "DueHintChecked": "Y"}, "기한·우선순위·근거만 갱신(사람이 언제든 수정 가능, 다른 열 보존)"),
        },
        purpose="번호가 붙은(P3P-F3 이후) 플래그 할 일 중 등록된 할 일에 기한이 없으면 메일 제목·미리보기의 '내일까지·10/30까지·금요일까지·긴급' 같은 표현으로 기한·우선순위를 채우고 근거를 남김."))

    # ---------------- A안 최소 구성(Minimum Viable Automation) — SIMPLIFIED_ARCHITECTURE.md ----------------
    # 목록 2개(ActionItems·FlowErrorLog) + 흐름 2개, Office Scripts·DecisionLog·Teams 없이 1주차에 끝낸다.
    flows.append(flag_flow("P3A-1", "Inbox", "실행", "[메일] ", None, name="P3A-1 (A안) 메일 플래그 → 할 일 등록"))
    flows[-1]["purpose"] = ("A안 1주차용. P3P-F1과 같은 고유키·멱등 규칙이지만 DecisionLog를 쓰지 않는다. "
                            "2주차에 DecisionLog를 만든 뒤 이 흐름을 끄고 P3P-F1을 켠다(같은 고유키라 중복 없음). 둘을 동시에 켜지 않는다.")
    open_f = f"Owner/EMail eq '@{{{CFG}?['me']}}' and (Status eq '미착수' or Status eq '진행중')"
    due = "convertFromUtc(item()?['DueDate'], 'Korea Standard Time', 'yyyy-MM-dd')"
    created = "convertFromUtc(item()?['Created'], 'Korea Standard Time', 'yyyy-MM-dd')"
    row = lambda extra: {"할 일": "@item()?['Title']", **extra, "상태": "@item()?['Status']?['Value']",
                         "우선순위": "@coalesce(item()?['Priority']?['Value'], '보통')", "링크": "@coalesce(item()?['SourceLink'], '')"}
    n = lambda a: f"length(body('{a}'))"
    flows.append(flow(
        "P3A-2", "P3A-2 (A안) 간단 아침 메일 — Office Scripts 없이",
        {"kind": "Recurrence", "recurrence": {"frequency": "Week", "interval": 1, "timeZone": "Korea Standard Time",
                                             "schedule": {"weekDays": weekdays, "hours": [7], "minutes": [40]}}},
        {
            "Get_open": sp("Get items", "ActionItems", "내 미결 할 일(기한 오름차순)", filter=open_f, orderBy="DueDate asc", top=500),
            "Overdue": {"type": "FilterArray", "note": "기한 지남",
                        "inputs": {"from": "@body('Get_open')?['value']",
                                   "where": f"@and(not(empty(item()?['DueDate'])), less({due}, outputs('Today')))"}},
            "Due_soon": {"type": "FilterArray", "note": "오늘~2일 뒤 마감",
                         "inputs": {"from": "@body('Get_open')?['value']",
                                    "where": f"@and(not(empty(item()?['DueDate'])), greaterOrEquals({due}, outputs('Today')), lessOrEquals({due}, outputs('Soon')))"}},
            "Undated": {"type": "FilterArray", "note": "기한 없음 — 기한을 만들어 넣지 않고 따로 보여 준다",
                        "inputs": {"from": "@body('Get_open')?['value']", "where": "@empty(item()?['DueDate'])"}},
            "Neglected": {"type": "FilterArray", "note": "방치 경고: 기한 없이 14일 이상, 또는 우선순위 높음인데 7일 이상",
                          "inputs": {"from": "@body('Undated')",
                                     "where": f"@or(lessOrEquals({created}, outputs('Ago14')), and(equals(item()?['Priority']?['Value'], '높음'), lessOrEquals({created}, outputs('Ago7'))))"}},
            "Rows_overdue": {"type": "Select", "note": "표 열", "inputs": {"from": "@body('Overdue')", "select": row({"기한": f"@{due}"})}},
            "Rows_soon": {"type": "Select", "note": "표 열", "inputs": {"from": "@body('Due_soon')", "select": row({"기한": f"@{due}"})}},
            "Rows_undated": {"type": "Select", "note": "표 열(등록일 = 경과 판단 근거)",
                             "inputs": {"from": "@body('Undated')", "select": row({"등록일": f"@{created}"})}},
            "Table_overdue": {"type": "Table", "note": "HTML 표 만들기", "inputs": {"from": "@body('Rows_overdue')", "format": "HTML"}},
            "Table_soon": {"type": "Table", "note": "HTML 표 만들기", "inputs": {"from": "@body('Rows_soon')", "format": "HTML"}},
            "Table_undated": {"type": "Table", "note": "HTML 표 만들기", "inputs": {"from": "@body('Rows_undated')", "format": "HTML"}},
            "Send_brief": {"type": "Connector", "connector": "Office 365 Outlook", "operation": "Send an email (V2)",
                           "note": "본인에게만(받는 사람 = 설정 me)",
                           "inputs": {"to": f"@{{{CFG}?['me']}}",
                                      "subject": f"@{{concat('[오늘 할 일] ', outputs('Today'), ' · 초과 ', string({n('Overdue')}), ' · 임박 ', string({n('Due_soon')}), ' · 기한없음 ', string({n('Undated')}), if(greater({n('Neglected')}, 0), concat(' · 방치경고 ', string({n('Neglected')})), ''))}}",
                                      "body": (f"@{{concat('<h3>기한 지남 ', string({n('Overdue')}), '건</h3>', if(equals({n('Overdue')}, 0), '<p>없음</p>', body('Table_overdue')), "
                                               f"'<h3>오늘~2일 뒤 마감 ', string({n('Due_soon')}), '건</h3>', if(equals({n('Due_soon')}, 0), '<p>없음</p>', body('Table_soon')), "
                                               f"'<h3>기한 없는 할 일 ', string({n('Undated')}), '건 (오래된 순 아님 — 등록일 확인)</h3>', if(greater({n('Neglected')}, 0), concat('<p><b>방치 경고 ', string({n('Neglected')}), '건</b>: 기한 없이 오래됐거나 우선순위 높음 — 기한을 정하거나 취소하세요.</p>'), ''), "
                                               f"if(equals({n('Undated')}, 0), '<p>없음</p>', body('Table_undated')), '<p><a href=', {CFG}?['links']?['myActions'], '>내 할 일 열기</a></p>')}}")}},
        },
        pre={"Today": {"type": "Compose", "inputs": f"@{{{TODAY}}}", "note": "오늘(KST)"},
             "Soon": {"type": "Compose", "inputs": "@{addDays(outputs('Today'), 2, 'yyyy-MM-dd')}", "note": "2일 뒤"},
             "Ago7": {"type": "Compose", "inputs": "@{addDays(outputs('Today'), -7, 'yyyy-MM-dd')}", "note": "7일 전"},
             "Ago14": {"type": "Compose", "inputs": "@{addDays(outputs('Today'), -14, 'yyyy-MM-dd')}", "note": "14일 전"}},
        purpose="A안 1주차용 아침 메일. 표준 액션(필터·선택·HTML 표)만 사용. 기한 지남·임박·기한 없음(방치 경고 포함)을 본인에게. 휴무일 건너뛰기·점수·일정·집중 시간은 B안(P3P-F6)."))
    return flows


def main():
    OUT.mkdir(exist_ok=True)
    for f in build():
        (OUT / f"{f['id']}.flow.json").write_text(json.dumps(f, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("wrote", f["id"], f["name"])


if __name__ == "__main__":
    main()
