// Law RAG API Client Layer
// This module provides a typed API client for the backend services.

import type {
  Session,
  Conversation,
  AskQuestionRequest,
  AskQuestionResponse,
  LegalDocument,
  CorpusStatus,
  PipelineJob,
  UploadedDocument,
  ProcessedUploadDocument,
  ProcessedUploadContent,
  DebugQueryRequest,
  DebugQueryResponse,
  UpdateSessionRequest,
  PaginatedResponse,
  ApiResponse,
  RuntimeStatus,
  RuntimeConfigRequest,
  LocalModel,
  EmbeddingTarget,
} from './types'

// ==================== Configuration ====================

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'

function getErrorMessage(payload: unknown, fallback: string): string {
  if (payload && typeof payload === 'object') {
    const data = payload as { error?: unknown; detail?: unknown; message?: unknown }
    if (typeof data.error === 'string') return data.error
    if (typeof data.detail === 'string') return data.detail
    if (typeof data.message === 'string') return data.message
  }
  return fallback
}

function buildUrl(path: string, params?: Record<string, string | number | undefined>): string {
  const baseUrl = API_BASE_URL.replace(/\/$/, '')
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const url = new URL(`${baseUrl}${normalizedPath}`)
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== '') {
        url.searchParams.set(key, String(value))
      }
    })
  }
  return url.toString()
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<ApiResponse<T>> {
  try {
    const response = await fetch(buildUrl(path), {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers || {}),
      },
      cache: 'no-store',
    })

    const payload = await response.json()
    if (!response.ok) {
      return {
        success: false,
        error: getErrorMessage(payload, `Request failed with status ${response.status}`),
      }
    }
    return payload as ApiResponse<T>
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown network error',
    }
  }
}

async function requestFormData<T>(path: string, body: FormData): Promise<ApiResponse<T>> {
  try {
    const response = await fetch(buildUrl(path), {
      method: 'POST',
      body,
      cache: 'no-store',
    })
    const payload = await response.json()
    if (!response.ok) {
      return {
        success: false,
        error: getErrorMessage(payload, `Request failed with status ${response.status}`),
      }
    }
    return payload as ApiResponse<T>
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown network error',
    }
  }
}

function toDate(value: string | Date | undefined | null): Date {
  if (value instanceof Date) return value
  return value ? new Date(value) : new Date()
}

function reviveSession(session: Session): Session {
  return {
    ...session,
    createdAt: toDate(session.createdAt),
    updatedAt: toDate(session.updatedAt),
  }
}

function reviveConversation(conversation: Conversation): Conversation {
  return {
    ...conversation,
    messages: conversation.messages.map((message) => ({
      ...message,
      timestamp: toDate(message.timestamp),
    })),
  }
}

function reviveDocument(document: LegalDocument): LegalDocument {
  return {
    ...document,
    crawledAt: toDate(document.crawledAt),
    lastUpdated: toDate(document.lastUpdated),
  }
}

function reviveJob(job: PipelineJob): PipelineJob {
  return {
    ...job,
    startedAt: job.startedAt ? toDate(job.startedAt) : undefined,
    completedAt: job.completedAt ? toDate(job.completedAt) : undefined,
  }
}

function reviveCorpusStatus(status: CorpusStatus): CorpusStatus {
  return {
    ...status,
    lastCrawlAt: status.lastCrawlAt ? toDate(status.lastCrawlAt) : undefined,
    lastIndexAt: status.lastIndexAt ? toDate(status.lastIndexAt) : undefined,
    bm25IndexStatus: {
      ...status.bm25IndexStatus,
      lastUpdated: status.bm25IndexStatus.lastUpdated ? toDate(status.bm25IndexStatus.lastUpdated) : undefined,
    },
    vectorIndexStatus: {
      ...status.vectorIndexStatus,
      lastUpdated: status.vectorIndexStatus.lastUpdated ? toDate(status.vectorIndexStatus.lastUpdated) : undefined,
    },
  }
}

function reviveUpload(upload: UploadedDocument): UploadedDocument {
  return {
    ...upload,
    uploadedAt: toDate(upload.uploadedAt),
  }
}

// ==================== Chat & Conversation API ====================

export async function getRuntimeStatus(): Promise<ApiResponse<RuntimeStatus>> {
  return requestJson<RuntimeStatus>('/api/runtime/status')
}

export async function updateRuntimeConfig(request: RuntimeConfigRequest): Promise<ApiResponse<RuntimeStatus>> {
  return requestJson<RuntimeStatus>('/api/runtime/config', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function getLocalModels(): Promise<ApiResponse<LocalModel[]>> {
  return requestJson<LocalModel[]>('/api/runtime/local-models')
}

export async function askQuestion(request: AskQuestionRequest): Promise<ApiResponse<AskQuestionResponse>> {
  return requestJson<AskQuestionResponse>('/api/chat/ask', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function askQuestionStream(
  request: AskQuestionRequest,
  onDelta: (delta: string) => void,
): Promise<ApiResponse<AskQuestionResponse>> {
  try {
    const response = await fetch(buildUrl('/api/chat/ask/stream'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      cache: 'no-store',
    })

    if (!response.ok || !response.body) {
      return {
        success: false,
        error: `Request failed with status ${response.status}`,
      }
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let finalData: AskQuestionResponse | null = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.trim()) continue
        const event = JSON.parse(line) as {
          type?: string
          delta?: string
          data?: AskQuestionResponse
          error?: string
        }
        if (event.type === 'answer_delta' && event.delta) {
          onDelta(event.delta)
        } else if (event.type === 'final' && event.data) {
          finalData = event.data
        } else if (event.type === 'error') {
          return { success: false, error: event.error || 'Streaming request failed' }
        }
      }
    }

    if (!finalData) {
      return { success: false, error: 'Backend did not return final answer.' }
    }
    return { success: true, data: finalData }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown network error',
    }
  }
}

export async function getSessions(): Promise<ApiResponse<Session[]>> {
  const response = await requestJson<Session[]>('/api/sessions')
  if (!response.success) return response
  return {
    success: true,
    data: response.data.map(reviveSession),
  }
}

export async function getSession(sessionId: string): Promise<ApiResponse<Session>> {
  const response = await requestJson<Session>(`/api/sessions/${sessionId}`)
  if (!response.success) return response
  return { success: true, data: reviveSession(response.data) }
}

export async function getConversation(sessionId: string): Promise<ApiResponse<Conversation>> {
  const response = await requestJson<Conversation>(`/api/sessions/${sessionId}/conversation`)
  if (!response.success) return response
  return { success: true, data: reviveConversation(response.data) }
}

export async function deleteSession(sessionId: string): Promise<ApiResponse<void>> {
  return requestJson<void>(`/api/sessions/${sessionId}`, {
    method: 'DELETE',
  })
}

export async function archiveSession(sessionId: string): Promise<ApiResponse<Session>> {
  const response = await requestJson<Session>(`/api/sessions/${sessionId}/archive`, {
    method: 'POST',
  })
  if (!response.success) return response
  return { success: true, data: reviveSession(response.data) }
}

export async function updateSession(sessionId: string, request: UpdateSessionRequest): Promise<ApiResponse<Session>> {
  const response = await requestJson<Session>(`/api/sessions/${sessionId}`, {
    method: 'PATCH',
    body: JSON.stringify(request),
  })
  if (!response.success) return response
  return { success: true, data: reviveSession(response.data) }
}

// ==================== Documents API ====================

export async function getDocuments(
  page: number = 1,
  pageSize: number = 20,
  filters?: {
    status?: string
    type?: string
    search?: string
  }
): Promise<ApiResponse<PaginatedResponse<LegalDocument>>> {
  const response = await requestJson<PaginatedResponse<LegalDocument>>(
    buildUrl('/api/documents', {
      page,
      pageSize,
      status: filters?.status,
      type: filters?.type,
      search: filters?.search,
    }).replace(API_BASE_URL, ''),
  )
  if (!response.success) return response
  return {
    success: true,
    data: {
      ...response.data,
      items: response.data.items.map(reviveDocument),
    },
  }
}

export async function getDocument(documentId: string): Promise<ApiResponse<LegalDocument>> {
  const response = await requestJson<LegalDocument>(`/api/documents/${documentId}`)
  if (!response.success) return response
  return { success: true, data: reviveDocument(response.data) }
}

// ==================== Admin / Pipeline API ====================

export async function getCorpusStatus(): Promise<ApiResponse<CorpusStatus>> {
  const response = await requestJson<CorpusStatus>('/api/admin/corpus-status')
  if (!response.success) return response
  return { success: true, data: reviveCorpusStatus(response.data) }
}

export async function getJobs(): Promise<ApiResponse<PipelineJob[]>> {
  const response = await requestJson<PipelineJob[]>('/api/admin/jobs')
  if (!response.success) return response
  return { success: true, data: response.data.map(reviveJob) }
}

export async function triggerCrawl(): Promise<ApiResponse<PipelineJob>> {
  const response = await requestJson<PipelineJob>('/api/admin/jobs/crawl', { method: 'POST' })
  if (!response.success) return response
  return { success: true, data: reviveJob(response.data) }
}

export async function triggerChunking(): Promise<ApiResponse<PipelineJob>> {
  const response = await requestJson<PipelineJob>('/api/admin/jobs/chunk', { method: 'POST' })
  if (!response.success) return response
  return { success: true, data: reviveJob(response.data) }
}

export async function triggerBM25Index(): Promise<ApiResponse<PipelineJob>> {
  const response = await requestJson<PipelineJob>('/api/admin/jobs/index-bm25', { method: 'POST' })
  if (!response.success) return response
  return { success: true, data: reviveJob(response.data) }
}

export async function triggerVectorIndex(): Promise<ApiResponse<PipelineJob>> {
  const response = await requestJson<PipelineJob>('/api/admin/jobs/index-vector', { method: 'POST' })
  if (!response.success) return response
  return { success: true, data: reviveJob(response.data) }
}

// ==================== Debug API ====================

export async function debugQuery(request: DebugQueryRequest): Promise<ApiResponse<DebugQueryResponse>> {
  return requestJson<DebugQueryResponse>('/api/admin/debug/query', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

// ==================== Upload API ====================

export async function uploadDocument(
  file: File,
  options?: {
    language?: string
    documentType?: string
    workspace?: 'public' | 'private'
  },
): Promise<ApiResponse<UploadedDocument>> {
  const formData = new FormData()
  formData.append('file', file)
  const params = new URLSearchParams()
  if (options?.language) params.set('language', options.language)
  if (options?.documentType) params.set('document_type', options.documentType)
  if (options?.workspace) params.set('workspace', options.workspace)
  const query = params.toString()
  const response = await requestFormData<UploadedDocument>(`/api/uploads${query ? `?${query}` : ''}`, formData)
  if (!response.success) return response
  return { success: true, data: reviveUpload(response.data) }
}

export async function getUploadStatus(uploadId: string): Promise<ApiResponse<UploadedDocument>> {
  const response = await requestJson<UploadedDocument>(`/api/uploads/${uploadId}`)
  if (!response.success) return response
  return { success: true, data: reviveUpload(response.data) }
}

export async function saveUploadText(
  uploadId: string,
  extractedText: string,
  options?: {
    embeddingTarget?: EmbeddingTarget
    forceLowConfidence?: boolean
  },
): Promise<ApiResponse<UploadedDocument>> {
  const response = await requestJson<UploadedDocument>(`/api/uploads/${uploadId}`, {
    method: 'PATCH',
    body: JSON.stringify({
      extractedText,
      status: 'ready',
      embeddingTarget: options?.embeddingTarget || 'none',
      forceLowConfidence: options?.forceLowConfidence || false,
    }),
  })
  if (!response.success) return response
  return { success: true, data: reviveUpload(response.data) }
}

export async function deleteUpload(uploadId: string): Promise<ApiResponse<void>> {
  return requestJson<void>(`/api/uploads/${uploadId}`, {
    method: 'DELETE',
  })
}

export async function getProcessedUploads(): Promise<ApiResponse<ProcessedUploadDocument[]>> {
  return requestJson<ProcessedUploadDocument[]>('/api/uploads/processed')
}

export async function getProcessedUploadContent(uploadId: string): Promise<ApiResponse<ProcessedUploadContent>> {
  return requestJson<ProcessedUploadContent>(`/api/uploads/processed/${uploadId}`)
}

export async function deleteProcessedUpload(uploadId: string): Promise<ApiResponse<{ deleted: boolean }>> {
  return requestJson<{ deleted: boolean }>(`/api/uploads/processed/${uploadId}`, {
    method: 'DELETE',
  })
}

export async function embedUpload(uploadId: string, embeddingTarget: Exclude<EmbeddingTarget, 'none'>): Promise<ApiResponse<UploadedDocument>> {
  const response = await requestJson<UploadedDocument>(`/api/uploads/${uploadId}/embed`, {
    method: 'POST',
    body: JSON.stringify({ embeddingTarget, forceLowConfidence: true }),
  })
  if (!response.success) return response
  return { success: true, data: reviveUpload(response.data) }
}

// ==================== SWR Fetchers ====================

export const fetchers = {
  sessions: getSessions,
  corpusStatus: getCorpusStatus,
  jobs: getJobs,
  runtimeStatus: getRuntimeStatus,
}
