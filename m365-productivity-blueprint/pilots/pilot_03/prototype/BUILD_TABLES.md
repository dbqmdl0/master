# Pilot 03 프로토타입 — 흐름별 디자이너 입력표 (자동 생성)

> 이 파일은 `tools/render_build_tables.py`가 `flows/*.flow.json`에서 생성한다. **직접 수정하지 말 것.**
> 사용법은 `BUILD_GUIDE.md` 3장. 표의 '액션 이름'은 액션 카드의 **… › 이름 바꾸기(Rename)** 로 똑같이 바꾼다 — 식이 이 이름을 참조한다.
> **fx** 표시 값은 입력란의 **식(fx)** 탭에 붙여넣는다. `@{...}`가 섞인 값은 입력란에 그대로 붙여넣는다(식 토큰으로 바뀌지 않으면 fx 탭에 중괄호 안 식만).
> `{{...}}` 자리표시자는 `BUILD_GUIDE.md` 1장 값으로 바꾼다.

## P3P-F1 메일 플래그(Inbox) → 실행 등록

**목적:** Outlook 'Inbox' 폴더에서 플래그한 메일을 ActionItems(실행)로 등록. 같은 메일 재플래그 시 중복 생성 없음.

**만들기:** 자동화된 클라우드 흐름 · 흐름 이름 `P3P-F1 메일 플래그(Inbox) → 실행 등록`

**트리거:** Office 365 Outlook › **When an email is flagged (V4)** (전자 메일에 플래그가 지정된 경우)

- 폴더(Folder): `Inbox`
- 트리거 **설정 › 동시성 제어(Concurrency control) 켬 › 병렬 처리 수준 1** (한 번 켜면 되돌리려면 트리거를 다시 만들어야 함)

| 단계 | 액션 이름(이름 바꾸기) | 추가할 액션 | 설정값 | 비고 |
|---|---|---|---|---|
| 1 | `Config` | 데이터 작업 › **작성(Compose)** | 입력(Inputs): `{"site": "{{SITE_URL}}", "me": "{{ME}}", "hostWorkbook": "{{HOST_WORKBOOK}}", "scriptFolder": "{{SCRIPT_FOLDER}}", "prototypeMode": true, "links": {"myActions": "{{VIEW_MY_ACTIONS}}", "decisionQueue": "{{VIEW_DECISION_QUEUE}}", "candidates": "{{VIEW_CANDIDATES}}"}}` | 설정값 모음. 샌드박스→운영 전환 시 이 값만 바꾼다(트리거의 사이트·목록은 직접 다시 선택). |
| 2 | `Try` | 컨트롤 › **범위(Scope)** | - |  |
| 2.1 | 　`Check_message_id` | 컨트롤 › **조건(Condition)** | 왼쪽 값: **fx** `empty(triggerOutputs()?['body/id'])` · 연산자 **같음(is equal to)** · 오른쪽 값: **fx** `true` | 메일 ID 누락 방어 |
| 2.1.예 | 　　**'True(예)' 분기** | | | |
| 2.1.예.1 | 　　`Stop_no_id` | 컨트롤 › **종료(Terminate)** | 상태: 실패함(Failed) · 코드 `InputMissing` · 메시지 `메일 ID가 없어 중복 확인을 할 수 없습니다` |  |
| 2.2 | 　`Find_existing` | SharePoint › **Get items** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `ActionItems`<br>필터 쿼리(Filter Query): `SourceMessageId eq '@{replace(triggerOutputs()?['body/id'], '''', '''''')}'`<br>상위 개수(Top Count): `1` | 같은 메일로 이미 만든 액션이 있는지(중복 방지) |
| 2.3 | 　`If_duplicate` | 컨트롤 › **조건(Condition)** | 왼쪽 값: **fx** `greater(length(body('Find_existing')?['value']), 0)` · 연산자 **같음(is equal to)** · 오른쪽 값: **fx** `true` | 중복이면 성공으로 종료 |
| 2.3.예 | 　　**'True(예)' 분기** | | | |
| 2.3.예.1 | 　　`Stop_duplicate` | 컨트롤 › **종료(Terminate)** | 상태: 성공함(Succeeded) |  |
| 2.4 | 　`Title_text` | 데이터 작업 › **작성(Compose)** | 입력(Inputs): `@{concat('[메일] ', if(empty(triggerOutputs()?['body/subject']), '(제목 없음)', triggerOutputs()?['body/subject']))}` | 제목 없음 대비 + 접두어 |
| 2.5 | 　`Create_action` | SharePoint › **Create item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `ActionItems`<br>할 일 `Title`: `@{if(greater(length(outputs('Title_text')), 250), substring(outputs('Title_text'), 0, 250), outputs('Title_text'))}`<br>담당자 `Owner` (사람: 이메일): `@{outputs('Config')?['me']}`<br>상태 `Status` (선택 값): `미착수`<br>유형 `ActionType` (선택 값): `실행`<br>출처 `Source` (선택 값): `이메일`<br>등록 경로 `CreatedVia` (선택 값): `Outlook 플래그`<br>우선순위 `Priority` (선택 값): `보통`<br>원문 링크 `SourceLink`: `@{coalesce(triggerOutputs()?['body/webLink'], '')}`<br>근거 문장 `Evidence`: `@{coalesce(triggerOutputs()?['body/bodyPreview'], '')}`<br>원본 메시지 ID(시스템) `SourceMessageId`: `@{triggerOutputs()?['body/id']}`<br>기한 `DueDate`: **fx** `if(empty(triggerOutputs()?['body/flag/dueDateTime/dateTime']), null, formatDateTime(triggerOutputs()?['body/flag/dueDateTime/dateTime'], 'yyyy-MM-dd'))` | 액션 등록 |
| 3 | `Catch` | 컨트롤 › **범위(Scope)** | **실행 후 구성**: 'Try' 이(가) 실패함, 시간 초과됨 | 실행 후 구성: Try가 '실패함'·'시간 초과됨'일 때 |
| 3.1 | 　`Failed_actions` | 데이터 작업 › **배열 필터링(Filter array)** | 보낸 사람(From): **fx** `result('Try')` · '고급 모드에서 편집' 후: `@equals(item()?['status'], 'Failed')` | Try 안에서 실패한 액션만 추림 |
| 3.2 | 　`Log_error` | SharePoint › **Create item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `FlowErrorLog`<br>Flow 이름 `Title`: `@{workflow()?['tags']?['flowDisplayName']}`<br>실행 ID `FlowRunId`: `@{workflow()?['run']?['name']}`<br>실패 액션 `FailedAction`: `@{coalesce(first(body('Failed_actions'))?['name'], '')}`<br>오류 메시지 `ErrorMessage`: `@{coalesce(first(body('Failed_actions'))?['error']?['message'], '상세 메시지 없음(실행 기록 확인)')}`<br>심각도 `Severity` (선택 값): `Critical`<br>조치완료 `Resolved`: `false`(식 탭)<br>실행 기록 링크 `RunUrl`: `@{concat('https://make.powerautomate.com/environments/', workflow()?['tags']?['environmentName'], '/flows/', workflow()?['name'], '/runs/', workflow()?['run']?['name'])}` | 공통 오류 로그 기록 |
| 3.3 | 　`Terminate_failed` | 컨트롤 › **종료(Terminate)** | 상태: 실패함(Failed) · 코드 `FlowFailed` · 메시지 `@{concat('실패 액션: ', coalesce(first(body('Failed_actions'))?['name'], '?'))}`<br>**실행 후 구성**: 'Log_error' 이(가) 성공함, 실패함, 건너뜀 |  |

## P3P-F2 메일 플래그(Sent Items) → 회신대기 등록

**목적:** Outlook 'Sent Items' 폴더에서 플래그한 메일을 ActionItems(회신대기)로 등록. 같은 메일 재플래그 시 중복 생성 없음.

**만들기:** 자동화된 클라우드 흐름 · 흐름 이름 `P3P-F2 메일 플래그(Sent Items) → 회신대기 등록`

**트리거:** Office 365 Outlook › **When an email is flagged (V4)** (전자 메일에 플래그가 지정된 경우)

- 폴더(Folder): `Sent Items`
- 트리거 **설정 › 동시성 제어(Concurrency control) 켬 › 병렬 처리 수준 1** (한 번 켜면 되돌리려면 트리거를 다시 만들어야 함)

| 단계 | 액션 이름(이름 바꾸기) | 추가할 액션 | 설정값 | 비고 |
|---|---|---|---|---|
| 1 | `Config` | 데이터 작업 › **작성(Compose)** | 입력(Inputs): `{"site": "{{SITE_URL}}", "me": "{{ME}}", "hostWorkbook": "{{HOST_WORKBOOK}}", "scriptFolder": "{{SCRIPT_FOLDER}}", "prototypeMode": true, "links": {"myActions": "{{VIEW_MY_ACTIONS}}", "decisionQueue": "{{VIEW_DECISION_QUEUE}}", "candidates": "{{VIEW_CANDIDATES}}"}}` | 설정값 모음. 샌드박스→운영 전환 시 이 값만 바꾼다(트리거의 사이트·목록은 직접 다시 선택). |
| 2 | `Try` | 컨트롤 › **범위(Scope)** | - |  |
| 2.1 | 　`Check_message_id` | 컨트롤 › **조건(Condition)** | 왼쪽 값: **fx** `empty(triggerOutputs()?['body/id'])` · 연산자 **같음(is equal to)** · 오른쪽 값: **fx** `true` | 메일 ID 누락 방어 |
| 2.1.예 | 　　**'True(예)' 분기** | | | |
| 2.1.예.1 | 　　`Stop_no_id` | 컨트롤 › **종료(Terminate)** | 상태: 실패함(Failed) · 코드 `InputMissing` · 메시지 `메일 ID가 없어 중복 확인을 할 수 없습니다` |  |
| 2.2 | 　`Find_existing` | SharePoint › **Get items** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `ActionItems`<br>필터 쿼리(Filter Query): `SourceMessageId eq '@{replace(triggerOutputs()?['body/id'], '''', '''''')}'`<br>상위 개수(Top Count): `1` | 같은 메일로 이미 만든 액션이 있는지(중복 방지) |
| 2.3 | 　`If_duplicate` | 컨트롤 › **조건(Condition)** | 왼쪽 값: **fx** `greater(length(body('Find_existing')?['value']), 0)` · 연산자 **같음(is equal to)** · 오른쪽 값: **fx** `true` | 중복이면 성공으로 종료 |
| 2.3.예 | 　　**'True(예)' 분기** | | | |
| 2.3.예.1 | 　　`Stop_duplicate` | 컨트롤 › **종료(Terminate)** | 상태: 성공함(Succeeded) |  |
| 2.4 | 　`Title_text` | 데이터 작업 › **작성(Compose)** | 입력(Inputs): `@{concat('[회신대기] ', if(empty(triggerOutputs()?['body/subject']), '(제목 없음)', triggerOutputs()?['body/subject']))}` | 제목 없음 대비 + 접두어 |
| 2.5 | 　`Create_action` | SharePoint › **Create item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `ActionItems`<br>할 일 `Title`: `@{if(greater(length(outputs('Title_text')), 250), substring(outputs('Title_text'), 0, 250), outputs('Title_text'))}`<br>담당자 `Owner` (사람: 이메일): `@{outputs('Config')?['me']}`<br>상태 `Status` (선택 값): `미착수`<br>유형 `ActionType` (선택 값): `회신대기`<br>출처 `Source` (선택 값): `이메일`<br>등록 경로 `CreatedVia` (선택 값): `Outlook 플래그`<br>우선순위 `Priority` (선택 값): `보통`<br>원문 링크 `SourceLink`: `@{coalesce(triggerOutputs()?['body/webLink'], '')}`<br>근거 문장 `Evidence`: `@{coalesce(triggerOutputs()?['body/bodyPreview'], '')}`<br>원본 메시지 ID(시스템) `SourceMessageId`: `@{triggerOutputs()?['body/id']}`<br>기한 `DueDate`: **fx** `if(empty(triggerOutputs()?['body/flag/dueDateTime/dateTime']), formatDateTime(addDays(convertFromUtc(utcNow(), 'Korea Standard Time'), 3), 'yyyy-MM-dd'), formatDateTime(triggerOutputs()?['body/flag/dueDateTime/dateTime'], 'yyyy-MM-dd'))` | 액션 등록 |
| 3 | `Catch` | 컨트롤 › **범위(Scope)** | **실행 후 구성**: 'Try' 이(가) 실패함, 시간 초과됨 | 실행 후 구성: Try가 '실패함'·'시간 초과됨'일 때 |
| 3.1 | 　`Failed_actions` | 데이터 작업 › **배열 필터링(Filter array)** | 보낸 사람(From): **fx** `result('Try')` · '고급 모드에서 편집' 후: `@equals(item()?['status'], 'Failed')` | Try 안에서 실패한 액션만 추림 |
| 3.2 | 　`Log_error` | SharePoint › **Create item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `FlowErrorLog`<br>Flow 이름 `Title`: `@{workflow()?['tags']?['flowDisplayName']}`<br>실행 ID `FlowRunId`: `@{workflow()?['run']?['name']}`<br>실패 액션 `FailedAction`: `@{coalesce(first(body('Failed_actions'))?['name'], '')}`<br>오류 메시지 `ErrorMessage`: `@{coalesce(first(body('Failed_actions'))?['error']?['message'], '상세 메시지 없음(실행 기록 확인)')}`<br>심각도 `Severity` (선택 값): `Critical`<br>조치완료 `Resolved`: `false`(식 탭)<br>실행 기록 링크 `RunUrl`: `@{concat('https://make.powerautomate.com/environments/', workflow()?['tags']?['environmentName'], '/flows/', workflow()?['name'], '/runs/', workflow()?['run']?['name'])}` | 공통 오류 로그 기록 |
| 3.3 | 　`Terminate_failed` | 컨트롤 › **종료(Terminate)** | 상태: 실패함(Failed) · 코드 `FlowFailed` · 메시지 `@{concat('실패 액션: ', coalesce(first(body('Failed_actions'))?['name'], '?'))}`<br>**실행 후 구성**: 'Log_error' 이(가) 성공함, 실패함, 건너뜀 |  |

## P3P-F3 ActionItems 번호·상태 기록

**목적:** ActionItems 새 항목에 ACT-연도-번호 부여, 상태 변경 시각 기록. 트리거 조건으로 자기 수정에 의한 재실행 차단.

**만들기:** 자동화된 클라우드 흐름 · 흐름 이름 `P3P-F3 ActionItems 번호·상태 기록`

**트리거:** SharePoint › **When an item is created or modified** (항목을 만들거나 수정한 경우)

- 사이트 주소: `{{SITE_URL}}` · 목록 이름: `ActionItems`
- 트리거 카드 **… › 설정(Settings) › 트리거 조건(Trigger conditions) › + 추가**: `@or(empty(triggerOutputs()?['body/ActionID']), not(equals(triggerOutputs()?['body/Status/Value'], coalesce(triggerOutputs()?['body/PrevStatus'], ''))))`

| 단계 | 액션 이름(이름 바꾸기) | 추가할 액션 | 설정값 | 비고 |
|---|---|---|---|---|
| 1 | `Config` | 데이터 작업 › **작성(Compose)** | 입력(Inputs): `{"site": "{{SITE_URL}}", "me": "{{ME}}", "hostWorkbook": "{{HOST_WORKBOOK}}", "scriptFolder": "{{SCRIPT_FOLDER}}", "prototypeMode": true, "links": {"myActions": "{{VIEW_MY_ACTIONS}}", "decisionQueue": "{{VIEW_DECISION_QUEUE}}", "candidates": "{{VIEW_CANDIDATES}}"}}` | 설정값 모음. 샌드박스→운영 전환 시 이 값만 바꾼다(트리거의 사이트·목록은 직접 다시 선택). |
| 2 | `Try` | 컨트롤 › **범위(Scope)** | - |  |
| 2.1 | 　`Update_item` | SharePoint › **Update item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `ActionItems`<br>ID: **fx** `triggerOutputs()?['body/ID']`<br>할 일 `Title`: `@{triggerOutputs()?['body/Title']}`<br>담당자 `Owner` (사람: 이메일): `@{triggerOutputs()?['body/Owner/Claims']}`<br>상태 `Status` (선택 값): `@{triggerOutputs()?['body/Status/Value']}`<br>유형 `ActionType` (선택 값): `@{triggerOutputs()?['body/ActionType/Value']}`<br>액션번호 `ActionID`: `@{if(empty(triggerOutputs()?['body/ActionID']), concat('ACT-', convertFromUtc(triggerOutputs()?['body/Created'], 'Korea Standard Time', 'yyyy'), '-', formatNumber(triggerOutputs()?['body/ID'], '00000')), triggerOutputs()?['body/ActionID'])}`<br>완료일시 `CompletedAt`: **fx** `if(equals(triggerOutputs()?['body/Status/Value'], '완료'), coalesce(triggerOutputs()?['body/CompletedAt'], utcNow()), null)`<br>이전 상태(시스템) `PrevStatus`: `@{triggerOutputs()?['body/Status/Value']}` | 번호 부여·상태 변경 기록. PrevStatus를 현재 상태로 맞춰 자기 재실행을 막는다 |
| 3 | `Catch` | 컨트롤 › **범위(Scope)** | **실행 후 구성**: 'Try' 이(가) 실패함, 시간 초과됨 | 실행 후 구성: Try가 '실패함'·'시간 초과됨'일 때 |
| 3.1 | 　`Failed_actions` | 데이터 작업 › **배열 필터링(Filter array)** | 보낸 사람(From): **fx** `result('Try')` · '고급 모드에서 편집' 후: `@equals(item()?['status'], 'Failed')` | Try 안에서 실패한 액션만 추림 |
| 3.2 | 　`Log_error` | SharePoint › **Create item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `FlowErrorLog`<br>Flow 이름 `Title`: `@{workflow()?['tags']?['flowDisplayName']}`<br>실행 ID `FlowRunId`: `@{workflow()?['run']?['name']}`<br>실패 액션 `FailedAction`: `@{coalesce(first(body('Failed_actions'))?['name'], '')}`<br>오류 메시지 `ErrorMessage`: `@{coalesce(first(body('Failed_actions'))?['error']?['message'], '상세 메시지 없음(실행 기록 확인)')}`<br>심각도 `Severity` (선택 값): `Critical`<br>조치완료 `Resolved`: `false`(식 탭)<br>실행 기록 링크 `RunUrl`: `@{concat('https://make.powerautomate.com/environments/', workflow()?['tags']?['environmentName'], '/flows/', workflow()?['name'], '/runs/', workflow()?['run']?['name'])}` | 공통 오류 로그 기록 |
| 3.3 | 　`Terminate_failed` | 컨트롤 › **종료(Terminate)** | 상태: 실패함(Failed) · 코드 `FlowFailed` · 메시지 `@{concat('실패 액션: ', coalesce(first(body('Failed_actions'))?['name'], '?'))}`<br>**실행 후 구성**: 'Log_error' 이(가) 성공함, 실패함, 건너뜀 |  |

## P3P-F4 DecisionLog 번호·상태 기록

**목적:** DecisionLog 새 항목에 DEC-연도-번호 부여, 상태 변경 시각 기록. 트리거 조건으로 자기 수정에 의한 재실행 차단.

**만들기:** 자동화된 클라우드 흐름 · 흐름 이름 `P3P-F4 DecisionLog 번호·상태 기록`

**트리거:** SharePoint › **When an item is created or modified** (항목을 만들거나 수정한 경우)

- 사이트 주소: `{{SITE_URL}}` · 목록 이름: `DecisionLog`
- 트리거 카드 **… › 설정(Settings) › 트리거 조건(Trigger conditions) › + 추가**: `@or(empty(triggerOutputs()?['body/DecisionID']), not(equals(triggerOutputs()?['body/Status/Value'], coalesce(triggerOutputs()?['body/PrevStatus'], ''))))`

| 단계 | 액션 이름(이름 바꾸기) | 추가할 액션 | 설정값 | 비고 |
|---|---|---|---|---|
| 1 | `Config` | 데이터 작업 › **작성(Compose)** | 입력(Inputs): `{"site": "{{SITE_URL}}", "me": "{{ME}}", "hostWorkbook": "{{HOST_WORKBOOK}}", "scriptFolder": "{{SCRIPT_FOLDER}}", "prototypeMode": true, "links": {"myActions": "{{VIEW_MY_ACTIONS}}", "decisionQueue": "{{VIEW_DECISION_QUEUE}}", "candidates": "{{VIEW_CANDIDATES}}"}}` | 설정값 모음. 샌드박스→운영 전환 시 이 값만 바꾼다(트리거의 사이트·목록은 직접 다시 선택). |
| 2 | `Try` | 컨트롤 › **범위(Scope)** | - |  |
| 2.1 | 　`Update_item` | SharePoint › **Update item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `DecisionLog`<br>ID: **fx** `triggerOutputs()?['body/ID']`<br>결정 제목 `Title`: `@{triggerOutputs()?['body/Title']}`<br>결정 내용 `DecisionText`: `@{triggerOutputs()?['body/DecisionText']}`<br>상태 `Status` (선택 값): `@{triggerOutputs()?['body/Status/Value']}`<br>결정번호 `DecisionID`: `@{if(empty(triggerOutputs()?['body/DecisionID']), concat('DEC-', convertFromUtc(triggerOutputs()?['body/Created'], 'Korea Standard Time', 'yyyy'), '-', formatNumber(triggerOutputs()?['body/ID'], '00000')), triggerOutputs()?['body/DecisionID'])}`<br>확정일 `DecidedAt`: **fx** `if(and(equals(triggerOutputs()?['body/Status/Value'], '확정'), empty(triggerOutputs()?['body/DecidedAt'])), convertFromUtc(utcNow(), 'Korea Standard Time', 'yyyy-MM-dd'), triggerOutputs()?['body/DecidedAt'])`<br>결정 요청일 `RequestedAt`: **fx** `if(and(equals(triggerOutputs()?['body/Status/Value'], '결정요청'), empty(triggerOutputs()?['body/RequestedAt'])), convertFromUtc(utcNow(), 'Korea Standard Time', 'yyyy-MM-dd'), triggerOutputs()?['body/RequestedAt'])`<br>이전 상태(시스템) `PrevStatus`: `@{triggerOutputs()?['body/Status/Value']}` | 번호 부여·상태 변경 기록. PrevStatus를 현재 상태로 맞춰 자기 재실행을 막는다 |
| 3 | `Catch` | 컨트롤 › **범위(Scope)** | **실행 후 구성**: 'Try' 이(가) 실패함, 시간 초과됨 | 실행 후 구성: Try가 '실패함'·'시간 초과됨'일 때 |
| 3.1 | 　`Failed_actions` | 데이터 작업 › **배열 필터링(Filter array)** | 보낸 사람(From): **fx** `result('Try')` · '고급 모드에서 편집' 후: `@equals(item()?['status'], 'Failed')` | Try 안에서 실패한 액션만 추림 |
| 3.2 | 　`Log_error` | SharePoint › **Create item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `FlowErrorLog`<br>Flow 이름 `Title`: `@{workflow()?['tags']?['flowDisplayName']}`<br>실행 ID `FlowRunId`: `@{workflow()?['run']?['name']}`<br>실패 액션 `FailedAction`: `@{coalesce(first(body('Failed_actions'))?['name'], '')}`<br>오류 메시지 `ErrorMessage`: `@{coalesce(first(body('Failed_actions'))?['error']?['message'], '상세 메시지 없음(실행 기록 확인)')}`<br>심각도 `Severity` (선택 값): `Critical`<br>조치완료 `Resolved`: `false`(식 탭)<br>실행 기록 링크 `RunUrl`: `@{concat('https://make.powerautomate.com/environments/', workflow()?['tags']?['environmentName'], '/flows/', workflow()?['name'], '/runs/', workflow()?['run']?['name'])}` | 공통 오류 로그 기록 |
| 3.3 | 　`Terminate_failed` | 컨트롤 › **종료(Terminate)** | 상태: 실패함(Failed) · 코드 `FlowFailed` · 메시지 `@{concat('실패 액션: ', coalesce(first(body('Failed_actions'))?['name'], '?'))}`<br>**실행 후 구성**: 'Log_error' 이(가) 성공함, 실패함, 건너뜀 |  |

## P3P-F5 Teams 메시지 → 결정·액션 기록

**목적:** Teams 메시지 '추가 작업'에서 결정·결정요청·액션을 기록. 같은 메시지 두 번 기록 방지, 담당자 실존 확인.

**만들기:** 인스턴트 클라우드 흐름 · 흐름 이름 `P3P-F5 Teams 메시지 → 결정·액션 기록`

**트리거:** Microsoft Teams › **For a selected message** (선택한 메시지에 대해)

- Adaptive Card: `../automation_assets/cards/capture_decision_action.json` 파일 내용을 붙여넣기

| 단계 | 액션 이름(이름 바꾸기) | 추가할 액션 | 설정값 | 비고 |
|---|---|---|---|---|
| 1 | `Config` | 데이터 작업 › **작성(Compose)** | 입력(Inputs): `{"site": "{{SITE_URL}}", "me": "{{ME}}", "hostWorkbook": "{{HOST_WORKBOOK}}", "scriptFolder": "{{SCRIPT_FOLDER}}", "prototypeMode": true, "links": {"myActions": "{{VIEW_MY_ACTIONS}}", "decisionQueue": "{{VIEW_DECISION_QUEUE}}", "candidates": "{{VIEW_CANDIDATES}}"}}` | 설정값 모음. 샌드박스→운영 전환 시 이 값만 바꾼다(트리거의 사이트·목록은 직접 다시 선택). |
| 2 | `Try` | 컨트롤 › **범위(Scope)** | - |  |
| 2.1 | 　`Content` | 데이터 작업 › **작성(Compose)** | 입력(Inputs): `@{if(greater(length(coalesce(triggerBody()?['messagePayload']?['body']?['content'], '')), 1000), substring(triggerBody()?['messagePayload']?['body']?['content'], 0, 1000), coalesce(triggerBody()?['messagePayload']?['body']?['content'], ''))}` | 메시지 본문 앞 1,000자(근거로 저장) |
| 2.2 | 　`Inputs` | 데이터 작업 › **작성(Compose)** | 입력(Inputs): `{"kind": "@{coalesce(triggerBody()?['cardOutputs']?['kind'], '액션')}", "title": "@{trim(coalesce(triggerBody()?['cardOutputs']?['title'], ''))}", "owner": "@{toLower(if(empty(triggerBody()?['cardOutputs']?['ownerEmail']), outputs('Config')?['me'], trim(triggerBody()?['cardOutputs']?['ownerEmail'])))}", "due": "@{coalesce(triggerBody()?['cardOutputs']?['dueDate'], '')}", "decisionId": "@{trim(coalesce(triggerBody()?['cardOutputs']?['decisionId'], ''))}", "messageId": "@{coalesce(triggerBody()?['messagePayload']?['id'], '')}", "link": "@{coalesce(triggerBody()?['linkToMessage'], '')}"}` | 카드 입력값 정리(담당자 비면 나) |
| 2.3 | 　`Validate_inputs` | 컨트롤 › **조건(Condition)** | 왼쪽 값: **fx** `or(empty(outputs('Inputs')?['title']), empty(outputs('Inputs')?['messageId']))` · 연산자 **같음(is equal to)** · 오른쪽 값: **fx** `true` | 데이터 누락 방어 |
| 2.3.예 | 　　**'True(예)' 분기** | | | |
| 2.3.예.1 | 　　`Tell_missing` | Microsoft Teams › **Post message in a chat or channel** | 게시자(Post as): `Flow bot`<br>게시 위치(Post in): `Chat with Flow bot`<br>받는 사람(Recipient): `@{outputs('Config')?['me']}`<br>메시지(Message): `기록하지 않았습니다: 제목 또는 메시지 정보가 비어 있습니다.` | 본인에게 Flow bot 메시지 |
| 2.3.예.2 | 　　`Stop_missing` | 컨트롤 › **종료(Terminate)** | 상태: 실패함(Failed) · 코드 `InputMissing` · 메시지 `제목 또는 메시지 ID 누락` |  |
| 2.4 | 　`Check_owner` | Office 365 Users › **Get user profile (V2)** | 사용자(UPN): `@{outputs('Inputs')?['owner']}` | 담당자 이메일이 실제 사용자인지 확인 |
| 2.5 | 　`If_action` | 컨트롤 › **조건(Condition)** | 왼쪽 값: **fx** `equals(outputs('Inputs')?['kind'], '액션')` · 연산자 **같음(is equal to)** · 오른쪽 값: **fx** `true` | 종류별 분기: 액션 / 결정·결정요청 |
| 2.5.예 | 　　**'True(예)' 분기** | | | |
| 2.5.예.1 | 　　`Find_dup_action` | SharePoint › **Get items** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `ActionItems`<br>필터 쿼리(Filter Query): `SourceMessageId eq '@{replace(outputs('Inputs')?['messageId'], '''', '''''')}'`<br>상위 개수(Top Count): `1` | 같은 메시지 중복 확인 |
| 2.5.예.2 | 　　`If_dup_action` | 컨트롤 › **조건(Condition)** | 왼쪽 값: **fx** `greater(length(body('Find_dup_action')?['value']), 0)` · 연산자 **같음(is equal to)** · 오른쪽 값: **fx** `true` |  |
| 2.5.예.2.예 | 　　　**'True(예)' 분기** | | | |
| 2.5.예.2.예.1 | 　　　`Tell_dup_action` | Microsoft Teams › **Post message in a chat or channel** | 게시자(Post as): `Flow bot`<br>게시 위치(Post in): `Chat with Flow bot`<br>받는 사람(Recipient): `@{outputs('Config')?['me']}`<br>메시지(Message): `이미 기록된 메시지입니다(중복 생성 안 함).` | 본인에게 Flow bot 메시지 |
| 2.5.예.2.예.2 | 　　　`Stop_dup_action` | 컨트롤 › **종료(Terminate)** | 상태: 성공함(Succeeded) |  |
| 2.5.예.3 | 　　`Create_action` | SharePoint › **Create item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `ActionItems`<br>할 일 `Title`: `@{outputs('Inputs')?['title']}`<br>담당자 `Owner` (사람: 이메일): `@{outputs('Inputs')?['owner']}`<br>기한 `DueDate`: **fx** `if(empty(outputs('Inputs')?['due']), null, outputs('Inputs')?['due'])`<br>상태 `Status` (선택 값): `미착수`<br>유형 `ActionType` (선택 값): `실행`<br>출처 `Source` (선택 값): `Teams 메시지`<br>등록 경로 `CreatedVia` (선택 값): `Teams 메시지`<br>우선순위 `Priority` (선택 값): `보통`<br>원문 링크 `SourceLink`: `@{outputs('Inputs')?['link']}`<br>근거 문장 `Evidence`: `@{outputs('Content')}`<br>결정번호 `DecisionID`: `@{outputs('Inputs')?['decisionId']}`<br>원본 메시지 ID(시스템) `SourceMessageId`: `@{outputs('Inputs')?['messageId']}` | 액션 등록 |
| 2.5.아니요 | 　　**'False(아니요)' 분기** | | | |
| 2.5.아니요.1 | 　　`Find_dup_decision` | SharePoint › **Get items** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `DecisionLog`<br>필터 쿼리(Filter Query): `SourceMessageId eq '@{replace(outputs('Inputs')?['messageId'], '''', '''''')}'`<br>상위 개수(Top Count): `1` | 같은 메시지 중복 확인 |
| 2.5.아니요.2 | 　　`If_dup_decision` | 컨트롤 › **조건(Condition)** | 왼쪽 값: **fx** `greater(length(body('Find_dup_decision')?['value']), 0)` · 연산자 **같음(is equal to)** · 오른쪽 값: **fx** `true` |  |
| 2.5.아니요.2.예 | 　　　**'True(예)' 분기** | | | |
| 2.5.아니요.2.예.1 | 　　　`Tell_dup_decision` | Microsoft Teams › **Post message in a chat or channel** | 게시자(Post as): `Flow bot`<br>게시 위치(Post in): `Chat with Flow bot`<br>받는 사람(Recipient): `@{outputs('Config')?['me']}`<br>메시지(Message): `이미 기록된 메시지입니다(중복 생성 안 함).` | 본인에게 Flow bot 메시지 |
| 2.5.아니요.2.예.2 | 　　　`Stop_dup_decision` | 컨트롤 › **종료(Terminate)** | 상태: 성공함(Succeeded) |  |
| 2.5.아니요.3 | 　　`Create_decision` | SharePoint › **Create item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `DecisionLog`<br>결정 제목 `Title`: `@{outputs('Inputs')?['title']}`<br>결정 내용 `DecisionText`: `@{concat(outputs('Inputs')?['title'], ' / 원문: ', outputs('Content'))}`<br>상태 `Status` (선택 값): `@{if(equals(outputs('Inputs')?['kind'], '결정요청'), '결정요청', '확정')}`<br>결정권자 `Decider` (사람: 이메일): `@{outputs('Inputs')?['owner']}`<br>결정 요청자 `RequestedBy` (사람: 이메일): `@{outputs('Config')?['me']}`<br>원문 링크 `SourceLink`: `@{outputs('Inputs')?['link']}`<br>등록 경로 `CreatedVia` (선택 값): `Teams 메시지`<br>원본 메시지 ID(시스템) `SourceMessageId`: `@{outputs('Inputs')?['messageId']}` | 결정 또는 결정요청 등록 |
| 2.6 | 　`Tell_done` | Microsoft Teams › **Post message in a chat or channel** | 게시자(Post as): `Flow bot`<br>게시 위치(Post in): `Chat with Flow bot`<br>받는 사람(Recipient): `@{outputs('Config')?['me']}`<br>메시지(Message): `@{concat('기록됨(', outputs('Inputs')?['kind'], '): ', outputs('Inputs')?['title'], ' — 번호는 잠시 후 목록에서 확인')}` | 본인에게 Flow bot 메시지 |
| 3 | `Catch` | 컨트롤 › **범위(Scope)** | **실행 후 구성**: 'Try' 이(가) 실패함, 시간 초과됨 | 실행 후 구성: Try가 '실패함'·'시간 초과됨'일 때 |
| 3.1 | 　`Failed_actions` | 데이터 작업 › **배열 필터링(Filter array)** | 보낸 사람(From): **fx** `result('Try')` · '고급 모드에서 편집' 후: `@equals(item()?['status'], 'Failed')` | Try 안에서 실패한 액션만 추림 |
| 3.2 | 　`Log_error` | SharePoint › **Create item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `FlowErrorLog`<br>Flow 이름 `Title`: `@{workflow()?['tags']?['flowDisplayName']}`<br>실행 ID `FlowRunId`: `@{workflow()?['run']?['name']}`<br>실패 액션 `FailedAction`: `@{coalesce(first(body('Failed_actions'))?['name'], '')}`<br>오류 메시지 `ErrorMessage`: `@{coalesce(first(body('Failed_actions'))?['error']?['message'], '상세 메시지 없음(실행 기록 확인)')}`<br>심각도 `Severity` (선택 값): `Critical`<br>조치완료 `Resolved`: `false`(식 탭)<br>실행 기록 링크 `RunUrl`: `@{concat('https://make.powerautomate.com/environments/', workflow()?['tags']?['environmentName'], '/flows/', workflow()?['name'], '/runs/', workflow()?['run']?['name'])}` | 공통 오류 로그 기록 |
| 3.3 | 　`Terminate_failed` | 컨트롤 › **종료(Terminate)** | 상태: 실패함(Failed) · 코드 `FlowFailed` · 메시지 `@{concat('실패 액션: ', coalesce(first(body('Failed_actions'))?['name'], '?'))}`<br>**실행 후 구성**: 'Log_error' 이(가) 성공함, 실패함, 건너뜀 |  |

## P3P-F6 아침 브리핑

**목적:** 평일 07:40 본인에게 '오늘 먼저 처리할 5가지' 카드. 계산은 Office Scripts, Teams 실패 시 본인 메일로 대체.

**만들기:** 예약된 클라우드 흐름 · 흐름 이름 `P3P-F6 아침 브리핑`

**트리거:** 일정 › **Recurrence(되풀이)**

- 간격 1 / 빈도 **주(Week)** · 표준 시간대 **(UTC+09:00) Seoul** · 요일 월~금 · 시간 7 · 분 40

| 단계 | 액션 이름(이름 바꾸기) | 추가할 액션 | 설정값 | 비고 |
|---|---|---|---|---|
| 1 | `Config` | 데이터 작업 › **작성(Compose)** | 입력(Inputs): `{"site": "{{SITE_URL}}", "me": "{{ME}}", "hostWorkbook": "{{HOST_WORKBOOK}}", "scriptFolder": "{{SCRIPT_FOLDER}}", "prototypeMode": true, "links": {"myActions": "{{VIEW_MY_ACTIONS}}", "decisionQueue": "{{VIEW_DECISION_QUEUE}}", "candidates": "{{VIEW_CANDIDATES}}"}}` | 설정값 모음. 샌드박스→운영 전환 시 이 값만 바꾼다(트리거의 사이트·목록은 직접 다시 선택). |
| 2 | `Today` | 데이터 작업 › **작성(Compose)** | 입력(Inputs): `@{convertFromUtc(utcNow(), 'Korea Standard Time', 'yyyy-MM-dd')}` | 오늘(KST) |
| 3 | `DayStartUtc` | 데이터 작업 › **작성(Compose)** | 입력(Inputs): `@{convertToUtc(concat(outputs('Today'), 'T00:00:00'), 'Korea Standard Time')}` | 오늘 0시(KST)를 UTC로 |
| 4 | `Try` | 컨트롤 › **범위(Scope)** | - |  |
| 4.1 | 　`Get_holidays` | SharePoint › **Get items** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `Holidays`<br>상위 개수(Top Count): `500` | 휴무일 |
| 4.2 | 　`Get_events` | Office 365 Outlook › **Get calendar view of events (V3)** | 일정 ID(Calendar id): `Calendar`<br>시작 시간(Start Time): `@{outputs('DayStartUtc')}`<br>종료 시간(End Time): `@{addDays(outputs('DayStartUtc'), 1)}` | 오늘 일정 |
| 4.3 | 　`Get_my_actions` | SharePoint › **Get items** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `ActionItems`<br>필터 쿼리(Filter Query): `Owner/EMail eq '@{outputs('Config')?['me']}' and (Status eq '미착수' or Status eq '진행중')`<br>상위 개수(Top Count): `500` | 내 미결 액션 |
| 4.4 | 　`Get_my_decisions` | SharePoint › **Get items** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `DecisionLog`<br>필터 쿼리(Filter Query): `Status eq '결정요청' and Decider/EMail eq '@{outputs('Config')?['me']}'`<br>상위 개수(Top Count): `200` | 내가 결정할 대기 건 |
| 4.5 | 　`Run_brief` | Excel Online (Business) › **Run script from SharePoint library** | 통합 문서(Workbook) 위치·파일: `@{outputs('Config')?['hostWorkbook']}`<br>스크립트(Script) 위치·파일: `@{outputs('Config')?['scriptFolder']}/BuildDailyBrief.osts`<br>매개변수 `meEmail`: `@{outputs('Config')?['me']}`<br>매개변수 `todayKst`: `@{outputs('Today')}`<br>매개변수 `eventsJson`: `@{string(body('Get_events')?['value'])}`<br>매개변수 `actionsJson`: `@{string(body('Get_my_actions')?['value'])}`<br>매개변수 `decisionsJson`: `@{string(body('Get_my_decisions')?['value'])}`<br>매개변수 `requestsJson`: `[]`<br>매개변수 `holidaysJson`: `@{string(body('Get_holidays')?['value'])}`<br>매개변수 `linksJson`: `@{string(outputs('Config')?['links'])}` | 점수 계산·카드 생성(Office Scripts) |
| 4.6 | 　`If_skip` | 컨트롤 › **조건(Condition)** | 왼쪽 값: **fx** `equals(body('Run_brief')?['result']?['skip'], true)` · 연산자 **같음(is equal to)** · 오른쪽 값: **fx** `true` | 주말·휴무일이면 게시 안 함 |
| 4.6.예 | 　　**'True(예)' 분기** | | | |
| 4.6.예.1 | 　　`Stop_skip` | 컨트롤 › **종료(Terminate)** | 상태: 성공함(Succeeded) |  |
| 4.7 | 　`Post_card` | Microsoft Teams › **Post card in a chat or channel** | 게시자(Post as): `Flow bot`<br>게시 위치(Post in): `Chat with Flow bot`<br>받는 사람(Recipient): `@{outputs('Config')?['me']}`<br>Adaptive Card: `@{body('Run_brief')?['result']?['cardJson']}` | 본인에게 Flow bot 채팅으로 카드 게시 |
| 5 | `Catch` | 컨트롤 › **범위(Scope)** | **실행 후 구성**: 'Try' 이(가) 실패함, 시간 초과됨 | 실행 후 구성: Try가 '실패함'·'시간 초과됨'일 때 |
| 5.1 | 　`Failed_actions` | 데이터 작업 › **배열 필터링(Filter array)** | 보낸 사람(From): **fx** `result('Try')` · '고급 모드에서 편집' 후: `@equals(item()?['status'], 'Failed')` | Try 안에서 실패한 액션만 추림 |
| 5.2 | 　`Log_error` | SharePoint › **Create item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `FlowErrorLog`<br>Flow 이름 `Title`: `@{workflow()?['tags']?['flowDisplayName']}`<br>실행 ID `FlowRunId`: `@{workflow()?['run']?['name']}`<br>실패 액션 `FailedAction`: `@{coalesce(first(body('Failed_actions'))?['name'], '')}`<br>오류 메시지 `ErrorMessage`: `@{coalesce(first(body('Failed_actions'))?['error']?['message'], '상세 메시지 없음(실행 기록 확인)')}`<br>심각도 `Severity` (선택 값): `Critical`<br>조치완료 `Resolved`: `false`(식 탭)<br>실행 기록 링크 `RunUrl`: `@{concat('https://make.powerautomate.com/environments/', workflow()?['tags']?['environmentName'], '/flows/', workflow()?['name'], '/runs/', workflow()?['run']?['name'])}` | 공통 오류 로그 기록 |
| 5.3 | 　`If_teams_failed` | 컨트롤 › **조건(Condition)** | 왼쪽 값: **fx** `equals(first(body('Failed_actions'))?['name'], 'Post_card')` · 연산자 **같음(is equal to)** · 오른쪽 값: **fx** `true` | Teams 실패 시 대체 |
| 5.3.예 | 　　**'True(예)' 분기** | | | |
| 5.3.예.1 | 　　`Email_fallback` | Office 365 Outlook › **Send an email (V2)** | 받는 사람(To): `@{outputs('Config')?['me']}`<br>제목(Subject): `[아침 브리핑] Teams 게시 실패 — 메일로 대체`<br>본문(Body): `@{body('Run_brief')?['result']?['htmlSummary']}` | Teams 카드 실패 시 본인 메일로 대체 발송 |
| 5.4 | 　`Terminate_failed` | 컨트롤 › **종료(Terminate)** | 상태: 실패함(Failed) · 코드 `FlowFailed` · 메시지 `@{concat('실패 액션: ', coalesce(first(body('Failed_actions'))?['name'], '?'))}`<br>**실행 후 구성**: 'If_teams_failed' 이(가) 성공함, 실패함, 건너뜀 |  |

## P3P-F7 액션 리마인더(담당자별 하루 1장)

**목적:** 평일 08:30 기한 D-1·당일·초과 액션을 담당자별 1장으로 알림. 같은 날 재알림 없음. 프로토타입 모드는 본인에게만.

**만들기:** 예약된 클라우드 흐름 · 흐름 이름 `P3P-F7 액션 리마인더(담당자별 하루 1장)`

**트리거:** 일정 › **Recurrence(되풀이)**

- 간격 1 / 빈도 **주(Week)** · 표준 시간대 **(UTC+09:00) Seoul** · 요일 월~금 · 시간 8 · 분 30

| 단계 | 액션 이름(이름 바꾸기) | 추가할 액션 | 설정값 | 비고 |
|---|---|---|---|---|
| 1 | `Config` | 데이터 작업 › **작성(Compose)** | 입력(Inputs): `{"site": "{{SITE_URL}}", "me": "{{ME}}", "hostWorkbook": "{{HOST_WORKBOOK}}", "scriptFolder": "{{SCRIPT_FOLDER}}", "prototypeMode": true, "links": {"myActions": "{{VIEW_MY_ACTIONS}}", "decisionQueue": "{{VIEW_DECISION_QUEUE}}", "candidates": "{{VIEW_CANDIDATES}}"}}` | 설정값 모음. 샌드박스→운영 전환 시 이 값만 바꾼다(트리거의 사이트·목록은 직접 다시 선택). |
| 2 | `Today` | 데이터 작업 › **작성(Compose)** | 입력(Inputs): `@{convertFromUtc(utcNow(), 'Korea Standard Time', 'yyyy-MM-dd')}` | 오늘(KST) |
| 3 | `DayStartUtc` | 데이터 작업 › **작성(Compose)** | 입력(Inputs): `@{convertToUtc(concat(outputs('Today'), 'T00:00:00'), 'Korea Standard Time')}` | 오늘 0시(KST)를 UTC로 |
| 4 | `Init_skipped` | 변수 › **변수 초기화(Initialize variable)** | 이름 `varSkipped`, 형식 Array, 값 `[]` |  |
| 5 | `Try` | 컨트롤 › **범위(Scope)** | - |  |
| 5.1 | 　`Get_holidays` | SharePoint › **Get items** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `Holidays`<br>상위 개수(Top Count): `500` | 휴무일 |
| 5.2 | 　`Get_due_actions` | SharePoint › **Get items** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `ActionItems`<br>필터 쿼리(Filter Query): `(Status eq '미착수' or Status eq '진행중') and DueDate le '@{addDays(outputs('Today'), 1, 'yyyy-MM-dd')}'`<br>상위 개수(Top Count): `2000` | 내일까지 기한인 미결 액션 |
| 5.3 | 　`Run_digest` | Excel Online (Business) › **Run script from SharePoint library** | 통합 문서(Workbook) 위치·파일: `@{outputs('Config')?['hostWorkbook']}`<br>스크립트(Script) 위치·파일: `@{outputs('Config')?['scriptFolder']}/BuildReminderDigest.osts`<br>매개변수 `todayKst`: `@{outputs('Today')}`<br>매개변수 `actionsJson`: `@{string(body('Get_due_actions')?['value'])}`<br>매개변수 `holidaysJson`: `@{string(body('Get_holidays')?['value'])}`<br>매개변수 `viewUrl`: `@{outputs('Config')?['links']?['myActions']}` | 담당자별 카드 생성(Office Scripts) |
| 5.4 | 　`If_skip` | 컨트롤 › **조건(Condition)** | 왼쪽 값: **fx** `equals(body('Run_digest')?['result']?['skip'], true)` · 연산자 **같음(is equal to)** · 오른쪽 값: **fx** `true` |  |
| 5.4.예 | 　　**'True(예)' 분기** | | | |
| 5.4.예.1 | 　　`Stop_skip` | 컨트롤 › **종료(Terminate)** | 상태: 성공함(Succeeded) |  |
| 5.5 | 　`For_each_digest` | 컨트롤 › **각각에 적용(Apply to each)** | 이전 단계에서 출력 선택: **fx** `body('Run_digest')?['result']?['digests']` · 설정 › 동시성 제어 **켬, 병렬 처리 수준 1** | 담당자별 반복(동시성 1) |
| 5.5.1 | 　　`If_allowed` | 컨트롤 › **조건(Condition)** | 왼쪽 값: **fx** `or(not(outputs('Config')?['prototypeMode']), equals(toLower(items('For_each_digest')?['ownerEmail']), toLower(outputs('Config')?['me'])))` · 연산자 **같음(is equal to)** · 오른쪽 값: **fx** `true` | 프로토타입 모드에서는 본인에게만 발송 |
| 5.5.1.예 | 　　　**'True(예)' 분기** | | | |
| 5.5.1.예.1 | 　　　`Post_digest` | Microsoft Teams › **Post card in a chat or channel** | 게시자(Post as): `Flow bot`<br>게시 위치(Post in): `Chat with Flow bot`<br>받는 사람(Recipient): `@{items('For_each_digest')?['ownerEmail']}`<br>Adaptive Card: `@{items('For_each_digest')?['cardJson']}` | 담당자에게 카드 |
| 5.5.1.예.2 | 　　　`For_each_item` | 컨트롤 › **각각에 적용(Apply to each)** | 이전 단계에서 출력 선택: **fx** `items('For_each_digest')?['itemIds']` · 설정 › 동시성 제어 **켬, 병렬 처리 수준 1** | 알린 항목 기록 |
| 5.5.1.예.2.1 | 　　　　`Get_action` | SharePoint › **Get item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `ActionItems`<br>ID: **fx** `items('For_each_item')` | 현재 값 읽기(Update 필수 입력용) |
| 5.5.1.예.2.2 | 　　　　`Mark_reminded` | SharePoint › **Update item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `ActionItems`<br>ID: **fx** `items('For_each_item')`<br>할 일 `Title`: `@{body('Get_action')?['Title']}`<br>담당자 `Owner` (사람: 이메일): `@{body('Get_action')?['Owner']?['Claims']}`<br>상태 `Status` (선택 값): `@{body('Get_action')?['Status']?['Value']}`<br>유형 `ActionType` (선택 값): `@{body('Get_action')?['ActionType']?['Value']}`<br>리마인더 횟수 `ReminderCount`: **fx** `add(coalesce(body('Get_action')?['ReminderCount'], 0), 1)`<br>최근 리마인더 `LastRemindedAt`: `@{utcNow()}` | 리마인더 횟수·시각 기록 |
| 5.5.1.아니요 | 　　　**'False(아니요)' 분기** | | | |
| 5.5.1.아니요.1 | 　　　`Remember_skipped` | 변수 › **배열 변수에 추가(Append to array variable)** | 이름 `varSkipped`, 값 **fx** `items('For_each_digest')?['ownerEmail']` |  |
| 5.6 | 　`If_any_skipped` | 컨트롤 › **조건(Condition)** | 왼쪽 값: **fx** `greater(length(variables('varSkipped')), 0)` · 연산자 **같음(is equal to)** · 오른쪽 값: **fx** `true` |  |
| 5.6.예 | 　　**'True(예)' 분기** | | | |
| 5.6.예.1 | 　　`Tell_skipped` | Microsoft Teams › **Post message in a chat or channel** | 게시자(Post as): `Flow bot`<br>게시 위치(Post in): `Chat with Flow bot`<br>받는 사람(Recipient): `@{outputs('Config')?['me']}`<br>메시지(Message): `@{concat('프로토타입 모드: 다른 담당자 ', string(length(variables('varSkipped'))), '명에게는 발송하지 않았습니다.')}` | 본인에게 Flow bot 메시지 |
| 6 | `Catch` | 컨트롤 › **범위(Scope)** | **실행 후 구성**: 'Try' 이(가) 실패함, 시간 초과됨 | 실행 후 구성: Try가 '실패함'·'시간 초과됨'일 때 |
| 6.1 | 　`Failed_actions` | 데이터 작업 › **배열 필터링(Filter array)** | 보낸 사람(From): **fx** `result('Try')` · '고급 모드에서 편집' 후: `@equals(item()?['status'], 'Failed')` | Try 안에서 실패한 액션만 추림 |
| 6.2 | 　`Log_error` | SharePoint › **Create item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `FlowErrorLog`<br>Flow 이름 `Title`: `@{workflow()?['tags']?['flowDisplayName']}`<br>실행 ID `FlowRunId`: `@{workflow()?['run']?['name']}`<br>실패 액션 `FailedAction`: `@{coalesce(first(body('Failed_actions'))?['name'], '')}`<br>오류 메시지 `ErrorMessage`: `@{coalesce(first(body('Failed_actions'))?['error']?['message'], '상세 메시지 없음(실행 기록 확인)')}`<br>심각도 `Severity` (선택 값): `Critical`<br>조치완료 `Resolved`: `false`(식 탭)<br>실행 기록 링크 `RunUrl`: `@{concat('https://make.powerautomate.com/environments/', workflow()?['tags']?['environmentName'], '/flows/', workflow()?['name'], '/runs/', workflow()?['run']?['name'])}` | 공통 오류 로그 기록 |
| 6.3 | 　`Terminate_failed` | 컨트롤 › **종료(Terminate)** | 상태: 실패함(Failed) · 코드 `FlowFailed` · 메시지 `@{concat('실패 액션: ', coalesce(first(body('Failed_actions'))?['name'], '?'))}`<br>**실행 후 구성**: 'Log_error' 이(가) 성공함, 실패함, 건너뜀 |  |

## P3P-F8 Copilot 추출 결과 검증 → 후보 생성

**목적:** 회의 추출 접수(MeetingIntake)에 Copilot 결과를 붙여넣으면 가드 검증 후 후보를 만든다. 등록은 하지 않는다.

**만들기:** 자동화된 클라우드 흐름 · 흐름 이름 `P3P-F8 Copilot 추출 결과 검증 → 후보 생성`

**트리거:** SharePoint › **When an item is created or modified** (항목을 만들거나 수정한 경우)

- 사이트 주소: `{{SITE_URL}}` · 목록 이름: `MeetingIntake`
- 트리거 카드 **… › 설정(Settings) › 트리거 조건(Trigger conditions) › + 추가**: `@or(equals(triggerOutputs()?['body/Status/Value'], '접수'), equals(triggerOutputs()?['body/Status/Value'], '재검증요청'))`

| 단계 | 액션 이름(이름 바꾸기) | 추가할 액션 | 설정값 | 비고 |
|---|---|---|---|---|
| 1 | `Config` | 데이터 작업 › **작성(Compose)** | 입력(Inputs): `{"site": "{{SITE_URL}}", "me": "{{ME}}", "hostWorkbook": "{{HOST_WORKBOOK}}", "scriptFolder": "{{SCRIPT_FOLDER}}", "prototypeMode": true, "links": {"myActions": "{{VIEW_MY_ACTIONS}}", "decisionQueue": "{{VIEW_DECISION_QUEUE}}", "candidates": "{{VIEW_CANDIDATES}}"}}` | 설정값 모음. 샌드박스→운영 전환 시 이 값만 바꾼다(트리거의 사이트·목록은 직접 다시 선택). |
| 2 | `Try` | 컨트롤 › **범위(Scope)** | - |  |
| 2.1 | 　`Get_roster` | SharePoint › **Get items** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `TeamRoster`<br>상위 개수(Top Count): `500` | 팀 명부(담당자 매핑 근거) |
| 2.2 | 　`Run_guard` | Excel Online (Business) › **Run script from SharePoint library** | 통합 문서(Workbook) 위치·파일: `@{outputs('Config')?['hostWorkbook']}`<br>스크립트(Script) 위치·파일: `@{outputs('Config')?['scriptFolder']}/GuardExtraction.osts`<br>매개변수 `transcript`: `@{triggerOutputs()?['body/Transcript']}`<br>매개변수 `rosterJson`: `@{string(body('Get_roster')?['value'])}`<br>매개변수 `extractionJson`: `@{triggerOutputs()?['body/ExtractionJson']}`<br>매개변수 `meetingDate`: `@{formatDateTime(triggerOutputs()?['body/MeetingDate'], 'yyyy-MM-dd')}` | G1~G6 검증(Office Scripts) |
| 2.3 | 　`Get_old_candidates` | SharePoint › **Get items** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `ActionCandidates`<br>필터 쿼리(Filter Query): `IntakeID eq @{triggerOutputs()?['body/ID']} and Status eq '제안'`<br>상위 개수(Top Count): `500` | 재검증 시 이전 '제안' 후보 |
| 2.4 | 　`Supersede_old` | 컨트롤 › **각각에 적용(Apply to each)** | 이전 단계에서 출력 선택: **fx** `body('Get_old_candidates')?['value']` · 설정 › 동시성 제어 **켬, 병렬 처리 수준 1** | 이전 후보는 삭제하지 않고 '기각' 처리(이력 보존) |
| 2.4.1 | 　　`Mark_superseded` | SharePoint › **Update item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `ActionCandidates`<br>ID: **fx** `items('Supersede_old')?['ID']`<br>후보 내용 `Title`: `@{items('Supersede_old')?['Title']}`<br>종류 `Kind` (선택 값): `@{items('Supersede_old')?['Kind']?['Value']}`<br>접수 항목 ID `IntakeID`: **fx** `items('Supersede_old')?['IntakeID']`<br>가드 판정 `Verdict` (선택 값): `@{items('Supersede_old')?['Verdict']?['Value']}`<br>처리 `Status` (선택 값): `기각` | 기각 |
| 2.5 | 　`If_parsed` | 컨트롤 › **조건(Condition)** | 왼쪽 값: **fx** `equals(body('Run_guard')?['result']?['ok'], true)` · 연산자 **같음(is equal to)** · 오른쪽 값: **fx** `true` | JSON 해석 성공 여부 |
| 2.5.예 | 　　**'True(예)' 분기** | | | |
| 2.5.예.1 | 　　`Create_candidates` | 컨트롤 › **각각에 적용(Apply to each)** | 이전 단계에서 출력 선택: **fx** `body('Run_guard')?['result']?['candidates']` · 설정 › 동시성 제어 **켬, 병렬 처리 수준 1** | 후보 1건 = 1행 |
| 2.5.예.1.1 | 　　　`Create_candidate` | SharePoint › **Create item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `ActionCandidates`<br>후보 내용 `Title`: `@{if(greater(length(items('Create_candidates')?['title']), 250), substring(items('Create_candidates')?['title'], 0, 250), items('Create_candidates')?['title'])}`<br>종류 `Kind` (선택 값): `@{items('Create_candidates')?['kind']}`<br>접수 항목 ID `IntakeID`: **fx** `triggerOutputs()?['body/ID']`<br>추출 순번 `Ref`: **fx** `items('Create_candidates')?['ref']`<br>회의명 `MeetingName`: `@{triggerOutputs()?['body/Title']}`<br>회의일 `MeetingDate`: `@{formatDateTime(triggerOutputs()?['body/MeetingDate'], 'yyyy-MM-dd')}`<br>담당자(추출 이름) `OwnerName`: `@{items('Create_candidates')?['ownerName']}`<br>담당자 이메일(확인·수정 가능) `OwnerEmail`: `@{items('Create_candidates')?['ownerEmail']}`<br>기한(확인·수정 가능) `DueDate`: **fx** `if(empty(items('Create_candidates')?['dueDate']), null, items('Create_candidates')?['dueDate'])`<br>근거 문장 `Evidence`: `@{items('Create_candidates')?['evidence']}`<br>가드 판정 `Verdict` (선택 값): `@{items('Create_candidates')?['verdict']}`<br>검토 사유 `Reasons`: `@{items('Create_candidates')?['reasons']}`<br>처리 `Status` (선택 값): `제안` | 후보 등록(상태: 제안) |
| 2.5.예.2 | 　　`Mark_intake_done` | SharePoint › **Update item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `MeetingIntake`<br>ID: **fx** `triggerOutputs()?['body/ID']`<br>회의명 `Title`: `@{triggerOutputs()?['body/Title']}`<br>회의일 `MeetingDate`: `@{triggerOutputs()?['body/MeetingDate']}`<br>회의록 원문 `Transcript`: `@{triggerOutputs()?['body/Transcript']}`<br>Copilot 추출 결과 `ExtractionJson`: `@{triggerOutputs()?['body/ExtractionJson']}`<br>처리 상태 `Status` (선택 값): `검증완료`<br>추천 후보 수 `RecommendedCount`: **fx** `body('Run_guard')?['result']?['recommendedCount']`<br>검토필요 후보 수 `ReviewCount`: **fx** `body('Run_guard')?['result']?['reviewCount']`<br>검증 요약 `ResultSummary`: `@{concat('추천 ', string(body('Run_guard')?['result']?['recommendedCount']), '건 · 검토필요 ', string(body('Run_guard')?['result']?['reviewCount']), '건', if(empty(body('Run_guard')?['result']?['schemaErrors']), '', concat(' · 형식 오류: ', join(body('Run_guard')?['result']?['schemaErrors'], '; '))))}`<br>처리 시각 `ProcessedAt`: `@{utcNow()}` | 접수 완료 표시(자기 재실행 차단) |
| 2.5.예.3 | 　　`Tell_candidates` | Microsoft Teams › **Post message in a chat or channel** | 게시자(Post as): `Flow bot`<br>게시 위치(Post in): `Chat with Flow bot`<br>받는 사람(Recipient): `@{outputs('Config')?['me']}`<br>메시지(Message): `@{concat('회의 "', triggerOutputs()?['body/Title'], '" 후보 ', string(length(body('Run_guard')?['result']?['candidates'])), '건(추천 ', string(body('Run_guard')?['result']?['recommendedCount']), ') — 확인 후 승인하세요: ', outputs('Config')?['links']?['candidates'])}` | 본인에게 Flow bot 메시지 |
| 2.5.아니요 | 　　**'False(아니요)' 분기** | | | |
| 2.5.아니요.1 | 　　`Mark_intake_error` | SharePoint › **Update item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `MeetingIntake`<br>ID: **fx** `triggerOutputs()?['body/ID']`<br>회의명 `Title`: `@{triggerOutputs()?['body/Title']}`<br>회의일 `MeetingDate`: `@{triggerOutputs()?['body/MeetingDate']}`<br>회의록 원문 `Transcript`: `@{triggerOutputs()?['body/Transcript']}`<br>Copilot 추출 결과 `ExtractionJson`: `@{triggerOutputs()?['body/ExtractionJson']}`<br>처리 상태 `Status` (선택 값): `오류`<br>검증 요약 `ResultSummary`: `@{body('Run_guard')?['result']?['parseError']}`<br>처리 시각 `ProcessedAt`: `@{utcNow()}` | 오류 표시 |
| 2.5.아니요.2 | 　　`Tell_parse_error` | Microsoft Teams › **Post message in a chat or channel** | 게시자(Post as): `Flow bot`<br>게시 위치(Post in): `Chat with Flow bot`<br>받는 사람(Recipient): `@{outputs('Config')?['me']}`<br>메시지(Message): `@{concat('회의 "', triggerOutputs()?['body/Title'], '" 추출 결과를 읽지 못했습니다: ', body('Run_guard')?['result']?['parseError'])}` | 본인에게 Flow bot 메시지 |
| 3 | `Catch` | 컨트롤 › **범위(Scope)** | **실행 후 구성**: 'Try' 이(가) 실패함, 시간 초과됨 | 실행 후 구성: Try가 '실패함'·'시간 초과됨'일 때 |
| 3.1 | 　`Failed_actions` | 데이터 작업 › **배열 필터링(Filter array)** | 보낸 사람(From): **fx** `result('Try')` · '고급 모드에서 편집' 후: `@equals(item()?['status'], 'Failed')` | Try 안에서 실패한 액션만 추림 |
| 3.2 | 　`Log_error` | SharePoint › **Create item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `FlowErrorLog`<br>Flow 이름 `Title`: `@{workflow()?['tags']?['flowDisplayName']}`<br>실행 ID `FlowRunId`: `@{workflow()?['run']?['name']}`<br>실패 액션 `FailedAction`: `@{coalesce(first(body('Failed_actions'))?['name'], '')}`<br>오류 메시지 `ErrorMessage`: `@{coalesce(first(body('Failed_actions'))?['error']?['message'], '상세 메시지 없음(실행 기록 확인)')}`<br>심각도 `Severity` (선택 값): `Critical`<br>조치완료 `Resolved`: `false`(식 탭)<br>실행 기록 링크 `RunUrl`: `@{concat('https://make.powerautomate.com/environments/', workflow()?['tags']?['environmentName'], '/flows/', workflow()?['name'], '/runs/', workflow()?['run']?['name'])}` | 공통 오류 로그 기록 |
| 3.3 | 　`Terminate_failed` | 컨트롤 › **종료(Terminate)** | 상태: 실패함(Failed) · 코드 `FlowFailed` · 메시지 `@{concat('실패 액션: ', coalesce(first(body('Failed_actions'))?['name'], '?'))}`<br>**실행 후 구성**: 'Log_error' 이(가) 성공함, 실패함, 건너뜀 |  |

## P3P-F9 승인된 후보 → 결정·액션 등록

**목적:** 사람이 ActionCandidates에서 '승인'으로 바꾼 후보만 등록. 최신 값 재확인으로 중복 등록 방지, 실패 시 후보에 사유 표시.

**만들기:** 자동화된 클라우드 흐름 · 흐름 이름 `P3P-F9 승인된 후보 → 결정·액션 등록`

**트리거:** SharePoint › **When an item is created or modified** (항목을 만들거나 수정한 경우)

- 사이트 주소: `{{SITE_URL}}` · 목록 이름: `ActionCandidates`
- 트리거 카드 **… › 설정(Settings) › 트리거 조건(Trigger conditions) › + 추가**: `@and(equals(triggerOutputs()?['body/Status/Value'], '승인'), empty(triggerOutputs()?['body/CreatedItemID']))`
- 트리거 **설정 › 동시성 제어(Concurrency control) 켬 › 병렬 처리 수준 1** (한 번 켜면 되돌리려면 트리거를 다시 만들어야 함)

| 단계 | 액션 이름(이름 바꾸기) | 추가할 액션 | 설정값 | 비고 |
|---|---|---|---|---|
| 1 | `Config` | 데이터 작업 › **작성(Compose)** | 입력(Inputs): `{"site": "{{SITE_URL}}", "me": "{{ME}}", "hostWorkbook": "{{HOST_WORKBOOK}}", "scriptFolder": "{{SCRIPT_FOLDER}}", "prototypeMode": true, "links": {"myActions": "{{VIEW_MY_ACTIONS}}", "decisionQueue": "{{VIEW_DECISION_QUEUE}}", "candidates": "{{VIEW_CANDIDATES}}"}}` | 설정값 모음. 샌드박스→운영 전환 시 이 값만 바꾼다(트리거의 사이트·목록은 직접 다시 선택). |
| 2 | `Try` | 컨트롤 › **범위(Scope)** | - |  |
| 2.1 | 　`Recheck` | SharePoint › **Get item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `ActionCandidates`<br>ID: **fx** `triggerOutputs()?['body/ID']` | 최신 값 재확인(동시 수정·중복 실행 방어) |
| 2.2 | 　`If_already` | 컨트롤 › **조건(Condition)** | 왼쪽 값: **fx** `not(and(equals(body('Recheck')?['Status']?['Value'], '승인'), empty(body('Recheck')?['CreatedItemID'])))` · 연산자 **같음(is equal to)** · 오른쪽 값: **fx** `true` |  |
| 2.2.예 | 　　**'True(예)' 분기** | | | |
| 2.2.예.1 | 　　`Stop_already` | 컨트롤 › **종료(Terminate)** | 상태: 성공함(Succeeded) |  |
| 2.3 | 　`If_kind_action` | 컨트롤 › **조건(Condition)** | 왼쪽 값: **fx** `equals(body('Recheck')?['Kind']?['Value'], '액션')` · 연산자 **같음(is equal to)** · 오른쪽 값: **fx** `true` | 종류별 등록 |
| 2.3.예 | 　　**'True(예)' 분기** | | | |
| 2.3.예.1 | 　　`Validate_owner` | Office 365 Users › **Get user profile (V2)** | 사용자(UPN): `@{body('Recheck')?['OwnerEmail']}` | 담당자 실존 확인(비어 있으면 실패) |
| 2.3.예.2 | 　　`Create_action` | SharePoint › **Create item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `ActionItems`<br>할 일 `Title`: `@{body('Recheck')?['Title']}`<br>담당자 `Owner` (사람: 이메일): `@{body('Validate_owner')?['mail']}`<br>기한 `DueDate`: **fx** `if(empty(body('Recheck')?['DueDate']), null, body('Recheck')?['DueDate'])`<br>상태 `Status` (선택 값): `미착수`<br>유형 `ActionType` (선택 값): `실행`<br>출처 `Source` (선택 값): `회의`<br>우선순위 `Priority` (선택 값): `보통`<br>근거 문장 `Evidence`: `@{body('Recheck')?['Evidence']}`<br>등록 경로 `CreatedVia` (선택 값): `AI 제안 승인` | 액션 등록 |
| 2.3.예.3 | 　　`Mark_done_action` | SharePoint › **Update item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `ActionCandidates`<br>ID: **fx** `triggerOutputs()?['body/ID']`<br>후보 내용 `Title`: `@{body('Recheck')?['Title']}`<br>종류 `Kind` (선택 값): `@{body('Recheck')?['Kind']?['Value']}`<br>접수 항목 ID `IntakeID`: **fx** `body('Recheck')?['IntakeID']`<br>가드 판정 `Verdict` (선택 값): `@{body('Recheck')?['Verdict']?['Value']}`<br>처리 `Status` (선택 값): `등록완료`<br>등록된 항목 ID(시스템) `CreatedItemID`: `@{string(body('Create_action')?['ID'])}` | 등록완료 표시 |
| 2.3.아니요 | 　　**'False(아니요)' 분기** | | | |
| 2.3.아니요.1 | 　　`Create_decision` | SharePoint › **Create item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `DecisionLog`<br>결정 제목 `Title`: `@{body('Recheck')?['Title']}`<br>결정 내용 `DecisionText`: `@{concat(body('Recheck')?['Title'], ' / 근거: ', coalesce(body('Recheck')?['Evidence'], ''))}`<br>상태 `Status` (선택 값): `확정`<br>회의명 `MeetingName`: `@{coalesce(body('Recheck')?['MeetingName'], '')}`<br>회의일 `MeetingDate`: **fx** `if(empty(body('Recheck')?['MeetingDate']), null, body('Recheck')?['MeetingDate'])`<br>확정일 `DecidedAt`: **fx** `if(empty(body('Recheck')?['MeetingDate']), convertFromUtc(utcNow(), 'Korea Standard Time', 'yyyy-MM-dd'), body('Recheck')?['MeetingDate'])`<br>결정권자 `Decider` (사람: 이메일): **fx** `if(empty(body('Recheck')?['OwnerEmail']), null, body('Recheck')?['OwnerEmail'])`<br>등록 경로 `CreatedVia` (선택 값): `AI 제안 승인` | 결정 등록(확정) |
| 2.3.아니요.2 | 　　`Mark_done_decision` | SharePoint › **Update item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `ActionCandidates`<br>ID: **fx** `triggerOutputs()?['body/ID']`<br>후보 내용 `Title`: `@{body('Recheck')?['Title']}`<br>종류 `Kind` (선택 값): `@{body('Recheck')?['Kind']?['Value']}`<br>접수 항목 ID `IntakeID`: **fx** `body('Recheck')?['IntakeID']`<br>가드 판정 `Verdict` (선택 값): `@{body('Recheck')?['Verdict']?['Value']}`<br>처리 `Status` (선택 값): `등록완료`<br>등록된 항목 ID(시스템) `CreatedItemID`: `@{string(body('Create_decision')?['ID'])}` | 등록완료 표시 |
| 3 | `Catch` | 컨트롤 › **범위(Scope)** | **실행 후 구성**: 'Try' 이(가) 실패함, 시간 초과됨 | 실행 후 구성: Try가 '실패함'·'시간 초과됨'일 때 |
| 3.1 | 　`Failed_actions` | 데이터 작업 › **배열 필터링(Filter array)** | 보낸 사람(From): **fx** `result('Try')` · '고급 모드에서 편집' 후: `@equals(item()?['status'], 'Failed')` | Try 안에서 실패한 액션만 추림 |
| 3.2 | 　`Log_error` | SharePoint › **Create item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `FlowErrorLog`<br>Flow 이름 `Title`: `@{workflow()?['tags']?['flowDisplayName']}`<br>실행 ID `FlowRunId`: `@{workflow()?['run']?['name']}`<br>실패 액션 `FailedAction`: `@{coalesce(first(body('Failed_actions'))?['name'], '')}`<br>오류 메시지 `ErrorMessage`: `@{coalesce(first(body('Failed_actions'))?['error']?['message'], '상세 메시지 없음(실행 기록 확인)')}`<br>심각도 `Severity` (선택 값): `Critical`<br>조치완료 `Resolved`: `false`(식 탭)<br>실행 기록 링크 `RunUrl`: `@{concat('https://make.powerautomate.com/environments/', workflow()?['tags']?['environmentName'], '/flows/', workflow()?['name'], '/runs/', workflow()?['run']?['name'])}` | 공통 오류 로그 기록 |
| 3.3 | 　`Mark_candidate_error` | SharePoint › **Update item** | 사이트 주소(Site Address) — '사용자 지정 값 입력': `@{outputs('Config')?['site']}`<br>목록 이름(List Name) — '사용자 지정 값 입력': `ActionCandidates`<br>ID: **fx** `triggerOutputs()?['body/ID']`<br>후보 내용 `Title`: `@{triggerOutputs()?['body/Title']}`<br>종류 `Kind` (선택 값): `@{triggerOutputs()?['body/Kind/Value']}`<br>접수 항목 ID `IntakeID`: **fx** `triggerOutputs()?['body/IntakeID']`<br>가드 판정 `Verdict` (선택 값): `@{triggerOutputs()?['body/Verdict/Value']}`<br>처리 `Status` (선택 값): `오류`<br>검토 사유 `Reasons`: `@{concat(coalesce(triggerOutputs()?['body/Reasons'], ''), ' / 등록 실패: ', coalesce(first(body('Failed_actions'))?['error']?['message'], first(body('Failed_actions'))?['name']))}` | 후보에 오류 표시(사용자가 고쳐 다시 승인) |
| 3.4 | 　`Terminate_failed` | 컨트롤 › **종료(Terminate)** | 상태: 실패함(Failed) · 코드 `FlowFailed` · 메시지 `@{concat('실패 액션: ', coalesce(first(body('Failed_actions'))?['name'], '?'))}`<br>**실행 후 구성**: 'Mark_candidate_error' 이(가) 성공함, 실패함, 건너뜀 |  |

