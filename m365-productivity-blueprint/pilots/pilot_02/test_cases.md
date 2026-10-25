# Pilot 02 — 테스트 케이스

> L = 로컬 자동(실행됨, 모의 데이터) · M = M365 수동(배포 후, **미실행**)
> 실행: `cd automation_assets && node --test tests/office_scripts.test.js && python3 -m unittest -v python/test_psi_validator.py`

## 1. 로컬 — Office Scripts (TypeScript strict 컴파일 + 모의 ExcelScript Workbook, 15/15 통과)

| ID | 대상 | 시나리오 | 기대 결과 | 상태 |
|---|---|---|---|---|
| TC-L01 | 전체 | 계약 열 정의가 data_contract.json·두 스크립트에서 동일 | 일치 | ✅ |
| TC-L02 | Validate | 정상 2행 + 빈 행 | ok, rowCount 2, rowsJson 2행 | ✅ |
| TC-L03 | Validate | E02~E08 오류 9행 주입 | 7종 코드 모두 검출, rowsJson '[]' | ✅ |
| TC-L04 | Validate | PSI 허용오차 경계(유입 1만, 차이 9 / 11) | 통과 / 반려 | ✅ |
| TC-L05 | Validate | 조정 사유 없음, 가동>가용 | W01·W02 경고, ok 유지 | ✅ |
| TC-L06 | Validate | 필수 열 누락 / 표 없음 / SKU 마스터 빈 값 / 데이터 없음 | 모두 파일 단위 반려(fail-closed) | ✅ |
| TC-L07 | Validate | 실행 전후 제출 파일 비교 | 변경 없음, 쓰기 호출 0 | ✅ |
| TC-L08 | Append | contiguousRuns | 블록 분할 정확 | ✅ |
| TC-L09 | Append | 같은 제출 2회 반영 | 결과 동일(멱등), 다른 주차 보존 | ✅ |
| TC-L10 | Append | 흩어진 기존 행 3개 재제출 | 3행 삭제 후 교체, 다른 공장 보존 | ✅ |
| TC-L11 | Append | 잘못된 JSON·열 수·키 불일치·머리글 불일치 | 거부, 마스터 무변경 | ✅ |
| TC-L12 | Report | ISO 주차(2026=53주, 연 경계) | 정확 | ✅ |
| TC-L13 | Report | X01~X05 주입 | 5종 검출, High 우선 정렬, 시트 기록, 재실행 누적 없음 | ✅ |
| TC-L14 | Report | 정상 주차 | 예외 0(침묵) | ✅ |
| TC-L15 | 교차 | 샘플 CSV 2개: Office Scripts 결과 == Python 검증기 결과 | 코드·행 번호 완전 일치(10건) | ✅ |

## 2. 로컬 — Python 검증기 (5/5 통과)
정상 파일 통과 · 오류 파일 기대 결과 일치 · SKU 마스터 없으면 반려 · 필수 열 누락 E01 · CLI 종료코드(0/1). 그 밖에 Python in Excel 셀 코드를 가짜 `xl()` 함수로 실행해 오류 파일에서 E06·E07·E08·W01·W02 검출 확인(핵심 규칙 일부만 구현한 간이판).

## 3. M365 수동 (배포 후 — 미실행)

| ID | 시나리오 | 기대 결과 |
|---|---|---|
| TC-M01 | 웹 Excel에서 스크립트 3개 저장·수동 실행(모의 마스터, week=2026-W43) | Exceptions 시트 생성, 120초 이내 |
| TC-M02 | 정상 제출(`PLT-A_2026-W44_ok.csv` 내용을 템플릿에 붙여 저장) | 5분 이내 합격 메시지, tblFact +8행, SubmissionLog 합격 |
| TC-M03 | 오류 제출(`PLT-B_…_errors.csv`) | 반려 카드에 10개 이슈(E02·E03·E05·E06·E07·E08×3·W01·W02), tblFact 변화 없음 |
| TC-M04 | 오류 수정 후 같은 파일명 재저장 | 합격, 같은 SubmissionKey 행 교체 |
| TC-M05 | 자동 저장으로 수정 이벤트 연속 3회 | 처리 1회(ETag 중복 방지) |
| TC-M06 | 두 공장 동시 제출 | 순차 처리(동시성 1), 두 공장 모두 반영 |
| TC-M07 | 폴더 경로 파싱 | Week·Plant Compose 값 정확 |
| TC-M08 | SKU 마스터 비움 | 전체 반려(fail-closed) |
| TC-M09 | 미제출 리마인더 | 미제출 공장에만 알림 |
| TC-M10 | 전 공장 합격 → 예외 리포트 | 채널 카드 1장, 재수정 시 재게시 없음 |
| TC-M11 | 마스터 머리글 임의 변경 | AppendToMaster 거부 + FlowErrorLog Critical |
| TC-M12 | 실행 시간 측정 | tblFact 2.5만 행 모의 데이터에서 각 스크립트 60초 이내 |

## 4. 합격 기준
L 전부 통과(완료). M01~M10 필수. M12에서 60초 초과 시 05 문서의 이전 기준 적용 검토.
