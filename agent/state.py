# agent/state.py
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    user_id: int

    style_description: str

    topic: str
    angle: str
    draft_text: str
    hooks: Any
    hashtags: Any
    image: Any
    platform: str

    # critique-цикл (этап 8)
    critique_iterations: int
    critique_issues: list[str]
    critique_candidates: list[dict]
    last_generation_tool: str
    cta_requested: bool

    # HITL (этап 9)
    auto_mode: bool
    pending_angle_confirm: bool

    # сохранение (этап 10, D-40)
    saved: bool
    saved_post_ids: list[int]


def initial_state(user_id: int) -> AgentState:
    return {
        "messages": [],
        "user_id": user_id,
        "topic": "",
        "angle": "",
        "draft_text": "",
        "hooks": None,
        "hashtags": None,
        "image": None,
        "platform": "",
        "style_description": "",
        "critique_iterations": 0,
        "critique_issues": [],
        "critique_candidates": [],
        "last_generation_tool": "",
        "cta_requested": False,
        "saved": False,
        "saved_post_ids": [],
    }