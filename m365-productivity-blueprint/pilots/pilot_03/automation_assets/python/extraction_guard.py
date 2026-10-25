"""Pilot 03 AI 추출 결과 검증기 (환각·오류 방지 가드레일)

AI(Copilot 회의 요약, Copilot Studio 프롬프트 등)가 회의록에서 뽑은 결정·액션 JSON을
사람에게 '확인 요청'하기 전에 기계적으로 검사한다. 규칙:
  G1 스키마: 필수 필드·형식
  G2 근거(evidence)는 회의록 원문에 그대로 존재해야 함(공백 정규화 후 부분 문자열, 8자 이상)
  G3 담당자는 참석자 명부(roster)에 있어야 함 — AI가 이메일을 지어내지 못하게 명부에서만 매핑
  G4 기한: 원문에 기한 표현이 없으면 null(=기한 미정, 사람이 정함). 날짜는 회의일 이후 180일 이내
  G5 중복 액션 제거
  G6 액션의 decision_ref는 존재하는 결정 번호여야 함
결과: accepted(확인 카드에 '추천'으로 표시) / needs_review(사유와 함께 표시). 어떤 경우에도 자동 등록하지 않는다.
표준 라이브러리만 사용. 실행: python3 extraction_guard.py transcript.txt roster.json extraction.json 2026-10-26
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

MIN_EVIDENCE_CHARS = 8
MAX_DUE_DAYS = 180


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _key(s: str) -> str:
    return re.sub(r"[\s\W_]+", "", (s or "").lower())


def resolve_owner(name: str | None, roster: list[dict]) -> dict | None:
    if not name:
        return None
    n = _key(name)
    hits = [p for p in roster if n in {_key(p["name"])} | {_key(a) for a in p.get("aliases", [])}]
    return hits[0] if len(hits) == 1 else None


def check(transcript: str, roster: list[dict], extraction: dict, meeting_date: date) -> dict:
    text = _norm(transcript)
    accepted = {"decisions": [], "actions": []}
    review = {"decisions": [], "actions": []}
    schema_errors: list[str] = []

    decisions = extraction.get("decisions")
    actions = extraction.get("actions")
    if not isinstance(decisions, list) or not isinstance(actions, list):
        return {"schemaErrors": ["decisions/actions 배열이 필요합니다"], "accepted": accepted, "needsReview": review}

    def evidence_ok(ev: str) -> bool:
        ev = _norm(ev)
        return len(ev) >= MIN_EVIDENCE_CHARS and ev in text

    valid_refs = set()
    for i, d in enumerate(decisions, 1):
        reasons = []
        if not isinstance(d, dict) or not d.get("text"):
            schema_errors.append(f"decision[{i}] text 누락")
            continue
        if not evidence_ok(d.get("evidence", "")):
            reasons.append("G2 근거 문장이 회의록에 없음")
        decider = d.get("decided_by")
        if decider and not resolve_owner(decider, roster):
            reasons.append("G3 결정자 명부 불일치")
        item = {"ref": i, "text": d["text"], "decided_by": decider, "evidence": d.get("evidence", "")}
        (review if reasons else accepted)["decisions"].append({**item, "reasons": reasons})
        valid_refs.add(i)

    seen = set()
    for i, a in enumerate(actions, 1):
        if not isinstance(a, dict) or not a.get("title"):
            schema_errors.append(f"action[{i}] title 누락")
            continue
        reasons = []
        k = _key(a["title"])
        if k in seen:
            continue  # G5 중복 제거(첫 항목만 유지)
        seen.add(k)
        if not evidence_ok(a.get("evidence", "")):
            reasons.append("G2 근거 문장이 회의록에 없음")
        owner = resolve_owner(a.get("owner_name"), roster)
        if not owner:
            reasons.append("G3 담당자 미확정(명부에 없거나 모호)")
        due = a.get("due_date")
        due_text = _norm(a.get("due_text") or "")
        if due:
            try:
                dd = date.fromisoformat(due)
                if dd < meeting_date or dd > meeting_date + timedelta(days=MAX_DUE_DAYS):
                    reasons.append("G4 기한 범위 이상")
                if not due_text or due_text not in text:
                    reasons.append("G4 기한 근거 표현이 회의록에 없음(추정 금지)")
            except ValueError:
                reasons.append("G4 기한 형식 오류(YYYY-MM-DD)")
        ref = a.get("decision_ref")
        if ref is not None and ref not in valid_refs:
            reasons.append("G6 존재하지 않는 결정 참조")
        item = {"ref": i, "title": a["title"], "owner_email": owner["email"] if owner else None,
                "owner_name": a.get("owner_name"), "due_date": due, "due_missing": not due,
                "decision_ref": ref, "evidence": a.get("evidence", "")}
        (review if reasons else accepted)["actions"].append({**item, "reasons": reasons})

    return {"schemaErrors": schema_errors, "accepted": accepted, "needsReview": review}


def main(argv: list[str]) -> int:
    transcript = Path(argv[1]).read_text(encoding="utf-8")
    roster = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
    extraction = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
    out = check(transcript, roster, extraction, date.fromisoformat(argv[4]))
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if not out["schemaErrors"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
