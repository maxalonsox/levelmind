import { useEffect, useState } from 'react'

const STORAGE_KEY = 'levelmind:lastActiveGoalId'
const CHANGE_EVENT = 'levelmind:last-active-goal-changed'

interface ValidatedActiveGoal {
  goalId: string
  userId: string
}

let validatedActiveGoal: ValidatedActiveGoal | null = null

export function getLastActiveGoalId(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function setLastActiveGoalId(goalId: string, userId: string): void {
  validatedActiveGoal = { goalId, userId }
  try {
    window.localStorage.setItem(STORAGE_KEY, goalId)
  } catch {
    // Navigation persistence is optional; the backend remains the source of truth.
  }
  window.dispatchEvent(new Event(CHANGE_EVENT))
}

export function clearLastActiveGoalId(): void {
  validatedActiveGoal = null
  try {
    window.localStorage.removeItem(STORAGE_KEY)
  } catch {
    // A storage failure must not block sign-out or plan error handling.
  }
  window.dispatchEvent(new Event(CHANGE_EVENT))
}

export function useValidatedActiveGoalId(userId: string | undefined): string | null {
  const [, setVersion] = useState(0)

  useEffect(() => {
    function refresh() {
      setVersion((version) => version + 1)
    }

    window.addEventListener(CHANGE_EVENT, refresh)
    return () => window.removeEventListener(CHANGE_EVENT, refresh)
  }, [])

  return getValidatedActiveGoalId(userId)
}

function getValidatedActiveGoalId(userId: string | undefined): string | null {
  if (!userId || validatedActiveGoal?.userId !== userId) return null
  return validatedActiveGoal.goalId
}
