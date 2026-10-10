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


def _item(name, vals):
    ks = [f"{2021 + i // 52}{i % 52 + 1:02d}" for i in range(len(vals))]
    return {"name": name, "series": [(k, f"2021-01-{1 + i % 28:02d}", v, v) for i, (k, v) in enumerate(zip(ks, vals))]}


class SpreadTest(unittest.TestCase):
    def test_gap_and_trend(self):
        base = _item("부산", [100.0] * 120)
        up = _item("해운대구", [100.0] * 60 + [100 + i * 0.1 for i in range(60)])
        rows = market.spread_rows([base, up], "부산", ["해운대구"], group=("평균", ["해운대구"]))
        self.assertEqual(rows[0]["gap"], 0)
        self.assertGreater(rows[1]["gap"], rows[1]["gap_prev"])
        self.assertEqual(market.spread_trend(rows[1]["gap"], rows[1]["gap_prev"]), "벌어짐")
        self.assertAlmostEqual(rows[2]["ch52"], rows[1]["ch52"])
        self.assertEqual(rows[1]["turn"][0], "상승")

    def test_trend_band(self):
        self.assertEqual(market.spread_trend(2.0, 1.7), "비슷")
        self.assertEqual(market.spread_trend(-1.0, -2.0), "좁혀짐")
        self.assertEqual(market.spread_trend(None, 1.0), "–")


class HistoryTest(unittest.TestCase):
    def test_month_end(self):
        it = {"name": "부산", "series": [("202601", "2026-01-05", 100.0, 1), ("202602", "2026-01-26", 101.0, 1),
                                        ("202605", "2026-02-02", 102.0, 1)]}
        self.assertEqual(market.month_ends(it, 12), [("2026-01", "2026-01-26"), ("2026-02", "2026-02-02")])
        self.assertEqual(market.month_end_index(it), {"2026-01": 101.0, "2026-02": 102.0})
        self.assertEqual(len(market._cut(it, "2026-01-26")["series"]), 2)


class CompareRegionTest(unittest.TestCase):
    def test_pick(self):
        from busan_note import reb
        self.assertTrue(reb.is_compare("서울"))
        self.assertTrue(reb.is_compare("서울>강남지역>동남권>강남구"))
        self.assertFalse(reb.is_compare("서울>강북지역>도심권>중구"))
        self.assertFalse(reb.is_compare("부산>중부산권>중구"))


if __name__ == "__main__":
    unittest.main()
