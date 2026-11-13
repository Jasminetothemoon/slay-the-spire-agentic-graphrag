"""各个顾问共用的调用循环。

约定：模型可以多次调用查询类的工具，最后必须调用一个「提交」工具给出答案。
提交的答案由调用方核对：
- 通过，循环结束；
- 不通过，原因作为提交工具的结果退回去，让模型修正，最多打回若干次；
- 模型只写文字不提交，也算一次打回。
模型调不通、被拒答、被截断，或始终过不了核对时，循环以失败结束，由调用方降级。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sts_advisor.agents.llm import (
    AssistantTurn,
    Model,
    ModelUnavailable,
    ToolCall,
    ToolResult,
    ToolSpec,
    ToolTurn,
    Turn,
    UserTurn,
)

MAX_MODEL_CALLS = 8  # 一次建议最多调几次模型（含工具往返）
MAX_PUSHBACKS = 2  # 答案没通过核对时，最多打回几次

# 核对函数：收到提交的参数，返回 (要退回的原因；None 表示通过, 通过时要带出去的东西)
Check = Callable[[Any], tuple[str | None, Any]]
RunTool = Callable[[ToolCall], ToolResult]


def no_submit_message(submit_tool: str) -> str:
    return f"你没有调用 {submit_tool}。请用 {submit_tool} 工具提交你的答案。"


@dataclass
class LoopOutcome:
    accepted: bool
    submitted: Any = None  # 通过核对的那次提交的参数
    payload: Any = None  # 核对函数带出来的东西
    note: str = ""  # 失败的原因
    model_calls: int = 0
    tool_calls: int = 0
    pushbacks: int = 0

    @property
    def stats(self) -> dict[str, int]:
        return {"model_calls": self.model_calls, "tool_calls": self.tool_calls, "pushbacks": self.pushbacks}


def run(
    *,
    model: Model,
    tier: str,
    system: str,
    tools: list[ToolSpec],
    first_message: str,
    submit_tool: str,
    run_tool: RunTool,
    check: Check,
    max_model_calls: int = MAX_MODEL_CALLS,
    max_pushbacks: int = MAX_PUSHBACKS,
) -> LoopOutcome:
    turns: list[Turn] = [UserTurn(first_message)]
    out = LoopOutcome(accepted=False)
    last_problem = ""

    while out.model_calls < max_model_calls:
        try:
            reply = model.create(tier=tier, system=system, tools=tools, turns=turns)
        except ModelUnavailable as e:
            out.note = f"模型不可用：{e}"
            return out
        out.model_calls += 1

        if reply.stop in ("truncated", "refused", "other"):
            out.note = f"模型没有给出完整回答（{reply.stop}）"
            return out

        turns.append(AssistantTurn(reply))

        if not reply.tool_calls:
            # 只写了文字，没有提交
            last_problem = no_submit_message(submit_tool)
            if out.pushbacks >= max_pushbacks:
                break
            out.pushbacks += 1
            turns.append(UserTurn(last_problem))
            continue

        results: list[ToolResult] = []
        rejected = False
        for call in reply.tool_calls:
            if call.name != submit_tool:
                results.append(run_tool(call))
                out.tool_calls += 1
                continue
            submitted = call.args if call.args is not None else {}
            problem, payload = check(submitted)
            if problem is None:
                out.accepted, out.submitted, out.payload = True, submitted, payload
                return out
            last_problem = problem
            rejected = True
            results.append(ToolResult(call.id, problem, is_error=True))

        if rejected:
            if out.pushbacks >= max_pushbacks:
                break
            out.pushbacks += 1
        # 同一轮的所有工具结果一起发回
        turns.append(ToolTurn(tuple(results)))

    out.note = f"答案没有通过核对：{last_problem}" if last_problem else "超过了模型调用次数上限"
    return out
