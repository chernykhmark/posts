# agent/llm.py
"""
LLM-клиент на OpenRouter (ChatOpenAI) с ретраями, фоллбэком и учётом usage.
usage_costs пишется ПОСЛЕ каждого вызова (D-8).
"""
import logging

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from config import settings
from db import get_db
from db.repositories import UsageCostsRepo

logger = logging.getLogger(__name__)

# usage: include=true просим OpenRouter вернуть usage/cost в теле ответа
_EXTRA_BODY = {"usage": {"include": True}}


def _make_llm(model: str, tools, temperature: float) -> ChatOpenAI:
    llm = ChatOpenAI(
        model=model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=temperature,
        max_retries=2,  # ретраи на таймаут/5xx (раздел 12)
        extra_body=_EXTRA_BODY,
    )
    if tools:
        return llm.bind_tools(tools)
    return llm


async def _log_usage(user_id: int | None, model: str, msg: AIMessage) -> None:
    """Извлечь usage из ответа и записать в usage_costs (D-8).
    tokens пишутся всегда; cost — если пришёл, иначе 0."""
    try:
        meta = getattr(msg, "response_metadata", {}) or {}
        usage = meta.get("token_usage") or meta.get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens", 0) or 0)
        tokens_out = int(usage.get("completion_tokens", 0) or 0)
        # OpenRouter кладёт cost в usage.cost при usage.include=true
        cost = usage.get("cost")
        cost = float(cost) if cost is not None else 0.0

        repo = UsageCostsRepo(get_db().pool)
        await repo.log_cost(
            user_id=user_id,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
        )
    except Exception as e:  # лог затрат не должен ронять диалог
        logger.warning("usage_costs log failed: %s", e)


async def call_orchestrator(messages: list, user_id: int | None, tools) -> AIMessage:
    """Вызов оркестратора с фоллбэком. Возвращает AIMessage (возможно с tool_calls)."""
    primary = settings.models.orchestrator
    fallback = settings.models.fallback_orchestrator

    for model in (primary, fallback):
        try:
            llm = _make_llm(model, tools, temperature=0.7)
            msg: AIMessage = await llm.ainvoke(messages)
            await _log_usage(user_id, model, msg)
            return msg
        except Exception as e:
            logger.error("orchestrator model %s failed: %s", model, e)
            if model == fallback:
                raise

    raise RuntimeError("no orchestrator model available")


async def call_llm(
    messages: list,
    model: str,
    user_id: int | None,
    temperature: float = 0.7,
) -> str:
    """Одиночный вызов LLM без tools (генерация/анализ). Возвращает текст.
    usage логируется (D-8). Ретраи внутри ChatOpenAI (max_retries=2)."""
    llm = _make_llm(model, tools=None, temperature=temperature)
    try:
        msg: AIMessage = await llm.ainvoke(messages)
    except Exception as e:
        logger.error("call_llm model %s failed: %s", model, e)
        raise
    await _log_usage(user_id, model, msg)
    content = msg.content
    if isinstance(content, list):
        # некоторые модели возвращают список блоков — склеиваем текстовые
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return (content or "").strip()