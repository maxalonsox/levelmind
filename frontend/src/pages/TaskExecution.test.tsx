import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import { ApiError } from '../lib/api'
import type { GoalPlan, PersistedTask, TaskResultResponse } from '../types/planning'
import { ActivePlanPage } from './ActivePlanPage'

const apiMocks = vi.hoisted(() => ({
  getGoalPlan: vi.fn(),
  resolveTask: vi.fn(),
}))

vi.mock(import('../api/goals'), () => ({ getGoalPlan: apiMocks.getGoalPlan }))
vi.mock(import('../api/tasks'), () => ({ resolveTask: apiMocks.resolveTask }))

const goalId = 'goal-id'
const timestamp = '2026-08-18T10:00:00Z'

const pendingTask: PersistedTask = {
  id: 'pending-task-id',
  mission_id: 'mission-id',
  title: 'Implementar endpoint',
  description: 'Agregar validación y persistencia',
  order_index: 0,
  estimated_duration_minutes: 45,
  estimated_difficulty: 'easy',
  xp_reward: 10,
  status: 'pending',
  difficulty_feedback: null,
  feedback_text: null,
  resolved_at: null,
  created_at: timestamp,
  updated_at: timestamp,
}

const completedTask: PersistedTask = {
  ...pendingTask,
  id: 'completed-task-id',
  title: 'Diseñar contrato',
  order_index: 1,
  xp_reward: 5,
  status: 'completed',
  difficulty_feedback: 'difficult',
  feedback_text: 'El contrato requirió más casos de borde.',
  resolved_at: timestamp,
}

function planWith(
  task: PersistedTask,
  options: {
    hierarchyStatus?: 'in_progress' | 'completed'
    percentage?: number
    pendingTasks?: number
    skippedTasks?: number
    xpEarned?: number
  } = {},
): GoalPlan {
  const hierarchyStatus = options.hierarchyStatus ?? 'in_progress'

  return {
    goal_id: goalId,
    status: hierarchyStatus === 'completed' ? 'completed' : 'active',
    progress: {
      percentage: options.percentage ?? 50,
      xp_earned: options.xpEarned ?? 5,
      completed_tasks: options.percentage === 100 ? 2 : 1,
      skipped_tasks: options.skippedTasks ?? 0,
      pending_tasks: options.pendingTasks ?? 1,
      total_tasks: 2,
    },
    stages: [
      {
        id: 'stage-id',
        goal_id: goalId,
        title: 'Backend sólido',
        description: 'Construir fundamentos confiables',
        order_index: 0,
        status: hierarchyStatus,
        created_at: timestamp,
        updated_at: timestamp,
        missions: [
          {
            id: 'mission-id',
            stage_id: 'stage-id',
            title: 'API de tareas',
            description: 'Implementar el flujo completo',
            order_index: 0,
            estimated_difficulty: 'normal',
            status: hierarchyStatus,
            created_at: timestamp,
            updated_at: timestamp,
            tasks: [task, completedTask],
          },
        ],
      },
    ],
  }
}

const authenticated: AuthContextValue = {
  isLoading: false,
  session: {
    access_token: 'test-token',
    refresh_token: 'test-refresh-token',
    expires_in: 3600,
    token_type: 'bearer',
    user: {
      id: 'user-id',
      app_metadata: {},
      user_metadata: {},
      aud: 'authenticated',
      created_at: timestamp,
    },
  },
  signIn: vi.fn(),
  signOut: vi.fn(),
}

function renderActivePlan() {
  return render(
    <AuthContext.Provider value={authenticated}>
      <MemoryRouter initialEntries={[`/goals/${goalId}`]}>
        <Routes>
          <Route path="/goals/:goalId" element={<ActivePlanPage />} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

function resolvedTask(
  result: 'completed' | 'skipped',
  difficultyFeedback: PersistedTask['difficulty_feedback'],
  feedbackText: string | null,
): TaskResultResponse {
  return {
    ...pendingTask,
    status: result,
    difficulty_feedback: difficultyFeedback,
    feedback_text: feedbackText,
    resolved_at: timestamp,
    xp_awarded: result === 'completed' ? pendingTask.xp_reward : 0,
  }
}

describe('task execution from the active plan', () => {
  beforeEach(() => {
    apiMocks.getGoalPlan.mockReset()
    apiMocks.resolveTask.mockReset()
  })

  it('renders the persisted hierarchy and only offers resolution for pending tasks', async () => {
    apiMocks.getGoalPlan.mockResolvedValue(planWith(pendingTask))
    renderActivePlan()

    expect(await screen.findByText('Backend sólido')).toBeInTheDocument()
    expect(screen.getByText('API de tareas')).toBeInTheDocument()
    expect(screen.getByText('Implementar endpoint')).toBeInTheDocument()
    expect(screen.getByText('Diseñar contrato')).toBeInTheDocument()
    expect(screen.getByText('Tu feedback: Difícil')).toBeInTheDocument()
    expect(screen.getByText('“El contrato requirió más casos de borde.”')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Registrar resultado' })).toHaveLength(1)
  })

  it('submits completed once, keeps backend state while loading, then refreshes progress and XP', async () => {
    let finishRequest!: (value: TaskResultResponse) => void
    const updatedTask = resolvedTask('completed', 'normal', 'Se completó sin bloqueos.')
    const updatedPlan = planWith(updatedTask, {
      hierarchyStatus: 'completed',
      percentage: 100,
      pendingTasks: 0,
      xpEarned: 15,
    })
    apiMocks.getGoalPlan.mockResolvedValueOnce(planWith(pendingTask)).mockResolvedValueOnce(updatedPlan)
    apiMocks.resolveTask.mockReturnValue(
      new Promise<TaskResultResponse>((resolve) => {
        finishRequest = resolve
      }),
    )
    renderActivePlan()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Registrar resultado' }))
    await user.click(screen.getByRole('radio', { name: /Completada/ }))
    await user.click(screen.getByRole('radio', { name: 'Normal' }))
    await user.type(
      screen.getByRole('textbox', { name: /Querés agregar algún comentario/ }),
      '  Se completó sin bloqueos.  ',
    )
    await user.dblClick(screen.getByRole('button', { name: 'Guardar resultado' }))

    expect(apiMocks.resolveTask).toHaveBeenCalledOnce()
    expect(apiMocks.resolveTask).toHaveBeenCalledWith('pending-task-id', {
      result: 'completed',
      difficulty_feedback: 'normal',
      feedback_text: 'Se completó sin bloqueos.',
    })
    expect(screen.getByRole('button', { name: 'Guardando…' })).toBeDisabled()
    expect(screen.getByText('50%')).toBeInTheDocument()
    expect(screen.getAllByText('Implementar endpoint')).toHaveLength(2)

    finishRequest(updatedTask)

    expect(await screen.findByText('100%')).toBeInTheDocument()
    expect(screen.getByText('15')).toBeInTheDocument()
    expect(screen.getByText('Tarea completada. +10 XP')).toBeInTheDocument()
    expect(screen.getAllByText('Completada').length).toBeGreaterThanOrEqual(3)
    expect(apiMocks.getGoalPlan).toHaveBeenCalledTimes(2)
    expect(apiMocks.getGoalPlan).toHaveBeenLastCalledWith(goalId)
    expect(screen.queryByRole('button', { name: 'Registrar resultado' })).not.toBeInTheDocument()
  })

  it('submits skipped with optional fields empty and never reuses estimated difficulty', async () => {
    const updatedTask = resolvedTask('skipped', null, null)
    apiMocks.getGoalPlan
      .mockResolvedValueOnce(planWith(pendingTask))
      .mockResolvedValueOnce(
        planWith(updatedTask, { pendingTasks: 0, skippedTasks: 1, xpEarned: 5 }),
      )
    apiMocks.resolveTask.mockResolvedValue(updatedTask)
    renderActivePlan()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Registrar resultado' }))
    await user.click(screen.getByRole('radio', { name: /Omitida/ }))
    await user.click(screen.getByRole('button', { name: 'Guardar resultado' }))

    await waitFor(() => {
      expect(apiMocks.resolveTask).toHaveBeenCalledWith('pending-task-id', {
        result: 'skipped',
        difficulty_feedback: null,
        feedback_text: null,
      })
    })
    expect(await screen.findByText('Resultado registrado. El plan ya está actualizado.')).toBeInTheDocument()
  })

  it('shows a readable error and does not apply an optimistic result', async () => {
    apiMocks.getGoalPlan.mockResolvedValue(planWith(pendingTask))
    apiMocks.resolveTask.mockRejectedValue(new ApiError('database detail', 500))
    renderActivePlan()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Registrar resultado' }))
    await user.click(screen.getByRole('radio', { name: /Completada/ }))
    await user.click(screen.getByRole('button', { name: 'Guardar resultado' }))

    expect(
      await screen.findByText('No pudimos guardar el resultado. Ningún cambio parcial fue aplicado.'),
    ).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
    expect(apiMocks.getGoalPlan).toHaveBeenCalledOnce()
    expect(screen.getByRole('button', { name: 'Guardar resultado' })).toBeEnabled()
  })

  it('refreshes authoritative state after a double-resolution conflict', async () => {
    const updatedTask = resolvedTask('completed', 'easy', null)
    apiMocks.getGoalPlan
      .mockResolvedValueOnce(planWith(pendingTask))
      .mockResolvedValueOnce(
        planWith(updatedTask, {
          hierarchyStatus: 'completed',
          percentage: 100,
          pendingTasks: 0,
          xpEarned: 15,
        }),
      )
    apiMocks.resolveTask.mockRejectedValue(new ApiError('already terminal', 409))
    renderActivePlan()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Registrar resultado' }))
    await user.click(screen.getByRole('radio', { name: /Omitida/ }))
    await user.click(screen.getByRole('button', { name: 'Guardar resultado' }))

    expect(
      await screen.findByText(
        'La tarea ya tenía otro resultado. Actualizamos el plan con su estado real.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('100%')).toBeInTheDocument()
    expect(apiMocks.getGoalPlan).toHaveBeenCalledTimes(2)
    expect(screen.queryByRole('button', { name: 'Registrar resultado' })).not.toBeInTheDocument()
  })
})
