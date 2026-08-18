import { Link } from 'react-router-dom'

import { AppShell } from '../components/AppShell'
import { useLastActiveGoalId } from '../lib/lastActiveGoal'

export function HomePage() {
  const lastActiveGoalId = useLastActiveGoalId()

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
          <div className="hero-card__actions">
            {lastActiveGoalId && (
              <Link className="button button--primary" to={`/goals/${lastActiveGoalId}`}>
                Continuar con mi plan <span aria-hidden="true">→</span>
              </Link>
            )}
            <Link
              className={`button ${lastActiveGoalId ? 'button--secondary' : 'button--primary'}`}
              to="/goals/new"
            >
              Crear objetivo <span aria-hidden="true">→</span>
            </Link>
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
