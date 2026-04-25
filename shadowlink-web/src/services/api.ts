/**
 * HTTP client — thin wrapper over fetch with typed responses.
 * All requests go through the Vite dev proxy (/api → Java backend).
 */

import type { ApiResult } from '@/types'

const BASE_URL = '/api'

class ApiError extends Error {
  constructor(
    public status: number,
    public code: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = `${BASE_URL}${path}`
  const res = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new ApiError(res.status, res.status, text)
  }

  const body: ApiResult<T> = await res.json()
  if (!body.success) {
    throw new ApiError(200, body.code, body.message)
  }

  return body.data as T
}

export const api = {
  get<T>(path: string): Promise<T> {
    return request<T>(path)
  },

  post<T>(path: string, data?: unknown): Promise<T> {
    return request<T>(path, {
      method: 'POST',
      body: data != null ? JSON.stringify(data) : undefined,
    })
  },

  put<T>(path: string, data?: unknown): Promise<T> {
    return request<T>(path, {
      method: 'PUT',
      body: data != null ? JSON.stringify(data) : undefined,
    })
  },

  delete<T>(path: string): Promise<T> {
    return request<T>(path, { method: 'DELETE' })
  },
}

export { ApiError }
