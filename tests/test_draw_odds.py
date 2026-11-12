import unittest

from sts_advisor.tools.draw_odds import draw_probability


class DrawOddsTest(unittest.TestCase):
    def test_one_of_five_in_one_draw(self):
        pile = ["Bash", "Strike", "Strike", "Defend", "Defend"]
        self.assertAlmostEqual(draw_probability(pile, "Bash", draws=1), 0.2)

    def test_drawing_whole_pile_is_certain(self):
        pile = ["Bash", "Strike", "Strike", "Defend", "Defend"]
        self.assertAlmostEqual(draw_probability(pile, "Bash", draws=5), 1.0)

    def test_at_least_two(self):
        # 4 张里有 2 张想要的，抽 2 张都中：1 / C(4,2) = 1/6
        pile = ["Bash", "Bash", "Strike", "Defend"]
        self.assertAlmostEqual(draw_probability(pile, "Bash", draws=2, at_least=2), 1 / 6)

    def test_wanted_can_be_a_set_or_predicate(self):
        pile = ["Bash", "Anger", "Strike", "Defend"]
        self.assertAlmostEqual(draw_probability(pile, {"Bash", "Anger"}, draws=1), 0.5)
        self.assertAlmostEqual(draw_probability(pile, lambda c: c != "Defend", draws=1), 0.75)

    def test_absent_card_is_impossible(self):
        self.assertEqual(draw_probability(["Strike", "Defend"], "Bash", draws=2), 0.0)

    def test_reshuffle_from_discard(self):
        # 抽牌堆 1 张（不是想要的），要抽 2 张：第 2 张来自洗回来的弃牌堆，4 张里有 1 张想要的
        self.assertAlmostEqual(
            draw_probability(["Strike"], "Bash", draws=2, discard_pile=["Bash", "Defend", "Defend", "Defend"]),
            0.25,
        )

    def test_reshuffle_when_draw_pile_already_satisfies(self):
        self.assertAlmostEqual(
            draw_probability(["Bash"], "Bash", draws=3, discard_pile=["Strike", "Strike"]),
            1.0,
        )

    def test_order_does_not_matter(self):
        pile = ["Bash", "Strike", "Defend", "Anger"]
        self.assertEqual(
            draw_probability(pile, "Bash", draws=2),
            draw_probability(list(reversed(pile)), "Bash", draws=2),
        )

    def test_negative_arguments_rejected(self):
        with self.assertRaises(ValueError):
            draw_probability(["Bash"], "Bash", draws=-1)


if __name__ == "__main__":
    unittest.main()
