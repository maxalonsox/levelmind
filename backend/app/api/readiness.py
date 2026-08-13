import logging
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.db.check import DatabaseConnectionError, check_database_connection

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check(response: Response) -> ReadinessResponse:
    try:
        check_database_connection()
    except DatabaseConnectionError:
        logger.warning("Database readiness check failed")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="not_ready")

    return ReadinessResponse(status="ready")
