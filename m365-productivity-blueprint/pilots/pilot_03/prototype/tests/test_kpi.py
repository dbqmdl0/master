"""KPI 보고서 테스트 — 에뮬레이터로 만든 가상 운영 데이터를 Lists CSV 내보내기 형식(표시 이름 머리글)으로 저장 후 계산."""
import csv
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
import kpi_report  # noqa: E402

SAMPLES = ROOT.parent / "automation_assets" / "sample_data"


def export(env, lst, folder):
    cols = {c["internalName"]: c["displayName"] for c in kpi_report.SCHEMA[lst]["columns"]}
    rows = env.items(lst)
    with (folder / f"{lst}.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(list(cols.values()))
        for r in rows:
            def val(v):
                if isinstance(v, dict):
                    return v.get("Value") or v.get("Email") or ""
                return "" if v is None else v
            w.writerow([val(r.get(k)) for k in cols])


class KpiTest(unittest.TestCase):
    def test_model_totals(self):
        m = kpi_report.model(write=False)
        # 순절감 = 총절감 196.8 − 추가 관리 16.8 − 유지 15 − 오류 복구 12 (모두 가정)
        self.assertEqual((m["base"], m["mgmt"], m["net"], m["conditional"]), (196.8, 16.8, 153.0, 44.0))
        self.assertEqual((m["a_gross"], m["a_net"]), (53.6, 32.8))

    def test_report_from_emulated_month(self):
        e = Env()
        e.flag_email("AAMk-a", due="2026-10-20T00:00:00")
        e.flag_email("AAMk-b")
        e.ui_create("ActionItems", {"Title": "수동 건", "Owner/Claims": ME, "DueDate": "2026-10-30", "Status/Value": "미착수",
                                    "ActionType/Value": "실행"})
        e.ui_create("MeetingIntake", {"Title": "회의", "MeetingDate": "2026-10-26",
                                      "Transcript": (SAMPLES / "mock_transcript.txt").read_text(encoding="utf-8"),
                                      "ExtractionJson": (SAMPLES / "extraction_good.json").read_text(encoding="utf-8"),
                                      "Status/Value": "접수"})
        cands = e.items("ActionCandidates")
        for c in cands[:3]:
            e.ui_update("ActionCandidates", c["ID"], {"Status/Value": "승인"})
        e.ui_update("ActionCandidates", cands[3]["ID"], {"Status/Value": "기각"})
        manual = next(a for a in e.items("ActionItems") if a["Title"] == "수동 건")
        e.ui_update("ActionItems", manual["ID"], {"Status/Value": "완료"})
        e.ui_create("DecisionLog", {"Title": "대기 건", "DecisionText": "x", "Status/Value": "결정요청", "RequestedAt": "2026-10-20"})
        tmp = Path(tempfile.mkdtemp())
        for lst in ("ActionItems", "DecisionLog", "ActionCandidates"):
            export(e, lst, tmp)
        log = tmp / "timelog.csv"
        with log.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["날짜", "구분", "업무", "소요분", "비고"])
            for d in range(1, 6):
                w.writerow([f"2026-10-0{d}", "기준선", "아침 업무 파악", 20, ""])
                w.writerow([f"2026-10-1{d}", "적용후", "아침 업무 파악", 9, ""])
            w.writerow(["2026-10-01", "기준선", "주간보고 작성", 30, ""])
            for d in range(1, 6):
                w.writerow([f"2026-10-1{d}", "적용후", "추가 관리(자동화)", 2, ""])
            w.writerow(["2026-10-12", "적용후", "오류 복구", 5, ""])
        rep = kpi_report.report(tmp, kpi_report.date(2026, 10, 26), log)
        self.assertIn("액션 총 5건, 자동·반자동 등록 비율 80% (4/5)", rep)
        self.assertIn("기한 초과율: 33% (1/3)", rep)          # 플래그 기한 10/20 건만 초과
        self.assertIn("기한 내 완료율: 100% (1/1)", rep)
        self.assertIn("'추천' 후보 채택률(정밀도 대용): 75% (3/4)", rep)
        self.assertIn("현재 결정 대기 1건, 최장 6일", rep)
        self.assertIn("| 아침 업무 파악 | 20.0 | 9.0 | +11.0 | 건수 없음(일평균 비교) | 실측 확정 |", rep)
        self.assertIn("기록 부족", rep)                         # 주간보고는 1일치 → 가정 유지
        self.assertIn("업무 절감 11.0 − 추가 관리 2.0 − 오류 복구 1.0 = **8.0분/일**", rep)

    def test_workload_normalization(self):
        tmp = Path(tempfile.mkdtemp())
        for lst in ("ActionItems", "DecisionLog", "ActionCandidates"):
            export(Env(flows=[]), lst, tmp)
        log = tmp / "timelog.csv"
        with log.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["날짜", "구분", "업무", "소요분", "처리건수", "비고"])
            for d in range(1, 6):
                w.writerow([f"2026-10-0{d}", "기준선", "공장 자료 정리", 40, 10, ""])   # 건당 4분, 하루 10건
                w.writerow([f"2026-10-1{d}", "적용후", "공장 자료 정리", 10, 20, ""])   # 건당 0.5분, 업무량 2배
        rep = kpi_report.report(tmp, kpi_report.date(2026, 10, 26), log)
        # 일평균 단순 비교는 30분이지만 업무량이 2배 → 건당 3.5분 × 20건 = 70분/일
        self.assertIn("| 공장 자료 정리 | 40.0 | 10.0 | +70.0 | 건당 4.0→0.5분 | 실측 확정 |", rep)


if __name__ == "__main__":
    unittest.main()
