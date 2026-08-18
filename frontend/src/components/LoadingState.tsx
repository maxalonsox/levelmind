interface LoadingStateProps {
  label?: string
  fullScreen?: boolean
}

export function LoadingState({
  label = 'Cargando',
  fullScreen = false,
}: LoadingStateProps) {
  return (
    <div className={fullScreen ? 'status-state status-state--fullscreen' : 'status-state'}>
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}
