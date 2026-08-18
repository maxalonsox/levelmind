import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

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
})
