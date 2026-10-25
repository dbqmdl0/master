# Pilot 02 — 구현 가이드 (실무자용)

> 소요: 약 3일(계약 합의 1일, 구축 1.5일, 테스트 0.5일). 먼저 **A-lite(Power Query)로 1주 운영**해 계약을 안정시킨 뒤 B(자동 흐름)로 올린다.
> 메뉴 표기는 `영문(한국어 예상)`. 확인하지 못한 경로는 '(확인 필요)'.

---

## 0. 준비물
- `automation_assets/templates/PlantSubmission_Template.xlsx` (제출 템플릿, 표 `tblSubmit`, 숫자 유효성 검사 포함)
- `automation_assets/templates/SCM_Master_Fact.xlsx` (마스터, 표 `tblFact`·`tblSKU`, 시트 `Exceptions` — **모의 이력 데이터 포함, 운영 전 tblFact 데이터 행 삭제·tblSKU를 실제 SKU로 교체**)
- `automation_assets/office_scripts/*.ts` 3개
- 로컬 재생성: `python3 make_samples.py` (가상 데이터)

## 1. 데이터 계약 합의 (1일, 사람의 일)
1. `data_contract.json`의 열·규칙을 공장 담당자와 30분 회의로 검토 → 합의 결과를 계약 v1.0으로 확정
2. 결정사항을 Pilot 03 DecisionLog에 기록(예: "DEC: 공장 주간 제출 데이터 계약 v1.0 적용, 2026-W46부터")
3. 제출 마감(예: 매주 화 12:00), 공장코드 목록, 담당자 명단 확정

## 2. SharePoint 구성 (30분)
1. 팀 사이트 → **New(새로 만들기) → Document library(문서 라이브러리)** `SCM_Submissions` → 폴더 `2026-W46/PLT-A`, `2026-W46/PLT-B` …(주차 폴더는 P2-F2가 매주 만들게 확장 가능, 파일럿은 수동)
2. 라이브러리 `SCM_Master` 에 `SCM_Master_Fact.xlsx` 업로드 → 공유: SCM 팀 **읽기**만(편집은 운영자)
3. 라이브러리 `SCM_Automation/Scripts` 생성(스크립트 보관)
4. Lists `SubmissionLog`, `SubmissionCalendar` 생성(`flows_spec.json`의 lists 열 정의)
5. 공장 담당자에게 자기 공장 폴더 **편집** 권한 — *권한 변경이므로 사이트 소유자 승인 후. 해외 공장이 외부 계정이면 외부 공유 정책 확인(`12` Q-07)*

## 3. A-lite: Power Query로 1주 운영 (1시간)
1. Excel 데스크톱 → 새 통합 문서 → **Data(데이터) → Get Data(데이터 가져오기) → From Other Sources(기타 원본에서) → Blank Query(빈 쿼리)**
2. **Advanced Editor(고급 편집기)** → `power_query/CombinePlantSubmissions.pq` 붙여넣기 → `SiteUrl`, `TargetWeek` 수정 → 완료 → 로그인(조직 계정)
3. **Close & Load(닫기 및 로드)** → 결과 표에서 `CheckFlag` ≠ "OK" 필터 → 공장별 오류 회신
4. (선택) 각 제출 파일에 Python 셀: **Formulas(수식) → Insert Python(Python 삽입)** → `python/python_in_excel_cell.py` 붙여넣기 → Ctrl+Enter. *Python in Excel은 Microsoft 클라우드에서 실행된다 — 사내 정책 확인 후 사용*

## 4. Office Scripts 등록 (30분)
1. 웹 Excel에서 `SCM_Master_Fact.xlsx` 열기 → **Automate(자동화) → New Script(새 스크립트)**
2. 편집기 내용을 지우고 `AppendToMaster.ts` 전체 붙여넣기 → 스크립트 이름 `AppendToMaster` → **Save script(스크립트 저장)**
3. 같은 방법으로 `BuildExceptionReport`, `ValidateSubmission` 저장(ValidateSubmission은 아무 제출 파일에서 만들어도 됨)
4. 스크립트는 기본적으로 개인 OneDrive `문서/Office Scripts` 폴더에 `.osts`로 저장된다(✅ S14) → 이 3개 파일을 `SCM_Automation/Scripts` 로 **복사** → 흐름에서는 **Run script from SharePoint library** 액션으로 이 위치를 지정(개인 OneDrive 의존 제거)
5. 수동 확인: 마스터에서 **Automate → BuildExceptionReport → Run(실행)** → 매개변수 week에 `2026-W43` → `Exceptions` 시트 생성 확인(모의 데이터)

## 5. 흐름 P2-F1 (제출 검증·반영, 2시간)
1. **Automated cloud flow** → 트리거 **When a file is created or modified (properties only)**(SharePoint) → 라이브러리 `SCM_Submissions`
2. 트리거 **Settings(설정)**:
   - Trigger conditions: `@endsWith(toLower(triggerOutputs()?['body/{FilenameWithExtension}']), '.xlsx')`
   - **Concurrency control(동시성 제어) 켜기 → Degree of Parallelism 1** *(한 번 켜면 끄려면 트리거를 다시 만들어야 한다 ✅ S32)*
3. Scope `Try`:
   1. Compose `PathParts` = `split(triggerOutputs()?['body/{Path}'], '/')`
      Compose `Week` = `outputs('PathParts')[sub(length(outputs('PathParts')), 3)]`
      Compose `Plant` = `outputs('PathParts')[sub(length(outputs('PathParts')), 2)]`
      *`{Path}`는 `SCM_Submissions/2026-W46/PLT-A/` 형태 — 첫 실행에서 Compose로 확인하고 인덱스 조정*
   2. **Delay** 1분
   3. **Get items**(SubmissionLog) 필터 `Title eq '@{outputs('Week')}|@{outputs('Plant')}' and ETag eq '@{triggerOutputs()?['body/{ETag}']}' and Result eq '합격'` → 1건 이상이면 **Terminate(Succeeded)**
   4. **List rows present in a table**(Excel Online (Business), 마스터, 표 `tblSKU`) → **Select** 맵 `item()?['SKU']` → Compose `SkusCsv` = `join(body('Select_SKU'), ',')`
   5. **Run script from SharePoint library**: Workbook = 트리거 파일, Script = `SCM_Automation/Scripts/ValidateSubmission.osts`, expectedWeek=`outputs('Week')`, plantCode=`outputs('Plant')`, validSkusCsv=`outputs('SkusCsv')`
   6. Condition `@equals(body('Run_script_Validate')?['result']?['ok'], true)`
      - 아니요: SubmissionLog 생성(Result=반려, ErrorCount) → 제출자(`triggerOutputs()?['body/Editor/Email']`)에게 Teams 메시지: issues 상위 20개를 Select로 `concat(item()?['code'], ' ', string(item()?['row']), '행 ', item()?['column'], ': ', item()?['message'])` → `join(..., '<br>')` + 파일 링크 → Terminate
      - 예: **Run script from SharePoint library**(마스터, `AppendToMaster.osts`): submissionKey=`body('Run_script_Validate')?['result']?['submissionKey']`, rowsJson=`body('Run_script_Validate')?['result']?['rowsJson']`, loadedBy=제출자 이메일 → 결과 ok=false면 FlowErrorLog(Critical) → SubmissionLog(Result=합격, LoadedAt, ETag) → 제출자에게 합격 메시지(경고 있으면 목록)
   7. 이번 주 SubmissionCalendar 조회 → ExpectedPlants 전부 합격이면 Status=완료로 업데이트
4. Scope `Catch` — Pilot 01과 같은 패턴
   *결과 경로 `body('…')?['result']`는 Run script 액션 출력 구조 — 첫 실행 출력에서 확인(확인 필요)*

## 6. 흐름 P2-F2, P2-F3
- P2-F2: Scheduled(월·화 09:00, Seoul) → SubmissionCalendar 이번 주 행 → `split(ExpectedPlants, ';')`와 SubmissionLog 합격 공장의 차집합(Filter array: `@not(contains(variables('varPassed'), item()))`) → 해당 공장 담당자만 알림
- P2-F3: SubmissionCalendar 트리거 + 조건(`flows_spec.json`) → Run script(BuildExceptionReport, week) → Teams 채널(또는 그룹 채팅) 카드: `counts`·`top` 상위 5 + 마스터 Exceptions 링크 → ReportPostedAt=`utcNow()`

## 7. 공장 안내문 (그대로 사용 가능)
> 이번 주부터 주간 생산·재고 데이터는 메일 대신 **SCM_Submissions/<주차>/<공장코드>** 폴더에 표준 템플릿으로 저장해 주세요. 저장 후 약 2~5분 안에 Teams로 검증 결과가 옵니다. 오류가 있으면 표시된 행만 고쳐 같은 이름으로 다시 저장하면 됩니다(이전 제출은 자동 교체). 마감: 매주 화 12:00.

## 8. 오류 시 확인 항목

| 증상 | 원인 후보 | 조치 |
|---|---|---|
| 'BadGateway' / 스크립트 실패 | ISO Strict 형식 xlsx, 파일 열림 잠금 | 표준 .xlsx로 다시 저장, Delay 늘리기 |
| 같은 제출이 여러 번 처리 | 자동 저장으로 수정 이벤트 연속 | Delay 60초 + ETag 중복 확인 단계 확인 |
| E05 전부 발생 | tblSKU 비었거나 Select 경로 오류 | SkusCsv Compose 출력 확인(fail-closed 동작) |
| 120초 시간 초과 | tblFact 과대 | 연도별 보관 파일 분리, 이전 기준 검토 |
| 공장 폴더 접근 불가 | 권한·외부 공유 | 사이트 소유자·IT 확인 |
| 'Run script' 일 한도 | 1,600회/일 초과(사실상 불가능) | 반복 실행 루프 점검 |

## 9. 운영·유지관리
| 주기 | 작업 |
|---|---|
| 매주 | 예외 리포트 검토(사람), 반려율·재제출 횟수 확인 |
| 매월 | SubmissionLog로 KPI(제출 정시율·반려율·오류 발견 시간) 산출 |
| 분기 | 계약 개정 요청 검토 → 개정 시 `data_contract.json`·3개 스크립트·템플릿을 **함께** 수정 후 `tools/check_consistency.py`·테스트 실행 → 버전 증가 |
| 연 1회 | tblFact 연도 보관(복사본) 후 정리 — **삭제 전 사용자 승인** |
