"""Pilot 03 성과 측정 — (1) 기대효과 모델 CSV 생성 (2) 실측 KPI 보고서 생성.

  python3 tools/kpi_report.py model                       → measurement/expected_savings.csv 생성·합계 출력
  python3 tools/kpi_report.py report <내보내기폴더> [--today YYYY-MM-DD] [--timelog 시간기록.csv]
      <내보내기폴더>: Lists '내보내기 › CSV로 내보내기' 파일(ActionItems.csv, DecisionLog.csv, ActionCandidates.csv)
      시간기록.csv: measurement/timelog_template.csv 형식(기준선·적용후 각 5일 이상)

효과 확정 규칙: 기준선과 적용후를 같은 방법으로 각각 5근무일 이상 기록한 항목만 '실측'으로 보고한다.
표준 라이브러리만 사용. 실제 데이터는 이 저장소에 커밋하지 말 것(로컬에서만 실행).
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = {l["name"]: l for l in json.loads((ROOT / "lists/lists_schema.json").read_text(encoding="utf-8"))["lists"]}

WORKDAYS = 240
WEEKS = 48
# (업무, 기준선 분, 목표 분, 단위, 연간 횟수, 활용률, 조건, 측정 방법)
MODEL = [
    ("아침 업무 파악(메일·채팅·일정·목록 순회)", 20, 8, "일", WORKDAYS, 0.7, "없음",
     "시간기록: 출근 후 '오늘 할 일 결정'까지 분"),
    ("회의 후속 정리(회의록·액션 정리·후속 메일)", 25, 8, "회의", 4 * WEEKS, 0.8, "Copilot 회의 전사 허용",
     "시간기록: 주관 회의 1건당 후속 정리 분"),
    ("액션 추적·독촉(누가 무엇을 언제까지)", 60, 20, "주", WEEKS, 0.8, "없음",
     "시간기록: 주간 진행 확인·독촉 메시지 작성 분"),
    ("메일 요청 정리·회신 대기 확인", 12, 4, "일", WORKDAYS, 0.5, "없음",
     "시간기록: 메일함에서 할 일·회신 대기 찾는 분"),
    ("주간보고 초안 작성(F12 주간 정리로 대체)", 30, 10, "주", WEEKS, 0.9, "없음",
     "시간기록: 주간보고 작성 분"),
    ("주간보고 폐지 시 남은 작성시간", 10, 0, "주", WEEKS, 1.0, "팀장 결정(주간보고 폐지·다이제스트 대체)",
     "시간기록: 주간보고 작성 분"),
    ("공장 자료 메일 첨부 저장·정리·수신 확인(F10)", 4, 0.5, "메일", 15 * WEEKS, 0.8, "없음",
     "FactoryInbox 건수 × 시간기록 표본(메일 1통 처리 분). 주 15통은 가정 — 대장이 실제 건수를 센다"),
    ("회의 준비(현황 확인·자료 찾기, F11)", 10, 3, "회의", 4 * WEEKS, 0.7, "없음",
     "시간기록: 회의 1건당 준비 분"),
    ("메일 할 일의 기한·우선순위 정하기(F13)", 1.5, 0.5, "메일", 6 * WORKDAYS, 0.6, "없음",
     "ActionItems '기한 근거' 채워진 비율 + 시간기록 표본"),
    ("정례 현황회의 참석", 60, 15, "주", WEEKS, 1.0, "팀장 결정(현황회의 15분화)",
     "Outlook 일정: 현황회의 실제 시간"),
]
MAINTENANCE_HOURS = 15  # 연간 운영·수정(가정, 개인, 흐름 13개)
TEAM_SIZE = 8
TEAM_MAINTENANCE_HOURS = 30  # 팀 확산 시 연간 운영(가정)


def model(write=True):
    rows, base_total, cond_total = [], 0.0, 0.0
    for task, before, after, unit, n, use, cond, how in MODEL:
        saved_h = (before - after) * n * use / 60
        rows.append([task, before, after, unit, n, use, round(saved_h, 1), cond, how])
        if cond == "없음" or cond.startswith("Copilot"):
            base_total += saved_h
        else:
            cond_total += saved_h
    net = base_total - MAINTENANCE_HOURS
    team = base_total * TEAM_SIZE - TEAM_MAINTENANCE_HOURS
    if write:
        out = ROOT / "measurement/expected_savings.csv"
        out.parent.mkdir(exist_ok=True)
        with out.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["업무", "기준선(분/단위,가정)", "목표(분/단위,가정)", "단위", "연간 횟수(가정)", "활용률(가정)",
                        "연간 절감시간(h)", "효과 조건", "측정 방법"])
            w.writerows(rows)
            w.writerow([])
            w.writerow(["# 개인(파일럿 사용자 1명) 기준. 계산식: (기준선−목표)×연간횟수×활용률÷60"])
            w.writerow(["# 조건 없는 효과 합계(h/년)", round(base_total, 1)])
            w.writerow(["# 연간 유지시간(h, 가정)", MAINTENANCE_HOURS])
            w.writerow(["# 순절감(h/년, 조직 결정 전)", round(net, 1)])
            w.writerow(["# 조직 결정 시 추가(h/년)", round(cond_total, 1)])
            w.writerow([f"# 팀 {TEAM_SIZE}명 확산 시(조건 없는 효과×{TEAM_SIZE} − 팀 유지 {TEAM_MAINTENANCE_HOURS}h, 가정)", round(team, 1)])
    return {"base": round(base_total, 1), "net": round(net, 1), "conditional": round(cond_total, 1),
            "team8": round(team, 1), "rows": rows}


def read_export(path: Path, list_name: str) -> list[dict]:
    """Lists CSV 내보내기는 표시 이름 머리글을 쓰므로 내부 이름으로 되돌린다."""
    if not path.exists():
        return []
    disp = {c["displayName"]: c["internalName"] for c in SCHEMA[list_name]["columns"]}
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [{disp.get(k, k): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def d10(s: str):
    s = (s or "").strip()
    if not s:
        return None
    s = s.replace(".", "-").replace("/", "-")[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def pct(a, b):
    return f"{a / b * 100:.0f}% ({a}/{b})" if b else "해당 없음(0건)"


def report(folder: Path, today: date, timelog: Path | None) -> str:
    acts = read_export(folder / "ActionItems.csv", "ActionItems")
    decs = read_export(folder / "DecisionLog.csv", "DecisionLog")
    cands = read_export(folder / "ActionCandidates.csv", "ActionCandidates")
    out = [f"# Pilot 03 KPI 보고서 (기준일 {today.isoformat()})", ""]
    via = {}
    for a in acts:
        via[a.get("CreatedVia") or "수동"] = via.get(a.get("CreatedVia") or "수동", 0) + 1
    auto = sum(v for k, v in via.items() if k != "수동")
    out += ["## 1. 기록 습관(입력 비용)", f"- 액션 총 {len(acts)}건, 자동·반자동 등록 비율 {pct(auto, len(acts))}",
            "- 경로별: " + (", ".join(f"{k} {v}" for k, v in sorted(via.items())) or "없음"), ""]
    open_ = [a for a in acts if a.get("Status") in ("미착수", "진행중")]
    dated_open = [a for a in open_ if d10(a.get("DueDate"))]
    overdue = [a for a in dated_open if d10(a["DueDate"]) < today]
    done = [a for a in acts if a.get("Status") == "완료" and d10(a.get("DueDate")) and d10(a.get("CompletedAt"))]
    ontime = [a for a in done if d10(a["CompletedAt"]) <= d10(a["DueDate"])]
    undated = len(open_) - len(dated_open)
    rem = [int(float(a["ReminderCount"])) for a in acts if a.get("Status") == "완료" and a.get("ReminderCount")]
    out += ["## 2. 실행 추적", f"- 미결 액션 중 기한 초과율: {pct(len(overdue), len(dated_open))}",
            f"- 기한 내 완료율: {pct(len(ontime), len(done))}", f"- 기한 미정 미결 액션: {undated}건",
            f"- 완료 액션당 평균 리마인더: {statistics.mean(rem):.1f}회" if rem else "- 완료 액션당 평균 리마인더: 데이터 없음", ""]
    waits = [(d10(d["DecidedAt"]) - d10(d["RequestedAt"])).days for d in decs
             if d10(d.get("RequestedAt")) and d10(d.get("DecidedAt"))]
    queue = [d for d in decs if d.get("Status") == "결정요청"]
    ages = [(today - d10(d["RequestedAt"])).days for d in queue if d10(d.get("RequestedAt"))]
    out += ["## 3. 의사결정 속도", f"- 결정 대기시간 중앙값(요청→확정): {statistics.median(waits):.1f}일 (n={len(waits)})" if waits
            else "- 결정 대기시간 중앙값: 데이터 없음",
            f"- 현재 결정 대기 {len(queue)}건, 최장 {max(ages)}일" if ages else f"- 현재 결정 대기 {len(queue)}건", ""]
    decided = [c for c in cands if c.get("Status") in ("등록완료", "기각", "오류", "승인")]
    rec = [c for c in decided if c.get("Verdict") == "추천"]
    rec_ok = [c for c in rec if c.get("Status") in ("등록완료", "승인")]
    rev = [c for c in decided if c.get("Verdict") == "검토필요"]
    rev_ok = [c for c in rev if c.get("Status") in ("등록완료", "승인")]
    out += ["## 4. AI(Copilot) 추출 품질", f"- 처리된 후보 {len(decided)}건 (대기 {len(cands) - len(decided)}건)",
            f"- '추천' 후보 채택률(정밀도 대용): {pct(len(rec_ok), len(rec))}  — 합격선 ≥90%",
            f"- '검토필요' 후보 중 사람이 고쳐 채택: {pct(len(rev_ok), len(rev))}", ""]
    if timelog and timelog.exists():
        with timelog.open(encoding="utf-8-sig", newline="") as f:
            logs = list(csv.DictReader(f))
        out += ["## 5. 시간 절감(실측)", "| 업무 | 기준선 일평균(분) | 적용후 일평균(분) | 차이 | 판정 |", "|---|---|---|---|---|"]
        tasks = sorted({r["업무"] for r in logs})
        for t in tasks:
            def daily(phase):
                days = {}
                for r in logs:
                    if r["업무"] == t and r["구분"] == phase:
                        days[r["날짜"]] = days.get(r["날짜"], 0) + float(r["소요분"] or 0)
                return days
            b, a = daily("기준선"), daily("적용후")
            if len(b) >= 5 and len(a) >= 5:
                mb, ma = statistics.mean(b.values()), statistics.mean(a.values())
                out.append(f"| {t} | {mb:.1f} | {ma:.1f} | {mb - ma:+.1f} | 실측 확정 |")
            else:
                out.append(f"| {t} | {len(b)}일 | {len(a)}일 | - | 기록 부족(각 5일 이상 필요) → 가정 유지 |")
        out.append("")
    m = model(write=False)
    out += ["## 6. 기대효과 모델(가정)", f"- 조건 없는 순절감 {m['net']}h/년(개인), 조직 결정 시 +{m['conditional']}h, 팀 8명 확산 시 {m['team8']}h/년",
            "- 실측(5장)이 확정되면 해당 업무의 가정값을 실측값으로 바꿔 다시 계산한다.", ""]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("model")
    r = sub.add_parser("report")
    r.add_argument("folder", type=Path)
    r.add_argument("--today", default=date.today().isoformat())
    r.add_argument("--timelog", type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "model":
        m = model()
        print(f"조건 없는 효과 {m['base']}h − 유지 {MAINTENANCE_HOURS}h = 순절감 {m['net']}h/년(개인), "
              f"조직 결정 시 +{m['conditional']}h, 팀 8명 {m['team8']}h/년")
    else:
        print(report(a.folder, date.fromisoformat(a.today), a.timelog))
    return 0


if __name__ == "__main__":
    sys.exit(main())
