# Pilot 03 — 구현 가이드 (실무자용)

> 소요: 약 2일. 순서: ① ActionItems + 메일 플래그(30분 만에 개인 효과) → ② 아침 브리핑 → ③ DecisionLog + Teams 메시지 기록 → ④ 리마인더·주간 다이제스트 → ⑤ 회의·보고 제거 규칙 시행 → ⑥ (C) AI.
> 메뉴 표기는 `영문(한국어 예상)`.

---

## 1. 목록 만들기 (40분)
Pilot 01과 같은 사이트에 `automation_assets/lists_schema.json`의 `DecisionLog`, `ActionItems`를 만든다(방법은 Pilot 01 가이드 2장). 인덱스: Status, Owner, DueDate, DecisionID, SourceMessageId(ActionItems) / Status, Decider, DecisionID, RelatedRequestID(DecisionLog). 보기 4개씩(스키마 views). '내 액션'·'결정 대기열' 보기 URL을 복사해 둔다.

## 2. P3-F3 메일 플래그 → 액션 (30분) — 가장 먼저
1. **Automated cloud flow** → 트리거 **When an email is flagged (V4)**(Office 365 Outlook), Folder = Inbox
2. **Get items**(ActionItems) 필터 `SourceMessageId eq '@{triggerOutputs()?['body/id']}'` → 결과가 있으면 Terminate
3. **Create item**(ActionItems): Title=`concat('[메일] ', triggerOutputs()?['body/subject'])`, Owner=나, DueDate=플래그 기한(없으면 비움), ActionType=실행, Source=이메일, SourceLink=`triggerOutputs()?['body/webLink']`, Evidence=`triggerOutputs()?['body/bodyPreview']`, CreatedVia=Outlook 플래그, SourceMessageId=`triggerOutputs()?['body/id']`, Status=미착수, PrevStatus=미착수
4. 같은 흐름을 **Save as(다른 이름으로 저장)** → Folder = Sent Items, ActionType=회신대기, Title 접두어 `[회신대기]`
   *트리거 출력의 필드 이름(id, webLink, bodyPreview, flag 기한)은 첫 실행 출력에서 확인(확인 필요)*
5. 테스트: 받은 메일 1건 플래그 → 목록에 생성 / 같은 메일 플래그 해제 후 재지정 → 중복 생성 안 됨

## 3. P3-F4 아침 브리핑 (2시간)
1. **Scheduled cloud flow** → 매주 월~금 07:40, Time zone `(UTC+09:00) Seoul`
2. Holidays 조회 → 오늘이면 Terminate
3. **Get calendar view of events (V3)**(Office 365 Outlook): 시작 시간 = `convertToUtc(concat(convertFromUtc(utcNow(), 'Korea Standard Time', 'yyyy-MM-dd'), 'T00:00:00'), 'Korea Standard Time')`, 종료 시간 = `addDays(<위 식>, 1)` (오늘 KST 0시~24시를 UTC로 입력). 결과의 start/end는 `convertFromUtc(..., 'Korea Standard Time')`로 변환해 사용
4. **Get items** 3개(`flows_spec.json` P3-F4 필터 그대로). Person 열 필터는 `Owner/EMail eq '...'` 형식
5. 점수 계산: 각 결과를 **Select**로 `{kind, id, text, score}` 객체로 변환 — 예(기한 초과 액션):
   - score: `add(100, mul(5, div(sub(ticks(variables('varTodayUtc')), ticks(item()?['DueDate'])), 864000000000)))`
6. **Compose** `AllItems` = `union(body('Select_Overdue'), body('Select_Decisions'), body('Select_SLA'), ...)` → 정렬 `sort(outputs('AllItems'), 'score')` 후 `reverse()` → `take(..., 5)` *(sort·reverse·take 식 함수 지원 여부는 디자이너에서 확인 — 미지원 시 Filter array 단계별 구성으로 대체)*
7. 카드: `cards/daily_brief_example.json` 구조(로컬에서 `python3 python/daily_brief.py sample_data/brief_input.json`으로 생성한 예시)를 템플릿으로 사용 → **Post card in a chat or channel**(Flow bot → 나)
8. 로컬 규칙과 결과 비교: 같은 날 모의 입력을 `daily_brief.py`에 넣어 Top 5 순서가 같은지 확인(TC-M06)

## 4. P3-F1 Teams 메시지 → 결정·액션 (1시간)
1. **Instant cloud flow** → **For a selected message**(Microsoft Teams) → 카드 = `cards/capture_decision_action.json`
2. ownerEmail 비면 `triggerOutputs()?['body/...']`의 실행자 이메일(확인 필요) → **Get user profile (V2)**로 실존 확인
3. SourceMessageId 중복 확인 → kind 별 Create item(`flows_spec.json`)
4. 실행자에게 응답 메시지(번호는 P3-F2가 붙인 뒤 링크로)
5. P3-F2(번호·완료일)·P3-F2b(DecisionLog 번호·DecidedAt): Pilot 01 P1-F2와 같은 Prev열 패턴

## 5. P3-F6 리마인더, P3-F5 주간 다이제스트 (1.5시간)
`flows_spec.json`의 단계대로. 공통 규칙: 담당자별 1장, `LastRemindedAt` 날짜가 오늘이면 제외, 리마인더 후 `ReminderCount` +1.

## 6. 회의·보고 제거 규칙 시행 (사람의 일, 30분 회의)
팀장에게 아래 4주 실험안 승인 요청(→ DecisionLog에 첫 결정으로 기록):
1. 주간보고 작성 중단. 금요일 16:00 자동 다이제스트로 대체
2. 월요일 현황회의 60분 → 15분 '막힌 건' 회의. 다이제스트 스레드에 답글이 달린 항목만 논의
3. 모든 회의는 종료 2분 전 결정·액션을 메시지 액션으로 기록(주관자 책임)
4. 4주 후 KPI(`09` P3)로 유지·복귀 결정

## 7. (Scenario C) AI 추출·결정 조회 에이전트
**전제:** Copilot 라이선스 + 회의 전사 허용 + 정보보안 승인. 셋 중 하나라도 없으면 진행하지 않는다.
1. 추출: Copilot Chat에 `agent/meeting_extractor_instructions.md`의 지침과 회의록을 붙여 JSON 생성 → 로컬 또는 흐름에서 `extraction_guard.py`로 검사 → 확인 카드로 선택 등록. (흐름 자동화는 Copilot Studio 에이전트 흐름 + 동일 규칙, 크레딧 소비량 사전 추정)
2. 결정 조회 에이전트: Microsoft 365 Copilot 앱 → **Agents(에이전트) → Create agent(에이전트 만들기)** → **Configure(구성)** 탭 → 이름·설명 → Instructions에 `agent/instructions.txt` 붙여넣기 → Knowledge(지식)에 DecisionLog 목록(목록 1개 지원)과 `회의록/결정근거` 폴더 → **웹 검색 끄기** → 시작 문구 4개 → 테스트 패널에서 `eval_cases.json` 12문항 실행 → 합격선 확인 후 SCM 팀에만 공유
3. Agents Toolkit 방식: `agent/declarativeAgent.json`(+ instructions.txt)을 VS Code Agents Toolkit 프로젝트의 appPackage에 넣는다. 스키마 버전은 툴킷이 생성한 최신 버전으로 맞추고, 지식 범위(items_by_url)를 반드시 지정한다. 앱 업로드는 관리자 정책 확인 후.

## 8. 오류 시 확인 항목
| 증상 | 조치 |
|---|---|
| 메시지 메뉴에 흐름이 안 보임 | 기본 환경에서 만들었는지, Teams 'Power Automate/Workflows' 앱 허용 |
| 같은 메일로 액션 2건 | SourceMessageId 조건 확인(인덱스 열) |
| 브리핑 시간이 9시간 어긋남 | 일정 시간 UTC → KST 변환 누락 |
| 카드 게시 실패(크기) | 항목 수 제한(각 섹션 5개), 긴 제목 자르기 `substring` |
| 에이전트가 근거 없이 답함 | 웹 검색·일반 지식 설정 확인, 지침 4번, 지식 범위 축소 |

## 9. 운영
| 주기 | 작업 |
|---|---|
| 매주 | 다이제스트에서 '기한 초과 상위 담당자'를 비난이 아니라 **부하 조정** 신호로 사용 |
| 매월 | KPI: 결정 대기시간 중앙값, 액션 기한초과율, 결정→액션 연결률, 회의 시간 |
| 분기 | 점수 규칙 조정(흐름·`daily_brief.py` 동시 수정 + 테스트) |
