# DEPENDENCY_MATRIX — 흐름별 선행 조건 (자동 생성)

> `tools/dependency_matrix.py`가 `flows/*.flow.json`과 구축 순서(STAGES)에서 생성·검사한다. 직접 수정하지 말 것.
> 규칙: **선행 조건이 하나라도 없으면 그 흐름을 만들지 않는다.** 이 표의 단계 배정은 생성 시 자동 검사된다(위반 시 오류).
> 라이선스: 모든 흐름이 Microsoft 365에 포함된 Power Automate **표준 커넥터**만 쓴다(Premium 불필요 — 커넥터 문서의 표준 표시로 확인, 테넌트 정책은 미확인).
> Copilot은 흐름이 아니라 사람이 회의록을 추출할 때만 쓴다(P3P-F8 입력). 회사 Copilot 정책 확인 전에는 실제 회의록을 넣지 않는다.

## 1. 요약

| 흐름 | 단계 | 목록(트리거·읽기·쓰기) | 커넥터(연결) | Office Scripts | 선행 흐름 | 첫 테스트 |
|---|---|---|---|---|---|---|
| **P3A-1** | 1주차 · A안 최소 구성 | `ActionItems`(쓰기·읽기)<br>`FlowErrorLog`(쓰기) | Office 365 Outlook, SharePoint, Microsoft Teams(알림, 선택) | 없음 | 없음 | 가상 메일 1통 플래그 → 할 일 1건 / 다시 플래그 → 늘지 않음 |
| **P3A-2** | 1주차 · A안 최소 구성 | `ActionItems`(읽기)<br>`FlowErrorLog`(쓰기) | Office 365 Outlook, SharePoint | 없음 | 없음 | '테스트' 실행 → 본인 메일 1통(초과·임박·기한 없음 표) |
| **P3P-F3** | 1주차 · A안 최소 구성 | `ActionItems`(쓰기·읽기·트리거)<br>`FlowErrorLog`(쓰기) | Office 365 Outlook, SharePoint | 없음 | 없음 | 할 일 1건 상태 변경 → 액션번호·완료일시 기록, 다른 열 그대로 |
| **P3P-F4** | 2주차 · 결정 기록·스크립트 브리핑(B안 전환) | `DecisionLog`(쓰기·읽기·트리거)<br>`FlowErrorLog`(쓰기) | Office 365 Outlook, SharePoint | 없음 | 없음 | 결정 1건 '확정'으로 변경 → 확정일·'확정 확인 필요' 표시 |
| **P3P-F1** | 2주차 · 결정 기록·스크립트 브리핑(B안 전환) | `ActionItems`(쓰기·읽기)<br>`DecisionLog`(쓰기·읽기)<br>`FlowErrorLog`(쓰기) | Office 365 Outlook, SharePoint, Microsoft Teams(알림, 선택) | 없음 | P3P-F3, P3P-F4 | 범주 '결정요청' 메일 플래그 → DecisionLog '결정요청' 1건, 할 일 0건 |
| **P3P-F2** | 2주차 · 결정 기록·스크립트 브리핑(B안 전환) | `ActionItems`(쓰기·읽기)<br>`FlowErrorLog`(쓰기) | Office 365 Outlook, SharePoint, Microsoft Teams(알림, 선택) | 없음 | P3P-F3 | 보낸 편지함 메일 플래그 → '회신대기' 할 일(기한 +3일) |
| **P3P-F13** | 2주차 · 결정 기록·스크립트 브리핑(B안 전환) | `ActionItems`(쓰기·읽기·트리거)<br>`Holidays`(읽기)<br>`FlowErrorLog`(쓰기) | Excel Online (Business), Office 365 Outlook, SharePoint | ParseDueHint | P3P-F3 | '내일까지' 문구 메일 플래그 → 기한·근거 채워짐 |
| **P3P-F6** | 2주차 · 결정 기록·스크립트 브리핑(B안 전환) | `Holidays`(읽기)<br>`ActionItems`(읽기)<br>`DecisionLog`(읽기)<br>`FlowErrorLog`(쓰기) | Excel Online (Business), Office 365 Outlook, SharePoint, Microsoft Teams(알림, 선택) | BuildDailyBrief | P3P-F3 | '테스트' 실행 → 브리핑 메일(또는 카드) 1통, 기한 없는 할 일 칸 확인 |
| **P3P-F7** | 2주차 · 결정 기록·스크립트 브리핑(B안 전환) | `Holidays`(읽기)<br>`ActionItems`(쓰기·읽기)<br>`FlowErrorLog`(쓰기) | Excel Online (Business), Office 365 Outlook, SharePoint, Microsoft Teams(알림, 선택) | BuildReminderDigest | P3P-F3 | 기한 지난 내 할 일 1건 → 리마인더 1통, 횟수 1 |
| **P3P-F8** | 3주차 · 회의 추출(Copilot) 검증 | `MeetingIntake`(쓰기·읽기·트리거)<br>`TeamRoster`(읽기)<br>`ActionCandidates`(쓰기·읽기)<br>`FlowErrorLog`(쓰기) | Excel Online (Business), Office 365 Outlook, SharePoint, Microsoft Teams(알림, 선택) | GuardExtraction | 없음 | 샘플 추출 결과 붙여넣기 → 후보 생성, 할 일 0건 |
| **P3P-F9** | 3주차 · 회의 추출(Copilot) 검증 | `ActionCandidates`(쓰기·읽기·트리거)<br>`ActionItems`(쓰기)<br>`DecisionLog`(쓰기)<br>`FlowErrorLog`(쓰기) | Office 365 Outlook, Office 365 Users, SharePoint | 없음 | P3P-F8, P3P-F3, P3P-F4 | 후보 1건 '승인' → 그 1건만 등록 |
| **P3P-F10** | 4주차 · 공장 자료·회의 준비·주간 정리 | `FactorySenders`(읽기)<br>`FactoryInbox`(쓰기·읽기)<br>`FlowErrorLog`(쓰기) | Office 365 Outlook, OneDrive for Business, SharePoint | 없음 | 없음 | 공장 발신자 등록 후 가상 첨부 메일 → OneDrive 저장 + 대장 1줄 |
| **P3P-F11** | 4주차 · 공장 자료·회의 준비·주간 정리 | `Holidays`(읽기)<br>`ActionItems`(읽기)<br>`DecisionLog`(읽기)<br>`FlowErrorLog`(쓰기) | Excel Online (Business), Office 365 Outlook, SharePoint, Microsoft Teams(알림, 선택) | BuildMeetingPrep | 없음 | 내일 가상 회의 1건 → 준비 메일 1통 |
| **P3P-F12** | 4주차 · 공장 자료·회의 준비·주간 정리 | `ActionItems`(읽기)<br>`DecisionLog`(읽기)<br>`FactoryInbox`(읽기)<br>`FlowErrorLog`(쓰기) | Excel Online (Business), Office 365 Outlook, SharePoint, Microsoft Teams(알림, 선택) | BuildWeeklyDigest | 없음 | '테스트' 실행 → 주간 정리 메일 1통 |
| **P3P-F5** | 보류 · 환경 조건 미충족 | `ActionItems`(쓰기·읽기)<br>`DecisionLog`(쓰기·읽기)<br>`FlowErrorLog`(쓰기) | Microsoft Teams, Office 365 Outlook, Office 365 Users, SharePoint | 없음 | P3P-F3, P3P-F4 | (보류) |

## 2. 단계별 준비 체크리스트(누적)

### 1주차 · A안 최소 구성

- [ ] 목록 만들기: `ActionItems`, `FlowErrorLog` (`LISTS_SETUP.md`)
- [ ] P3A-1 만들기 → 첫 테스트: 가상 메일 1통 플래그 → 할 일 1건 / 다시 플래그 → 늘지 않음 · 2주차에 끄고 P3P-F1로 교체(같은 고유키라 중복 없음). P3P-F1과 동시에 켜지 않는다.
- [ ] P3A-2 만들기 → 첫 테스트: '테스트' 실행 → 본인 메일 1통(초과·임박·기한 없음 표) · 2주차에 P3P-F6이 안정되면 끈다(둘 다 켜 두면 아침 메일 2통).
- [ ] P3P-F3 만들기 → 첫 테스트: 할 일 1건 상태 변경 → 액션번호·완료일시 기록, 다른 열 그대로

### 2주차 · 결정 기록·스크립트 브리핑(B안 전환)

- [ ] 목록 만들기: `DecisionLog`, `Holidays` (`LISTS_SETUP.md`)
- [ ] 파일: P3_AutomationHost.xlsx → 본인 OneDrive `문서/P3/`
- [ ] Office Scripts: BuildDailyBrief, BuildReminderDigest, ParseDueHint → Excel 웹 › 자동화 › 새 스크립트 › 붙여넣기 › 저장(본인 OneDrive `문서/Office Scripts`에 저장됨)
- [ ] P3P-F4 만들기 → 첫 테스트: 결정 1건 '확정'으로 변경 → 확정일·'확정 확인 필요' 표시 · 확정 시 빈 항목(결정권자·근거·후속조치) 표시.
- [ ] P3P-F1 만들기 → 첫 테스트: 범주 '결정요청' 메일 플래그 → DecisionLog '결정요청' 1건, 할 일 0건 · 범주 '결정요청'·'결정' 메일을 DecisionLog에 쓴다 → DecisionLog·F4(번호)가 먼저 있어야 한다.
- [ ] P3P-F2 만들기 → 첫 테스트: 보낸 편지함 메일 플래그 → '회신대기' 할 일(기한 +3일)
- [ ] P3P-F13 만들기 → 첫 테스트: '내일까지' 문구 메일 플래그 → 기한·근거 채워짐 · 트리거 조건에 '액션번호 있음'이 있어 F3가 번호를 붙인 뒤에만 실행된다(두 흐름이 같은 항목을 동시에 고치지 않게).
- [ ] P3P-F6 만들기 → 첫 테스트: '테스트' 실행 → 브리핑 메일(또는 카드) 1통, 기한 없는 할 일 칸 확인
- [ ] P3P-F7 만들기 → 첫 테스트: 기한 지난 내 할 일 1건 → 리마인더 1통, 횟수 1

### 3주차 · 회의 추출(Copilot) 검증

- [ ] 목록 만들기: `MeetingIntake`, `ActionCandidates`, `TeamRoster` (`LISTS_SETUP.md`)
- [ ] Office Scripts: GuardExtraction → Excel 웹 › 자동화 › 새 스크립트 › 붙여넣기 › 저장(본인 OneDrive `문서/Office Scripts`에 저장됨)
- [ ] P3P-F8 만들기 → 첫 테스트: 샘플 추출 결과 붙여넣기 → 후보 생성, 할 일 0건
- [ ] P3P-F9 만들기 → 첫 테스트: 후보 1건 '승인' → 그 1건만 등록

### 4주차 · 공장 자료·회의 준비·주간 정리

- [ ] 목록 만들기: `FactorySenders`, `FactoryInbox` (`LISTS_SETUP.md`)
- [ ] Office Scripts: BuildMeetingPrep, BuildWeeklyDigest → Excel 웹 › 자동화 › 새 스크립트 › 붙여넣기 › 저장(본인 OneDrive `문서/Office Scripts`에 저장됨)
- [ ] P3P-F10 만들기 → 첫 테스트: 공장 발신자 등록 후 가상 첨부 메일 → OneDrive 저장 + 대장 1줄
- [ ] P3P-F11 만들기 → 첫 테스트: 내일 가상 회의 1건 → 준비 메일 1통
- [ ] P3P-F12 만들기 → 첫 테스트: '테스트' 실행 → 주간 정리 메일 1통 · FactoryInbox 목록이 없으면 조회 단계가 실패한다 → 4주차(목록 생성 후)에 만든다. 비어 있는 것은 괜찮다.

### 보류 · 환경 조건 미충족

- ⛔ P3P-F5: Teams 메시지 '추가 작업' 트리거는 Teams의 Workflows(Power Automate) 앱이 필요하다. 현재 테넌트에서 앱이 없으므로 만들지 않는다 — 대체: P3P-F1 + Outlook 범주.

## 3. 흐름별 사용 열(내부 이름) — 목록에 이 열이 없으면 흐름을 저장·실행할 수 없다

- **P3A-1**: `ActionItems` ← ActionID, ActionType, CompletedAt, CreatedVia, DecisionID, DueDate, DueHint, DueHintChecked, Evidence, FlagDue, LastRemindedAt, Owner, PrevStatus, Priority, ReminderCount, Source, SourceKey, SourceLink, SourceMessageId, Status, SyncNote, Title; `FlowErrorLog` ← ErrorMessage, FailedAction, FlowRunId, Resolved, RunUrl, Severity, Title
- **P3A-2**: `ActionItems` ← Owner, Status; `FlowErrorLog` ← ErrorMessage, FailedAction, FlowRunId, Resolved, RunUrl, Severity, Title
- **P3P-F3**: `ActionItems` ← ActionID, ActionType, CompletedAt, CreatedVia, DecisionID, DueDate, DueHint, DueHintChecked, Evidence, FlagDue, LastRemindedAt, Owner, PrevStatus, Priority, ReminderCount, Source, SourceKey, SourceLink, SourceMessageId, Status, SyncNote, Title; `FlowErrorLog` ← ErrorMessage, FailedAction, FlowRunId, Resolved, RunUrl, Severity, Title
- **P3P-F4**: `DecisionLog` ← ConfirmationGap, CreatedVia, DecidedAt, Decider, DecisionID, DecisionText, FollowUps, Impact, MeetingDate, MeetingName, OptionsConsidered, PrevStatus, Rationale, RelatedRequestID, RequestedAt, RequestedBy, ReviewDate, SourceKey, SourceLink, SourceMessageId, Status, SupersededBy, SyncNote, Title; `FlowErrorLog` ← ErrorMessage, FailedAction, FlowRunId, Resolved, RunUrl, Severity, Title
- **P3P-F1**: `ActionItems` ← ActionID, ActionType, CompletedAt, CreatedVia, DecisionID, DueDate, DueHint, DueHintChecked, Evidence, FlagDue, LastRemindedAt, Owner, PrevStatus, Priority, ReminderCount, Source, SourceKey, SourceLink, SourceMessageId, Status, SyncNote, Title; `DecisionLog` ← ConfirmationGap, CreatedVia, DecidedAt, Decider, DecisionID, DecisionText, FollowUps, Impact, MeetingDate, MeetingName, OptionsConsidered, PrevStatus, Rationale, RelatedRequestID, RequestedAt, RequestedBy, ReviewDate, SourceKey, SourceLink, SourceMessageId, Status, SupersededBy, SyncNote, Title; `FlowErrorLog` ← ErrorMessage, FailedAction, FlowRunId, Resolved, RunUrl, Severity, Title
- **P3P-F2**: `ActionItems` ← ActionID, ActionType, CompletedAt, CreatedVia, DecisionID, DueDate, DueHint, DueHintChecked, Evidence, FlagDue, LastRemindedAt, Owner, PrevStatus, Priority, ReminderCount, Source, SourceKey, SourceLink, SourceMessageId, Status, SyncNote, Title; `FlowErrorLog` ← ErrorMessage, FailedAction, FlowRunId, Resolved, RunUrl, Severity, Title
- **P3P-F13**: `ActionItems` ← ActionID, ActionType, CompletedAt, CreatedVia, DecisionID, DueDate, DueHint, DueHintChecked, Evidence, FlagDue, LastRemindedAt, Owner, PrevStatus, Priority, ReminderCount, Source, SourceKey, SourceLink, SourceMessageId, Status, SyncNote, Title; `Holidays` ← (열 지정 없음); `FlowErrorLog` ← ErrorMessage, FailedAction, FlowRunId, Resolved, RunUrl, Severity, Title
- **P3P-F6**: `Holidays` ← (열 지정 없음); `ActionItems` ← Owner, Status; `DecisionLog` ← Decider, Status; `FlowErrorLog` ← ErrorMessage, FailedAction, FlowRunId, Resolved, RunUrl, Severity, Title
- **P3P-F7**: `Holidays` ← (열 지정 없음); `ActionItems` ← ActionID, ActionType, CompletedAt, CreatedVia, DecisionID, DueDate, DueHint, DueHintChecked, Evidence, FlagDue, LastRemindedAt, Owner, PrevStatus, Priority, ReminderCount, Source, SourceKey, SourceLink, SourceMessageId, Status, SyncNote, Title; `FlowErrorLog` ← ErrorMessage, FailedAction, FlowRunId, Resolved, RunUrl, Severity, Title
- **P3P-F8**: `MeetingIntake` ← ExtractionJson, MeetingDate, ProcessedAt, RecommendedCount, ResultSummary, ReviewCount, Status, Title, Transcript; `TeamRoster` ← (열 지정 없음); `ActionCandidates` ← CreatedItemID, DueDate, Evidence, IntakeID, Kind, MeetingDate, MeetingName, OwnerEmail, OwnerName, Reasons, Ref, Status, Title, Verdict; `FlowErrorLog` ← ErrorMessage, FailedAction, FlowRunId, Resolved, RunUrl, Severity, Title
- **P3P-F9**: `ActionCandidates` ← CreatedItemID, DueDate, Evidence, IntakeID, Kind, MeetingDate, MeetingName, OwnerEmail, OwnerName, Reasons, Ref, Status, Title, Verdict; `ActionItems` ← ActionType, CreatedVia, DueDate, Evidence, Owner, Priority, Source, Status, Title; `DecisionLog` ← CreatedVia, DecisionText, MeetingDate, MeetingName, Status, Title; `FlowErrorLog` ← ErrorMessage, FailedAction, FlowRunId, Resolved, RunUrl, Severity, Title
- **P3P-F10**: `FactorySenders` ← (열 지정 없음); `FactoryInbox` ← FileCount, FileNames, PlantCode, ReceivedAt, SavedFolder, Sender, SourceMessageId, Title; `FlowErrorLog` ← ErrorMessage, FailedAction, FlowRunId, Resolved, RunUrl, Severity, Title
- **P3P-F11**: `Holidays` ← (열 지정 없음); `ActionItems` ← Status; `DecisionLog` ← DecidedAt, Status; `FlowErrorLog` ← ErrorMessage, FailedAction, FlowRunId, Resolved, RunUrl, Severity, Title
- **P3P-F12**: `ActionItems` ← Owner, Status; `DecisionLog` ← Status; `FactoryInbox` ← ReceivedAt; `FlowErrorLog` ← ErrorMessage, FailedAction, FlowRunId, Resolved, RunUrl, Severity, Title
- **P3P-F5**: `ActionItems` ← ActionType, CreatedVia, DecisionID, DueDate, Evidence, Owner, Priority, Source, SourceLink, SourceMessageId, Status, Title; `DecisionLog` ← CreatedVia, Decider, DecisionText, RequestedBy, SourceLink, SourceMessageId, Status, Title; `FlowErrorLog` ← ErrorMessage, FailedAction, FlowRunId, Resolved, RunUrl, Severity, Title

## 4. 연결(Connection)과 권한

| 커넥터 | 필요한 권한·조건 |
|---|---|
| SharePoint | 해당 목록 편집 권한(본인 사이트) |
| Office 365 Outlook | 본인 사서함·일정(위임 권한) |
| Microsoft Teams | Workflows 앱 허용 필요(채널=teams일 때만). 메일 모드에서는 조건의 Teams 분기를 비워 두면 Teams 연결 불필요 |
| Excel Online (Business) | 본인 OneDrive의 호스트 통합 문서·'문서/Office Scripts' 스크립트 |
| OneDrive for Business | 본인 OneDrive 쓰기 |
| Office 365 Users | 사용자 프로필 읽기(조직 기본 허용, 미확인 시 IT 확인) |

- Teams **Workflows 앱 사용 불가**와 **Teams 커넥터 사용 불가**는 다른 문제다. 앱이 없으면 Flow bot 게시·메시지 트리거가 막히고, 커넥터 자체가 DLP로 막히면 Teams 액션이 들어간 흐름은 저장이 거부된다. 둘은 `APPROVALS.md` 확인 항목에서 따로 점검한다.

