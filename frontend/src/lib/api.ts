import { env } from './env'
import { supabase } from './supabase'

interface ApiRequestOptions extends Omit<RequestInit, 'body'> {
  authenticated?: boolean
  body?: object | null
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const { authenticated = true, body, headers: initialHeaders, ...requestInit } = options
  const headers = new Headers(initialHeaders)

  if (authenticated) {
    const { data, error } = await supabase.auth.getSession()
    const accessToken = data.session?.access_token

    if (error || !accessToken) {
      throw new ApiError('Tu sesión no está disponible. Volvé a iniciar sesión.', 401)
    }

    headers.set('Authorization', `Bearer ${accessToken}`)
  }

  let requestBody: BodyInit | null | undefined
  if (body !== undefined && body !== null) {
    headers.set('Content-Type', 'application/json')
    requestBody = JSON.stringify(body)
  }

  const response = await fetch(`${env.apiBaseUrl}/${path.replace(/^\//, '')}`, {
    ...requestInit,
    body: requestBody,
    headers,
  })

  if (!response.ok) {
    throw new ApiError(await getErrorMessage(response), response.status)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

async function getErrorMessage(response: Response): Promise<string> {
  const fallback = `La solicitud falló (${response.status}).`

  try {
    const payload = (await response.json()) as { detail?: unknown }
    return typeof payload.detail === 'string' ? payload.detail : fallback
  } catch {
    return fallback
  }
}
