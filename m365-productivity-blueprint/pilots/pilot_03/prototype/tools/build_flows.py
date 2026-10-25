"""Pilot 03 프로토타입 흐름 정의 생성기 → flows/*.flow.json

각 흐름은 '설정(Config) → Try 범위 → Catch 범위' 공통 골격을 쓴다.
생성된 JSON은 (1) 에뮬레이터가 그대로 실행해 테스트하고 (2) render_build_tables.py가 디자이너 입력표로 변환한다.
값의 {{...}} 자리표시자는 구축 시 실제 값(사이트 주소, 본인 이메일, 파일 경로, 보기 URL)으로 바꾼다.
실행: python3 tools/build_flows.py
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "flows"
SITE = "{{SITE_URL}}"
T = "triggerOutputs()?['body/{}']"

CONFIG = {"type": "Compose", "note": "설정값 모음. 샌드박스→운영 전환 시 이 값만 바꾼다(트리거의 사이트·목록은 직접 다시 선택).",
          "inputs": {"site": SITE, "me": "{{ME}}", "hostWorkbook": "{{HOST_WORKBOOK}}",
                     "scriptFolder": "{{SCRIPT_FOLDER}}", "prototypeMode": True, "channel": "{{NOTIFY_CHANNEL}}",
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
    return {"type": "Connector", "connector": "Excel Online (Business)", "operation": "Run script from SharePoint library",
            "inputs": {"workbook": f"@{{{CFG}?['hostWorkbook']}}", "script": f"@{{{CFG}?['scriptFolder']}}/{name}.osts",
                       "parameters": params}, "note": note}


def terminate(status, code, message):
    return {"type": "Terminate", "inputs": {"runStatus": status, "runError": {"code": code, "message": message}}}


def iff(expr, yes: dict, no: dict | None = None, note=""):
    a = {"type": "If", "expression": expr, "actions": chain(yes), "note": note}
    if no is not None:
        a["else"] = {"actions": chain(no)}
    return a


def catch(extra: dict | None = None) -> dict:
    acts = {
        "Failed_actions": {"type": "FilterArray", "note": "Try 안에서 실패한 액션만 추림",
                           "inputs": {"from": "@result('Try')", "where": "@equals(item()?['status'], 'Failed')"}},
        "Log_error": sp("Create item", "FlowErrorLog", "공통 오류 로그 기록", item={
            "Title": "@{workflow()?['tags']?['flowDisplayName']}",
            "FlowRunId": "@{workflow()?['run']?['name']}",
            "FailedAction": "@{coalesce(first(body('Failed_actions'))?['name'], '')}",
            "ErrorMessage": "@{coalesce(first(body('Failed_actions'))?['error']?['message'], '상세 메시지 없음(실행 기록 확인)')}",
            "Severity/Value": "Critical", "Resolved": False,
            "RunUrl": "@{concat('https://make.powerautomate.com/environments/', workflow()?['tags']?['environmentName'], '/flows/', workflow()?['name'], '/runs/', workflow()?['run']?['name'])}"}),
    }
    for k, v in (extra or {}).items():
        acts[k] = v
    chain(acts)
    last = list(acts)[-1]
    acts["Terminate_failed"] = {**terminate("Failed", "FlowFailed", "@{concat('실패 액션: ', coalesce(first(body('Failed_actions'))?['name'], '?'))}"),
                                "runAfter": {last: ["Succeeded", "Failed", "Skipped"]}}
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


def flag_flow(fid, folder, action_type, prefix, default_due_days, route_decisions=False):
    due = (f"@if(empty({t('flag/dueDateTime/dateTime')}), "
           + ("null" if default_due_days is None else
              f"formatDateTime(addDays(convertFromUtc(utcNow(), 'Korea Standard Time'), {default_due_days}), 'yyyy-MM-dd')")
           + f", formatDateTime({t('flag/dueDateTime/dateTime')}, 'yyyy-MM-dd'))")
    msg_id = f"replace({t('id')}, '''', '''''')"
    create_action = {
        "Title_text": {"type": "Compose", "note": "제목 없음 대비 + 접두어",
                       "inputs": f"@{{concat('{prefix}', if(empty({t('subject')}), '(제목 없음)', {t('subject')}))}}"},
        "Create_action": sp("Create item", "ActionItems", "액션 등록", item={
            "Title": "@{if(greater(length(outputs('Title_text')), 250), substring(outputs('Title_text'), 0, 250), outputs('Title_text'))}",
            "Owner/Claims": f"@{{{CFG}?['me']}}",
            "Status/Value": "미착수", "ActionType/Value": action_type, "Source/Value": "이메일",
            "CreatedVia/Value": "Outlook 플래그", "Priority/Value": "보통",
            "SourceLink": f"@{{coalesce({t('webLink')}, '')}}",
            "Evidence": f"@{{coalesce({t('bodyPreview')}, '')}}",
            "SourceMessageId": f"@{{{t('id')}}}",
            "DueDate": due}),
    }
    acts = {
        "Check_message_id": iff(f"@empty({t('id')})",
                                {"Stop_no_id": terminate("Failed", "InputMissing", "메일 ID가 없어 중복 확인을 할 수 없습니다")},
                                note="메일 ID 누락 방어"),
        "Find_existing": sp("Get items", "ActionItems", "같은 메일로 이미 만든 액션이 있는지(중복 방지)",
                            filter=f"SourceMessageId eq '@{{{msg_id}}}'", top=1),
    }
    dup = "greater(length(body('Find_existing')?['value']), 0)"
    if route_decisions:
        acts["Find_existing_decision"] = sp("Get items", "DecisionLog", "같은 메일로 이미 만든 결정이 있는지",
                                            filter=f"SourceMessageId eq '@{{{msg_id}}}'", top=1)
        dup = f"or({dup}, greater(length(body('Find_existing_decision')?['value']), 0))"
    acts["If_duplicate"] = iff(f"@{dup}", {"Stop_duplicate": terminate("Succeeded", "Duplicate", "이미 등록된 메일")},
                               note="중복이면 성공으로 종료")
    if not route_decisions:
        acts.update(create_action)
    else:
        cats = f"coalesce({t('categories')}, createArray())"
        subj = f"if(empty({t('subject')}), '(제목 없음)', {t('subject')})"
        acts["Kind"] = {"type": "Compose", "note": "Outlook 범주로 종류 판별: '결정요청'/'결정' 범주가 있으면 결정, 없으면 할 일",
                        "inputs": f"@{{if(contains({cats}, '결정요청'), '결정요청', if(contains({cats}, '결정'), '결정', '액션'))}}"}
        acts["If_action"] = iff("@equals(outputs('Kind'), '액션')", create_action, {
            "Create_decision": sp("Create item", "DecisionLog", "결정 또는 결정요청 등록", item={
                "Title": f"@{{if(greater(length({subj}), 250), substring({subj}, 0, 250), {subj})}}",
                "DecisionText": f"@{{concat({subj}, ' / 원문: ', coalesce({t('bodyPreview')}, ''))}}",
                "Status/Value": "@{if(equals(outputs('Kind'), '결정요청'), '결정요청', '확정')}",
                "Decider/Claims": f"@{{{CFG}?['me']}}", "RequestedBy/Claims": f"@{{{CFG}?['me']}}",
                "SourceLink": f"@{{coalesce({t('webLink')}, '')}}", "CreatedVia/Value": "Outlook 플래그",
                "SourceMessageId": f"@{{{t('id')}}}"}),
        }, note="종류별 분기: 할 일 / 결정·결정요청")
    extra = " 범주 '결정'·'결정요청'이 붙은 메일은 DecisionLog로 기록(Teams 메시지 기록의 대체 경로)." if route_decisions else ""
    return flow(
        fid, f"{fid} 메일 플래그({folder}) → {action_type if not route_decisions else '할 일·결정'} 등록",
        {"kind": "Outlook.WhenAnEmailIsFlaggedV4", "inputs": {"folder": folder}, "concurrency": 1},
        acts,
        purpose=f"Outlook '{folder}' 폴더에서 플래그한 메일을 등록. 같은 메일 재플래그 시 중복 생성 없음.{extra}")


def numbering_flow(fid, lst, id_col, prefix, extra_item, required):
    item = {c: v for c, v in required.items()}
    item[id_col] = (f"@{{if(empty({t(id_col)}), concat('{prefix}-', convertFromUtc({t('Created')}, 'Korea Standard Time', 'yyyy'), "
                    f"'-', formatNumber({t('ID')}, '00000')), {t(id_col)})}}")
    item.update(extra_item)
    item["PrevStatus"] = f"@{{{t('Status/Value')}}}"
    return flow(
        fid, f"{fid} {lst} 번호·상태 기록",
        {"kind": "SharePoint.WhenAnItemIsCreatedOrModified", "inputs": {"site": SITE, "list": lst},
         "conditions": [f"@or(empty({t(id_col)}), not(equals({t('Status/Value')}, coalesce({t('PrevStatus')}, ''))))"]},
        {"Update_item": sp("Update item", lst, "번호 부여·상태 변경 기록. PrevStatus를 현재 상태로 맞춰 자기 재실행을 막는다",
                           id=f"@{t('ID')}", item=item)},
        purpose=f"{lst} 새 항목에 {prefix}-연도-번호 부여, 상태 변경 시각 기록. 트리거 조건으로 자기 수정에 의한 재실행 차단.")


def build() -> list[dict]:
    flows = []
    flows.append(flag_flow("P3P-F1", "Inbox", "실행", "[메일] ", None, route_decisions=True))
    flows.append(flag_flow("P3P-F2", "Sent Items", "회신대기", "[회신대기] ", 3))

    flows.append(numbering_flow(
        "P3P-F3", "ActionItems", "ActionID", "ACT",
        {"CompletedAt": f"@if(equals({t('Status/Value')}, '완료'), coalesce({t('CompletedAt')}, utcNow()), null)"},
        {"Title": f"@{{{t('Title')}}}", "Owner/Claims": f"@{{{t('Owner/Claims')}}}",
         "Status/Value": f"@{{{t('Status/Value')}}}", "ActionType/Value": f"@{{{t('ActionType/Value')}}}"}))
    today = "convertFromUtc(utcNow(), 'Korea Standard Time', 'yyyy-MM-dd')"
    flows.append(numbering_flow(
        "P3P-F4", "DecisionLog", "DecisionID", "DEC",
        {"DecidedAt": f"@if(and(equals({t('Status/Value')}, '확정'), empty({t('DecidedAt')})), {today}, {t('DecidedAt')})",
         "RequestedAt": f"@if(and(equals({t('Status/Value')}, '결정요청'), empty({t('RequestedAt')})), {today}, {t('RequestedAt')})"},
        {"Title": f"@{{{t('Title')}}}", "DecisionText": f"@{{{t('DecisionText')}}}",
         "Status/Value": f"@{{{t('Status/Value')}}}"}))

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
                "Create_decision": sp("Create item", "DecisionLog", "결정 또는 결정요청 등록", item={
                    "Title": f"@{{{inp}?['title']}}",
                    "DecisionText": f"@{{concat({inp}?['title'], ' / 원문: ', outputs('Content'))}}",
                    "Status/Value": f"@{{if(equals({inp}?['kind'], '결정요청'), '결정요청', '확정')}}",
                    "Decider/Claims": f"@{{{inp}?['owner']}}", "RequestedBy/Claims": f"@{{{CFG}?['me']}}",
                    "SourceLink": f"@{{{inp}?['link']}}", "CreatedVia/Value": "Teams 메시지",
                    "SourceMessageId": f"@{{{inp}?['messageId']}}"}),
            }, note="종류별 분기: 액션 / 결정·결정요청"),
            "Tell_done": msg_to_me(f"@{{concat('기록됨(', {inp}?['kind'], '): ', {inp}?['title'], ' — 번호는 잠시 후 목록에서 확인')}}"),
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
            "Get_my_decisions": sp("Get items", "DecisionLog", "내가 결정할 대기 건",
                                   filter=f"Status eq '결정요청' and Decider/EMail eq '@{{{CFG}?['me']}}'", top=200),
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
                        "Mark_reminded": sp("Update item", "ActionItems", "리마인더 횟수·시각 기록", id="@items('For_each_item')", item={
                            "Title": "@{body('Get_action')?['Title']}", "Owner/Claims": "@{body('Get_action')?['Owner']?['Claims']}",
                            "Status/Value": "@{body('Get_action')?['Status']?['Value']}",
                            "ActionType/Value": "@{body('Get_action')?['ActionType']?['Value']}",
                            "ReminderCount": "@add(coalesce(body('Get_action')?['ReminderCount'], 0), 1)",
                            "LastRemindedAt": "@{utcNow()}"}),
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
    req_intake = {"Title": f"@{{{t('Title')}}}", "MeetingDate": f"@{{{t('MeetingDate')}}}",
                  "Transcript": f"@{{{t('Transcript')}}}", "ExtractionJson": f"@{{{t('ExtractionJson')}}}"}
    flows.append(flow(
        "P3P-F8", "P3P-F8 Copilot 추출 결과 검증 → 후보 생성",
        {"kind": "SharePoint.WhenAnItemIsCreatedOrModified", "inputs": {"site": SITE, "list": "MeetingIntake"},
         "conditions": [f"@or(equals({t('Status/Value')}, '접수'), equals({t('Status/Value')}, '재검증요청'))"]},
        {
            "Get_roster": sp("Get items", "TeamRoster", "팀 명부(담당자 매핑 근거)", top=500),
            "Run_guard": script("GuardExtraction", {
                "transcript": f"@{{{t('Transcript')}}}", "rosterJson": "@{string(body('Get_roster')?['value'])}",
                "extractionJson": f"@{{{t('ExtractionJson')}}}",
                "meetingDate": f"@{{formatDateTime({t('MeetingDate')}, 'yyyy-MM-dd')}}"}, "G1~G6 검증(Office Scripts)"),
            "Get_old_candidates": sp("Get items", "ActionCandidates", "재검증 시 이전 '제안' 후보",
                                     filter=f"IntakeID eq @{{{t('ID')}}} and Status eq '제안'", top=500),
            "Supersede_old": {"type": "Foreach", "foreach": "@body('Get_old_candidates')?['value']",
                              "note": "이전 후보는 삭제하지 않고 '기각' 처리(이력 보존)", "actions": {
                "Mark_superseded": sp("Update item", "ActionCandidates", "기각", id="@items('Supersede_old')?['ID']", item={
                    "Title": "@{items('Supersede_old')?['Title']}", "Kind/Value": "@{items('Supersede_old')?['Kind']?['Value']}",
                    "IntakeID": "@items('Supersede_old')?['IntakeID']",
                    "Verdict/Value": "@{items('Supersede_old')?['Verdict']?['Value']}", "Status/Value": "기각"}, runAfter={})}},
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
                "Mark_intake_done": sp("Update item", "MeetingIntake", "접수 완료 표시(자기 재실행 차단)", id=f"@{t('ID')}", item={
                    **req_intake, "Status/Value": "검증완료",
                    "RecommendedCount": f"@{g}?['recommendedCount']", "ReviewCount": f"@{g}?['reviewCount']",
                    "ResultSummary": f"@{{concat('추천 ', string({g}?['recommendedCount']), '건 · 검토필요 ', string({g}?['reviewCount']), '건', if(empty({g}?['schemaErrors']), '', concat(' · 형식 오류: ', join({g}?['schemaErrors'], '; '))))}}",
                    "ProcessedAt": "@{utcNow()}"}),
                "Tell_candidates": msg_to_me(f"@{{concat('회의 \"', {t('Title')}, '\" 후보 ', string(length({g}?['candidates'])), '건(추천 ', string({g}?['recommendedCount']), ') — 확인 후 승인하세요: ', {CFG}?['links']?['candidates'])}}"),
            }, {
                "Mark_intake_error": sp("Update item", "MeetingIntake", "오류 표시", id=f"@{t('ID')}", item={
                    **req_intake, "Status/Value": "오류", "ResultSummary": f"@{{{g}?['parseError']}}", "ProcessedAt": "@{utcNow()}"}),
                "Tell_parse_error": msg_to_me(f"@{{concat('회의 \"', {t('Title')}, '\" 추출 결과를 읽지 못했습니다: ', {g}?['parseError'])}}"),
            }, note="JSON 해석 성공 여부"),
        },
        purpose="회의 추출 접수(MeetingIntake)에 Copilot 결과를 붙여넣으면 가드 검증 후 후보를 만든다. 등록은 하지 않는다."))

    rc = "body('Recheck')"
    req_cand = {"Title": f"@{{{rc}?['Title']}}", "Kind/Value": f"@{{{rc}?['Kind']?['Value']}}",
                "IntakeID": f"@{rc}?['IntakeID']", "Verdict/Value": f"@{{{rc}?['Verdict']?['Value']}}"}
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
                "Mark_done_action": sp("Update item", "ActionCandidates", "등록완료 표시", id=f"@{t('ID')}", item={
                    **req_cand, "Status/Value": "등록완료", "CreatedItemID": "@{string(body('Create_action')?['ID'])}"}),
            }, {
                "Create_decision": sp("Create item", "DecisionLog", "결정 등록(확정)", item={
                    "Title": f"@{{{rc}?['Title']}}", "DecisionText": f"@{{concat({rc}?['Title'], ' / 근거: ', coalesce({rc}?['Evidence'], ''))}}",
                    "Status/Value": "확정", "MeetingName": f"@{{coalesce({rc}?['MeetingName'], '')}}",
                    "MeetingDate": f"@if(empty({rc}?['MeetingDate']), null, {rc}?['MeetingDate'])",
                    "DecidedAt": f"@if(empty({rc}?['MeetingDate']), {today}, {rc}?['MeetingDate'])",
                    "Decider/Claims": f"@if(empty({rc}?['OwnerEmail']), null, {rc}?['OwnerEmail'])",
                    "CreatedVia/Value": "AI 제안 승인"}),
                "Mark_done_decision": sp("Update item", "ActionCandidates", "등록완료 표시", id=f"@{t('ID')}", item={
                    **req_cand, "Status/Value": "등록완료", "CreatedItemID": "@{string(body('Create_decision')?['ID'])}"}),
            }, note="종류별 등록"),
        },
        catch_extra={"Mark_candidate_error": sp("Update item", "ActionCandidates", "후보에 오류 표시(사용자가 고쳐 다시 승인)", id=f"@{t('ID')}", item={
            "Title": f"@{{{t('Title')}}}", "Kind/Value": f"@{{{t('Kind/Value')}}}", "IntakeID": f"@{t('IntakeID')}",
            "Verdict/Value": f"@{{{t('Verdict/Value')}}}", "Status/Value": "오류",
            "Reasons": f"@{{concat(coalesce({t('Reasons')}, ''), ' / 등록 실패: ', coalesce(first(body('Failed_actions'))?['error']?['message'], first(body('Failed_actions'))?['name']))}}"})},
        purpose="사람이 ActionCandidates에서 '승인'으로 바꾼 후보만 등록. 최신 값 재확인으로 중복 등록 방지, 실패 시 후보에 사유 표시."))
    return flows


def main():
    OUT.mkdir(exist_ok=True)
    for f in build():
        (OUT / f"{f['id']}.flow.json").write_text(json.dumps(f, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("wrote", f["id"], f["name"])


if __name__ == "__main__":
    main()
