# Pilot 01 — 구현 가이드 (실무자용)

> 대상: IT 개발자가 아닌 SCM 실무자. 소요: 약 2일(목록 0.5일, 흐름 1일, 테스트 0.5일).
> **메뉴 이름 표기:** Power Automate·SharePoint는 UI 번역이 버전마다 다르다. `영문 명칭(한국어 예상 명칭)`으로 적었다. 화면에서 찾을 수 없으면 검색창에 **영문 명칭**을 입력하라. 확인하지 못한 메뉴는 '(확인 필요)'로 표시했다.
> **안전 규칙:** 운영 중인 기존 시제품 목록은 ① CSV 백업 ② 테스트용 복제 목록에서 먼저 시험 ③ 사용자 승인 후 원본 적용. 대량 수정·삭제·권한 변경은 하지 않는다.

---

## 0. 사전 확인 (15분, 읽기 전용)

| 확인 | 방법 | 통과 기준 |
|---|---|---|
| 기존 시제품 목록 위치 | 목록 열기 → 주소창 URL 기록 `https://<tenant>.sharepoint.com/sites/<사이트>/Lists/<목록>` | 팀 사이트에 있음 |
| 목록 편집 권한 | 목록 → **+ Add column(+ 열 추가)** 가 보이는가 | 보임 |
| Power Automate | make.powerautomate.com 로그인 → **My flows(내 흐름)** 열림 | 열림 |
| Workflows 앱 | Teams → **Apps(앱)** → 'Workflows' 검색 | 추가 가능 |
| DLP | `01` 문서 U2 방법 | 저장 시 DLP 경고 없음 |

하나라도 실패하면 `07_Licensing_Security_Review.md`의 Scenario A 대체 설계를 따른다.

## 1. 기존 목록 백업과 열 매핑 (30분)

1. 기존 목록 → 상단 **Export(내보내기) → Export to CSV(CSV로 내보내기)** → 파일을 팀 사이트 `SCM_Automation/backup/` 에 날짜 붙여 저장
2. 목록 → 오른쪽 위 톱니(설정) → **List settings(목록 설정)** → 'Columns(열)' 표를 캡처
3. 아래 매핑표를 채운다(이 파일 사본에 직접 기입)

| 필요 열(내부 이름) | 기존 목록의 같은 의미 열 | 조치 |
|---|---|---|
| Title | (제목) | 그대로 |
| RequestType | | 없으면 추가(Choice) |
| Requester | (만든 사람으로 대체 가능?) | 대리 등록이 있으면 추가 |
| DueDateRequested | (희망일) | 있으면 그대로 사용 → 흐름 식의 이름만 교체 |
| Status | (진행상태) | **선택지 값이 다르면** 기존 값을 새 선택지로 매핑(수정 전 승인) |
| Owner, SLATargetDate, DueDateCommitted, ChangeCount, LastChangeReason, ApprovalOutcome, ClosedDate, DuplicateKey, PrevStatus, PrevDueDateCommitted, RequestID, Source | | 추가 |

## 2. 목록 만들기 — 세 가지 방법 중 하나

### 방법 1(권장): 기존 목록에 열 추가
목록 → **+ Add column(+ 열 추가)** → 형식 선택 → 이름은 **먼저 영문 내부 이름으로** 만들고(예: `SLATargetDate`), 만든 뒤 열 머리글 → **Column settings(열 설정) → Edit(편집)** 에서 표시 이름을 한글로 바꾼다. (처음부터 한글로 만들면 내부 이름이 `_x0053_...` 형태로 깨져 흐름 식이 복잡해진다.)

열별 설정값은 `automation_assets/lists_schema.json` 의 `columns` 를 그대로 따른다:
- `Choice` → **Choice(선택)**, choices 값을 한 줄에 하나씩 붙여넣기, default 지정
- `User` → **Person(사람)**
- `DateTime` + `dateOnly: true` → **Date and time(날짜 및 시간)** → '시간 포함' 끔
- `Note` → **Multiple lines of text(여러 줄 텍스트)**
- `hidden: true` 열 → 목록 → **+ New(새로 만들기)** → 양식 오른쪽 위 **Edit form(양식 편집) → Edit columns(열 편집)** 에서 체크 해제(사용자 입력 화면에서 숨김)

### 방법 2: 새 목록을 CSV에서 만들기(테스트용 복제에 적합)
Microsoft Lists 앱(microsoft365.com → 앱 → Lists) → **+ New list(+ 새 목록) → From CSV(CSV에서)** → `automation_assets/templates/RequestHub_import_sample.csv` 업로드 → 각 열 형식을 위 규칙대로 지정 → 저장 위치를 **팀 사이트**로 선택 → 이름 `RequestHub`

### 방법 3(Scenario B, IT 승인 필요): 스크립트
`automation_assets/provision_lists.ps1` — 조직이 등록한 PnP용 Entra ID 앱(ClientId)이 있어야 한다. 기본은 미리보기(Dry-run). *작성 환경에 PowerShell이 없어 실행 검증되지 않았다 — 테스트 사이트에서 Dry-run 출력부터 확인.*

### 나머지 목록
`RequestLog`, `SLAPolicy`, `Holidays`, `FlowErrorLog` 를 같은 방법으로 만든다. `SLAPolicy_seed.csv`, `Holidays_sample.csv` 로 'CSV에서' 만들면 데이터까지 들어간다. **Holidays는 회사 공식 달력으로 반드시 교체**(샘플은 일부 날짜만 있음). SLAPolicy의 이메일은 실제 담당자로 수정.

## 3. 목록 설정 (20분)

| 설정 | 경로 | 값 |
|---|---|---|
| 버전 기록 | 목록 설정 → **Versioning settings(버전 관리 설정)** | 버전 만들기 '예', 보존 수 50(사내 기준 따름) |
| 인덱스 | 목록 설정 → **Indexed columns(인덱싱된 열)** → **Create a new index(새 인덱스 만들기)** | Status, Owner, SLATargetDate, DuplicateKey, RequestID, ProductCode 각각 |
| 항목 수준 권한 | 목록 설정 → **Advanced settings(고급 설정)** → 'Create and Edit access' | '모든 항목 읽기' + '본인이 만든 항목만 편집'(요청 부서용). SCM 팀은 사이트 편집 권한으로 전체 편집 *(권한 변경이므로 사이트 소유자와 합의 후)* |
| 로그 목록 보호 | RequestLog → 목록 설정 → **Permissions for this list(이 목록에 대한 사용 권한)** | 팀원 읽기 — *상속 중단은 사이트 소유자만 가능, 불가하면 '보기 숨김'으로 대체* |

## 4. 보기와 열 서식 (20분)

1. 목록 → 보기 메뉴 → **Create new view(새 보기 만들기)** → `lists_schema.json` 의 views 4개 작성
   - '내 담당(진행)': 필터 `SCM 담당자 = [Me]` 그리고 `상태`가 완료·반려·취소가 아님(필터 3줄 AND)
   - '보드(상태별)': 보기 형식 **Board(보드)**, 그룹 기준 상태
2. SLA 목표일 열 머리글 → **Column settings(열 설정) → Format this column(이 열 서식 지정) → Advanced mode(고급 모드)** → `formatting/sla_target_column.json` 붙여넣기 → 저장
3. 각 보기 주소(URL)를 복사해 둔다 — 카드의 `{{MyViewUrl}}`, `{{SlaViewUrl}}` 에 넣는다.

## 5. 흐름 P1-F1 만들기 (요청 접수, 2시간)

1. make.powerautomate.com → **+ Create(+ 만들기) → Automated cloud flow(자동화된 클라우드 흐름)**
2. 이름 `P1-F1 요청 접수 처리`, 트리거 검색 **When an item is created**(SharePoint) → 사이트 주소·목록 이름 `RequestHub` 선택
3. **+ New step → Scope(범위)** 추가, 이름 `Try`. 이하 액션은 모두 Try 안에 넣는다.
4. **Get items**(SharePoint, 이름 `Get_items_SLAPolicy`): 목록 SLAPolicy, Filter Query `Title eq '@{triggerOutputs()?['body/RequestType/Value']}'`, Top Count 1
5. **Get items**(이름 `Get_items_Holidays`) → **Select**(이름 `Select_Holidays`) → **Initialize variable** `varHolidays` — `expressions.md` 4장 그대로
6. **Initialize variable** `varCreatedKst`, `varD`, `varSlaDays`, `varAdded` — `expressions.md` 5·6장
7. **Condition** "당일 접수 인정"(5장 식) → 아니요 쪽에 **Do until** "영업일 찾기"
8. **Condition** `varSlaDays` > 0 → 예 쪽에 **Do until** "SLA 가산"(6장). Do until의 **Change limits(제한 변경)**: Count 100, Timeout PT10M
9. **Compose** 이름 `DuplicateKey` = 3장 식 → **Get items**(RequestHub) 중복 후보 필터(3장)
10. **Update item**(RequestHub, Id = 트리거 ID):
    - RequestID = 2장 식
    - Owner Claims = `first(body('Get_items_SLAPolicy')?['value'])?['DefaultOwnerEmail']`
    - SLATargetDate = `variables('varD')`
    - DuplicateKey = `outputs('DuplicateKey')`
    - PrevStatus = `triggerOutputs()?['body/Status/Value']`
    - PrevDueDateCommitted = (빈 값) · *Update item은 필수 열(Title 등)도 요구하므로 트리거 값을 그대로 다시 넣는다*
11. **Create item**(RequestLog): Title=RequestID, RequestItemId=트리거 ID, EventType=생성, EventAt=`utcNow()`, FlowRunId=`workflow()?['run']?['name']`. 중복 후보가 1건 이상(`greater(length(body('Get_items_dup')?['value']), 0)`)이면 EventType=중복의심 1건 추가
12. **Post card in a chat or channel**(Teams): Post as **Flow bot**, Post in **Chat with Flow bot**, Recipient = 담당자 이메일, Adaptive Card = `cards/owner_new_request.json` (중괄호 `{{...}}` 자리에 동적 콘텐츠 삽입)
13. **Post message in a chat or channel**: 요청자에게 "접수됨: REQ번호 / SLA 목표일 / 링크"
14. Try 아래에 **Scope** `Catch` → **…→ Configure run after(실행 후 구성)** → `has failed(실패함)`, `has timed out(시간 초과됨)` 체크 → 안에 `expressions.md` 10장 액션(Filter array → Create item FlowErrorLog → 운영자 메시지 → **Terminate** 상태 Failed)
15. 모든 SharePoint·Teams 액션 → **Settings(설정)** → Retry policy 지수 4회(11장)
16. **Save(저장)** → 테스트는 6장

## 6. 첫 실행 테스트 (P1-F1)
1. 흐름 오른쪽 위 **Test(테스트) → Manually(수동)** → 목록에 테스트 항목 1건 입력(`[테스트]` 접두어)
2. 실행 기록에서 `Select_Holidays` 출력이 `["2026-10-05", ...]` 형태인지 확인 → 아니면 `expressions.md` 4장 주석대로 식 수정
3. 항목에 RequestID·SLA 목표일·담당자가 채워졌는지, 담당자 Teams에 카드가 왔는지 확인
4. `test_cases.md` TC-M01~M05 기록

## 7. 흐름 P1-F2 (상태·약속일 변경, 2시간)
1. 트리거 **When an item is created or modified** → 트리거 카드 **… → Settings → Trigger conditions(트리거 조건)** 에 `expressions.md` 1장 두 줄 입력
2. Try 안: Initialize `varTransitions`(8장) → Condition "상태 변경?" `@not(equals(triggerOutputs()?['body/Status/Value'], triggerOutputs()?['body/PrevStatus']))`
   - 예: Condition "허용 전이?"(8장) → 아니요: RequestLog '규칙위반' + 담당자 메시지 / 예: RequestLog '상태변경'
   - 새 상태 ∈ {완료, 반려, 취소} → ClosedDate = `utcNow()`
   - 새 상태 = 승인대기 AND SLAPolicy.RequiresApproval = 예 → **Update item** ApprovalOutcome=대기 → **Start and wait for an approval**(Approve/Reject – First to respond, Assigned to = ApproverEmail, Item link = 항목 링크, 액션 Settings → Timeout `P7D`) → **Get item**(현재 상태 재조회) → 현재 상태 = 승인대기일 때만 Status·ApprovalOutcome·PrevStatus 갱신, 아니면 로그만
3. Condition "약속일 변경?" `@not(equals(coalesce(triggerOutputs()?['body/DueDateCommitted'], ''), coalesce(triggerOutputs()?['body/PrevDueDateCommitted'], '')))` → PrevDueDateCommitted가 비어있지 않으면 ChangeCount + 1(`add(coalesce(triggerOutputs()?['body/ChangeCount'], 0), 1)`), LastChangeReason 비어 있으면 담당자에게 사유 요청 메시지
4. 요청자 알림 1건
5. **마지막 Update item**: PrevStatus = 현재 Status, PrevDueDateCommitted = `coalesce(triggerOutputs()?['body/DueDateCommitted'], '')` ← 이 단계가 빠지면 흐름이 반복 실행된다
6. Catch는 P1-F1과 같음

## 8. 흐름 P1-F3 (SLA 다이제스트), P1-F4 (Teams 메시지 등록)
- P1-F3: **+ Create → Scheduled cloud flow(예약된 클라우드 흐름)** → Repeat every 1 Week, On these days 월~금, At 8:00, Time zone `(UTC+09:00) Seoul` → `flows_spec.json` P1-F3 단계, 식은 `expressions.md` 7·9장
- P1-F4: **+ Create → Instant cloud flow(인스턴트 클라우드 흐름)** → 트리거 **For a selected message**(Microsoft Teams) → 트리거의 Adaptive Card에 `cards/capture_request_from_message.json` 붙여넣기 → Create item(RequestHub). *Teams 메시지 메뉴에는 기본(Default) 환경의 흐름만 표시된다는 보고가 있다 — 안 보이면 환경 확인.* 사용: Teams 메시지 → **…(추가 작업) → More actions → P1-F4 …**

## 9. 오류 시 확인 항목

| 증상 | 원인 후보 | 확인·조치 |
|---|---|---|
| 흐름이 계속 반복 실행 | P1-F2 마지막 Update에서 Prev열 미갱신 / 트리거 조건 오타 | 실행 기록에서 마지막 액션 확인, 트리거 조건 내부 이름 대소문자 |
| SLA 목표일이 하루 어긋남 | 날짜만 열의 UTC/KST 처리 | Compose로 원시값 확인 → `expressions.md` 4장 |
| 'The expression is invalid' | 작은따옴표·괄호 짝 | 식을 메모장에서 다시 복사, 따옴표가 스마트 따옴표(‘ ’)로 바뀌지 않았는지 |
| Get items 결과가 비어 있음 | 필터의 열 내부 이름 불일치 | 목록 설정 → 열 클릭 → 주소창 `Field=` 뒤 값이 내부 이름 |
| 카드가 오지 않음 | Workflows 앱 차단 / 받는 사람 이메일 오류 | Teams 앱 허용 확인, 담당자 이메일 |
| 401/403 | 연결 만료·권한 부족 | **Data → Connections(연결)** → Fix connection, 사이트 권한 |
| 429 Too Many Requests | 조절(Throttling) | 재시도 정책 확인, 반복문에 Delay 2초 |
| 승인 응답이 반영 안 됨 | 응답 전 상태가 바뀜(의도된 보호) | RequestLog 확인 |

## 10. 운영·유지관리

| 주기 | 작업 | 담당 | 소요 |
|---|---|---|---|
| 매일 | (자동) FlowErrorLog 알림 확인 | 운영자 | 2분 |
| 매주 | 실행 기록 실패율, '규칙위반'·'중복의심' 로그 검토 | 운영자 | 15분 |
| 매월 | KPI 산출(리드타임 중앙값·SLA 준수율·정보보완률) → `09` 모델 갱신 | 파일럿 책임자 | 30분 |
| 매년 | Holidays 다음 해 입력, SLAPolicy 담당자 점검 | 팀장 | 30분 |
| 변경 시 | 흐름 수정은 '다른 이름으로 저장' 사본에서 테스트 후 교체, 흐름 패키지 내보내기(… → Export → Package(.zip))를 저장소에 커밋 | 운영자 | - |
| 인사 이동 | 흐름 공동 소유자 이전, 연결 재설정 | 팀장 | 30분 |
