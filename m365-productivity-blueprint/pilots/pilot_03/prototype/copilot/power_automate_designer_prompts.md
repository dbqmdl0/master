# Power Automate '설계를 위해 설명'(AI 흐름 생성)용 지시문

> 위치: make.powerautomate.com › **+ 만들기** › **설계를 위해 설명**(원하는 흐름을 설명하면 AI가 자동으로 생성) — 2026-10-26 회사 화면에서 메뉴 존재 확인(사용자 보고)
> AI가 만든 흐름은 **뼈대**다. 생성 후 아래 '고칠 곳'을 `BUILD_TABLES.md` 표 기준으로 맞춘다. 로컬 테스트를 통과한 것은 BUILD_TABLES의 정의이지, AI가 만든 흐름이 아니다.
> 전제: 목록 `ActionItems`, `FlowErrorLog`를 먼저 만든다(AI가 사이트·목록을 고르라고 묻는다).

## P3A-2 (A안) 간단 아침 메일

### 지시문 (한국어로 먼저, 결과가 엉뚱하면 영어판)
```text
평일(월~금) 매일 오전 7시 40분, 표준 시간대 (UTC+09:00) 서울로 실행되는 예약 흐름을 만들어 줘.
1) SharePoint의 내 목록 ActionItems에서 Get items로 항목을 가져와. 필터 쿼리: 담당자(Owner)가 나이고 상태(Status)가 '미착수' 또는 '진행중'. 정렬: DueDate 오름차순. 최대 500개.
2) 배열 필터링(Filter array) 3개로 나눠: (가) 기한(DueDate)이 오늘보다 이전 (나) 기한이 오늘부터 2일 뒤까지 (다) 기한이 비어 있음.
3) 각 묶음을 선택(Select)으로 '할 일'(Title), '기한'(DueDate), '상태'(Status), '우선순위'(Priority), '링크'(SourceLink) 열만 남기고, HTML 표 만들기(Create HTML table)로 표 3개를 만들어.
4) Office 365 Outlook의 메일 보내기(V2)로 나에게만 보내. 제목은 '[오늘 할 일] 오늘 날짜 · 초과 (가)의 개수 · 임박 (나)의 개수 · 기한없음 (다)의 개수', 본문은 '기한 지남', '오늘~2일 뒤 마감', '기한 없는 할 일' 제목 아래에 표 3개.
```
```text
Create a scheduled cloud flow that runs Monday to Friday at 7:40 AM, time zone (UTC+09:00) Seoul.
1) SharePoint Get items from my list ActionItems. Filter query: Owner is me and Status is '미착수' or '진행중'. Order by DueDate ascending. Top count 500.
2) Use three Filter array actions: (a) DueDate before today, (b) DueDate from today to 2 days later, (c) DueDate is empty.
3) For each, use Select to keep 할 일=Title, 기한=DueDate, 상태=Status value, 우선순위=Priority value, 링크=SourceLink, then Create HTML table.
4) Send an email (V2) only to me. Subject: '[오늘 할 일] today · 초과 count(a) · 임박 count(b) · 기한없음 count(c)'. Body: the three tables under the headings '기한 지남', '오늘~2일 뒤 마감', '기한 없는 할 일'.
```

### 생성 후 고칠 곳 (BUILD_TABLES P3A-2 기준)
| # | 확인할 것 | 맞는 값 |
|---|---|---|
| 1 | 트리거 | 주 · 월~금 · 7시 40분 · (UTC+09:00) Seoul |
| 2 | 맨 위에 작성(Compose) `Today` 추가 | `convertFromUtc(utcNow(), 'Korea Standard Time', 'yyyy-MM-dd')` (fx) — AI는 흔히 utcNow()만 써서 아침 9시 전에는 **어제 날짜**가 된다 |
| 3 | 작성 `Soon`, `Ago7`, `Ago14` | `addDays(outputs('Today'), 2, 'yyyy-MM-dd')`, `-7`, `-14` |
| 4 | Get items 필터 쿼리 | `Owner/EMail eq '본인메일' and (Status eq '미착수' or Status eq '진행중')` · 정렬 `DueDate asc` · 상위 500 |
| 5 | 기한 지남 필터(고급 모드) | `@and(not(empty(item()?['DueDate'])), less(convertFromUtc(item()?['DueDate'], 'Korea Standard Time', 'yyyy-MM-dd'), outputs('Today')))` |
| 6 | 임박 필터 | `@and(not(empty(item()?['DueDate'])), greaterOrEquals(convertFromUtc(item()?['DueDate'], 'Korea Standard Time', 'yyyy-MM-dd'), outputs('Today')), lessOrEquals(convertFromUtc(item()?['DueDate'], 'Korea Standard Time', 'yyyy-MM-dd'), outputs('Soon')))` |
| 7 | 기한 없음 필터 | `@empty(item()?['DueDate'])` |
| 8 | (추가) 방치 경고 필터 `Neglected` — '기한 없음' 결과에서 | `@or(lessOrEquals(convertFromUtc(item()?['Created'], 'Korea Standard Time', 'yyyy-MM-dd'), outputs('Ago14')), and(equals(item()?['Priority']?['Value'], '높음'), lessOrEquals(convertFromUtc(item()?['Created'], 'Korea Standard Time', 'yyyy-MM-dd'), outputs('Ago7'))))` |
| 9 | 선택(Select)의 상태·우선순위 | 상태 `item()?['Status']?['Value']`, 우선순위 `coalesce(item()?['Priority']?['Value'], '보통')` (선택 열은 `?['Value']`) |
| 10 | 메일 받는 사람 | **본인 주소만** |
| 11 | 액션 이름 | BUILD_TABLES와 같게(`Get_open`, `Overdue`, `Due_soon`, `Undated`, `Neglected`, `Send_brief` …) — 표의 식이 이름으로 서로를 찾는다 |
| 12 | 오류 처리(나중에 해도 됨) | 전체를 범위 `Try`로 감싸고 `Catch` 범위(실행 후 구성: 실패함·시간 초과됨) — BUILD_TABLES 표 |

**성공 기준:** 테스트 › 수동 → 본인 메일 1통, 목록의 `[가상]` 항목이 기한 기준으로 표에 나뉘어 있음.

## P3A-1 (메일 플래그 → 할 일)은 AI 생성을 권하지 않는다
중복 방지·기존 항목 갱신·사후 점검 등 조건이 많아(액션 53개) AI 뼈대를 고치는 시간이 더 든다. BUILD_TABLES 표대로 직접 만든다. 막히는 단계는 오류 문구로 질문.
