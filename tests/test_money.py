import unittest

from busan_note.money import format_won, korean_unit


class FormatWonTest(unittest.TestCase):
    def test_examples_from_spec(self):
        self.assertEqual(format_won(1_080_000_000), "1,080,000,000원 (10억 8,000만)")
        self.assertEqual(format_won(820_000_000), "820,000,000원 (8억 2,000만)")
        self.assertEqual(format_won(25_000_000), "25,000,000원 (2,500만)")

    def test_round_eok(self):
        self.assertEqual(format_won(1_000_000_000), "1,000,000,000원 (10억)")

    def test_eok_with_small_man(self):
        self.assertEqual(korean_unit(1_205_000_000), "12억 500만")

    def test_below_man_rounds(self):
        self.assertEqual(korean_unit(815_005_000), "8억 1,501만")

    def test_none(self):
        self.assertEqual(format_won(None), "-")


if __name__ == "__main__":
    unittest.main()
