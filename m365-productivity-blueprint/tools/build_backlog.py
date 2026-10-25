"""혁신 과제 백로그 → 우선순위 매트릭스(04) 및 KPI·ROI 모델(09) 생성기.

- 모든 수치는 '가정(Assumption)'이다. 실측값을 얻으면 OPPS 표의 값을 바꾸고 다시 실행한다.
- 실행: python3 tools/build_backlog.py  (표준 라이브러리만 사용)
- 출력: 04_Prioritization_Matrix.csv, 09_KPI_ROI_Model.csv (UTF-8 BOM → Excel에서 한글 깨짐 없음)
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 평가 기준과 가중치 (합계 1.00). 점수는 모두 1~5, 5가 '좋음'.
WEIGHTS = {
    "hours": 0.25,        # 연간 순절감시간(아래 구간표로 환산)
    "error": 0.10,        # 오류 감소 효과
    "decision": 0.15,     # 의사결정 속도 개선
    "reach": 0.10,        # 적용 대상자 × 업무 빈도
    "scalability": 0.10,  # 다른 업무·부서로 확산 가능성
    "ease": 0.10,         # 구현 용이성 (5=쉬움)
    "cost": 0.05,         # 구축·운영 비용 효율 (5=추가비용 없음)
    "license": 0.10,      # 라이선스·권한 실현성 (5=기본 권한으로 가능)
    "risk": 0.05,         # 보안·운영 리스크 (5=낮음)
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

HOURS_BINS = [(200, 5), (120, 4), (70, 3), (30, 2), (0, 1)]
HIGH_RISK_THRESHOLD = 2  # risk 점수가 이 값 이하이면 '별도 승인' 대상

# 시스템 구축 없이 규칙·습관 변경으로 즉시 시행하는 '제거(Eliminate) 패키지' → Phase 1에 바로 시행, TOP10 구축 과제에서 제외
ELIMINATE_PACKAGE = {"O14", "O17", "O26", "O30"}
# 독립 구축보다 상위 과제의 기능으로 흡수하는 편이 중복을 줄이는 과제
MERGED_INTO = {"O27": "O01", "O12": "O05", "O29": "O05", "O15": "O03", "O16": "O03",
               "O31": "O07", "O10": "O04", "O23": "O11"}

# 공통 가정: SCM 팀 8명, 연 240 근무일. (12_Open_Questions에서 실측 확인 필요)
TEAM = 8
DAYS = 240

# id, 과제명, 분류, ECRS 레버, 최소 시나리오,
# 연간 건수, 건당 절감(분), 활용률, 연간 유지(시간),
# error, decision, reach, scalability, ease, cost, license, risk, 핵심 기술
OPPS = [
    ("O01", "AI 업무 비서: 아침 브리핑(일정·미결·마감·SLA 위험 1장 요약)", "개인비서", "Integrate", "A",
     DAYS * TEAM, 12, 0.7, 12, 2, 3, 5, 5, 4, 5, 5, 4, "Power Automate(Recurrence)+Lists+Outlook+Teams 카드 / C: Copilot 예약 프롬프트"),
    ("O02", "이메일 요청 → 업무 자동 등록·미회신 추적", "이메일", "Integrate", "A",
     6 * DAYS * TEAM, 2, 0.5, 16, 3, 3, 5, 5, 3, 5, 4, 3, "Outlook 플래그 트리거+Lists / C: Copilot 추출+사용자 확인"),
    ("O03", "회의 결정사항·액션 레지스터와 자동 추적", "회의", "Standardize", "A",
     400, 25, 0.8, 12, 4, 5, 4, 5, 4, 5, 5, 4, "Lists(DecisionLog/ActionItems)+Teams 메시지 액션+리마인더 Flow"),
    ("O04", "공장 데이터 계약: 표준 제출→자동 정합성 검증→단일 원본", "Excel", "Eliminate", "A",
     6 * 52, 35, 0.9, 24, 5, 4, 3, 5, 3, 5, 5, 4, "Excel 표준 템플릿+Office Scripts+Power Automate / A-lite: Power Query 폴더 결합"),
    ("O05", "통합 업무요청 허브(기존 시제품 Lists 확장)", "요청관리", "Standardize", "A",
     1200, 12, 0.8, 20, 4, 4, 4, 5, 4, 5, 5, 4, "Lists+Power Automate+Approvals+Adaptive Cards"),
    ("O06", "S&OP 계획 변경 감지·의사결정 이슈 자동 도출", "S&OP", "Automate", "B",
     52, 180, 0.7, 30, 4, 5, 3, 4, 2, 4, 3, 3, "O04 단일 원본+버전 비교 Script / C: Power BI+Copilot 코멘트"),
    ("O07", "SCM 지식 검색 Agent(출처 제시)", "지식관리", "Augment", "C",
     3 * DAYS * TEAM, 4, 0.5, 24, 3, 4, 5, 5, 3, 2, 2, 3, "SharePoint 지식 라이브러리+Agent Builder(Copilot 라이선스 또는 종량제)"),
    ("O08", "경영진 보고 자동화(데이터→차트→핵심 메시지 초안)", "보고", "Automate", "B",
     64, 150, 0.8, 24, 4, 4, 3, 4, 3, 4, 3, 3, "Power BI 또는 Excel 차트+Office Scripts / C: Copilot in PowerPoint"),
    ("O09", "공장 간 생산배분 What-if 시뮬레이터", "분석", "Augment", "A",
     24, 240, 0.7, 16, 3, 5, 2, 3, 2, 4, 4, 4, "Excel LAMBDA/Python in Excel(표준 컴퓨트)"),
    ("O10", "생산능력 부하율·병목(TOC) 자동 분석", "분석", "Automate", "A",
     52, 120, 0.8, 12, 3, 4, 2, 3, 3, 5, 4, 4, "O04 단일 원본+Power Query/동적 배열"),
    ("O11", "재고 건전성 모니터(과잉·결품·장기체화 예외 알림)", "재고", "Automate", "A",
     52, 90, 0.8, 10, 4, 4, 3, 4, 3, 5, 4, 4, "O04 단일 원본+규칙 Script+Teams 알림"),
    ("O12", "계획 변경요청 관리와 Frozen Fence 위반 감지", "S&OP", "Standardize", "A",
     300, 20, 0.8, 12, 4, 4, 3, 4, 4, 5, 5, 4, "O05 허브의 요청유형 확장+규칙"),
    ("O13", "타부서 SCM 문의 셀프서비스 Agent", "Agent", "Eliminate", "C",
     10 * DAYS, 8, 0.4, 30, 3, 3, 4, 4, 2, 2, 2, 2, "Copilot Studio+O04/O05 데이터(권한 설계 필수)"),
    ("O14", "정례 진행현황 회의 → 비동기 업데이트로 대체", "회의", "Eliminate", "A",
     52 * TEAM, 40, 0.6, 6, 1, 3, 5, 5, 5, 5, 5, 5, "Teams 채널 게시+ActionItems 뷰(도구 추가 없음)"),
    ("O15", "결정 대기열(Decision Queue)과 결정 대기시간 측정", "의사결정", "Simplify", "A",
     150, 15, 0.7, 4, 2, 5, 3, 4, 4, 5, 5, 5, "DecisionLog 상태 '결정요청'+경과일 서식"),
    ("O16", "회의 사전자료(Pre-read) 자동 패키징", "회의", "Automate", "A",
     150, 20, 0.7, 6, 2, 3, 3, 4, 4, 5, 4, 4, "Outlook 일정+SharePoint 링크 수집 Flow"),
    ("O17", "주간보고 제거: 업무 데이터에서 상태보고 자동 생성", "보고", "Eliminate", "A",
     52 * TEAM, 30, 0.7, 8, 2, 3, 5, 5, 4, 5, 5, 4, "ActionItems/RequestHub 뷰+주간 다이제스트 Flow"),
    ("O18", "마스터데이터 품질 모니터(SKU·BOM·리드타임 불일치)", "데이터품질", "Automate", "B",
     52, 60, 0.7, 10, 5, 2, 2, 4, 3, 5, 3, 4, "ERP/APS 추출본+검증 Script"),
    ("O19", "핵심 Excel 자산 대장(EUC 리스크 관리)", "거버넌스", "Standardize", "A",
     4, 240, 1.0, 4, 4, 1, 2, 4, 4, 5, 5, 5, "Lists(자산 대장)+Excel 수식 점검"),
    ("O20", "자동화 자산 레지스트리·실행 오류 모니터링", "거버넌스", "Standardize", "A",
     52, 30, 0.9, 4, 4, 1, 2, 5, 4, 5, 5, 5, "FlowErrorLog List+Try/Catch 패턴+Git 백업"),
    ("O21", "해외 공장·법인 커뮤니케이션 표준 템플릿+번역", "커뮤니케이션", "Standardize", "A",
     3 * 52 * TEAM, 10, 0.5, 6, 3, 2, 4, 4, 5, 5, 5, 3, "Outlook 내 번역/빠른 단계·템플릿 / C: Copilot 초안"),
    ("O22", "신제품 론칭 Stage-gate 체크리스트 자동 추적", "S&OP", "Standardize", "A",
     20, 180, 0.7, 10, 4, 3, 2, 4, 4, 5, 5, 4, "Lists 템플릿+작업 자동 생성 Flow"),
    ("O23", "단산 SKU 잔량 소진·폐기 위험 관리", "재고", "Automate", "A",
     30, 120, 0.7, 8, 4, 3, 2, 3, 3, 5, 4, 4, "O04 단일 원본+소진 시뮬레이션"),
    ("O24", "원부자재 수급 리스크 조기 경보(소요 vs 공급 확정)", "공급", "Automate", "C",
     52, 90, 0.6, 16, 4, 4, 2, 3, 2, 3, 2, 3, "ERP 데이터 연동(Premium/게이트웨이)"),
    ("O25", "선적·물류 ETA 변경 감지 알림", "물류", "Automate", "C",
     52, 60, 0.6, 12, 3, 4, 2, 3, 2, 3, 2, 3, "물류 시스템 API(Premium/IT 승인)"),
    ("O26", "첨부파일 금지·링크 공유로 문서 단일 원본화", "문서관리", "Eliminate", "A",
     2 * DAYS * TEAM, 3, 0.6, 2, 4, 2, 5, 5, 5, 5, 5, 4, "SharePoint/Teams 파일+공유 링크 규칙"),
    ("O27", "개인 업무 칸반+주간 리뷰 자동화", "개인비서", "Simplify", "A",
     52 * TEAM, 20, 0.6, 4, 2, 2, 4, 4, 5, 5, 5, 5, "To Do/Planner+ActionItems 통합 뷰"),
    ("O28", "담당자 변경 시 인수인계 패키지 자동 생성", "지식관리", "Automate", "A",
     4, 960, 0.6, 4, 3, 1, 2, 4, 4, 5, 4, 4, "RequestHub/ActionItems/Decision 필터 내보내기"),
    ("O29", "승인 프로세스 표준화(근거·이력 자동 기록)", "승인", "Standardize", "A",
     400, 10, 0.8, 8, 3, 4, 3, 5, 4, 5, 5, 4, "Approvals 커넥터+RequestLog"),
    ("O30", "정기 현황 수집 메일 → Forms/Lists 직접 입력 전환", "자료취합", "Eliminate", "A",
     24, 120, 0.8, 4, 3, 2, 3, 4, 5, 5, 5, 4, "Forms+Lists(또는 Lists 양식)"),
    ("O31", "회의록·결정 근거 지식베이스 자동 축적", "지식관리", "Integrate", "B",
     400, 5, 0.6, 4, 2, 2, 3, 4, 3, 4, 3, 3, "DecisionLog+SharePoint 페이지 / C: Copilot 요약"),
    ("O32", "S&OP KPI 자동 산출과 편차 코멘트 초안", "S&OP", "Automate", "B",
     12, 360, 0.8, 10, 4, 4, 3, 4, 3, 4, 4, 4, "O04 단일 원본+KPI Script / C: Copilot 코멘트"),
    ("O33", "APS 실행 결과 Run-to-Run 비교 검증", "APS", "Automate", "B",
     52, 90, 0.7, 12, 5, 3, 2, 2, 3, 5, 4, 4, "APS 내보내기+diff Script"),
    ("O34", "조직 표준 프롬프트·Agent 라이브러리", "확산", "Standardize", "B",
     1 * DAYS * TEAM, 3, 0.4, 8, 1, 2, 4, 5, 5, 4, 3, 4, "SharePoint 페이지/Copilot 프롬프트 갤러리"),
    ("O35", "Agentic S&OP: 시나리오 자동 생성·제안(차세대)", "Agent", "Augment", "C",
     12, 480, 0.5, 40, 2, 5, 2, 3, 1, 1, 1, 1, "Copilot Studio 자율 Agent+APS/ERP 연동(IT 승인 필수)"),
]

FIELDS = ["id", "name", "category", "ecrs", "min_scenario", "annual_cases", "min_saved_per_case",
          "adoption", "maint_hours", "error", "decision", "reach", "scalability", "ease", "cost",
          "license", "risk", "tech"]


def hours_score(net_hours: float) -> int:
    for threshold, score in HOURS_BINS:
        if net_hours >= threshold:
            return score
    return 1


def evaluate(row: dict) -> dict:
    gross = row["annual_cases"] * row["min_saved_per_case"] / 60 * row["adoption"]
    net = gross - row["maint_hours"]
    scores = {k: row[k] for k in WEIGHTS if k != "hours"}
    scores["hours"] = hours_score(net)
    weighted = sum(WEIGHTS[k] * scores[k] for k in WEIGHTS) / 5 * 100
    return {
        **row,
        "gross_hours": round(gross, 1),
        "net_hours": round(net, 1),
        "hours_score": scores["hours"],
        "weighted_score": round(weighted, 1),
        "approval_required": "Y" if row["risk"] <= HIGH_RISK_THRESHOLD else "N",
    }


def build() -> list[dict]:
    rows = [evaluate(dict(zip(FIELDS, o))) for o in OPPS]
    rows.sort(key=lambda r: (-r["weighted_score"], -r["net_hours"]))
    rank = 0
    top = 0
    for r in rows:
        if r["approval_required"] == "N":
            rank += 1
            r["rank"] = rank
        else:
            r["rank"] = "별도승인"
        if r["id"] in ELIMINATE_PACKAGE:
            r["track"] = "제거패키지(즉시시행)"
        elif r["id"] in MERGED_INTO:
            r["track"] = f"{MERGED_INTO[r['id']]}에 통합"
        elif r["approval_required"] == "Y":
            r["track"] = "별도승인 후 재평가"
        elif top < 10:
            top += 1
            r["track"] = f"TOP10-{top:02d}"
        else:
            r["track"] = "백로그"
    return rows


def write_matrix(rows: list[dict]) -> Path:
    path = ROOT / "04_Prioritization_Matrix.csv"
    header = ["순위", "ID", "과제명", "분류", "ECRS레버", "최소시나리오(A/B/C)",
              "연간건수(가정)", "건당절감분(가정)", "활용률(가정)", "연간유지시간(가정)",
              "연간총절감시간", "연간순절감시간", "절감시간점수",
              "오류감소", "의사결정속도", "적용범위·빈도", "확산가능성", "구현용이성",
              "비용효율", "라이선스·권한실현성", "리스크(5=낮음)", "가중점수(100)", "별도승인필요",
              "추진구분", "핵심기술", "근거구분"]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow([r["rank"], r["id"], r["name"], r["category"], r["ecrs"], r["min_scenario"],
                        r["annual_cases"], r["min_saved_per_case"], r["adoption"], r["maint_hours"],
                        r["gross_hours"], r["net_hours"], r["hours_score"],
                        r["error"], r["decision"], r["reach"], r["scalability"], r["ease"],
                        r["cost"], r["license"], r["risk"], r["weighted_score"], r["approval_required"],
                        r["track"], r["tech"], "가정(팀 8명·연 240일 기준, 실측 전)"])
        w.writerow([])
        w.writerow(["# 가중치"] + [f"{k}={v}" for k, v in WEIGHTS.items()])
        w.writerow(["# 절감시간점수 구간", ">=200h:5", "120~199h:4", "70~119h:3", "30~69h:2", "<30h:1"])
        w.writerow(["# 계산식", "연간순절감시간 = 연간건수 × 건당절감분/60 × 활용률 − 연간유지시간"])
        w.writerow(["# 별도승인", f"리스크 점수 <= {HIGH_RISK_THRESHOLD} 인 과제는 효과와 무관하게 순위에서 제외하고 IT·보안 승인 후 재평가"])
    return path


# 파일럿 KPI·ROI 모델. 시간당 인건비(H)는 확정하지 않고 입력변수로 둔다.
PILOTS = [
    # pilot, 범위 과제, 구축시간, 연간유지시간, Scenario A 추가 라이선스(원/년), KPI 목록
    ("P1 통합 업무요청 허브", ["O05", "O12", "O29"], 40, None, 0, [
        ("요청 1건당 SCM 처리 시간(분)", "타임 로그 2주 표본(20건)", "기준선 실측", "-30% 이상"),
        ("요청→완료 리드타임 중앙값(영업일)", "RequestLog Created↔Closed", "기준선 실측", "-25%"),
        ("SLA(약속기한) 준수율", "DueDateCommitted vs ClosedDate", "기준선 실측", "90% 이상"),
        ("'진행상황 문의' 메일·메신저 건수/주", "받은편지함 검색 표본", "기준선 실측", "-50%"),
        ("요청 정보 누락으로 인한 재요청률", "RequestLog EventType=정보보완", "기준선 실측", "10% 이하"),
    ]),
    ("P2 공장 데이터 계약·자동 검증", ["O04", "O10", "O11"], 60, None, 0, [
        ("주간 취합·검증 소요시간(분/주)", "2주 타임 로그", "기준선 실측", "-60% 이상"),
        ("제출 데이터 검증 실패율(%)", "SubmissionLog Result", "도입 1주차 값", "4주 내 절반"),
        ("오류 발견 시점(제출 후 경과 시간)", "SubmissionLog 검증시각-제출시각", "수작업: 수시간~수일", "10분 이내"),
        ("재요청 메일 건수/주", "보낸편지함 표본", "기준선 실측", "-70%"),
        ("단일 원본 이후 재가공(복사·붙여넣기) 단계 수", "프로세스 맵", "기준선 실측", "0~1단계"),
    ]),
    ("P3 결정–액션 루프+아침 브리핑", ["O03", "O01", "O14", "O17"], 40, None, 0, [
        ("결정사항의 액션 등록률(%)", "DecisionLog↔ActionItems 연결", "기준선 실측", "95% 이상"),
        ("액션 기한 초과율(%)", "ActionItems DueDate vs CompletedAt", "기준선 실측", "-50%"),
        ("결정 대기시간 중앙값(일)", "DecisionLog 결정요청→확정", "기준선 실측", "-30%"),
        ("정례 현황회의 시간(시간/주·팀)", "Outlook 일정 집계", "기준선 실측", "-50%"),
        ("아침 업무 파악 시간(분/일)", "자기기록 5일", "기준선 실측", "-60%"),
    ]),
]


def write_roi(rows: list[dict]) -> Path:
    by_id = {r["id"]: r for r in rows}
    path = ROOT / "09_KPI_ROI_Model.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["섹션", "항목", "값", "단위", "구분", "설명·계산식"])
        w.writerow(["입력변수", "H_시간당인건비", "", "원/시간", "사용자 입력 필요",
                    "회사 기준 인건비(복리후생 포함). 미확정 시 비워두고 '시간 ROI'만 사용"])
        w.writerow(["입력변수", "TEAM_팀인원", TEAM, "명", "가정", "SCM 팀 인원(실측 후 수정)"])
        w.writerow(["입력변수", "DAYS_연근무일", DAYS, "일", "가정", ""])
        w.writerow(["입력변수", "L_추가라이선스비_ScenarioC", "", "원/년", "견적 필요",
                    "Copilot·Premium·Copilot Credits 견적(07 문서 참조)"])
        for name, ids, build_h, _, lic, kpis in PILOTS:
            gross = sum(by_id[i]["gross_hours"] for i in ids)
            maint = sum(by_id[i]["maint_hours"] for i in ids)
            net = gross - maint
            # 첫해 순효과: 파일럿 이후 9개월 운영 가정(0.75) − 구축시간
            first_year = round(net * 0.75 - build_h, 1)
            w.writerow([name, "범위 과제", "+".join(ids), "", "", ""])
            w.writerow([name, "연간총절감시간(가정)", round(gross, 1), "시간/년", "가정", "Σ 연간건수×건당절감×활용률"])
            w.writerow([name, "연간유지시간(가정)", maint, "시간/년", "가정", ""])
            w.writerow([name, "연간순절감시간(가정)", round(net, 1), "시간/년", "가정", "총절감−유지"])
            w.writerow([name, "구축시간(가정)", build_h, "시간", "가정", "설계·구축·테스트·교육"])
            w.writerow([name, "첫해 순효과(가정)", first_year, "시간", "가정", "순절감×0.75(9개월 운영)−구축시간"])
            w.writerow([name, "시간 ROI(가정)", round(net / (build_h + maint), 2), "배", "가정",
                        "연간순절감 ÷ (구축+연간유지). 1 초과 시 첫해 회수"])
            w.writerow([name, "금액 ROI 계산식", "", "", "계산식",
                        "(연간순절감×H − 추가라이선스) ÷ (구축시간×H + 추가라이선스)"])
            w.writerow([name, "Scenario A 추가 라이선스", lic, "원/년", "가정", "표준 커넥터만 사용 시 0"])
            for kpi, src, base, target in kpis:
                w.writerow([name, f"KPI: {kpi}", "", "", f"기준선={base}; 목표={target}", f"측정원천: {src}"])
        w.writerow(["원칙", "효과 확정 규칙", "", "", "",
                    "기준선과 적용 후 각각 최소 2주 동일 방법으로 측정한 값만 '확정 효과'로 보고. 그 전에는 '가정' 표기 유지"])
    return path


def main() -> int:
    rows = build()
    m = write_matrix(rows)
    r = write_roi(rows)
    print(f"wrote {m.name}, {r.name}")
    for row in rows:
        print(f"{str(row['rank']):>6}  {row['id']}  {row['weighted_score']:>5}  {row['net_hours']:>7}h  {row['track']:<14} {row['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
