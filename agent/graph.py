# agent/graph.py
import logging

from langgraph.graph import END, START, StateGraph

from agent.checkpointer import get_checkpointer
from agent.nodes import GENERATION_TOOLS, agent_node, critique_node, tool_node
from agent.state import AgentState, initial_state

logger = logging.getLogger(__name__)

_graph = None


def _route_after_agent(state) -> str:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return END


def _route_after_tools(state) -> str:
    if state.get("last_generation_tool") in GENERATION_TOOLS:
        return "critique"
    return "agent"


def _route_after_critique(state) -> str:
    last = state["messages"][-1] if state.get("messages") else None
    if last is not None and getattr(last, "tool_calls", None):
        return "tools"
    return "agent"


# agent/graph.py  (замени функцию build_graph и get_graph целиком)
def build_graph(checkpointer=None):
    if checkpointer is None:
        checkpointer = get_checkpointer()

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.add_node("critique", critique_node)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", _route_after_agent, {"tools": "tools", END: END})
    builder.add_conditional_edges("tools", _route_after_tools, {"critique": "critique", "agent": "agent"})
    builder.add_conditional_edges("critique", _route_after_critique, {"tools": "tools", "agent": "agent"})

    global _graph
    _graph = builder.compile(checkpointer=checkpointer)
    logger.info("graph compiled")
    return _graph

def get_graph():
    return _graph


# agent/graph.py
# agent/graph.py
async def run_graph(thread_id: str, user_message: str, user_id: int) -> dict:
    from langchain_core.messages import HumanMessage
    from db import get_db
    from db.repositories import StyleProfilesRepo

    global _graph
    if _graph is None:
        _graph = build_graph(get_checkpointer())

    config = {"configurable": {"thread_id": thread_id}}

    # подтягиваем стиль юзера в state
    style_description = ""
    try:
        pool = get_db().pool
        profile = await StyleProfilesRepo(pool).get(user_id)
        if profile:
            style_description = profile if isinstance(profile, str) else profile.get("style_description", "")
    except Exception:
        logger.exception("[graph.py] не удалось подтянуть стиль")

    input_state = {
        "messages": [HumanMessage(content=user_message)],
        "user_id": user_id,
    }
    if style_description:
        input_state["style_description"] = style_description

    result = await _graph.ainvoke(input_state, config=config)

    last = result["messages"][-1]
    reply = getattr(last, "content", "") or ""
    return {"reply": reply, "interrupt": None}