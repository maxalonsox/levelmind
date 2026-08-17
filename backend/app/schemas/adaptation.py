from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.ai.adaptation.contracts import AdaptationProposal
from app.models.enums import AdaptationStatus


class PlanAdaptationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    goal_id: UUID
    proposal: AdaptationProposal
    status: AdaptationStatus
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None


class AdaptationPreviewResponse(AdaptationProposal):
    needs_adaptation: bool
    adaptation: PlanAdaptationResponse | None
