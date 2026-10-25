# 결정 조회 에이전트 — Agent Builder 설정 (Copilot 라이선스 보유 → 사용 가능 범위)

설정서·지침·평가셋은 기존 자산을 그대로 쓴다: `../../automation_assets/agent/decision_assistant_instructions.md`, `instructions.txt`, `eval_cases.json`.

## 클릭 순서
1. Microsoft 365 Copilot 앱 → 왼쪽 **에이전트(Agents)** → **에이전트 만들기(Create agent)** (또는 '새 에이전트')
2. **구성(Configure)** 탭
   - 이름: `SCM 결정 조회 도우미(샌드박스)` · 설명: `결정 레지스터에서 결정·근거를 출처와 함께 찾아줍니다. 읽기 전용.`
   - 지침(Instructions): `instructions.txt` 전체 붙여넣기(611자, 한도 8,000자)
   - 지식(Knowledge): **SharePoint** → 샌드박스 `DecisionLog` 목록 선택(목록은 1개만 지원) · 근거 문서 폴더가 있으면 추가
   - 웹 콘텐츠/웹 검색: **끔**
   - 시작 문구: 설정서의 4개
3. 오른쪽 **테스트 패널**에서 `eval_cases.json` 12문항을 차례로 입력 → 결과를 `TEST_REPORT.md` 3장 표에 기록
4. 합격(정답 ≥10/12, 환각 0, '찾지 못함' 3/3, 출처 100%) 시 **만들기(Create)** → 본인만 사용. 팀 공유는 운영 전환 후.

## 막힐 수 있는 지점(IT 확인)
- **Restricted SharePoint Search**가 켜져 있으면 SharePoint 지식을 추가할 수 없다(S22).
- 개인 '내 목록'(OneDrive)의 목록이 지식 선택 화면에 안 보이면, 샌드박스 목록을 팀 사이트에 `SBX_` 접두어로 만들어 사용한다.
- 에이전트 만들기 메뉴 자체가 없으면 관리자가 에이전트 생성을 제한한 것 → IT에 요청(아래 APPROVALS.md I-05).
