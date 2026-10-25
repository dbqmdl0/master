# Pilot 01 — 복사해서 쓰는 Power Automate 표현식

> 사용법: Flow 디자이너에서 입력란 클릭 → **fx(식)** 탭 → 아래 식을 붙여넣기 → **추가**.
> `triggerOutputs()?['body/열내부이름']` 은 트리거 항목의 값이다. 열 내부 이름은 `lists_schema.json`과 같아야 한다.
> 선택(Choice) 열은 `/Value`, 사용자(Person) 열은 `/Email` 을 붙인다.
> 모든 식은 이 저장소의 `request_hub_rules.py`와 같은 규칙이다(테스트 19건 통과). Flow 첫 실행에서는 반드시 **Compose(작성)** 액션으로 중간값을 찍어 원시값 형식을 확인하라.

## 1. 트리거 조건 (P1-F2, 무한 루프·불필요 실행 차단)

트리거 카드 **… → 설정(Settings) → 트리거 조건(Trigger conditions) → + 추가**에 두 줄을 각각 넣는다(모두 참일 때만 실행).

```text
@not(empty(triggerOutputs()?['body/PrevStatus']))
```
```text
@or(not(equals(triggerOutputs()?['body/Status/Value'], triggerOutputs()?['body/PrevStatus'])), not(equals(coalesce(triggerOutputs()?['body/DueDateCommitted'], ''), coalesce(triggerOutputs()?['body/PrevDueDateCommitted'], ''))))
```

- 첫 줄: F1이 처리를 끝내기 전(생성 직후)에는 F2가 돌지 않는다.
- 둘째 줄: 상태나 약속일이 실제로 바뀐 경우에만 돈다. F2는 마지막 단계에서 `PrevStatus`/`PrevDueDateCommitted`를 현재값으로 맞추므로, 자기 자신의 수정으로는 다시 실행되지 않는다.

## 2. 요청번호 (P1-F1)

```text
concat('REQ-', convertFromUtc(triggerOutputs()?['body/Created'], 'Korea Standard Time', 'yyyy'), '-', formatNumber(triggerOutputs()?['body/ID'], '00000'))
```
SharePoint 항목 ID 기반이므로 동시 접수가 있어도 번호가 겹치지 않는다(별도 채번 테이블 불필요).

## 3. 중복검사키 (P1-F1)

```text
toLower(concat(triggerOutputs()?['body/RequestType/Value'], '|', trim(coalesce(triggerOutputs()?['body/ProductCode'], '')), '|', coalesce(triggerOutputs()?['body/Plant/Value'], ''), '|', triggerOutputs()?['body/Requester/Email'], '|', convertFromUtc(triggerOutputs()?['body/DueDateRequested'], 'Korea Standard Time', 'yyyy-MM-dd')))
```
중복 후보 조회(Get items → 필터 쿼리). `outputs('DuplicateKey')`는 위 식을 담은 Compose 이름이다. 제품코드에 작은따옴표가 들어갈 수 있으면 `replace(outputs('DuplicateKey'), '''', '''''')`로 한 번 감싼다.
```text
DuplicateKey eq '@{outputs('DuplicateKey')}' and ID ne @{triggerOutputs()?['body/ID']} and Status ne '완료' and Status ne '반려' and Status ne '취소' and Created ge '@{addDays(utcNow(), -14)}'
```

## 4. 휴무일 배열 (P1-F1, P1-F3)

1. **Get items** (목록: Holidays, 필터: `HolidayDate ge '@{addDays(utcNow(), -7)}'`, 상위 개수 500)
2. **Select(선택)** → 보낸 사람: `body('Get_items_Holidays')?['value']`, 맵 오른쪽 상단 **텍스트 모드 전환** 후:
```text
convertFromUtc(item()?['HolidayDate'], 'Korea Standard Time', 'yyyy-MM-dd')
```
3. **Initialize variable** `varHolidays` (Array) = `body('Select_Holidays')`

> ⚠ 날짜만(Date only) 열이 `2026-10-09` 형태로 오는지 `2026-10-08T15:00:00Z` 형태로 오는지는 사이트 지역 설정에 따라 다르다. 위 식은 두 경우 모두 KST 날짜를 돌려준다. 첫 실행에서 Select 결과가 회사 달력과 일치하는지 반드시 눈으로 확인하라.

## 5. 접수 기준일 (17시 컷오프)

- `varCreatedKst` (String) = `convertFromUtc(triggerOutputs()?['body/Created'], 'Korea Standard Time', 'yyyy-MM-ddTHH:mm:ss')`
- `varD` (String) = `formatDateTime(variables('varCreatedKst'), 'yyyy-MM-dd')`
- 조건 **"당일 접수 인정"** (고급 모드 식이 참이면 그대로):
```text
@and(less(int(formatDateTime(variables('varCreatedKst'), 'HH')), 17), not(equals(dayOfWeek(variables('varD')), 0)), not(equals(dayOfWeek(variables('varD')), 6)), not(contains(variables('varHolidays'), variables('varD'))))
```
- 거짓이면 **Do until** "영업일 찾기": 본문에서 `varD = formatDateTime(addDays(variables('varD'), 1), 'yyyy-MM-dd')`, 종료 조건:
```text
@and(not(equals(dayOfWeek(variables('varD')), 0)), not(equals(dayOfWeek(variables('varD')), 6)), not(contains(variables('varHolidays'), variables('varD'))))
```

## 6. SLA 목표일 = 접수 기준일 + N영업일

- `varSlaDays` (Integer) = `int(first(body('Get_items_SLAPolicy')?['value'])?['SLABusinessDays'])`
- `varAdded` (Integer) = 0
- **조건** `varSlaDays > 0` 일 때만 **Do until** 실행 (Do until은 본문을 최소 1회 실행하므로 0일 정책 보호)
  - 본문 1: `varD` 설정 = `formatDateTime(addDays(variables('varD'), 1), 'yyyy-MM-dd')`
  - 본문 2: 조건(영업일이면) → `varAdded` 1 증가
```text
@and(not(equals(dayOfWeek(variables('varD')), 0)), not(equals(dayOfWeek(variables('varD')), 6)), not(contains(variables('varHolidays'), variables('varD'))))
```
  - 종료 조건: `@greaterOrEquals(variables('varAdded'), variables('varSlaDays'))`
  - 제한(Change limits): Count 100, Timeout PT10M
- 결과 `varD` 를 `SLATargetDate`에 기록.

## 7. 에스컬레이션 기준일 (P1-F3, `escalation_cutoff`와 동치)

- `varCut` = 오늘 KST(`convertFromUtc(utcNow(), 'Korea Standard Time', 'yyyy-MM-dd')`), `varCnt` = 0
- **Do until** `@equals(variables('varCnt'), 2)`:
  - 조건(영업일이면) → `varCnt` 1 증가
  - 조건 `@less(variables('varCnt'), 2)` 이면 `varCut = formatDateTime(addDays(variables('varCut'), -1), 'yyyy-MM-dd')`
- 루프 후 `varEscalationCutoff = formatDateTime(addDays(variables('varCut'), -1), 'yyyy-MM-dd')`
- 판정: `@lessOrEquals(item()?['SLATargetDate'], variables('varEscalationCutoff'))` (날짜 문자열 비교 전 `formatDateTime(...,'yyyy-MM-dd')`로 맞출 것)

## 8. 상태 전이 검사 (P1-F2)

- `varTransitions` (Object) — 초기화 값에 그대로 붙여넣기:
```json
{"접수":["정보보완","검토중","반려","취소"],"정보보완":["접수","검토중","취소"],"검토중":["정보보완","승인대기","진행중","보류","반려"],"승인대기":["진행중","반려","보류"],"진행중":["완료","보류","정보보완"],"보류":["검토중","진행중","취소"],"완료":["진행중"],"반려":[],"취소":[]}
```
- 허용 여부:
```text
@contains(variables('varTransitions')?[triggerOutputs()?['body/PrevStatus']], triggerOutputs()?['body/Status/Value'])
```

## 9. 담당자별 다이제스트 (P1-F3)

- 담당자 목록(중복 제거): Select(맵=`item()?['Owner']?['Email']`) 후
```text
union(body('Select_Owners'), body('Select_Owners'))
```
- 담당자별 기한초과 FactSet 배열: Filter array(`@and(equals(item()?['Owner']?['Email'], items('Apply_to_each_owner')), less(formatDateTime(item()?['SLATargetDate'], 'yyyy-MM-dd'), variables('varToday')))`) → Select(텍스트 모드 아님, 키/값):
  - `title` : `item()?['RequestID']`
  - `value` : `concat(item()?['Title'], ' · 목표 ', formatDateTime(item()?['SLATargetDate'], 'MM-dd'), ' · ', item()?['Status']?['Value'])`
- 카드 JSON의 `"{{OVERDUE_FACTS_ARRAY}}"`(따옴표 포함)를 `@{body('Select_Overdue_Facts')}` 대신 **식** `body('Select_Overdue_Facts')`로 교체한다.

## 10. 오류 처리 공통 (Try / Catch)

- Scope `Try` 안에 본문 전체를 넣고, Scope `Catch`의 **실행 후 구성(Configure run after)** 을 Try의 **실패함 / 시간 초과됨**으로 설정.
- 실패 액션 찾기: Filter array `result('Try')` 조건 `@equals(item()?['status'], 'Failed')`
- 실행 ID: `workflow()?['run']?['name']`
- 실행 기록 링크:
```text
concat('https://make.powerautomate.com/environments/', workflow()?['tags']?['environmentName'], '/flows/', workflow()?['name'], '/runs/', workflow()?['run']?['name'])
```
- 오류 메시지: `first(body('Filter_Failed'))?['error']?['message']`
- 마지막에 **Terminate** 상태=실패 (실행 기록에 실패가 남아야 모니터링 가능)

## 11. 재시도 정책 (모든 SharePoint·Teams 액션)

액션 **… → 설정 → 재시도 정책(Retry policy)**: 유형 **지수(Exponential)**, 횟수 4, 간격 `PT10S`, 최소 `PT5S`, 최대 `PT5M`. 429(조절) 오류가 반복되면 Apply to each 안에 **지연(Delay) 2초**를 넣는다.
