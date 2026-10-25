"""설계 감사(AUDIT_REPORT.md) P0·P1 결함 수정 검증 — 가상 데이터, 로컬 에뮬레이터.

분류: A1 멱등·중복(P0-2) / A2 기한 없는 할 일(P0-3) / A3 Office Scripts 실행 방식(P0-4)
      A4 Update item 보존(P0-5) / A5 결정 상태 구분(P0-6) / A6 A안 최소 구성 / A7 오류 처리
실행: cd prototype && python3 -m unittest -v tests/test_audit.py
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from env import ME, SCRIPTS, SITE, Env  # noqa: E402

SAMPLES = ROOT.parent / "automation_assets" / "sample_data"
OTHER = "doyun.park@example.com"
SYSTEM = {"Modified", "Editor", "{Link}"}


def runs_of(env, fid):
    return [r for r in env.rt.runs if r.flow == fid]


def notices(env):
    return [p.get("message", "") for p in env.teams.posts] + [m["subject"] for m in env.outlook.sent]


class A1_Idempotency(unittest.TestCase):
    """P0-2: 'When an email is flagged (V4)'는 이미 플래그된 메일이 바뀔 때마다 다시 실행될 수 있다."""

    def test_first_flag_creates_exactly_one_with_stable_key(self):
        e = Env()
        e.flag_email("m-1", due="2026-10-28T00:00:00")
        [a] = e.items("ActionItems")
        self.assertEqual((a["SourceKey"], a["DueDate"], a["FlagDue"]), ("imid|<m-1@mail.example.com>", "2026-10-28", "2026-10-28"))

    def test_reflag_and_other_changes_write_nothing(self):
        e = Env()
        e.flag_email("m-2")
        before = e.items("ActionItems")[0]
        for _ in range(3):  # 읽음 표시·재플래그 등 같은 메일의 변화
            r = e.flag_email("m-2")[0]
            self.assertEqual(r.terminate["code"], "NoChange")
        self.assertEqual(e.items("ActionItems"), [before])  # 수정 시각까지 그대로(쓰기 없음)

    def test_move_to_other_folder_keeps_one_item_and_updates_link(self):
        e = Env()
        e.flag_email("m-3")
        # 폴더 이동: Outlook 기본 메일 ID는 바뀌고 internetMessageId 는 그대로(공식 문서: immutable ID 문서 참조)
        e.flag_email("m-3-moved", imid="<m-3@mail.example.com>")
        [a] = e.items("ActionItems")
        self.assertEqual(a["SourceMessageId"], "m-3-moved")
        self.assertTrue(a["SourceLink"].endswith("m-3-moved"))

    def test_different_mails_same_subject_are_not_merged(self):
        e = Env()
        e.flag_email("m-4a", subject="같은 제목")
        e.flag_email("m-4b", subject="같은 제목")
        self.assertEqual(len(e.items("ActionItems")), 2)

    def test_without_internet_message_id_fingerprint_dedupes(self):
        e = Env()
        e.flag_email("m-5", imid=None)
        e.flag_email("m-5", imid=None)
        [a] = e.items("ActionItems")
        self.assertTrue(a["SourceKey"].startswith("fp|doyun.park@example.com|2026-10-25T23:00:00Z|"))

    def test_fingerprint_does_not_merge_mails_received_at_different_times(self):
        e = Env()
        e.flag_email("m-6a", imid=None, received="2026-10-25T23:00:00Z")
        e.flag_email("m-6b", imid=None, received="2026-10-25T23:05:00Z")
        self.assertEqual(len(e.items("ActionItems")), 2)

    def test_due_change_follows_flag_until_user_sets_own_due(self):
        e = Env()
        e.flag_email("m-7", due="2026-10-28T00:00:00")
        e.flag_email("m-7", due="2026-10-30T00:00:00")
        a = e.items("ActionItems")[0]
        self.assertEqual((a["DueDate"], a["FlagDue"]), ("2026-10-30", "2026-10-30"))
        e.ui_update("ActionItems", a["ID"], {"DueDate": "2026-11-05"})  # 사람이 직접 정함
        e.flag_email("m-7", due="2026-11-07T00:00:00")
        a = e.items("ActionItems")[0]
        self.assertEqual(a["DueDate"], "2026-11-05")                       # 사람 값 유지
        self.assertIn("목록 기한을 직접 정해 두어 유지함", a["SyncNote"])

    def test_reflag_after_completion_asks_instead_of_reopening(self):
        e = Env()
        e.flag_email("m-8")
        a = e.items("ActionItems")[0]
        e.ui_update("ActionItems", a["ID"], {"Status/Value": "완료"})
        e.flag_email("m-8")
        e.flag_email("m-8")  # 같은 날 다시 → 알림 1회만
        a = e.items("ActionItems")[0]
        self.assertEqual(a["Status"]["Value"], "완료")                     # 자동으로 다시 열지 않음
        self.assertIn("다시 하려면 상태를 미착수로", a["SyncNote"])
        self.assertEqual(sum("완료(또는 취소)한 할 일" in n for n in notices(e)), 1)
        self.assertEqual(len(e.items("ActionItems")), 1)

    def test_flag_completed_in_outlook_asks_before_completing(self):
        e = Env()
        e.flag_email("m-9")
        e.flag_email("m-9", flag_status="complete")
        a = e.items("ActionItems")[0]
        self.assertEqual(a["Status"]["Value"], "미착수")                   # 자동 완료하지 않음
        self.assertIn("플래그 완료", a["SyncNote"])
        self.assertTrue(any("플래그를 완료했습니다" in n for n in notices(e)))

    def test_race_that_concurrency_cannot_prevent_is_contained(self):
        # 동시성 1이 막지 못하는 겹침(재전송·흐름 재저장·다른 흐름)을 강제로 재현
        e = Env()
        e.flag_email("m-10", parallel=2, force_race=True)
        st = [i["Status"]["Value"] for i in e.items("ActionItems")]
        self.assertEqual(st, ["미착수", "취소"])                             # 삭제가 아니라 취소 + 사유
        self.assertIn("원본 항목 ID 1", e.items("ActionItems")[1]["SyncNote"])
        self.assertEqual(e.errors(), [])

    def test_retry_after_failure_does_not_duplicate(self):
        e = Env()
        e.faults.add("SharePoint", "Create item", "ActionItems", [500] * 5)
        self.assertEqual(e.flag_email("m-11")[0].status, "Failed")
        e.flag_email("m-11")  # 다음 변경 이벤트(또는 재제출)
        e.flag_email("m-11")
        self.assertEqual(len(e.items("ActionItems")), 1)

    def test_category_added_later_creates_linked_decision_and_keeps_action(self):
        e = Env()
        e.flag_email("m-12")
        e.flag_email("m-12", categories=["결정요청"])
        [a] = e.items("ActionItems")
        [d] = e.items("DecisionLog")
        self.assertEqual((a["Status"]["Value"], d["Status"]["Value"]), ("미착수", "결정요청"))
        self.assertIn("결정 레지스터에 연결 기록", a["SyncNote"])
        self.assertIn(f"할 일 ID {a['ID']}", d["SyncNote"])
        e.flag_email("m-12", categories=["결정요청"])   # 재실행 → 결정 기록도 1건 유지
        e.flag_email("m-12", categories=[])             # 범주 제거 → 아무것도 지우거나 만들지 않음
        self.assertEqual((len(e.items("ActionItems")), len(e.items("DecisionLog"))), (1, 1))

    def test_decision_only_mail_does_not_spawn_action_when_category_removed(self):
        e = Env()
        e.flag_email("m-13", categories=["결정"])
        r = e.flag_email("m-13", categories=[])[0]
        self.assertEqual(r.terminate["code"], "DecisionExists")
        self.assertEqual(e.items("ActionItems"), [])


class A2_UndatedInBrief(unittest.TestCase):
    """P0-3: 기한 없는 할 일이 아침 브리핑에서 사라지지 않는다(흐름 수준)."""

    def test_brief_flow_shows_undated_and_neglect_warning(self):
        e = Env()
        e.clock.set_kst("2026-10-05T09:00:00")
        e.ui_create("ActionItems", {"Title": "오래 방치된 일", "Owner/Claims": ME, "Status/Value": "진행중", "ActionType/Value": "실행"})
        e.clock.set_kst("2026-10-26T07:40:00")
        e.ui_create("ActionItems", {"Title": "끝난 일", "Owner/Claims": ME, "Status/Value": "완료", "ActionType/Value": "실행",
                                    "DueDate": "2026-10-20"})
        r = e.recurrence("P3P-F6")
        self.assertEqual(r.status, "Succeeded", r.actions)
        card = json.dumps(e.teams.posts[0]["card"], ensure_ascii=False)
        self.assertIn("오래 방치된 일 (기한 없음 · 등록 21일째)", card)
        self.assertIn("방치 경고 1건", card)
        self.assertNotIn("끝난 일", card)


class A3_OfficeScriptsLocation(unittest.TestCase):
    """P0-4: 개인 파일럿은 OneDrive 'Run script' 하나로 통일."""

    def test_all_script_actions_use_onedrive_run_script(self):
        found = 0
        for p in sorted((ROOT / "flows").glob("*.flow.json")):
            raw = p.read_text(encoding="utf-8")
            for op in ("Run script from SharePoint library",):
                self.assertNotIn(op, raw, p.name)
            for chunk in raw.split('"operation": "Run script"')[1:]:
                found += 1
                self.assertIn('"location": "OneDrive for Business"', chunk[:400], p.name)
        self.assertEqual(found, 6)  # F6·F7·F8·F11·F12·F13

    def test_script_missing_from_onedrive_scripts_folder_is_logged(self):
        e = Env()
        e.excel.files.pop(f"{SCRIPTS}/BuildDailyBrief.osts")
        r = e.recurrence("P3P-F6")
        self.assertEqual(r.status, "Failed")
        self.assertEqual(e.errors()[0]["FailedAction"], "Run_brief")
        self.assertIn("파일 없음", e.errors()[0]["ErrorMessage"])

    def test_run_script_rejects_path_style_script(self):
        e = Env()
        from fakes import ConnectorError
        with self.assertRaises(ConnectorError):
            e.excel.run_script(ME, "/Documents/P3/P3_AutomationHost.xlsx", f"{SCRIPTS}/BuildDailyBrief.osts", {}, operation="Run script")


class A4_UpdatePreservesFields(unittest.TestCase):
    """P0-5: 에뮬레이터 엄격 모드(입력하지 않은 열은 지워짐)에서도 자동화가 값을 잃지 않는다."""

    def _fields(self, item, skip=()):
        return {k: v for k, v in item.items() if k not in SYSTEM and k not in skip}

    def test_strict_emulator_really_clears_omitted_fields(self):
        e = Env(flows=[])
        a = e.sp.create(ME, SITE, "ActionItems", {"Title": "t", "Owner/Claims": ME, "Status/Value": "미착수",
                                                  "ActionType/Value": "실행", "Evidence": "근거", "DueDate": "2026-10-30"})
        b = e.sp.update(ME, SITE, "ActionItems", a["ID"], {"Title": "t", "Owner/Claims": ME, "Status/Value": "진행중",
                                                           "ActionType/Value": "실행"})
        self.assertEqual((b["Evidence"], b["DueDate"], b["Priority"]), (None, None, None))  # 검증 장치가 진짜로 잡는지

    def test_status_changes_through_f3_keep_every_other_field(self):
        e = Env()
        e.flag_email("p-1", due="2026-10-30T00:00:00", preview="근거 문장 원문")
        before = e.items("ActionItems")[0]
        e.ui_update("ActionItems", before["ID"], {"Priority/Value": "높음"})
        e.ui_update("ActionItems", before["ID"], {"Status/Value": "진행중"})
        e.ui_update("ActionItems", before["ID"], {"Status/Value": "완료"})
        after = e.items("ActionItems")[0]
        changed = {"Status", "PrevStatus", "CompletedAt", "Priority"}
        self.assertEqual(self._fields(after, changed), self._fields(before, changed))
        self.assertEqual((after["Priority"]["Value"], after["CompletedAt"] is not None), ("높음", True))

    def test_reminder_and_due_hint_keep_other_fields(self):
        e = Env(kst="2026-10-26T08:30:00")
        e.flag_email("p-2", subject="자료 송부 요청", preview="내일까지 부탁드립니다")
        a = e.items("ActionItems")[0]
        self.assertEqual((a["DueDate"], a["ActionID"], a["DueHintChecked"]), ("2026-10-27", "ACT-2026-00001", "Y"))
        self.assertEqual(a["FlagDue"], "2026-10-27")
        before = a
        e.recurrence("P3P-F7")
        after = e.items("ActionItems")[0]
        self.assertEqual(after["ReminderCount"], 1)
        self.assertEqual(self._fields(after, {"ReminderCount", "LastRemindedAt"}),
                         self._fields(before, {"ReminderCount", "LastRemindedAt"}))

    def test_f13_runs_only_after_numbering(self):
        e = Env()
        e.flag_email("p-3", preview="금요일까지 회신 바랍니다")
        order = [r.flow for r in e.rt.runs if r.flow in ("P3P-F3", "P3P-F13") and r.status == "Succeeded" and not r.terminate]
        self.assertEqual(order[:2], ["P3P-F3", "P3P-F13"])
        self.assertEqual(len(runs_of(e, "P3P-F13")), 1)

    def test_mutation_dropping_a_column_from_update_loses_data(self):
        # 변이: F3 Update item 에서 Evidence 를 빼면 엄격 모드에서 근거가 사라진다 → 보존 패턴이 필요함을 입증
        d = json.loads((ROOT / "flows/P3P-F3.flow.json").read_text(encoding="utf-8"))
        d["actions"]["Try"]["actions"]["Update_item"]["inputs"]["item"].pop("Evidence")
        tmp = Path(tempfile.mkdtemp()) / "P3P-F3.flow.json"
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        paths = [p for p in (ROOT / "flows").glob("P3P-*.flow.json") if p.stem.split(".")[0] != "P3P-F3"] + [tmp]
        e = Env(flow_paths=paths)
        e.flag_email("p-4", preview="중요한 근거")
        self.assertIsNone(e.items("ActionItems")[0]["Evidence"])

    def test_many_edits_stay_bounded(self):
        e = Env()
        e.flag_email("p-5")
        a = e.items("ActionItems")[0]
        for st in ("진행중", "보류", "진행중", "완료", "진행중", "완료"):
            e.ui_update("ActionItems", a["ID"], {"Status/Value": st})
        self.assertLessEqual(len(runs_of(e, "P3P-F3")), 1 + 6)  # 생성 1 + 상태 변경당 1, 자기 재실행 없음
        self.assertEqual(e.errors(), [])


class A5_DecisionStates(unittest.TestCase):
    """P0-6: 제안·결정요청·확정 구분. 자동화는 확정을 만들지 않고, 확정 시 빈 항목을 표시한다."""

    def test_confirmation_gap_tracks_missing_fields_without_loop(self):
        e = Env()
        d = e.ui_create("DecisionLog", {"Title": "11월 증량", "DecisionText": "6천 증량", "Status/Value": "제안"})
        self.assertEqual(e.items("DecisionLog")[0]["Status"]["Value"], "제안")
        e.ui_update("DecisionLog", d["ID"], {"Status/Value": "확정"})
        x = e.items("DecisionLog")[0]
        self.assertEqual((x["ConfirmationGap"], x["DecidedAt"]), ("결정권자 근거 후속조치", "2026-10-26"))
        e.ui_update("DecisionLog", d["ID"], {"Decider/Claims": ME, "Rationale": "CAPA 확인", "FollowUps": "ACT-2026-00001"})
        x = e.items("DecisionLog")[0]
        self.assertEqual(x["ConfirmationGap"], "")
        self.assertLessEqual(len(runs_of(e, "P3P-F4")), 3)
        self.assertEqual(e.errors(), [])

    def test_default_status_for_manual_entry_is_proposal(self):
        e = Env(flows=[])
        d = e.sp.create(ME, SITE, "DecisionLog", {"Title": "t", "DecisionText": "x"})
        self.assertEqual(d["Status"]["Value"], "제안")

    def test_only_approved_ai_candidates_are_registered(self):
        e = Env()
        e.ui_create("MeetingIntake", {"Title": "S&OP", "MeetingDate": "2026-10-26",
                                      "Transcript": (SAMPLES / "mock_transcript.txt").read_text(encoding="utf-8"),
                                      "ExtractionJson": (SAMPLES / "extraction_good.json").read_text(encoding="utf-8"),
                                      "Status/Value": "접수"})
        cands = e.items("ActionCandidates")
        self.assertGreater(len(cands), 1)
        self.assertEqual((e.items("ActionItems"), e.items("DecisionLog")), ([], []))   # 승인 전 등록 0
        act = next(c for c in cands if c["Kind"]["Value"] == "액션" and c["OwnerEmail"])
        e.ui_update("ActionCandidates", act["ID"], {"Status/Value": "승인"})
        self.assertEqual(len(e.items("ActionItems")), 1)
        self.assertEqual(e.items("DecisionLog"), [])
        c = next(x for x in e.items("ActionCandidates") if x["ID"] == act["ID"])
        self.assertEqual((c["Status"]["Value"], c["Evidence"]), ("등록완료", act["Evidence"]))  # 다른 열 보존

    def test_bad_extraction_is_never_registered(self):
        e = Env()
        e.ui_create("MeetingIntake", {"Title": "회의", "MeetingDate": "2026-10-26", "Transcript": "원문",
                                      "ExtractionJson": "이건 JSON이 아닙니다", "Status/Value": "접수"})
        [m] = e.items("MeetingIntake")
        self.assertEqual((m["Status"]["Value"], m["Transcript"]), ("오류", "원문"))
        self.assertEqual((e.items("ActionCandidates"), e.items("ActionItems")), ([], []))


class A6_MinimumViable(unittest.TestCase):
    """A안: ActionItems·FlowErrorLog 두 목록 + P3A-1·P3A-2 만으로 동작."""

    def env(self, **kw):
        return Env(flows=["P3A-1", "P3A-2"], channel="email", **kw)

    def test_mva_runs_without_decisionlog_or_scripts(self):
        e = self.env()
        del e.sp.lists[(SITE.lower(), "DecisionLog")]   # 1주차에는 없는 목록
        e.excel.files.clear()                           # Office Scripts 없음
        e.flag_email("v-1", categories=["결정요청"])     # 범주가 있어도 A안은 할 일로만
        e.flag_email("v-1")
        self.assertEqual(len(e.items("ActionItems")), 1)
        r = e.recurrence("P3A-2")
        self.assertEqual(r.status, "Succeeded", r.actions)
        self.assertEqual(e.errors(), [])

    def test_mva_brief_groups_overdue_soon_undated_and_excludes_done(self):
        e = self.env()
        e.clock.set_kst("2026-10-05T09:00:00")
        e.ui_create("ActionItems", {"Title": "방치 건", "Owner/Claims": ME, "Status/Value": "미착수", "ActionType/Value": "실행"})
        e.clock.set_kst("2026-10-26T07:40:00")
        for title, due, st, owner in (("초과 건", "2026-10-22", "진행중", ME), ("임박 건", "2026-10-27", "미착수", ME),
                                      ("먼 건", "2026-11-20", "미착수", ME), ("끝난 건", "2026-10-20", "완료", ME),
                                      ("남의 건", "2026-10-20", "미착수", OTHER), ("새 기한없음", None, "미착수", ME)):
            f = {"Title": title, "Owner/Claims": owner, "Status/Value": st, "ActionType/Value": "실행"}
            if due:
                f["DueDate"] = due
            e.ui_create("ActionItems", f)
        e.recurrence("P3A-2")
        [m] = e.outlook.sent
        self.assertEqual(m["to"], ME)
        self.assertEqual(m["subject"], "[오늘 할 일] 2026-10-26 · 초과 1 · 임박 1 · 기한없음 2 · 방치경고 1")
        for s in ("초과 건", "임박 건", "방치 건", "새 기한없음", "<table>"):
            self.assertIn(s, m["body"])
        for s in ("끝난 건", "남의 건", "먼 건"):
            self.assertNotIn(s, m["body"])

    def test_upgrade_from_mva_to_full_flow_has_no_duplicates(self):
        e = self.env()
        e.flag_email("v-2")
        e2_paths = sorted((ROOT / "flows").glob("P3P-*.flow.json"))
        # 같은 목록 위에서 A안 흐름을 끄고 B안(P3P-F1) 흐름을 켠다
        for f in e.rt.flows:
            f.enabled = False
        from runtime import Flow
        from env import SITE_MAP
        for p in e2_paths:
            e.rt.register(Flow(p, ME, {**SITE_MAP, "{{NOTIFY_CHANNEL}}": "email"}))
        r = e.flag_email("v-2")[0]
        self.assertEqual((r.flow, r.terminate["code"]), ("P3P-F1", "NoChange"))
        self.assertEqual(len(e.items("ActionItems")), 1)


class A8_BuildOrder(unittest.TestCase):
    """P0-1: 구축 순서가 선행 조건을 어기면 검사가 실패한다."""

    def setUp(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import dependency_matrix
        self.dm = dependency_matrix

    def test_current_order_passes(self):
        self.assertEqual(self.dm.check(self.dm.load()), [])

    def test_building_f1_in_week1_is_rejected(self):
        import copy
        orig = copy.deepcopy(self.dm.STAGES)
        try:
            self.dm.STAGES[0][1]["flows"].append("P3P-F1")
            self.dm.STAGES[1][1]["flows"].remove("P3P-F1")
            errs = "\n".join(self.dm.check(self.dm.load()))
            self.assertIn("P3P-F1 가 아직 만들지 않은 목록 DecisionLog 사용", errs)
            self.assertIn("선행 흐름 P3P-F4", errs)
        finally:
            self.dm.STAGES[:] = orig

    def test_f12_before_factoryinbox_is_rejected(self):
        import copy
        orig = copy.deepcopy(self.dm.STAGES)
        try:
            self.dm.STAGES[3][1]["flows"].remove("P3P-F12")
            self.dm.STAGES[1][1]["flows"].append("P3P-F12")
            self.dm.STAGES[1][1]["scripts"].append("BuildWeeklyDigest")
            self.assertIn("FactoryInbox", "\n".join(self.dm.check(self.dm.load())))
        finally:
            self.dm.STAGES[:] = orig


class A7_ErrorHandling(unittest.TestCase):
    def test_outlook_connection_expired_is_logged_without_content(self):
        e = Env(flows=["P3A-2"], channel="email")
        e.ui_create("ActionItems", {"Title": "기밀 단가 협상 건", "Owner/Claims": ME, "Status/Value": "미착수", "ActionType/Value": "실행"})
        e.faults.add("Office 365 Outlook", "Send an email (V2)", None, [401])
        r = e.recurrence("P3A-2")
        self.assertEqual(r.status, "Failed")
        [err] = e.errors()
        self.assertEqual(err["FailedAction"], "Send_brief")
        self.assertIn("Unauthorized", err["ErrorMessage"])
        self.assertNotIn("기밀", json.dumps(err, ensure_ascii=False))   # 업무 내용은 오류 로그에 없음
        self.assertLessEqual(len(err["ErrorMessage"]), 300)

    def test_error_log_write_failure_falls_back_to_self_email(self):
        e = Env(flows=["P3A-2"], channel="email", acl_override={"FlowErrorLog": {ME: "read"}})
        e.faults.add("SharePoint", "Get items", "ActionItems", [403])
        r = e.recurrence("P3A-2")
        self.assertEqual(r.status, "Failed")
        [m] = e.outlook.sent
        self.assertEqual(m["to"], ME)
        self.assertIn("오류 로그 기록도 실패", m["subject"])
        self.assertIn("Get_open", m["body"])

    def test_teams_workflows_app_blocked_is_distinct_from_connector_error(self):
        e = Env()
        e.teams.workflows_app_allowed = False
        e.ui_create("ActionItems", {"Title": "x", "Owner/Claims": ME, "Status/Value": "미착수", "ActionType/Value": "실행",
                                    "DueDate": "2026-10-22"})
        r = e.recurrence("P3P-F6")
        self.assertEqual(r.actions["Post_card_teams"]["error"]["code"], "WorkflowsAppBlocked")
        self.assertTrue(any("메일로 대체" in m["subject"] for m in e.outlook.sent))

    def test_every_notification_goes_to_me_only(self):
        # 생성된 모든 흐름 정의 정적 검사(L12) + 실행 중 가짜 Outlook 의 본인 외 발송 차단
        sys.path.insert(0, str(ROOT / "tools"))
        import lint_flows
        for p in sorted((ROOT / "flows").glob("*.flow.json")):
            errs = [x for x in lint_flows.lint_flow(json.loads(p.read_text(encoding="utf-8")), lint_flows.schema()) if "L12" in x]
            self.assertEqual(errs, [], p.name)


if __name__ == "__main__":
    unittest.main()
