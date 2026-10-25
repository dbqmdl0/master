"""Teams Workflows 앱이 없는 환경(사용자 테넌트 점검 결과, 2026-10-26) 대응 테스트.
설정 channel=email: 모든 알림을 본인 메일로. Teams 메시지 기록(F5) 대신 Outlook 범주 + 플래그로 결정 기록(F1).
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from env import ME, Env  # noqa: E402

SAMPLES = HERE.parent.parent / "automation_assets" / "sample_data"


def email_env(**kw):
    e = Env(channel="email", **kw)
    e.teams.workflows_app_allowed = False  # 실제 상황 재현: Teams Flow bot 사용 불가
    return e


class EmailChannel(unittest.TestCase):
    def test_E01_brief_by_email_without_teams(self):
        e = email_env()
        e.ui_create("ActionItems", {"Title": "PLT-B 11월 CAPA 확인", "Owner/Claims": ME, "DueDate": "2026-10-22",
                                    "Status/Value": "진행중", "ActionType/Value": "실행"})
        r = e.recurrence("P3P-F6")
        self.assertEqual(r.status, "Succeeded", r.actions)
        self.assertEqual(e.teams.posts, [])
        [m] = e.outlook.sent
        self.assertEqual((m["to"], m["subject"]), (ME, "[아침 브리핑] 2026-10-26"))
        self.assertIn("PLT-B 11월 CAPA 확인", m["body"])
        self.assertEqual(e.errors(), [])
        self.assertFalse(any(c[2].startswith("Post ") for c in e.rt.connector_calls))  # Teams 호출 자체가 없음

    def test_E02_reminder_by_email_and_skip_notice(self):
        e = email_env(kst="2026-10-26T08:30:00")
        for owner in (ME, "doyun.park@example.com"):
            e.ui_create("ActionItems", {"Title": f"{owner} 건", "Owner/Claims": owner, "DueDate": "2026-10-26",
                                        "Status/Value": "미착수", "ActionType/Value": "실행"})
        r = e.recurrence("P3P-F7")
        self.assertEqual(r.status, "Succeeded", r.actions)
        subjects = [m["subject"] for m in e.outlook.sent]
        self.assertEqual(subjects, ["[액션 리마인더] 2026-10-26", "[P3 알림]"])
        self.assertIn("오늘 마감", e.outlook.sent[0]["body"])
        self.assertIn("1명에게는 발송하지 않았습니다", e.outlook.sent[1]["body"])
        self.assertTrue(all(m["to"] == ME for m in e.outlook.sent))

    def test_E03_copilot_candidates_notice_by_email(self):
        e = email_env()
        e.ui_create("MeetingIntake", {"Title": "주간 공급 조정 회의", "MeetingDate": "2026-10-26",
                                      "Transcript": (SAMPLES / "mock_transcript.txt").read_text(encoding="utf-8"),
                                      "ExtractionJson": (SAMPLES / "extraction_good.json").read_text(encoding="utf-8"),
                                      "Status/Value": "접수"})
        self.assertEqual(len(e.items("ActionCandidates")), 4)
        [m] = e.outlook.sent
        self.assertIn("후보 4건", m["body"])

    def test_E04_teams_channel_but_blocked_falls_back_once(self):
        e = Env(channel="teams")
        e.teams.workflows_app_allowed = False
        r = e.recurrence("P3P-F6")
        self.assertEqual(r.status, "Failed")
        self.assertEqual(len(e.outlook.sent), 1)
        self.assertEqual(e.errors()[0]["FailedAction"], "Post_card")

    def test_E05_email_failure_does_not_trigger_teams_fallback(self):
        e = email_env()
        e.faults.add("Office 365 Outlook", "Send an email (V2)", None, [403])
        r = e.recurrence("P3P-F6")
        self.assertEqual(r.status, "Failed")
        self.assertEqual(e.outlook.sent, [])
        self.assertEqual(len(e.errors()), 1)


class CategoryRouting(unittest.TestCase):
    def test_C01_categories_route_to_decision_log(self):
        e = email_env()
        e.flag_email("AAMk-d1", subject="해외-1 11월 증량 6천 확정", preview="6천 확정, 6천 이월", categories=["결정"])
        e.flag_email("AAMk-d2", subject="SKU-MOCK-310 잔량 처리 결정 부탁", preview="판촉 소진 vs 폐기", categories=["결정요청", "공장자료"])
        e.flag_email("AAMk-a1", subject="라인 2 계획 수정본 공유 요청", categories=["공장자료"])
        d = {x["Title"]: x for x in e.items("DecisionLog")}
        self.assertEqual(d["해외-1 11월 증량 6천 확정"]["Status"]["Value"], "확정")
        self.assertEqual(d["해외-1 11월 증량 6천 확정"]["DecidedAt"], "2026-10-26")
        self.assertEqual(d["SKU-MOCK-310 잔량 처리 결정 부탁"]["Status"]["Value"], "결정요청")
        self.assertEqual(d["SKU-MOCK-310 잔량 처리 결정 부탁"]["RequestedAt"], "2026-10-26")
        self.assertTrue(all(x["DecisionID"].startswith("DEC-2026-") for x in d.values()))
        [a] = e.items("ActionItems")
        self.assertEqual(a["Title"], "[메일] 라인 2 계획 수정본 공유 요청")

    def test_C02_reflag_decision_mail_no_duplicate(self):
        e = email_env()
        e.flag_email("AAMk-d3", subject="결정 건", categories=["결정"])
        r = e.flag_email("AAMk-d3", subject="결정 건", categories=["결정"])[0]
        self.assertEqual(r.terminate["code"], "Duplicate")
        self.assertEqual(len(e.items("DecisionLog")), 1)
        self.assertEqual(e.items("ActionItems"), [])

    def test_C03_nested_failure_is_logged(self):
        e = email_env(acl_override={"DecisionLog": {ME: "read"}})
        r = e.flag_email("AAMk-d4", subject="결정 건", categories=["결정"])[0]
        self.assertEqual(r.status, "Failed")
        [err] = e.errors()
        self.assertEqual(err["FailedAction"], "If_action")      # 실제 엔진처럼 범위의 최상위 액션 이름
        self.assertIn("/runs/", err["RunUrl"])                  # 상세는 실행 기록 링크로


if __name__ == "__main__":
    unittest.main()
