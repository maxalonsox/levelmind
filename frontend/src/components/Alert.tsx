import type { PropsWithChildren } from 'react'

interface AlertProps extends PropsWithChildren {
  title?: string
}

export function Alert({ children, title = 'No pudimos completar la acción' }: AlertProps) {
  return (
    <div className="alert" role="alert">
      <span className="alert__icon" aria-hidden="true">
        !
      </span>
      <div>
        <strong>{title}</strong>
        <p>{children}</p>
      </div>
    </div>
  )
}
