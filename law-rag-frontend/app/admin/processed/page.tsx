'use client'

import { useEffect, useState } from 'react'
import { Archive, CheckCircle2, Eye, RefreshCw, Trash2, XCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  deleteProcessedUpload,
  embedUpload,
  getProcessedUploadContent,
  getProcessedUploads,
  getRuntimeStatus,
} from '@/lib/api'
import type {
  EmbeddingTarget,
  ProcessedUploadContent,
  ProcessedUploadDocument,
  UploadEmbeddingResult,
} from '@/lib/types'
import { toast } from 'sonner'

export default function ProcessedUploadsPage() {
  const [documents, setDocuments] = useState<ProcessedUploadDocument[]>([])
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [embeddingId, setEmbeddingId] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [contentLoadingId, setContentLoadingId] = useState<string | null>(null)
  const [contentPreview, setContentPreview] = useState<ProcessedUploadContent | null>(null)

  async function loadDocuments(showLoading = true) {
    if (showLoading) setLoading(true)
    const response = await getProcessedUploads()
    if (response.success) {
      setDocuments(response.data)
      setSelectedIds(prev => prev.filter(id => response.data.some(document => document.id === id)))
    } else {
      toast.error(response.error)
    }
    setLoading(false)
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadDocuments(false)
    }, 0)
    return () => window.clearTimeout(timer)
  }, [])

  async function handleEmbed(document: ProcessedUploadDocument, target: Exclude<EmbeddingTarget, 'none'>) {
    if (target === 'api' || target === 'both') {
      const runtime = await getRuntimeStatus()
      if (!runtime.success || !runtime.data.hasOpenaiApiKey) {
        toast.error('Chưa có OpenAI API key. Hãy cấu hình key trước khi dùng API embedding.')
        return
      }
    }
    setEmbeddingId(`${document.id}:${target}`)
    const response = await embedUpload(document.id, target)
    if (response.success) {
      toast.success('Đã cập nhật embedding.')
      await loadDocuments(false)
    } else {
      toast.error(response.error)
    }
    setEmbeddingId(null)
  }

  async function handleViewContent(document: ProcessedUploadDocument) {
    setContentLoadingId(document.id)
    const response = await getProcessedUploadContent(document.id)
    if (response.success) {
      setContentPreview(response.data)
    } else {
      toast.error(response.error)
    }
    setContentLoadingId(null)
  }

  function toggleSelected(id: string, checked: boolean) {
    setSelectedIds(prev => checked ? Array.from(new Set([...prev, id])) : prev.filter(item => item !== id))
  }

  function toggleAll(checked: boolean) {
    setSelectedIds(checked ? documents.map(document => document.id) : [])
  }

  async function deleteSelected(ids = selectedIds) {
    if (ids.length === 0 || deleting) return
    const confirmed = window.confirm(`Xóa ${ids.length} tài liệu đã xử lý? Thao tác này sẽ xóa cả chunks và embeddings đã tạo.`)
    if (!confirmed) return

    setDeleting(true)
    const results = await Promise.all(ids.map(id => deleteProcessedUpload(id)))
    const deletedIds = ids.filter((_id, index) => results[index].success)
    const failedCount = ids.length - deletedIds.length

    setDocuments(prev => prev.filter(document => !deletedIds.includes(document.id)))
    setSelectedIds(prev => prev.filter(id => !deletedIds.includes(id)))
    if (contentPreview && deletedIds.includes(contentPreview.id)) {
      setContentPreview(null)
    }
    if (deletedIds.length > 0) {
      toast.success(`Đã xóa ${deletedIds.length} tài liệu.`)
    }
    if (failedCount > 0) {
      toast.error(`${failedCount} tài liệu chưa xóa được.`)
    }
    setDeleting(false)
  }

  const allSelected = documents.length > 0 && documents.every(document => selectedIds.includes(document.id))

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Tài liệu đã xử lý</h1>
          <p className="mt-1 text-muted-foreground">
            Theo dõi các tài liệu OCR đã lưu, số chunk và trạng thái embedding API/local.
          </p>
        </div>
        <Button variant="outline" onClick={() => loadDocuments()} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Làm mới
        </Button>
      </div>

      <Card>
        <CardHeader className="gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle>Kho tài liệu sau OCR</CardTitle>
            <CardDescription>{documents.length} tài liệu đã được lưu</CardDescription>
          </div>
          {documents.length > 0 && (
            <div className="flex items-center gap-2">
              <Checkbox
                checked={allSelected}
                onCheckedChange={(checked) => toggleAll(checked === true)}
                aria-label="Chọn tất cả tài liệu đã xử lý"
              />
              <span className="text-sm text-muted-foreground">Chọn tất cả</span>
            </div>
          )}
        </CardHeader>
        <CardContent className="space-y-3">
          {selectedIds.length > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/30 px-3 py-2">
              <span className="text-sm text-muted-foreground">Đã chọn {selectedIds.length} tài liệu</span>
              <Button variant="outline" size="sm" onClick={() => deleteSelected()} disabled={deleting}>
                <Trash2 className="mr-2 h-4 w-4" />
                {deleting ? 'Đang xóa...' : 'Xóa đã chọn'}
              </Button>
            </div>
          )}
          {documents.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-center">
              <Archive className="mb-3 h-8 w-8 text-muted-foreground" />
              <p className="font-medium">Chưa có tài liệu đã xử lý</p>
              <p className="text-sm text-muted-foreground">Lưu tài liệu sau OCR để thấy trạng thái tại đây.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {documents.map((document) => (
                <ProcessedDocumentRow
                  key={document.id}
                  document={document}
                  selected={selectedIds.includes(document.id)}
                  deleting={deleting}
                  embeddingId={embeddingId}
                  contentLoadingId={contentLoadingId}
                  onSelect={toggleSelected}
                  onEmbed={handleEmbed}
                  onDelete={() => deleteSelected([document.id])}
                  onView={handleViewContent}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={contentPreview !== null} onOpenChange={(open) => !open && setContentPreview(null)}>
        <DialogContent className="max-h-[90vh] sm:max-w-4xl">
          <DialogHeader>
            <DialogTitle className="pr-8">{contentPreview?.fileName || 'Nội dung tài liệu'}</DialogTitle>
            <DialogDescription>
              {contentPreview
                ? `${contentPreview.workspace === 'public' ? 'Corpus chung' : 'Cá nhân'} · ${contentPreview.chunkCount || 0} chunks${typeof contentPreview.confidence === 'number' ? ` · ${(contentPreview.confidence * 100).toFixed(0)}% OCR` : ''}`
                : 'Nội dung đã lưu sau OCR'}
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-[68vh] overflow-auto rounded-md border bg-muted/20 p-4">
            <pre className="whitespace-pre-wrap break-words font-mono text-sm leading-6">
              {contentPreview?.text?.trim() || 'Tài liệu này chưa có nội dung text đã lưu.'}
            </pre>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function ProcessedDocumentRow({
  document,
  selected,
  deleting,
  embeddingId,
  contentLoadingId,
  onSelect,
  onEmbed,
  onDelete,
  onView,
}: {
  document: ProcessedUploadDocument
  selected: boolean
  deleting: boolean
  embeddingId: string | null
  contentLoadingId: string | null
  onSelect: (id: string, checked: boolean) => void
  onEmbed: (document: ProcessedUploadDocument, target: Exclude<EmbeddingTarget, 'none'>) => void
  onDelete: () => void
  onView: (document: ProcessedUploadDocument) => void
}) {
  const apiBuilt = Boolean(document.embeddingStatus?.api?.built)
  const localBuilt = Boolean(document.embeddingStatus?.local?.built)
  const busy = embeddingId !== null

  return (
    <div className="rounded-lg border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <Checkbox
            checked={selected}
            onCheckedChange={(checked) => onSelect(document.id, checked === true)}
            aria-label={`Chọn ${document.fileName}`}
          />
          <div className="min-w-0">
            <p className="truncate font-medium">{document.fileName}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge variant={document.workspace === 'public' ? 'default' : 'secondary'}>
                {document.workspace === 'public' ? 'Corpus chung' : 'Cá nhân'}
              </Badge>
              <Badge variant="outline">{document.chunkCount || 0} chunks</Badge>
              {typeof document.confidence === 'number' && (
                <Badge variant="outline">{(document.confidence * 100).toFixed(0)}% OCR</Badge>
              )}
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <EmbeddingBadge label="API" result={document.embeddingStatus?.api} />
          <EmbeddingBadge label="Local" result={document.embeddingStatus?.local} />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onView(document)}
          disabled={contentLoadingId === document.id}
        >
          <Eye className="mr-2 h-4 w-4" />
          {contentLoadingId === document.id ? 'Đang tải...' : 'Xem nội dung'}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onEmbed(document, 'api')}
          disabled={busy || apiBuilt}
        >
          {apiBuilt ? 'API đã embed' : embeddingId === `${document.id}:api` ? 'Đang embed API...' : 'Embed API'}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onEmbed(document, 'local')}
          disabled={busy || localBuilt}
        >
          {localBuilt ? 'Local đã embed' : embeddingId === `${document.id}:local` ? 'Đang embed local...' : 'Embed local'}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onEmbed(document, 'both')}
          disabled={busy || (apiBuilt && localBuilt)}
        >
          {apiBuilt && localBuilt ? 'Đã embed cả hai' : embeddingId === `${document.id}:both` ? 'Đang embed...' : 'Embed cả hai'}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onDelete}
          disabled={deleting}
        >
          <Trash2 className="mr-2 h-4 w-4" />
          Xóa
        </Button>
      </div>

      {document.qualityWarning && (
        <p className="mt-3 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-muted-foreground">
          {document.qualityWarning}
        </p>
      )}
    </div>
  )
}

function EmbeddingBadge({ label, result }: { label: string; result?: UploadEmbeddingResult | null }) {
  if (!result) {
    return (
      <Badge variant="outline" className="gap-1">
        <XCircle className="h-3.5 w-3.5" />
        {label}: chưa chạy
      </Badge>
    )
  }

  if (result.built) {
    return (
      <Badge variant="outline" className="gap-1 border-success/40 text-success">
        <CheckCircle2 className="h-3.5 w-3.5" />
        {label}: {result.model || result.embedding_model}
      </Badge>
    )
  }

  return (
    <Badge variant="outline" className="gap-1 border-destructive/40 text-destructive">
      <XCircle className="h-3.5 w-3.5" />
      {label}: lỗi
    </Badge>
  )
}
