import unittest

from busan_note import dashboard, market


class DashboardPartsTest(unittest.TestCase):
    def test_progress_clamps(self):
        self.assertIn("width:100%", dashboard.progress(140))
        self.assertIn("width:0%", dashboard.progress(-5))

    def test_stacked_skips_zero(self):
        html = dashboard.stacked({market.YES: 3, market.MID: 0, market.NO: 2})
        self.assertIn("width:60%", html)
        self.assertIn("width:40%", html)
        self.assertNotIn("애매 0", html)

    def test_sparkline_needs_two_points(self):
        self.assertEqual(dashboard.sparkline([1.0]), "")
        self.assertIn("<polyline", dashboard.sparkline([1.0, 2.0, 1.5]))

    def test_css_built(self):
        css = dashboard.css()
        self.assertIn(".tw-grid", css)
        self.assertNotIn("preflight", css)


if __name__ == "__main__":
    unittest.main()
