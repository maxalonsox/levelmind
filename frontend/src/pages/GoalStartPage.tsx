import { useState, type ChangeEvent, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { createGoal, previewGoalPlan } from '../api/goals'
import { Alert } from '../components/Alert'
import { AppShell } from '../components/AppShell'
import { getGoalCreationError, getPlanningError } from '../lib/userFacingError'
import type { Goal, GoalCreate } from '../types/goals'

interface GoalFormValues {
  title: string
  currentSituation: string
  expectedOutcome: string
  targetTimeframe: string
  availability: string
}

type GoalField = keyof GoalFormValues
type FormErrors = Partial<Record<GoalField, string>>
type SubmissionPhase = 'idle' | 'creating' | 'planning' | 'preview-error'

const initialValues: GoalFormValues = {
  title: '',
  currentSituation: '',
  expectedOutcome: '',
  targetTimeframe: '',
  availability: '',
}

export function GoalStartPage() {
  const navigate = useNavigate()
  const [values, setValues] = useState(initialValues)
  const [errors, setErrors] = useState<FormErrors>({})
  const [phase, setPhase] = useState<SubmissionPhase>('idle')
  const [requestError, setRequestError] = useState<string | null>(null)
  const [createdGoal, setCreatedGoal] = useState<Goal | null>(null)

  const isSubmitting = phase === 'creating' || phase === 'planning'

  function updateField(field: GoalField, value: string) {
    setValues((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({ ...current, [field]: undefined }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextErrors = validateGoal(values)

    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      setRequestError(null)
      return
    }

    setPhase('creating')
    setRequestError(null)

    let goal: Goal
    try {
      goal = await createGoal(toGoalCreate(values))
      setCreatedGoal(goal)
    } catch (error) {
      setPhase('idle')
      setRequestError(getGoalCreationError(error))
      return
    }

    await generatePreview(goal)
  }

  async function generatePreview(goal: Goal) {
    setPhase('planning')
    setRequestError(null)

    try {
      const preview = await previewGoalPlan(goal.id)
      navigate(`/goals/${goal.id}/plan`, {
        state: { goal, preview },
      })
    } catch (error) {
      setPhase('preview-error')
      setRequestError(getPlanningError(error))
    }
  }

  if (phase === 'planning') {
    return (
      <AppShell eyebrow="Planificación inicial" title="LevelMind está preparando tu plan…">
        <section className="planner-state" aria-live="polite">
          <div className="planner-orbit" aria-hidden="true">
            <span />
          </div>
          <div>
            <p className="eyebrow">IA trabajando</p>
            <h2>Convirtiendo tu objetivo en un camino concreto</h2>
            <p>
              Estamos organizando etapas, misiones y tareas según tu contexto y disponibilidad.
            </p>
          </div>
        </section>
      </AppShell>
    )
  }

  if (phase === 'preview-error' && createdGoal) {
    return (
      <AppShell eyebrow="Planificación inicial" title="El objetivo ya fue creado.">
        <section className="request-state-card">
          <Alert title="No pudimos generar la propuesta">{requestError}</Alert>
          <h2>{createdGoal.title}</h2>
          <p>
            Tu objetivo está guardado. Reintentar sólo vuelve a solicitar el preview y no crea un
            objetivo duplicado.
          </p>
          <button
            className="button button--primary"
            onClick={() => void generatePreview(createdGoal)}
          >
            Reintentar planificación
          </button>
        </section>
      </AppShell>
    )
  }

  return (
    <AppShell
      eyebrow="Nuevo objetivo"
      title="Configurar objetivo"
      description="Danos el contexto esencial. LevelMind lo convertirá en una propuesta que vas a poder revisar antes de aceptarla."
    >
      <div className="goal-setup-layout">
        <form className="goal-form-card" onSubmit={handleSubmit} noValidate>
          <div className="goal-form-card__heading">
            <span className="goal-form-card__step">Paso 1 de 2</span>
            <h2>Definí qué querés conseguir</h2>
            <p>Los campos marcados con * son necesarios para crear el objetivo.</p>
          </div>

          {requestError && <Alert>{requestError}</Alert>}

          <GoalFieldControl
            id="title"
            label="Objetivo profesional"
            hint="Una frase clara y específica."
            value={values.title}
            error={errors.title}
            maxLength={200}
            placeholder="Ej. Conseguir mi primer rol como backend developer"
            onChange={(value) => updateField('title', value)}
            disabled={isSubmitting}
            required
          />

          <GoalFieldControl
            id="current-situation"
            label="Situación actual"
            hint="Contanos qué experiencia o conocimientos tenés hoy."
            value={values.currentSituation}
            error={errors.currentSituation}
            placeholder="Ej. Conozco fundamentos de Python y construí proyectos pequeños"
            onChange={(value) => updateField('currentSituation', value)}
            disabled={isSubmitting}
            required
            multiline
          />

          <GoalFieldControl
            id="expected-outcome"
            label="Resultado esperado"
            hint="¿Qué cambio concreto indicaría que alcanzaste el objetivo?"
            value={values.expectedOutcome}
            error={errors.expectedOutcome}
            placeholder="Ej. Crear y desplegar APIs de producción y superar una entrevista técnica"
            onChange={(value) => updateField('expectedOutcome', value)}
            disabled={isSubmitting}
            required
            multiline
          />

          <div className="goal-form-grid">
            <GoalFieldControl
              id="target-timeframe"
              label="Plazo aproximado"
              hint="Opcional"
              value={values.targetTimeframe}
              error={errors.targetTimeframe}
              maxLength={100}
              placeholder="Ej. 6 meses"
              onChange={(value) => updateField('targetTimeframe', value)}
              disabled={isSubmitting}
            />
            <GoalFieldControl
              id="availability"
              label="Disponibilidad"
              hint="Opcional"
              value={values.availability}
              error={errors.availability}
              placeholder="Ej. 8 horas por semana"
              onChange={(value) => updateField('availability', value)}
              disabled={isSubmitting}
            />
          </div>

          <div className="goal-form-card__actions">
            <p>El plan generado todavía no se guardará: primero vas a revisarlo.</p>
            <button className="button button--primary" disabled={isSubmitting}>
              {phase === 'creating' ? (
                <>
                  <span className="spinner spinner--small" aria-hidden="true" /> Creando objetivo…
                </>
              ) : (
                <>
                  Crear y generar plan <span aria-hidden="true">→</span>
                </>
              )}
            </button>
          </div>
        </form>

        <aside className="goal-flow-card" aria-label="Próximos pasos">
          <p className="eyebrow">Cómo funciona</p>
          <ol>
            <li className="is-active">
              <span>1</span>
              <div>
                <strong>Contexto</strong>
                <p>Definís tu objetivo y punto de partida.</p>
              </div>
            </li>
            <li>
              <span>2</span>
              <div>
                <strong>Propuesta</strong>
                <p>LevelMind organiza etapas, misiones y tareas.</p>
              </div>
            </li>
            <li>
              <span>3</span>
              <div>
                <strong>Tu decisión</strong>
                <p>La aceptación del plan llegará en el próximo slice.</p>
              </div>
            </li>
          </ol>
          <div className="goal-flow-card__note">
            <span aria-hidden="true">◇</span>
            <p>La IA propone. Vos mantenés el control sobre los cambios importantes.</p>
          </div>
        </aside>
      </div>
    </AppShell>
  )
}

interface GoalFieldControlProps {
  id: string
  label: string
  hint: string
  value: string
  error?: string
  placeholder: string
  onChange: (value: string) => void
  disabled: boolean
  maxLength?: number
  multiline?: boolean
  required?: boolean
}

function GoalFieldControl({
  id,
  label,
  hint,
  value,
  error,
  placeholder,
  onChange,
  disabled,
  maxLength,
  multiline = false,
  required = false,
}: GoalFieldControlProps) {
  const describedBy = error ? `${id}-hint ${id}-error` : `${id}-hint`
  const commonProps = {
    id,
    name: id,
    value,
    placeholder,
    disabled,
    maxLength,
    required,
    'aria-invalid': Boolean(error),
    'aria-describedby': describedBy,
    onChange: (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      onChange(event.target.value),
  }

  return (
    <div className="field field--goal">
      <label htmlFor={id}>
        {label} {required && <span aria-hidden="true">*</span>}
      </label>
      <span className="field__hint" id={`${id}-hint`}>
        {hint}
      </span>
      {multiline ? <textarea {...commonProps} rows={4} /> : <input {...commonProps} />}
      {error && (
        <span className="field__error" id={`${id}-error`}>
          {error}
        </span>
      )}
    </div>
  )
}

function validateGoal(values: GoalFormValues): FormErrors {
  const errors: FormErrors = {}

  if (!values.title.trim()) errors.title = 'Ingresá un objetivo profesional.'
  if (values.title.trim().length > 200) errors.title = 'Usá como máximo 200 caracteres.'
  if (!values.currentSituation.trim()) errors.currentSituation = 'Contanos tu situación actual.'
  if (!values.expectedOutcome.trim()) errors.expectedOutcome = 'Describí el resultado esperado.'
  if (values.targetTimeframe.trim().length > 100) {
    errors.targetTimeframe = 'Usá como máximo 100 caracteres.'
  }

  return errors
}

function toGoalCreate(values: GoalFormValues): GoalCreate {
  return {
    title: values.title.trim(),
    current_situation: values.currentSituation.trim(),
    expected_outcome: values.expectedOutcome.trim(),
    target_timeframe: values.targetTimeframe.trim() || null,
    availability: values.availability.trim() || null,
  }
}
