import { supabase } from './supabase'

const apiUrl = (
  import.meta.env.VITE_API_URL as string | undefined
)?.replace(/\/$/, '')

if (!apiUrl) {
  throw new Error('VITE_API_URL is not configured')
}

export class ApiError extends Error {
  status: number

  constructor(
    status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const {
    data: { session },
  } = await supabase.auth.getSession()

  if (!session?.access_token) {
    throw new ApiError(
      401,
      'Authentication is required',
    )
  }

  const headers = new Headers(init.headers)
  headers.set(
    'Authorization',
    `Bearer ${session.access_token}`,
  )
  headers.set('Accept', 'application/json')

  if (
    init.body !== undefined &&
    !headers.has('Content-Type')
  ) {
    headers.set(
      'Content-Type',
      'application/json',
    )
  }

  const response = await fetch(
    `${apiUrl}${path}`,
    {
      ...init,
      headers,
    },
  )

  if (response.status === 401) {
    await supabase.auth.signOut()
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`

    try {
      const payload = (
        await response.json()
      ) as {
        detail?: string
      }

      if (payload.detail) {
        message = payload.detail
      }
    } catch {
      // Preserve the fallback message.
    }

    throw new ApiError(
      response.status,
      message,
    )
  }

  return response.json() as Promise<T>
}
