// Law RAG Types - Vietnamese Legal AI Assistant

// ==================== Chat & Conversation ====================

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  sources?: RetrievedSource[]
  metadata?: MessageMetadata
}

export interface MessageMetadata {
  retrievalMode?: RetrievalMode
  modelUsed?: string
  queryRewritten?: string
  processingTimeMs?: number
}

export interface Session {
  id: string
  title: string
  createdAt: Date
  updatedAt: Date
  messageCount: number
  preview?: string
  archived?: boolean
  pinned?: boolean
}

export interface Conversation {
  sessionId: string
  messages: Message[]
}

// ==================== Retrieval & Sources ====================

export type RetrievalMode = 'hybrid' | 'vector' | 'bm25'
export type VectorBackend = 'faiss' | 'atlas'

export interface RetrievedSource {
  id: string
  documentId: string
  documentTitle: string
  articleNumber?: string
  clauseNumber?: string
  targetArticle?: string
  chunkText: string
  relevanceScore: number
  retrievalOrigin: 'bm25' | 'vector' | 'hybrid'
  sourceUrl?: string
  issuedDate?: string
  documentType?: DocumentType
}

export interface RetrievalSettings {
  mode: RetrievalMode
  vectorBackend: VectorBackend
  topK: number
  queryRewrite: boolean
  model?: string
}

// ==================== Legal Documents ====================

export type DocumentType = 
  | 'law' 
  | 'decree' 
  | 'circular' 
  | 'resolution' 
  | 'decision' 
  | 'guideline'
  | 'other'

export type DocumentStatus = 'crawled' | 'chunked' | 'indexed' | 'failed'

export interface LegalDocument {
  id: string
  title: string
  documentNumber: string
  documentType: DocumentType
  issuedDate: string
  effectiveDate?: string
  issuingAuthority: string
  sourceUrl: string
  status: DocumentStatus
  chunkCount?: number
  crawledAt: Date
  lastUpdated: Date
  previewText?: string
}

export interface DocumentChunk {
  id: string
  documentId: string
  chunkIndex: number
  content: string
  articleNumber?: string
  clauseNumber?: string
  tokens?: number
}

// ==================== Pipeline & Admin ====================

export type JobType = 'crawl' | 'chunk' | 'index_bm25' | 'index_vector'
export type JobStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface PipelineJob {
  id: string
  type: JobType
  status: JobStatus
  progress: number
  startedAt?: Date
  completedAt?: Date
  error?: string
  metadata?: Record<string, unknown>
}

export interface CorpusStatus {
  totalDocuments: number
  crawledDocuments: number
  chunkedDocuments: number
  totalChunks: number
  bm25IndexStatus: IndexStatus
  vectorIndexStatus: IndexStatus
  lastCrawlAt?: Date
  lastIndexAt?: Date
}

export interface IndexStatus {
  built: boolean
  documentCount: number
  lastUpdated?: Date
  sizeBytes?: number
}

// ==================== OCR & Upload ====================

export type UploadStatus = 'uploading' | 'processing' | 'ocr_complete' | 'ready' | 'failed'

export interface UploadedDocument {
  id: string
  fileName: string
  fileType: 'pdf' | 'image' | 'docx'
  fileSize: number
  uploadedAt: Date
  status: UploadStatus
  ocrProgress?: number
  extractedText?: string
  confidence?: number
  tags?: string[]
  workspace?: 'public' | 'private'
}

export interface OCRResult {
  documentId: string
  pages: OCRPage[]
  overallConfidence: number
  language: 'vi' | 'en' | 'mixed'
}

export interface OCRPage {
  pageNumber: number
  text: string
  confidence: number
  regions?: OCRRegion[]
}

export interface OCRRegion {
  id: string
  text: string
  confidence: number
  boundingBox: {
    x: number
    y: number
    width: number
    height: number
  }
}

// ==================== API Contracts ====================

export interface AskQuestionRequest {
  question: string
  sessionId?: string
  settings?: Partial<RetrievalSettings>
}

export interface AskQuestionResponse {
  answer: string
  sessionId: string
  messageId: string
  sources: RetrievedSource[]
  metadata: MessageMetadata
}

export interface UpdateSessionRequest {
  title?: string
  pinned?: boolean
}

export interface DebugQueryRequest {
  query: string
  settings?: Partial<RetrievalSettings>
}

export interface DebugQueryResponse {
  originalQuery: string
  rewrittenQuery?: string
  bm25Results: RetrievedSource[]
  vectorResults: RetrievedSource[]
  fusedResults: RetrievedSource[]
  timings: {
    queryRewrite?: number
    bm25Search: number
    vectorSearch: number
    fusion: number
    total: number
  }
}

// ==================== UI State ====================

export interface AppState {
  currentSession?: Session
  sessions: Session[]
  retrievalSettings: RetrievalSettings
  isLoading: boolean
}

export interface AdminState {
  corpusStatus: CorpusStatus
  activeJobs: PipelineJob[]
  recentJobs: PipelineJob[]
}

// ==================== Utility Types ====================

export type ApiResponse<T> = {
  success: true
  data: T
} | {
  success: false
  error: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  hasMore: boolean
}
