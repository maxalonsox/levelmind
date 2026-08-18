import { useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import { acceptGoalPlan } from '../api/goals'
import { Alert } from '../components/Alert'
import { AppShell } from '../components/AppShell'
import { PlanHierarchy } from '../components/PlanHierarchy'
import {
  getPlanAcceptanceError,
  isPlanAlreadyAcceptedError,
} from '../lib/userFacingError'
import type { Goal } from '../types/goals'
import type { PlanPreview } from '../types/planning'

interface PreviewRouteState {
  goal: Goal
  preview: PlanPreview
}

export function PlanPreviewPage() {
  const { goalId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const state = getPreviewRouteState(location.state, goalId)
  const requestInFlight = useRef(false)
  const [isAccepting, setIsAccepting] = useState(false)
  const [acceptanceError, setAcceptanceError] = useState<string | null>(null)
  const [hasConflict, setHasConflict] = useState(false)

  async function handleAccept() {
    if (!state || requestInFlight.current) return

    requestInFlight.current = true
    setIsAccepting(true)
    setAcceptanceError(null)
    setHasConflict(false)

    try {
      await acceptGoalPlan(state.goal.id, state.preview)
      navigate(`/goals/${state.goal.id}`, {
        replace: true,
        state: { goal: state.goal },
      })
    } catch (error) {
      if (isPlanAlreadyAcceptedError(error)) {
        setHasConflict(true)
        setAcceptanceError(
          'Este objetivo ya tiene un plan activo. Podés continuar hacia la versión guardada.',
        )
      } else {
        setAcceptanceError(getPlanAcceptanceError(error))
      }
    } finally {
      requestInFlight.current = false
      setIsAccepting(false)
    }
  }

  if (!state) {
    return (
      <AppShell eyebrow="Planificación inicial" title="Este preview ya no está disponible.">
        <section className="request-state-card">
          <h2>El plan propuesto todavía no se persiste</h2>
          <p>
            El preview sin aceptar vive sólo durante esta navegación. Si ya confirmaste la
            propuesta, consultá la versión guardada.
          </p>
          <div className="request-state-card__actions">
            <Link className="button button--primary" to={`/goals/${goalId}`}>
              Ver plan activo
            </Link>
            <Link className="button button--secondary" to="/">
              Volver al inicio
            </Link>
          </div>
        </section>
      </AppShell>
    )
  }

  const { goal, preview } = state

  return (
    <AppShell
      eyebrow="Plan propuesto"
      title={goal.title}
      description="Revisá cómo LevelMind transformó tu objetivo en un recorrido accionable. Este preview todavía no fue aceptado ni persistido."
    >
      <section className="goal-summary-card">
        <div>
          <span>Resultado esperado</span>
          <p>{goal.expected_outcome}</p>
        </div>
        {goal.target_timeframe && (
          <div>
            <span>Plazo</span>
            <p>{goal.target_timeframe}</p>
          </div>
        )}
        {goal.availability && (
          <div>
            <span>Disponibilidad</span>
            <p>{goal.availability}</p>
          </div>
        )}
      </section>

      <div className="plan-preview-heading">
        <div>
          <p className="eyebrow">Objetivo → Etapas → Misiones → Tareas</p>
          <h2>Tu recorrido inicial</h2>
        </div>
        <span className="preview-badge">Preview</span>
      </div>

      <PlanHierarchy preview={preview} />

      <section className="acceptance-card" aria-live="polite">
        <div>
          <p className="eyebrow">Tu decisión</p>
          <h2>{hasConflict ? 'El plan ya está activo' : '¿Listo para comenzar?'}</h2>
          <p>
            {hasConflict
              ? 'La propuesta no se volvió a guardar. Consultá el plan persistido para continuar.'
              : 'Revisá la propuesta antes de confirmarla. El plan se guardará recién cuando lo aceptes.'}
          </p>
        </div>

        {acceptanceError && (
          <Alert title={hasConflict ? 'Plan aceptado anteriormente' : undefined}>
            {acceptanceError}
          </Alert>
        )}

        {hasConflict ? (
          <button
            className="button button--primary acceptance-card__action"
            onClick={() => navigate(`/goals/${goal.id}`, { state: { goal } })}
          >
            Ver plan activo
          </button>
        ) : (
          <button
            className="button button--primary acceptance-card__action"
            onClick={() => void handleAccept()}
            disabled={isAccepting}
          >
            {isAccepting ? (
              <>
                <span className="spinner spinner--small" aria-hidden="true" /> Guardando plan…
              </>
            ) : (
              'Aceptar plan'
            )}
          </button>
        )}
      </section>
    </AppShell>
  )
}

function getPreviewRouteState(state: unknown, goalId: string | undefined): PreviewRouteState | null {
  if (
    typeof state !== 'object' ||
    state === null ||
    !('goal' in state) ||
    !('preview' in state)
  ) {
    return null
  }

  const candidate = state as Partial<PreviewRouteState>
  if (
    !candidate.goal ||
    candidate.goal.id !== goalId ||
    !candidate.preview ||
    !Array.isArray(candidate.preview.stages)
  ) {
    return null
  }

  return candidate as PreviewRouteState
}
