"""结算器的测试。输入用 bottled_ai 测试目录里真实录下的游戏状态：
铁甲战士，手牌 3 张打击加 1 张痛击+，2 点能量，5 点格挡；大颚虫 41 血，本回合攻击 11。"""
import copy
import json
import unittest

from sts_advisor.ingest.visible_state import to_visible
from sts_advisor.tools.settle import BOTTLED_ROOT, Play, settle

FIXTURE = BOTTLED_ROOT / "tests" / "res" / "battles" / "general" / "battle_simple_state.json"


@unittest.skipUnless(FIXTURE.is_file(), "third_party/bottled_ai 子模块没有初始化")
class SettleTest(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE, encoding="utf-8") as f:
            self.raw = json.load(f)

    def test_two_strikes(self):
        result = settle(to_visible(self.raw), [Play("Strike_R", 0), Play("Strike_R", 0)])
        self.assertTrue(result.ok, result.reason)
        self.assertEqual(result.monsters_before[0]["hp"], 41)
        self.assertEqual(result.monsters_after[0]["hp"], 29)  # 41 - 6 - 6
        self.assertEqual(result.energy_left, 0)
        self.assertEqual(result.killed, [])
        self.assertEqual(result.hp_lost_after_enemy_turn, 6)  # 敌人打 11，自己有 5 格挡
        self.assertEqual(result.hand_after, ["bash+", "strike_r"])

    def test_vulnerable_first_deals_more(self):
        raw = copy.deepcopy(self.raw)
        raw["game_state"]["combat_state"]["player"]["energy"] = 3
        bash_first = settle(to_visible(raw), [Play("Bash+", 0), Play("Strike_R", 0)])
        strike_first = settle(to_visible(raw), [Play("Strike_R", 0), Play("Bash+", 0)])
        self.assertEqual(bash_first.monsters_after[0]["hp"], 22)  # 41 - 10 - 9（易伤后打击 6×1.5）
        self.assertEqual(strike_first.monsters_after[0]["hp"], 25)  # 41 - 6 - 10

    def test_not_enough_energy(self):
        result = settle(to_visible(self.raw), [Play("Bash+", 0), Play("Strike_R", 0)])
        self.assertFalse(result.ok)
        self.assertEqual(result.failed_step, 1)
        self.assertIn("打不出", result.reason)

    def test_card_not_in_hand(self):
        result = settle(to_visible(self.raw), [Play("Defend_R")])
        self.assertFalse(result.ok)
        self.assertIn("手牌里没有", result.reason)

    def test_wrong_target(self):
        result = settle(to_visible(self.raw), [Play("Strike_R")])
        self.assertFalse(result.ok)
        self.assertIn("目标不对", result.reason)

    def test_kill_is_reported(self):
        raw = copy.deepcopy(self.raw)
        raw["game_state"]["combat_state"]["monsters"][0]["current_hp"] = 12
        result = settle(to_visible(raw), [Play("Strike_R", 0), Play("Strike_R", 0)])
        self.assertEqual(result.killed, [0])
        self.assertEqual(result.hp_lost_after_enemy_turn, 0)

    def test_unsupported_card_is_flagged(self):
        raw = copy.deepcopy(self.raw)
        first = raw["game_state"]["combat_state"]["hand"][0]
        first["id"] = first["name"] = "True Grit"
        state = to_visible(raw)
        self.assertEqual(settle(state, []).unsupported_cards, ["True Grit"])
        result = settle(state, [Play("True Grit")])
        self.assertFalse(result.ok)
        self.assertIn("无法试算", result.reason)

    def test_localized_relic_names_are_still_recognized(self):
        raw = copy.deepcopy(self.raw)
        for relic in raw["game_state"]["relics"]:
            relic["name"] = "中文显示名"
        result = settle(to_visible(raw), [Play("Strike_R", 0)])
        self.assertTrue(result.ok, result.reason)
        self.assertEqual(result.unrecognized_relics, [])

    def test_draw_pile_order_does_not_change_result(self):
        raw = copy.deepcopy(self.raw)
        raw["game_state"]["combat_state"]["draw_pile"].reverse()
        plays = [Play("Strike_R", 0), Play("Strike_R", 0)]
        self.assertEqual(settle(to_visible(self.raw), plays), settle(to_visible(raw), plays))

    def test_outside_combat(self):
        result = settle(to_visible({"in_game": True, "game_state": {"screen_type": "REST", "relics": []}}), [])
        self.assertFalse(result.ok)


if __name__ == "__main__":
    unittest.main()
