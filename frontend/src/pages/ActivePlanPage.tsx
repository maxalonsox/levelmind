import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'

import { getGoalPlan } from '../api/goals'
import { Alert } from '../components/Alert'
import { AppShell } from '../components/AppShell'
import { LoadingState } from '../components/LoadingState'
import { PlanHierarchy } from '../components/PlanHierarchy'
import { getActivePlanError } from '../lib/userFacingError'
import type { Goal } from '../types/goals'
import type { GoalPlan } from '../types/planning'

export function ActivePlanPage() {
  const { goalId } = useParams()
  const location = useLocation()
  const goal = getRouteGoal(location.state, goalId)
  const [plan, setPlan] = useState<GoalPlan | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function retryPlan() {
    if (!goalId) return

    setIsLoading(true)
    setError(null)
    try {
      setPlan(await getGoalPlan(goalId))
    } catch (cause) {
      setError(getActivePlanError(cause))
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (!goalId) return

    let isActive = true
    void getGoalPlan(goalId)
      .then((activePlan) => {
        if (isActive) setPlan(activePlan)
      })
      .catch((cause: unknown) => {
        if (isActive) setError(getActivePlanError(cause))
      })
      .finally(() => {
        if (isActive) setIsLoading(false)
      })

    return () => {
      isActive = false
    }
  }, [goalId])

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
          <button className="button button--primary" onClick={() => void retryPlan()}>
            Reintentar
          </button>
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

      <div className="plan-preview-heading">
        <div>
          <p className="eyebrow">Objetivo → Etapas → Misiones → Tareas</p>
          <h2>Plan guardado</h2>
        </div>
      </div>

      <PlanHierarchy preview={plan} />
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
