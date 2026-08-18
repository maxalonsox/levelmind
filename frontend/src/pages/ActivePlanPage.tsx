import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import { previewGoalAdaptation } from '../api/adaptations'
import { getGoalPlan } from '../api/goals'
import { resolveTask } from '../api/tasks'
import { ActivePlanHierarchy } from '../components/ActivePlanHierarchy'
import { Alert } from '../components/Alert'
import { AppShell } from '../components/AppShell'
import { LoadingState } from '../components/LoadingState'
import { TaskResolutionPanel } from '../components/TaskResolutionPanel'
import {
  getActivePlanError,
  getAdaptationPreviewError,
  getTaskResolutionError,
  isActivePlanNotFoundError,
  isTaskAlreadyResolvedError,
} from '../lib/userFacingError'
import { clearLastActiveGoalId, setLastActiveGoalId } from '../lib/lastActiveGoal'
import type { Goal } from '../types/goals'
import type { GoalPlan, PersistedTask, TaskResultCreate } from '../types/planning'

interface ResolutionNotice {
  kind: 'success' | 'info'
  message: string
}

export function ActivePlanPage() {
  const { goalId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const goal = getRouteGoal(location.state, goalId)
  const routePlan = getRoutePlan(location.state, goalId)
  const adaptationNotice = getRouteAdaptationNotice(location.state)
  const [plan, setPlan] = useState<GoalPlan | null>(routePlan)
  const [isLoading, setIsLoading] = useState(routePlan === null)
  const [error, setError] = useState<string | null>(null)
  const [planNotFound, setPlanNotFound] = useState(false)
  const [isEvaluating, setIsEvaluating] = useState(false)
  const [adaptationError, setAdaptationError] = useState<string | null>(null)
  const [selectedTask, setSelectedTask] = useState<PersistedTask | null>(null)
  const [isResolving, setIsResolving] = useState(false)
  const [resolutionError, setResolutionError] = useState<string | null>(null)
  const [resolutionNotice, setResolutionNotice] = useState<ResolutionNotice | null>(null)
  const resolutionInFlight = useRef(false)
  const evaluationInFlight = useRef(false)

  async function retryPlan() {
    if (!goalId) return

    setIsLoading(true)
    setError(null)
    setPlanNotFound(false)
    try {
      setPlan(await getGoalPlan(goalId))
    } catch (cause) {
      if (isActivePlanNotFoundError(cause)) {
        clearLastActiveGoalId()
        setPlanNotFound(true)
      }
      setError(getActivePlanError(cause))
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (!goalId || routePlan) return

    let isActive = true
    void getGoalPlan(goalId)
      .then((activePlan) => {
        if (isActive) setPlan(activePlan)
      })
      .catch((cause: unknown) => {
        if (isActive) {
          if (isActivePlanNotFoundError(cause)) {
            clearLastActiveGoalId()
            setPlanNotFound(true)
          }
          setError(getActivePlanError(cause))
        }
      })
      .finally(() => {
        if (isActive) setIsLoading(false)
      })

    return () => {
      isActive = false
    }
  }, [goalId, routePlan])

  useEffect(() => {
    if (goalId && plan) setLastActiveGoalId(goalId)
  }, [goalId, plan])

  async function reviewPlan() {
    if (!goalId || !plan || evaluationInFlight.current) return
    evaluationInFlight.current = true
    setIsEvaluating(true)
    setAdaptationError(null)

    try {
      const preview = await previewGoalAdaptation(goalId)
      navigate(`/goals/${goalId}/adaptation`, {
        state: { preview, plan, goal },
      })
    } catch (cause) {
      setAdaptationError(getAdaptationPreviewError(cause))
    } finally {
      evaluationInFlight.current = false
      setIsEvaluating(false)
    }
  }

  function selectTask(task: PersistedTask) {
    setSelectedTask(task)
    setResolutionError(null)
    setResolutionNotice(null)
  }

  async function handleTaskResult(payload: TaskResultCreate) {
    if (!goalId || !selectedTask || resolutionInFlight.current) return

    resolutionInFlight.current = true
    setIsResolving(true)
    setResolutionError(null)
    setResolutionNotice(null)

    try {
      const result = await resolveTask(selectedTask.id, payload)

      try {
        const refreshedPlan = await getGoalPlan(goalId)
        setPlan(refreshedPlan)
        setSelectedTask(null)
        setResolutionNotice({
          kind: 'success',
          message:
            result.xp_awarded > 0
              ? `Tarea completada. +${result.xp_awarded} XP`
              : 'Resultado registrado. El plan ya está actualizado.',
        })
      } catch {
        setResolutionError(
          'El resultado se guardó, pero no pudimos actualizar el plan. Volvé a intentarlo.',
        )
      }
    } catch (cause) {
      if (isTaskAlreadyResolvedError(cause)) {
        try {
          setPlan(await getGoalPlan(goalId))
          setSelectedTask(null)
          setResolutionNotice({
            kind: 'info',
            message: 'La tarea ya tenía otro resultado. Actualizamos el plan con su estado real.',
          })
        } catch {
          setResolutionError(
            'La tarea ya fue resuelta y no pudimos actualizar el plan. Recargá la página.',
          )
        }
      } else {
        setResolutionError(getTaskResolutionError(cause))
      }
    } finally {
      resolutionInFlight.current = false
      setIsResolving(false)
    }
  }

  if (isLoading) {
    return (
      <AppShell eyebrow="Plan activo" title="Cargando tu plan…">
        <LoadingState label="Consultando la versión guardada" />
      </AppShell>
    )
  }

  if (error || !plan) {
    return (
      <AppShell eyebrow="Plan activo" title="No pudimos mostrar tu plan.">
        <section className="request-state-card">
          <Alert>{error ?? 'No encontramos información para este plan.'}</Alert>
          {planNotFound ? (
            <div className="request-state-card__actions">
              <Link className="button button--primary" to="/">Volver al inicio</Link>
              <Link className="button button--secondary" to="/goals/new">Crear objetivo</Link>
            </div>
          ) : (
            <button className="button button--primary" onClick={() => void retryPlan()}>
              Reintentar
            </button>
          )}
        </section>
      </AppShell>
    )
  }

  if (plan.stages.length === 0) {
    return (
      <AppShell eyebrow="Plan activo" title="Este objetivo todavía no tiene un plan activo.">
        <section className="request-state-card">
          <p>
            No encontramos una jerarquía persistida. Un preview sólo se convierte en plan activo
            después de que lo aceptás.
          </p>
          <Link className="button button--secondary" to="/">
            Volver al inicio
          </Link>
        </section>
      </AppShell>
    )
  }

  return (
    <AppShell
      eyebrow="Plan activo"
      title="Tu plan está listo"
      description="La propuesta fue confirmada por el backend y ya forma parte de tu recorrido activo."
    >
      <section className="active-plan-banner">
        <span className="active-plan-banner__check" aria-hidden="true">
          ✓
        </span>
        <div>
          <span className="active-badge">Plan activo</span>
          <h2>{goal?.title ?? 'Objetivo profesional'}</h2>
          <p>Podés volver a consultar esta estructura porque ya está persistida.</p>
        </div>
      </section>

      <section className="progress-summary" aria-label="Progreso del plan">
        <div>
          <span>Progreso</span>
          <strong>{plan.progress.percentage}%</strong>
        </div>
        <div>
          <span>Tareas pendientes</span>
          <strong>{plan.progress.pending_tasks}</strong>
        </div>
        <div>
          <span>XP obtenido</span>
          <strong>{plan.progress.xp_earned}</strong>
        </div>
      </section>

      {resolutionNotice && (
        <div className={`plan-notice plan-notice--${resolutionNotice.kind}`} role="status">
          <span aria-hidden="true">{resolutionNotice.kind === 'success' ? '✓' : 'i'}</span>
          <p>{resolutionNotice.message}</p>
        </div>
      )}

      {adaptationNotice && (
        <div className="plan-notice plan-notice--success" role="status">
          <span aria-hidden="true">✓</span>
          <p>{adaptationNotice}</p>
        </div>
      )}

      <section className="adaptation-entry-card">
        <div>
          <p className="eyebrow">Plan adaptable</p>
          <h2>¿Querés revisar cómo viene funcionando?</h2>
          <p>LevelMind puede evaluar tu progreso reciente y sugerir ajustes si hacen falta.</p>
          {adaptationError && <Alert>{adaptationError}</Alert>}
        </div>
        <button
          className="button button--secondary adaptation-entry-card__action"
          type="button"
          disabled={isEvaluating}
          onClick={() => void reviewPlan()}
        >
          {isEvaluating ? 'LevelMind está evaluando tu progreso reciente…' : 'Revisar mi plan'}
        </button>
      </section>

      <div className="plan-preview-heading">
        <div>
          <p className="eyebrow">Objetivo → Etapas → Misiones → Tareas</p>
          <h2>Plan guardado</h2>
        </div>
      </div>

      <ActivePlanHierarchy
        stages={plan.stages}
        selectedTaskId={selectedTask?.id ?? null}
        onSelectTask={selectTask}
        renderResolutionPanel={(task) => (
          <TaskResolutionPanel
            task={task}
            isSubmitting={isResolving}
            error={resolutionError}
            onCancel={() => {
              setSelectedTask(null)
              setResolutionError(null)
            }}
            onSubmit={handleTaskResult}
          />
        )}
      />
    </AppShell>
  )
}

function getRouteGoal(state: unknown, goalId: string | undefined): Goal | null {
  if (typeof state !== 'object' || state === null || !('goal' in state)) {
    return null
  }

  const candidate = state.goal
  if (
    typeof candidate !== 'object' ||
    candidate === null ||
    !('id' in candidate) ||
    candidate.id !== goalId
  ) {
    return null
  }

  return candidate as Goal
}

function getRoutePlan(state: unknown, goalId: string | undefined): GoalPlan | null {
  if (typeof state !== 'object' || state === null || !('activePlan' in state)) return null
  const candidate = state.activePlan
  if (
    typeof candidate !== 'object' ||
    candidate === null ||
    !('goal_id' in candidate) ||
    candidate.goal_id !== goalId
  ) return null
  return candidate as GoalPlan
}

function getRouteAdaptationNotice(state: unknown): string | null {
  if (typeof state !== 'object' || state === null || !('adaptationNotice' in state)) return null
  return typeof state.adaptationNotice === 'string' ? state.adaptationNotice : null
}
