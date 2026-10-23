from fastapi import APIRouter

# The AI slice exposes no endpoints; other slices inject its orchestrator via app.ai.dependencies.
router = APIRouter(tags=["ai"])
