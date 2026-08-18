import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '../app/App'
import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import { ApiError } from '../lib/api'
import type { Goal } from '../types/goals'
import type { GoalPlan, PersistedPlan, PlanPreview } from '../types/planning'
import { ActivePlanPage } from './ActivePlanPage'
import { PlanPreviewPage } from './PlanPreviewPage'

const apiMocks = vi.hoisted(() => ({
  acceptGoalPlan: vi.fn(),
  createGoal: vi.fn(),
  getGoalPlan: vi.fn(),
  previewGoalPlan: vi.fn(),
}))

vi.mock(import('../api/goals'), () => apiMocks)

const goal: Goal = {
  id: 'e9d7145c-d348-4e8a-b411-d8e6ef54e6fc',
  user_id: '55e8ce33-da90-4fb4-a203-e41360441cbf',
  title: 'Dominar desarrollo backend',
  current_situation: 'Conozco Python',
  expected_outcome: 'Construir APIs de producción',
  target_timeframe: '6 meses',
  availability: '8 horas por semana',
  status: 'active',
  created_at: '2026-08-18T10:00:00Z',
  updated_at: '2026-08-18T10:00:00Z',
}

const preview: PlanPreview = {
  stages: [
    {
      title: 'Fundamentos backend',
      description: 'Preparar una base sólida',
      order_index: 0,
      missions: [
        {
          title: 'Construir una API',
          description: 'Aplicar contratos y persistencia',
          order_index: 0,
          estimated_difficulty: 'normal',
          tasks: [
            {
              title: 'Crear endpoint de Goal',
              description: 'Validar el request y response',
              order_index: 0,
              estimated_duration_minutes: 45,
              xp_reward: 10,
            },
          ],
        },
      ],
    },
  ],
}

const persistedPlan: PersistedPlan = {
  stages: [
    {
      ...preview.stages[0]!,
      id: 'stage-id',
      goal_id: goal.id,
      status: 'pending',
      created_at: goal.created_at,
      updated_at: goal.updated_at,
      missions: [
        {
          ...preview.stages[0]!.missions[0]!,
          id: 'mission-id',
          stage_id: 'stage-id',
          status: 'pending',
          created_at: goal.created_at,
          updated_at: goal.updated_at,
          tasks: [
            {
              ...preview.stages[0]!.missions[0]!.tasks[0]!,
              id: 'task-id',
              mission_id: 'mission-id',
              estimated_difficulty: null,
              status: 'pending',
              difficulty_feedback: null,
              feedback_text: null,
              resolved_at: null,
              created_at: goal.created_at,
              updated_at: goal.updated_at,
            },
          ],
        },
      ],
    },
  ],
}

const activePlan: GoalPlan = {
  ...persistedPlan,
  goal_id: goal.id,
  status: 'active',
  progress: {
    percentage: 0,
    xp_earned: 0,
    completed_tasks: 0,
    skipped_tasks: 0,
    pending_tasks: 1,
    total_tasks: 1,
  },
}

const authenticated: AuthContextValue = {
  isLoading: false,
  session: {
    access_token: 'test-token',
    refresh_token: 'test-refresh-token',
    expires_in: 3600,
    token_type: 'bearer',
    user: {
      id: goal.user_id,
      app_metadata: {},
      user_metadata: {},
      aud: 'authenticated',
      created_at: goal.created_at,
      email: 'user@example.com',
    },
  },
  signIn: vi.fn(),
  signOut: vi.fn(),
}

const unauthenticated: AuthContextValue = {
  isLoading: false,
  session: null,
  signIn: vi.fn(),
  signOut: vi.fn(),
}

function renderPreview() {
  return render(
    <AuthContext.Provider value={authenticated}>
      <MemoryRouter
        initialEntries={[
          {
            pathname: `/goals/${goal.id}/plan`,
            state: { goal, preview },
          },
        ]}
      >
        <Routes>
          <Route path="/goals/:goalId/plan" element={<PlanPreviewPage />} />
          <Route path="/goals/:goalId" element={<ActivePlanPage />} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

describe('initial plan acceptance', () => {
  beforeEach(() => {
    apiMocks.acceptGoalPlan.mockReset()
    apiMocks.createGoal.mockReset()
    apiMocks.getGoalPlan.mockReset()
    apiMocks.previewGoalPlan.mockReset()
  })

  it('shows the reviewed hierarchy and the accept action', () => {
    renderPreview()

    expect(screen.getByText('Fundamentos backend')).toBeInTheDocument()
    expect(screen.getByText('Construir una API')).toBeInTheDocument()
    expect(screen.getByText('Crear endpoint de Goal')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Aceptar plan' })).toBeInTheDocument()
  })

  it('submits the same preview once, waits for persistence, and shows the active plan', async () => {
    let resolveAcceptance!: (plan: PersistedPlan) => void
    apiMocks.acceptGoalPlan.mockReturnValue(
      new Promise<PersistedPlan>((resolve) => {
        resolveAcceptance = resolve
      }),
    )
    apiMocks.getGoalPlan.mockResolvedValue(activePlan)
    renderPreview()
    const user = userEvent.setup()
    const acceptButton = screen.getByRole('button', { name: 'Aceptar plan' })

    await user.dblClick(acceptButton)

    expect(apiMocks.acceptGoalPlan).toHaveBeenCalledOnce()
    expect(apiMocks.acceptGoalPlan).toHaveBeenCalledWith(goal.id, preview)
    expect(screen.getByRole('button', { name: 'Guardando plan…' })).toBeDisabled()
    expect(apiMocks.previewGoalPlan).not.toHaveBeenCalled()

    resolveAcceptance(persistedPlan)

    expect(await screen.findByText('Tu plan está listo')).toBeInTheDocument()
    expect(apiMocks.getGoalPlan).toHaveBeenCalledWith(goal.id)
    expect(screen.getAllByText('Plan activo')).toHaveLength(2)
    expect(screen.getByText('Fundamentos backend')).toBeInTheDocument()
    expect(screen.getByText('Crear endpoint de Goal')).toBeInTheDocument()
    expect(apiMocks.previewGoalPlan).not.toHaveBeenCalled()
  })

  it('shows a readable persistence error and allows retrying', async () => {
    apiMocks.acceptGoalPlan.mockRejectedValue(new ApiError('database details', 500))
    renderPreview()
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: 'Aceptar plan' }))

    expect(
      await screen.findByText('No pudimos guardar el plan. Ningún cambio parcial fue aplicado.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Aceptar plan' })).toBeEnabled()
  })

  it('handles a 409 conflict and continues to the persisted plan', async () => {
    apiMocks.acceptGoalPlan.mockRejectedValue(
      new ApiError('Goal already has a persisted plan', 409),
    )
    apiMocks.getGoalPlan.mockResolvedValue(activePlan)
    renderPreview()
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: 'Aceptar plan' }))

    expect(
      await screen.findByText(
        'Este objetivo ya tiene un plan activo. Podés continuar hacia la versión guardada.',
      ),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Ver plan activo' }))

    expect(await screen.findByText('Tu plan está listo')).toBeInTheDocument()
    expect(apiMocks.getGoalPlan).toHaveBeenCalledWith(goal.id)
    expect(apiMocks.previewGoalPlan).not.toHaveBeenCalled()
  })

  it('reloads an already active hierarchy without route state', async () => {
    apiMocks.getGoalPlan.mockResolvedValue(activePlan)
    render(
      <AuthContext.Provider value={authenticated}>
        <MemoryRouter initialEntries={[`/goals/${goal.id}`]}>
          <Routes>
            <Route path="/goals/:goalId" element={<ActivePlanPage />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>,
    )

    expect(await screen.findByText('Tu plan está listo')).toBeInTheDocument()
    expect(screen.getByText('Objetivo profesional')).toBeInTheDocument()
    expect(screen.getByText('Fundamentos backend')).toBeInTheDocument()
  })

  it('keeps plan routes behind authentication', async () => {
    render(
      <AuthContext.Provider value={unauthenticated}>
        <MemoryRouter initialEntries={[`/goals/${goal.id}`]}>
          <App />
        </MemoryRouter>
      </AuthContext.Provider>,
    )

    expect(await screen.findByRole('heading', { name: 'Ingresá a LevelMind' })).toBeInTheDocument()
    expect(apiMocks.getGoalPlan).not.toHaveBeenCalled()
  })
})
