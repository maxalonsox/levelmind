import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { Alert } from '../components/Alert'
import { Brand } from '../components/Brand'
import { LoadingState } from '../components/LoadingState'
import { getLoginError } from '../lib/userFacingError'

export function LoginPage() {
  const { isLoading: isAuthLoading, session, signIn } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const destination = getSafeDestination(location.state)

  if (isAuthLoading) {
    return <LoadingState label="Comprobando tu sesión" fullScreen />
  }

  if (session) {
    return <Navigate to={destination} replace />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      await signIn(email.trim(), password)
      navigate(destination, { replace: true })
    } catch (cause) {
      setError(getLoginError(cause))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="login-layout">
      <section className="login-intro" aria-labelledby="login-heading">
        <Brand linked={false} />
        <div className="login-intro__content">
          <p className="eyebrow">Planificación adaptativa</p>
          <h1 id="login-heading">
            Avanzá con claridad.
            <span> Adaptá el camino.</span>
          </h1>
          <p>
            Convertí tu objetivo profesional en etapas, misiones y tareas concretas, sin perder
            el control de las decisiones importantes.
          </p>
        </div>
        <p className="login-intro__note">Objetivos claros · Progreso real · Adaptación con vos</p>
      </section>

      <section className="login-panel">
        <form className="auth-card" onSubmit={handleSubmit}>
          <div className="auth-card__heading">
            <span className="auth-card__signal" aria-hidden="true" />
            <p className="eyebrow">Bienvenido</p>
            <h2>Ingresá a LevelMind</h2>
            <p>Continuá construyendo tu camino profesional.</p>
          </div>

          {error && <Alert>{error}</Alert>}

          <label className="field">
            <span>Email</span>
            <input
              type="email"
              name="email"
              autoComplete="email"
              placeholder="vos@ejemplo.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              disabled={isSubmitting}
            />
          </label>

          <label className="field">
            <span>Contraseña</span>
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              placeholder="Tu contraseña"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={6}
              disabled={isSubmitting}
            />
          </label>

          <button className="button button--primary button--wide" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <span className="spinner spinner--small" aria-hidden="true" /> Ingresando…
              </>
            ) : (
              'Ingresar'
            )}
          </button>

          <p className="auth-card__footnote">
            ¿No tenés cuenta? <Link to="/register">Crear cuenta</Link>
          </p>
        </form>
      </section>
    </main>
  )
}

function getSafeDestination(state: unknown): string {
  if (
    typeof state === 'object' &&
    state !== null &&
    'from' in state &&
    typeof state.from === 'string' &&
    state.from.startsWith('/') &&
    !state.from.startsWith('//')
  ) {
    return state.from
  }

  return '/'
}
