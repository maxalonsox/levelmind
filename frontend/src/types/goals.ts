export interface GoalCreate {
  title: string
  current_situation: string
  expected_outcome: string
  target_timeframe: string | null
  availability: string | null
}

export interface Goal {
  id: string
  user_id: string
  title: string
  current_situation: string
  expected_outcome: string
  target_timeframe: string | null
  availability: string | null
  status: string
  created_at: string
  updated_at: string
}
