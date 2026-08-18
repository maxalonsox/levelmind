import { useState, type FormEvent } from 'react'

import type { PersistedTask, TaskUpdate } from '../types/planning'

interface TaskEditPanelProps {
  task: PersistedTask
  isSubmitting: boolean
  error: string | null
  onCancel: () => void
  onSubmit: (payload: TaskUpdate) => Promise<void>
}

export function TaskEditPanel({
  task,
  isSubmitting,
  error,
  onCancel,
  onSubmit,
}: TaskEditPanelProps) {
  const [title, setTitle] = useState(task.title)
  const [description, setDescription] = useState(task.description ?? '')
  const [duration, setDuration] = useState(
    task.estimated_duration_minutes?.toString() ?? '',
  )
  const [validationError, setValidationError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalizedTitle = title.trim()
    const parsedDuration = duration === '' ? null : Number(duration)
    if (!normalizedTitle) {
      setValidationError('Ingresá un título para la tarea.')
      return
    }
    if (
      parsedDuration !== null &&
      (!Number.isInteger(parsedDuration) || parsedDuration <= 0)
    ) {
      setValidationError('La duración debe ser un número entero mayor que cero.')
      return
    }

    setValidationError(null)
    await onSubmit({
      title: normalizedTitle,
      description: description.trim() || null,
      estimated_duration_minutes: parsedDuration,
    })
  }

  return (
    <form className="task-resolution-panel" onSubmit={handleSubmit} noValidate>
      <div className="task-resolution-panel__heading">
        <div>
          <p className="eyebrow">Editar tarea</p>
          <h4>{task.title}</h4>
        </div>
      </div>

      <label className="field field--goal">
        <span>Título</span>
        <input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          maxLength={200}
          disabled={isSubmitting}
        />
      </label>
      <label className="field field--goal">
        <span>Descripción</span>
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          maxLength={2000}
          rows={3}
          disabled={isSubmitting}
        />
      </label>
      <label className="field field--goal">
        <span>Duración estimada en minutos</span>
        <input
          type="number"
          min="1"
          step="1"
          value={duration}
          onChange={(event) => setDuration(event.target.value)}
          disabled={isSubmitting}
        />
      </label>

      {validationError && <p className="field__error">{validationError}</p>}
      {error && <p className="task-resolution-panel__error" role="alert">{error}</p>}

      <div className="task-resolution-panel__actions">
        <button
          className="button button--secondary"
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
        >
          Cancelar
        </button>
        <button className="button button--primary" disabled={isSubmitting}>
          {isSubmitting ? 'Guardando…' : 'Guardar cambios'}
        </button>
      </div>
    </form>
  )
}
