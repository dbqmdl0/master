"""Pilot 01 규칙 단위 테스트 (모의 데이터만 사용). 실행: python3 -m unittest -v test_request_hub_rules.py"""
import unittest
from datetime import date, datetime, timezone

import request_hub_rules as R

UTC = timezone.utc
# 샘플 휴무일(테스트용). 운영에서는 Holidays List(회사 공식 달력)를 사용한다.
HOL = {date(2026, 10, 5), date(2026, 10, 9), date(2026, 12, 25)}


def utc(y, m, d, h=0, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=UTC)


class TestRequestId(unittest.TestCase):
    def test_format_uses_kst_year(self):
        # UTC 2026-12-31 16:00 = KST 2027-01-01 01:00 → 2027
        self.assertEqual(R.request_id(utc(2026, 12, 31, 16), 7), "REQ-2027-00007")
        self.assertEqual(R.request_id(utc(2026, 10, 26, 1), 1234), "REQ-2026-01234")


class TestBusinessDays(unittest.TestCase):
    def test_intake_before_cutoff_same_day(self):
        # KST 월 10:00 (UTC 01:00)
        self.assertEqual(R.intake_date(utc(2026, 10, 26, 1), HOL), date(2026, 10, 26))

    def test_intake_after_cutoff_next_bday(self):
        # KST 금 18:00 (UTC 09:00) → 다음 영업일 월
        self.assertEqual(R.intake_date(utc(2026, 10, 23, 9), HOL), date(2026, 10, 26))

    def test_intake_weekend(self):
        self.assertEqual(R.intake_date(utc(2026, 10, 25, 2), HOL), date(2026, 10, 26))

    def test_intake_on_holiday_skips(self):
        # 10/9(금, 휴무) 접수 → 10/12(월)
        self.assertEqual(R.intake_date(utc(2026, 10, 9, 1), HOL), date(2026, 10, 12))

    def test_add_business_days_skips_weekend_and_holiday(self):
        # 10/2(금) + 1영업일 → 10/5 휴무, 주말 건너뜀 → 10/6(화)
        self.assertEqual(R.add_business_days(date(2026, 10, 2), 1, HOL), date(2026, 10, 6))
        # 10/8(목) + 2 → 10/9 휴무 → 10/12(월), 10/13(화)
        self.assertEqual(R.add_business_days(date(2026, 10, 8), 2, HOL), date(2026, 10, 13))
        self.assertEqual(R.add_business_days(date(2026, 10, 8), 0, HOL), date(2026, 10, 8))

    def test_sla_target(self):
        # KST 10/23(금) 18시 접수 → 기준일 10/26(월) + 3영업일 = 10/29(목)
        self.assertEqual(R.sla_target(utc(2026, 10, 23, 9), 3, HOL), date(2026, 10, 29))

    def test_business_days_between(self):
        self.assertEqual(R.business_days_between(date(2026, 10, 2), date(2026, 10, 6), HOL), 1)
        self.assertEqual(R.business_days_between(date(2026, 10, 6), date(2026, 10, 2), HOL), -1)
        self.assertEqual(R.business_days_between(date(2026, 10, 6), date(2026, 10, 6), HOL), 0)


class TestSla(unittest.TestCase):
    def test_states(self):
        t = date(2026, 10, 29)
        self.assertEqual(R.sla_state(t, date(2026, 10, 26), HOL, "검토중"), "ok")
        self.assertEqual(R.sla_state(t, date(2026, 10, 28), HOL, "검토중"), "due_soon")
        self.assertEqual(R.sla_state(t, date(2026, 10, 29), HOL, "검토중"), "due_soon")
        self.assertEqual(R.sla_state(t, date(2026, 10, 30), HOL, "검토중"), "overdue")
        self.assertEqual(R.sla_state(t, date(2026, 11, 30), HOL, "완료"), "closed")

    def test_escalation_after_two_overdue_bdays(self):
        t = date(2026, 10, 29)  # 목
        self.assertFalse(R.should_escalate(t, date(2026, 10, 30), HOL, "진행중"))  # 1영업일 초과
        self.assertTrue(R.should_escalate(t, date(2026, 11, 2), HOL, "진행중"))   # 금·월 = 2영업일
        self.assertFalse(R.should_escalate(t, date(2026, 11, 2), HOL, "완료"))


    def test_escalation_cutoff_equivalent_to_rule(self):
        # 3개월 × 목표일 범위 전수 비교: 단일 기준일 방식(Flow) == 영업일 계산 방식(규칙)
        from datetime import timedelta
        start = date(2026, 9, 1)
        for i in range(90):
            today = start + timedelta(days=i)
            cut = R.escalation_cutoff(today, HOL)
            for j in range(-30, 5):
                target = today + timedelta(days=j)
                self.assertEqual(target <= cut, R.should_escalate(target, today, HOL, "진행중"),
                                 f"today={today} target={target} cut={cut}")


class TestTransitions(unittest.TestCase):
    def test_all_statuses_have_rules(self):
        self.assertEqual(set(R.TRANSITIONS), set(R.STATUSES))
        for targets in R.TRANSITIONS.values():
            self.assertTrue(targets <= set(R.STATUSES))

    def test_terminal_states(self):
        self.assertFalse(R.is_valid_transition("반려", "진행중"))
        self.assertFalse(R.is_valid_transition("취소", "접수"))
        self.assertTrue(R.is_valid_transition("완료", "진행중"))

    def test_apply_invalid_transition_logged_not_applied(self):
        req = R.Request(1, "t", "시제품", "a@x.com", utc(2026, 10, 26, 1), date(2026, 11, 6))
        self.assertFalse(R.apply_status_change(req, "완료", "b@x.com", utc(2026, 10, 26, 2)))
        self.assertEqual(req.status, "접수")
        self.assertIn("규칙위반", req.log[-1]["Comment"])
        self.assertTrue(R.apply_status_change(req, "검토중", "b@x.com", utc(2026, 10, 26, 3)))
        self.assertEqual(req.status, "검토중")


class TestDuplicates(unittest.TestCase):
    def test_duplicate_detection_normalizes_and_windows(self):
        base = R.Request(1, "A", "시제품", "Kim@X.com", utc(2026, 10, 1), date(2026, 11, 6),
                         product_code="SKU-100 ", plant="PLT-A")
        dup = R.Request(2, "A2", "시제품", "kim@x.com", utc(2026, 10, 10), date(2026, 11, 6),
                        product_code="SKU-100", plant="PLT-A")
        old = R.Request(3, "A3", "시제품", "kim@x.com", utc(2026, 9, 1), date(2026, 11, 6),
                        product_code="SKU-100", plant="PLT-A")
        closed = R.Request(4, "A4", "시제품", "kim@x.com", utc(2026, 10, 5), date(2026, 11, 6),
                           product_code="SKU-100", plant="PLT-A", status="완료")
        found = R.find_duplicates(dup, [base, old, closed, dup])
        self.assertEqual([r.item_id for r in found], [1])


class TestCommitment(unittest.TestCase):
    def test_reason_required(self):
        req = R.Request(1, "t", "시제품", "a@x.com", utc(2026, 10, 26, 1), date(2026, 11, 6))
        with self.assertRaises(ValueError):
            R.change_commitment(req, date(2026, 11, 5), " ", "o@x.com", utc(2026, 10, 26, 2))

    def test_change_count_and_warnings(self):
        req = R.Request(1, "t", "시제품", "a@x.com", utc(2026, 10, 26, 1), date(2026, 11, 6))
        self.assertEqual(R.change_commitment(req, date(2026, 11, 5), "최초 약속", "o", utc(2026, 10, 26)), [])
        self.assertEqual(req.change_count, 0)  # 최초 설정은 변경 아님
        R.change_commitment(req, date(2026, 11, 6), "원료 입고 지연", "o", utc(2026, 10, 27))
        R.change_commitment(req, date(2026, 11, 5), "재조정", "o", utc(2026, 10, 28))
        w = R.change_commitment(req, date(2026, 11, 9), "설비 점검", "o", utc(2026, 10, 29))
        self.assertEqual(req.change_count, 3)
        self.assertIn("반복변경", w)
        self.assertIn("희망일초과", w)


class TestDigestAndKpi(unittest.TestCase):
    def test_digest_groups_by_owner(self):
        reqs = [
            R.Request(1, "a", "시제품", "r@x", utc(2026, 10, 1), date(2026, 11, 1), status="진행중",
                      owner_email="o1@x", sla_target=date(2026, 10, 29)),
            R.Request(2, "b", "시제품", "r@x", utc(2026, 10, 1), date(2026, 11, 1), status="검토중",
                      owner_email="o1@x", sla_target=date(2026, 11, 3)),
            R.Request(3, "c", "재고확인", "r@x", utc(2026, 10, 1), date(2026, 11, 1), status="검토중",
                      owner_email="o2@x", sla_target=date(2026, 11, 20)),
            R.Request(4, "d", "재고확인", "r@x", utc(2026, 10, 1), date(2026, 11, 1), status="완료",
                      owner_email="o2@x", sla_target=date(2026, 10, 1)),
        ]
        dg = R.build_digest(reqs, date(2026, 11, 2), HOL)
        self.assertEqual(dg, {"o1@x": {"overdue": [1], "due_soon": [2], "escalate": [1]}})

    def test_lead_time(self):
        self.assertEqual(R.lead_time_bdays(utc(2026, 10, 2, 1), utc(2026, 10, 8, 5), HOL), 3)


if __name__ == "__main__":
    unittest.main()
