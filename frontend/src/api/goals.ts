import { apiRequest } from '../lib/api'
import type { Goal, GoalCreate } from '../types/goals'
import type { GoalPlan, PersistedPlan, PlanPreview } from '../types/planning'

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

export function acceptGoalPlan(goalId: string, preview: PlanPreview): Promise<PersistedPlan> {
  return apiRequest<PersistedPlan>(`/goals/${encodeURIComponent(goalId)}/plan/accept`, {
    method: 'POST',
    body: preview,
  })
}

export function getGoalPlan(goalId: string): Promise<GoalPlan> {
  return apiRequest<GoalPlan>(`/goals/${encodeURIComponent(goalId)}/plan`)
}

export function getActiveGoal(): Promise<Goal> {
  return apiRequest<Goal>('/goals/active', {
    cache: 'no-store',
  })
}

export function deleteGoal(goalId: string): Promise<void> {
  return apiRequest<void>(`/goals/${encodeURIComponent(goalId)}`, {
    method: 'DELETE',
  })
}
