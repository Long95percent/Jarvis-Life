const AI_API = '/v1'

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  const body = await res.json()
  if (!body.success) throw new Error(body.message || 'Request failed')
  return body.data as T
}

export interface RagIndexInfo {
  name: string
  total_vectors: number
  dimension: number
  mode_id: string
  last_updated: string
}

export interface RagIngestResult {
  file_path: string
  file_name: string
  size: number
  indexed: boolean
  chunks?: number
  mode_id?: string
  latency_ms?: number
  message?: string
}

export const ragApi = {
  listIndices(): Promise<RagIndexInfo[]> {
    return fetchJSON<RagIndexInfo[]>(`${AI_API}/rag/indices`)
  },

  listSupportedFormats(): Promise<string[]> {
    return fetchJSON<string[]>(`${AI_API}/file/formats`)
  },

  async uploadAndIngest(file: File, modeId: string): Promise<RagIngestResult> {
    const formData = new FormData()
    formData.append('file', file)

    const res = await fetch(
      `${AI_API}/file/upload-and-ingest?mode_id=${encodeURIComponent(modeId)}`,
      { method: 'POST', body: formData },
    )
    const body = await res.json()
    if (body.success && body.data) return body.data as RagIngestResult

    return {
      file_path: '',
      file_name: file.name,
      size: file.size,
      indexed: false,
      message: body.message || 'Upload failed',
    }
  },

  async deleteIndex(modeId: string): Promise<void> {
    await fetch(`${AI_API}/rag/indices/${encodeURIComponent(modeId)}`, { method: 'DELETE' })
  },
}
