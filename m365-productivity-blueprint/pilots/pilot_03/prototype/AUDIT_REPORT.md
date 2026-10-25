# AUDIT_REPORT — Pilot 03 프로토타입 설계 감사

> 감사·수정일: **2026-10-25(KST)** · 대상: `pilots/pilot_03/prototype/` 전체 · 데이터: 전부 가상
> 판정 기준: **로컬 에뮬레이터·실제 TypeScript 실행으로 확인한 것만 '로컬 검증'**. 회사 M365 테넌트에서는 아무것도 실행하지 않았다(접근 권한 없음, 승인 전).
> 공식 문서는 이 환경에서 본문 열람(WebFetch)이 막혀 **검색 결과 요약으로만 확인**했다. 확인하지 못한 동작은 '추정' 또는 '미확인'으로 적었다.

## 0. 결론 요약

| 구분 | 내용 |
|---|---|
| P0 결함 | 6건 발견 → **6건 모두 소스에서 수정**, 로컬 테스트로 수정 확인 |
| P1 개선 | A안 최소 구성 신설, 오류 처리 강화, 측정식 보정, 확인 요청 정책 문서화 |
| 운영 적용 권고 | **아직 아님.** 테넌트에서만 확인 가능한 항목(TEST_RESULTS.md 'NOT TESTED' 9건)이 남아 있다. 1주차 A안을 본인 범위에서 시험하고 T-T1~T-T9를 통과한 뒤 판단한다. |

## 1. 공식 문서로 확인한 사실과 미확인 사항

| # | 주제 | 확인 내용(검색 기준, 2026-10-25) | 이 설계에 미친 영향 | 출처 |
|---|---|---|---|---|
| D1 | 'When an email is flagged (V4)' | 이미 플래그된 메일이 **바뀔 때마다** 트리거될 수 있고, 여러 통을 한꺼번에 플래그하면 여러 번 실행된다(미리 보기 기능) | 재실행을 '중복 방지 후 종료'가 아니라 **멱등 갱신 규칙**으로 처리(P0-2) | [Office 365 Outlook 커넥터](https://learn.microsoft.com/en-us/connectors/office365/) |
| D2 | Run script vs Run script from SharePoint library | 'Run script'는 OneDrive의 기본 스크립트 위치를 사용, SharePoint 라이브러리에 둔 스크립트는 별도 액션 | 개인 파일럿은 **Run script(OneDrive)** 로 통일(P0-4) | [Run Office Scripts with Power Automate](https://learn.microsoft.com/en-us/office/dev/scripts/develop/power-automate-integration) |
| D3 | Run script 반환값 경로 | 찾은 문서에 정확한 출력 JSON 경로가 없음 → **미확인** | `body('…')?['result']` 는 로컬 가정, 테넌트 스모크 테스트 T-T2 | 위 문서 |
| D4 | Outlook 메시지 ID | 기본 ID는 폴더 이동 시 바뀔 수 있고, immutable ID는 같은 사서함 안에서 유지. internetMessageId의 커넥터 출력 포함 여부·안정성은 **미확인** | 고유키를 internetMessageId(있으면) 또는 지문으로, 메일 ID는 보조 키로 | [Outlook immutable IDs](https://learn.microsoft.com/en-us/graph/outlook-immutable-id), [Mail API](https://learn.microsoft.com/en-us/graph/api/resources/mail-api-overview?view=graph-rest-1.0) |
| D5 | SharePoint 'Update item' 빈 값 | 공식: 지정하지 않은 열은 유지(필수 열·예/아니요 예외). 커뮤니티: 비워 둔 입력이 값을 지운 사례 | **모든 열을 최신 값으로 다시 넣는** 보존 패턴 + 에뮬레이터 엄격 모드(P0-5) | [SharePoint 커넥터](https://learn.microsoft.com/en-us/connectors/sharepointonline/), [Q&A](https://learn.microsoft.com/en-us/answers/questions/5438257/i-have-an-issue-regarding-power-automate-update-it) |
| D6 | 고유 값 적용(Enforce unique values) | 인덱스 열 필요. 빈 값 처리·기존 데이터 처리 **미확인** | 기본 설계는 사후 중복 점검. 고유 값 설정은 선택(NOT TESTED) | [Enforcing uniqueness](https://learn.microsoft.com/en-us/previous-versions/office/developer/sharepoint-2010/ee536168(v=office.14)) |
| D7 | Teams 게시 액션 | Flow bot·사용자 게시 모두 Teams 관리 센터에서 Workflows 앱 허용이 필요 | 'Workflows 앱 없음'과 'Teams 커넥터 DLP 차단'을 별도 점검(APPROVALS I-02a/I-02b) | [Teams 커넥터](https://learn.microsoft.com/en-us/connectors/teams/), [Send a message in Teams](https://learn.microsoft.com/en-us/power-automate/teams/send-a-message-in-teams) |

## 2. 결함 목록과 수정

| ID | 심각도 | 결함(수정 전) | 근거 위치(수정 전) | 수정(소스) | 검증 |
|---|---|---|---|---|---|
| **P0-1** | P0 | 1주차 가이드가 목록 2개(ActionItems·FlowErrorLog)만 만들게 하고 P3P-F1을 만들게 했는데, F1은 DecisionLog를 조회·기록한다 → 저장·실행 실패. F12는 FactoryInbox 없이 만들면 실패. F13은 F3와 같은 항목을 동시에 고칠 수 있었다 | START_HERE.md 2단계, flows/P3P-F1 `Find_existing_decision` | ① A안 흐름 **P3A-1**(DecisionLog 없음) 신설 ② `tools/dependency_matrix.py`가 단계별 목록·스크립트·선행 흐름을 **자동 검사**(위반 시 실패) ③ F13 트리거 조건에 '액션번호 있음' 추가(F3 이후에만) | test_audit A8(3건), A4 `test_f13_runs_only_after_numbering`, run_all_checks 9단계 |
| **P0-2** | P0 | V4 트리거 재실행을 '이미 있으면 종료'로만 처리. 동시성 1을 중복 방지 보장처럼 서술. 폴더 이동 시 메일 ID가 바뀌면 새 할 일이 생길 수 있음. 완료 후 재플래그·플래그 기한 변경·범주 변경 규칙 없음 | build_flows.py `flag_flow` | 고유키 `SourceKey`(imid/지문) + 보조 키(메일 ID). 기존 항목은 규칙대로 갱신(기한 변경은 사람이 손대지 않은 경우만, 메일 이동 시 링크 갱신), 완료·플래그 완료는 **자동 변경 대신 메모 + 본인 확인 요청(하루 1회)**, 범주 추가 시 결정 기록을 연결 생성(할 일 유지·삭제 없음). 생성 직후 **사후 중복 점검**(나중에 만든 쪽을 '취소'+사유) | test_audit A1(13건), test_mutations 2건(사전·사후 방어 각각 제거) |
| **P0-3** | P0 | 기한 없는 할 일이 아침 브리핑 TOP5에서 제외되고 건수만 표시 → 오래 방치될 수 있음 | BuildDailyBrief.ts `if (due === "") { undated++; return; }` | 기한 없는 할 일도 점수(30+2/경과일, 상한 40) + 우선순위 가감(높음 +15, 낮음 −10). TOP5와 별도로 '기한 없는 할 일' 칸(3건), **방치 경고**(14일↑ 또는 높음+7일↑). 기한은 만들어 넣지 않음. Python 참조 구현 동일 수정 | test_office_scripts 교차 검증 + `test_undated_priority_age_and_neglect_warning`, test_audit A2 |
| **P0-4** | P0 | 흐름은 'Run script from SharePoint library'(경로 지정)인데 가이드·시험 절차는 OneDrive 'Run script'(드롭다운) — 위치·액션·매개변수 불일치 | build_flows.py `script()`, BUILD_GUIDE 3장 | 모든 스크립트 액션을 **Run script(위치 OneDrive for Business, 파일=호스트 통합 문서, 스크립트=이름)** 로 통일. lint L11이 SharePoint 라이브러리 액션을 금지(팀 단계 전환 시 해제). 에뮬레이터는 OneDrive `문서/Office Scripts`에서만 스크립트를 찾음 | test_audit A3(3건) |
| **P0-5** | P0 | F3·F4·F7·F8·F9·F13 'Update item'이 필수 열만 넣거나 **트리거 시점의 오래된 값**을 다시 씀 → 비운 칸이 값을 지우는 환경이면 근거·링크·기한 손실, 두 흐름이 같은 항목을 고치면 덮어쓰기 | build_flows.py 각 Update item | `preserve()`: Get item으로 읽은 **최신 값으로 모든 열을 다시 채우고 바꿀 열만 변경**(선택 열 /Value, 사람 열 /Claims, 날짜 null 유지). F3·F4·F8은 최신 값 재확인 후 이미 처리됐으면 종료. lint L10이 모든 Update item의 전체 열 입력을 강제. 에뮬레이터 **엄격 모드(입력 안 한 열은 지워짐)** 로 전 테스트 실행 | test_audit A4(6건, 변이 1건 포함). 기존 124건 전부 엄격 모드 통과 |
| **P0-6** | P0 | 메일 범주 '결정', Teams 카드 '결정', AI 후보 승인이 모두 DecisionLog에 **'확정'** 으로 기록, AI가 추정한 담당자를 결정권자로, 회의일을 확정일로 기록 | flag_flow·F5·F9 `Status '확정'`, 목록 기본값 '확정' | 자동화는 '확정'을 만들지 않음: '결정' → **'제안'**, '결정요청' → 결정요청. AI 결정은 결정권자·확정일 비움, 추정 관련자는 '(미확인)'으로 본문에만. 목록 기본 상태 '제안'. 새 열 `FollowUps`·`ConfirmationGap`: 사람이 '확정'으로 바꾸면 F4가 빈 결정권자·근거·후속조치를 표시(루프 없음). 브리핑에 '확정 대기 제안 N건' | test_audit A5(4건), test_scenarios S03·S06, test_email_mode C01 |
| P1-1 | P1 | 최소 구성 없이 13개 흐름 전체를 전제(구축·유지 부담) | — | **A안**: 목록 2 + 흐름 2(+F3 선택), Office Scripts 없음. P3A-2는 필터·선택·HTML 표만으로 초과·임박·기한 없음·방치 경고 메일 | test_audit A6(3건, B안 전환 시 중복 없음 포함) |
| P1-2 | P1 | Catch: 시간 초과 액션 누락, 실패 배열이 비면 빈 값, 오류 로그 기록 실패 시 아무도 모름, 오류 메시지 길이 무제한 | build_flows.py `catch()` | 실패·시간 초과 모두 수집, 비면 '식별 불가', 조건 안쪽 실패는 위치 안내, **300자 제한·업무 내용 미포함**, 로그 기록 실패 시 본인 메일 직접 알림(Teams 미경유) | test_audit A7(4건), test_scenarios F01·P01 |
| P1-3 | P1 | 알림 수신자 검사가 실행 시에만(에뮬레이터) 존재 | — | lint L12: 모든 메일·Teams 알림의 받는 사람이 본인(설정 me)인지 정적 검사(예외: 프로토타입 모드 검사 안쪽) | test_audit `test_every_notification_goes_to_me_only` |
| P1-4 | P1 | 기대효과 109h·181.8h가 추가 관리·오류 복구 시간을 빼지 않음, 업무량이 다른 기간을 그대로 비교 | kpi_report.py | 순절감 = 기존 − 개선 후 − **추가 관리 − 유지보수 − 오류 복구**. 시간기록에 '처리건수'·'추가 관리'·'오류 복구' 칸, 건당 시간으로 업무량 보정. 모든 값에 근거 구분(가정) | test_kpi 3건 |
| P1-5 | P1 | 기록일을 미래 날짜(2026-10-26)로 표기 | 12_Open_Questions, START_HERE 등 11개 파일 | 실제 작업일 2026-10-25로 정정(가상 테스트 데이터 날짜는 유지) | 수동 확인(grep) |

## 3. 남은 위험(미확인·잔여)

| # | 위험 | 왜 남는가 | 대응 |
|---|---|---|---|
| R1 | V4 트리거 출력에 `internetMessageId`·`flag/flagStatus`·`categories` 가 실제로 있는지 | 출력 스키마 미확인(D4) | 없으면 지문 키로 동작(테스트 완료). 첫 실행 원시 출력 확인(T-T1) |
| R2 | Get item → Update item 사이 수 초 동안 사람이 같은 항목을 고치면 사람 값이 덮어써질 수 있음 | SharePoint 커넥터 Update item에 버전 조건(ETag) 입력이 없는 것으로 앎(미확인) | 자동 갱신을 '바뀐 것이 있을 때만'으로 줄임. 목록 버전 기록 켬(되돌리기 가능) |
| R3 | Run script 출력 경로 | D3 | T-T2 스모크 테스트 |
| R4 | 플래그 기한 `flag/dueDateTime` 의 시간대 | 출력 형식 미확인 | 첫 실행에서 기한 하루 밀림 여부 확인(T-T3) |
| R5 | 완료 후 재플래그 감지는 '변경 이벤트'일 뿐 재플래그인지 구분 못 함 | V4가 모든 변경에 반응(D1) | 자동 재오픈하지 않고 확인 요청(하루 1회)으로 설계 — 오탐 비용이 메일 1통 |
| R6 | 사후 중복 점검 사이 아주 짧은 경합 | 두 실행이 거의 동시에 만들고 동시에 점검하면 둘 다 상대를 볼 수 있음 → 나중 ID만 취소되므로 안전, 반대로 둘 다 못 보는 경우는 이론상 남음 | 선택: SourceKey에 '고유 값 적용'(NOT TESTED, 빈 값·기존 행 확인 후) |
| R7 | Office 365 Outlook 연결 만료 시 트리거 자체가 안 돌면 Catch도 안 돈다 | 플랫폼 동작 | 아침 메일이 안 오면 그것이 신호. Power Automate의 흐름 실패·연결 알림 메일 확인(주 1회) |
| R8 | 메일 모드에서도 정의에 Teams 액션이 있으면 저장 시 Teams 연결을 요구할 수 있음 | 미확인 | 메일 모드에서는 조건의 Teams 분기를 비워 둔다(DEPENDENCY_MATRIX 4장) |
| R9 | 기대효과 수치 | 전부 가정 | 4주 측정 후 실측 업무만 교체 |

## 4. 이번 감사로 바뀐 파일
`CHANGELOG.md` 참조. 생성 파일(BUILD_TABLES.md·LISTS_SETUP.md·DEPENDENCY_MATRIX.md·flows/*.json·lists/*.csv·sandbox/*)은 모두 원본(`tools/build_flows.py`, `lists/lists_schema.json`, `tools/*.py`)을 고친 뒤 다시 생성했다.
