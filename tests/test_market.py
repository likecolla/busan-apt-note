import unittest

from busan_note import market


class StateTest(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(market.state_of(0.59), "회복")
        self.assertEqual(market.state_of(-0.22), "보합")
        self.assertEqual(market.state_of(-0.51, recent_low=True), "하락 (새 저점)")
        self.assertEqual(market.state_of(-0.70, at_low=True), "하락 (지금이 저점)")
        self.assertEqual(market.state_of(None), "–")


class VerdictTest(unittest.TestCase):
    def test_count(self):
        pts = [("a", "", "있음", "g1"), ("b", "", "애매", "g1"), ("c", "", "반대", "g1"),
               ("d", "", "반대", "g1"), ("e", "", "반대", "g1")]
        n, lean = market.verdict(pts, "보합")
        self.assertEqual(n, {"있음": 1, "애매": 1, "반대": 3})
        self.assertEqual(lean, "하락 쪽")


class CardFactsTest(unittest.TestCase):
    def test_sides(self):
        c = {"yoy": 0.065, "vs_peak": -0.193, "peak": {"price": 1}, "floor_premium": 0.18,
             "low_sample": False, "n3": 15, "n12": 263, "cancel_rate": 0.057, "cancel_n": 15,
             "direct_n": 8, "peak_cancel": [1, 2],
             "jeonse_ratio": {"ratio": 0.55, "n": 6, "basis": "신규"}}
        up, down = market.card_facts(c)
        self.assertIn("3.3㎡당 가격이 1년 전보다 +6.5%", up)
        self.assertTrue(any("최고가보다 -19.3%" in d for d in down))
        self.assertTrue(any("전세가율 55%" in d for d in down))

    def test_jeonse_needs_new_contracts(self):
        up, down = market.card_facts({"jeonse_ratio": {"ratio": 0.31, "n": 2, "basis": "전체"}})
        self.assertEqual((up, down), ([], []))


if __name__ == "__main__":
    unittest.main()
