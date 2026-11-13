"""判断层用的模型接口。不绑定供应商。

Agent 的逻辑只依赖这里的 Model 协议和几个数据类型：
- 对话记录用下面三种 Turn 表示，由各家的适配层翻译成自己的消息格式；
- 模型的回答统一成 ModelReply；
- 最终答案也通过工具调用提交，这样不依赖各家各不相同的「结构化输出」功能。

适配层：
- llm_deepseek.py：DeepSeek，默认。
- llm_claude.py：Claude，可选。

模型分档（docs/v2_design.md 改动点 7）：fast 用于普通小怪战，strong 用于精英和 Boss。
每家适配层各自规定两个档位用哪个模型。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, Union

MAX_TOKENS = 16000
PROVIDER_ENV = "STS_ADVISOR_PROVIDER"
DEFAULT_PROVIDER = "deepseek"


class ModelUnavailable(RuntimeError):
    """模型这次调不通：没有凭据、余额不足、限流、超时、服务端出错等。调用方据此降级。"""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    args: Any  # 解析好的参数；模型给的不是合法 JSON 时为 None
    error: str = ""  # 参数解析失败的原因


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    content: str
    is_error: bool = False


@dataclass(frozen=True)
class ModelReply:
    # tool_calls：模型要调用工具；end：模型说完了，没有调用工具；
    # truncated：回答被长度上限截断；refused：被拒答；other：其他原因停下
    stop: Literal["tool_calls", "end", "truncated", "refused", "other"]
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    raw: Any = None  # 供应商原样的 assistant 消息，回放对话时原样发回（推理内容等都在里面）


@dataclass(frozen=True)
class UserTurn:
    content: str


@dataclass(frozen=True)
class AssistantTurn:
    reply: ModelReply


@dataclass(frozen=True)
class ToolTurn:
    results: tuple[ToolResult, ...] = field(default_factory=tuple)


Turn = Union[UserTurn, AssistantTurn, ToolTurn]


class Model(Protocol):
    def create(self, *, tier: str, system: str, tools: list[ToolSpec], turns: list[Turn]) -> ModelReply: ...


def default_model() -> Model:
    """按环境变量 STS_ADVISOR_PROVIDER 选供应商，默认 DeepSeek。"""
    provider = os.environ.get(PROVIDER_ENV, DEFAULT_PROVIDER).strip().lower()
    if provider == "deepseek":
        from sts_advisor.agents.llm_deepseek import DeepSeekModel

        return DeepSeekModel()
    if provider == "claude":
        from sts_advisor.agents.llm_claude import ClaudeModel

        return ClaudeModel()
    raise ValueError(f"不认识的供应商：{provider}。可选 deepseek、claude")
