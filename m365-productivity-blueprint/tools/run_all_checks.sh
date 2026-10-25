#!/usr/bin/env bash
# 모든 로컬 테스트·정합성 검사 일괄 실행 (가상 데이터만 사용, 외부 접속 없음)
# 필요: Python 3.10+, Node 18+, TypeScript(tsc). 선택: openpyxl(템플릿 검사), pandas(없어도 됨)
set -euo pipefail
cd "$(dirname "$0")/.."
echo "== 1. 우선순위 매트릭스·ROI 모델 재생성"; python3 tools/build_backlog.py > /dev/null && echo ok
echo "== 2. Pilot 01 규칙 테스트"; (cd pilots/pilot_01/automation_assets && python3 -m unittest -q test_request_hub_rules.py)
echo "== 3. Pilot 02 Python 검증기 테스트"; (cd pilots/pilot_02/automation_assets && python3 -m unittest -q python/test_psi_validator.py > /dev/null)
echo "   ok"
echo "== 4. Pilot 02 Office Scripts(strict 컴파일 + 모의 Workbook) 테스트"; (cd pilots/pilot_02/automation_assets && node --test tests/office_scripts.test.js 2>&1 | grep -E "^# (pass|fail)")
echo "== 5. Pilot 03 브리핑·AI 추출 가드 테스트"; (cd pilots/pilot_03/automation_assets && python3 -m unittest -q python/test_pilot03.py)
echo "== 6. 정합성 검사"; python3 tools/check_consistency.py | tail -1
echo "== 7. Pilot 03 프로토타입: 흐름 lint"; (cd pilots/pilot_03/prototype && python3 tools/lint_flows.py | grep -c PASS | xargs -I{} echo "{}/9 흐름 통과")
echo "== 8. Pilot 03 프로토타입: 에뮬레이터 시나리오·Office Scripts 교차 검증·변이·KPI"; (cd pilots/pilot_03/prototype && python3 -m unittest -q tests/test_scenarios.py tests/test_office_scripts.py tests/test_mutations.py tests/test_kpi.py tests/test_email_mode.py 2>&1 | grep -E "^(Ran|OK|FAILED)")
