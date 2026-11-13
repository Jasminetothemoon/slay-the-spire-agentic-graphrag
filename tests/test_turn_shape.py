"""一回合有几点能量、抽几张牌，会随遗物变化。体检和结算都要跟着变。"""
import copy
import json
import unittest

from sts_advisor.ingest.visible_state import to_visible
from sts_advisor.tools.deck_checkup import DeckChecker
from sts_advisor.tools.settle import BOTTLED_ROOT, RELIC_ID_TO_BOTTLED_NAME, RELICS_NOT_IMPLEMENTED, settle
from sts_advisor.tools.turn_shape import turn_shape

FIXTURE = BOTTLED_ROOT / "tests" / "res" / "battles" / "general" / "battle_simple_state.json"


def relics(*ids):
    return [{"id": i, "name": "中文显示名", "counter": -1} for i in ids]


class TurnShapeTest(unittest.TestCase):
    def test_default(self):
        shape = turn_shape([])
        self.assertEqual((shape.energy, shape.hand_size), (3, 5))
        self.assertFalse(shape.first_turn_differs)

    def test_first_turn_draw_relics(self):
        shape = turn_shape(relics("Ring of the Snake"))  # 静默猎手的初始遗物：第一回合多抽 2 张
        self.assertEqual((shape.hand_size, shape.first_turn_hand_size), (5, 7))
        self.assertTrue(shape.first_turn_differs)
        self.assertEqual(turn_shape(relics("Ring of the Snake", "Bag of Preparation")).first_turn_hand_size, 9)

    def test_every_turn_draw_relics(self):
        shape = turn_shape(relics("Snecko Eye"))
        self.assertEqual((shape.hand_size, shape.first_turn_hand_size), (7, 7))
        self.assertIn("异蛇之眼", shape.notes[0])  # 费用随机这件事算不了，要说出来
        self.assertEqual(turn_shape(relics("Ring of the Serpent")).hand_size, 6)

    def test_energy_relics(self):
        self.assertEqual(turn_shape(relics("Coffee Dripper")).energy, 4)
        self.assertEqual(turn_shape(relics("Coffee Dripper", "Sozu")).energy, 5)
        lantern = turn_shape(relics("Lantern"))
        self.assertEqual((lantern.energy, lantern.first_turn_energy), (3, 4))

    def test_hand_is_capped_at_ten(self):
        shape = turn_shape(relics("Snecko Eye", "Ring of the Serpent", "Ring of the Snake", "Bag of Preparation"))
        self.assertEqual((shape.hand_size, shape.first_turn_hand_size), (8, 10))

    def test_unrelated_relics_change_nothing(self):
        shape = turn_shape(relics("Burning Blood", "Vajra"))
        self.assertEqual((shape.energy, shape.hand_size, shape.notes), (3, 5, ()))


@unittest.skipUnless(FIXTURE.is_file(), "third_party/bottled_ai 子模块没有初始化")
class CheckupFollowsRelicsTest(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE, encoding="utf-8") as f:
            self.raw = json.load(f)
        self.deck = self.raw["game_state"]["deck"]  # 5 打击、4 防御、1 痛击+
        self.base = DeckChecker(relics("Burning Blood")).checkup(self.deck)

    def test_energy_relic_raises_output(self):
        result = DeckChecker(relics("Coffee Dripper")).checkup(self.deck)
        self.assertEqual(result.energy, 4)
        self.assertGreater(result.avg_damage, self.base.avg_damage)
        self.assertGreater(result.avg_block, self.base.avg_block)

    def test_first_turn_is_computed_separately(self):
        result = DeckChecker(relics("Ring of the Snake")).checkup(self.deck)
        self.assertEqual((result.hand_size, result.first_turn_hand_size), (5, 7))
        self.assertEqual(result.avg_damage, self.base.avg_damage)  # 平时的回合不受影响
        self.assertGreater(result.first_turn_damage, result.avg_damage)  # 第一回合牌多，选择更好
        self.assertEqual(self.base.first_turn_damage, self.base.avg_damage)  # 没有这类遗物时两者相同

    def test_bigger_hand_every_turn(self):
        result = DeckChecker(relics("Snecko Eye")).checkup(self.deck)
        self.assertEqual(result.hand_size, 7)
        self.assertEqual(result.chance_to_see_a_card, 0.7)  # 10 张里每回合看到 7 张
        self.assertTrue(result.assumptions)

    def test_comparison_still_matches_direct_enumeration(self):
        cleave = {
            "id": "Cleave", "name": "顺劈斩", "type": "ATTACK", "cost": 1, "has_target": False, "upgrades": 0,
            "exhausts": False, "ethereal": False, "rarity": "COMMON", "uuid": "c",
        }  # fmt: skip
        checker = DeckChecker(relics("Ring of the Snake", "Coffee Dripper"))
        direct = checker.checkup(self.deck + [cleave])
        via = checker.compare(self.deck, [cleave])[1].checkup
        for key in ("avg_damage", "avg_aoe_damage", "avg_block", "first_turn_damage", "first_turn_block"):
            self.assertAlmostEqual(getattr(via, key), getattr(direct, key), places=2, msg=key)


@unittest.skipUnless(FIXTURE.is_file(), "third_party/bottled_ai 子模块没有初始化")
class RelicNamesTest(unittest.TestCase):
    """游戏内部的遗物编号有一部分和结算模块认的名字不同，要先换名。"""

    def setUp(self):
        with open(FIXTURE, encoding="utf-8") as f:
            self.raw = json.load(f)

    def with_relics(self, *ids):
        raw = copy.deepcopy(self.raw)
        raw["game_state"]["relics"] = relics(*ids)
        return to_visible(raw)

    def test_table_covers_the_known_mismatches(self):
        self.assertEqual(len(RELIC_ID_TO_BOTTLED_NAME), 45)
        self.assertEqual(RELIC_ID_TO_BOTTLED_NAME["InkBottle"], "ink bottle")
        self.assertEqual(RELIC_ID_TO_BOTTLED_NAME["Snake Skull"], "snecko skull")
        self.assertIn("Dead Branch", RELICS_NOT_IMPLEMENTED)

    def test_renamed_relics_are_recognized(self):
        result = settle(self.with_relics("InkBottle", "Snake Skull", "Boot", "Burning Blood"), [])
        self.assertEqual(result.unrecognized_relics, [])

    def test_unimplemented_relics_are_reported(self):
        result = settle(self.with_relics("Dead Branch", "Burning Blood"), [])
        self.assertEqual(result.unrecognized_relics, ["Dead Branch"])


if __name__ == "__main__":
    unittest.main()
