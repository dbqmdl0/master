# Pilot 03 프로토타입 — 결정–액션 루프 + 아침 브리핑 + Copilot 회의 추출

> **처음이라면 [`START_HERE_V2.md`](START_HERE_V2.md)부터** — 설계 감사(2026-10-25) 반영판. A안(최소 구성) 1주차 → B안 4주 확장. 기존 `START_HERE.md`는 검증 전까지 보존.
> 감사 결과: `AUDIT_REPORT.md`(P0 6건 수정) · `TEST_RESULTS.md`(로컬 124건 PASS, 테넌트 9건 NOT TESTED) · `SIMPLIFIED_ARCHITECTURE.md`(A안 vs B안) · `DEPENDENCY_MATRIX.md`(흐름별 선행 조건) · `ROLLBACK_PLAN.md` · `CHANGELOG.md

선정 이유: `01_PILOT_SELECTION.md` — 현재 권한(팀 사이트 목록 생성 가능)·라이선스(Copilot 보유)로 구현 가능하고, 타 부서 참여 없이 첫날부터 효과가 나며, 절감 기대치가 가장 크다.

## 무엇이 동작하나 (사용자 관점)
1. **메일에 플래그만 하면** 할 일(액션)로 등록된다. 보낸 메일에 플래그하면 '회신 대기'로 추적된다. 같은 메일을 다시 플래그해도 중복되지 않는다.
2. **Outlook 범주 + 플래그**로 결정요청·결정 제안을 기록한다(Teams 메시지 바로 기록 P3P-F5는 Workflows 앱이 없어 보류). 자동화는 '확정'을 만들지 않는다 — 확정은 사람이 목록에서.
3. **평일 07:40** 본인 Teams로 '오늘 먼저 처리할 5가지'(기한초과·결정대기·오늘마감 순)와 집중 가능 시간, 안건 없는 내 주관 회의 경고가 온다. Teams가 막혀 있으면 메일로 온다.
4. **평일 08:30** 기한 임박·초과 액션을 담당자별 하루 1장으로 알린다(프로토타입은 본인에게만).
5. **회의 후 Copilot이 뽑은 결정·액션**을 붙여넣으면, 근거 문장이 회의록에 실제로 있는지·담당자가 명부에 있는지·기한을 지어내지 않았는지 자동 검사해 '후보'로 만든다. **사람이 승인한 것만** 등록된다.
6. 🆕 공장 첨부 메일 자동 저장·수신 대장, 메일 문구로 기한 추정, 다음 날 회의 준비 메일, 금요일 주간보고 초안(`02_ADDITIONAL_AUTOMATIONS.md`).
7. Copilot 에이전트로 "그거 누가 언제 왜 결정했지?"를 출처와 함께 찾는다.

## 파일
| 경로 | 내용 |
|---|---|
| `01_PILOT_SELECTION.md` | 파일럿 선정 근거(답변 반영 재평가) |
| `BUILD_GUIDE.md` | **클릭 순서 구축 가이드**(사전 점검 → 목록 → 스크립트 → 흐름 → Copilot → 테스트 → 운영 전환) |
| `BUILD_TABLES.md` | 흐름 15개(A안 2 + B안 13)의 액션별 입력값 표(자동 생성) |
| `DEPENDENCY_MATRIX.md` | 흐름별 목록·열·커넥터·스크립트·선행 흐름·첫 테스트(자동 생성·검사) |
| `LISTS_SETUP.md` | 목록 9개의 열 설정표(자동 생성) |
| `02_ADDITIONAL_AUTOMATIONS.md` | 🆕 추가 자동화 후보 10개 평가·선정 4개(공장 자료 저장·회의 준비·주간 정리·기한 추정) |
| `TEST_RESULTS.md` | 감사 후 결과(PASS/FAIL/NOT TESTED) — 로컬 124건 PASS, 테넌트 9건 NOT TESTED |
| `TEST_REPORT.md` | 감사 전 테스트 설계·결과(84건) + 테넌트 테스트 T01~T18 |
| `APPROVALS.md` | 사용자 승인 / 팀장 결정 / IT 지원 구분 + IT 요청 메일 초안 |
| `MEASUREMENT.md` | 기대효과(B안 개인 순절감 153.0h/년, A안 32.8h/년, 모두 가정)와 검증 방법 |
| `LIMITATIONS.md` | 구현 못 한 부분·원인·대체안, 에뮬레이터 한계 |
| `office_scripts/` | BuildDailyBrief · BuildReminderDigest · GuardExtraction · 🆕 ParseDueHint · BuildMeetingPrep · BuildWeeklyDigest |
| `flows/` | 흐름 정의 15개(JSON, `tools/build_flows.py`가 생성) — `P3A-*` A안, `P3P-*` B안 |
| `lists/` | 목록 스키마 + 가상 데이터 CSV 7개 |
| `copilot/` | 회의 추출 프롬프트, 예약 프롬프트, 결정 조회 에이전트 설정 |
| `sandbox/` | 스크립트 호스트 통합 문서, 테넌트 첫 실행 점검용 입력·기대 결과(`smoke/`) |
| `measurement/` | 기대효과 CSV, 시간기록 양식 |
| `emulator/` | Power Automate 식·흐름 실행기, 가짜 커넥터(로컬 검증 전용) |
| `tests/` | 시나리오·Office Scripts 교차 검증·변이·KPI 테스트 |
| `tools/` | 흐름 생성, lint, 입력표 생성, 샌드박스 파일 생성, KPI 보고서 |

## 로컬에서 다시 검증하기
```bash
cd m365-productivity-blueprint/pilots/pilot_03/prototype
python3 tools/build_flows.py            # 흐름 정의 재생성(수정 시)
python3 tools/lint_flows.py             # 정적 검사
python3 tools/render_build_tables.py    # 입력표 재생성
python3 -m unittest tests/test_scenarios.py tests/test_office_scripts.py tests/test_mutations.py tests/test_kpi.py tests/test_email_mode.py tests/test_extensions.py
```
필요: Python 3.10+, Node 18+, TypeScript(`tsc`). 외부 접속 없음, 가상 데이터만 사용.

## 수정할 때의 규칙
흐름을 바꾸려면 `BUILD_TABLES.md`가 아니라 `tools/build_flows.py`를 고친다 → 흐름 재생성 → lint → 테스트 → 입력표 재생성 → 테넌트 반영. 그래야 문서·테스트·실제 흐름이 같은 원본을 유지한다.
