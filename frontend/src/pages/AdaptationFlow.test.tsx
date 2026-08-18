import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '../app/App'
import { AuthContext, type AuthContextValue } from '../auth/AuthContext'
import { ApiError } from '../lib/api'
import type {
  AdaptationAcceptResponse,
  AdaptationPreviewResponse,
  AdaptationRejectResponse,
} from '../types/adaptation'
import type { Goal } from '../types/goals'
import type { GoalPlan } from '../types/planning'
import { ActivePlanPage } from './ActivePlanPage'
import { AdaptationReviewPage } from './AdaptationReviewPage'

const apiMocks = vi.hoisted(() => ({
  acceptAdaptation: vi.fn(),
  getGoalPlan: vi.fn(),
  previewGoalAdaptation: vi.fn(),
  rejectAdaptation: vi.fn(),
}))

vi.mock(import('../api/adaptations'), () => ({
  acceptAdaptation: apiMocks.acceptAdaptation,
  previewGoalAdaptation: apiMocks.previewGoalAdaptation,
  rejectAdaptation: apiMocks.rejectAdaptation,
}))
vi.mock(import('../api/goals'), () => ({ getGoalPlan: apiMocks.getGoalPlan }))

const goalId = 'goal-id'
const adaptationId = 'adaptation-id'
const timestamp = '2026-08-18T10:00:00Z'

const goal: Goal = {
  id: goalId,
  user_id: 'user-id',
  title: 'Dominar backend',
  current_situation: 'Conozco Python',
  expected_outcome: 'Construir APIs',
  target_timeframe: null,
  availability: null,
  status: 'active',
  created_at: timestamp,
  updated_at: timestamp,
}

const activePlan: GoalPlan = {
  goal_id: goalId,
  status: 'active',
  progress: {
    percentage: 0,
    xp_earned: 0,
    completed_tasks: 0,
    skipped_tasks: 0,
    pending_tasks: 1,
    total_tasks: 1,
  },
  stages: [
    {
      id: 'stage-id',
      goal_id: goalId,
      title: 'Backend',
      description: null,
      order_index: 0,
      status: 'pending',
      created_at: timestamp,
      updated_at: timestamp,
      missions: [
        {
          id: 'mission-id',
          stage_id: 'stage-id',
          title: 'API delivery',
          description: null,
          order_index: 0,
          estimated_difficulty: 'normal',
          status: 'pending',
          created_at: timestamp,
          updated_at: timestamp,
          tasks: [
            {
              id: 'task-id',
              mission_id: 'mission-id',
              title: 'Implement endpoint',
              description: null,
              order_index: 0,
              estimated_duration_minutes: 45,
              estimated_difficulty: 'normal',
              xp_reward: 10,
              status: 'pending',
              difficulty_feedback: null,
              feedback_text: null,
              resolved_at: null,
              created_at: timestamp,
              updated_at: timestamp,
            },
          ],
        },
      ],
    },
  ],
}

const noChangePreview: AdaptationPreviewResponse = {
  decision: 'no_change',
  summary: 'El ritmo actual es sostenible.',
  rationale: 'La evidencia reciente no justifica modificar tareas.',
  changes: [],
  needs_adaptation: true,
  adaptation: null,
}

const proposalPreview: AdaptationPreviewResponse = {
  decision: 'propose_changes',
  summary: 'Conviene ajustar seis puntos del plan.',
  rationale: 'Tu ejecución reciente permite hacer cambios pequeños y concretos.',
  needs_adaptation: true,
  changes: [
    {
      type: 'add_task',
      target: {
        stage_order_index: 0,
        stage_title: 'Backend',
        mission_order_index: 0,
        mission_title: 'API delivery',
      },
      reason: 'Falta una práctica previa.',
      insert_after_task_order_index: null,
      task: {
        title: 'Definir reglas de validación',
        description: 'Documentar casos inválidos.',
        estimated_duration_minutes: 20,
        xp_reward: 5,
      },
    },
    {
      type: 'split_task',
      target: {
        stage_order_index: 0,
        stage_title: 'Backend',
        mission_order_index: 0,
        mission_title: 'API delivery',
        task_order_index: 0,
        task_title: 'Implement endpoint',
      },
      reason: 'La tarea es demasiado amplia.',
      replacement_tasks: [
        {
          title: 'Implementar request',
          description: null,
          estimated_duration_minutes: 30,
          xp_reward: 5,
        },
        {
          title: 'Implementar response',
          description: null,
          estimated_duration_minutes: 30,
          xp_reward: 5,
        },
      ],
    },
    {
      type: 'replace_task',
      target: {
        stage_order_index: 0,
        stage_title: 'Backend',
        mission_order_index: 0,
        mission_title: 'API delivery',
        task_order_index: 1,
        task_title: 'Leer documentación',
      },
      reason: 'Una práctica es más útil.',
      replacement: {
        title: 'Preparar checklist',
        description: 'Validar configuración.',
        estimated_duration_minutes: 25,
        xp_reward: 10,
      },
    },
    {
      type: 'reorder_task',
      target: {
        stage_order_index: 0,
        stage_title: 'Backend',
        mission_order_index: 0,
        mission_title: 'API delivery',
        task_order_index: 2,
        task_title: 'Probar endpoint',
      },
      reason: 'Probar antes reduce retrabajo.',
      destination_order_index: 0,
    },
    {
      type: 'adjust_task_difficulty',
      target: {
        stage_order_index: 0,
        stage_title: 'Backend',
        mission_order_index: 0,
        mission_title: 'API delivery',
        task_order_index: 3,
        task_title: 'Desplegar API',
      },
      reason: 'La dificultad estimada fue alta.',
      proposed_difficulty: 'easy',
    },
    {
      type: 'adjust_task_duration',
      target: {
        stage_order_index: 0,
        stage_title: 'Backend',
        mission_order_index: 0,
        mission_title: 'API delivery',
        task_order_index: 4,
        task_title: 'Integrar persistencia',
      },
      reason: 'La estimación anterior fue corta.',
      estimated_duration_minutes: 90,
    },
  ],
  adaptation: {
    id: adaptationId,
    goal_id: goalId,
    base_revision_id: 'revision-id',
    proposal: {
      decision: 'propose_changes',
      summary: 'Conviene ajustar seis puntos del plan.',
      rationale: 'Tu ejecución reciente permite hacer cambios pequeños y concretos.',
      changes: [],
    },
    status: 'pending',
    created_at: timestamp,
    updated_at: timestamp,
    reviewed_at: null,
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
      created_at: timestamp,
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

function renderFlow() {
  return render(
    <AuthContext.Provider value={authenticated}>
      <MemoryRouter initialEntries={[{ pathname: `/goals/${goalId}`, state: { goal } }]}>
        <Routes>
          <Route path="/goals/:goalId" element={<ActivePlanPage />} />
          <Route path="/goals/:goalId/adaptation" element={<AdaptationReviewPage />} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

async function openProposal(user: ReturnType<typeof userEvent.setup>) {
  apiMocks.previewGoalAdaptation.mockResolvedValue(proposalPreview)
  renderFlow()
  await user.click(await screen.findByRole('button', { name: 'Revisar mi plan' }))
  expect(await screen.findByRole('heading', { name: 'LevelMind propone algunos ajustes' })).toBeInTheDocument()
}

describe('adaptation HITL flow', () => {
  beforeEach(() => {
    apiMocks.acceptAdaptation.mockReset()
    apiMocks.getGoalPlan.mockReset()
    apiMocks.previewGoalAdaptation.mockReset()
    apiMocks.rejectAdaptation.mockReset()
    apiMocks.getGoalPlan.mockResolvedValue(activePlan)
  })

  it('starts one preview from the active plan and shows a blocking evaluation state', async () => {
    let finishPreview!: (value: AdaptationPreviewResponse) => void
    apiMocks.previewGoalAdaptation.mockReturnValue(
      new Promise<AdaptationPreviewResponse>((resolve) => {
        finishPreview = resolve
      }),
    )
    renderFlow()
    const user = userEvent.setup()

    await user.dblClick(await screen.findByRole('button', { name: 'Revisar mi plan' }))

    expect(apiMocks.previewGoalAdaptation).toHaveBeenCalledOnce()
    expect(apiMocks.previewGoalAdaptation).toHaveBeenCalledWith(goalId)
    expect(screen.getByRole('button', { name: 'LevelMind está evaluando tu progreso reciente…' })).toBeDisabled()
    expect(screen.getByText('Implement endpoint')).toBeInTheDocument()

    finishPreview(noChangePreview)
    expect(await screen.findByRole('heading', { name: 'Tu plan sigue funcionando bien' })).toBeInTheDocument()
  })

  it('renders backend no_change content without review actions', async () => {
    apiMocks.previewGoalAdaptation.mockResolvedValue(noChangePreview)
    renderFlow()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Revisar mi plan' }))

    expect(await screen.findByText(noChangePreview.summary)).toBeInTheDocument()
    expect(screen.getByText(noChangePreview.rationale)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Aceptar cambios' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Mantener plan actual' })).not.toBeInTheDocument()
  })

  it('replaces technical insufficient-data content with a concise user-facing fallback', async () => {
    apiMocks.previewGoalAdaptation.mockResolvedValue({
      ...noChangePreview,
      summary: 'The current evidence does not justify changing the plan.',
      rationale: 'The evaluation status is insufficient_data.',
      needs_adaptation: false,
    })
    renderFlow()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Revisar mi plan' }))

    expect(
      await screen.findAllByText('Todavía necesitamos un poco más de información'),
    ).toHaveLength(2)
    expect(
      screen.getByText(
        'Completá algunas tareas más y LevelMind volverá a evaluar si conviene ajustar tu plan.',
      ),
    ).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('insufficient_data')
  })

  it('renders every supported change in human language and no raw JSON', async () => {
    const user = userEvent.setup()
    await openProposal(user)

    for (const label of [
      'Agregar tarea',
      'Dividir tarea',
      'Reemplazar tarea',
      'Reordenar tarea',
      'Ajustar dificultad',
      'Ajustar duración',
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
    expect(screen.getByText('Definir reglas de validación')).toBeInTheDocument()
    expect(screen.getByText('Implementar request')).toBeInTheDocument()
    expect(screen.getByText('Leer documentación')).toBeInTheDocument()
    expect(screen.getByText('Preparar checklist')).toBeInTheDocument()
    expect(screen.getByText('Posición actual: 3')).toBeInTheDocument()
    expect(screen.getByText('Nueva posición: 1')).toBeInTheDocument()
    expect(screen.getByText('Dificultad propuesta: Fácil')).toBeInTheDocument()
    expect(screen.getByText('Nueva duración estimada: 90 min')).toBeInTheDocument()
    expect(screen.getByText('Tu plan todavía no cambió.')).toBeInTheDocument()
    expect(screen.getAllByText('¿Por qué este cambio?')).toHaveLength(6)
    expect(document.body.textContent).not.toContain('"type":"add_task"')
    expect(document.body.textContent).not.toContain('revision-id')
    expect(document.body.textContent).not.toContain(adaptationId)
  })

  it('accepts the existing adaptation once, refreshes the plan, and never previews again', async () => {
    let finishAccept!: (value: AdaptationAcceptResponse) => void
    apiMocks.acceptAdaptation.mockReturnValue(
      new Promise<AdaptationAcceptResponse>((resolve) => {
        finishAccept = resolve
      }),
    )
    const user = userEvent.setup()
    await openProposal(user)

    await user.dblClick(screen.getByRole('button', { name: 'Aceptar cambios' }))

    expect(apiMocks.acceptAdaptation).toHaveBeenCalledOnce()
    expect(apiMocks.acceptAdaptation).toHaveBeenCalledWith(goalId, adaptationId)
    expect(apiMocks.previewGoalAdaptation).toHaveBeenCalledOnce()
    expect(screen.getByRole('button', { name: 'Aplicando cambios…' })).toBeDisabled()
    expect(screen.getByText('Tu plan todavía no cambió.')).toBeInTheDocument()

    finishAccept({
      adaptation_id: adaptationId,
      status: 'accepted',
      reviewed_at: timestamp,
      revision_id: 'new-revision-id',
      revision_number: 2,
      applied_change_count: 6,
    })

    expect(await screen.findByText('Se aplicaron 6 ajustes a tu plan.')).toBeInTheDocument()
    expect(apiMocks.getGoalPlan).toHaveBeenCalledTimes(2)
    expect(apiMocks.previewGoalAdaptation).toHaveBeenCalledOnce()
  })

  it('rejects the existing adaptation without refreshing or changing the plan', async () => {
    const response: AdaptationRejectResponse = {
      adaptation_id: adaptationId,
      status: 'rejected',
      reviewed_at: timestamp,
    }
    apiMocks.rejectAdaptation.mockResolvedValue(response)
    const user = userEvent.setup()
    await openProposal(user)

    await user.click(screen.getByRole('button', { name: 'Mantener plan actual' }))

    expect(apiMocks.rejectAdaptation).toHaveBeenCalledWith(goalId, adaptationId)
    expect(apiMocks.previewGoalAdaptation).toHaveBeenCalledOnce()
    expect(await screen.findByText('Mantuviste tu plan actual. No se aplicaron cambios.')).toBeInTheDocument()
    expect(screen.getByText('Implement endpoint')).toBeInTheDocument()
    expect(apiMocks.getGoalPlan).toHaveBeenCalledOnce()
  })

  it('invalidates a stale proposal, refreshes the plan, and explains the conflict', async () => {
    apiMocks.acceptAdaptation.mockRejectedValue(
      new ApiError('Adaptation was created for an obsolete plan revision', 409),
    )
    const user = userEvent.setup()
    await openProposal(user)

    await user.click(screen.getByRole('button', { name: 'Aceptar cambios' }))

    expect(
      await screen.findByText(
        'El plan cambió desde que se generó esta propuesta. Volvé a revisarlo para obtener una recomendación actualizada.',
      ),
    ).toBeInTheDocument()
    expect(apiMocks.getGoalPlan).toHaveBeenCalledTimes(2)
    expect(screen.queryByRole('button', { name: 'Aceptar cambios' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Mantener plan actual' })).not.toBeInTheDocument()
  })

  it('shows an already-reviewed conflict without retrying preview', async () => {
    apiMocks.rejectAdaptation.mockRejectedValue(
      new ApiError('Adaptation has already been reviewed', 409),
    )
    const user = userEvent.setup()
    await openProposal(user)

    await user.click(screen.getByRole('button', { name: 'Mantener plan actual' }))

    expect(await screen.findByText('Esta propuesta ya fue revisada.')).toBeInTheDocument()
    expect(apiMocks.previewGoalAdaptation).toHaveBeenCalledOnce()
  })

  it.each([
    [503, 'El servicio de IA no está disponible en este momento.'],
    [504, 'La evaluación tardó demasiado. Podés intentar nuevamente.'],
  ])('maps preview error %s without leaving the current plan', async (status, message) => {
    apiMocks.previewGoalAdaptation.mockRejectedValue(new ApiError('internal detail', status))
    renderFlow()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Revisar mi plan' }))

    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(screen.getByText('Implement endpoint')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Revisar mi plan' })).toBeEnabled()
  })

  it('shows a specific safe message when adaptation preview exhausts rate-limit retries', async () => {
    apiMocks.previewGoalAdaptation.mockRejectedValue(
      new ApiError('AI service rate limit exceeded', 502),
    )
    renderFlow()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Revisar mi plan' }))

    expect(
      await screen.findByText(
        'El servicio de IA está recibiendo demasiadas solicitudes. Esperá unos segundos e intentá nuevamente.',
      ),
    ).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('OpenRouter')
    expect(document.body.textContent).not.toContain('429')
    expect(screen.getByText('Implement endpoint')).toBeInTheDocument()
  })

  it('keeps the generic fallback for other adaptation preview 502 errors', async () => {
    apiMocks.previewGoalAdaptation.mockRejectedValue(
      new ApiError('Adaptation provider returned an invalid response', 502),
    )
    renderFlow()
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Revisar mi plan' }))

    expect(
      await screen.findByText('No pudimos interpretar la evaluación. Podés intentarlo nuevamente.'),
    ).toBeInTheDocument()
  })

  it('does not create another preview when the review route is refreshed without state', () => {
    render(
      <AuthContext.Provider value={authenticated}>
        <MemoryRouter initialEntries={[`/goals/${goalId}/adaptation`]}>
          <Routes>
            <Route path="/goals/:goalId/adaptation" element={<AdaptationReviewPage />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>,
    )

    expect(screen.getByRole('heading', { name: 'Esta revisión ya no está disponible' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Volver al plan' })).toBeInTheDocument()
    expect(apiMocks.previewGoalAdaptation).not.toHaveBeenCalled()
  })

  it('keeps the adaptation route protected', async () => {
    render(
      <AuthContext.Provider value={unauthenticated}>
        <MemoryRouter initialEntries={[`/goals/${goalId}/adaptation`]}>
          <App />
        </MemoryRouter>
      </AuthContext.Provider>,
    )

    expect(await screen.findByRole('heading', { name: 'Ingresá a LevelMind' })).toBeInTheDocument()
    expect(apiMocks.previewGoalAdaptation).not.toHaveBeenCalled()
  })
})
