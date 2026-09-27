import unittest

from busan_note.analyze import band, floor_band, median_won, per_pyeong, quarter, shift_months


class AnalyzeTest(unittest.TestCase):
    def test_band_edges(self):
        self.assertEqual(band(59.99), "60㎡ 미만")
        self.assertEqual(band(60), "60~75㎡")
        self.assertEqual(band(75), "84㎡형")
        self.assertEqual(band(84.99), "84㎡형")
        self.assertEqual(band(90), "90㎡ 이상")

    def test_per_pyeong(self):
        # 84.9㎡ 10억 → 3.3㎡당 약 3,894만원
        self.assertAlmostEqual(per_pyeong(1_000_000_000, 84.9) / 10000, 3893.8, places=1)
        self.assertIsNone(per_pyeong(None, 84.9))

    def test_floor_band(self):
        self.assertEqual(floor_band("10", 30), "저층")
        self.assertEqual(floor_band("11", 30), "중층")
        self.assertEqual(floor_band("21", 30), "고층")
        self.assertEqual(floor_band("", 30), "")

    def test_median_rounds_to_manwon(self):
        self.assertEqual(median_won([815_000_000, 816_010_000]), 815_510_000)
        self.assertIsNone(median_won([]))

    def test_months(self):
        self.assertEqual(shift_months("2026-01", -1), "2025-12")
        self.assertEqual(shift_months("2026-09", -12), "2025-09")
        self.assertEqual(quarter("2026-09"), "2026 3분기")


if __name__ == "__main__":
    unittest.main()
