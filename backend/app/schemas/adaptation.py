from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.ai.adaptation.contracts import AdaptationProposal
from app.models.enums import AdaptationStatus


class PlanAdaptationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    goal_id: UUID
    base_revision_id: UUID | None
    proposal: AdaptationProposal
    status: AdaptationStatus
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None


class AdaptationPreviewResponse(AdaptationProposal):
    needs_adaptation: bool
    adaptation: PlanAdaptationResponse | None


class AdaptationAcceptResponse(BaseModel):
    adaptation_id: UUID
    status: AdaptationStatus
    reviewed_at: datetime
    revision_id: UUID
    revision_number: int = Field(gt=0)
    applied_change_count: int = Field(gt=0)


class AdaptationRejectResponse(BaseModel):
    adaptation_id: UUID
    status: Literal[AdaptationStatus.REJECTED]
    reviewed_at: datetime
