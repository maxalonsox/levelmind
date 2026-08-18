import asyncio
from typing import Any

import pytest

from app.ai.adaptation.contracts import (
    AdaptationContext,
    AdaptationDecision,
    AdaptationMissionOutline,
    AdaptationProposal,
    AdaptationStageOutline,
    AdaptationTaskOutline,
)
from app.ai.adaptation.errors import (
    InvalidAdaptationProposalError,
    InvalidAdaptationTargetError,
)
from app.ai.adaptation.prompts import build_adaptation_prompt
from app.ai.evaluation.contracts import EvaluationGoalContext, EvaluationResult
from app.services.adaptation import AdaptationService, build_no_change_proposal


def evaluation(*, needs_adaptation: bool) -> EvaluationResult:
    return EvaluationResult(
        status="struggling" if needs_adaptation else "on_track",
        summary="Repeated execution evidence was evaluated.",
        signals=(
            [
                {
                    "type": "high_difficulty",
                    "description": "Three Tasks were marked difficult.",
                    "severity": "high",
                }
            ]
            if needs_adaptation
            else []
        ),
        needs_adaptation=needs_adaptation,
    )


def adaptation_context() -> AdaptationContext:
    result = evaluation(needs_adaptation=True)
    return AdaptationContext(
        goal=EvaluationGoalContext(
            title="Learn backend",
            current_situation="Python fundamentals",
            expected_outcome="Build production APIs",
            target_timeframe="Three months",
            availability="Five hours per week",
        ),
        evaluation=result,
        plan_outline=[
            AdaptationStageOutline(
                order_index=0,
                title="Backend",
                missions=[
                    AdaptationMissionOutline(
                        order_index=0,
                        title="API delivery",
                        tasks=[
                            AdaptationTaskOutline(
                                order_index=0,
                                title="Model endpoint",
                                status="completed",
                            ),
                            AdaptationTaskOutline(
                                order_index=1,
                                title="Implement endpoint",
                                status="pending",
                            ),
                        ],
                    )
                ],
            )
        ],
        relevant_tasks=[],
    )


def target() -> dict[str, Any]:
    return {
        "stage_order_index": 0,
        "stage_title": "Backend",
        "mission_order_index": 0,
        "mission_title": "API delivery",
        "task_order_index": 1,
        "task_title": "Implement endpoint",
    }


def valid_proposal() -> dict[str, Any]:
    return {
        "decision": "propose_changes",
        "summary": "Correct the duration estimate.",
        "rationale": "Repeated high difficulty supports a bounded change.",
        "changes": [
            {
                "type": "adjust_task_duration",
                "target": target(),
                "reason": "The current estimate is too short.",
                "estimated_duration_minutes": 90,
            }
        ],
    }


class FakeProvider:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.contexts: list[AdaptationContext] = []
        self.closed = False

    async def propose(self, context: AdaptationContext) -> Any:
        self.contexts.append(context)
        return self.result

    async def close(self) -> None:
        self.closed = True


def test_adaptation_service_short_circuits_without_provider() -> None:
    factory_calls = 0

    def fail_if_constructed() -> FakeProvider:
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError("Provider must not be built")

    result = asyncio.run(
        AdaptationService(fail_if_constructed).propose(
            evaluation(needs_adaptation=False)
        )
    )

    assert result.decision is AdaptationDecision.NO_CHANGE
    assert result.changes == []
    assert factory_calls == 0


def test_insufficient_data_no_change_is_concise_and_hides_internal_status() -> None:
    result = build_no_change_proposal(
        EvaluationResult(
            status="insufficient_data",
            summary="Internal evaluation summary.",
            signals=[
                {
                    "type": "insufficient_data",
                    "description": "Internal signal.",
                    "severity": "low",
                }
            ],
            needs_adaptation=False,
        )
    )

    content = f"{result.summary} {result.rationale}"
    assert "poca evidencia" in content
    assert "insufficient_data" not in content


def test_adaptation_service_validates_and_returns_provider_proposal() -> None:
    context = adaptation_context()
    provider = FakeProvider(valid_proposal())
    assert (
        "recent_observed_task_execution_history"
        not in build_adaptation_prompt(context).user
    )

    result = asyncio.run(
        AdaptationService(lambda: provider).propose(
            context.evaluation, context
        )
    )

    assert isinstance(result, AdaptationProposal)
    assert result.decision is AdaptationDecision.PROPOSE_CHANGES
    assert provider.contexts == [context]
    assert provider.closed is True


def test_adaptation_service_rejects_invalid_provider_schema() -> None:
    context = adaptation_context()
    provider = FakeProvider(
        {
            "decision": "propose_changes",
            "summary": "Invalid",
            "rationale": "No changes are supplied.",
            "changes": [],
        }
    )

    with pytest.raises(InvalidAdaptationProposalError):
        asyncio.run(
            AdaptationService(lambda: provider).propose(
                context.evaluation, context
            )
        )

    assert provider.closed is True


@pytest.mark.parametrize(
    ("target_override", "expected_fragment"),
    [
        ({"stage_order_index": 9}, "Stage"),
        ({"mission_order_index": 9}, "Mission"),
        ({"task_order_index": 9}, "Task"),
        ({"task_title": "Stale title"}, "Task"),
    ],
)
def test_adaptation_service_rejects_invalid_targets(
    target_override: dict[str, Any], expected_fragment: str
) -> None:
    context = adaptation_context()
    payload = valid_proposal()
    payload["changes"][0]["target"].update(target_override)
    provider = FakeProvider(payload)

    with pytest.raises(InvalidAdaptationTargetError, match=expected_fragment):
        asyncio.run(
            AdaptationService(lambda: provider).propose(
                context.evaluation, context
            )
        )


def test_adaptation_service_rejects_invalid_reorder_destination() -> None:
    context = adaptation_context()
    payload = valid_proposal()
    payload["changes"] = [
        {
            "type": "reorder_task",
            "target": target(),
            "reason": "Move it after a prerequisite.",
            "destination_order_index": 9,
        }
    ]

    with pytest.raises(InvalidAdaptationTargetError, match="destination"):
        asyncio.run(
            AdaptationService(lambda: FakeProvider(payload)).propose(
                context.evaluation, context
            )
        )


def test_adaptation_service_rejects_invalid_add_location() -> None:
    context = adaptation_context()
    payload = valid_proposal()
    task_target = target()
    task_target.pop("task_order_index")
    task_target.pop("task_title")
    payload["changes"] = [
        {
            "type": "add_task",
            "target": task_target,
            "reason": "Add a prerequisite.",
            "insert_after_task_order_index": 9,
            "task": {
                "title": "Prepare endpoint contract",
                "description": None,
                "estimated_duration_minutes": 45,
                "xp_reward": 10,
            },
        }
    ]

    with pytest.raises(InvalidAdaptationTargetError, match="insertion"):
        asyncio.run(
            AdaptationService(lambda: FakeProvider(payload)).propose(
                context.evaluation, context
            )
        )
