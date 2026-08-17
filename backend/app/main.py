from fastapi import FastAPI

from app.api.adaptation_accept import router as adaptation_accept_router
from app.api.adaptation_preview import router as adaptation_preview_router
from app.api.evaluation_preview import router as evaluation_preview_router
from app.api.goals import router as goals_router
from app.api.goal_plan import router as goal_plan_router
from app.api.health import router as health_router
from app.api.missions import router as missions_router
from app.api.plan_accept import router as plan_accept_router
from app.api.plan_preview import router as plan_preview_router
from app.api.readiness import router as readiness_router
from app.api.stages import router as stages_router
from app.api.tasks import router as tasks_router
from app.api.task_results import router as task_results_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.include_router(health_router)
app.include_router(readiness_router)
app.include_router(goals_router)
app.include_router(stages_router)
app.include_router(missions_router)
app.include_router(tasks_router)
app.include_router(plan_preview_router)
app.include_router(plan_accept_router)
app.include_router(task_results_router)
app.include_router(goal_plan_router)
app.include_router(evaluation_preview_router)
app.include_router(adaptation_preview_router)
app.include_router(adaptation_accept_router)
