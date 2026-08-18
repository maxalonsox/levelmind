import { Link, useLocation, useParams } from 'react-router-dom'

import { AppShell } from '../components/AppShell'
import { PlanHierarchy } from '../components/PlanHierarchy'
import type { Goal } from '../types/goals'
import type { PlanPreview } from '../types/planning'

interface PreviewRouteState {
  goal: Goal
  preview: PlanPreview
}

export function PlanPreviewPage() {
  const { goalId } = useParams()
  const location = useLocation()
  const state = getPreviewRouteState(location.state, goalId)

  if (!state) {
    return (
      <AppShell eyebrow="Planificación inicial" title="Este preview ya no está disponible.">
        <section className="request-state-card">
          <h2>El plan propuesto todavía no se persiste</h2>
          <p>
            En F2 el preview vive sólo durante este flujo. Volvé a crear la propuesta; la
            persistencia mediante aceptación se incorporará en F3.
          </p>
          <Link className="button button--primary" to="/goals/new">
            Configurar otro objetivo
          </Link>
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
