"""Pilot 03 아침 브리핑 — 우선순위 규칙과 카드 생성의 참조 구현 (Scenario A: 규칙 기반, AI 불필요).

Power Automate P3-F4가 같은 규칙으로 Adaptive Card를 만든다. 이 모듈은
  1) 규칙을 모의 데이터로 테스트하고  2) 카드 JSON 크기(Teams 약 28KB 제한)를 사전 검증한다.
입력은 Flow가 모으는 4개 원천과 같은 모양의 JSON(sample_data/brief_input.json).
실행: python3 daily_brief.py ../sample_data/brief_input.json  → 카드 JSON 출력
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

WORK_START = time(9, 0)
WORK_END = time(18, 0)
FOCUS_MIN_MINUTES = 60
TOP_N = 5
SECTION_MAX = 5
CARD_LIMIT_BYTES = 28 * 1024

# 점수 규칙(높을수록 먼저). 운영 중 조정 시 Flow의 Compose 'Score' 식도 같이 바꾼다.
SCORE = {
    "action_overdue": 100, "action_overdue_per_day": 5,
    "request_overdue": 90,
    "action_due_today": 80,
    "decision_waiting": 70, "decision_waiting_per_day": 3,
    "request_due_soon": 60,
    "reply_waiting": 40, "reply_waiting_per_day": 2,
}
OPEN_ACTION = {"미착수", "진행중"}


def _d(s: str) -> date:
    return date.fromisoformat(s[:10])


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)


def score_items(data: dict, today: date) -> list[dict]:
    items: list[dict] = []
    for a in data.get("actions", []):
        if a["status"] not in OPEN_ACTION or not a.get("due"):
            continue
        due = _d(a["due"])
        kind = "회신대기" if a.get("actionType") == "회신대기" else "액션"
        if kind == "회신대기" and due <= today:
            days = (today - due).days
            items.append({"score": SCORE["reply_waiting"] + SCORE["reply_waiting_per_day"] * days,
                          "kind": kind, "id": a["id"], "text": f"{a['title']} (회신 대기 {days}일)", "url": a.get("url", "")})
        elif due < today:
            days = (today - due).days
            items.append({"score": SCORE["action_overdue"] + SCORE["action_overdue_per_day"] * days,
                          "kind": "기한초과", "id": a["id"], "text": f"{a['title']} ({days}일 초과)", "url": a.get("url", "")})
        elif due == today:
            items.append({"score": SCORE["action_due_today"], "kind": "오늘마감", "id": a["id"],
                          "text": a["title"], "url": a.get("url", "")})
    for d in data.get("decisions", []):
        if d["status"] != "결정요청":
            continue
        age = (today - _d(d["requestedAt"])).days
        items.append({"score": SCORE["decision_waiting"] + SCORE["decision_waiting_per_day"] * age,
                      "kind": "결정대기", "id": d["id"], "text": f"{d['title']} (대기 {age}일)", "url": d.get("url", "")})
    for r in data.get("requests", []):
        if r["slaState"] == "overdue":
            items.append({"score": SCORE["request_overdue"], "kind": "SLA초과", "id": r["id"],
                          "text": r["title"], "url": r.get("url", "")})
        elif r["slaState"] == "due_soon":
            items.append({"score": SCORE["request_due_soon"], "kind": "SLA임박", "id": r["id"],
                          "text": r["title"], "url": r.get("url", "")})
    items.sort(key=lambda x: (-x["score"], x["id"]))
    return items


def focus_blocks(events: list[dict], today: date) -> list[tuple[str, str]]:
    """근무시간 중 일정이 없는 60분 이상 구간(집중 시간 후보)."""
    start, end = datetime.combine(today, WORK_START), datetime.combine(today, WORK_END)
    busy = sorted((max(_dt(e["start"]), start), min(_dt(e["end"]), end))
                  for e in events if not e.get("isAllDay") and _dt(e["end"]) > start and _dt(e["start"]) < end)
    free, cur = [], start
    for s, e in busy:
        if s > cur and (s - cur) >= timedelta(minutes=FOCUS_MIN_MINUTES):
            free.append((cur.strftime("%H:%M"), s.strftime("%H:%M")))
        cur = max(cur, e)
    if end - cur >= timedelta(minutes=FOCUS_MIN_MINUTES):
        free.append((cur.strftime("%H:%M"), end.strftime("%H:%M")))
    return free


def meeting_hours(events: list[dict], today: date) -> float:
    total = 0.0
    for e in events:
        if e.get("isAllDay"):
            continue
        s, en = _dt(e["start"]), _dt(e["end"])
        if s.date() == today:
            total += (en - s).total_seconds() / 3600
    return round(total, 1)


def build_brief(data: dict) -> dict:
    today = _d(data["today"])
    items = score_items(data, today)
    events = [e for e in data.get("events", []) if _dt(e["start"]).date() == today and not e.get("isAllDay")]
    no_preread = [e["subject"] for e in events if e.get("isOrganizer") and not e.get("hasAgendaLink")]
    return {
        "today": today.isoformat(),
        "top": items[:TOP_N],
        "counts": {k: sum(1 for i in items if i["kind"] == k)
                   for k in ("기한초과", "오늘마감", "결정대기", "SLA초과", "SLA임박", "회신대기")},
        "meetingCount": len(events),
        "meetingHours": meeting_hours(events, today),
        "focusBlocks": focus_blocks(events, today),
        "organizerWithoutAgenda": no_preread[:SECTION_MAX],
        "events": [{"time": _dt(e["start"]).strftime("%H:%M"), "subject": e["subject"]}
                   for e in sorted(events, key=lambda x: x["start"])][:8],
    }


def to_card(brief: dict) -> dict:
    body = [
        {"type": "TextBlock", "text": f"아침 브리핑 · {brief['today']}", "weight": "Bolder", "size": "Medium"},
        {"type": "TextBlock", "wrap": True, "spacing": "Small",
         "text": (f"회의 {brief['meetingCount']}건({brief['meetingHours']}h) · 기한초과 {brief['counts']['기한초과']} · "
                  f"결정대기 {brief['counts']['결정대기']} · SLA위험 {brief['counts']['SLA초과'] + brief['counts']['SLA임박']}")},
        {"type": "TextBlock", "text": "오늘 먼저 처리할 5가지", "weight": "Bolder", "spacing": "Medium"},
    ]
    if brief["top"]:
        body.append({"type": "FactSet", "facts": [{"title": i["kind"], "value": i["text"]} for i in brief["top"]]})
    else:
        body.append({"type": "TextBlock", "text": "급한 미결 항목이 없습니다. 전략 과제에 시간을 쓰세요.", "wrap": True})
    blocks = ", ".join(f"{a}~{b}" for a, b in brief["focusBlocks"]) or "없음(일정 재조정 검토)"
    body.append({"type": "TextBlock", "text": f"집중 가능 시간: {blocks}", "wrap": True, "spacing": "Medium"})
    if brief["events"]:
        body.append({"type": "FactSet", "facts": [{"title": e["time"], "value": e["subject"]} for e in brief["events"]]})
    if brief["organizerWithoutAgenda"]:
        body.append({"type": "TextBlock", "color": "Warning", "wrap": True,
                     "text": "안건·사전자료 링크가 없는 내 주관 회의: " + ", ".join(brief["organizerWithoutAgenda"])})
    card = {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard",
            "version": "1.4", "body": body,
            "actions": [{"type": "Action.OpenUrl", "title": "내 액션 열기", "url": "{{MyActionsViewUrl}}"},
                        {"type": "Action.OpenUrl", "title": "결정 대기열", "url": "{{DecisionQueueViewUrl}}"}]}
    size = len(json.dumps(card, ensure_ascii=False).encode("utf-8"))
    if size > CARD_LIMIT_BYTES:
        raise ValueError(f"카드 크기 {size}B > {CARD_LIMIT_BYTES}B")
    return card


def main(argv: list[str]) -> int:
    data = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    print(json.dumps(to_card(build_brief(data)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
