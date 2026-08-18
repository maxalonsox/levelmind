import type { Difficulty } from './planning'

export type AdaptationDecision = 'no_change' | 'propose_changes'
export type AdaptationStatus = 'pending' | 'accepted' | 'rejected'

export interface ProposedTask {
  title: string
  description: string | null
  estimated_duration_minutes: number
  xp_reward: number
}

export interface AdaptationMissionTarget {
  stage_order_index: number
  stage_title: string
  mission_order_index: number
  mission_title: string
}

export interface AdaptationTaskTarget extends AdaptationMissionTarget {
  task_order_index: number
  task_title: string
}

export interface AddTaskChange {
  type: 'add_task'
  target: AdaptationMissionTarget
  reason: string
  insert_after_task_order_index: number | null
  task: ProposedTask
}

export interface SplitTaskChange {
  type: 'split_task'
  target: AdaptationTaskTarget
  reason: string
  replacement_tasks: ProposedTask[]
}

export interface ReplaceTaskChange {
  type: 'replace_task'
  target: AdaptationTaskTarget
  reason: string
  replacement: ProposedTask
}

export interface ReorderTaskChange {
  type: 'reorder_task'
  target: AdaptationTaskTarget
  reason: string
  destination_order_index: number
}

export interface AdjustTaskDifficultyChange {
  type: 'adjust_task_difficulty'
  target: AdaptationTaskTarget
  reason: string
  proposed_difficulty: Difficulty
}

export interface AdjustTaskDurationChange {
  type: 'adjust_task_duration'
  target: AdaptationTaskTarget
  reason: string
  estimated_duration_minutes: number
}

export type AdaptationChange =
  | AddTaskChange
  | SplitTaskChange
  | ReplaceTaskChange
  | ReorderTaskChange
  | AdjustTaskDifficultyChange
  | AdjustTaskDurationChange

export interface AdaptationProposal {
  decision: AdaptationDecision
  summary: string
  rationale: string
  changes: AdaptationChange[]
}

export interface PlanAdaptation {
  id: string
  goal_id: string
  base_revision_id: string | null
  proposal: AdaptationProposal
  status: AdaptationStatus
  created_at: string
  updated_at: string
  reviewed_at: string | null
}

export interface AdaptationPreviewResponse extends AdaptationProposal {
  needs_adaptation: boolean
  adaptation: PlanAdaptation | null
}

export interface AdaptationAcceptResponse {
  adaptation_id: string
  status: 'accepted'
  reviewed_at: string
  revision_id: string
  revision_number: number
  applied_change_count: number
}

export interface AdaptationRejectResponse {
  adaptation_id: string
  status: 'rejected'
  reviewed_at: string
}
