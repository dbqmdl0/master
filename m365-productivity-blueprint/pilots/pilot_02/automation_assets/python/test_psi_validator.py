"""psi_validator 단위 테스트(모의 데이터). 실행: python3 -m unittest -v python/test_psi_validator.py"""
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import psi_validator as pv  # noqa: E402

SD = HERE.parent / "sample_data"
SKUS = (SD / "sku_master.txt").read_text(encoding="utf-8").split()


class TestValidator(unittest.TestCase):
    def test_ok_file(self):
        h, b = pv.read_csv(SD / "PLT-A_2026-W44_ok.csv")
        r = pv.validate(h, b, "2026-W44", "PLT-A", SKUS)
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["rows"]), r["rowCount"])

    def test_error_file_matches_expected(self):
        exp = json.loads((SD / "expected_issues.json").read_text(encoding="utf-8"))
        h, b = pv.read_csv(SD / "PLT-B_2026-W44_errors.csv")
        r = pv.validate(h, b, "2026-W44", "PLT-B", SKUS)
        self.assertFalse(r["ok"])
        self.assertEqual(sorted(f"{i['code']}@{i['row']}" for i in r["issues"]), exp["PLT-B_2026-W44_errors.csv"])
        self.assertEqual(r["rows"], [])

    def test_fail_closed_without_master(self):
        h, b = pv.read_csv(SD / "PLT-A_2026-W44_ok.csv")
        self.assertFalse(pv.validate(h, b, "2026-W44", "PLT-A", [])["ok"])

    def test_missing_column(self):
        h, b = pv.read_csv(SD / "PLT-A_2026-W44_ok.csv")
        r = pv.validate(h[1:], [x[1:] for x in b], "2026-W44", "PLT-A", SKUS)
        self.assertEqual(r["issues"][0]["code"], "E01")

    def test_cli_exit_codes(self):
        self.assertEqual(pv.main([str(SD / "PLT-A_2026-W44_ok.csv"), "--week", "2026-W44", "--plant", "PLT-A",
                                  "--skus", "@" + str(SD / "sku_master.txt")]), 0)
        self.assertEqual(pv.main([str(SD / "PLT-B_2026-W44_errors.csv"), "--week", "2026-W44", "--plant", "PLT-B",
                                  "--skus", ",".join(SKUS)]), 1)


if __name__ == "__main__":
    unittest.main()
