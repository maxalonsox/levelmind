import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { acceptGoalPlan, getActiveGoal } from '../api/goals'
import { acceptAdaptation, previewGoalAdaptation, rejectAdaptation } from '../api/adaptations'
import { resolveTask, updateTask } from '../api/tasks'
import type { PlanPreview, TaskResultCreate } from '../types/planning'
import { apiRequest } from './api'
import { supabase } from './supabase'

const getSession = vi.spyOn(supabase.auth, 'getSession')

describe('apiRequest', () => {
  beforeEach(() => {
    getSession.mockReset()
    getSession.mockResolvedValue({
      data: {
        session: {
          access_token: 'supabase-access-token',
          refresh_token: 'test-refresh-token',
          expires_in: 3600,
          token_type: 'bearer',
          user: {
            id: 'test-user-id',
            app_metadata: {},
            user_metadata: {},
            aud: 'authenticated',
            created_at: '2026-08-18T10:00:00Z',
          },
        },
      },
      error: null,
    })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ id: 'goal-id' }), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('attaches the current Bearer token and serializes JSON requests', async () => {
    const payload = { title: 'Learn FastAPI' }

    await apiRequest<{ id: string }>('/goals', {
      method: 'POST',
      body: payload,
    })

    expect(getSession).toHaveBeenCalledOnce()
    expect(fetch).toHaveBeenCalledOnce()
    const [url, request] = vi.mocked(fetch).mock.calls[0]!
    const headers = new Headers(request?.headers)
    expect(url).toBe('http://api.test/goals')
    expect(request?.method).toBe('POST')
    expect(request?.body).toBe(JSON.stringify(payload))
    expect(headers.get('Authorization')).toBe('Bearer supabase-access-token')
    expect(headers.get('Content-Type')).toBe('application/json')
  })

  it('posts the reviewed GeneratedPlan to the existing acceptance endpoint', async () => {
    const reviewedPreview: PlanPreview = {
      stages: [
        {
          title: 'Foundation',
          description: null,
          order_index: 0,
          missions: [
            {
              title: 'First mission',
              description: null,
              order_index: 0,
              estimated_difficulty: 'normal',
              tasks: [
                {
                  title: 'First task',
                  description: null,
                  order_index: 0,
                  estimated_duration_minutes: 30,
                  xp_reward: 10,
                },
              ],
            },
          ],
        },
      ],
    }

    await acceptGoalPlan('goal-id', reviewedPreview)

    const [url, request] = vi.mocked(fetch).mock.calls[0]!
    expect(url).toBe('http://api.test/goals/goal-id/plan/accept')
    expect(request?.method).toBe('POST')
    expect(request?.body).toBe(JSON.stringify(reviewedPreview))
    expect(new Headers(request?.headers).get('Authorization')).toBe(
      'Bearer supabase-access-token',
    )
  })

  it('always revalidates the active Goal against the backend', async () => {
    await getActiveGoal()

    const [url, request] = vi.mocked(fetch).mock.calls[0]!
    expect(url).toBe('http://api.test/goals/active')
    expect(request?.cache).toBe('no-store')
    expect(new Headers(request?.headers).get('Authorization')).toBe(
      'Bearer supabase-access-token',
    )
  })

  it('posts an authenticated task result to the existing execution endpoint', async () => {
    const payload: TaskResultCreate = {
      result: 'completed',
      difficulty_feedback: 'difficult',
      feedback_text: 'Necesité más tiempo del esperado.',
    }

    await resolveTask('task/id', payload)

    const [url, request] = vi.mocked(fetch).mock.calls[0]!
    expect(url).toBe('http://api.test/tasks/task%2Fid/result')
    expect(request?.method).toBe('POST')
    expect(request?.body).toBe(JSON.stringify(payload))
    expect(new Headers(request?.headers).get('Authorization')).toBe(
      'Bearer supabase-access-token',
    )
  })

  it('patches only editable task fields', async () => {
    const payload = {
      title: 'Updated task',
      estimated_duration_minutes: 45,
    }

    await updateTask('task/id', payload)

    const [url, request] = vi.mocked(fetch).mock.calls[0]!
    expect(url).toBe('http://api.test/tasks/task%2Fid')
    expect(request?.method).toBe('PATCH')
    expect(request?.body).toBe(JSON.stringify(payload))
  })

  it.each([
    ['preview', () => previewGoalAdaptation('goal/id'), 'http://api.test/goals/goal%2Fid/adaptation/preview'],
    [
      'accept',
      () => acceptAdaptation('goal/id', 'adaptation/id'),
      'http://api.test/goals/goal%2Fid/adaptations/adaptation%2Fid/accept',
    ],
    [
      'reject',
      () => rejectAdaptation('goal/id', 'adaptation/id'),
      'http://api.test/goals/goal%2Fid/adaptations/adaptation%2Fid/reject',
    ],
  ])('posts authenticated adaptation %s requests to the existing endpoint', async (_name, requestCall, expectedUrl) => {
    await requestCall()

    const [url, request] = vi.mocked(fetch).mock.calls[0]!
    expect(url).toBe(expectedUrl)
    expect(request?.method).toBe('POST')
    expect(request?.body).toBeUndefined()
    expect(new Headers(request?.headers).get('Authorization')).toBe(
      'Bearer supabase-access-token',
    )
  })
})
