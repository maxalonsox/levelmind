import { useState, type PropsWithChildren, type ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { clearLastActiveGoalId, useLastActiveGoalId } from '../lib/lastActiveGoal'
import { Brand } from './Brand'

interface AppShellProps extends PropsWithChildren {
  eyebrow?: string
  title: string
  description?: string
  action?: ReactNode
}

export function AppShell({ children, eyebrow, title, description, action }: AppShellProps) {
  const { session, signOut } = useAuth()
  const navigate = useNavigate()
  const lastActiveGoalId = useLastActiveGoalId()
  const [signOutError, setSignOutError] = useState<string | null>(null)
  const [isSigningOut, setIsSigningOut] = useState(false)

  async function handleSignOut() {
    setSignOutError(null)
    setIsSigningOut(true)
    try {
      await signOut()
      clearLastActiveGoalId()
      navigate('/login', { replace: true })
    } catch {
      setSignOutError('No pudimos cerrar la sesión. Intentá nuevamente.')
    } finally {
      setIsSigningOut(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar__inner">
          <Brand />
          <nav className="topbar__nav" aria-label="Navegación principal">
            <NavLink to="/" end>
              Inicio
            </NavLink>
            {lastActiveGoalId && <NavLink to={`/goals/${lastActiveGoalId}`}>Mi plan</NavLink>}
          </nav>
          <div className="topbar__account">
            <span className="topbar__email">{session?.user.email}</span>
            <button
              className="button button--ghost button--small"
              disabled={isSigningOut}
              onClick={() => void handleSignOut()}
            >
              {isSigningOut ? 'Saliendo…' : 'Salir'}
            </button>
            {signOutError && <span className="topbar__signout-error" role="alert">{signOutError}</span>}
          </div>
        </div>
      </header>

      <main className="page-container">
        <div className="page-heading">
          <div>
            {eyebrow && <p className="eyebrow">{eyebrow}</p>}
            <h1>{title}</h1>
            {description && <p className="page-heading__description">{description}</p>}
          </div>
          {action && <div className="page-heading__action">{action}</div>}
        </div>
        {children}
      </main>
    </div>
  )
}
