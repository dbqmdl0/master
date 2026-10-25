"""Pilot 03 프로토타입 시나리오 테스트 — 흐름 정의 JSON을 에뮬레이터로 그대로 실행한다(가상 데이터).

실행: cd prototype && python3 -m unittest -v tests/test_scenarios.py
분류: S 성공 / F 실패·장애 / D 중복 실행 / P 권한 오류 / M 데이터 누락
"""
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from env import ME, SCRIPTS, Env  # noqa: E402

SAMPLES = HERE.parent.parent / "automation_assets" / "sample_data"
TRANSCRIPT = (SAMPLES / "mock_transcript.txt").read_text(encoding="utf-8")
GOOD = (SAMPLES / "extraction_good.json").read_text(encoding="utf-8")
BAD = (SAMPLES / "extraction_bad.json").read_text(encoding="utf-8")


def last_run(env, fid):
    return [r for r in env.rt.runs if r.flow == fid][-1]


def runs_of(env, fid):
    return [r for r in env.rt.runs if r.flow == fid]


class S_Success(unittest.TestCase):
    def test_S01_flag_inbox_creates_action_and_number(self):
        e = Env()
        r = e.flag_email("AAMk-1", due="2026-10-28T00:00:00")[0]
        self.assertEqual(r.status, "Succeeded", r.actions)
        [a] = e.items("ActionItems")
        self.assertEqual(a["Title"], "[메일] 11월 증량 요청 건 확인 부탁드립니다")
        self.assertEqual(a["ActionID"], "ACT-2026-00001")         # P3P-F3 이 번호 부여
        self.assertEqual(a["PrevStatus"], "미착수")
        self.assertEqual(a["DueDate"], "2026-10-28")
        self.assertEqual(a["CreatedVia"]["Value"], "Outlook 플래그")
        self.assertEqual(len(runs_of(e, "P3P-F3")), 1)            # 자기 수정으로 재실행되지 않음
        self.assertEqual(e.errors(), [])

    def test_S02_flag_sent_items_creates_reply_waiting_with_default_due(self):
        e = Env()
        e.flag_email("AAMk-S1", subject="포장재 단가 회신 요청", folder="Sent Items")
        [a] = e.items("ActionItems")
        self.assertEqual(a["ActionType"]["Value"], "회신대기")
        self.assertTrue(a["Title"].startswith("[회신대기] "))
        self.assertEqual(a["DueDate"], "2026-10-29")              # 기본 3일 후

    def test_S03_teams_message_to_action_decision_request(self):
        e = Env()
        r1 = e.select_message("m-100", "<p>라인 2 수정본 공유 부탁</p>", "액션", "라인 2 계획 수정본 공유", "haeun.choi@example.com", "2026-10-28")
        r2 = e.select_message("m-101", "<p>11월 6천 확정</p>", "결정", "해외-1 11월 증량 6천 확정")
        r3 = e.select_message("m-102", "<p>단산 잔량 처리 결정 필요</p>", "결정요청", "SKU-MOCK-310 잔량 처리", "doyun.park@example.com")
        self.assertEqual([r1.status, r2.status, r3.status], ["Succeeded"] * 3)
        [a] = e.items("ActionItems")
        self.assertEqual((a["ActionID"], a["Owner"]["Email"], a["Evidence"]), ("ACT-2026-00001", "haeun.choi@example.com", "<p>라인 2 수정본 공유 부탁</p>"))
        d = {x["Title"]: x for x in e.items("DecisionLog")}
        # 자동화는 '확정'을 만들지 않는다(P0-6): '결정'으로 기록해도 '제안' → 사람이 목록에서 확정
        self.assertEqual(d["해외-1 11월 증량 6천 확정"]["Status"]["Value"], "제안")
        self.assertIsNone(d["해외-1 11월 증량 6천 확정"]["DecidedAt"])  # 확정 전이므로 확정일 없음
        self.assertEqual(d["SKU-MOCK-310 잔량 처리"]["Status"]["Value"], "결정요청")
        self.assertEqual(d["SKU-MOCK-310 잔량 처리"]["RequestedAt"], "2026-10-26")
        self.assertEqual(sorted(x["DecisionID"] for x in d.values()), ["DEC-2026-00001", "DEC-2026-00002"])
        self.assertIn("기록됨(액션)", e.teams.posts[0]["message"])

    def _seed_brief(self, e):
        e.ui_create("ActionItems", {"Title": "PLT-B 11월 CAPA 확인", "Owner/Claims": ME, "DueDate": "2026-10-22",
                                    "Status/Value": "진행중", "ActionType/Value": "실행"})
        e.ui_create("ActionItems", {"Title": "해외-1 이월 수량 안내", "Owner/Claims": ME, "DueDate": "2026-10-26",
                                    "Status/Value": "미착수", "ActionType/Value": "실행"})
        e.ui_create("ActionItems", {"Title": "다른 사람 일", "Owner/Claims": "doyun.park@example.com", "DueDate": "2026-10-20",
                                    "Status/Value": "미착수", "ActionType/Value": "실행"})
        e.ui_create("DecisionLog", {"Title": "단산 잔량 처리 방식", "DecisionText": "판촉 소진 vs 폐기", "Status/Value": "결정요청",
                                    "Decider/Claims": ME, "RequestedAt": "2026-10-20"})
        e.outlook.calendar[ME] = [
            {"subject": "주간 공급 조정 회의", "start": "2026-10-26T00:30:00.0000000", "end": "2026-10-26T01:30:00.0000000",
             "isAllDay": False, "organizer": ME, "body": "안건: https://contoso/agenda"},
            {"subject": "S&OP 사전 검토", "start": "2026-10-26T06:30:00.0000000", "end": "2026-10-26T07:00:00.0000000",
             "isAllDay": False, "organizer": ME, "body": ""},
        ]

    def test_S04_morning_brief_card(self):
        e = Env()
        self._seed_brief(e)
        r = e.recurrence("P3P-F6")
        self.assertEqual(r.status, "Succeeded", r.actions)
        [post] = e.teams.posts
        self.assertEqual(post["recipient"], ME)
        facts = post["card"]["body"][3]["facts"]
        self.assertEqual([f["title"] for f in facts], ["기한초과", "결정대기", "오늘마감"])
        self.assertIn("4일 초과", facts[0]["value"])
        self.assertNotIn("다른 사람 일", json.dumps(post["card"], ensure_ascii=False))
        self.assertIn("S&OP 사전 검토", json.dumps(post["card"], ensure_ascii=False))  # 안건 없는 주관 회의 경고

    def test_S05_reminder_digest_and_counts(self):
        e = Env(kst="2026-10-26T08:30:00")
        for title, due in (("초과 건", "2026-10-23"), ("오늘 건", "2026-10-26"), ("내일 건", "2026-10-27"), ("모레 건", "2026-10-28")):
            e.ui_create("ActionItems", {"Title": title, "Owner/Claims": ME, "DueDate": due, "Status/Value": "미착수",
                                        "ActionType/Value": "실행"})
        r = e.recurrence("P3P-F7")
        self.assertEqual(r.status, "Succeeded", r.actions)
        [post] = e.teams.posts
        labels = [f["title"] for f in post["card"]["body"][2]["facts"]]
        self.assertEqual(labels, ["3일 초과", "오늘 마감", "내일 마감"])
        counts = {a["Title"]: a["ReminderCount"] for a in e.items("ActionItems")}
        self.assertEqual(counts, {"초과 건": 1, "오늘 건": 1, "내일 건": 1, "모레 건": 0})
        self.assertEqual(len(runs_of(e, "P3P-F3")), 4)  # 생성 4회뿐, 리마인더 기록으로 번호 흐름이 다시 돌지 않음

    def test_S06_copilot_extraction_to_registration(self):
        e = Env()
        e.ui_create("MeetingIntake", {"Title": "주간 공급 조정 회의", "MeetingDate": "2026-10-26", "Transcript": TRANSCRIPT,
                                      "ExtractionJson": "```json\n" + GOOD + "\n```", "Status/Value": "접수"})
        intake = e.items("MeetingIntake")[0]
        self.assertEqual(intake["Status"]["Value"], "검증완료", last_run(e, "P3P-F8").actions)
        self.assertEqual((intake["RecommendedCount"], intake["ReviewCount"]), (4, 0))
        cands = e.items("ActionCandidates")
        self.assertEqual([c["Kind"]["Value"] for c in cands], ["결정", "액션", "액션", "액션"])
        self.assertTrue(all(c["Status"]["Value"] == "제안" for c in cands))
        self.assertEqual(e.items("ActionItems"), [])  # 사람이 승인하기 전에는 등록되지 않음
        for c in cands:
            e.ui_update("ActionCandidates", c["ID"], {"Status/Value": "승인"})
        self.assertEqual(sorted(c["Status"]["Value"] for c in e.items("ActionCandidates")), ["등록완료"] * 4)
        acts = e.items("ActionItems")
        self.assertEqual(len(acts), 3)
        self.assertEqual({a["Owner"]["Email"] for a in acts}, {"haeun.choi@example.com", "doyun.park@example.com", "minjae.lee@example.com"})
        self.assertTrue(all(a["ActionID"].startswith("ACT-2026-") for a in acts))
        [d] = e.items("DecisionLog")
        # AI 추출 결정은 사람이 승인해도 '제안' — 결정권자·확정일은 비움(P0-6)
        self.assertEqual((d["Status"]["Value"], d["DecisionID"], d["DecidedAt"], d["Decider"]), ("제안", "DEC-2026-00001", None, None))

    def test_S07_completed_at_set_and_cleared(self):
        e = Env()
        e.flag_email("AAMk-2")
        a = e.items("ActionItems")[0]
        e.ui_update("ActionItems", a["ID"], {"Status/Value": "완료"})
        self.assertIsNotNone(e.items("ActionItems")[0]["CompletedAt"])
        e.ui_update("ActionItems", a["ID"], {"Status/Value": "진행중"})
        a2 = e.items("ActionItems")[0]
        self.assertIsNone(a2["CompletedAt"])
        self.assertEqual(a2["PrevStatus"], "진행중")


class F_Failures(unittest.TestCase):
    def test_F01_persistent_500_retries_then_logged(self):
        e = Env()
        e.faults.add("SharePoint", "Create item", "ActionItems", [500] * 5)
        r = e.flag_email("AAMk-3", folder="Sent Items")[0]
        self.assertEqual(r.status, "Failed")
        tries = [c for c in e.rt.connector_calls if c[1] == "Create_action"]
        self.assertEqual(len(tries), 5)  # 최초 1 + 재시도 4
        [err] = e.errors()
        # 조건 안쪽 실패: 엔진은 바깥 조건 이름만 올려 준다 → 오류 로그가 위치와 확인 방법을 안내
        self.assertEqual(err["FailedAction"], "If_has_action")
        self.assertIn("안쪽 단계가 실패", err["ErrorMessage"])
        self.assertEqual(r.actions["Create_action"]["error"]["status"], 500)  # 상세는 실행 기록에 남음
        self.assertEqual(e.items("ActionItems"), [])

    def test_F02_throttling_recovers(self):
        e = Env()
        e.faults.add("SharePoint", "Create item", "ActionItems", [429, 429])
        r = e.flag_email("AAMk-4")[0]
        self.assertEqual(r.status, "Succeeded")
        self.assertEqual(len(e.items("ActionItems")), 1)
        self.assertEqual(e.errors(), [])

    def test_F03_teams_blocked_falls_back_to_email(self):
        e = Env()
        e.teams.workflows_app_allowed = False
        r = e.recurrence("P3P-F6")
        self.assertEqual(r.status, "Failed")               # 운영자가 알 수 있게 실행은 실패로 남김
        self.assertEqual(e.errors()[0]["FailedAction"], "Post_card")
        [mail] = e.outlook.sent
        self.assertEqual(mail["to"], ME)
        self.assertIn("아침 브리핑", mail["body"])

    def test_F04_outlook_connection_expired(self):
        e = Env()
        e.faults.add("Office 365 Outlook", "Get calendar view of events (V3)", None, [401])
        r = e.recurrence("P3P-F6")
        self.assertEqual(r.status, "Failed")
        self.assertEqual(e.errors()[0]["FailedAction"], "Get_events")
        self.assertEqual(len([c for c in e.rt.connector_calls if c[1] == "Get_events"]), 1)  # 401은 재시도 안 함
        self.assertEqual(e.teams.posts, [])

    def test_F05_script_error_reported(self):
        e = Env()
        e.ui_create("ActionItems", {"Title": "x", "Owner/Claims": ME, "Status/Value": "미착수", "ActionType/Value": "실행"})
        e.excel.files.pop(f"{SCRIPTS}/BuildDailyBrief.osts")
        r = e.recurrence("P3P-F6")
        self.assertEqual(r.status, "Failed")
        self.assertIn("파일 없음", e.errors()[0]["ErrorMessage"])


class D_Duplicates(unittest.TestCase):
    def test_D01_same_email_flagged_twice(self):
        e = Env()
        e.flag_email("AAMk-5")
        r = e.flag_email("AAMk-5")[0]
        # 이미 있는 메일 → 바뀐 것이 없으면 아무것도 쓰지 않고 성공 종료(P0-2 멱등 규칙)
        self.assertEqual((r.status, r.terminate["code"]), ("Succeeded", "NoChange"))
        self.assertEqual(len(e.items("ActionItems")), 1)

    def test_D02_parallel_triggers_with_concurrency_1(self):
        e = Env()
        e.flag_email("AAMk-6", parallel=3)
        self.assertEqual(len(e.items("ActionItems")), 1)

    def test_D02b_without_concurrency_limit_duplicates_appear(self):
        """동시성 1 설정이 왜 필요한지 보여주는 대조 실험: 제한을 풀면 병렬 실행이 서로를 못 보고 중복 생성."""
        e = Env()
        f1 = next(f for f in e.rt.flows if f.id == "P3P-F1")
        f1.trigger["concurrency"] = None
        e.flag_email("AAMk-7", parallel=3)
        self.assertEqual(len(e.items("ActionItems")), 3)

    def test_D03_same_teams_message_twice(self):
        e = Env()
        e.select_message("m-200", "c", "액션", "같은 메시지")
        r = e.select_message("m-200", "c", "액션", "같은 메시지")
        self.assertEqual(r.terminate["code"], "Duplicate")
        self.assertEqual(len(e.items("ActionItems")), 1)
        self.assertIn("이미 기록된", e.teams.posts[-1]["message"])

    def test_D04_stale_approval_trigger_does_not_double_register(self):
        e = Env()
        e.ui_create("MeetingIntake", {"Title": "회의", "MeetingDate": "2026-10-26", "Transcript": TRANSCRIPT,
                                      "ExtractionJson": GOOD, "Status/Value": "접수"})
        c = [x for x in e.items("ActionCandidates") if x["Kind"]["Value"] == "액션"][0]
        stale = e.sp.update(ME, e.rt.flows[0].d["actions"]["Config"]["inputs"]["site"], "ActionCandidates", c["ID"],
                            {"Status/Value": "승인"}, ui=True)
        e.sp.events.clear()
        flow = next(f for f in e.rt.flows if f.id == "P3P-F9")
        e.rt.run(flow, {"body": stale})          # 1번째 실행(정상 등록)
        e.rt.drain()
        r2 = e.rt.run(flow, {"body": stale})     # 같은 '승인' 시점 스냅샷으로 늦게 도착한 2번째 실행
        self.assertEqual(r2.terminate["code"], "AlreadyHandled")
        self.assertEqual(len(e.items("ActionItems")), 1)

    def test_D05_revalidation_supersedes_without_duplicates(self):
        e = Env()
        e.ui_create("MeetingIntake", {"Title": "회의", "MeetingDate": "2026-10-26", "Transcript": TRANSCRIPT,
                                      "ExtractionJson": GOOD, "Status/Value": "접수"})
        i = e.items("MeetingIntake")[0]
        e.ui_update("MeetingIntake", i["ID"], {"Status/Value": "재검증요청"})
        st = [c["Status"]["Value"] for c in e.items("ActionCandidates")]
        self.assertEqual(st.count("제안"), 4)
        self.assertEqual(st.count("기각"), 4)
        self.assertEqual(len(runs_of(e, "P3P-F8")), 2)

    def test_D06_reminder_twice_same_day(self):
        e = Env(kst="2026-10-26T08:30:00")
        e.ui_create("ActionItems", {"Title": "초과 건", "Owner/Claims": ME, "DueDate": "2026-10-23", "Status/Value": "미착수",
                                    "ActionType/Value": "실행"})
        e.recurrence("P3P-F7")
        e.recurrence("P3P-F7")
        self.assertEqual(len(e.teams.posts), 1)
        self.assertEqual(e.items("ActionItems")[0]["ReminderCount"], 1)


class P_Permissions(unittest.TestCase):
    def test_P01_no_edit_permission_on_list(self):
        e = Env(acl_override={"ActionItems": {ME: "read"}})
        r = e.flag_email("AAMk-8", folder="Sent Items")[0]
        self.assertEqual(r.status, "Failed")
        self.assertEqual(len([c for c in e.rt.connector_calls if c[1] == "Create_action"]), 1)  # 403은 재시도 안 함
        self.assertIn("안쪽 단계가 실패", e.errors()[0]["ErrorMessage"])
        self.assertIn("권한 없음", r.actions["Create_action"]["error"]["message"])

    def test_P02_host_workbook_not_shared(self):
        e = Env()
        e.excel.files[e.rt.flows[0].d["actions"]["Config"]["inputs"]["hostWorkbook"]] = {"someone@example.com"}
        r = e.recurrence("P3P-F6")
        self.assertEqual(r.status, "Failed")
        self.assertIn("접근 권한 없음", e.errors()[0]["ErrorMessage"])

    def test_P03_unknown_owner_in_candidate_marked_error(self):
        e = Env()
        e.ui_create("MeetingIntake", {"Title": "회의", "MeetingDate": "2026-10-26", "Transcript": TRANSCRIPT,
                                      "ExtractionJson": GOOD, "Status/Value": "접수"})
        c = [x for x in e.items("ActionCandidates") if x["Kind"]["Value"] == "액션"][0]
        e.ui_update("ActionCandidates", c["ID"], {"OwnerEmail": "nobody@example.com", "Status/Value": "승인"})
        c2 = next(x for x in e.items("ActionCandidates") if x["ID"] == c["ID"])
        self.assertEqual(c2["Status"]["Value"], "오류")
        self.assertIn("등록 실패", c2["Reasons"])
        self.assertEqual(e.items("ActionItems"), [])
        # 사용자가 이메일을 고쳐 다시 승인하면 등록된다
        e.ui_update("ActionCandidates", c["ID"], {"OwnerEmail": "haeun.choi@example.com", "Status/Value": "승인"})
        self.assertEqual(len(e.items("ActionItems")), 1)

    def test_P04_prototype_mode_sends_only_to_me(self):
        e = Env(kst="2026-10-26T08:30:00")
        for owner in (ME, "doyun.park@example.com"):
            e.ui_create("ActionItems", {"Title": f"{owner} 건", "Owner/Claims": owner, "DueDate": "2026-10-26",
                                        "Status/Value": "미착수", "ActionType/Value": "실행"})
        e.recurrence("P3P-F7")
        cards = [p for p in e.teams.posts if "card" in p]
        self.assertEqual([p["recipient"] for p in cards], [ME])
        self.assertIn("1명에게는 발송하지 않았습니다", e.teams.posts[-1]["message"])
        other = next(a for a in e.items("ActionItems") if a["Owner"]["Email"] != ME)
        self.assertEqual(other["ReminderCount"], 0)

    def test_P05_ui_user_without_access_cannot_create(self):
        e = Env()
        from fakes import ConnectorError
        with self.assertRaises(ConnectorError) as cm:
            e.ui_create("ActionItems", {"Title": "x", "Owner/Claims": ME, "Status/Value": "미착수", "ActionType/Value": "실행"},
                        user="doyun.park@example.com")
        self.assertEqual(cm.exception.status, 403)


class M_MissingData(unittest.TestCase):
    def test_M01_email_without_subject_and_due(self):
        e = Env()
        e.flag_email("AAMk-9", subject="", preview=None)
        [a] = e.items("ActionItems")
        self.assertEqual(a["Title"], "[메일] (제목 없음)")
        self.assertIsNone(a["DueDate"])

    def test_M02_email_without_id_rejected(self):
        e = Env()
        r = e.flag_email(None)[0]
        self.assertEqual(r.status, "Failed")
        self.assertEqual(r.terminate["code"], "InputMissing")
        self.assertEqual(e.items("ActionItems"), [])

    def test_M03_teams_capture_without_title(self):
        e = Env()
        r = e.select_message("m-300", "본문", "액션", "   ")
        self.assertEqual(r.terminate["code"], "InputMissing")
        self.assertEqual(e.items("ActionItems"), [])
        self.assertIn("제목", e.teams.posts[-1]["message"])

    def test_M04_copilot_prose_instead_of_json(self):
        e = Env()
        e.ui_create("MeetingIntake", {"Title": "회의", "MeetingDate": "2026-10-26", "Transcript": TRANSCRIPT,
                                      "ExtractionJson": "죄송합니다. 회의록이 너무 짧아 요약할 수 없습니다.", "Status/Value": "접수"})
        i = e.items("MeetingIntake")[0]
        self.assertEqual(i["Status"]["Value"], "오류")
        self.assertIn("JSON이 아닙니다", i["ResultSummary"])
        self.assertEqual(e.items("ActionCandidates"), [])

    def test_M05_hallucinated_extraction_flagged(self):
        e = Env()
        e.ui_create("MeetingIntake", {"Title": "회의", "MeetingDate": "2026-10-26", "Transcript": TRANSCRIPT,
                                      "ExtractionJson": BAD, "Status/Value": "접수"})
        i = e.items("MeetingIntake")[0]
        self.assertEqual((i["RecommendedCount"], i["ReviewCount"]), (0, 4))
        self.assertIn("action[4] title 누락", i["ResultSummary"])
        cands = e.items("ActionCandidates")
        self.assertTrue(all(c["Verdict"]["Value"] == "검토필요" for c in cands))
        self.assertTrue(any("G2" in c["Reasons"] for c in cands))
        self.assertTrue(all(c["OwnerEmail"] in ("", None) or c["OwnerEmail"].endswith("@example.com") for c in cands))

    def test_M06_decision_candidate_without_owner_still_registers(self):
        e = Env()
        ex = json.dumps({"decisions": [{"text": "11월 증량 6천 확정", "decided_by": None,
                                        "evidence": "11월 증량은 6천으로 확정하고 나머지 6천은 12월 첫 주로 이월하는 것으로 결정합니다."}],
                         "actions": []}, ensure_ascii=False)
        e.ui_create("MeetingIntake", {"Title": "회의", "MeetingDate": "2026-10-26", "Transcript": TRANSCRIPT,
                                      "ExtractionJson": ex, "Status/Value": "접수"})
        c = e.items("ActionCandidates")[0]
        e.ui_update("ActionCandidates", c["ID"], {"Status/Value": "승인"})
        [d] = e.items("DecisionLog")
        self.assertIsNone(d["Decider"])

    def test_M07_holiday_and_weekend_skip(self):
        e = Env(kst="2026-10-09T07:40:00")
        r = e.recurrence("P3P-F6")
        self.assertEqual((r.status, r.terminate["code"]), ("Succeeded", "Skip"))
        self.assertEqual(e.teams.posts, [])

    def test_M08_empty_day_card(self):
        e = Env()
        e.recurrence("P3P-F6")
        self.assertIn("급한 미결 항목이 없습니다", json.dumps(e.teams.posts[0]["card"], ensure_ascii=False))

    def test_M09_missing_required_field_in_ui(self):
        e = Env()
        from fakes import ConnectorError
        with self.assertRaises(ConnectorError) as cm:
            e.ui_create("MeetingIntake", {"Title": "회의", "MeetingDate": "2026-10-26", "Transcript": TRANSCRIPT})
        self.assertEqual(cm.exception.code, "RequiredFieldMissing")


class Z_NoRunaway(unittest.TestCase):
    def test_Z01_full_day_has_no_self_trigger_loops(self):
        """하루 전체 흐름을 돌려도 에뮬레이터의 루프 감지(200회)에 걸리지 않고 오류 로그가 비어 있다."""
        e = Env()
        S_Success._seed_brief(None, e)
        e.flag_email("AAMk-10")
        e.select_message("m-400", "c", "결정요청", "결정 필요 건", ME)
        e.ui_create("MeetingIntake", {"Title": "회의", "MeetingDate": "2026-10-26", "Transcript": TRANSCRIPT,
                                      "ExtractionJson": GOOD, "Status/Value": "접수"})
        for c in e.items("ActionCandidates"):
            e.ui_update("ActionCandidates", c["ID"], {"Status/Value": "승인"})
        e.recurrence("P3P-F6")
        e.clock.set_kst("2026-10-26T08:30:00")
        e.recurrence("P3P-F7")
        self.assertEqual(e.errors(), [])
        self.assertTrue(all(r.status == "Succeeded" for r in e.rt.runs), [(r.flow, r.status, r.actions) for r in e.rt.runs if r.status != "Succeeded"])


if __name__ == "__main__":
    unittest.main()
