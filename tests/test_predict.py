import unittest

from busan_note.predict import status


class StatusTest(unittest.TestCase):
    P = {"period": ["2026-10", "2026-12"], "metric": "med84", "op": ">=", "value": 100}

    def test_before_during_after(self):
        self.assertEqual(status(self.P, "2026-09", None, 0), "대기")
        self.assertEqual(status(self.P, "2026-11", 90, 3), "진행 중")
        self.assertEqual(status(self.P, "2027-02", 90, 3), "신고 기다림")
        self.assertEqual(status(self.P, "2027-03", 120, 5), "적중")
        self.assertEqual(status(self.P, "2027-03", 90, 5), "빗나감")

    def test_small_sample(self):
        self.assertEqual(status(self.P, "2027-03", 120, 2), "표본 부족")

    def test_count_metric_allows_zero(self):
        p = dict(self.P, metric="jeonse_count", value=1)
        self.assertEqual(status(p, "2027-03", 0, 0), "빗나감")


if __name__ == "__main__":
    unittest.main()
