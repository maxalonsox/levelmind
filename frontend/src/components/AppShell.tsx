import type { PropsWithChildren, ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
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

  async function handleSignOut() {
    await signOut()
    navigate('/login', { replace: true })
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
          </nav>
          <div className="topbar__account">
            <span className="topbar__email">{session?.user.email}</span>
            <button className="button button--ghost button--small" onClick={handleSignOut}>
              Salir
            </button>
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
