"""변이 테스트 — 흐름 정의를 일부러 망가뜨렸을 때 에뮬레이터·lint 가 실제로 잡아내는지 확인한다.
('테스트가 항상 통과하는 가짜 검증'이 아님을 증명)
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools"))
from env import ME, Env  # noqa: E402
import lint_flows  # noqa: E402

FLOWS = ROOT / "flows"


def mutated(fid, fn):
    d = json.loads((FLOWS / f"{fid}.flow.json").read_text(encoding="utf-8"))
    fn(d)
    tmp = Path(tempfile.mkdtemp()) / f"{fid}.flow.json"
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    others = [p for p in FLOWS.glob("*.flow.json") if p.stem.split(".")[0] != fid]
    return others + [tmp], d


class Mutations(unittest.TestCase):
    def test_removing_prevstatus_sync_causes_runaway_loop(self):
        paths, _ = mutated("P3P-F3", lambda d: d["actions"]["Try"]["actions"]["Update_item"]["inputs"]["item"].pop("PrevStatus"))
        e = Env(flow_paths=paths)
        with self.assertRaisesRegex(RuntimeError, "자기 트리거 루프"):
            e.flag_email("AAMk-x")

    def test_removing_duplicate_check_creates_duplicates(self):
        def drop(d):
            t = d["actions"]["Try"]["actions"]
            t.pop("Find_existing")
            t.pop("If_duplicate")
            t["Title_text"]["runAfter"] = {"Check_message_id": ["Succeeded"]}
        paths, _ = mutated("P3P-F2", drop)
        e = Env(flow_paths=paths)
        e.flag_email("AAMk-y", folder="Sent Items")
        e.flag_email("AAMk-y", folder="Sent Items")
        self.assertEqual(len(e.items("ActionItems")), 2)

    def test_removing_recheck_allows_double_registration(self):
        def drop(d):
            t = d["actions"]["Try"]["actions"]
            t["If_already"]["expression"] = "@equals(1, 2)"
        paths, _ = mutated("P3P-F9", drop)
        e = Env(flow_paths=paths)
        e.ui_create("MeetingIntake", {"Title": "회의", "MeetingDate": "2026-10-26",
                                      "Transcript": (ROOT.parent / "automation_assets/sample_data/mock_transcript.txt").read_text(encoding="utf-8"),
                                      "ExtractionJson": (ROOT.parent / "automation_assets/sample_data/extraction_good.json").read_text(encoding="utf-8"),
                                      "Status/Value": "접수"})
        c = [x for x in e.items("ActionCandidates") if x["Kind"]["Value"] == "액션"][0]
        site = e.rt.flows[0].d["actions"]["Config"]["inputs"]["site"]
        stale = e.sp.update(ME, site, "ActionCandidates", c["ID"], {"Status/Value": "승인"}, ui=True)
        e.sp.events.clear()
        flow = next(f for f in e.rt.flows if f.id == "P3P-F9")
        e.rt.run(flow, {"body": stale})
        e.rt.run(flow, {"body": stale})
        self.assertEqual(len(e.items("ActionItems")), 2)

    def test_lint_catches_broken_expression_missing_required_and_bad_choice(self):
        d = json.loads((FLOWS / "P3P-F2.flow.json").read_text(encoding="utf-8"))
        bad = copy.deepcopy(d)
        item = bad["actions"]["Try"]["actions"]["Create_action"]["inputs"]["item"]
        item["Title"] = "@{concat('a', outputs('Title_text')}"          # 괄호 누락
        item.pop("ActionType/Value")                                     # 필수 열 누락
        item["Status/Value"] = "대기"                                     # 없는 선택지
        item["SourceLink"] = "@{body('No_such_action')?['x']}"           # 없는 액션 참조
        errs = lint_flows.lint_flow(bad, lint_flows.schema())
        joined = "\n".join(errs)
        for code in ("L1", "L5 P3P-F2.Create_action: 필수 열 입력 누락", "선택지 아님", "No_such_action"):
            self.assertIn(code, joined)

    def test_lint_catches_script_param_mismatch_and_terminate_in_loop(self):
        d = json.loads((FLOWS / "P3P-F7.flow.json").read_text(encoding="utf-8"))
        d["actions"]["Try"]["actions"]["Run_digest"]["inputs"]["parameters"].pop("viewUrl")
        d["actions"]["Try"]["actions"]["For_each_digest"]["actions"]["Stop"] = {
            "type": "Terminate", "inputs": {"runStatus": "Failed"}, "runAfter": {}}
        errs = "\n".join(lint_flows.lint_flow(d, lint_flows.schema()))
        self.assertIn("L6", errs)
        self.assertIn("L4", errs)

    def test_removing_factory_dedupe_saves_twice(self):
        def drop(d):
            t = d["actions"]["Try"]["actions"]
            t["If_duplicate"]["expression"] = "@equals(1, 2)"
        paths, _ = mutated("P3P-F10", drop)
        e = Env(flow_paths=paths, channel="email")
        site = e.rt.flows[0].d["actions"]["Config"]["inputs"]["site"]
        e.sp.create(ME, site, "FactorySenders", {"Title": "A", "PlantCode": "PLT-A", "SenderPattern": "@plta.example.com"})
        e.sp.events.clear()
        e.new_email("dup-1", "kim@plta.example.com", attachments=["a.xlsx"])
        r = e.new_email("dup-1", "kim@plta.example.com", attachments=["a.xlsx"])
        self.assertEqual(r.status, "Failed")  # 같은 파일 이름 충돌(409)로 실패 → 중복 방지 단계가 필요함을 입증
        self.assertEqual(len(e.items("FactoryInbox")), 1)

    def test_lint_passes_all_real_flows(self):
        self.assertEqual(lint_flows.main(), 0)


if __name__ == "__main__":
    unittest.main()
