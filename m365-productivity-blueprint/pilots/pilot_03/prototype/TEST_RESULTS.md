# TEST_RESULTS — 감사 후 테스트 결과

> 실행일 **2026-10-25(KST)** · 데이터 전부 가상 · 실행 명령: `bash m365-productivity-blueprint/tools/run_all_checks.sh`
> 판정: **PASS** = 이 환경에서 실제로 실행해 통과(로컬 에뮬레이터 또는 실제 TypeScript 실행) · **FAIL** = 실행해 실패 · **NOT TESTED** = 실행하지 못함(코드 검토만 한 것은 PASS가 아니다)
> **로컬 PASS ≠ 회사 M365에서 성공.** 에뮬레이터는 공식 문서 기반 가정으로 만든 가짜 커넥터다(LIMITATIONS.md 3장). 테넌트 항목(T-T*)은 전부 NOT TESTED.

## 1. 전체 실행 결과

| 검사 | 결과 |
|---|---|
| 흐름 정적 검사(lint L1~L12) | 15/15 흐름 통과 |
| 구축 순서 의존성 검사 | 통과(흐름 15, 단계 5) |
| 단위·시나리오·교차 검증·변이 테스트 | **124건 실행, 124 통과, 0 실패** (test_scenarios 34, test_office_scripts 15, test_mutations 8, test_kpi 3, test_email_mode 8, test_extensions 19, test_audit 37) |
| 저장소 정합성 검사 | 29/29 |
| 에뮬레이터 모드 | **엄격 모드**: Update item에서 입력하지 않은 열은 지워진다고 가정(최악의 경우) |

## 2. 감사 지시서의 최소 테스트

| # | 시나리오 | 판정 | 실행한 테스트 | 확인 내용 |
|---|---|---|---|---|
| 1 | 메일 최초 플래그 → 할 일 1개 생성 | **PASS** | test_audit `A1.test_first_flag_creates_exactly_one_with_stable_key`, test_scenarios S01 | 1건, 고유키 `imid|…`, 기한·자동 기한 기록 |
| 2 | 같은 메일 재플래그 → 새 할 일 없음 | **PASS** | `A1.test_reflag_and_other_changes_write_nothing`, D01, D02 | 3회 재실행 후에도 1건, 수정 시각까지 그대로(쓰기 없음) |
| 3 | 범주 변경 → 정의한 정책대로 처리 | **PASS** | `A1.test_category_added_later_creates_linked_decision_and_keeps_action`, `…decision_only_mail_does_not_spawn_action…`, C01~C03 | 할 일 유지 + 결정요청 연결 생성, 범주 제거 시 삭제·생성 없음 |
| 4 | 기한 없는 할 일이 브리핑에 표시 | **PASS** | test_office_scripts `test_undated_and_others_actions`, `test_undated_priority_age_and_neglect_warning`, test_audit A2, A6 | TOP5 후보 + 별도 칸 + 방치 경고, 기한을 만들지 않음 |
| 5 | 기한 초과 할 일이 우선순위 규칙대로 정렬 | **PASS** | 교차 검증(TS = Python), S04, `test_undated_priority_age…` | 초과 100+5/일 > 오늘마감 80 > … , 우선순위 가감 |
| 6 | 완료 항목은 브리핑에서 제외 | **PASS** | A2, A6 `test_mva_brief…`, `test_undated_priority…` | 완료·남의 일·먼 미래 기한 제외 |
| 7 | SharePoint 항목 갱신 시 기존 필드 보존 | **PASS** | A4 `test_status_changes_through_f3…`, `test_reminder_and_due_hint…`, `test_only_approved_ai_candidates…`, 변이 `test_mutation_dropping_a_column…` | 엄격 모드에서 바꾼 열 외 전부 동일. 열 하나 빼면 실제로 값이 사라짐(검증 장치 작동 확인) |
| 8 | 반복 수정에도 무한 루프 없음 | **PASS** | A4 `test_many_edits_stay_bounded`, A5 `test_confirmation_gap…`, 변이 `test_removing_prevstatus_sync…`, Z_AllTogether | 실행 횟수 상한 이내, 보호 장치 제거 시 루프 검출 |
| 9 | 연결 실패 시 오류 로그·사용자 확인 | **PASS** | A7 `test_outlook_connection_expired…`, `test_error_log_write_failure…`, F01~F05, P01~P03 | 401 → FlowErrorLog(300자, 업무 내용 없음), 로그 실패 시 본인 메일 |
| 10 | Copilot 추출 오류 시 자동 등록 금지 | **PASS** | A5 `test_bad_extraction_is_never_registered`, S07, M04 | 접수 '오류', 후보·할 일 0건, 원문 보존 |
| 11 | AI 후보 승인 후에만 등록 | **PASS** | A5 `test_only_approved_ai_candidates_are_registered`, S06, D04 | 승인 전 0건, 승인 1건 → 1건만, 결정은 '제안' |
| 12 | 팀 알림 기능은 본인에게만 | **PASS** | P04, E02, A7 `test_every_notification_goes_to_me_only`(lint L12) | 다른 담당자 몫은 발송 안 하고 건수만 본인에게 |

## 3. 감사 추가 테스트(P0별)

| P0 | 테스트 | 판정 |
|---|---|---|
| P0-1 구축 순서 | A8: 현재 순서 통과 / F1을 1주차로 옮기면 'DecisionLog·선행 흐름 F4 없음'으로 실패 / F12를 FactoryInbox 전에 두면 실패 | PASS(3) |
| P0-2 멱등 | 폴더 이동(메일 ID 변경) 1건 유지·링크 갱신 / 같은 제목 다른 메일 2건 / imid 없을 때 지문 키 / 수신 시각 다른 메일 분리 / 플래그 기한 변경 반영·사람 기한 유지 / 완료 후 재플래그 자동 재오픈 없음·알림 1회 / Outlook 플래그 완료 시 확인 요청 / 동시성으로 못 막는 경합 → 나중 것 '취소' / 실패 후 재시도 중복 없음 | PASS(13) |
| P0-3 기한 없음 | 위 #4 | PASS |
| P0-4 스크립트 위치 | 모든 스크립트 액션 = Run script(OneDrive) 6개 / OneDrive 스크립트 폴더에 없으면 오류 로그 / 경로형 스크립트 지정 거부 | PASS(3) |
| P0-5 보존 | 위 #7·#8 + F13은 F3 번호 부여 뒤에만 실행 | PASS(6) |
| P0-6 결정 상태 | 확정 시 빈 칸 표시·채우면 해제(루프 없음) / 수동 입력 기본값 '제안' / AI 결정 결정권자·확정일 비움 | PASS(4) |
| A안 | DecisionLog·스크립트 없이 동작 / 초과·임박·기한 없음·방치 경고 메일 / A안→B안 전환 시 중복 없음 | PASS(3) |

## 4. 회사 테넌트에서만 확인 가능한 항목 — 전부 NOT TESTED

| ID | 확인 | 방법(본인 범위, 가상 메일) | 통과 기준 |
|---|---|---|---|
| T-T1 | V4 트리거 출력에 `internetMessageId`·`categories`·`flag/flagStatus`·`flag/dueDateTime` 존재 | P3A-1 첫 실행 기록 › 트리거 › 원시 출력 보기 | 필드 이름 일치. 없으면 지문 키로 동작하는지 확인 |
| T-T2 | Run script 출력 경로 `body/result` | 스모크 흐름(BUILD_GUIDE 3.1) | `result.top` 보임 |
| T-T3 | 플래그 기한 시간대(하루 밀림 여부) | 기한 '내일'로 플래그 | 목록 기한 = 내일 |
| T-T4 | 메일을 다른 폴더로 옮겼다가 받은 편지함으로 되돌린 뒤 플래그 기한 변경(F1은 받은 편지함만 감시) | 가상 메일 1통 | 할 일 1건 유지, 원문 링크 열림 |
| T-T5 | Outlook에서 '완료 표시' 시 V4 실행 여부 | 플래그 완료 | 실행되면 확인 요청 메일 1통, 안 되면 '목록에서 직접 완료' 습관 |
| T-T6 | Update item 보존(실제 커넥터) | 상태 바꾼 뒤 버전 기록 비교 | 근거·링크·기한 그대로 |
| T-T7 | 메일 모드에서 Teams 분기를 비운 흐름 저장 가능 | 저장 | 오류 없음 |
| T-T8 | DLP: SharePoint+Outlook(+Excel) 동일 흐름 저장 | 저장 | 경고 없음 |
| T-T9 | 오류 알림: 일부러 없는 목록 이름으로 실패시키기 | 사본 흐름 | FlowErrorLog 1줄 또는 본인 메일 1통 |

## 5. 운영 적용 판단
- P0 6건: 소스 수정 + 로컬 PASS.
- **테넌트 확인(T-T1~T-T9): 0/9.** 따라서 **운영(팀·타인 대상) 적용을 권고하지 않는다.** 본인 범위의 A안 시험(START_HERE_V2 1주차)만 권고한다.
