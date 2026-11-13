"""Claude 适配层（可选供应商，设 STS_ADVISOR_PROVIDER=claude 启用）。

用 Anthropic 官方 SDK。需要另外安装：pip install -e ".[claude]"
凭据由 SDK 从环境里取（ANTHROPIC_API_KEY，或 ant auth login 的配置）。

- 这两个模型不接受强制调用工具，所以只用默认的 auto；工具开 strict 保证参数符合 schema。
- 这两个模型默认开着自适应思考，不传 thinking；深度由 effort 控制。
- 不变的系统提示打缓存标记；会变的局面在 messages 里。
"""
from __future__ import annotations

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

FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass(frozen=True)
class Tier:
    model: str
    effort: str
    # Claude Opus 5.5 的安全分类器可能拒答；打开服务端回退后，被拒的请求会自动换模型重跑。
    # Claude Haiku 5.5 没有服务端回退。
    server_fallback: bool


# 两个档位的初始设置，没有实测过
TIERS: dict[str, Tier] = {
    "fast": Tier(model="claude-haiku-5-5", effort="low", server_fallback=False),
    "strong": Tier(model="claude-opus-5-5", effort="medium", server_fallback=True),
}

_STOP = {"tool_use": "tool_calls", "end_turn": "end", "max_tokens": "truncated", "refusal": "refused"}


def _to_messages(turns: list[Turn]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for turn in turns:
        if isinstance(turn, UserTurn):
            messages.append({"role": "user", "content": turn.content})
        elif isinstance(turn, AssistantTurn):
            messages.append({"role": "assistant", "content": turn.reply.raw})
        elif isinstance(turn, ToolTurn):
            # 同一轮的工具结果必须放在同一条 user 消息里
            blocks = []
            for r in turn.results:
                block: dict[str, Any] = {"type": "tool_result", "tool_use_id": r.call_id, "content": r.content}
                if r.is_error:
                    block["is_error"] = True
                blocks.append(block)
            messages.append({"role": "user", "content": blocks})
    return messages


def _to_reply(response: Any) -> ModelReply:
    return ModelReply(
        stop=_STOP.get(response.stop_reason, "other"),
        text="".join(b.text for b in response.content if b.type == "text"),
        tool_calls=tuple(ToolCall(b.id, b.name, b.input) for b in response.content if b.type == "tool_use"),
        raw=response.content,  # 含思考块，回放时要原样发回
    )


class ClaudeModel:
    def __init__(self, client: Any = None):
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def create(self, *, tier: str, system: str, tools: list[ToolSpec], turns: list[Turn]) -> ModelReply:
        import anthropic

        cfg = TIERS[tier]
        client = self._get_client()
        request: dict[str, Any] = dict(
            model=cfg.model,
            max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=[
                {"name": t.name, "description": t.description, "input_schema": t.parameters, "strict": True}
                for t in tools
            ],
            messages=_to_messages(turns),
            output_config={"effort": cfg.effort},
        )
        try:
            if cfg.server_fallback:
                response = client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **request)
            else:
                response = client.messages.create(**request)
        except anthropic.AuthenticationError as e:
            raise ModelUnavailable("凭据无效或没有配置") from e
        except anthropic.RateLimitError as e:
            raise ModelUnavailable("被限流") from e
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                raise ModelUnavailable(f"服务端出错（{e.status_code}）") from e
            raise  # 其余 4xx 是请求写错了，应该暴露出来修，不该悄悄降级
        except anthropic.APIConnectionError as e:
            raise ModelUnavailable("网络不通或超时") from e
        return _to_reply(response)
