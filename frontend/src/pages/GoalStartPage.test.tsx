import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import type { Goal } from '../types/goals'
import type { PlanPreview } from '../types/planning'
import { GoalStartPage } from './GoalStartPage'
import { PlanPreviewPage } from './PlanPreviewPage'

const apiMocks = vi.hoisted(() => ({
  createGoal: vi.fn(),
  previewGoalPlan: vi.fn(),
}))

vi.mock(import('../api/goals'), () => apiMocks)

const goal: Goal = {
  id: 'd499db65-7234-433a-8776-92bc02196ce6',
  user_id: '5de1ba50-14b8-4b39-89a9-9994aceb1b97',
  title: 'Convertirme en backend developer',
  current_situation: 'Conozco fundamentos de Python',
  expected_outcome: 'Crear y desplegar APIs de producción',
  target_timeframe: '6 meses',
  availability: '8 horas por semana',
  status: 'active',
  created_at: '2026-08-18T10:00:00Z',
  updated_at: '2026-08-18T10:00:00Z',
}

const preview: PlanPreview = {
  stages: [
    {
      title: 'Fundamentos de APIs',
      description: 'Construir una base sólida',
      order_index: 0,
      missions: [
        {
          title: 'Crear una API validada',
          description: 'Aplicar contratos explícitos',
          order_index: 0,
          estimated_difficulty: 'normal',
          tasks: [
            {
              title: 'Implementar el primer endpoint',
              description: 'Agregar validación de entrada',
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

const authValue: AuthContextValue = {
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

function renderGoalFlow() {
  return render(
    <AuthContext.Provider value={authValue}>
      <MemoryRouter initialEntries={['/goals/new']}>
        <Routes>
          <Route path="/goals/new" element={<GoalStartPage />} />
          <Route path="/goals/:goalId/plan" element={<PlanPreviewPage />} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

async function fillRequiredFields() {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText(/Objetivo profesional/), goal.title)
  await user.type(screen.getByLabelText(/Situación actual/), goal.current_situation)
  await user.type(screen.getByLabelText(/Resultado esperado/), goal.expected_outcome)
  return user
}

describe('GoalStartPage', () => {
  beforeEach(() => {
    apiMocks.createGoal.mockReset()
    apiMocks.previewGoalPlan.mockReset()
  })

  it('renders the five fields from the backend GoalCreate contract', () => {
    renderGoalFlow()

    expect(screen.getByLabelText(/Objetivo profesional/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Situación actual/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Resultado esperado/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Plazo aproximado/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Disponibilidad/)).toBeInTheDocument()
  })

  it('shows local validation errors without calling the API', async () => {
    renderGoalFlow()

    await userEvent.click(screen.getByRole('button', { name: /Crear y generar plan/ }))

    expect(screen.getByText('Ingresá un objetivo profesional.')).toBeInTheDocument()
    expect(screen.getByText('Contanos tu situación actual.')).toBeInTheDocument()
    expect(screen.getByText('Describí el resultado esperado.')).toBeInTheDocument()
    expect(apiMocks.createGoal).not.toHaveBeenCalled()
  })

  it('creates the exact payload, requests the preview, and renders its hierarchy', async () => {
    apiMocks.createGoal.mockResolvedValue(goal)
    apiMocks.previewGoalPlan.mockResolvedValue(preview)
    renderGoalFlow()
    const user = await fillRequiredFields()
    await user.type(screen.getByLabelText(/Plazo aproximado/), goal.target_timeframe!)
    await user.type(screen.getByLabelText(/Disponibilidad/), goal.availability!)

    await user.click(screen.getByRole('button', { name: /Crear y generar plan/ }))

    expect(await screen.findByText('Fundamentos de APIs')).toBeInTheDocument()
    expect(apiMocks.createGoal).toHaveBeenCalledWith({
      title: goal.title,
      current_situation: goal.current_situation,
      expected_outcome: goal.expected_outcome,
      target_timeframe: goal.target_timeframe,
      availability: goal.availability,
    })
    expect(apiMocks.previewGoalPlan).toHaveBeenCalledWith(goal.id)
    expect(screen.getByText('Crear una API validada')).toBeInTheDocument()
    expect(screen.getByText('Implementar el primer endpoint')).toBeInTheDocument()
    expect(screen.getByText('Normal')).toBeInTheDocument()
    expect(screen.getByText('45 min')).toBeInTheDocument()
  })

  it('shows a readable creation error and does not request a preview', async () => {
    apiMocks.createGoal.mockRejectedValue(new Error('database details'))
    renderGoalFlow()
    const user = await fillRequiredFields()

    await user.click(screen.getByRole('button', { name: /Crear y generar plan/ }))

    expect(
      await screen.findByText('No pudimos crear el objetivo. Intentá nuevamente en unos momentos.'),
    ).toBeInTheDocument()
    expect(apiMocks.previewGoalPlan).not.toHaveBeenCalled()
  })

  it('keeps the created goal and shows a retry action when preview fails', async () => {
    apiMocks.createGoal.mockResolvedValue(goal)
    apiMocks.previewGoalPlan
      .mockRejectedValueOnce(new Error('provider details'))
      .mockResolvedValueOnce(preview)
    renderGoalFlow()
    const user = await fillRequiredFields()

    await user.click(screen.getByRole('button', { name: /Crear y generar plan/ }))

    expect(await screen.findByText('El objetivo ya fue creado.')).toBeInTheDocument()
    expect(screen.getByText('No pudimos preparar el plan. Podés intentarlo nuevamente.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Reintentar planificación' }))

    expect(await screen.findByText('Fundamentos de APIs')).toBeInTheDocument()
    expect(apiMocks.createGoal).toHaveBeenCalledTimes(1)
    expect(apiMocks.previewGoalPlan).toHaveBeenCalledTimes(2)
  })

  it('explains the non-persisted preview limitation after a direct refresh', () => {
    render(
      <AuthContext.Provider value={authValue}>
        <MemoryRouter initialEntries={[`/goals/${goal.id}/plan`]}>
          <Routes>
            <Route path="/goals/:goalId/plan" element={<PlanPreviewPage />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>,
    )

    expect(screen.getByText('Este preview ya no está disponible.')).toBeInTheDocument()
    expect(screen.getByText(/el preview vive sólo durante este flujo/i)).toBeInTheDocument()
  })
})
