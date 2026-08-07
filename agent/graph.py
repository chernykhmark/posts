# agent/graph.py
"""
Сборка графа: agent_node → (есть tool_calls?) → tool_node → agent_node → ... → END.
run_graph возвращает {"reply", "interrupt"} (D-26).
"""
import logging

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from agent.checkpointer import get_checkpointer
from agent.nodes import agent_node, tool_node
from agent.state import AgentState, initial_state
from db import get_db
from db.repositories import StyleProfilesRepo

logger = logging.getLogger(__name__)

_graph = None


def _route_after_agent(state: AgentState) -> str:
    """Если оркестратор выбрал инструмент — идём в tool_node, иначе завершаем."""
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return END


def build_graph():
    """Компиляция графа с checkpointer."""
    global _graph
    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", _route_after_agent, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")  # результат tool возвращается оркестратору

    _graph = builder.compile(checkpointer=get_checkpointer())
    logger.info("graph compiled")
    return _graph


def get_graph():
    if _graph is None:
        raise RuntimeError("graph not built")
    return _graph


async def run_graph(thread_id: str, user_message: str, user_id: int) -> dict:
    """Прогон графа по thread_id. Возвращает {"reply", "interrupt"}."""
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    # текущее состояние thread (может быть пустым для нового черновика)
    snapshot = await graph.aget_state(config)
    if not snapshot.values:
        # инициализируем служебные поля нового черновика
        base = initial_state(user_id)
        # D-32: подтянуть стиль в state, чтобы agent_node знал ветку 4.2 с первого хода
        try:
            style = await StyleProfilesRepo(get_db().pool).get(user_id)
            if style:
                base["style_description"] = style
        except Exception as e:
            logger.warning("failed to load style_description into state: %s", e)
    else:
        base = {}

    input_state = {
        **base,
        "user_id": user_id,
        "messages": [HumanMessage(content=user_message)],
    }

    result = await graph.ainvoke(input_state, config)

    # ответ юзеру — последний AIMessage без tool_calls
    reply = ""
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
            reply = msg.content or ""
            break

    if not reply:
        reply = "Готово."  # на случай пустого ответа

    return {"reply": reply, "interrupt": None}  # interrupt-ветка — этап 9