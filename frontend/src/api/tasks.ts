import { apiRequest } from '../lib/api'
import type {
  PersistedTask,
  TaskResultCreate,
  TaskResultResponse,
  TaskUpdate,
} from '../types/planning'

export function resolveTask(
  taskId: string,
  payload: TaskResultCreate,
): Promise<TaskResultResponse> {
  return apiRequest<TaskResultResponse>(`/tasks/${encodeURIComponent(taskId)}/result`, {
    method: 'POST',
    body: payload,
  })
}

export function updateTask(taskId: string, payload: TaskUpdate): Promise<PersistedTask> {
  return apiRequest<PersistedTask>(`/tasks/${encodeURIComponent(taskId)}`, {
    method: 'PATCH',
    body: payload,
  })
}
