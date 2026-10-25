# m365-productivity-blueprint

KT&G SCM 조직을 위한 Microsoft 365 기반 업무 방식 혁신 설계와 구현 자산. 먼저 `00_Executive_Summary.md`를 읽으세요.

## 구성

```
00_Executive_Summary.md          결론·효과·TOP10·TOP3·90일·미래 기회
01_Current_State_Assessment.md   환경·가정·업무 원자 분해·진단 체크리스트
02_M365_Technology_Map.md        기술별 제공 상태·라이선스·권한·검증 등급
03_Productivity_Opportunity_Backlog.md  혁신 과제 35개
04_Prioritization_Matrix.csv     의사결정 매트릭스(tools/build_backlog.py가 생성)
05_Target_Architecture.md        통합 아키텍처·저장소 선정·경량판·공통 패턴
06_TOP10_Use_Cases.md            TOP10·파일럿 TOP3 선정
07_Licensing_Security_Review.md  Scenario A/B/C·보안 규칙·위험 등록부
08_90_Day_Roadmap.md             Phase 1~4·오늘 할 일
09_KPI_ROI_Model.csv             파일럿 KPI·ROI(tools/build_backlog.py가 생성)
10_Management_Presentation_Outline.md
11_Official_Sources.md           공식 출처(검증일·등급)
12_Open_Questions_and_Decisions.md
13_Quality_Self_Assessment.md
pilots/pilot_01  통합 업무요청 허브       (process_design, implementation_guide, test_cases, automation_assets)
pilots/pilot_02  공장 데이터 계약·자동 검증
pilots/pilot_03  결정–액션 루프 + 아침 브리핑
tools/           build_backlog.py, check_consistency.py, run_all_checks.sh
```

## 로컬 검증 (가상 데이터만 사용, 외부 접속 없음)

필요: Python 3.10+, Node 18+, TypeScript(`tsc`). 선택: `openpyxl`(템플릿 생성·검사).

```bash
./tools/run_all_checks.sh
```

2026-10-25 실행 결과: Pilot 01 19건, Pilot 02 Python 5건 + Office Scripts 15건, Pilot 03 10건 테스트 통과, 정합성 검사 29/29 통과.

## 주의
- 회사 M365 테넌트에 배포되지 않았다. 배포는 각 `implementation_guide.md`를 따른다.
- 샘플 데이터·이메일·이름은 모두 가상이다. 실제 업무 데이터를 이 저장소에 넣지 마라.
- 수치는 가정이다. 실측은 `09_KPI_ROI_Model.csv`의 KPI 정의대로 측정한다.
