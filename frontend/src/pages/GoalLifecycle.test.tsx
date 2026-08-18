import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Session } from '@supabase/supabase-js'
import { useState, type ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import { ApiError } from '../lib/api'
import {
  clearLastActiveGoalId,
  getLastActiveGoalId,
} from '../lib/lastActiveGoal'
import type { Goal } from '../types/goals'
import type { GoalPlan, PlanPreview } from '../types/planning'
import { ActivePlanPage } from './ActivePlanPage'
import { HomePage } from './HomePage'
import { LoginPage } from './LoginPage'
import { PlanPreviewPage } from './PlanPreviewPage'

const apiMocks = vi.hoisted(() => ({
  deleteGoal: vi.fn(),
  getActiveGoal: vi.fn(),
  getGoalPlan: vi.fn(),
  previewGoalPlan: vi.fn(),
}))

vi.mock(import('../api/goals'), async (importOriginal) => ({
  ...(await importOriginal()),
  deleteGoal: apiMocks.deleteGoal,
  getActiveGoal: apiMocks.getActiveGoal,
  getGoalPlan: apiMocks.getGoalPlan,
  previewGoalPlan: apiMocks.previewGoalPlan,
}))

const timestamp = '2026-08-18T10:00:00Z'
const goalA = makeGoal('goal-a', 'user-a')
const goalB = makeGoal('goal-b', 'user-b')
const plan: GoalPlan = {
  goal_id: goalA.id,
  status: 'active',
  progress: {
    percentage: 0,
    xp_earned: 0,
    completed_tasks: 0,
    skipped_tasks: 0,
    pending_tasks: 0,
    total_tasks: 0,
  },
  stages: [
    {
      id: 'stage-id',
      goal_id: goalA.id,
      title: 'Primera etapa',
      description: 'Descripción',
      order_index: 0,
      status: 'pending',
      created_at: timestamp,
      updated_at: timestamp,
      missions: [],
    },
  ],
}
const planningPending: GoalPlan = {
  ...plan,
  stages: [],
}
const preview: PlanPreview = {
  stages: [
    {
      title: 'Primera etapa recuperada',
      description: 'Una propuesta nueva para el objetivo existente',
      order_index: 0,
      missions: [
        {
          title: 'Primera misión',
          description: null,
          order_index: 0,
          estimated_difficulty: 'normal',
          tasks: [
            {
              title: 'Primera tarea',
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

function makeGoal(id: string, userId: string): Goal {
  return {
    id,
    user_id: userId,
    title: `Objetivo ${id}`,
    current_situation: 'Situación actual',
    expected_outcome: 'Resultado esperado',
    target_timeframe: null,
    availability: null,
    status: 'active',
    created_at: timestamp,
    updated_at: timestamp,
  }
}

function makeSession(userId: string): Session {
  return {
    access_token: 'test-token',
    refresh_token: 'test-refresh-token',
    expires_in: 3600,
    token_type: 'bearer',
    user: {
      id: userId,
      email: `${userId}@example.com`,
      app_metadata: {},
      user_metadata: {},
      aud: 'authenticated',
      created_at: timestamp,
    },
  }
}

function authValue(userId = 'user-a'): AuthContextValue {
  return {
    isLoading: false,
    session: makeSession(userId),
    signIn: vi.fn(),
    signOut: vi.fn(),
  }
}

function renderAuthenticated(children: ReactNode, userId = 'user-a') {
  return render(
    <AuthContext.Provider value={authValue(userId)}>{children}</AuthContext.Provider>,
  )
}

function renderActivePlan() {
  return renderAuthenticated(
    <MemoryRouter
      initialEntries={[{
        pathname: `/goals/${goalA.id}`,
        state: { activePlan: plan, goal: goalA },
      }]}
    >
      <Routes>
        <Route path="/goals/:goalId" element={<ActivePlanPage />} />
        <Route path="/" element={<HomePage />} />
      </Routes>
    </MemoryRouter>,
  )
}

function renderPlanningRecovery() {
  return renderAuthenticated(
    <MemoryRouter initialEntries={[`/goals/${goalA.id}`]}>
      <Routes>
        <Route path="/goals/:goalId" element={<ActivePlanPage />} />
        <Route path="/goals/:goalId/plan" element={<PlanPreviewPage />} />
        <Route path="/" element={<HomePage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('backend-driven active goal recovery', () => {
  beforeEach(() => {
    clearLastActiveGoalId()
    apiMocks.deleteGoal.mockReset()
    apiMocks.getActiveGoal.mockReset()
    apiMocks.getGoalPlan.mockReset()
    apiMocks.previewGoalPlan.mockReset()
  })

  it('recovers the active Goal after login and rebuilds Home navigation', async () => {
    apiMocks.getActiveGoal.mockResolvedValue(goalA)
    const user = userEvent.setup()

    function LoginRecoveryApp() {
      const [session, setSession] = useState<Session | null>(null)
      const value: AuthContextValue = {
        isLoading: false,
        session,
        signIn: async () => setSession(makeSession('user-a')),
        signOut: vi.fn(),
      }
      return (
        <AuthContext.Provider value={value}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<HomePage />} />
          </Routes>
        </AuthContext.Provider>
      )
    }

    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginRecoveryApp />
      </MemoryRouter>,
    )
    await user.type(screen.getByLabelText('Email'), 'user@example.com')
    await user.type(screen.getByLabelText('Contraseña'), 'password')
    await user.click(screen.getByRole('button', { name: 'Ingresar' }))

    expect(await screen.findByRole('link', { name: /Continuar con mi plan/ })).toHaveAttribute(
      'href',
      `/goals/${goalA.id}`,
    )
    expect(screen.getByRole('link', { name: 'Mi plan' })).toHaveAttribute(
      'href',
      `/goals/${goalA.id}`,
    )
    expect(getLastActiveGoalId()).toBe(goalA.id)
  })

  it('treats a 404 after reload as a valid empty state and clears stale navigation', async () => {
    window.localStorage.setItem('levelmind:lastActiveGoalId', goalA.id)
    apiMocks.getActiveGoal.mockRejectedValue(new ApiError('Active goal not found', 404))

    renderAuthenticated(<MemoryRouter><HomePage /></MemoryRouter>)

    expect(await screen.findByRole('link', { name: /Crear objetivo/ })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Continuar con mi plan/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Mi plan' })).not.toBeInTheDocument()
    expect(getLastActiveGoalId()).toBeNull()
    expect(apiMocks.getActiveGoal).toHaveBeenCalledOnce()
  })

  it('does not recreate plan navigation after logout and login without an active Goal', async () => {
    apiMocks.getActiveGoal
      .mockResolvedValueOnce(goalA)
      .mockRejectedValueOnce(new ApiError('Active goal not found', 404))
    const user = userEvent.setup()

    function SessionCycleApp() {
      const [session, setSession] = useState<Session | null>(makeSession('user-a'))
      const value: AuthContextValue = {
        isLoading: false,
        session,
        signIn: async () => setSession(makeSession('user-a')),
        signOut: async () => setSession(null),
      }
      return (
        <AuthContext.Provider value={value}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<HomePage />} />
          </Routes>
        </AuthContext.Provider>
      )
    }

    render(<MemoryRouter><SessionCycleApp /></MemoryRouter>)
    expect(await screen.findByRole('link', { name: /Continuar con mi plan/ })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Salir' }))
    expect(await screen.findByRole('heading', { name: 'Ingresá a LevelMind' })).toBeInTheDocument()

    await user.type(screen.getByLabelText('Email'), 'user@example.com')
    await user.type(screen.getByLabelText('Contraseña'), 'password')
    await user.click(screen.getByRole('button', { name: 'Ingresar' }))

    expect(await screen.findByRole('link', { name: /Crear objetivo/ })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Continuar con mi plan/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Mi plan' })).not.toBeInTheDocument()
    expect(getLastActiveGoalId()).toBeNull()
  })

  it('does not let a second user inherit the first user Goal reference', async () => {
    apiMocks.getActiveGoal.mockResolvedValueOnce(goalA).mockResolvedValueOnce(goalB)
    const view = renderAuthenticated(<MemoryRouter><HomePage /></MemoryRouter>, 'user-a')
    expect(await screen.findByRole('link', { name: /Continuar con mi plan/ })).toHaveAttribute(
      'href',
      `/goals/${goalA.id}`,
    )

    view.rerender(
      <AuthContext.Provider value={authValue('user-b')}>
        <MemoryRouter><HomePage /></MemoryRouter>
      </AuthContext.Provider>,
    )

    expect(await screen.findByRole('link', { name: /Continuar con mi plan/ })).toHaveAttribute(
      'href',
      `/goals/${goalB.id}`,
    )
    expect(screen.getByRole('link', { name: 'Mi plan' })).toHaveAttribute(
      'href',
      `/goals/${goalB.id}`,
    )
    expect(getLastActiveGoalId()).toBe(goalB.id)
    expect(apiMocks.getActiveGoal).toHaveBeenCalledTimes(2)
  })
})

describe('active plan deletion', () => {
  beforeEach(() => {
    clearLastActiveGoalId()
    apiMocks.deleteGoal.mockReset()
    apiMocks.getActiveGoal.mockReset()
    apiMocks.getGoalPlan.mockReset()
    apiMocks.previewGoalPlan.mockReset()
  })

  it('shows a confirmation and Cancelar does not call the API', async () => {
    const user = userEvent.setup()
    renderActivePlan()

    await user.click(screen.getByRole('button', { name: 'Eliminar plan' }))
    const dialog = screen.getByRole('dialog', { name: '¿Eliminar este plan?' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(within(dialog).getByRole('button', { name: 'Eliminar plan' })).toHaveFocus()
    await user.click(within(dialog).getByRole('button', { name: 'Cancelar' }))

    expect(apiMocks.deleteGoal).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Plan guardado' })).toBeInTheDocument()
  })

  it('blocks duplicate submits, deletes the Goal, clears the reference and returns Home', async () => {
    let resolveDelete: (() => void) | undefined
    let rejectRecovery: ((cause: unknown) => void) | undefined
    apiMocks.deleteGoal.mockImplementation(
      () => new Promise<void>((resolve) => { resolveDelete = resolve }),
    )
    apiMocks.getActiveGoal.mockImplementation(
      () => new Promise((_resolve, reject) => { rejectRecovery = reject }),
    )
    const user = userEvent.setup()
    renderActivePlan()
    await waitFor(() => expect(getLastActiveGoalId()).toBe(goalA.id))

    await user.click(screen.getByRole('button', { name: 'Eliminar plan' }))
    const dialog = screen.getByRole('dialog')
    const confirm = within(dialog).getByRole('button', { name: 'Eliminar plan' })
    await user.click(confirm)
    confirm.click()

    expect(apiMocks.deleteGoal).toHaveBeenCalledOnce()
    expect(apiMocks.deleteGoal).toHaveBeenCalledWith(goalA.id)
    expect(within(dialog).getByRole('button', { name: 'Eliminando plan…' })).toBeDisabled()

    resolveDelete?.()
    await waitFor(() => expect(apiMocks.getActiveGoal).toHaveBeenCalledOnce())
    expect(getLastActiveGoalId()).toBeNull()
    expect(screen.queryByRole('link', { name: /Continuar con mi plan/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Mi plan' })).not.toBeInTheDocument()

    rejectRecovery?.(new ApiError('Active goal not found', 404))
    expect(await screen.findByRole('link', { name: /Crear objetivo/ })).toBeInTheDocument()
    expect(getLastActiveGoalId()).toBeNull()
    expect(screen.queryByRole('link', { name: /Continuar con mi plan/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Mi plan' })).not.toBeInTheDocument()
  })

  it('keeps the plan and local reference visible when deletion fails', async () => {
    apiMocks.deleteGoal.mockRejectedValue(new ApiError('private backend detail', 500))
    const user = userEvent.setup()
    renderActivePlan()
    await waitFor(() => expect(getLastActiveGoalId()).toBe(goalA.id))

    await user.click(screen.getByRole('button', { name: 'Eliminar plan' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Eliminar plan' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No pudimos eliminar el plan. No se aplicó ningún cambio.',
    )
    expect(screen.getByRole('heading', { name: 'Plan guardado' })).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(getLastActiveGoalId()).toBe(goalA.id)
  })
})

describe('planning recovery for an active Goal without a plan', () => {
  beforeEach(() => {
    clearLastActiveGoalId()
    apiMocks.deleteGoal.mockReset()
    apiMocks.getActiveGoal.mockReset()
    apiMocks.getGoalPlan.mockReset()
    apiMocks.previewGoalPlan.mockReset()
    apiMocks.getGoalPlan.mockResolvedValue(planningPending)
  })

  it('recovers after refresh and generates a preview for the existing Goal', async () => {
    apiMocks.getActiveGoal.mockResolvedValue(goalA)
    apiMocks.previewGoalPlan.mockResolvedValue(preview)
    const user = userEvent.setup()
    renderPlanningRecovery()

    expect(await screen.findByRole('heading', { name: 'Tu objetivo está guardado.' }))
      .toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Generar plan' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Eliminar objetivo' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Generar plan' }))

    expect(await screen.findByRole('heading', { name: 'Tu recorrido inicial' }))
      .toBeInTheDocument()
    expect(apiMocks.getActiveGoal).toHaveBeenCalledOnce()
    expect(apiMocks.previewGoalPlan).toHaveBeenCalledOnce()
    expect(apiMocks.previewGoalPlan).toHaveBeenCalledWith(goalA.id)
    expect(screen.getByText('Primera etapa recuperada')).toBeInTheDocument()
  })

  it('keeps the recovery actions available after a sanitized planning error', async () => {
    apiMocks.getActiveGoal.mockResolvedValue(goalA)
    apiMocks.previewGoalPlan.mockRejectedValue(new ApiError('private provider detail', 504))
    const user = userEvent.setup()
    renderPlanningRecovery()

    await user.click(await screen.findByRole('button', { name: 'Generar plan' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'La planificación demoró demasiado. Podés intentarlo otra vez.',
    )
    expect(screen.getByRole('button', { name: 'Generar plan' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Eliminar objetivo' })).toBeEnabled()
  })

  it('deletes the unplanned Goal and returns Home without stale navigation', async () => {
    apiMocks.deleteGoal.mockResolvedValue(undefined)
    apiMocks.getActiveGoal.mockRejectedValue(new ApiError('Active goal not found', 404))
    const user = userEvent.setup()
    renderPlanningRecovery()

    await user.click(await screen.findByRole('button', { name: 'Eliminar objetivo' }))
    const dialog = screen.getByRole('dialog', { name: '¿Eliminar este objetivo?' })
    await user.click(within(dialog).getByRole('button', { name: 'Eliminar objetivo' }))

    expect(await screen.findByRole('link', { name: /Crear objetivo/ })).toBeInTheDocument()
    expect(apiMocks.deleteGoal).toHaveBeenCalledWith(goalA.id)
    expect(screen.queryByRole('link', { name: /Continuar con mi plan/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Mi plan' })).not.toBeInTheDocument()
    expect(getLastActiveGoalId()).toBeNull()
  })
})
