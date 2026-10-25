# CHANGELOG — Pilot 03 프로토타입

## 2026-10-25 · 설계 감사 반영 (AUDIT_REPORT.md)

### 수정(원본)
- `tools/build_flows.py`
  - `flag_flow`: 고유키 `SourceKey`(internetMessageId 또는 지문) + 멱등 갱신 규칙 + 사후 중복 점검. 재플래그·폴더 이동·플래그 기한 변경·완료 후 재플래그·플래그 완료·범주 변경 처리(P0-2)
  - `script()`: 'Run script from SharePoint library' → **'Run script'(OneDrive)**, 스크립트는 이름으로(P0-4)
  - `preserve()`·`update_preserving()`: 모든 Update item을 '최신 값 읽기 → 전체 열 보존 → 바꿀 열만 변경'으로(F1·F3·F4·F7·F8·F9·F13, P0-5)
  - `numbering_flow`: 트리거 값 대신 Get item 최신 값 사용, 이미 처리된 실행 종료. F4에 `ConfirmationGap` 계산(P0-6)
  - F1·F5·F9: 자동화는 '확정'을 만들지 않음('결정' → '제안'), AI 결정의 결정권자·확정일 비움(P0-6)
  - F6: 결정 조회에 '내가 만든 제안' 포함(확정 대기 건수)
  - F8: 접수 항목 최신 값 재확인 후 처리, F13: 트리거 조건에 '액션번호 있음', 자동 기한(`FlagDue`) 기록
  - `catch()`: 시간 초과 포함, 빈 실패 배열·조건 안쪽 실패 안내, 300자 제한, 오류 로그 실패 시 본인 메일
  - **신규 A안 흐름** `P3A-1`(플래그 → 할 일, DecisionLog 없음), `P3A-2`(간단 아침 메일, Office Scripts 없음)
- `lists/lists_schema.json`: ActionItems `SourceKey`·`FlagDue`·`SyncNote`, DecisionLog `FollowUps`·`ConfirmationGap`·`SourceKey`·`SyncNote`, DecisionLog 상태 기본값 '확정' → **'제안'**, 선택지 '취소' 추가, 보기 '확정 대기 제안'·'확정 확인 필요'
- `office_scripts/BuildDailyBrief.ts`·`automation_assets/python/daily_brief.py`: 기한 없는 할 일 점수·별도 칸·방치 경고, 우선순위 가감, 확정 대기 제안 건수(P0-3). TOP5 규칙을 머리 주석에 명시
- `emulator/fakes.py`: Update item **엄격 모드**(입력 안 한 열은 지워짐), Get items 정렬, OneDrive 'Run script'(문서/Office Scripts에서만 스크립트 찾기)
- `emulator/runtime.py`: 'HTML 표 만들기' 액션, Run script(OneDrive) 경로, 경합 강제 재현(`force_race`), 자기 쓰기 후 최신 읽기
- `tools/lint_flows.py`: L10(Update item 전체 열), L11(개인 파일럿 Run script), L12(알림 수신자 = 본인)
- `tools/render_build_tables.py`: 보존 패턴·HTML 표·선택 액션·Run script 입력란 표시, 요일 표기 수정(F12 금요일)
- `tools/kpi_report.py`: 순절감 = 기존 − 개선 후 − 추가 관리 − 유지 − 오류 복구, A안 모델, 업무량 보정(처리건수), 근거 구분
- `tools/make_sandbox_files.py`: 호스트 통합 문서 안내문을 OneDrive Run script 기준으로
- `measurement/timelog_template.csv`: '처리건수' 열, '추가 관리(자동화)'·'오류 복구' 행, 날짜 자리표시(YYYY-MM-DD)
- `m365-productivity-blueprint/tools/run_all_checks.sh`: test_audit 포함, 9단계 의존성 검사 추가

### 신규
- `tools/dependency_matrix.py` → `DEPENDENCY_MATRIX.md`(생성 + 구축 순서 자동 검사)
- `tests/test_audit.py`(37건)
- `AUDIT_REPORT.md`, `SIMPLIFIED_ARCHITECTURE.md`, `TEST_RESULTS.md`, `ROLLBACK_PLAN.md`, `START_HERE_V2.md`, `CHANGELOG.md`

### 재생성(직접 수정하지 않음)
- `flows/*.flow.json`(15개), `BUILD_TABLES.md`, `LISTS_SETUP.md`, `DEPENDENCY_MATRIX.md`, `lists/*.csv`, `sandbox/*`, `measurement/expected_savings.csv`

### 테스트 변경(동작 변경에 따른 기대값 수정)
- 재플래그 종료 코드 `Duplicate` → `NoChange`(D01·C02)
- '결정' 기록 상태 '확정' → '제안', 확정일 없음(S03·S06·C01)
- 조건 안쪽 실패의 오류 로그: 실패 위치 안내 + 상세는 실행 기록(F01·P01)
- 브리핑: 기한 없는 할 일이 TOP5 후보(test_undated_and_others_actions), 교차 검증에 기한 없음·우선순위 사례 추가
- KPI 모델 기대값 181.8h → 153.0h(추가 관리·오류 복구 차감)

### 문서 정정
- 기록일 미래 날짜(2026-10-26) → 실제 작업일 2026-10-25: `12_Open_Questions_and_Decisions.md`, `README.md`, `APPROVALS.md`, `BUILD_GUIDE.md`, `01_PILOT_SELECTION.md`, `MEASUREMENT.md`, `TEST_REPORT.md`, `02_ADDITIONAL_AUTOMATIONS.md`, `LIMITATIONS.md`, `START_HERE.md`(가상 테스트 데이터의 날짜는 유지)
- `START_HERE.md`는 보존하고 맨 위에 START_HERE_V2 안내만 추가(새 가이드 검증 전까지)

## 이전
- 추가 자동화 F10~F13, 프롬프트 팩 (커밋 8a829ec)
- Workflows 앱 없음 대응: 메일 알림 모드, Outlook 범주 결정 기록 (3e48232)
- START_HERE 단계 가이드 (0efff7e)
