"""两家适配层的测试：只检查发出去的请求和回答的翻译，用假的客户端接住，不联网。"""
import importlib.util
import os
import unittest
from types import SimpleNamespace
from unittest import mock

from sts_advisor.agents.llm import (
    AssistantTurn,
    ModelReply,
    ModelUnavailable,
    ToolResult,
    ToolSpec,
    ToolTurn,
    UserTurn,
    default_model,
)

TOOL = ToolSpec("settle", "结算", {"type": "object", "properties": {}, "required": [], "additionalProperties": False})


class Recorder:
    def __init__(self, response):
        self.kwargs = None
        self.response = response

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


# ---------------------------------------------------------------- DeepSeek


def deepseek_response(finish_reason="stop", content="", reasoning=None, tool_calls=None):
    message = SimpleNamespace(content=content, reasoning_content=reasoning, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish_reason, message=message)])


def deepseek_call(call_id, name, arguments):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


@unittest.skipUnless(importlib.util.find_spec("openai"), "没有安装 openai")
class DeepSeekModelTest(unittest.TestCase):
    def make(self, response):
        from sts_advisor.agents.llm_deepseek import DeepSeekModel

        recorder = Recorder(response)
        client = SimpleNamespace(chat=SimpleNamespace(completions=recorder))
        return DeepSeekModel(client), recorder

    def test_request_shape(self):
        from sts_advisor.agents.llm_deepseek import TIERS

        for tier in ("fast", "strong"):
            with self.subTest(tier):
                model, recorder = self.make(deepseek_response())
                model.create(tier=tier, system="系统提示", tools=[TOOL], turns=[UserTurn("局面")])
                sent = recorder.kwargs
                self.assertEqual(sent["model"], TIERS[tier].model)
                self.assertEqual(sent["reasoning_effort"], TIERS[tier].reasoning_effort)
                self.assertEqual(sent["messages"][0], {"role": "system", "content": "系统提示"})
                self.assertEqual(sent["messages"][1], {"role": "user", "content": "局面"})
                self.assertEqual(
                    sent["tools"],
                    [{"type": "function", "function": {"name": "settle", "description": "结算", "parameters": TOOL.parameters}}],
                )
                # 思考模式下强制调用工具会返回 400，所以不传 tool_choice
                self.assertNotIn("tool_choice", sent)

    def test_tool_loop_replays_reasoning_and_sends_one_message_per_result(self):
        raw = {
            "role": "assistant",
            "content": "",
            "reasoning_content": "先试算",
            "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "settle", "arguments": "{}"}}],
        }
        turns = [
            UserTurn("局面"),
            AssistantTurn(ModelReply(stop="tool_calls", raw=raw)),
            ToolTurn((ToolResult("c1", "结果一"), ToolResult("c2", "结果二", is_error=True))),
        ]
        model, recorder = self.make(deepseek_response())
        model.create(tier="fast", system="s", tools=[TOOL], turns=turns)
        messages = recorder.kwargs["messages"]
        self.assertIs(messages[2], raw)  # 推理内容随 assistant 消息原样传回
        self.assertEqual(messages[3], {"role": "tool", "tool_call_id": "c1", "content": "结果一"})
        self.assertEqual(messages[4], {"role": "tool", "tool_call_id": "c2", "content": "结果二"})

    def test_reply_with_tool_calls(self):
        response = deepseek_response(
            finish_reason="tool_calls",
            reasoning="想一想",
            tool_calls=[deepseek_call("c1", "settle", '{"plays": []}'), deepseek_call("c2", "settle", "{不是 json")],
        )
        model, _ = self.make(response)
        reply = model.create(tier="fast", system="s", tools=[TOOL], turns=[UserTurn("局面")])

        self.assertEqual(reply.stop, "tool_calls")
        self.assertEqual(reply.tool_calls[0].args, {"plays": []})
        self.assertIsNone(reply.tool_calls[1].args)  # 参数不是合法 JSON：交给调用方当工具错误处理
        self.assertIn("JSON", reply.tool_calls[1].error)
        self.assertEqual(reply.raw["reasoning_content"], "想一想")
        self.assertEqual(reply.raw["tool_calls"][1]["function"]["arguments"], "{不是 json")

    def test_finish_reasons(self):
        for finish, stop in (("stop", "end"), ("length", "truncated"), ("content_filter", "refused"), ("???", "other")):
            with self.subTest(finish):
                model, _ = self.make(deepseek_response(finish_reason=finish, content="文字"))
                reply = model.create(tier="fast", system="s", tools=[], turns=[UserTurn("局面")])
                self.assertEqual((reply.stop, reply.text), (stop, "文字"))

    def test_missing_api_key(self):
        from sts_advisor.agents.llm_deepseek import API_KEY_ENV, DeepSeekModel

        with mock.patch.dict(os.environ, clear=False):
            os.environ.pop(API_KEY_ENV, None)
            with self.assertRaises(ModelUnavailable):
                DeepSeekModel().create(tier="fast", system="s", tools=[], turns=[UserTurn("局面")])


# ---------------------------------------------------------------- Claude


def claude_response(stop_reason="end_turn", blocks=()):
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocks))


@unittest.skipUnless(importlib.util.find_spec("anthropic"), "没有安装 anthropic")
class ClaudeModelTest(unittest.TestCase):
    def make(self, response=None):
        from sts_advisor.agents.llm_claude import ClaudeModel

        plain, beta = Recorder(response or claude_response()), Recorder(response or claude_response())
        client = SimpleNamespace(messages=plain, beta=SimpleNamespace(messages=beta))
        return ClaudeModel(client), plain, beta

    def test_fast_tier_uses_plain_endpoint(self):
        from sts_advisor.agents.llm_claude import TIERS

        model, plain, beta = self.make()
        model.create(tier="fast", system="系统提示", tools=[TOOL], turns=[UserTurn("局面")])
        self.assertIsNone(beta.kwargs)
        sent = plain.kwargs
        self.assertEqual(sent["model"], TIERS["fast"].model)
        self.assertEqual(sent["output_config"], {"effort": TIERS["fast"].effort})
        self.assertEqual(sent["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(sent["tools"][0]["input_schema"], TOOL.parameters)
        self.assertTrue(sent["tools"][0]["strict"])
        for absent in ("tool_choice", "thinking", "betas", "fallbacks"):
            self.assertNotIn(absent, sent)

    def test_strong_tier_enables_server_side_fallback(self):
        from sts_advisor.agents.llm_claude import FALLBACK_BETA, TIERS

        model, plain, beta = self.make()
        model.create(tier="strong", system="s", tools=[TOOL], turns=[UserTurn("局面")])
        self.assertIsNone(plain.kwargs)
        self.assertEqual(beta.kwargs["model"], TIERS["strong"].model)
        self.assertEqual(beta.kwargs["betas"], [FALLBACK_BETA])
        self.assertEqual(beta.kwargs["fallbacks"], "default")

    def test_tool_results_go_back_in_one_user_message(self):
        blocks = [SimpleNamespace(type="thinking"), SimpleNamespace(type="tool_use", id="c1", name="settle", input={})]
        turns = [
            UserTurn("局面"),
            AssistantTurn(ModelReply(stop="tool_calls", raw=blocks)),
            ToolTurn((ToolResult("c1", "结果一"), ToolResult("c2", "结果二", is_error=True))),
        ]
        model, plain, _ = self.make()
        model.create(tier="fast", system="s", tools=[TOOL], turns=turns)
        messages = plain.kwargs["messages"]
        self.assertIs(messages[1]["content"], blocks)  # 含思考块，原样发回
        self.assertEqual(
            messages[2],
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "c1", "content": "结果一"},
                    {"type": "tool_result", "tool_use_id": "c2", "content": "结果二", "is_error": True},
                ],
            },
        )

    def test_reply_translation(self):
        blocks = [
            SimpleNamespace(type="thinking"),
            SimpleNamespace(type="text", text="先试算"),
            SimpleNamespace(type="tool_use", id="c1", name="settle", input={"plays": []}),
        ]
        model, _, _ = self.make(claude_response("tool_use", blocks))
        reply = model.create(tier="fast", system="s", tools=[TOOL], turns=[UserTurn("局面")])
        self.assertEqual((reply.stop, reply.text), ("tool_calls", "先试算"))
        self.assertEqual(reply.tool_calls[0].args, {"plays": []})
        self.assertEqual(reply.raw, blocks)  # 含思考块的完整内容，留着回放

    def test_stop_reasons(self):
        for stop_reason, stop in (("end_turn", "end"), ("max_tokens", "truncated"), ("refusal", "refused"), ("pause_turn", "other")):
            with self.subTest(stop_reason):
                model, _, _ = self.make(claude_response(stop_reason))
                reply = model.create(tier="fast", system="s", tools=[], turns=[UserTurn("局面")])
                self.assertEqual(reply.stop, stop)


# ---------------------------------------------------------------- 默认供应商


class DefaultModelTest(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("openai"), "没有安装 openai")
    def test_default_is_deepseek(self):
        with mock.patch.dict(os.environ, clear=False):
            os.environ.pop("STS_ADVISOR_PROVIDER", None)
            self.assertEqual(type(default_model()).__name__, "DeepSeekModel")

    def test_unknown_provider(self):
        with mock.patch.dict(os.environ, {"STS_ADVISOR_PROVIDER": "不存在"}):
            with self.assertRaises(ValueError):
                default_model()


if __name__ == "__main__":
    unittest.main()
