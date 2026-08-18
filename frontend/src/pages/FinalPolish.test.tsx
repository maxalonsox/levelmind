import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import { AppShell } from '../components/AppShell'
import { ApiError } from '../lib/api'
import {
  clearLastActiveGoalId,
  getLastActiveGoalId,
  setLastActiveGoalId,
} from '../lib/lastActiveGoal'
import type { GoalPlan } from '../types/planning'
import { ActivePlanPage } from './ActivePlanPage'
import { GoalStartPage } from './GoalStartPage'
import { HomePage } from './HomePage'
import { LoginPage } from './LoginPage'

const apiMocks = vi.hoisted(() => ({
  getActiveGoal: vi.fn(),
  getGoalPlan: vi.fn(),
}))

vi.mock(import('../api/goals'), async (importOriginal) => ({
  ...(await importOriginal()),
  getActiveGoal: apiMocks.getActiveGoal,
  getGoalPlan: apiMocks.getGoalPlan,
}))

const goalId = 'goal-navigation-id'
const timestamp = '2026-08-18T10:00:00Z'
const plan: GoalPlan = {
  goal_id: goalId,
  status: 'active',
  progress: {
    percentage: 0,
    xp_earned: 0,
    completed_tasks: 0,
    skipped_tasks: 0,
    pending_tasks: 0,
    total_tasks: 0,
  },
  stages: [],
}

function authValue(
  signOut: AuthContextValue['signOut'] = vi.fn().mockResolvedValue(undefined),
): AuthContextValue {
  return {
    isLoading: false,
    session: {
      access_token: 'test-token',
      refresh_token: 'test-refresh-token',
      expires_in: 3600,
      token_type: 'bearer',
      user: {
        id: 'user-id',
        email: 'user@example.com',
        app_metadata: {},
        user_metadata: {},
        aud: 'authenticated',
        created_at: timestamp,
      },
    },
    signIn: vi.fn(),
    signOut,
  }
}

function renderAuthenticated(children: ReactNode, signOut?: AuthContextValue['signOut']) {
  return render(
    <AuthContext.Provider value={authValue(signOut)}>{children}</AuthContext.Provider>,
  )
}

describe('final MVP navigation and session polish', () => {
  beforeEach(() => {
    clearLastActiveGoalId()
    apiMocks.getActiveGoal.mockReset()
    apiMocks.getGoalPlan.mockReset()
  })

  it('stores only the goal reference after opening a valid active plan', async () => {
    renderAuthenticated(
      <MemoryRouter initialEntries={[{ pathname: `/goals/${goalId}`, state: { activePlan: plan } }]}>
        <Routes><Route path="/goals/:goalId" element={<ActivePlanPage />} /></Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByText('Este objetivo todavía no tiene un plan activo.')).toBeInTheDocument()
    expect(getLastActiveGoalId()).toBe(goalId)
    expect(window.localStorage).toHaveLength(1)
  })

  it('does not show Mi plan from an unvalidated stored reference', () => {
    window.localStorage.setItem('levelmind:lastActiveGoalId', goalId)
    renderAuthenticated(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<AppShell title="Inicio de prueba" />} />
          <Route path="/goals/:goalId" element={<h1>Destino del plan</h1>} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.queryByRole('link', { name: 'Mi plan' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Destino del plan' })).not.toBeInTheDocument()
  })

  it('offers Continuar con mi plan on Home after backend recovery', async () => {
    window.localStorage.setItem('levelmind:lastActiveGoalId', goalId)
    apiMocks.getActiveGoal.mockResolvedValue({ id: goalId })
    renderAuthenticated(<MemoryRouter><HomePage /></MemoryRouter>)

    expect(await screen.findByRole('link', { name: /Continuar con mi plan/ })).toHaveAttribute(
      'href',
      `/goals/${goalId}`,
    )
    expect(screen.getByRole('link', { name: /Crear objetivo/ })).toBeInTheDocument()
  })

  it('clears a stale goal reference after the plan endpoint returns 404', async () => {
    setLastActiveGoalId(goalId, 'user-id')
    apiMocks.getGoalPlan.mockRejectedValue(new ApiError('Goal not found', 404))
    renderAuthenticated(
      <MemoryRouter initialEntries={[`/goals/${goalId}`]}>
        <Routes><Route path="/goals/:goalId" element={<ActivePlanPage />} /></Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByText('No encontramos este plan.')).toBeInTheDocument()
    expect(getLastActiveGoalId()).toBeNull()
    expect(screen.queryByRole('link', { name: 'Mi plan' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Volver al inicio' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Crear objetivo' })).toBeInTheDocument()
  })

  it('clears the reference after a successful logout', async () => {
    setLastActiveGoalId(goalId, 'user-id')
    const signOut = vi.fn().mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderAuthenticated(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<AppShell title="Inicio" />} />
          <Route path="/login" element={<h1>Sesión cerrada</h1>} />
        </Routes>
      </MemoryRouter>,
      signOut,
    )

    await user.click(screen.getByRole('button', { name: 'Salir' }))
    expect(await screen.findByRole('heading', { name: 'Sesión cerrada' })).toBeInTheDocument()
    expect(signOut).toHaveBeenCalledOnce()
    expect(getLastActiveGoalId()).toBeNull()
  })

  it('handles logout errors, keeps the session reference, and shows feedback', async () => {
    setLastActiveGoalId(goalId, 'user-id')
    const signOut = vi.fn().mockRejectedValue(new Error('private provider error'))
    const user = userEvent.setup()
    renderAuthenticated(
      <MemoryRouter><AppShell title="Inicio" /></MemoryRouter>,
      signOut,
    )

    await user.click(screen.getByRole('button', { name: 'Salir' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No pudimos cerrar la sesión. Intentá nuevamente.',
    )
    expect(getLastActiveGoalId()).toBe(goalId)
  })

  it('does not expose obsolete slice messaging in login or goal creation', () => {
    const unauthenticated: AuthContextValue = {
      isLoading: false,
      session: null,
      signIn: vi.fn(),
      signOut: vi.fn(),
    }
    const login = render(
      <AuthContext.Provider value={unauthenticated}>
        <MemoryRouter><LoginPage /></MemoryRouter>
      </AuthContext.Provider>,
    )
    expect(screen.queryByText(/próximo slice/i)).not.toBeInTheDocument()
    login.unmount()

    renderAuthenticated(<MemoryRouter><GoalStartPage /></MemoryRouter>)
    expect(screen.queryByText(/próximo slice/i)).not.toBeInTheDocument()
  })
})
