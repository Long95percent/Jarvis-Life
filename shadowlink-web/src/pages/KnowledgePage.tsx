/**
 * KnowledgePage — RAG knowledge base management.
 *
 * Features:
 * - File upload with drag-and-drop
 * - Document list with ingest status
 * - Index management per work mode
 * - Supported formats display
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Book,
  Database,
  FileText,
  HardDrive,
  Loader2,
  Trash2,
  Upload,
} from 'lucide-react'

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

interface IndexInfo {
  name: string
  total_vectors: number
  dimension: number
  mode_id: string
  last_updated: string
}

interface IngestResult {
  file_path: string
  file_name: string
  size: number
  indexed: boolean
  chunks?: number
  mode_id?: string
  latency_ms?: number
  message?: string
}

export function KnowledgePage() {
  const [indices, setIndices] = useState<IndexInfo[]>([])
  const [formats, setFormats] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Upload state
  const [uploading, setUploading] = useState(false)
  const [uploadResults, setUploadResults] = useState<IngestResult[]>([])
  const [dragOver, setDragOver] = useState(false)
  const [modeId, setModeId] = useState('general')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [idxData, fmtData] = await Promise.all([
        fetchJSON<IndexInfo[]>(`${AI_API}/rag/indices`),
        fetchJSON<string[]>(`${AI_API}/file/formats`),
      ])
      setIndices(idxData || [])
      setFormats(fmtData || [])
    } catch (e) {
      setError('Unable to connect to AI service. Make sure Python is running on port 8000.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleUpload = async (files: FileList | File[]) => {
    setUploading(true)
    setUploadResults([])
    const results: IngestResult[] = []

    for (const file of Array.from(files)) {
      try {
        const formData = new FormData()
        formData.append('file', file)

        const res = await fetch(
          `${AI_API}/file/upload-and-ingest?mode_id=${encodeURIComponent(modeId)}`,
          { method: 'POST', body: formData },
        )
        const body = await res.json()
        if (body.success && body.data) {
          results.push(body.data)
        } else {
          results.push({
            file_path: '',
            file_name: file.name,
            size: file.size,
            indexed: false,
            message: body.message || 'Upload failed',
          })
        }
      } catch (e) {
        results.push({
          file_path: '',
          file_name: file.name,
          size: file.size,
          indexed: false,
          message: (e as Error).message,
        })
      }
    }

    setUploadResults(results)
    setUploading(false)
    loadData() // Refresh indices
  }

  const handleDeleteIndex = async (modeId: string) => {
    try {
      await fetch(`${AI_API}/rag/indices/${modeId}`, { method: 'DELETE' })
      loadData()
    } catch {
      // ignore
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files.length > 0) {
      handleUpload(e.dataTransfer.files)
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(true)
  }

  const totalVectors = indices.reduce((sum, idx) => sum + (idx.total_vectors || 0), 0)

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-6 overflow-y-auto h-full">
      <div>
        <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
          <Book size={20} /> Knowledge Base
        </h1>
        <p className="text-sm text-muted mt-1">
          Upload documents to build your AI's knowledge. Files are parsed, chunked, embedded, and indexed for retrieval.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* ── Stats Bar ── */}
      <div className="grid grid-cols-3 gap-3">
        <div className="surface-card p-4 text-center">
          <Database size={18} className="mx-auto text-primary-400 mb-1" />
          <p className="text-lg font-semibold text-foreground">{indices.length}</p>
          <p className="text-xs text-muted">Index Partitions</p>
        </div>
        <div className="surface-card p-4 text-center">
          <HardDrive size={18} className="mx-auto text-primary-400 mb-1" />
          <p className="text-lg font-semibold text-foreground">{totalVectors.toLocaleString()}</p>
          <p className="text-xs text-muted">Total Vectors</p>
        </div>
        <div className="surface-card p-4 text-center">
          <FileText size={18} className="mx-auto text-primary-400 mb-1" />
          <p className="text-lg font-semibold text-foreground">{formats.length}</p>
          <p className="text-xs text-muted">Supported Formats</p>
        </div>
      </div>

      {/* ── Upload Section ── */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-foreground">Upload Documents</h2>
          <select
            value={modeId}
            onChange={(e) => setModeId(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-surface-secondary text-xs text-foreground outline-none"
          >
            <option value="general">General</option>
            <option value="code-dev">Code Dev</option>
            <option value="paper-reading">Paper Reading</option>
            <option value="creative-writing">Creative Writing</option>
            <option value="data-analysis">Data Analysis</option>
            <option value="project-management">Project Mgmt</option>
          </select>
        </div>

        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={() => setDragOver(false)}
          onClick={() => fileInputRef.current?.click()}
          className={`surface-card border-2 border-dashed p-8 text-center cursor-pointer transition-all ${
            dragOver
              ? 'border-primary-500/50 bg-primary-500/5'
              : 'border-white/10 hover:border-white/20'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            accept={formats.map((f) => f).join(',')}
            onChange={(e) => e.target.files && handleUpload(e.target.files)}
          />
          {uploading ? (
            <div className="flex flex-col items-center gap-2">
              <Loader2 size={28} className="animate-spin text-primary-400" />
              <p className="text-sm text-muted">Processing files...</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <Upload size={28} className="text-muted" />
              <p className="text-sm text-muted">
                Drag & drop files here, or click to browse
              </p>
              <p className="text-xs text-muted/60">
                {formats.length > 0
                  ? `Supported: ${formats.join(', ')}`
                  : 'PDF, DOCX, XLSX, MD, TXT, PY, JS, TS, Java...'}
              </p>
            </div>
          )}
        </div>

        {/* Upload results */}
        {uploadResults.length > 0 && (
          <div className="space-y-2">
            {uploadResults.map((r, i) => (
              <div
                key={i}
                className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs ${
                  r.indexed
                    ? 'bg-green-500/10 border border-green-500/20 text-green-400'
                    : 'bg-red-500/10 border border-red-500/20 text-red-400'
                }`}
              >
                <span className="truncate">{r.file_name}</span>
                <span>
                  {r.indexed
                    ? `${r.chunks} chunks, ${r.latency_ms?.toFixed(0)}ms`
                    : r.message || 'Failed'}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── Index Management ── */}
      <section className="space-y-3">
        <h2 className="text-sm font-medium text-foreground">Index Partitions</h2>
        {loading ? (
          <div className="flex items-center justify-center py-8 text-muted">
            <Loader2 size={18} className="animate-spin mr-2" /> Loading...
          </div>
        ) : indices.length === 0 ? (
          <div className="surface-card p-6 text-center">
            <Database size={24} className="mx-auto text-muted mb-2" />
            <p className="text-sm text-muted">No indices yet</p>
            <p className="text-xs text-muted/60 mt-1">Upload documents to create your first index</p>
          </div>
        ) : (
          <div className="space-y-2">
            {indices.map((idx) => (
              <div key={idx.name} className="surface-card flex items-center justify-between px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-primary-500/10 flex items-center justify-center">
                    <Database size={14} className="text-primary-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">{idx.mode_id || idx.name}</p>
                    <p className="text-xs text-muted">
                      {idx.total_vectors.toLocaleString()} vectors &middot; {idx.dimension}d
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => handleDeleteIndex(idx.mode_id || idx.name)}
                  className="p-1.5 rounded-md text-muted hover:text-red-400 hover:bg-red-500/10 transition-colors"
                  title="Delete index"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── Supported Formats ── */}
      {formats.length > 0 && (
        <section className="surface-card p-4">
          <h3 className="text-xs font-medium text-muted mb-2">Supported Formats</h3>
          <div className="flex flex-wrap gap-1.5">
            {formats.map((fmt) => (
              <span key={fmt} className="px-2 py-0.5 rounded-full text-[10px] bg-surface-secondary text-muted">
                {fmt}
              </span>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
