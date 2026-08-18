import { apiRequest } from '../lib/api'
import type { Goal, GoalCreate } from '../types/goals'
import type { PlanPreview } from '../types/planning'

export function createGoal(payload: GoalCreate): Promise<Goal> {
  return apiRequest<Goal>('/goals', {
    method: 'POST',
    body: payload,
  })
}

export function previewGoalPlan(goalId: string): Promise<PlanPreview> {
  return apiRequest<PlanPreview>(`/goals/${encodeURIComponent(goalId)}/plan/preview`, {
    method: 'POST',
  })
}
