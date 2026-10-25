"""Pilot 03 테스트(모의 데이터). 실행: python3 -m unittest -v python/test_pilot03.py"""
import json
import sys
import unittest
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import daily_brief as B  # noqa: E402
import extraction_guard as G  # noqa: E402

SD = HERE.parent / "sample_data"
load = lambda n: json.loads((SD / n).read_text(encoding="utf-8"))  # noqa: E731


class TestBrief(unittest.TestCase):
    def setUp(self):
        self.data = load("brief_input.json")
        self.brief = B.build_brief(self.data)

    def test_priority_order(self):
        kinds = [i["kind"] for i in self.brief["top"]]
        self.assertEqual(kinds, ["기한초과", "SLA초과", "결정대기", "오늘마감", "SLA임박"])
        self.assertEqual(self.brief["top"][0]["id"], "ACT-2026-00012")

    def test_closed_and_future_items_excluded(self):
        ids = {i["id"] for i in B.score_items(self.data, date(2026, 10, 26))}
        self.assertNotIn("ACT-2026-00009", ids)  # 완료
        self.assertNotIn("ACT-2026-00020", ids)  # 미래 기한
        self.assertNotIn("DEC-2026-00033", ids)  # 확정
        self.assertNotIn("REQ-2026-00110", ids)  # SLA ok
        self.assertIn("ACT-2026-00016", ids)     # 회신대기

    def test_calendar(self):
        self.assertEqual(self.brief["meetingCount"], 3)  # 종일 일정 제외
        self.assertEqual(self.brief["meetingHours"], 2.5)
        self.assertEqual(self.brief["focusBlocks"], [("10:30", "13:00"), ("14:00", "15:30"), ("16:00", "18:00")])
        self.assertEqual(self.brief["organizerWithoutAgenda"], ["S&OP 사전 검토"])

    def test_card_valid_and_small(self):
        card = B.to_card(self.brief)
        raw = json.dumps(card, ensure_ascii=False)
        self.assertLess(len(raw.encode("utf-8")), B.CARD_LIMIT_BYTES)
        self.assertEqual(card["version"], "1.4")

    def test_empty_day(self):
        card = B.to_card(B.build_brief({"today": "2026-10-26"}))
        self.assertIn("급한 미결 항목이 없습니다", json.dumps(card, ensure_ascii=False))


class TestGuard(unittest.TestCase):
    def setUp(self):
        self.t = (SD / "mock_transcript.txt").read_text(encoding="utf-8")
        self.roster = load("roster.json")
        self.md = date(2026, 10, 26)

    def test_good_extraction_all_accepted(self):
        r = G.check(self.t, self.roster, load("extraction_good.json"), self.md)
        self.assertEqual(r["schemaErrors"], [])
        self.assertEqual(len(r["accepted"]["decisions"]), 1)
        self.assertEqual(len(r["accepted"]["actions"]), 3)
        self.assertEqual(r["needsReview"], {"decisions": [], "actions": []})
        a = r["accepted"]["actions"]
        self.assertEqual(a[0]["owner_email"], "haeun.choi@example.com")
        self.assertTrue(a[2]["due_missing"])  # 기한 미정은 사람이 정함

    def test_bad_extraction_flagged(self):
        r = G.check(self.t, self.roster, load("extraction_bad.json"), self.md)
        self.assertEqual(r["schemaErrors"], ["action[4] title 누락"])
        self.assertEqual(r["accepted"], {"decisions": [], "actions": []})
        rd = r["needsReview"]["decisions"]
        self.assertIn("G2 근거 문장이 회의록에 없음", rd[0]["reasons"])  # 지어낸 결정
        self.assertIn("G3 결정자 명부 불일치", rd[1]["reasons"])
        ra = r["needsReview"]["actions"]
        self.assertEqual(len(ra), 2)  # 중복 1건 제거
        self.assertIn("G4 기한 근거 표현이 회의록에 없음(추정 금지)", ra[0]["reasons"])
        self.assertTrue({"G2 근거 문장이 회의록에 없음", "G3 담당자 미확정(명부에 없거나 모호)",
                         "G4 기한 범위 이상", "G6 존재하지 않는 결정 참조"} <= set(ra[1]["reasons"]))
        self.assertIsNone(ra[1]["owner_email"])  # 이메일을 지어내지 않음

    def test_evidence_whitespace_normalized(self):
        ex = {"decisions": [], "actions": [{"title": "x", "owner_name": "박도윤", "due_date": None,
              "evidence": "현지 법인에   이월 수량을\n안내해 주시고요."}]}
        r = G.check(self.t, self.roster, ex, self.md)
        self.assertEqual(len(r["accepted"]["actions"]), 1)

    def test_ambiguous_owner(self):
        roster = self.roster + [{"name": "최하은", "email": "other@example.com"}]
        self.assertIsNone(G.resolve_owner("최하은", roster))

    def test_not_arrays(self):
        self.assertTrue(G.check(self.t, self.roster, {"decisions": {}}, self.md)["schemaErrors"])


if __name__ == "__main__":
    unittest.main()
