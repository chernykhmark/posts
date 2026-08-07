# agent/state.py
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage


class AgentState(TypedDict, total=False):
    # артефакты диалога (рабочая память до save_post)
    topic: str
    angle: str
    draft_text: str
    hooks: list
    hashtags: list
    image: str
    platform: str

    # служебные поля графа
    messages: Annotated[list[AnyMessage], add_messages]
    user_id: int


def initial_state(user_id: int) -> AgentState:
    """Начальное состояние нового черновика."""
    return {
        "messages": [],
        "user_id": user_id,
    }