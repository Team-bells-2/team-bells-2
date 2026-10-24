from fastapi import Depends

from app.ai.orchestrator import AIOrchestrator
from app.shared.env import settings
from app.shared.Infrastructure.llm.client import LLMClient, get_llm_client

# Factories only, so other slices can inject the AI orchestrator without importing routers.


def get_ai_orchestrator(llm_client: LLMClient = Depends(get_llm_client)) -> AIOrchestrator:
    return AIOrchestrator(llm_client, settings.DEMO_MODE)
