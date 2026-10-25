# 02. Microsoft 365 기술 지도 (업무 방식 관점)

> 기준일 2026-10-25. **기능이 존재한다는 것과 사용자가 쓸 수 있다는 것은 다르다.** 아래 '라이선스·권한' 열은 일반 원칙이며, 사용자 테넌트에서의 실제 사용 가능 여부는 `01` 문서 D1~D10 진단으로 확인해야 한다.
>
> **검증 등급**
> - ✅ **검색확인**: 2026-10-25에 Microsoft 공식 페이지(learn.microsoft.com, support.microsoft.com, microsoft.com, techcommunity)를 웹 검색 결과로 확인. *이 실행 환경에서는 learn.microsoft.com 본문 직접 열람이 네트워크 정책으로 차단되어 검색 결과 요약으로 확인했다. 운영 배포 전 본문 재확인 권장.*
> - ⚠ **상충**: 공식 출처끼리 또는 공식·커뮤니티 간 내용이 다름 → 테넌트에서 직접 확인 필수
> - ❔ **미검증**: 작성자의 사전 지식. 공식 문서 확인 전까지 설계의 필수 전제로 쓰지 않음
>
> 출처 ID(S01…)는 `11_Official_Sources.md` 참조.

---

## 1. 이 문서를 읽는 법 — 기능 목록이 아니라 '역할' 지도

기능을 나열하지 않고, 업무 운영체계에서 각 기술이 맡는 **역할**로 분류했다. 같은 역할을 하는 도구가 여럿이면 하나만 고른다(도구 최소화).

| 역할 | 1순위(기본 권한) | 대안 / 확장 | 고르지 않은 것과 이유 |
|---|---|---|---|
| 구조화된 업무 기록(요청·결정·액션) | **Microsoft Lists** | Dataverse(대량·관계형) | Planner: 구조화 필드·API 제약, Excel: 동시 편집·이력 약함 |
| 표 형식 데이터 원본(주간 사실 데이터) | **Excel 표(tblFact) on SharePoint** | Dataverse / Power BI 데이터플로 | Lists: 수만 행 수치 집계에 부적합 |
| 이벤트 감지·규칙 실행 | **Power Automate 클라우드 흐름(표준 커넥터)** | Copilot Studio 에이전트 흐름 | Power Automate Desktop: 화면 자동화는 마지막 수단 |
| 데이터 가공·검증 | **Office Scripts**(서버 실행) | Power Query(수동 새로 고침), Python in Excel | VBA: 클라우드 흐름에서 실행 불가 |
| 사람 인터페이스(알림·입력) | **Teams 채팅 + Adaptive Card** | Lists 양식, Power Apps | 이메일 알림: 묻히고 추적 불가 |
| 승인 | **Approvals 커넥터** | Lists 상태 + 카드 | 메일 회신 승인: 감사 불가 |
| 분석·시각화 | **Excel(동적 배열·피벗)** | Power BI(Pro 필요 여부 확인) | - |
| AI 증강 | **(라이선스 있으면) M365 Copilot·Agent Builder** | Copilot Studio | 승인되지 않은 외부 AI: 금지 |

## 2. 기술별 검증표

### A. 기본 업무 도구

| 기술 | 제공 상태 | 라이선스 | 권한 | DLP·보안 영향 | 추가비용 | 업무 방식 관점의 실질적 장점 / 한계 | 근거 |
|---|---|---|---|---|---|---|---|
| Microsoft Lists / SharePoint 목록 | GA | M365 기본 | 사이트 편집(목록 생성), 소유자(권한·설정) | 사이트 권한 상속, 버전 기록 | 0 | 목록당 최대 3천만 항목 저장, 단 **한 번의 보기·쿼리는 약 5,000건(목록 보기 임계값) 이하**로 처리 → 인덱스 열·필터 보기 필수. 한도 변경 불가 | ✅ S27 |
| SharePoint 문서 라이브러리 | GA | M365 기본 | 사이트 편집 | 민감도 레이블·보존 정책 적용 대상 | 0 | 파일 '첨부' 대신 '링크'로 단일 원본화(O26) | ❔ |
| Excel(데스크톱·웹) 동적 배열·LAMBDA | GA | M365 기본 | - | - | 0 | 반복 계산을 함수 하나로 표준화 → 사람 간 수식 편차 제거 | ❔ |
| Teams 회의 인텔리전트 요약(Recap) | GA | **Teams Premium 또는 Copilot 라이선스** | 관리자 정책: 기록·전사 허용 | 전사본 보존 정책 | 라이선스 | 회의록 작성 시간 제거. 오디오 요약은 Copilot 라이선스 필요 | ✅ S19 |
| Teams Facilitator(AI 회의 노트) | GA(정확한 상태 확인 필요) | Copilot 라이선스 필요(커뮤니티 답변) | 관리자: 앱·회의 정책 'Copilot 허용' | 회의 정책 의존 | 라이선스 | 회의 중 실시간 노트·액션 정리 | ⚠ 커뮤니티 출처 위주, S19 |
| Loop 앱·구성요소 | GA | 업무 계정이면 사용 가능, Copilot in Loop는 Copilot 필요 | 2026-02부터 저장소 요건 충족 시 워크스페이스 생성 가능 | Loop 파일도 SharePoint Embedded 저장 | 0(Copilot 기능 제외) | 비동기 진행 공유 페이지. 단 **구조화 데이터 원본으로는 Lists가 적합** | ✅ S33 |
| Copilot Pages / Notebooks | GA | Pages: OneDrive 라이선스, Notebooks: Copilot 또는 Copilot Chat | - | - | - | AI 답변을 팀 문서로 고정 | ✅ S33 |
| Planner(기본) | GA | M365 기본 | 그룹 구성원 | - | 0 | 간단 작업판. Power Automate Planner 커넥터는 **기본 플랜만 지원** | ✅ S20 |
| Planner 프리미엄 플랜 | GA | Planner Plan 1(구 Project Plan 1) 이상 | - | - | 유료 | 일정·의존관계. 표준 Planner 커넥터·Graph Planner API로 프리미엄 데이터 접근 불가(Dataverse 경유) | ⚠ S20 + 커뮤니티 |
| To Do / OneNote / Forms / Word / PowerPoint | GA | M365 기본 | - | - | 0 | Forms→Lists 직접 입력 전환(O30), Outlook 플래그↔To Do 연동 | ❔ |

### B. 자동화·개발 도구

| 기술 | 제공 상태 | 라이선스 | 표준/프리미엄 | 권한 | 추가비용 | 실질적 장점 / 한계 | 근거 |
|---|---|---|---|---|---|---|---|
| Power Automate 클라우드 흐름 | GA | **M365 포함(시드) 라이선스 = 표준 커넥터만** | SharePoint·Outlook·Teams·Excel Online (Business)·Approvals 등 표준 | 일반 사용자 생성 가능(DLP 범위 내) | 0 | 이벤트 기반 자동화의 중심. 동시성 제어 1~100(기본 해제, 켜면 되돌리려면 트리거 재생성), 재시도 지수 정책, 14일 연속 한도 초과 시 자동 중지 | ✅ S08, S32 |
| Power Automate Premium / Process | GA | Premium 사용자당 월 $15, Process 흐름당 월 $150(2025-05 가이드, 2026-01 가이드 유지 추정) | HTTP·Dataverse·SQL·사용자 지정 커넥터 등 | 라이선스 할당은 관리자 | 유료 | 자동/예약 흐름은 **소유자만** Premium 필요, 수동(인스턴트) 흐름은 **실행자 모두** 필요 | ✅ S08, S09, S10 |
| Excel Online (Business) 'Run script' / 'Run script from SharePoint library' | GA(구 문서엔 Preview 표기) | 업무용 M365 | **표준** | 파일·스크립트 접근 권한 | 0 | 사용자당 1,600회/일·10초당 3회, 동기 120초, 요청·응답 5MB, 파일 25MB, 스크립트 내 외부 호출(fetch) 불가. SharePoint 저장 스크립트로 개인 OneDrive 의존 제거 | ✅ S11, S12, S13 |
| Office Scripts | GA | 업무용 M365 | - | 관리자 비활성화 가능 | 0 | TypeScript, 서버 실행 → 담당자 PC가 꺼져도 동작. VBA 대체 | ✅ S11, S14 |
| Power Query | GA | M365 기본 | - | 원천 접근 권한 | 0 | 폴더 결합으로 '복사·붙여넣기' 제거. 단 새로 고침은 사람이(데스크톱) | ❔ |
| Python in Excel | GA | 업무·기업 구독에 표준 컴퓨트 포함, 고속 컴퓨트는 유료 추가 기능 | - | 관리자 정책 | 0(표준) | Windows 2408+, Mac, 웹. Microsoft 클라우드에서 실행. 장치 기반 라이선스·공유 컴퓨터 활성화 미지원 | ✅ S15, S16 |
| Power Automate Desktop(RPA) | GA | Windows 사용자는 기본 환경·개인용 attended만, **M365 시드 라이선스엔 미포함**, 클라우드 트리거·공유는 Premium | 해당 없음 | 설치 권한 | Premium | ERP/MES 화면 반복 입력의 최후 수단. API·내보내기 파일이 있으면 쓰지 않는다 | ✅ S08, S28 (무료 범위 문서 간 ⚠) |
| Approvals 커넥터 | GA | M365 기본 | 표준 | - | 0 | 승인 이력이 자동 기록(감사) | ❔ |
| Adaptive Cards in Teams | GA | M365 기본 | Teams 커넥터 표준 | Teams 관리 센터에서 **Workflows 앱 허용** 필요 | 0 | 메시지 크기 약 28KB, 템플릿 기능 미지원. 'Post adaptive card and wait for a response'는 **폐지 여부 출처 상충** → 파일럿은 '기다리지 않는' 카드 + Lists 링크로 설계 | ⚠ S31 + 커뮤니티 |
| Teams 'For a selected message' 트리거 | GA | M365 기본 | 표준 | **기본(Default) 환경**의 흐름만 메시지 메뉴에 표시된다는 보고 | 0 | 대화 속 요청·결정을 클릭 두 번으로 구조화(P1-F4, P3-F1) | ✅ S35 (환경 제약은 커뮤니티) |
| Microsoft Graph API | GA | - | (Power Automate에서 HTTP 호출 시 Premium) | 위임 Mail.Read는 문서상 관리자 동의 불필요이나, Microsoft 관리 동의 정책 변경(MC1163922)으로 메일·Teams 데이터 접근 앱에 **관리자 승인 필요** 가능 | IT 승인 | 표준 커넥터로 부족할 때만. 앱 등록은 IT | ⚠ S30 |
| PnP PowerShell | 커뮤니티 OSS | - | - | 2024-09 공용 앱 제거 → **조직 전용 Entra ID 앱 등록 필수** | IT 승인 | 목록 일괄 생성(Scenario B). 일반 사용자 단독 사용 불가 | ✅ S37(비MS) |
| AI Builder 크레딧 | **폐지 진행**: 2026-11-01 판매 종료, 이후 Copilot Credits로 대체 | - | - | - | - | Power Automate의 AI 프롬프트 액션 비용 모델이 바뀜 → 신규 설계에서 AI Builder 크레딧 전제 금지 | ✅ S26 |

### C. AI 및 Agent

| 기술 | 제공 상태 | 라이선스 | 권한 | 보안·DLP | 추가비용 | 실질적 장점 / 한계 | 근거 |
|---|---|---|---|---|---|---|---|
| Microsoft 365 Copilot Chat(무료 포함) | GA | 자격 있는 M365 플랜에 포함 | - | 엔터프라이즈 데이터 보호 | 0 | 웹 기반 + 지침·공개 웹 기반 선언형 에이전트는 무료. **SharePoint 등 조직 데이터 접지 에이전트는 종량제(기본 꺼짐, 관리자가 Azure 구독 연결)** | ✅ S01, S02, S04 |
| Microsoft 365 Copilot(유료) | GA | 기업 추가 기능 $30/사용자/월(연간), Business 추가 기능 $21(2026-07~12 프로모션 $18) | 관리자 할당 | 기존 권한·민감도 레이블 준수 | 유료 | 메일·회의·파일 전반 접지, 에이전트 사용 포함 | ✅ S05, S06, S03 |
| Agent Builder(Copilot 내 노코드 에이전트) | GA(일부 'Skills'는 Frontier 프로그램 Preview) | SharePoint·OneDrive 지식은 **Copilot 라이선스 필요** | - | 기존 권한 준수, Restricted SharePoint Search 켜져 있으면 SharePoint 지식 불가 | 0~라이선스 | 지식: 웹·SharePoint(최대 100개 파일/폴더/사이트 + 목록 1개)·Teams·메일 등 | ✅ S21, S22 |
| Microsoft 365 Agents Toolkit(선언형 에이전트) | GA | 개발 도구 무료, 사용은 위와 동일 | 앱 업로드(사이드로드) 권한은 관리자 | 지식 범위 미지정 시 **사용자가 접근 가능한 OneDrive·SharePoint 전체**가 대상 → 반드시 범위 지정 | 0 | 지침 8,000자 한도, 모델 일반지식 억제 옵션 존재 | ✅ S23, S24 |
| Copilot Studio | GA | Copilot Credits: 테넌트 팩 월 $200(25,000 크레딧), 종량제, 사전구매 플랜 / M365 Copilot 사용자는 M365 내 내부 에이전트 포함 | 환경 메이커 권한 | DLP·환경 정책 적용 | 유료(사용량) | 자율 트리거·에이전트 흐름·MCP 도구 연결. 비용은 사용량 기반이라 **파일럿 전 크레딧 소비량 추정 필수** | ✅ S17, S18, S38 (세부 계량 방식 문서 간 ⚠) |
| Copilot Studio MCP 연결 | GA(2025-05), SSE 전송 2025-08 이후 미지원(Streamable만) | Copilot Studio | 생성형 오케스트레이션 필수 | 승인된 MCP 서버만 | 사용량 | 사내 시스템을 표준 프로토콜로 에이전트 도구화 → ERP/APS 연동의 미래 경로(IT 소유) | ✅ S25 |
| Copilot 예약 프롬프트(Scheduled prompts) | GA(2026-08부터 '연결된 경험'으로 이동) | Copilot 라이선스 + 표준 Power Automate | 연결된 경험 허용 | 관리자 비활성화 가능 | 라이선스 | 아침 받은편지함 요약을 AI로(Pilot 03 Scenario C). 최대 10개 예약 | ✅ S36 |
| Copilot in Excel / Word / PowerPoint 에이전트 기능 | GA(2026-04-22) | Copilot 라이선스 | - | - | 라이선스 | Excel 에이전트 모드에서 OpenAI·Anthropic 모델 선택. 보고서 초안·분석 보조(O08) | ✅ S29 |

### D. 고급 아키텍처 요소

| 요소 | 상태 | 라이선스 | 판단 |
|---|---|---|---|
| Dataverse(정식) | GA | Power Apps/Automate **Premium** | 관계형·트랜잭션·행 단위 보안이 필요해지는 Phase 4 이후 후보 ❔ |
| Dataverse for Teams | GA | Teams 포함 라이선스에서 프리미엄 커넥터 일부 사용 가능(Dataverse for Teams 환경 한정) | 팀 단위 앱엔 유효하나 환경 관리·용량 제약 → 파일럿 비채택 ✅ S08(시드 표 각주) |
| Power BI | GA | 공유·예약 새로 고침에 Pro/PPU 등 필요(E5 포함 여부 ❔) | 공유 용량은 하루 8회 예약 새로 고침, 온프레미스 원천은 게이트웨이 필요 ✅ S34 |
| 조직 지식 검색(RAG) | GA | Copilot 또는 종량제 | Agent Builder 지식 + SharePoint 권한 = 사내 RAG. 별도 벡터 DB 구축 불필요 ✅ S21–S23 |
| Git 기반 자동화 자산 관리 | - | - | 흐름 '내보내기(패키지 .zip)'·스크립트(.osts의 TS 원문)·카드 JSON을 저장소에 보관. 이 저장소가 그 시작점 |

## 3. 결론: 선택한 기술 조합과 그 이유

1. **Lists + Power Automate(표준) + Teams 카드 + Office Scripts** 만으로 3개 파일럿 전부 구현 가능 → 추가 라이선스 0(Scenario A/B).
2. AI는 **'없어도 동작, 있으면 가속'** 위치에 둔다. Copilot 라이선스·정책이 확인되면 Pilot 03의 AI 추출·결정 조회 에이전트, O07 지식 에이전트를 켠다.
3. 프리미엄이 필요해지는 시점(ERP/APS 직접 연동, Dataverse)은 **효과가 측정된 뒤**(Phase 4)로 미룬다 — 비용을 효과 증거로 정당화한다.
4. 출처가 상충하는 기능(카드 '응답 대기', Facilitator 라이선스, Copilot Studio 계량 방식)은 설계의 필수 경로에서 제외했다.
