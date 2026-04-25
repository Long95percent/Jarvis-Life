/** API response types — mirrors Java Result<T> */

export interface ApiResult<T = unknown> {
  success: boolean
  code: number
  message: string
  data: T | null
  timestamp: number
}

export interface PageResult<T> {
  records: T[]
  total: number
  page: number
  size: number
  pages: number
}

export interface PageRequest {
  page?: number
  size?: number
  sortBy?: string
  asc?: boolean
}

/** RAG types */
export interface RAGChunk {
  chunkId: string
  content: string
  source: string
  score: number
  metadata: Record<string, unknown>
}

export interface RAGQueryRequest {
  query: string
  modeId?: string
  topK?: number
  rerank?: boolean
}

export interface RAGQueryResponse {
  chunks: RAGChunk[]
  answer: string
  queryClassification: string
  rewrittenQuery: string
}

export interface IngestRequest {
  filePaths: string[]
  modeId?: string
  chunkingStrategy?: string
}

/** Settings types */
export interface SystemSettings {
  llm: any
  theme: string
  language: string
}

/** LLM Provider types */
export interface LLMProvider {
  id: string
  name: string
  base_url: string
  model: string
  api_key: string
  api_key_masked?: string
  temperature: number
  max_tokens: number
}

export interface ProvidersData {
  providers: LLMProvider[]
  active_id: string | null
}
