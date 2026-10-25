# BUILD GUIDE — Pilot 03 프로토타입 구축 (클릭 순서)

> **⚠ 2026-10-25 감사 반영:** 구축 **순서**는 `START_HERE_V2.md`·`DEPENDENCY_MATRIX.md`를 따른다(아래 2장의 '목록 7개 한꺼번에'는 참고용). Office Scripts는 개인 파일럿에서 **'Run script'(OneDrive)** 하나로 통일했다(3장과 BUILD_TABLES 일치). 'Update item'은 **모든 열을 채운다**(BUILD_TABLES의 ⚠ 표시).

> **원칙:** 운영 환경을 바꾸기 전에 **샌드박스(가상 데이터)** 에서 전부 돌려본다. 샌드박스 = 본인만 보는 '내 목록'(OneDrive) + 본인 OneDrive의 `P3` 폴더. 알림은 본인에게만 간다(프로토타입 모드).
> **소요(가정):** 준비 30분 · 목록 1.5시간 · 스크립트 20분 · 흐름 9개 4~5시간 · Copilot 30분 · 테스트 1.5시간 ≈ **1.5일**
> **메뉴 표기:** `영문(한국어 예상)`. 화면 언어·버전(새 디자이너/클래식)에 따라 이름이 다를 수 있다. 못 찾으면 **영문 명칭으로 검색**. 확인하지 못한 경로는 *(확인 필요)*.
> **입력값의 원본:** 흐름은 `BUILD_TABLES.md`, 목록은 `LISTS_SETUP.md` — 둘 다 테스트를 통과한 정의 파일에서 자동 생성된 표다. 이 가이드는 '어디를 누르는지'를, 두 표는 '무엇을 넣는지'를 알려준다.

---

## 0. 사전 점검 (15분, 아무것도 바꾸지 않음)

| # | 확인 | 클릭 순서 | 통과 기준 | 실패 시 |
|---|---|---|---|---|
| C1 | Power Automate 접속·환경 | make.powerautomate.com → 오른쪽 위 **환경(Environment)** 표시 확인 | 이름에 '(default)' 또는 회사 기본 환경 | Teams 메시지 흐름(F5)은 기본 환경에서만 메시지 메뉴에 보인다는 보고 → 기본 환경 사용 |
| C2 | DLP | **+ 만들기(Create) › 인스턴트 클라우드 흐름** → 이름 `DLP점검` → 수동 트리거 → 액션 5개 추가(SharePoint Get items, Office 365 Outlook Send an email (V2), Microsoft Teams Post message, Excel Online (Business) Run script, Office 365 Users Get user profile) → **저장만**(실행 안 함) | 저장 시 DLP 경고 없음 | 경고 문구를 캡처해 IT 요청(APPROVALS I-01). 확인 후 이 흐름은 삭제 |
| C3 | Teams Workflows 앱 | Teams → **앱(Apps)** → `Workflows`(옛 이름 `Power Automate`) 검색 | '추가' 또는 '열기' 가능 | **점검 결과 없음** → `{{NOTIFY_CHANNEL}}=email`. 모든 알림 메일로, P3P-F5 대신 Outlook 범주 방식(START_HERE 6단계). IT 요청 I-02는 선택 |
| C4 | Office Scripts | 웹 Excel(office.com에서 아무 통합 문서) → 리본 **자동화(Automate)** 탭 | 탭 있음 | IT 요청 I-03(관리자가 끔) |
| C5 | Copilot | Teams 회의 채팅 또는 microsoft365.com의 **Copilot** → **업무(Work)** 탭 | 응답 가능 | 라이선스 할당 확인 |
| C6 | 에이전트 만들기 | Copilot 앱 왼쪽 **에이전트(Agents)** | '에이전트 만들기' 보임 | 결정 조회 에이전트만 보류(I-05), 나머지 진행 |

## 1. 설정값 정하기 (자리표시자)

흐름의 `Config` 작성(Compose) 액션에 아래 값을 넣는다. 샌드박스→운영 전환 때는 이 값과 트리거의 사이트·목록만 바꾸면 된다.

| 자리표시자 | 샌드박스 값(예) | 확인 방법 |
|---|---|---|
| `{{SITE_URL}}` | `https://<회사>-my.sharepoint.com/personal/<계정>` | 2장에서 만든 목록을 열고 주소창의 `/Lists/` 앞부분 |
| `{{ME}}` | 본인 회사 이메일 | Outlook 프로필 |
| `{{HOST_WORKBOOK}}` | `/Documents/P3/P3_AutomationHost.xlsx` | 3장 업로드 위치 *(Run script 액션에서는 드롭다운으로 직접 선택)* |
| `{{SCRIPT_FOLDER}}` | `/Documents/Office Scripts` | 3장 스크립트 저장 위치 *(개인 파일럿의 'Run script'는 이 기본 위치에서 이름으로 고르므로 흐름 식에서는 쓰지 않는다. 팀 단계 SharePoint 라이브러리 전환용)* |
| `{{VIEW_MY_ACTIONS}}` | ActionItems '내 액션' 보기 URL | 보기 선택 후 주소창 복사 |
| `{{VIEW_DECISION_QUEUE}}` | DecisionLog '결정 대기열' 보기 URL | 〃 |
| `{{VIEW_CANDIDATES}}` | ActionCandidates '확인 대기' 보기 URL | 〃 |
| `{{NOTIFY_CHANNEL}}` | **`email`** (2026-10-25 점검: Workflows 앱 없음) | Workflows 앱이 허용되면 `teams` |
| `{{FACTORY_FOLDER}}` | `/SCM_수신` | 추가 기능 F10의 OneDrive 저장 기본 폴더 |

`prototypeMode: true` — 리마인더를 본인에게만 보낸다. **운영 전환 승인(APPROVALS U-04) 전까지 false로 바꾸지 않는다.**

## 2. 샌드박스 목록 7개 만들기 (1.5시간)

순서: `TeamRoster` → `Holidays` → `FlowErrorLog` → `ActionItems` → `DecisionLog` → `MeetingIntake` → `ActionCandidates`

### 2.1 CSV로 목록 만들기
1. microsoft365.com → 왼쪽 **앱(Apps)** → **Lists** → **+ 새 목록(New list)** → **CSV에서(From CSV)**
2. `lists/<목록이름>.csv` 업로드(가상 데이터 포함, 머리글이 내부 이름)
3. 열 형식 확인 화면에서 `LISTS_SETUP.md`의 '형식'대로 지정 — 날짜 열은 날짜, 숫자 열은 숫자, 선택 열은 선택 *(CSV 가져오기에서 '사람' 형식을 고를 수 없으면 일단 한 줄 텍스트로 가져온다 → 2.3)*
4. **저장 위치: 내 목록(My lists)** → 이름은 CSV 파일명과 똑같이(`ActionItems` 등, 영문) → **만들기**

### 2.2 열 다듬기 (목록마다)
목록 → 열 머리글 클릭 → **열 설정(Column settings) › 편집(Edit)**:
- **표시 이름**을 `LISTS_SETUP.md`의 한글 표시 이름으로 변경(내부 이름은 바뀌지 않음)
- 선택 열: 선택지를 표와 똑같이(철자·띄어쓰기 포함), 기본값 지정
- '필수' 표시된 열: **이 열에 정보 필요(Require that this column contains information)** 켬
- 날짜 열: '시간 포함' — 표의 (날짜만)/(시간 포함)대로

### 2.3 사람 열(Owner, Decider, RequestedBy)
CSV에서 텍스트로 들어왔다면: 그 열 삭제 → **+ 열 추가(Add column) › 사람(Person)** → 이름을 **먼저 영문 내부 이름**(`Owner`)으로 만들고 저장 → 다시 편집해 표시 이름을 한글로. 가상 데이터 행의 담당자는 본인으로 다시 선택.
*(사람 열을 처음부터 한글 이름으로 만들면 내부 이름이 `_x...` 형태로 깨져 흐름 식이 맞지 않는다.)*

### 2.4 인덱스·숨김·버전
- 인덱스: 목록 → 톱니(설정) → **목록 설정(List settings)** → **인덱싱된 열(Indexed columns)** → **새 인덱스 만들기** — 표의 '인덱스 예' 열마다
- 숨김(시스템 열): 목록 → **+ 새로 만들기(New)** → 양식 오른쪽 위 **양식 편집(Edit form) › 열 편집(Edit columns)** → 표의 '숨김 예' 열 체크 해제 → 저장
- 버전 기록: 목록 설정 → **버전 관리 설정(Versioning settings)** → 예(기본 켜짐 확인)

### 2.5 보기
목록 → 보기 메뉴 → **새 보기 만들기(Create new view)** → 표의 '보기' 행대로(예: ActionItems '내 액션' = 담당자가 [나] 이고 상태가 미착수 또는 진행중, 기한 오름차순). 보기 URL을 1장 표에 기록.

### 2.6 명부·휴무일 데이터
- `TeamRoster`: 가상 4명이 들어 있다. 실제 팀원으로 바꾸는 것은 운영 전환 때(개인정보 최소: 이름·회사 이메일·별칭만)
- `Holidays`: 샘플 2건 → **회사 공식 휴무일로 교체**(주말은 스크립트가 자동 처리)

✅ 확인: 7개 목록이 '내 목록'에 있고, `ActionItems`에 가상 4행이 보인다.

## 3. Office Scripts 3종 등록 (20분)

1. OneDrive → `문서(Documents)`에 폴더 `P3` 만들기 → `sandbox/P3_AutomationHost.xlsx` 업로드
2. 그 파일을 **웹 Excel**로 열기 → **자동화(Automate) › 새 스크립트(New Script)**
3. 코드 편집기의 기본 코드를 모두 지우고 `office_scripts/BuildDailyBrief.ts` 전체 붙여넣기 → 스크립트 이름(편집기 위쪽)을 `BuildDailyBrief`로 → **스크립트 저장(Save script)**
4. 같은 방법으로 `BuildReminderDigest`, `GuardExtraction` 저장
5. 저장 위치: 기본은 OneDrive `문서/Office Scripts` 폴더(.osts) — 공식 문서 S14
6. 흐름에서는 Excel Online (Business)의 **Run script** 액션(위치: OneDrive for Business, 문서 라이브러리: OneDrive, 파일: `P3/P3_AutomationHost.xlsx`, 스크립트: 드롭다운에서 선택)을 쓴다. 운영 전환 때 팀 사이트로 옮기면 **Run script from SharePoint library** 로 바꾼다(매개변수는 동일).

### 3.1 스크립트 점검 흐름 (테넌트 첫 실행, 15분)
1. **+ 만들기 › 인스턴트 클라우드 흐름** → `P3P-T0 스크립트 점검` → 트리거 **수동으로 흐름 트리거(Manually trigger a flow)**
2. **Run script** 추가 → 스크립트 `GuardExtraction` → 매개변수 4개에 `sandbox/smoke/GuardExtraction.params.json`의 값을 각각 붙여넣기
3. **저장 › 테스트 › 수동 › 흐름 실행**
4. 실행 기록에서 Run script 출력(`result`)을 열어 `sandbox/smoke/GuardExtraction.expected.json`과 비교: `recommendedCount = 4`, `reviewCount = 0`, 후보 4건
5. `BuildDailyBrief`, `BuildReminderDigest`도 같은 방법(`*.params.json` ↔ `*.expected.json`). **출력 경로가 `body/result`인지 확인** — 흐름 식이 `body('Run_brief')?['result']`를 쓴다. 다르면 BUILD_TABLES의 해당 식만 실제 경로로 바꾼다.

## 4. 흐름 9개 만들기 (4~5시간)

### 4.1 공통 조작 (모든 흐름)
| 하려는 일 | 클릭 |
|---|---|
| 흐름 만들기 | make.powerautomate.com → **+ 만들기(Create)** → 표의 '만들기' 유형(자동화된/예약된/인스턴트) → 흐름 이름 입력 → 트리거 검색·선택 → **만들기** |
| 액션 추가 | 카드 아래 **+** → **액션 추가(Add an action)** → 표의 '추가할 액션' 이름 검색 |
| 이름 바꾸기 | 액션 카드 **…(더 보기)** → **이름 바꾸기(Rename)** → 표의 '액션 이름'과 **완전히 같게**(밑줄 포함). *식이 이 이름을 참조한다* |
| 식 입력(**fx**) | 입력란 클릭 → 오른쪽 **fx(식)** 아이콘/탭 → 표의 식 붙여넣기 → **추가(Add)/확인** |
| `@{...}` 값 | 입력란에 그대로 붙여넣기 → 식 토큰(보라색)으로 바뀌는지 확인. 안 바뀌면 fx 탭에 중괄호 안 식만 |
| 범위 안에 넣기 | `Try` 범위(Scope) 카드 **안쪽**의 + 로 추가(밖에 추가하면 Catch가 동작하지 않음) |
| 조건(Condition) | 왼쪽 값: fx 식 / 연산자 **is equal to(같음)** / 오른쪽 값: fx `true` → 표의 '예/아니요 분기'에 이어서 추가 |
| 실행 후 구성 | `Catch` 범위 카드 **…** → **실행 후 구성(Configure run after)** → `Try`: **실패함(has failed)**, **시간 초과됨(has timed out)** 만 체크 → 완료 |
| 트리거 조건 | 트리거 카드 → **설정(Settings)** → **트리거 조건(Trigger conditions) › + 추가** → 표의 조건을 한 줄씩 |
| 동시성 | 트리거(또는 Apply to each) **설정 › 동시성 제어(Concurrency control)** 켬 → 병렬 처리 수준 **1** |
| SharePoint 사이트·목록 | 드롭다운 대신 **사용자 지정 값 입력(Enter custom value)** → 표의 값(식) — 트리거만은 드롭다운으로 직접 선택 |
| 사람 열 입력 | Create/Update item의 `담당자 Claims` 칸에 이메일(식) |
| 저장·테스트 | 오른쪽 위 **저장(Save)** → **테스트(Test) › 수동(Manually)** → 트리거 동작 수행 |

### 4.2 만드는 순서와 각 흐름의 핵심 확인 (입력값은 `BUILD_TABLES.md`)
| 순서 | 흐름 | 만들기 유형 | 핵심 설정(놓치기 쉬운 것) |
|---|---|---|---|
| 1 | P3P-F3 ActionItems 번호·상태 | 자동화(SharePoint 항목 생성·수정) | **트리거 조건** 필수(없으면 무한 반복). Update item에 필수 열 4개 다시 입력 |
| 2 | P3P-F4 DecisionLog 번호·상태 | 〃 | 〃 |
| 3 | P3P-F1 메일 플래그(받은편지함) | 자동화(Outlook 플래그 V4, 폴더 Inbox) | 트리거 **동시성 1** |
| 4 | P3P-F2 메일 플래그(보낸편지함) | F1을 **다른 이름으로 저장(Save As)** 후 폴더 Sent Items, 유형 회신대기, 접두어·기본 기한만 변경 | 〃 |
| 5 | ~~P3P-F5 Teams 메시지 기록~~ **(Workflows 앱 없음 → 건너뜀, F1의 범주 방식으로 대체)** | 인스턴트(Teams **For a selected message**) | 트리거의 Adaptive Card 칸에 `../automation_assets/cards/capture_decision_action.json` 붙여넣기 |
| 6 | P3P-F6 아침 브리핑 | 예약(평일 07:40, Seoul) | `Catch` 안의 `If_teams_failed` → 본인 메일 대체 |
| 7 | P3P-F7 리마인더 | 예약(평일 08:30, Seoul) | 최상위 `Init_skipped` 변수 초기화는 **Try 밖(위)** 에. `For_each_digest` 동시성 1 |
| 8 | P3P-F8 Copilot 추출 검증 | 자동화(MeetingIntake 생성·수정) | 트리거 조건(접수·재검증요청일 때만) |
| 10~13 | 🆕 P3P-F10 공장 자료 저장 · F13 기한 추정 · F12 주간 정리 · F11 회의 준비 | START_HERE '추가 기능' 절 | F10 트리거 고급 옵션(첨부 포함·첨부 있는 메일만), F13 트리거 조건 |
| 9 | P3P-F9 승인 후보 등록 | 자동화(ActionCandidates 생성·수정) | 트리거 조건 + **동시성 1** + 첫 액션 `Recheck`(최신 값 재확인) |

### 4.3 첫 실행에서 반드시 확인할 '추정 필드' (공식 스키마 미확인 → 출력으로 확정)
| 흐름 | 확인할 값 | 방법 | 다르면 |
|---|---|---|---|
| F1·F2 | 트리거 출력의 `id`, `subject`, `bodyPreview`, `webLink`, `flag/dueDateTime/dateTime` | 실행 기록 → 트리거 → **원시 출력 표시(Show raw outputs)** | 해당 식의 경로만 수정 |
| F5 | `cardOutputs`, `messagePayload/id`, `messagePayload/body/content`, `linkToMessage` | 〃 | `Content`·`Inputs` 작성 액션만 수정(다른 액션은 `Inputs`만 참조하도록 설계됨) |
| F6 | 일정 V3 출력의 `start`·`end` 시간대(UTC 여부), `organizer` 형식 | `Get_events` 출력 | 스크립트가 UTC·시간대 표기 모두 처리. organizer가 객체면 그대로 동작(이메일 추출) |
| F6·F7·F8 | Run script 출력 `body/result` | 3.1 점검 | 식의 `?['result']` 경로 |
| 전체 | 날짜만 열 값 형식(`2026-10-26` 또는 `…T15:00:00Z`) | Get items 출력 | 스크립트가 두 형식 모두 처리(테스트 완료). 흐름 식 쪽은 `formatDateTime`으로 맞춤 |

## 5. Copilot 설정 (30분)
1. **회의 추출(반자동):** 회의 후 Copilot에 `copilot/meeting_extraction_prompt.md` 프롬프트 실행 → `MeetingIntake` 목록 **+ 새로 만들기** → 회의명·회의일·회의록 원문·Copilot 추출 결과(응답 전체) 붙여넣기 → **저장** → 1~2분 뒤 Teams로 "후보 N건" 메시지 → `ActionCandidates` '확인 대기' 보기에서 근거 문장을 보고 **처리**를 `승인` 또는 `기각`으로 변경(담당자 이메일·기한은 여기서 고칠 수 있음)
2. **결정 조회 에이전트:** `copilot/decision_agent_setup.md`
3. **예약 프롬프트(받은편지함 요약):** `copilot/scheduled_prompt.md`

## 6. 샌드박스 테스트 (1.5시간)
`TEST_REPORT.md` 2장 'T 시리즈'를 순서대로 실행하고 결과 칸을 채운다. 테스트 데이터는 제목에 `[테스트]`를 붙인다.

## 7. 운영 전환 (승인 후)
`APPROVALS.md`의 U-·L- 항목 승인과 I- 항목 지원이 끝난 뒤:
1. 팀 사이트에 같은 7개 목록 생성(2장 절차, 저장 위치 = 팀 사이트) — 샌드박스 목록은 4주 보관 후 사용자 승인 받아 삭제
2. 호스트 통합 문서·스크립트를 팀 사이트 라이브러리로 복사 → Run script를 **Run script from SharePoint library**로 교체
3. 각 흐름: **다른 이름으로 저장(Save As)** → 트리거 사이트·목록 재선택 → `Config` 값 교체 → 공동 소유자 추가(**… › 공유(Share)**) → 테스트 T01·T04·T09 재실행 → 샌드박스 흐름 끄기
4. `prototypeMode`를 false로 바꾸는 것은 **팀 리마인더 발송 승인(U-04)** 후에만
5. 흐름마다 **… › 내보내기(Export) › 패키지(.zip)** → 이 저장소 `prototype/flows/exported/`에 커밋(변경 이력 관리)
