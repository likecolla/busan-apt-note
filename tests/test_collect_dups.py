import unittest

from busan_note import collect


def rec(dong, price=1_000_000_000, date="2026-09-05", floor="23"):
    return {"kind": "trade", "lawd": "26500", "aptSeq": "X1", "apt": "남천자이", "jibun": "1", "dong": dong,
            "date": date, "area": 84.99, "floor": floor, "price": price}


class DongDupTest(unittest.TestCase):
    def test_drop_empty_dong_twin(self):
        out = collect.drop_dong_dups([rec(""), rec("101")])
        self.assertEqual([r["dong"] for r in out], ["101"])

    def test_keep_different_deals(self):
        recs = [rec("101"), rec("102"), rec("", floor="5")]
        self.assertEqual(len(collect.drop_dong_dups(recs)), 3)

    def test_keep_lone_empty(self):
        self.assertEqual(len(collect.drop_dong_dups([rec("")])), 1)


if __name__ == "__main__":
    unittest.main()
