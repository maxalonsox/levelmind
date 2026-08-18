import { Link } from 'react-router-dom'

import { AppShell } from '../components/AppShell'

export function GoalStartPage() {
  return (
    <AppShell
      eyebrow="Nuevo objetivo"
      title="Prepará tu próximo objetivo profesional."
      description="El formulario de creación y el preview del plan se incorporarán en el próximo slice end-to-end."
    >
      <section className="empty-card">
        <span className="empty-card__icon" aria-hidden="true">
          +
        </span>
        <h2>Foundation lista</h2>
        <p>
          Esta ruta ya está protegida y preparada para conectar el flujo real de creación con
          FastAPI, sin adelantar funcionalidad fuera de F1.
        </p>
        <Link className="button button--secondary" to="/">
          Volver al inicio
        </Link>
      </section>
    </AppShell>
  )
}
