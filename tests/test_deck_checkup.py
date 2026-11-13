"""牌组体检的测试。牌组用 bottled_ai 录下的真实状态里的初始牌组：
5 张打击、4 张防御、1 张痛击+，遗物是燃烧之血。"""
import copy
import json
import unittest
from dataclasses import asdict

from sts_advisor.ingest.visible_state import to_visible
from sts_advisor.knowledge import monsters, trials
from sts_advisor.tools.deck_checkup import SKIP, DeckChecker, checkup_state, compare_candidates, trials_for
from sts_advisor.tools.settle import BOTTLED_ROOT

FIXTURE = BOTTLED_ROOT / "tests" / "res" / "battles" / "general" / "battle_simple_state.json"


def card(card_id, card_type, cost, needs_target, upgrades=0):
    return {
        "id": card_id,
        "name": "中文显示名",  # 体检只认内部编号，显示名是什么都不影响
        "type": card_type,
        "cost": cost,
        "has_target": needs_target,
        "upgrades": upgrades,
        "exhausts": False,
        "ethereal": False,
        "rarity": "COMMON",
        "uuid": card_id,
    }


CLEAVE = card("Cleave", "ATTACK", 1, False)  # 对所有敌人造成伤害
SHRUG = card("Shrug It Off", "SKILL", 1, False)  # 格挡并抽 1 张
POMMEL = card("Pommel Strike", "ATTACK", 1, True)  # 伤害并抽 1 张
INFLAME = card("Inflame", "POWER", 1, False)  # 能力牌：加力量
TRUE_GRIT = card("True Grit", "SKILL", 1, False)  # 结算模块没有实现的牌


@unittest.skipUnless(FIXTURE.is_file(), "third_party/bottled_ai 子模块没有初始化")
class DeckCheckupTest(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE, encoding="utf-8") as f:
            self.state = to_visible(json.load(f))
        self.deck = self.state.game["deck"]
        self.checker = DeckChecker(self.state.game["relics"])

    # ---------- 单副牌 ----------

    def test_starter_deck(self):
        result = checkup_state(self.state)
        self.assertEqual((result.deck_size, result.method, result.hands), (10, "exact", 252))  # C(10,5)
        self.assertEqual(result.aoe_bonus, 0.0)  # 初始牌组没有任何群伤
        self.assertEqual(result.draw_per_turn, 0.0)
        self.assertEqual(result.skill_share, 0.4)
        self.assertEqual(result.chance_to_see_a_card, 0.5)
        self.assertEqual(result.relics, ["Burning Blood"])
        self.assertEqual((result.power_cards, result.unsupported_cards, result.dead_cards), ([], [], []))

    def test_block_matches_hand_calculation(self):
        # 10 张里 4 张防御，抽 5 张，3 点能量最多打 3 张防御，每张 5 点：
        # 平均格挡 = 5 × (平均防御张数 2 − 抽到 4 张防御的概率 6/252)
        expected = 5 * (2 - 6 / 252)
        self.assertAlmostEqual(self.checker.checkup(self.deck).avg_block, expected, places=2)

    def test_damage_is_within_what_the_cards_allow(self):
        result = self.checker.checkup(self.deck)
        # 最好的一手是痛击+ 接打击（10 + 易伤后的 9 = 19），最差是 5 张里只有 1 张攻击牌
        self.assertTrue(6 <= result.low_damage <= result.avg_damage <= 19)
        self.assertEqual(result.avg_damage, 17.27)  # 回归值：结算模块或算法变了要重新确认

    def test_small_deck(self):
        result = self.checker.checkup(self.deck[:3])  # 3 张打击，比一手牌还少
        self.assertEqual((result.hands, result.avg_damage, result.chance_to_see_a_card), (1, 18.0, 1.0))

    def test_empty_deck_is_rejected(self):
        with self.assertRaises(ValueError):
            self.checker.checkup([])

    def test_large_deck_is_sampled_and_reproducible(self):
        big = self.deck + [CLEAVE, SHRUG, POMMEL] * 4
        first = DeckChecker(self.state.game["relics"]).checkup(big)
        second = DeckChecker(self.state.game["relics"]).checkup(big)
        self.assertEqual(first.method, "sampled")
        self.assertEqual(asdict(first), asdict(second))  # 固定种子，两次结果相同
        self.assertGreater(first.aoe_bonus, 0)

    # ---------- 候选对比 ----------

    def test_skip_is_a_candidate_with_no_change(self):
        rows = compare_candidates(self.state, [CLEAVE])
        self.assertEqual(rows[0].candidate, SKIP)
        self.assertTrue(all(v == 0.0 for v in rows[0].delta.values()))

    def test_each_candidate_moves_the_expected_numbers(self):
        rows = {r.candidate: r for r in compare_candidates(self.state, [CLEAVE, SHRUG, POMMEL, INFLAME])}

        self.assertGreater(rows["Cleave"].delta["aoe_bonus"], 5)  # 群伤牌补的是群伤
        self.assertGreater(rows["Shrug It Off"].delta["avg_block"], 2)  # 格挡牌补的是格挡
        self.assertGreater(rows["Shrug It Off"].delta["draw_per_turn"], 0)
        self.assertGreater(rows["Pommel Strike"].delta["avg_damage"], 1)
        # 能力牌的收益在之后的回合，单回合试算看不出来，所以单独列出，交给构筑顾问判断
        self.assertLess(rows["Inflame"].delta["avg_damage"], 0)
        self.assertEqual(rows["Inflame"].checkup.power_cards, ["Inflame"])
        # 任何一张牌都会让其他牌更难上手
        for name in ("Cleave", "Shrug It Off", "Pommel Strike", "Inflame"):
            self.assertAlmostEqual(rows[name].delta["chance_to_see_a_card"], 5 / 11 - 5 / 10, places=3)

    def test_unsupported_candidate_is_flagged(self):
        row = compare_candidates(self.state, [TRUE_GRIT])[1]
        self.assertEqual(row.checkup.unsupported_cards, ["True Grit"])

    def test_comparison_matches_direct_enumeration(self):
        """对比时只另算「含新牌」的手牌再加权，结果应当和直接穷举加牌后的牌组一致。"""
        for candidate in (CLEAVE, SHRUG, POMMEL):
            with self.subTest(candidate["id"]):
                direct = self.checker.checkup(self.deck + [candidate])
                via = self.checker.compare(self.deck, [candidate])[1].checkup
                for key in ("avg_damage", "low_damage", "avg_aoe_damage", "avg_block", "low_block"):
                    self.assertAlmostEqual(getattr(via, key), getattr(direct, key), places=2, msg=key)

    def test_input_is_not_modified(self):
        before = copy.deepcopy(self.deck)
        compare_candidates(self.state, [CLEAVE])
        self.assertEqual(self.deck, before)

    # ---------- 考验表 ----------

    def test_trials_for_act_one(self):
        result = self.checker.checkup(self.deck)
        rows = {r["monster_id"]: r for r in trials_for(self.state, result)}
        self.assertEqual(sorted(rows), ["GremlinNob", "Lagavulin", "Sentry", "TheGuardian"])  # 本幕 Boss 是守护者
        self.assertEqual((rows["GremlinNob"]["total_hp"], rows["GremlinNob"]["rough_turns_to_kill"]), (84, 5))
        # 三只哨卫按总血量算，用的是对多个目标的总伤害
        self.assertEqual((rows["Sentry"]["count"], rows["Sentry"]["total_hp"]), (3, 120))
        self.assertEqual(rows["Sentry"]["damage_per_turn"], result.avg_aoe_damage)
        self.assertTrue(rows["TheGuardian"]["warnings"])


class TrialsTableTest(unittest.TestCase):
    def test_every_trial_points_at_a_known_monster(self):
        for entry in trials.for_act(1):
            self.assertIsNotNone(monsters.lookup(entry["monster_id"]), entry)
            self.assertIn(entry["metric"], ("avg_damage", "avg_aoe_damage"))

    def test_unknown_act_is_empty(self):
        self.assertEqual(trials.for_act(9), [])

    def test_about_says_it_is_uncalibrated(self):
        self.assertIn("没有校准", trials.about()["status"])

    def test_boss_lookup_by_english_name(self):
        self.assertEqual(monsters.lookup_by_name("The Guardian")["id"], "TheGuardian")
        self.assertIsNone(monsters.lookup_by_name("Nobody"))


if __name__ == "__main__":
    unittest.main()
