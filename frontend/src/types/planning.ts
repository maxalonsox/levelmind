export type Difficulty = 'easy' | 'normal' | 'difficult'
export type PlanningStatus = 'pending' | 'in_progress' | 'completed' | 'skipped'
export type TaskResult = 'completed' | 'skipped'

export interface PlanTask {
  title: string
  description: string | null
  order_index: number
  estimated_duration_minutes: number | null
  xp_reward: number
}

export interface PlanMission {
  title: string
  description: string | null
  order_index: number
  estimated_difficulty: Difficulty | null
  tasks: PlanTask[]
}

export interface PlanStage {
  title: string
  description: string | null
  order_index: number
  missions: PlanMission[]
}

export interface PlanPreview {
  stages: PlanStage[]
}

export interface PersistedTask extends PlanTask {
  id: string
  mission_id: string
  estimated_difficulty: Difficulty | null
  status: PlanningStatus
  difficulty_feedback: Difficulty | null
  feedback_text: string | null
  resolved_at: string | null
  created_at: string
  updated_at: string
}

export interface PersistedMission extends Omit<PlanMission, 'tasks'> {
  id: string
  stage_id: string
  status: PlanningStatus
  created_at: string
  updated_at: string
  tasks: PersistedTask[]
}

export interface PersistedStage extends Omit<PlanStage, 'missions'> {
  id: string
  goal_id: string
  status: PlanningStatus
  created_at: string
  updated_at: string
  missions: PersistedMission[]
}

export interface PersistedPlan {
  stages: PersistedStage[]
}

export interface PlanProgress {
  percentage: number
  xp_earned: number
  completed_tasks: number
  skipped_tasks: number
  pending_tasks: number
  total_tasks: number
}

export interface GoalPlan extends PersistedPlan {
  goal_id: string
  status: string
  progress: PlanProgress
}

export interface TaskResultCreate {
  result: TaskResult
  difficulty_feedback: Difficulty | null
  feedback_text: string | null
}

export interface TaskResultResponse extends PersistedTask {
  xp_awarded: number
}
