import logging
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from app.ai.adaptation.contracts import (
    AdaptationContext,
    AdaptationDecision,
    AdaptationLLMProvider,
    AdaptationMissionOutline,
    AdaptationMissionTarget,
    AdaptationProposal,
    AdaptationStageOutline,
    AdaptationTaskTarget,
    AddTaskChange,
    ReorderTaskChange,
)
from app.ai.adaptation.errors import (
    InvalidAdaptationProposalError,
    InvalidAdaptationTargetError,
)
from app.ai.evaluation.contracts import EvaluationResult

logger = logging.getLogger(__name__)

AdaptationProviderFactory = Callable[[], AdaptationLLMProvider]


class AdaptationService:
    def __init__(self, provider_factory: AdaptationProviderFactory) -> None:
        self._provider_factory = provider_factory

    async def propose(
        self,
        evaluation: EvaluationResult,
        context: AdaptationContext | None = None,
    ) -> AdaptationProposal:
        logger.info(
            "Adaptation preview started",
            extra={
                "evaluation_status": evaluation.status.value,
                "needs_adaptation": evaluation.needs_adaptation,
            },
        )
        if not evaluation.needs_adaptation:
            logger.info(
                "Adaptation preview completed deterministically",
                extra={"llm_invoked": False, "decision": "no_change"},
            )
            return build_no_change_proposal(evaluation)
        if context is None:
            raise ValueError(
                "AdaptationContext is required when adaptation is needed"
            )

        provider = self._provider_factory()
        try:
            provider_result = await provider.propose(context)
        finally:
            await provider.close()

        payload: Any = (
            provider_result.model_dump()
            if isinstance(provider_result, BaseModel)
            else provider_result
        )
        try:
            proposal = AdaptationProposal.model_validate(payload)
        except ValidationError as exc:
            raise InvalidAdaptationProposalError(
                "Adaptation response does not match AdaptationProposal"
            ) from exc

        validate_adaptation_targets(proposal, context)
        logger.info(
            "Adaptation preview completed",
            extra={
                "llm_invoked": True,
                "decision": proposal.decision.value,
                "change_count": len(proposal.changes),
            },
        )
        return proposal


def build_no_change_proposal(
    evaluation: EvaluationResult,
) -> AdaptationProposal:
    return AdaptationProposal(
        decision=AdaptationDecision.NO_CHANGE,
        summary="The current evidence does not justify changing the plan.",
        rationale=(
            f"The evaluation status is {evaluation.status.value} and its "
            "validated result does not require adaptation."
        ),
        changes=[],
    )


def validate_adaptation_targets(
    proposal: AdaptationProposal,
    context: AdaptationContext,
) -> None:
    validate_adaptation_targets_against_outline(
        proposal, context.plan_outline
    )


def validate_adaptation_targets_against_outline(
    proposal: AdaptationProposal,
    plan_outline: list[AdaptationStageOutline],
) -> None:
    stages = _unique_by_index(plan_outline, "Stage")
    for change in proposal.changes:
        if isinstance(change, AddTaskChange):
            mission = _resolve_mission(stages, change.target)
            task_indexes = _unique_by_index(mission.tasks, "Task")
            insert_after = change.insert_after_task_order_index
            if insert_after is not None and insert_after not in task_indexes:
                raise InvalidAdaptationTargetError(
                    "add_task insertion target does not exist"
                )
            continue

        target = change.target
        if not isinstance(target, AdaptationTaskTarget):
            raise InvalidAdaptationTargetError(
                "Task change requires a Task target"
            )
        mission = _resolve_mission(stages, target)
        tasks = _unique_by_index(mission.tasks, "Task")
        task = tasks.get(target.task_order_index)
        if task is None or task.title != target.task_title:
            raise InvalidAdaptationTargetError(
                "Adaptation Task target does not match the current plan"
            )

        if isinstance(change, ReorderTaskChange):
            if (
                change.destination_order_index not in tasks
                or change.destination_order_index == target.task_order_index
            ):
                raise InvalidAdaptationTargetError(
                    "reorder_task destination is not a different sibling Task"
                )


def _resolve_mission(
    stages: dict[int, AdaptationStageOutline],
    target: AdaptationMissionTarget,
) -> AdaptationMissionOutline:
    stage = stages.get(target.stage_order_index)
    if stage is None or stage.title != target.stage_title:
        raise InvalidAdaptationTargetError(
            "Adaptation Stage target does not match the current plan"
        )
    missions = _unique_by_index(stage.missions, "Mission")
    mission = missions.get(target.mission_order_index)
    if mission is None or mission.title != target.mission_title:
        raise InvalidAdaptationTargetError(
            "Adaptation Mission target does not match the current plan"
        )
    return mission


def _unique_by_index(items: list[Any], label: str) -> dict[int, Any]:
    indexed: dict[int, Any] = {}
    for item in items:
        if item.order_index in indexed:
            raise InvalidAdaptationTargetError(
                f"Current plan has ambiguous {label} order_index values"
            )
        indexed[item.order_index] = item
    return indexed
