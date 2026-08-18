import { ApiError } from './api'

export function getGoalCreationError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Tu sesión venció. Volvé a iniciar sesión.'
    if (error.status === 422) return 'Revisá los datos del objetivo e intentá nuevamente.'
  }

  return 'No pudimos crear el objetivo. Intentá nuevamente en unos momentos.'
}

export function getPlanningError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Tu sesión venció. Volvé a iniciar sesión.'
    if (error.status === 404) return 'No encontramos el objetivo para generar su plan.'
    if (error.status === 502) return 'La propuesta recibida no fue válida. Podés intentarlo otra vez.'
    if (error.status === 503) return 'La planificación no está disponible en este momento.'
    if (error.status === 504) return 'La planificación demoró demasiado. Podés intentarlo otra vez.'
  }

  return 'No pudimos preparar el plan. Podés intentarlo nuevamente.'
}
