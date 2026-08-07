# agent/graph.py
import logging

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from agent.checkpointer import get_checkpointer
from agent.nodes import (
    GENERATION_TOOLS,
    agent_node,
    confirm_angle_node,
    confirm_draft_node,
    critique_node,
    tool_node,
)
from agent.state import AgentState

logger = logging.getLogger(__name__)

_graph = None


def _route_after_agent(state) -> str:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return END


def _route_after_tools(state) -> str:
    # после generation-инструмента → critique
    if state.get("last_generation_tool") in GENERATION_TOOLS:
        return "critique"
    # после make_angle → подтверждение угла (если не auto_mode)
    if state.get("pending_angle_confirm"):
        if state.get("auto_mode"):
            return "agent"
        return "confirm_angle"
    return "agent"


def _route_after_critique(state) -> str:
    last = state["messages"][-1] if state.get("messages") else None
    # critique попросил доработку → синтетический tool_call → tools
    if last is not None and getattr(last, "tool_calls", None):
        return "tools"
    # critique ok → показать текст юзеру (пауза)
    return "confirm_draft"


def build_graph(checkpointer=None):
    if checkpointer is None:
        checkpointer = get_checkpointer()

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.add_node("critique", critique_node)
    builder.add_node("confirm_angle", confirm_angle_node)
    builder.add_node("confirm_draft", confirm_draft_node)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", _route_after_agent, {"tools": "tools", END: END})
    builder.add_conditional_edges(
        "tools", _route_after_tools,
        {"critique": "critique", "confirm_angle": "confirm_angle", "agent": "agent"},
    )
    builder.add_conditional_edges(
        "critique", _route_after_critique,
        {"tools": "tools", "confirm_draft": "confirm_draft"},
    )
    # после паузы резолв через оркестратор (D-7, D-39)
    builder.add_edge("confirm_angle", "agent")
    builder.add_edge("confirm_draft", "agent")

    global _graph
    _graph = builder.compile(checkpointer=checkpointer)
    logger.info("graph compiled")
    return _graph


def get_graph():
    return _graph


async def run_graph(thread_id: str, user_message: str, user_id: int) -> dict:
    from langchain_core.messages import HumanMessage
    from db import get_db
    from db.repositories import StyleProfilesRepo, UsersRepo

    global _graph
    if _graph is None:
        _graph = build_graph(get_checkpointer())

    config = {"configurable": {"thread_id": thread_id}}

    # стоим ли на паузе (interrupt) по этому thread — определяем из checkpointer (D-39)
    resuming = False
    try:
        snapshot = await _graph.aget_state(config)
        resuming = bool(getattr(snapshot, "next", None))
    except Exception:
        logger.exception("[graph.py] не удалось прочитать state для resume-check")

    if resuming:
        # резолв interrupt: значение уходит в узел паузы → HumanMessage → agent_node
        logger.info("[graph.py] resume interrupt на thread=%s", thread_id)
        result = await _graph.ainvoke(Command(resume=user_message), config=config)
        return _format_result(result)

    # обычный прогон
    style_description = ""
    auto_mode = False
    try:
        pool = get_db().pool
        profile = await StyleProfilesRepo(pool).get(user_id)
        if profile:
            style_description = profile if isinstance(profile, str) else profile.get("style_description", "")
        auto_mode = await UsersRepo(pool).get_auto_mode(user_id)
    except Exception:
        logger.exception("[graph.py] не удалось подтянуть стиль/auto_mode")

    input_state = {
        "messages": [HumanMessage(content=user_message)],
        "user_id": user_id,
        "auto_mode": bool(auto_mode),
    }
    if style_description:
        input_state["style_description"] = style_description

    result = await _graph.ainvoke(input_state, config=config)
    return _format_result(result)


def _format_result(result: dict) -> dict:
    """Разбор результата: interrupt (пауза) vs обычный ответ (D-26, D-39)."""
    interrupts = result.get("__interrupt__")
    if interrupts:
        intr = interrupts[0]
        payload = getattr(intr, "value", intr)
        question = payload.get("question") if isinstance(payload, dict) else str(payload)
        return {"reply": question, "interrupt": question}

    messages = result.get("messages") or []
    last = messages[-1] if messages else None
    reply = getattr(last, "content", "") if last is not None else ""
    return {"reply": reply or "", "interrupt": None}