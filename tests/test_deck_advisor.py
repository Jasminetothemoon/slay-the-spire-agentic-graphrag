"""构筑顾问的测试。模型用按脚本回答的假模型代替，不联网、不花钱。
局面用 bottled_ai 录下的真实状态：铁甲战士第一幕第 1 层，初始牌组 10 张，
可选剑柄打击、飞踢、震荡波，也可以跳过；本幕 Boss 是史莱姆老大。"""
import copy
import json
import unittest

from sts_advisor.agents.deckbuilding import DeckAdvisor
from sts_advisor.agents.llm import ModelReply, ModelUnavailable, ToolCall, UserTurn
from sts_advisor.ingest.visible_state import to_visible
from sts_advisor.tools.deck_checkup import SKIP
from sts_advisor.tools.settle import BOTTLED_ROOT

FIXTURE = BOTTLED_ROOT / "tests" / "res" / "card_reward" / "card_reward_skip.json"
OPTIONS = ["Pommel Strike", "Dropkick", "Shockwave", SKIP]


def reason(text, metric=None, claim=None):
    return {"text": text, "metric": metric, "claim": claim}


def submit(choice, ranking=None, reasons=None, tool_id="s1", **overrides):
    args = {
        "choice": choice,
        "ranking": ranking if ranking is not None else [choice] + [o for o in OPTIONS if o != choice],
        "summary": "结论",
        "reasons": reasons if reasons is not None else [reason("自己的判断")],
        "too_greedy": "不贪",
        "too_timid": "不怂",
        "risks": [],
        "uncertain": [],
    }
    args.update(overrides)
    return ToolCall(tool_id, "submit_choice", args)


def reply(*calls, stop="tool_calls", text=""):
    return ModelReply(stop=stop, text=text, tool_calls=tuple(calls), raw={"role": "assistant"})


class ScriptedModel:
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
class DeckAdvisorTest(unittest.TestCase):
    def setUp(self):
        with open(FIXTURE, encoding="utf-8") as f:
            self.raw = json.load(f)
        self.state = to_visible(self.raw)

    def advise(self, *responses, state=None):
        model = ScriptedModel(responses)
        return DeckAdvisor(model).advise(state or self.state), model

    def last_result(self, model):
        return model.calls[-1]["turns"][-1].results[0]

    # ---------- 输入 ----------

    def test_model_receives_the_computed_facts(self):
        _, model = self.advise(reply(submit("Pommel Strike")))
        self.assertEqual(model.calls[0]["tier"], "strong")
        first = model.calls[0]["turns"][0]
        self.assertIsInstance(first, UserTurn)
        self.assertNotIn("seed", first.content)
        view = json.loads(first.content)

        self.assertEqual([o["option"] for o in view["options"]], OPTIONS)
        self.assertEqual(view["checkup_now"]["deck_size"], 10)
        self.assertEqual(sorted(view["change_if_taken"]), sorted(OPTIONS))
        self.assertTrue(all(v == 0 for v in view["change_if_taken"][SKIP].values()))  # 跳过：什么都不变
        self.assertGreater(view["change_if_taken"]["Pommel Strike"]["avg_damage"], 0)
        # 考验里有第一幕的精英和本幕 Boss，并且每个候选都估了回合数
        trial_ids = [t["monster_id"] for t in view["trials"]]
        self.assertEqual(trial_ids, ["GremlinNob", "Lagavulin", "Sentry", "SlimeBoss"])
        self.assertEqual(sorted(view["trials"][0]["rough_turns_if_taken"]), ["Dropkick", "Pommel Strike", "Shockwave"])

    # ---------- 通过 ----------

    def test_accepted_choice_with_checked_and_unchecked_reasons(self):
        advice, _ = self.advise(
            reply(
                submit(
                    "Pommel Strike",
                    reasons=[reason("伤害更高", "avg_damage", "increase"), reason("抽牌让牌组更顺")],
                )
            )
        )
        self.assertEqual((advice.source, advice.choice), ("model", "Pommel Strike"))
        self.assertEqual(advice.ranking[0], "Pommel Strike")
        checked, judged = advice.reasons
        self.assertTrue(checked.checked)
        self.assertGreater(checked.change, 0)  # 程序附上体检算出的实际变化
        self.assertFalse(judged.checked)  # 模型自己的判断，标为未核对
        self.assertIsNone(judged.change)
        self.assertEqual((advice.too_greedy, advice.too_timid), ("不贪", "不怂"))

    def test_skip_is_a_valid_choice(self):
        advice, _ = self.advise(
            reply(submit(SKIP, reasons=[reason("牌组不会变厚", "chance_to_see_a_card", "no_change")]))
        )
        self.assertEqual((advice.source, advice.choice), ("model", SKIP))
        self.assertTrue(advice.reasons[0].checked)

    # ---------- 核对与打回 ----------

    def test_claim_that_contradicts_the_checkup_is_pushed_back(self):
        wrong = submit("Pommel Strike", reasons=[reason("格挡更高", "avg_block", "increase")], tool_id="s1")
        right = submit("Pommel Strike", reasons=[reason("格挡会略降", "avg_block", "decrease")], tool_id="s2")
        advice, model = self.advise(reply(wrong), reply(right))

        self.assertEqual((advice.source, advice.pushbacks), ("model", 1))
        rejected = self.last_result(model)
        self.assertTrue(rejected.is_error)
        self.assertIn("和体检对不上", rejected.content)
        self.assertIn("avg_block", rejected.content)
        self.assertIn("-0.", rejected.content)  # 把体检算出的实际数字告诉模型

    def test_choice_must_be_offered(self):
        advice, model = self.advise(reply(submit("Demon Form", ranking=OPTIONS, tool_id="s1")), reply(submit("Dropkick", tool_id="s2")))
        self.assertIn("必须是 options 里的一项", self.last_result(model).content)
        self.assertEqual(advice.choice, "Dropkick")

    def test_ranking_must_cover_every_option_and_lead_with_choice(self):
        incomplete = submit("Dropkick", ranking=["Dropkick", SKIP], tool_id="s1")
        misordered = submit("Dropkick", ranking=[SKIP, "Dropkick", "Pommel Strike", "Shockwave"], tool_id="s2")
        advice, model = self.advise(reply(incomplete), reply(misordered), reply(submit("Dropkick", tool_id="s3")))
        self.assertIn("各列一次", model.calls[1]["turns"][-1].results[0].content)
        self.assertIn("第一项", model.calls[2]["turns"][-1].results[0].content)
        self.assertEqual((advice.source, advice.pushbacks), ("model", 2))

    def test_both_directions_must_be_answered(self):
        advice, model = self.advise(reply(submit("Dropkick", too_timid="  ", tool_id="s1")), reply(submit("Dropkick", tool_id="s2")))
        self.assertIn("会不会太怂", self.last_result(model).content)
        self.assertEqual(advice.source, "model")

    def test_metric_and_claim_go_together(self):
        half = submit("Dropkick", reasons=[reason("伤害更高", "avg_damage", None)], tool_id="s1")
        advice, model = self.advise(reply(half), reply(submit("Dropkick", tool_id="s2")))
        self.assertIn("要么都填", self.last_result(model).content)
        self.assertEqual(advice.source, "model")

    def test_skip_cannot_be_chosen_when_the_game_does_not_offer_it(self):
        raw = copy.deepcopy(self.raw)
        raw["game_state"]["screen_state"]["skip_available"] = False
        state = to_visible(raw)
        three = ["Pommel Strike", "Dropkick", "Shockwave"]
        advice, model = self.advise(
            reply(submit(SKIP, ranking=[SKIP] + three, tool_id="s1")),
            reply(submit("Dropkick", ranking=["Dropkick", "Pommel Strike", "Shockwave"], tool_id="s2")),
            state=state,
        )
        self.assertEqual(advice.options, three)
        self.assertIn("必须是 options 里的一项", self.last_result(model).content)
        self.assertEqual(advice.choice, "Dropkick")

    # ---------- 工具 ----------

    def test_enemy_info_tool(self):
        ask = reply(ToolCall("t1", "enemy_info", {"monster_id": "SlimeBoss"}), ToolCall("t2", "enemy_info", {"monster_id": "Nobody"}))
        advice, model = self.advise(ask, reply(submit("Dropkick")))
        known, unknown = model.calls[1]["turns"][-1].results
        self.assertTrue(json.loads(known.content)["found"])
        self.assertFalse(json.loads(unknown.content)["found"])
        self.assertFalse(unknown.is_error)
        self.assertEqual(advice.tool_calls, 2)

    # ---------- 降级 ----------

    def test_model_unavailable_leaves_the_checkup(self):
        advice, _ = self.advise(ModelUnavailable("账户余额不足"))
        self.assertEqual((advice.source, advice.choice), ("checkup_only", None))
        self.assertIn("余额不足", advice.note)
        # 没有模型的结论，但程序算出的事实都在
        self.assertEqual(advice.options, OPTIONS)
        self.assertEqual(advice.checkup_now["deck_size"], 10)
        self.assertIn("Pommel Strike", advice.change_if_taken)
        self.assertTrue(advice.trials)

    def test_advice_that_never_passes_degrades(self):
        bad = [reply(submit("Demon Form", ranking=OPTIONS, tool_id=f"s{i}")) for i in range(3)]
        advice, model = self.advise(*bad)
        self.assertEqual((advice.source, advice.pushbacks), ("checkup_only", 2))
        self.assertIn("没有通过核对", advice.note)
        self.assertEqual(model.responses, [])

    def test_rejects_other_screens(self):
        campfire = to_visible({"in_game": True, "game_state": {"screen_type": "REST", "relics": []}})
        with self.assertRaises(ValueError):
            DeckAdvisor(ScriptedModel([])).advise(campfire)


if __name__ == "__main__":
    unittest.main()
