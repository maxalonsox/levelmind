import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { getActiveGoal } from '../api/goals'
import { useAuth } from '../auth/AuthContext'
import { Alert } from '../components/Alert'
import { AppShell } from '../components/AppShell'
import {
  clearLastActiveGoalId,
  setLastActiveGoalId,
} from '../lib/lastActiveGoal'
import { isActiveGoalNotFoundError } from '../lib/userFacingError'

export function HomePage() {
  const { session } = useAuth()
  const currentUserId = session?.user.id
  const [recovery, setRecovery] = useState({
    userId: currentUserId,
    isComplete: false,
    error: null as string | null,
    goalId: null as string | null,
  })
  const isRecoveringGoal = recovery.userId !== currentUserId || !recovery.isComplete
  const recoveryError = recovery.userId === currentUserId ? recovery.error : null
  const activeGoalId = recovery.userId === currentUserId ? recovery.goalId : null

  useEffect(() => {
    let isActive = true
    clearLastActiveGoalId()
    if (!currentUserId) {
      return () => {
        isActive = false
      }
    }

    void getActiveGoal()
      .then((goal) => {
        if (!isActive) return
        if (currentUserId) setLastActiveGoalId(goal.id, currentUserId)
        setRecovery({ userId: currentUserId, isComplete: true, error: null, goalId: goal.id })
      })
      .catch((cause: unknown) => {
        if (!isActive) return
        clearLastActiveGoalId()
        setRecovery({
          userId: currentUserId,
          isComplete: true,
          goalId: null,
          error: isActiveGoalNotFoundError(cause)
            ? null
            : 'No pudimos recuperar tu plan activo. Podés intentarlo recargando la página.',
        })
      })

    return () => {
      isActive = false
    }
  }, [currentUserId])

  return (
    <AppShell title="Tu camino empieza con un objetivo." eyebrow="Inicio">
      <section className="hero-card">
        <div className="hero-card__glow" aria-hidden="true" />
        <div className="hero-card__content">
          <span className="path-icon" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          <div>
            <p className="eyebrow">Primer paso</p>
            <h2>Transformá una meta profesional en un plan que puedas ejecutar.</h2>
            <p>
              LevelMind organizará tu objetivo en etapas, misiones y tareas. Antes de guardar el
              plan, siempre vas a poder revisarlo.
            </p>
          </div>
          {recoveryError && <Alert>{recoveryError}</Alert>}
          <div className="hero-card__actions">
            {isRecoveringGoal ? (
              <span className="button button--primary" role="status">Buscando tu plan…</span>
            ) : (
              <>
                {activeGoalId && (
                  <Link className="button button--primary" to={`/goals/${activeGoalId}`}>
                    Continuar con mi plan <span aria-hidden="true">→</span>
                  </Link>
                )}
                <Link
                  className={`button ${activeGoalId ? 'button--secondary' : 'button--primary'}`}
                  to="/goals/new"
                >
                  Crear objetivo <span aria-hidden="true">→</span>
                </Link>
              </>
            )}
          </div>
        </div>
      </section>

      <section className="principles-grid" aria-label="Cómo funciona LevelMind">
        <article className="info-card">
          <span className="info-card__number">01</span>
          <h3>Definí tu norte</h3>
          <p>Contanos qué querés lograr y cuál es tu punto de partida.</p>
        </article>
        <article className="info-card">
          <span className="info-card__number">02</span>
          <h3>Revisá el plan</h3>
          <p>La IA propone una estructura; vos conservás la decisión final.</p>
        </article>
        <article className="info-card">
          <span className="info-card__number">03</span>
          <h3>Avanzá y adaptá</h3>
          <p>Tu ejecución y feedback ayudan a mantener el camino relevante.</p>
        </article>
      </section>
    </AppShell>
  )
}
