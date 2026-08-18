import { apiRequest } from '../lib/api'
import type { TaskResultCreate, TaskResultResponse } from '../types/planning'

export function resolveTask(
  taskId: string,
  payload: TaskResultCreate,
): Promise<TaskResultResponse> {
  return apiRequest<TaskResultResponse>(`/tasks/${encodeURIComponent(taskId)}/result`, {
    method: 'POST',
    body: payload,
  })
}
