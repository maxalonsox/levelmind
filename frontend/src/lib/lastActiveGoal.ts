import { useEffect, useState } from 'react'

const STORAGE_KEY = 'levelmind:lastActiveGoalId'
const CHANGE_EVENT = 'levelmind:last-active-goal-changed'

export function getLastActiveGoalId(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function setLastActiveGoalId(goalId: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, goalId)
    window.dispatchEvent(new Event(CHANGE_EVENT))
  } catch {
    // Navigation persistence is optional; the backend remains the source of truth.
  }
}

export function clearLastActiveGoalId(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY)
    window.dispatchEvent(new Event(CHANGE_EVENT))
  } catch {
    // A storage failure must not block sign-out or plan error handling.
  }
}

export function useLastActiveGoalId(): string | null {
  const [goalId, setGoalId] = useState(getLastActiveGoalId)

  useEffect(() => {
    function refresh() {
      setGoalId(getLastActiveGoalId())
    }

    window.addEventListener(CHANGE_EVENT, refresh)
    window.addEventListener('storage', refresh)
    return () => {
      window.removeEventListener(CHANGE_EVENT, refresh)
      window.removeEventListener('storage', refresh)
    }
  }, [])

  return goalId
}
