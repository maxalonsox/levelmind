import { apiRequest } from '../lib/api'
import type {
  AdaptationAcceptResponse,
  AdaptationPreviewResponse,
  AdaptationRejectResponse,
} from '../types/adaptation'

export function previewGoalAdaptation(goalId: string): Promise<AdaptationPreviewResponse> {
  return apiRequest<AdaptationPreviewResponse>(
    `/goals/${encodeURIComponent(goalId)}/adaptation/preview`,
    { method: 'POST' },
  )
}

export function acceptAdaptation(
  goalId: string,
  adaptationId: string,
): Promise<AdaptationAcceptResponse> {
  return apiRequest<AdaptationAcceptResponse>(
    `/goals/${encodeURIComponent(goalId)}/adaptations/${encodeURIComponent(adaptationId)}/accept`,
    { method: 'POST' },
  )
}

export function rejectAdaptation(
  goalId: string,
  adaptationId: string,
): Promise<AdaptationRejectResponse> {
  return apiRequest<AdaptationRejectResponse>(
    `/goals/${encodeURIComponent(goalId)}/adaptations/${encodeURIComponent(adaptationId)}/reject`,
    { method: 'POST' },
  )
}
