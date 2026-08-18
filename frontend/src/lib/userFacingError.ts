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

export function isPlanAlreadyAcceptedError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409
}

export function getPlanAcceptanceError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Tu sesión venció. Volvé a iniciar sesión.'
    if (error.status === 404) return 'No encontramos el objetivo que querés confirmar.'
    if (error.status === 422) return 'La propuesta ya no tiene un formato válido.'
    if (error.status === 500) return 'No pudimos guardar el plan. Ningún cambio parcial fue aplicado.'
  }

  return 'No pudimos aceptar el plan. Intentá nuevamente.'
}

export function getActivePlanError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Tu sesión venció. Volvé a iniciar sesión.'
    if (error.status === 404) return 'No encontramos este plan.'
  }

  return 'No pudimos cargar el plan activo. Intentá nuevamente.'
}

export function isActivePlanNotFoundError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404
}

export function isTaskAlreadyResolvedError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409
}

export function getTaskResolutionError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Tu sesión venció. Volvé a iniciar sesión.'
    if (error.status === 404) return 'No encontramos la tarea que querés actualizar.'
    if (error.status === 422) return 'Revisá el resultado y el feedback ingresados.'
    if (error.status === 500) return 'No pudimos guardar el resultado. Ningún cambio parcial fue aplicado.'
  }

  return 'No pudimos registrar el resultado. Intentá nuevamente.'
}

export function getAdaptationPreviewError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Tu sesión venció. Volvé a iniciar sesión.'
    if (error.status === 404) return 'No encontramos el plan que querés revisar.'
    if (error.status === 409) return 'El plan cambió mientras se evaluaba. Podés intentarlo nuevamente.'
    if (error.status === 422) return 'No pudimos identificar el plan que querés revisar.'
    if (error.status === 502 && error.message === 'AI service rate limit exceeded') {
      return 'El servicio de IA está recibiendo demasiadas solicitudes. Esperá unos segundos e intentá nuevamente.'
    }
    if (error.status === 502) return 'No pudimos interpretar la evaluación. Podés intentarlo nuevamente.'
    if (error.status === 503) return 'El servicio de IA no está disponible en este momento.'
    if (error.status === 504) return 'La evaluación tardó demasiado. Podés intentar nuevamente.'
    if (error.status === 500) return 'No pudimos revisar el plan en este momento.'
  }

  return 'No pudimos revisar tu plan. Intentá nuevamente.'
}

export function isAdaptationConflict(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409
}

export function getAdaptationConflictError(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = error.message.toLowerCase()
    if (
      detail.includes('obsolete') ||
      detail.includes('changed') ||
      detail.includes('no longer match')
    ) {
      return 'El plan cambió desde que se generó esta propuesta. Volvé a revisarlo para obtener una recomendación actualizada.'
    }
    if (detail.includes('already been reviewed')) {
      return 'Esta propuesta ya fue revisada.'
    }
  }

  return 'Esta propuesta ya no puede aplicarse de forma segura. Volvé a revisar tu plan para obtener una recomendación actualizada.'
}

export function getAdaptationReviewError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Tu sesión venció. Volvé a iniciar sesión.'
    if (error.status === 404) return 'No encontramos la propuesta que querés revisar.'
    if (error.status === 422) return 'La propuesta ya no tiene un formato válido.'
    if (error.status === 500) return 'No pudimos guardar tu decisión. Ningún cambio parcial fue aplicado.'
  }

  return 'No pudimos guardar tu decisión. Intentá nuevamente.'
}
