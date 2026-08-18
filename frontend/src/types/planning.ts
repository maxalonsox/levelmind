export type Difficulty = 'easy' | 'normal' | 'difficult'

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
