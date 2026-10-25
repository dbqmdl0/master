"""추가 기능 테스트(2026-10-26): F10 공장 자료 자동 저장 · F11 회의 준비 · F12 주간 정리 · F13 기한 자동 제안
메일 알림 모드(channel=email, Teams Workflows 앱 없음)를 기본으로 검증한다. 가상 데이터만 사용.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from env import ME, Env  # noqa: E402

DOYUN, HAEUN = "doyun.park@example.com", "haeun.choi@example.com"


def run(script, params):
    p = subprocess.run(["node", str(ROOT / "emulator/run_office_script.js")],
                       input=json.dumps({"script": script, "params": params}), capture_output=True, text=True, timeout=120)
    return json.loads(p.stdout)


def hint(text, received="2026-10-26", holidays="[]"):
    r = run("ParseDueHint", {"text": text, "receivedKst": received, "holidaysJson": holidays})
    assert r["ok"], r
    return r["result"]


def env(**kw):
    e = Env(channel="email", **kw)
    e.teams.workflows_app_allowed = False
    for name, code, pat in (("A공장", "PLT-A", "@plta.example.com"), ("해외-1", "OVS-1", "planner@ovs1.example.com")):
        e.sp.create(ME, e.rt.flows[0].d["actions"]["Config"]["inputs"]["site"], "FactorySenders",
                    {"Title": name, "PlantCode": code, "SenderPattern": pat})
    e.sp.events.clear()
    return e


class DueHintScript(unittest.TestCase):
    """2026-10-26 = 월요일"""
    def test_relative_words(self):
        self.assertEqual(hint("오늘 중으로 회신 부탁")["dueDate"], "2026-10-26")
        self.assertEqual(hint("내일까지 자료 부탁드립니다")["dueDate"], "2026-10-27")
        self.assertEqual(hint("모레까지")["dueDate"], "2026-10-28")
        self.assertEqual(hint("이번 주 중 확인")["dueDate"], "2026-10-30")
        self.assertEqual(hint("다음 주까지 검토")["dueDate"], "2026-11-06")
        self.assertEqual(hint("금요일까지 공유")["dueDate"], "2026-10-30")
        self.assertEqual(hint("월요일까지")["dueDate"], "2026-10-26")  # 오늘이 월요일

    def test_explicit_dates_need_deadline_marker(self):
        self.assertEqual(hint("10/30까지 회신")["dueDate"], "2026-10-30")
        self.assertEqual(hint("11월 3일(화) 마감")["dueDate"], "2026-11-03")
        self.assertEqual(hint("10/28 회의에서 논의")["dueDate"], "")      # 기한 표지 없음 → 기한 아님
        self.assertEqual(hint("11월 증량 1.2만 가능 여부")["dueDate"], "")  # 수량·월 표현은 무시

    def test_year_rollover_and_earliest(self):
        self.assertEqual(hint("1/5까지 확정", received="2026-12-20")["dueDate"], "2027-01-05")
        r = hint("다음 주까지 초안, 내일까지 1차 의견")
        self.assertEqual((r["dueDate"], r["phrase"]), ("2026-10-27", "내일까지"))

    def test_business_days_and_holidays(self):
        self.assertEqual(hint("내일까지", received="2026-10-30")["dueDate"], "2026-11-02")  # 금 → 월
        hol = json.dumps([{"HolidayDate": "2026-10-27"}])
        self.assertEqual(hint("내일까지", holidays=hol)["dueDate"], "2026-10-28")

    def test_priority_and_none(self):
        self.assertEqual(hint("[긴급] 선적 지연 확인")["priority"], "높음")
        r = hint("참고 자료 송부드립니다")
        self.assertEqual((r["dueDate"], r["rule"], r["priority"]), ("", "none", ""))

    def test_past_explicit_date_ignored(self):
        self.assertEqual(hint("10/20까지 회신 요청(지난 건)")["dueDate"], "")


class F13_DueHintFlow(unittest.TestCase):
    def test_flagged_mail_gets_due_and_reason(self):
        e = env()
        e.flag_email("m-h1", subject="[긴급] PLT-B 11월 CAPA 확인 요청", preview="내일까지 회신 부탁드립니다")
        [a] = e.items("ActionItems")
        self.assertEqual(a["DueDate"], "2026-10-27")
        self.assertEqual(a["Priority"]["Value"], "높음")
        self.assertIn("내일까지", a["DueHint"])
        self.assertEqual(a["DueHintChecked"], "Y")
        self.assertEqual(a["ActionID"], "ACT-2026-00001")
        self.assertEqual(e.errors(), [])

    def test_no_phrase_marks_checked_without_due(self):
        e = env()
        e.flag_email("m-h2", subject="참고 자료", preview="첨부 참고 바랍니다")
        [a] = e.items("ActionItems")
        self.assertIsNone(a["DueDate"])
        self.assertIn("근거 없음", a["DueHint"])

    def test_flag_due_date_wins_and_manual_items_untouched(self):
        e = env()
        e.flag_email("m-h3", subject="내일까지 회신", due="2026-11-10T00:00:00")
        e.ui_create("ActionItems", {"Title": "내일까지 할 일(수동)", "Owner/Claims": ME, "Status/Value": "미착수", "ActionType/Value": "실행"})
        rows = {x["Title"]: x for x in e.items("ActionItems")}
        self.assertEqual(rows["[메일] 내일까지 회신"]["DueDate"], "2026-11-10")
        self.assertIsNone(rows["내일까지 할 일(수동)"]["DueDate"])
        self.assertFalse(any(r.flow == "P3P-F13" and r.status != "Succeeded" for r in e.rt.runs))

    def test_script_failure_logged_item_kept(self):
        e = env()
        e.excel.files.pop("/personal/seoyeon_han/Documents/P3/Scripts/ParseDueHint.osts")
        e.flag_email("m-h4", subject="내일까지 회신")
        [a] = e.items("ActionItems")              # 할 일 자체는 등록됨(F1은 스크립트에 의존하지 않음)
        self.assertIsNone(a["DueDate"])
        self.assertTrue(any(x["FailedAction"] == "Run_hint" for x in e.errors()))


class F10_FactoryInbox(unittest.TestCase):
    def test_saves_excel_attachments_and_logs(self):
        e = env()
        r = e.new_email("f-1", "kim@plta.example.com", attachments=["주간실적.xlsx", "계획.CSV", "설명.pdf"])
        self.assertEqual(r.status, "Succeeded", r.actions)
        # endsWith 는 대소문자를 구분하지 않으므로 '.CSV'도 저장, PDF는 제외
        self.assertEqual(sorted(e.onedrive.files), ["/SCM_수신/PLT-A/2026-10-26/1010_계획.CSV",
                                                    "/SCM_수신/PLT-A/2026-10-26/1010_주간실적.xlsx"])
        [row] = e.items("FactoryInbox")
        self.assertEqual((row["PlantCode"], row["FileCount"]), ("PLT-A", 2))
        self.assertEqual(row["FileNames"], "주간실적.xlsx, 계획.CSV")

    def test_csv_and_overseas_sender(self):
        e = env()
        e.new_email("f-2", "Planner@OVS1.example.com", subject="11월 출하계획", attachments=["plan.csv", "plan_v2.xlsx"])
        self.assertEqual(len(e.onedrive.files), 2)
        self.assertEqual(e.items("FactoryInbox")[0]["PlantCode"], "OVS-1")

    def test_non_factory_and_no_excel_ignored(self):
        e = env()
        r1 = e.new_email("f-3", "sales@other.example.com", attachments=["a.xlsx"])
        r2 = e.new_email("f-4", "kim@plta.example.com", attachments=["사진.jpg"])
        self.assertEqual((r1.terminate["code"], r2.terminate["code"]), ("NotFactory", "NoExcel"))
        self.assertEqual((e.items("FactoryInbox"), e.onedrive.files), ([], {}))

    def test_duplicate_mail_not_saved_twice(self):
        e = env()
        e.new_email("f-5", "kim@plta.example.com", attachments=["a.xlsx"])
        r = e.new_email("f-5", "kim@plta.example.com", attachments=["a.xlsx"])
        self.assertEqual(r.terminate["code"], "Duplicate")
        self.assertEqual(len(e.items("FactoryInbox")), 1)

    def test_onedrive_failure_logged_no_ledger_row(self):
        e = env()
        e.faults.add("OneDrive for Business", "Create file", None, [500] * 5)
        r = e.new_email("f-6", "kim@plta.example.com", attachments=["a.xlsx"])
        self.assertEqual(r.status, "Failed")
        self.assertEqual(e.items("FactoryInbox"), [])
        self.assertEqual(e.errors()[0]["FailedAction"], "Save_files")


class F11_MeetingPrep(unittest.TestCase):
    def seed(self, e):
        site = e.rt.flows[0].d["actions"]["Config"]["inputs"]["site"]
        for title, owner, due in (("라인2 계획 수정본", HAEUN, "2026-10-23"), ("이월 수량 안내", DOYUN, "2026-10-30"),
                                  ("무관한 일", "minjae.lee@example.com", "2026-10-20")):
            e.ui_create("ActionItems", {"Title": title, "Owner/Claims": owner, "DueDate": due, "Status/Value": "미착수",
                                        "ActionType/Value": "실행"})
        e.ui_create("DecisionLog", {"Title": "단산 잔량 처리", "DecisionText": "x", "Status/Value": "결정요청",
                                    "Decider/Claims": DOYUN, "RequestedAt": "2026-10-20"})
        e.outlook.calendar[ME] = [
            {"subject": "주간 공급 조정", "start": "2026-10-27T00:30:00.0000000", "end": "2026-10-27T01:30:00.0000000",
             "organizer": ME, "requiredAttendees": f"{DOYUN};{HAEUN};", "optionalAttendees": "", "body": ""},
            {"subject": "취소된 회의", "start": "2026-10-27T05:00:00.0000000", "end": "2026-10-27T06:00:00.0000000",
             "organizer": DOYUN, "isCancelled": True, "requiredAttendees": ME},
        ]
        return site

    def test_prep_mail_contents(self):
        e = env(kst="2026-10-26T16:30:00")
        self.seed(e)
        r = e.recurrence("P3P-F11")
        self.assertEqual(r.status, "Succeeded", r.actions)
        [m] = e.outlook.sent
        self.assertEqual(m["subject"], "[회의 준비] 2026-10-27 · 1건")
        b = m["body"]
        for s in ("주간 공급 조정", "라인2 계획 수정본", "4일 초과", "이월 수량 안내", "단산 잔량 처리", "결정요청 1건 결정", "안건·자료 링크가 없습니다"):
            self.assertIn(s, b)
        self.assertNotIn("무관한 일", b)
        self.assertNotIn("취소된 회의", b)

    def test_friday_prepares_monday_and_skips_empty(self):
        e = env(kst="2026-10-30T16:30:00")
        e.outlook.calendar[ME] = [{"subject": "월요 회의", "start": "2026-11-02T00:00:00.0000000",
                                   "end": "2026-11-02T01:00:00.0000000", "organizer": DOYUN, "requiredAttendees": ME}]
        e.recurrence("P3P-F11")
        self.assertEqual(e.outlook.sent[0]["subject"], "[회의 준비] 2026-11-02 · 1건")
        e2 = env(kst="2026-10-26T16:30:00")
        r = e2.recurrence("P3P-F11")
        self.assertEqual((r.terminate["code"], e2.outlook.sent), ("Skip", []))


class F12_WeeklyDigest(unittest.TestCase):
    def test_weekly_digest(self):
        e = env(kst="2026-10-26T09:00:00")
        e.flag_email("w-1", subject="완료할 일")
        e.flag_email("w-2", subject="10/28까지 회신 요청")
        e.new_email("f-w1", "kim@plta.example.com", attachments=["a.xlsx", "b.xlsx"])
        e.ui_create("DecisionLog", {"Title": "동결 구간 2주 유지", "DecisionText": "x", "Status/Value": "확정", "Decider/Claims": ME})
        e.ui_create("DecisionLog", {"Title": "잔량 처리", "DecisionText": "x", "Status/Value": "결정요청", "Decider/Claims": ME})
        a = next(x for x in e.items("ActionItems") if x["Title"] == "[메일] 완료할 일")
        e.ui_update("ActionItems", a["ID"], {"Status/Value": "완료"})
        e.clock.set_kst("2026-10-30T16:00:00")
        e.new_email("f-w2", "planner@ovs1.example.com", attachments=["c.csv"], received="2026-10-30T02:00:00Z")
        r = e.recurrence("P3P-F12")
        self.assertEqual(r.status, "Succeeded", r.actions)
        m = e.outlook.sent[-1]
        self.assertEqual(m["subject"], "[주간 정리] 2026-W44 초안")
        b = m["body"]
        for s in ("완료 1", "신규 2", "기한초과 1", "확정 결정 1", "결정 대기 1", "PLT-A: 메일 1 · 파일 2", "OVS-1: 메일 1 · 파일 1",
                  "월 1", "금 1", "10/28까지 회신 요청"):
            self.assertIn(s, b)


class Z_AllTogether(unittest.TestCase):
    def test_full_day_with_extensions_no_loops_no_errors(self):
        e = env(kst="2026-10-26T07:40:00")
        e.flag_email("z-1", subject="[긴급] 내일까지 회신")
        e.flag_email("z-2", subject="결정 공유", categories=["결정"])
        e.new_email("z-f", "kim@plta.example.com", attachments=["a.xlsx"])
        e.recurrence("P3P-F6")
        e.clock.set_kst("2026-10-26T08:30:00")
        e.recurrence("P3P-F7")
        e.clock.set_kst("2026-10-26T16:30:00")
        e.recurrence("P3P-F11")
        self.assertEqual(e.errors(), [])
        bad = [(r.flow, r.status, r.terminate) for r in e.rt.runs if r.status != "Succeeded"]
        self.assertEqual(bad, [])
        self.assertEqual(e.teams.posts, [])
        self.assertTrue(all(m["to"] == ME for m in e.outlook.sent))


if __name__ == "__main__":
    unittest.main()
