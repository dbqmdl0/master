# Pilot 03 프로토타입 — 결정–액션 루프 + 아침 브리핑 + Copilot 회의 추출

> **처음이라면 `START_HERE.md`부터** — 4주 단계별 따라하기 가이드.

선정 이유: `01_PILOT_SELECTION.md` — 현재 권한(팀 사이트 목록 생성 가능)·라이선스(Copilot 보유)로 구현 가능하고, 타 부서 참여 없이 첫날부터 효과가 나며, 절감 기대치가 가장 크다.

## 무엇이 동작하나 (사용자 관점)
1. **메일에 플래그만 하면** 할 일(액션)로 등록된다. 보낸 메일에 플래그하면 '회신 대기'로 추적된다. 같은 메일을 다시 플래그해도 중복되지 않는다.
2. **Teams 메시지 → 추가 작업**에서 결정·결정요청·액션을 클릭 몇 번으로 기록한다. 원문 링크와 본문이 근거로 남는다.
3. **평일 07:40** 본인 Teams로 '오늘 먼저 처리할 5가지'(기한초과·결정대기·오늘마감 순)와 집중 가능 시간, 안건 없는 내 주관 회의 경고가 온다. Teams가 막혀 있으면 메일로 온다.
4. **평일 08:30** 기한 임박·초과 액션을 담당자별 하루 1장으로 알린다(프로토타입은 본인에게만).
5. **회의 후 Copilot이 뽑은 결정·액션**을 붙여넣으면, 근거 문장이 회의록에 실제로 있는지·담당자가 명부에 있는지·기한을 지어내지 않았는지 자동 검사해 '후보'로 만든다. **사람이 승인한 것만** 등록된다.
6. Copilot 에이전트로 "그거 누가 언제 왜 결정했지?"를 출처와 함께 찾는다.

## 파일
| 경로 | 내용 |
|---|---|
| `01_PILOT_SELECTION.md` | 파일럿 선정 근거(답변 반영 재평가) |
| `BUILD_GUIDE.md` | **클릭 순서 구축 가이드**(사전 점검 → 목록 → 스크립트 → 흐름 → Copilot → 테스트 → 운영 전환) |
| `BUILD_TABLES.md` | 흐름 9개의 액션별 입력값 표(자동 생성) |
| `LISTS_SETUP.md` | 목록 7개의 열 설정표(자동 생성) |
| `TEST_REPORT.md` | 테스트 설계·결과(로컬 56건 통과) + 테넌트 테스트 T01~T15 |
| `APPROVALS.md` | 사용자 승인 / 팀장 결정 / IT 지원 구분 + IT 요청 메일 초안 |
| `MEASUREMENT.md` | 기대효과(개인 순절감 108.7h/년, 가정)와 검증 방법 |
| `LIMITATIONS.md` | 구현 못 한 부분·원인·대체안, 에뮬레이터 한계 |
| `office_scripts/` | BuildDailyBrief · BuildReminderDigest · GuardExtraction (TypeScript) |
| `flows/` | 흐름 정의 9개(JSON, `tools/build_flows.py`가 생성) |
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
python3 -m unittest tests/test_scenarios.py tests/test_office_scripts.py tests/test_mutations.py tests/test_kpi.py
```
필요: Python 3.10+, Node 18+, TypeScript(`tsc`). 외부 접속 없음, 가상 데이터만 사용.

## 수정할 때의 규칙
흐름을 바꾸려면 `BUILD_TABLES.md`가 아니라 `tools/build_flows.py`를 고친다 → 흐름 재생성 → lint → 테스트 → 입력표 재생성 → 테넌트 반영. 그래야 문서·테스트·실제 흐름이 같은 원본을 유지한다.
