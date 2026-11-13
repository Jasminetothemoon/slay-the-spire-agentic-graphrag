"""DeepSeek 适配层（默认供应商）。

按 DeepSeek 官方文档（api-docs.deepseek.com，2026-11 查阅）：
- 接口是 OpenAI 格式，base_url 为 https://api.deepseek.com，用 OpenAI 的 Python SDK 调用。
- 模型：deepseek-flash、deepseek-v4-pro。两者默认都开着思考模式。
- 思考模式下不能强制调用工具（tool_choice 为 required 或指定函数会返回 400），所以只用默认的 auto。
- 带工具的对话里，assistant 消息的 reasoning_content 必须原样传回，否则返回 400。
- 上下文缓存自动生效，不需要任何标记：把不变的系统提示放在最前面即可。

没有用 strict 模式：它需要 beta 的 base_url。工具参数由调用方自己核对。
凭据：环境变量 DEEPSEEK_API_KEY。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from sts_advisor.agents.llm import (
    MAX_TOKENS,
    AssistantTurn,
    ModelReply,
    ModelUnavailable,
    ToolCall,
    ToolSpec,
    ToolTurn,
    Turn,
    UserTurn,
)

BASE_URL = "https://api.deepseek.com"
API_KEY_ENV = "DEEPSEEK_API_KEY"


@dataclass(frozen=True)
class Tier:
    model: str
    reasoning_effort: str  # none / low / high / max


# 两个档位的初始设置，没有实测过，测出延迟和效果后再调
TIERS: dict[str, Tier] = {
    "fast": Tier(model="deepseek-flash", reasoning_effort="low"),
    "strong": Tier(model="deepseek-v4-pro", reasoning_effort="high"),
}

_STOP = {"tool_calls": "tool_calls", "stop": "end", "length": "truncated", "content_filter": "refused"}


def _to_messages(system: str, turns: list[Turn]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for turn in turns:
        if isinstance(turn, UserTurn):
            messages.append({"role": "user", "content": turn.content})
        elif isinstance(turn, AssistantTurn):
            messages.append(turn.reply.raw)
        elif isinstance(turn, ToolTurn):
            # 每个工具结果各占一条消息
            messages.extend(
                {"role": "tool", "tool_call_id": r.call_id, "content": r.content} for r in turn.results
            )
    return messages


def _to_reply(choice: Any) -> ModelReply:
    message = choice.message
    calls, raw_calls = [], []
    for call in message.tool_calls or []:
        raw_calls.append(
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments},
            }
        )
        try:
            calls.append(ToolCall(call.id, call.function.name, json.loads(call.function.arguments or "{}")))
        except json.JSONDecodeError as e:
            calls.append(ToolCall(call.id, call.function.name, None, error=f"参数不是合法的 JSON：{e}"))

    raw: dict[str, Any] = {"role": "assistant", "content": message.content or ""}
    reasoning = getattr(message, "reasoning_content", None)
    if reasoning is not None:
        raw["reasoning_content"] = reasoning
    if raw_calls:
        raw["tool_calls"] = raw_calls

    return ModelReply(
        stop=_STOP.get(choice.finish_reason, "other"),
        text=message.content or "",
        tool_calls=tuple(calls),
        raw=raw,
    )


class DeepSeekModel:
    def __init__(self, client: Any = None):
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            api_key = os.environ.get(API_KEY_ENV)
            if not api_key:
                raise ModelUnavailable(f"没有配置 {API_KEY_ENV}")
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key, base_url=BASE_URL)
        return self._client

    def create(self, *, tier: str, system: str, tools: list[ToolSpec], turns: list[Turn]) -> ModelReply:
        import openai

        cfg = TIERS[tier]
        client = self._get_client()
        try:
            response = client.chat.completions.create(
                model=cfg.model,
                max_tokens=MAX_TOKENS,
                reasoning_effort=cfg.reasoning_effort,
                messages=_to_messages(system, turns),
                tools=[
                    {
                        "type": "function",
                        "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
                    }
                    for t in tools
                ],
            )
        except openai.AuthenticationError as e:
            raise ModelUnavailable("API key 无效") from e
        except openai.RateLimitError as e:
            raise ModelUnavailable("请求过快或超出并发限制") from e
        except openai.APIStatusError as e:
            if e.status_code == 402:
                raise ModelUnavailable("账户余额不足") from e
            if e.status_code >= 500:
                raise ModelUnavailable(f"服务端出错或过载（{e.status_code}）") from e
            raise  # 其余 4xx 是请求写错了，应该暴露出来修，不该悄悄降级
        except openai.APIConnectionError as e:
            raise ModelUnavailable("网络不通或超时") from e
        return _to_reply(response.choices[0])
