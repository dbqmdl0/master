"""Office Scripts 단위·교차 검증 — 실제 TypeScript 스크립트를 node 로 실행해 Python 참조 구현과 결과를 비교한다."""
import json
import subprocess
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REF = ROOT.parent / "automation_assets"
sys.path.insert(0, str(REF / "python"))
import daily_brief as PB  # noqa: E402
import extraction_guard as PG  # noqa: E402

ME = "seoyeon.han@example.com"


def run(script, params):
    p = subprocess.run(["node", str(ROOT / "emulator/run_office_script.js")],
                       input=json.dumps({"script": script, "params": params}), capture_output=True, text=True, timeout=120)
    if p.returncode:
        raise RuntimeError(p.stderr)
    return json.loads(p.stdout)


def kst_to_utc_naive(s):
    return (datetime.fromisoformat(s) - timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:%S.0000000")


class CrossCheckBrief(unittest.TestCase):
    def test_same_result_as_python_reference(self):
        data = json.loads((REF / "sample_data/brief_input.json").read_text(encoding="utf-8"))
        # 기한 없는 할 일(오래됨·우선순위 높음)과 우선순위 가감을 교차 검증에 포함(P0-3)
        data["actions"] += [
            {"id": "ACT-2026-00090", "title": "포장재 대체 공급사 검토", "status": "진행중", "priority": "높음", "created": "2026-10-10"},
            {"id": "ACT-2026-00091", "title": "재고 기준표 정리", "status": "미착수", "created": "2026-10-24"},
            {"id": "ACT-2026-00092", "title": "낮은 우선 정리", "status": "미착수", "priority": "낮음", "due": data["today"]}]
        py = PB.build_brief(data)
        events = [{"subject": e["subject"], "start": kst_to_utc_naive(e["start"]), "end": kst_to_utc_naive(e["end"]),
                   "isAllDay": e.get("isAllDay", False), "organizer": ME if e.get("isOrganizer") else "x@example.com",
                   "hasAgendaLink": e.get("hasAgendaLink", False)} for e in data["events"]]
        actions = [{"ActionID": a["id"], "Title": a["title"], "DueDate": a.get("due"), "Status": {"Value": a["status"]},
                    "ActionType": {"Value": a.get("actionType", "실행")}, "Owner": {"Email": ME},
                    "Priority": {"Value": a["priority"]} if a.get("priority") else None,
                    "Created": f"{a['created']}T00:00:00Z" if a.get("created") else None} for a in data["actions"]]
        decisions = [{"DecisionID": d["id"], "Title": d["title"], "Status": {"Value": d["status"]},
                      "RequestedAt": d["requestedAt"], "Decider": {"Email": ME}} for d in data["decisions"]]
        requests = [{"RequestID": r["id"], "Title": r["title"], "slaState": r["slaState"]} for r in data["requests"]]
        r = run("BuildDailyBrief", {"meEmail": ME, "todayKst": data["today"], "eventsJson": json.dumps(events),
                                    "actionsJson": json.dumps(actions), "decisionsJson": json.dumps(decisions),
                                    "requestsJson": json.dumps(requests), "holidaysJson": "[]", "linksJson": "{}"})
        self.assertTrue(r["ok"], r)
        ts = r["result"]
        self.assertEqual([(i["kind"], i["id"], i["text"], i["score"]) for i in ts["top"]],
                         [(i["kind"], i["id"], i["text"], i["score"]) for i in py["top"]])
        c = py["counts"]
        self.assertEqual(ts["counts"], {"overdue": c["기한초과"], "dueToday": c["오늘마감"], "decisionWaiting": c["결정대기"],
                                        "slaOverdue": c["SLA초과"], "slaDueSoon": c["SLA임박"], "replyWaiting": c["회신대기"],
                                        "undated": c["기한미정"], "neglectedUndated": len(py["neglected"]), "proposalsToConfirm": 0})
        self.assertEqual([i["id"] for i in ts["undatedTop"]], [i["id"] for i in py["undatedTop"]])
        self.assertEqual([i["id"] for i in ts["neglected"]], [i["id"] for i in py["neglected"]])
        self.assertEqual(c["기한미정"], 2)
        self.assertEqual((ts["meetingCount"], ts["meetingHours"]), (py["meetingCount"], py["meetingHours"]))
        self.assertEqual(ts["focusBlocks"], [f"{a}~{b}" for a, b in py["focusBlocks"]])
        self.assertEqual(ts["organizerWithoutAgenda"], py["organizerWithoutAgenda"])
        card = json.loads(ts["cardJson"])
        self.assertEqual(card["type"], "AdaptiveCard")
        self.assertLess(len(ts["cardJson"].encode()), 28 * 1024)
        self.assertIn("<ol>", ts["htmlSummary"])


class BriefEdgeCases(unittest.TestCase):
    base = {"meEmail": ME, "eventsJson": "[]", "decisionsJson": "[]", "requestsJson": "[]", "holidaysJson": "[]", "linksJson": "{}"}

    def brief(self, today, actions, **kw):
        p = dict(self.base, todayKst=today, actionsJson=json.dumps(actions))
        p.update(kw)
        return run("BuildDailyBrief", p)

    def test_due_date_formats_both_supported(self):
        # 날짜만 열이 'YYYY-MM-DD' 또는 'KST 자정의 UTC 표현'으로 올 수 있음 → 둘 다 같은 날로 해석
        a1 = {"ActionID": "A1", "Title": "t1", "DueDate": "2026-10-26", "Status": {"Value": "미착수"}}
        a2 = {"ActionID": "A2", "Title": "t2", "DueDate": "2026-10-25T15:00:00Z", "Status": {"Value": "미착수"}}
        r = self.brief("2026-10-26", [a1, a2])["result"]
        self.assertEqual([i["kind"] for i in r["top"]], ["오늘마감", "오늘마감"])

    def test_weekend_and_holiday_skip(self):
        self.assertEqual(self.brief("2026-10-25", [])["result"]["reason"], "주말")
        r = self.brief("2026-10-09", [], holidaysJson=json.dumps([{"HolidayDate": "2026-10-08T15:00:00Z"}]))["result"]
        self.assertEqual(r["reason"], "휴무일")

    def test_undated_and_others_actions(self):
        acts = [{"ActionID": "A1", "Title": "기한없음", "Status": {"Value": "진행중"}},
                {"ActionID": "A2", "Title": "남의일", "DueDate": "2026-10-20", "Status": {"Value": "미착수"}, "Owner": {"Email": "x@example.com"}}]
        r = self.brief("2026-10-26", acts)["result"]
        # 기한 없는 할 일도 TOP5 후보(점수 30)이며 기한을 만들어 넣지 않는다. 남의 일은 제외
        self.assertEqual([(i["kind"], i["id"], i["score"]) for i in r["top"]], [("기한미정", "A1", 30)])
        self.assertEqual(r["undatedOpenActions"], 1)
        self.assertIn("기한 없는 할 일 1건", r["cardJson"])
        self.assertNotIn("2026-10", r["top"][0]["text"])

    def test_undated_priority_age_and_neglect_warning(self):
        acts = [
            {"ActionID": "U-OLD", "Title": "오래된 기한없음", "Status": {"Value": "미착수"}, "Created": "2026-10-01T01:00:00Z"},
            {"ActionID": "U-HIGH", "Title": "중요 기한없음", "Status": {"Value": "진행중"}, "Priority": {"Value": "높음"},
             "Created": "2026-10-16T01:00:00Z"},
            {"ActionID": "U-NEW", "Title": "새 기한없음", "Status": {"Value": "미착수"}, "Created": "2026-10-25T23:00:00Z"},
            {"ActionID": "D-TODAY", "Title": "오늘 마감", "DueDate": "2026-10-26", "Status": {"Value": "미착수"}},
            {"ActionID": "D-FUT", "Title": "다음 주 마감", "DueDate": "2026-11-02", "Status": {"Value": "미착수"}},
            {"ActionID": "D-DONE", "Title": "완료됨", "DueDate": "2026-10-20", "Status": {"Value": "완료"}}]
        r = self.brief("2026-10-26", acts, decisionsJson=json.dumps([{"Title": "제안1", "Status": {"Value": "제안"}}]))["result"]
        # 오래된(25일 → 30+40 상한=70), 중요(10일 → 30+20+15=65), 오늘마감 80, 새 것(0일 → 30)
        self.assertEqual([(i["id"], i["score"]) for i in r["top"]], [("D-TODAY", 80), ("U-OLD", 70), ("U-HIGH", 65), ("U-NEW", 30)])
        self.assertEqual(sorted(i["id"] for i in r["neglected"]), ["U-HIGH", "U-OLD"])  # 14일↑, 또는 높음+7일↑
        self.assertEqual(r["counts"]["proposalsToConfirm"], 1)
        self.assertIn("방치 경고 2건", r["cardJson"])
        self.assertIn("확정 대기 제안 1건", r["htmlSummary"])
        self.assertNotIn("D-FUT", [i["id"] for i in r["top"]])     # 미래 기한은 오늘 할 일 아님
        self.assertNotIn("D-DONE", [i["id"] for i in r["top"]])    # 완료 제외

    def test_large_input_card_stays_under_limit(self):
        acts = [{"ActionID": f"A{i}", "Title": "긴 제목 " * 40, "DueDate": "2026-10-20", "Status": {"Value": "미착수"}} for i in range(500)]
        r = self.brief("2026-10-26", acts)
        self.assertTrue(r["ok"])
        self.assertLess(len(r["result"]["cardJson"].encode()), 28 * 1024)

    def test_malformed_input_fails_loudly(self):
        r = run("BuildDailyBrief", dict(self.base, todayKst="2026-10-26", actionsJson="{not json"))
        self.assertFalse(r["ok"])
        self.assertIn("JSON 형식 오류", r["error"])
        r = run("BuildDailyBrief", dict(self.base, todayKst="10/26/2026", actionsJson="[]"))
        self.assertFalse(r["ok"])

    def test_missing_parameter_rejected(self):
        p = dict(self.base, todayKst="2026-10-26")
        r = run("BuildDailyBrief", p)  # actionsJson 누락
        self.assertFalse(r["ok"])
        self.assertIn("actionsJson", r["error"])


class CrossCheckGuard(unittest.TestCase):
    def compare(self, extraction_text):
        t = (REF / "sample_data/mock_transcript.txt").read_text(encoding="utf-8")
        roster = json.loads((REF / "sample_data/roster.json").read_text(encoding="utf-8"))
        py = PG.check(t, roster, json.loads(extraction_text), date(2026, 10, 26))
        r = run("GuardExtraction", {"transcript": t, "rosterJson": json.dumps(roster, ensure_ascii=False),
                                    "extractionJson": extraction_text, "meetingDate": "2026-10-26"})
        self.assertTrue(r["ok"], r)
        ts = r["result"]
        self.assertEqual(ts["schemaErrors"], py["schemaErrors"])
        expect = []
        for kind, key in (("결정", "decisions"), ("액션", "actions")):
            for bucket in ("accepted", "needsReview"):
                for it in py[bucket][key]:
                    expect.append((kind, it["ref"], "추천" if bucket == "accepted" else "검토필요", "; ".join(it["reasons"]),
                                   it.get("owner_email") or ""))
        got = [(c["kind"], c["ref"], c["verdict"], c["reasons"], c["ownerEmail"] if c["kind"] == "액션" else "") for c in ts["candidates"]]
        self.assertEqual(sorted(got), sorted(expect))
        return ts

    def test_good(self):
        ts = self.compare((REF / "sample_data/extraction_good.json").read_text(encoding="utf-8"))
        self.assertEqual((ts["recommendedCount"], ts["reviewCount"]), (4, 0))

    def test_bad(self):
        ts = self.compare((REF / "sample_data/extraction_bad.json").read_text(encoding="utf-8"))
        self.assertEqual(ts["recommendedCount"], 0)

    def test_code_fence_and_prose_wrapping(self):
        t = (REF / "sample_data/mock_transcript.txt").read_text(encoding="utf-8")
        good = (REF / "sample_data/extraction_good.json").read_text(encoding="utf-8")
        wrapped = "다음은 추출 결과입니다.\n```json\n" + good + "\n```\n확인해 주세요."
        r = run("GuardExtraction", {"transcript": t, "rosterJson": "[]", "extractionJson": wrapped, "meetingDate": "2026-10-26"})
        self.assertTrue(r["result"]["ok"])
        self.assertEqual(len(r["result"]["candidates"]), 4)
        # 명부가 비면 담당자는 모두 미확정(추측 금지)
        self.assertTrue(all(c["ownerEmail"] == "" for c in r["result"]["candidates"]))

    def test_sharepoint_roster_shape_and_aliases(self):
        t = (REF / "sample_data/mock_transcript.txt").read_text(encoding="utf-8")
        ex = json.dumps({"decisions": [], "actions": [{"title": "x", "owner_name": "PLT-A 최하은", "due_date": None,
                         "evidence": "최하은 님이 라인 2 생산계획 수정본을 10월 28일까지 공유해 주세요."}]}, ensure_ascii=False)
        roster = [{"Title": "최하은", "Email": "haeun.choi@example.com", "Aliases": "PLT-A 최하은; 하은"}]
        r = run("GuardExtraction", {"transcript": t, "rosterJson": json.dumps(roster, ensure_ascii=False),
                                    "extractionJson": ex, "meetingDate": "2026-10-26"})
        self.assertEqual(r["result"]["candidates"][0]["ownerEmail"], "haeun.choi@example.com")

    def test_input_errors(self):
        r = run("GuardExtraction", {"transcript": "", "rosterJson": "[]", "extractionJson": "{}", "meetingDate": "2026-10-26"})
        self.assertIn("비어 있습니다", r["result"]["parseError"])
        r = run("GuardExtraction", {"transcript": "x", "rosterJson": "[]", "extractionJson": "{}", "meetingDate": "26/10"})
        self.assertIn("meetingDate", r["result"]["parseError"])


class ReminderDigest(unittest.TestCase):
    def test_grouping_skip_and_escalation(self):
        acts = [
            {"ID": 1, "ActionID": "ACT-1", "Title": "초과", "DueDate": "2026-10-20", "Status": {"Value": "미착수"},
             "Owner": {"Email": "A@example.com"}, "ReminderCount": 3, "DecisionID": "DEC-9"},
            {"ID": 2, "ActionID": "ACT-2", "Title": "내일", "DueDate": "2026-10-27", "Status": {"Value": "진행중"}, "Owner": {"Email": "a@example.com"}},
            {"ID": 3, "ActionID": "ACT-3", "Title": "모레", "DueDate": "2026-10-28", "Status": {"Value": "진행중"}, "Owner": {"Email": "a@example.com"}},
            {"ID": 4, "ActionID": "ACT-4", "Title": "오늘 이미 알림", "DueDate": "2026-10-26", "Status": {"Value": "미착수"},
             "Owner": {"Email": "b@example.com"}, "LastRemindedAt": "2026-10-25T23:35:00Z"},
            {"ID": 5, "ActionID": "ACT-5", "Title": "완료", "DueDate": "2026-10-20", "Status": {"Value": "완료"}, "Owner": {"Email": "b@example.com"}},
            {"ID": 6, "ActionID": "ACT-6", "Title": "어제 알림", "DueDate": "2026-10-26", "Status": {"Value": "미착수"},
             "Owner": {"Email": "b@example.com"}, "LastRemindedAt": "2026-10-25T00:00:00Z"},
        ]
        r = run("BuildReminderDigest", {"todayKst": "2026-10-26", "actionsJson": json.dumps(acts), "holidaysJson": "[]", "viewUrl": "u"})
        res = r["result"]
        self.assertEqual([(d["ownerEmail"], d["itemIds"]) for d in res["digests"]], [("a@example.com", [1, 2]), ("b@example.com", [6])])
        self.assertEqual([(x["itemId"], x["daysOverdue"]) for x in res["escalations"]], [(1, 6)])
        card = json.loads(res["digests"][0]["cardJson"])
        self.assertEqual([f["title"] for f in card["body"][2]["facts"]], ["6일 초과", "내일 마감"])

    def test_overflow_lines(self):
        acts = [{"ID": i, "Title": f"t{i}", "DueDate": "2026-10-26", "Status": {"Value": "미착수"}, "Owner": {"Email": "a@example.com"}} for i in range(1, 16)]
        res = run("BuildReminderDigest", {"todayKst": "2026-10-26", "actionsJson": json.dumps(acts), "holidaysJson": "[]", "viewUrl": ""})["result"]
        self.assertIn("외 5건", res["digests"][0]["cardJson"])
        self.assertEqual(res["digests"][0]["itemCount"], 15)


if __name__ == "__main__":
    unittest.main()
