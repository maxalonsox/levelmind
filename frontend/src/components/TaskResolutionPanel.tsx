import { useState, type FormEvent } from 'react'

import type {
  Difficulty,
  PersistedTask,
  TaskResult,
  TaskResultCreate,
} from '../types/planning'

interface TaskResolutionPanelProps {
  task: PersistedTask
  isSubmitting: boolean
  error: string | null
  onCancel: () => void
  onSubmit: (payload: TaskResultCreate) => Promise<void>
}

const difficultyOptions: Array<{ label: string; value: Difficulty }> = [
  { label: 'Fácil', value: 'easy' },
  { label: 'Normal', value: 'normal' },
  { label: 'Difícil', value: 'difficult' },
]

export function TaskResolutionPanel({
  task,
  isSubmitting,
  error,
  onCancel,
  onSubmit,
}: TaskResolutionPanelProps) {
  const [result, setResult] = useState<TaskResult | null>(null)
  const [difficultyFeedback, setDifficultyFeedback] = useState<Difficulty | null>(null)
  const [feedbackText, setFeedbackText] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!result) {
      setValidationError('Elegí cómo resultó la tarea.')
      return
    }

    setValidationError(null)
    await onSubmit({
      result,
      difficulty_feedback: difficultyFeedback,
      feedback_text: feedbackText.trim() || null,
    })
  }

  return (
    <form className="task-resolution-panel" onSubmit={handleSubmit} noValidate>
      <div className="task-resolution-panel__heading">
        <div>
          <p className="eyebrow">Registrar resultado</p>
          <h4>{task.title}</h4>
        </div>
        <button
          className="button button--ghost button--small"
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
        >
          Cerrar
        </button>
      </div>

      <fieldset className="choice-group">
        <legend>¿Cómo resultó?</legend>
        <div className="result-options">
          <label className={result === 'completed' ? 'choice-card is-selected' : 'choice-card'}>
            <input
              type="radio"
              name="result"
              value="completed"
              checked={result === 'completed'}
              onChange={() => setResult('completed')}
              disabled={isSubmitting}
            />
            <span className="choice-card__icon" aria-hidden="true">✓</span>
            <span>
              <strong>Completada</strong>
              <small>Completé esta tarea</small>
            </span>
          </label>
          <label className={result === 'skipped' ? 'choice-card is-selected' : 'choice-card'}>
            <input
              type="radio"
              name="result"
              value="skipped"
              checked={result === 'skipped'}
              onChange={() => setResult('skipped')}
              disabled={isSubmitting}
            />
            <span className="choice-card__icon choice-card__icon--skipped" aria-hidden="true">–</span>
            <span>
              <strong>Omitida</strong>
              <small>No pude completarla</small>
            </span>
          </label>
        </div>
        {validationError && <span className="field__error">{validationError}</span>}
      </fieldset>

      <fieldset className="choice-group">
        <legend>¿Qué dificultad tuvo para vos?</legend>
        <p className="choice-group__hint">
          Es tu experiencia real y no modifica la dificultad estimada del plan.
        </p>
        <div className="difficulty-options">
          {difficultyOptions.map((option) => (
            <label
              className={
                difficultyFeedback === option.value
                  ? 'difficulty-option is-selected'
                  : 'difficulty-option'
              }
              key={option.value}
            >
              <input
                type="radio"
                name="difficulty-feedback"
                value={option.value}
                checked={difficultyFeedback === option.value}
                onChange={() => setDifficultyFeedback(option.value)}
                disabled={isSubmitting}
              />
              {option.label}
            </label>
          ))}
          <button
            className="difficulty-option difficulty-option--clear"
            type="button"
            onClick={() => setDifficultyFeedback(null)}
            disabled={isSubmitting || difficultyFeedback === null}
          >
            No indicar
          </button>
        </div>
      </fieldset>

      <label className="field field--goal task-feedback-field">
        <span>¿Querés agregar algún comentario?</span>
        <span className="field__hint">
          Esto ayuda a LevelMind a entender mejor cómo resultó la tarea.
        </span>
        <textarea
          value={feedbackText}
          onChange={(event) => setFeedbackText(event.target.value)}
          maxLength={2000}
          rows={3}
          placeholder="Opcional"
          disabled={isSubmitting}
        />
      </label>

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
          {isSubmitting ? (
            <>
              <span className="spinner spinner--small" aria-hidden="true" /> Guardando…
            </>
          ) : (
            'Guardar resultado'
          )}
        </button>
      </div>
    </form>
  )
}
