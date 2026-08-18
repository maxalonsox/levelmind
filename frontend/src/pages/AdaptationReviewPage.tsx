import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import { acceptAdaptation, rejectAdaptation } from '../api/adaptations'
import { getGoalPlan } from '../api/goals'
import { AdaptationChangeList } from '../components/AdaptationChangeList'
import { Alert } from '../components/Alert'
import { AppShell } from '../components/AppShell'
import {
  getAdaptationConflictError,
  getAdaptationReviewError,
  isAdaptationConflict,
} from '../lib/userFacingError'
import type { AdaptationPreviewResponse } from '../types/adaptation'
import type { Goal } from '../types/goals'
import type { GoalPlan } from '../types/planning'

interface AdaptationRouteState {
  preview: AdaptationPreviewResponse
  plan: GoalPlan
  goal: Goal | null
}

type ReviewStatus = 'idle' | 'accepting' | 'rejecting' | 'accepted' | 'rejected' | 'error' | 'conflict'

export function AdaptationReviewPage() {
  const { goalId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const [routeState] = useState(() => getAdaptationRouteState(location.state, goalId))
  const [status, setStatus] = useState<ReviewStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [refreshedPlan, setRefreshedPlan] = useState<GoalPlan | null>(null)
  const reviewInFlight = useRef(false)

  useEffect(() => {
    if (routeState && location.state !== null) {
      navigate(location.pathname, { replace: true, state: null })
    }
  }, [location.pathname, location.state, navigate, routeState])

  if (!goalId || !routeState) {
    return (
      <AppShell eyebrow="Revisión del plan" title="Esta revisión ya no está disponible">
        <section className="request-state-card">
          <p>
            Por seguridad, una propuesta no se guarda en este dispositivo. Volvé al plan para
            solicitar una nueva revisión cuando quieras.
          </p>
          <Link className="button button--primary" to={goalId ? `/goals/${goalId}` : '/'}>
            Volver al plan
          </Link>
        </section>
      </AppShell>
    )
  }

  const activeGoalId = goalId
  const { preview, plan, goal } = routeState
  const adaptation = preview.adaptation
  const isSubmitting = status === 'accepting' || status === 'rejecting'
  const isInvalid = status === 'conflict'
  const isFinal = status === 'accepted' || status === 'rejected'

  async function handleConflict(cause: unknown) {
    setStatus('conflict')
    setError(getAdaptationConflictError(cause))
    try {
      setRefreshedPlan(await getGoalPlan(activeGoalId))
    } catch {
      setRefreshedPlan(null)
    }
  }

  async function handleAccept() {
    if (!adaptation || reviewInFlight.current) return
    reviewInFlight.current = true
    setStatus('accepting')
    setError(null)

    try {
      const result = await acceptAdaptation(activeGoalId, adaptation.id)
      setStatus('accepted')
      try {
        const activePlan = await getGoalPlan(activeGoalId)
        navigate(`/goals/${activeGoalId}`, {
          replace: true,
          state: {
            activePlan,
            goal,
            adaptationNotice: `Se aplicaron ${result.applied_change_count} ajustes a tu plan.`,
          },
        })
      } catch {
        setError('Los cambios se aplicaron, pero no pudimos actualizar el plan. Volvé al plan para recargarlo.')
      }
    } catch (cause) {
      if (isAdaptationConflict(cause)) {
        await handleConflict(cause)
      } else {
        setStatus('error')
        setError(getAdaptationReviewError(cause))
      }
    } finally {
      reviewInFlight.current = false
    }
  }

  async function handleReject() {
    if (!adaptation || reviewInFlight.current) return
    reviewInFlight.current = true
    setStatus('rejecting')
    setError(null)

    try {
      await rejectAdaptation(activeGoalId, adaptation.id)
      setStatus('rejected')
      navigate(`/goals/${activeGoalId}`, {
        replace: true,
        state: {
          activePlan: plan,
          goal,
          adaptationNotice: 'Mantuviste tu plan actual. No se aplicaron cambios.',
        },
      })
    } catch (cause) {
      if (isAdaptationConflict(cause)) {
        await handleConflict(cause)
      } else {
        setStatus('error')
        setError(getAdaptationReviewError(cause))
      }
    } finally {
      reviewInFlight.current = false
    }
  }

  if (!adaptation) {
    const presentation = getNoChangePresentation(preview)
    return (
      <AppShell
        eyebrow="Revisión del plan"
        title={presentation.pageTitle}
        description="La revisión terminó y no propone modificaciones en este momento."
      >
        <section className="adaptation-result-card adaptation-result-card--no-change">
          <span className="adaptation-result-card__icon" aria-hidden="true">✓</span>
          <div>
            <p className="eyebrow">Sin cambios necesarios</p>
            <h2>{presentation.title}</h2>
            <p>{presentation.description}</p>
          </div>
        </section>
        <Link className="button button--primary" to={`/goals/${goalId}`} state={{ activePlan: plan, goal }}>
          Volver al plan
        </Link>
      </AppShell>
    )
  }

  return (
    <AppShell
      eyebrow="Revisión del plan"
      title="LevelMind propone algunos ajustes"
      description="Revisá cada cambio antes de decidir. Vos mantenés el control del plan."
    >
      <section className="adaptation-proposal-card">
        <div className="adaptation-proposal-card__intro">
          <span className="adaptation-ai-mark" aria-hidden="true">✦</span>
          <div>
            <p className="eyebrow">Propuesta para revisar</p>
            <h2>{preview.summary}</h2>
            <p>{preview.rationale}</p>
          </div>
        </div>
        <div className="adaptation-safety-note">
          <strong>Tu plan todavía no cambió.</strong>
          <span>Podés aceptar la propuesta o mantener el plan actual.</span>
        </div>
      </section>

      <AdaptationChangeList changes={preview.changes} />

      {error && <Alert>{error}</Alert>}

      <section className="adaptation-review-actions">
        {isInvalid || isFinal ? (
          <Link
            className="button button--primary"
            to={`/goals/${goalId}`}
            state={status === 'accepted' ? { goal } : { activePlan: refreshedPlan ?? plan, goal }}
          >
            Volver al plan
          </Link>
        ) : (
          <>
            <button
              className="button button--secondary"
              type="button"
              disabled={isSubmitting}
              onClick={() => void handleReject()}
            >
              {status === 'rejecting' ? 'Guardando decisión…' : 'Mantener plan actual'}
            </button>
            <button
              className="button button--primary"
              type="button"
              disabled={isSubmitting}
              onClick={() => void handleAccept()}
            >
              {status === 'accepting' ? 'Aplicando cambios…' : 'Aceptar cambios'}
            </button>
          </>
        )}
      </section>
    </AppShell>
  )
}

function getAdaptationRouteState(state: unknown, goalId: string | undefined): AdaptationRouteState | null {
  if (!isRecord(state) || !isRecord(state.preview) || !isRecord(state.plan)) return null
  if (state.plan.goal_id !== goalId) return null
  if (state.preview.decision !== 'no_change' && state.preview.decision !== 'propose_changes') return null
  return state as unknown as AdaptationRouteState
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function getNoChangePresentation(preview: AdaptationPreviewResponse) {
  const content = `${preview.summary} ${preview.rationale}`.toLowerCase()
  const insufficientEvidence = [
    'insufficient_data',
    'insufficient evidence',
    'not enough evidence',
    'poca evidencia',
    'evidencia insuficiente',
  ].some((marker) => content.includes(marker))

  if (insufficientEvidence) {
    return {
      pageTitle: 'Todavía necesitamos un poco más de información',
      title: 'Todavía necesitamos un poco más de información',
      description:
        'Completá algunas tareas más y LevelMind volverá a evaluar si conviene ajustar tu plan.',
    }
  }

  const technicalContent = [
    'needs_adaptation',
    'propose_changes',
    'evaluationresult',
    'adaptationproposal',
    'langgraph',
    'evaluationservice',
    'memoryentry',
  ].some((marker) => content.includes(marker))

  if (technicalContent) {
    return {
      pageTitle: 'Tu plan sigue funcionando bien',
      title: 'Tu plan sigue funcionando bien',
      description:
        'Por ahora no vemos motivos suficientes para modificarlo. Podés seguir avanzando con el plan actual.',
    }
  }

  return {
    pageTitle: 'Tu plan sigue funcionando bien',
    title: preview.summary,
    description: preview.rationale,
  }
}
