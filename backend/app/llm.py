"""LLM 抽象层 — 统一 OpenAI / Anthropic 接口，方便后续切换 provider"""
from __future__ import annotations

from app.config import settings


def get_llm():
    """根据 settings.llm_provider 创建对应的 LLM 实例"""
    if settings.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=0.3,
        )
    else:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            temperature=0.3,
        )
