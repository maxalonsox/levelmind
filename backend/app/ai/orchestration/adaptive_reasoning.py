from collections.abc import Callable
from typing import Literal, NotRequired, Protocol, TypedDict, cast
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from app.ai.adaptation.contracts import (
    AdaptationContext,
    AdaptationProposal,
)
from app.ai.evaluation.contracts import (
    EvaluationContext,
    EvaluationResult,
)


class AdaptiveReasoningState(TypedDict):
    user_id: UUID
    goal_id: UUID
    evaluation_context: NotRequired[EvaluationContext]
    evaluation: NotRequired[EvaluationResult]
    adaptation: NotRequired[AdaptationProposal]


class EvaluationRunner(Protocol):
    async def evaluate(self, context: EvaluationContext) -> EvaluationResult:
        """Run the existing Evaluation behavior."""
        ...


class AdaptationRunner(Protocol):
    async def propose(
        self,
        evaluation: EvaluationResult,
        context: AdaptationContext | None = None,
    ) -> AdaptationProposal:
        """Run the existing Adaptation behavior."""
        ...


EvaluationContextBuilder = Callable[
    [UUID, UUID],
    EvaluationContext,
]
AdaptationContextBuilder = Callable[
    [UUID, UUID, EvaluationContext, EvaluationResult],
    AdaptationContext,
]


class AdaptiveReasoningOrchestrator:
    def __init__(
        self,
        *,
        evaluation_service: EvaluationRunner,
        adaptation_service: AdaptationRunner,
        build_evaluation_context: EvaluationContextBuilder,
        build_adaptation_context: AdaptationContextBuilder,
    ) -> None:
        self._evaluation_service = evaluation_service
        self._adaptation_service = adaptation_service
        self._build_evaluation_context = build_evaluation_context
        self._build_adaptation_context = build_adaptation_context

        workflow = StateGraph(AdaptiveReasoningState)
        workflow.add_node("evaluate", self._evaluate)
        workflow.add_node("adapt", self._adapt)
        workflow.add_edge(START, "evaluate")
        workflow.add_conditional_edges(
            "evaluate",
            self._route_after_evaluation,
            {"adapt": "adapt", "end": END},
        )
        workflow.add_edge("adapt", END)
        self._graph = workflow.compile()

    async def run(
        self,
        *,
        user_id: UUID,
        goal_id: UUID,
    ) -> AdaptiveReasoningState:
        result = await self._graph.ainvoke(
            {"user_id": user_id, "goal_id": goal_id}
        )
        return cast(AdaptiveReasoningState, result)

    async def _evaluate(
        self,
        state: AdaptiveReasoningState,
    ) -> dict[str, EvaluationContext | EvaluationResult]:
        context = self._build_evaluation_context(
            state["goal_id"], state["user_id"]
        )
        evaluation = await self._evaluation_service.evaluate(context)
        return {
            "evaluation_context": context,
            "evaluation": evaluation,
        }

    @staticmethod
    def _route_after_evaluation(
        state: AdaptiveReasoningState,
    ) -> Literal["adapt", "end"]:
        evaluation = state["evaluation"]
        return "adapt" if evaluation.needs_adaptation else "end"

    async def _adapt(
        self,
        state: AdaptiveReasoningState,
    ) -> dict[str, AdaptationProposal]:
        evaluation = state["evaluation"]
        evaluation_context = state["evaluation_context"]
        context = self._build_adaptation_context(
            state["goal_id"],
            state["user_id"],
            evaluation_context,
            evaluation,
        )
        adaptation = await self._adaptation_service.propose(
            evaluation,
            context,
        )
        return {"adaptation": adaptation}
