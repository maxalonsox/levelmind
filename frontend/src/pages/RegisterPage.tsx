import { useRef, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { Alert } from '../components/Alert'
import { Brand } from '../components/Brand'
import { LoadingState } from '../components/LoadingState'
import { getRegistrationError } from '../lib/userFacingError'
import { supabase } from '../lib/supabase'

export function RegisterPage() {
  const { isLoading: isAuthLoading, session } = useAuth()
  const navigate = useNavigate()
  const requestInFlight = useRef(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirmation, setPasswordConfirmation] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [requiresConfirmation, setRequiresConfirmation] = useState(false)

  if (isAuthLoading) return <LoadingState label="Comprobando tu sesión" fullScreen />
  if (session) return <Navigate to="/" replace />

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (requestInFlight.current) return

    setError(null)
    if (password !== passwordConfirmation) {
      setError('Las contraseñas no coinciden.')
      return
    }

    requestInFlight.current = true
    setIsSubmitting(true)
    try {
      const { data, error: signUpError } = await supabase.auth.signUp({
        email: email.trim(),
        password,
      })
      if (signUpError) throw signUpError

      if (data.session) {
        navigate('/', { replace: true })
      } else {
        setRequiresConfirmation(true)
      }
    } catch (cause) {
      setError(getRegistrationError(cause))
    } finally {
      requestInFlight.current = false
      setIsSubmitting(false)
    }
  }

  return (
    <main className="login-layout">
      <section className="login-intro" aria-labelledby="register-heading">
        <Brand linked={false} />
        <div className="login-intro__content">
          <p className="eyebrow">Tu recorrido en LevelMind</p>
          <h1 id="register-heading">
            Creá tu cuenta.
            <span> Empezá con un objetivo.</span>
          </h1>
          <p>
            Convertí tu meta profesional en un plan que puedas revisar, ejecutar y adaptar.
          </p>
        </div>
        <p className="login-intro__note">Un plan claro · Decisiones siempre bajo tu control</p>
      </section>

      <section className="login-panel">
        {requiresConfirmation ? (
          <div className="auth-card auth-card--confirmation" role="status">
            <div className="auth-card__heading">
              <span className="auth-card__signal" aria-hidden="true" />
              <p className="eyebrow">Cuenta creada</p>
              <h2>Revisá tu correo</h2>
              <p>
                Te enviamos un enlace para confirmar tu cuenta. Después de confirmarla vas a poder
                iniciar sesión.
              </p>
            </div>
            <Link className="button button--primary button--wide" to="/login">
              Ir a iniciar sesión
            </Link>
          </div>
        ) : (
          <form className="auth-card" onSubmit={handleSubmit} aria-describedby={error ? 'register-error' : undefined}>
            <div className="auth-card__heading">
              <span className="auth-card__signal" aria-hidden="true" />
              <p className="eyebrow">Registro</p>
              <h2>Crear cuenta</h2>
              <p>Usá un email al que puedas acceder.</p>
            </div>

            {error && <div id="register-error"><Alert>{error}</Alert></div>}

            <label className="field">
              <span>Email</span>
              <input
                type="email"
                name="email"
                autoComplete="email"
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
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                minLength={6}
                disabled={isSubmitting}
              />
            </label>

            <label className="field">
              <span>Repetir contraseña</span>
              <input
                type="password"
                name="password-confirmation"
                autoComplete="new-password"
                value={passwordConfirmation}
                onChange={(event) => setPasswordConfirmation(event.target.value)}
                required
                minLength={6}
                disabled={isSubmitting}
              />
            </label>

            <button className="button button--primary button--wide" disabled={isSubmitting}>
              {isSubmitting ? 'Creando cuenta…' : 'Crear cuenta'}
            </button>

            <p className="auth-card__footnote">
              ¿Ya tenés cuenta? <Link to="/login">Iniciar sesión</Link>
            </p>
          </form>
        )}
      </section>
    </main>
  )
}
