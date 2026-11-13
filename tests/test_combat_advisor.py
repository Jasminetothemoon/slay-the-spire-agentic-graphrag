"""战斗顾问的测试。模型用按脚本回答的假模型代替，不联网、不花钱。
局面用 bottled_ai 录下的真实状态：手牌 3 张打击加 1 张痛击+，2 点能量，5 点格挡；
大颚虫 41 血，本回合攻击 11。"""
import copy
import json
import unittest

from sts_advisor.agents.combat import NO_SUBMIT, CombatAdvisor, pick_tier, render_state
from sts_advisor.agents.llm import ModelReply, ModelUnavailable, ToolCall, ToolTurn, UserTurn
from sts_advisor.ingest.visible_state import to_visible
from sts_advisor.tools.enumerate import best_single_turn
from sts_advisor.tools.settle import BOTTLED_ROOT, Play, all_enemies_dead, settle

FIXTURE = BOTTLED_ROOT / "tests" / "res" / "battles" / "general" / "battle_simple_state.json"

TWO_STRIKES = [("Strike_R", 0), ("Strike_R", 0)]
TOO_EXPENSIVE = [("Bash+", 0), ("Strike_R", 0)]  # 只有 2 点能量，第 2 步打不出


def as_plays(pairs):
    return [{"card": c, "target": t} for c, t in pairs]


def use(tool_id, name, args):
    return ToolCall(tool_id, name, args)


def submit(pairs, tool_id="s1", tentative_from=None, reasons=("理由",)):
    return ToolCall(
        tool_id,
        "submit_plan",
        {
            "plays": as_plays(pairs),
            "tentative_from": tentative_from,
            "summary": "结论",
            "reasons": list(reasons),
            "risks": [],
            "uncertain": [],
        },
    )


def reply(*calls, stop="tool_calls", text=""):
    return ModelReply(stop=stop, text=text, tool_calls=tuple(calls), raw={"role": "assistant"})


class ScriptedModel:
    """按顺序吐出预先写好的回答，并记下每次收到的请求。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append({**kwargs, "turns": list(kwargs["turns"])})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@unittest.skipUnless(FIXTURE.is_file(), "third_party/bottled_ai 子模块没有初始化")
class CombatAdvisorTest(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE, encoding="utf-8") as f:
            self.raw = json.load(f)
        self.state = to_visible(self.raw)

    def with_monster_hp(self, hp):
        raw = copy.deepcopy(self.raw)
        raw["game_state"]["combat_state"]["monsters"][0]["current_hp"] = hp
        return to_visible(raw)

    # ---------- 正常流程 ----------

    def test_tool_call_then_verified_plan(self):
        model = ScriptedModel(
            [reply(use("t1", "settle", {"plays": as_plays(TWO_STRIKES)})), reply(submit(TWO_STRIKES))]
        )
        advice = CombatAdvisor(model).advise(self.state)

        self.assertEqual(advice.source, "model")
        self.assertEqual(advice.plays, [Play("Strike_R", 0), Play("Strike_R", 0)])
        self.assertEqual((advice.model_calls, advice.tool_calls, advice.pushbacks), (2, 1, 0))
        # 展示用的数字来自程序的结算，不来自模型的文字
        self.assertEqual(advice.result.monsters_after[0]["hp"], 29)
        self.assertEqual(advice.result.hp_lost_after_enemy_turn, 6)

        # 第二次请求里，上一轮的工具结果已经发回，编号对得上
        tool_turn = model.calls[1]["turns"][-1]
        self.assertIsInstance(tool_turn, ToolTurn)
        self.assertEqual([r.call_id for r in tool_turn.results], ["t1"])
        self.assertTrue(json.loads(tool_turn.results[0].content)["ok"])

    def test_settle_and_submit_in_one_reply(self):
        model = ScriptedModel([reply(use("t1", "settle", {"plays": as_plays(TWO_STRIKES)}), submit(TWO_STRIKES))])
        advice = CombatAdvisor(model).advise(self.state)
        self.assertEqual(advice.source, "model")
        self.assertEqual((advice.model_calls, advice.tool_calls), (1, 1))

    def test_state_sent_to_model_has_no_hidden_information(self):
        model = ScriptedModel([reply(submit([("Strike_R", 0)]))])
        CombatAdvisor(model).advise(self.state)
        first = model.calls[0]["turns"][0]
        self.assertIsInstance(first, UserTurn)
        self.assertNotIn("seed", first.content)
        view = json.loads(first.content)
        self.assertIsInstance(view["draw_pile"], dict)  # 抽牌堆只给「哪些牌各几张」，没有顺序
        self.assertEqual(sum(view["draw_pile"].values()), len(self.state.combat["draw_pile"]))
        self.assertEqual(view["monsters"][0]["attack"], {"damage": 11, "hits": 1})

    # ---------- 核对与打回 ----------

    def test_illegal_plan_is_returned_as_tool_error_then_accepted(self):
        model = ScriptedModel([reply(submit(TOO_EXPENSIVE, "s1")), reply(submit([("Bash+", 0)], "s2"))])
        advice = CombatAdvisor(model).advise(self.state)

        self.assertEqual(advice.source, "model")
        self.assertEqual(advice.plays, [Play("Bash+", 0)])
        self.assertEqual(advice.pushbacks, 1)
        rejected = model.calls[1]["turns"][-1].results[0]
        self.assertEqual(rejected.call_id, "s1")
        self.assertTrue(rejected.is_error)
        self.assertIn("不合法", rejected.content)
        self.assertIn("第 2 步", rejected.content)

    def test_other_tool_results_are_kept_when_plan_is_rejected(self):
        model = ScriptedModel(
            [
                reply(use("t1", "settle", {"plays": []}), submit(TOO_EXPENSIVE, "s1")),
                reply(submit([("Bash+", 0)], "s2")),
            ]
        )
        CombatAdvisor(model).advise(self.state)
        results = model.calls[1]["turns"][-1].results
        self.assertEqual([r.call_id for r in results], ["t1", "s1"])
        self.assertEqual([r.is_error for r in results], [False, True])

    def test_plan_that_never_passes_falls_back_to_enumeration(self):
        model = ScriptedModel([reply(submit(TOO_EXPENSIVE, f"s{i}")) for i in range(3)])
        advice = CombatAdvisor(model).advise(self.state)

        self.assertEqual(advice.source, "enumeration")
        self.assertEqual(advice.pushbacks, 2)
        self.assertIn("没有通过核对", advice.note)
        self.assertTrue(advice.result.ok)
        self.assertEqual(model.responses, [])  # 打回 2 次，共问了 3 次，没有多问

    def test_text_without_submit_is_pushed_back(self):
        model = ScriptedModel([reply(stop="end", text="我建议打两张打击"), reply(submit(TWO_STRIKES))])
        advice = CombatAdvisor(model).advise(self.state)

        self.assertEqual(advice.source, "model")
        self.assertEqual(advice.pushbacks, 1)
        self.assertEqual(model.calls[1]["turns"][-1], UserTurn(NO_SUBMIT))

    def test_missed_lethal_is_flagged_and_fixed(self):
        state = self.with_monster_hp(12)  # 两张打击正好打死
        model = ScriptedModel([reply(submit([], "s1")), reply(submit(TWO_STRIKES, "s2"))])
        advice = CombatAdvisor(model).advise(state)

        self.assertIn("打死全部敌人", model.calls[1]["turns"][-1].results[0].content)
        self.assertEqual(advice.source, "model")
        self.assertTrue(all_enemies_dead(advice.result))

    def test_model_may_keep_its_plan_after_lethal_reminder(self):
        state = self.with_monster_hp(12)
        model = ScriptedModel([reply(submit([], "s1")), reply(submit([], "s2", reasons=("有意保留手牌",)))])
        advice = CombatAdvisor(model).advise(state)

        self.assertEqual(advice.source, "model")
        self.assertEqual(advice.plays, [])
        self.assertEqual(advice.pushbacks, 1)  # 只提醒一次，说明理由后接受

    # ---------- 降级 ----------

    def test_model_unavailable_falls_back(self):
        advice = CombatAdvisor(ScriptedModel([ModelUnavailable("账户余额不足")])).advise(self.state)
        self.assertEqual(advice.source, "enumeration")
        self.assertIn("余额不足", advice.note)
        self.assertTrue(advice.result.ok)

    def test_refusal_or_truncation_falls_back(self):
        for stop in ("refused", "truncated", "other"):
            with self.subTest(stop):
                advice = CombatAdvisor(ScriptedModel([reply(stop=stop)])).advise(self.state)
                self.assertEqual(advice.source, "enumeration")
                self.assertIn(stop, advice.note)

    def test_endless_tool_calls_are_cut_off(self):
        loop = [reply(use(f"t{i}", "settle", {"plays": []})) for i in range(20)]
        advice = CombatAdvisor(ScriptedModel(loop)).advise(self.state)
        self.assertEqual(advice.source, "enumeration")
        self.assertEqual(advice.model_calls, 8)

    # ---------- 工具 ----------

    def test_tool_errors_are_reported_to_the_model(self):
        model = ScriptedModel(
            [
                reply(use("t1", "no_such_tool", {}), ToolCall("t2", "settle", None, error="参数不是合法的 JSON")),
                reply(submit([("Strike_R", 0)])),
            ]
        )
        CombatAdvisor(model).advise(self.state)
        results = model.calls[1]["turns"][-1].results
        self.assertEqual([r.is_error for r in results], [True, True])
        self.assertIn("JSON", results[1].content)

    def test_draw_odds_tool_uses_the_visible_piles(self):
        draw_pile = [c["id"] for c in self.state.combat["draw_pile"]]
        some_card = draw_pile[0]
        expected = draw_pile.count(some_card) / len(draw_pile)
        model = ScriptedModel(
            [
                reply(use("t1", "draw_odds", {"cards": [some_card], "draws": 1, "at_least": 1})),
                reply(submit([("Strike_R", 0)])),
            ]
        )
        CombatAdvisor(model).advise(self.state)
        result = json.loads(model.calls[1]["turns"][-1].results[0].content)
        self.assertAlmostEqual(result["probability"], expected, places=4)

    def test_enemy_info_tool(self):
        model = ScriptedModel(
            [
                reply(use("t1", "enemy_info", {"monster_id": "GremlinNob"}), use("t2", "enemy_info", {"monster_id": "JawWorm"})),
                reply(submit([("Strike_R", 0)])),
            ]
        )
        CombatAdvisor(model).advise(self.state)
        known, unknown = model.calls[1]["turns"][-1].results
        nob = json.loads(known.content)
        self.assertTrue(nob["found"])
        self.assertIn("技能牌", nob["warnings"][0])
        # 没收录的敌人：如实说查不到，不算工具出错
        self.assertFalse(unknown.is_error)
        self.assertFalse(json.loads(unknown.content)["found"])

    def test_state_gives_monster_ids_for_lookup(self):
        view = json.loads(render_state(self.state))
        self.assertEqual(view["monsters"][0]["id"], "JawWorm")

    # ---------- 档位 ----------

    def test_tier_follows_room_type(self):
        for room, tier in (("MonsterRoom", "fast"), ("MonsterRoomElite", "strong"), ("MonsterRoomBoss", "strong")):
            with self.subTest(room):
                raw = copy.deepcopy(self.raw)
                raw["game_state"]["room_type"] = room
                state = to_visible(raw)
                self.assertEqual(pick_tier(state), tier)
                model = ScriptedModel([reply(submit([("Strike_R", 0)]))])
                CombatAdvisor(model).advise(state)
                self.assertEqual(model.calls[0]["tier"], tier)

    def test_rejects_non_combat_state(self):
        campfire = to_visible({"in_game": True, "game_state": {"screen_type": "REST", "relics": []}})
        with self.assertRaises(ValueError):
            CombatAdvisor(ScriptedModel([])).advise(campfire)

    # ---------- 单回合枚举 ----------

    def test_enumeration_returns_a_legal_line(self):
        plays = best_single_turn(self.state)
        self.assertTrue(plays)
        self.assertTrue(settle(self.state, plays).ok)

    def test_enumeration_finds_the_kill(self):
        state = self.with_monster_hp(12)
        self.assertTrue(all_enemies_dead(settle(state, best_single_turn(state))))

    def test_render_state_lists_unsupported_cards(self):
        view = json.loads(render_state(self.state, battle_goal="少掉血", unsupported=["True Grit"]))
        self.assertEqual(view["unsupported_cards"], ["True Grit"])
        self.assertEqual(view["battle_goal"], "少掉血")


if __name__ == "__main__":
    unittest.main()
