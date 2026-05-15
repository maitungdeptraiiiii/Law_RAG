'use client'

import { useState, useRef } from 'react'
import { 
  Upload, 
  FileText, 
  Image as ImageIcon, 
  File,
  X,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Eye,
  Trash2
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { toast } from 'sonner'
import { deleteUpload, getRuntimeStatus, getUploadStatus, saveUploadText, uploadDocument } from '@/lib/api'
import type { EmbeddingTarget, UploadedDocument } from '@/lib/types'
import { OCRReviewPanel } from '@/components/admin/ocr-review-panel'

export default function UploadPage() {
  const [uploads, setUploads] = useState<UploadedDocument[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const [selectedUpload, setSelectedUpload] = useState<UploadedDocument | null>(null)
  const [selectedUploadIds, setSelectedUploadIds] = useState<string[]>([])
  const [batchSaving, setBatchSaving] = useState(false)
  const [batchDeleting, setBatchDeleting] = useState(false)
  const tempUploadSeq = useRef(0)
  const [uploadSettings, setUploadSettings] = useState({
    language: 'vi',
    documentType: 'other',
    workspace: 'private' as 'public' | 'private',
    embeddingTarget: 'none' as EmbeddingTarget,
  })

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    
    const files = Array.from(e.dataTransfer.files)
    await processFiles(files)
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    await processFiles(files)
    e.target.value = '' // Reset input
  }

  async function processFiles(files: File[]) {
    const validFiles = files.filter(file => {
      const ext = file.name.split('.').pop()?.toLowerCase()
      return ['pdf', 'jpg', 'jpeg', 'png', 'docx'].includes(ext || '')
    })

    if (validFiles.length !== files.length) {
      toast.error('Một số file không được hỗ trợ. Chỉ chấp nhận PDF, ảnh và DOCX.')
    }

    for (const file of validFiles) {
      // Create temporary upload entry
      tempUploadSeq.current += 1
      const tempUpload: UploadedDocument = {
        id: `temp-${tempUploadSeq.current}-${file.name}`,
        fileName: file.name,
        fileType: getFileType(file.name),
        fileSize: file.size,
        uploadedAt: new Date(),
        status: 'uploading',
        ocrProgress: 0,
      }
      
      setUploads(prev => [...prev, tempUpload])

      try {
        const response = await uploadDocument(file, uploadSettings)
        if (response.success) {
          setUploads(prev => 
            prev.map(u => 
              u.id === tempUpload.id ? { ...response.data, status: 'processing' } : u
            )
          )
          pollUploadStatus(response.data.id)
        }
      } catch {
        setUploads(prev => 
          prev.map(u => 
            u.id === tempUpload.id ? { ...u, status: 'failed' } : u
          )
        )
        toast.error(`Lỗi tải lên: ${file.name}`)
      }
    }
  }

  const pollUploadStatus = (uploadId: string, attempt = 0) => {
    window.setTimeout(async () => {
      const response = await getUploadStatus(uploadId)
      if (!response.success) {
        setUploads(prev =>
          prev.map(u => u.id === uploadId ? { ...u, status: 'failed', error: response.error } : u)
        )
        return
      }

      const updatedUpload = response.data
      setUploads(prev => prev.map(u => u.id === uploadId ? updatedUpload : u))
      setSelectedUpload(current => current?.id === uploadId ? updatedUpload : current)

      if (updatedUpload.status === 'processing' && attempt < 300) {
        pollUploadStatus(uploadId, attempt + 1)
      } else if (updatedUpload.status === 'ocr_complete') {
        toast.success(`OCR hoàn tất: ${updatedUpload.fileName}`)
      } else if (updatedUpload.status === 'failed') {
        toast.error(updatedUpload.error || `OCR thất bại: ${updatedUpload.fileName}`)
      }
    }, 1000)
  }

  const removeUpload = async (id: string) => {
    if (!id.startsWith('temp-')) {
      const response = await deleteUpload(id)
      if (!response.success) {
        toast.error(response.error)
        return
      }
    }
    setUploads(prev => prev.filter(u => u.id !== id))
    setSelectedUploadIds(prev => prev.filter(uploadId => uploadId !== id))
    setSelectedUpload(current => current?.id === id ? null : current)
  }

  const toggleUploadSelection = (id: string, checked: boolean) => {
    setSelectedUploadIds(prev =>
      checked ? Array.from(new Set([...prev, id])) : prev.filter(uploadId => uploadId !== id)
    )
  }

  const toggleAllUploads = (checked: boolean) => {
    setSelectedUploadIds(checked ? uploads.map(upload => upload.id) : [])
  }

  const selectedUploads = uploads.filter(upload => selectedUploadIds.includes(upload.id))
  const selectedReadyUploads = selectedUploads.filter(upload => upload.status === 'ocr_complete' || upload.status === 'ready')
  const allUploadsSelected = uploads.length > 0 && uploads.every(upload => selectedUploadIds.includes(upload.id))

  const saveSelectedUploads = async () => {
    if (batchSaving) return
    if (selectedReadyUploads.length === 0) {
      toast.error('Chọn ít nhất một tài liệu đã OCR xong để lưu.')
      return
    }
    if (!confirmLowConfidence(selectedReadyUploads)) return
    if (!(await canUseSelectedEmbedding())) return

    setBatchSaving(true)
    try {
      toast.info(`Đang lưu ${selectedReadyUploads.length} tài liệu...`)
      const results = await Promise.all(
        selectedReadyUploads.map(upload =>
          saveUploadText(upload.id, upload.extractedText || '', {
            embeddingTarget: uploadSettings.embeddingTarget,
            forceLowConfidence: true,
          })
        )
      )
      const updatedUploads = results.filter(result => result.success).map(result => result.data)
      const failedResults = results.filter(result => !result.success)

      setUploads(prev =>
        prev.map(upload => updatedUploads.find(updated => updated.id === upload.id) || upload)
      )
      setSelectedUploadIds(prev =>
        prev.filter(id => !updatedUploads.some(upload => upload.id === id))
      )

      if (updatedUploads.length > 0) {
        toast.success(`Đã lưu ${updatedUploads.length} tài liệu.`)
      }
      if (failedResults.length > 0) {
        toast.error(failedResults[0].error || `${failedResults.length} tài liệu chưa lưu được.`)
      }
    } finally {
      setBatchSaving(false)
    }
  }

  const deleteSelectedUploads = async () => {
    if (batchDeleting) return
    if (selectedUploads.length === 0) return

    setBatchDeleting(true)
    try {
      const results = await Promise.all(
        selectedUploads.map(upload =>
          upload.id.startsWith('temp-') ? Promise.resolve({ success: true as const, data: undefined }) : deleteUpload(upload.id)
        )
      )
      const deletedIds = selectedUploads
        .filter((_upload, index) => results[index].success)
        .map(upload => upload.id)
      const failedCount = results.length - deletedIds.length

      setUploads(prev => prev.filter(upload => !deletedIds.includes(upload.id)))
      setSelectedUploadIds(prev => prev.filter(id => !deletedIds.includes(id)))
      setSelectedUpload(current => current && deletedIds.includes(current.id) ? null : current)

      if (deletedIds.length > 0) {
        toast.success(`Đã xóa ${deletedIds.length} tài liệu.`)
      }
      if (failedCount > 0) {
        toast.error(`${failedCount} tài liệu chưa xóa được.`)
      }
    } finally {
      setBatchDeleting(false)
    }
  }

  const confirmLowConfidence = (items: UploadedDocument[]) => {
    const lowConfidenceItems = items.filter(upload => upload.qualityWarning || (upload.confidence ?? 1) < 0.7)
    if (lowConfidenceItems.length === 0) return true
    return window.confirm(
      `${lowConfidenceItems.length} tài liệu có độ tin cậy OCR thấp. Bạn vẫn muốn tiếp tục lưu, chunk và embedding?`
    )
  }

  const canUseSelectedEmbedding = async () => {
    if (uploadSettings.embeddingTarget !== 'api' && uploadSettings.embeddingTarget !== 'both') {
      return true
    }
    const response = await getRuntimeStatus()
    if (!response.success || !response.data.hasOpenaiApiKey) {
      toast.error('Chưa có OpenAI API key. Vào Admin > Tổng quan để cấu hình key hoặc chọn Local/Chưa embedding.')
      return false
    }
    return true
  }

  const getFileType = (fileName: string): 'pdf' | 'image' | 'docx' => {
    const ext = fileName.split('.').pop()?.toLowerCase()
    if (ext === 'pdf') return 'pdf'
    if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext || '')) return 'image'
    return 'docx'
  }

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-semibold">Tải lên tài liệu</h1>
        <p className="text-muted-foreground mt-1">
          Tải lên văn bản PDF, ảnh scan hoặc DOCX để nhận dạng và phân tích nội dung pháp lý
        </p>
      </div>

      <div className="grid lg:grid-cols-[1fr,350px] gap-6">
        {/* Upload Area */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Tải lên file</CardTitle>
              <CardDescription>
                Kéo thả hoặc chọn file để tải lên. Hệ thống sẽ tự động nhận dạng văn bản (OCR).
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* Drop Zone */}
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`
                  relative border-2 border-dashed rounded-xl p-12 text-center transition-colors
                  ${isDragging 
                    ? 'border-primary bg-primary/5' 
                    : 'border-border hover:border-muted-foreground/50'
                  }
                `}
              >
                <input
                  type="file"
                  multiple
                  accept=".pdf,.jpg,.jpeg,.png,.docx"
                  onChange={handleFileSelect}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
                <div className="space-y-4">
                  <div className="mx-auto w-16 h-16 rounded-full bg-muted flex items-center justify-center">
                    <Upload className="h-8 w-8 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="font-medium">Kéo thả file vào đây</p>
                    <p className="text-sm text-muted-foreground mt-1">
                      hoặc nhấn để chọn file từ máy tính
                    </p>
                  </div>
                  <div className="flex items-center justify-center gap-4 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <FileText className="h-4 w-4" />
                      PDF
                    </span>
                    <span className="flex items-center gap-1">
                      <ImageIcon className="h-4 w-4" />
                      JPG, PNG
                    </span>
                    <span className="flex items-center gap-1">
                      <File className="h-4 w-4" />
                      DOCX
                    </span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Upload Queue */}
          {uploads.length > 0 && (
            <Card>
              <CardHeader className="gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <CardTitle>Hàng đợi xử lý</CardTitle>
                  <CardDescription>
                    {uploads.filter(u => u.status === 'ocr_complete' || u.status === 'ready').length} / {uploads.length} hoàn thành
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox
                    checked={allUploadsSelected}
                    onCheckedChange={(checked) => toggleAllUploads(checked === true)}
                    aria-label="Chọn tất cả tài liệu"
                  />
                  <span className="text-sm text-muted-foreground">Chọn tất cả</span>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {selectedUploadIds.length > 0 && (
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/30 px-3 py-2">
                    <span className="text-sm text-muted-foreground">
                      Đã chọn {selectedUploadIds.length} tài liệu
                    </span>
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        onClick={saveSelectedUploads}
                        disabled={selectedReadyUploads.length === 0 || batchSaving}
                      >
                        {batchSaving ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <CheckCircle2 className="mr-2 h-4 w-4" />
                        )}
                        {batchSaving ? 'Đang lưu...' : 'Lưu đã chọn'}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={deleteSelectedUploads}
                        disabled={batchDeleting}
                      >
                        {batchDeleting ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="mr-2 h-4 w-4" />
                        )}
                        {batchDeleting ? 'Đang xóa...' : 'Xóa đã chọn'}
                      </Button>
                    </div>
                  </div>
                )}
                <ScrollArea className="max-h-[400px]">
                  <div className="space-y-3">
                    {uploads.map((upload) => (
                      <UploadItem 
                        key={upload.id} 
                        upload={upload}
                        selected={selectedUploadIds.includes(upload.id)}
                        onSelectedChange={(checked) => toggleUploadSelection(upload.id, checked)}
                        onRemove={() => removeUpload(upload.id)}
                        onReview={() => setSelectedUpload(upload)}
                      />
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Settings Sidebar */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Cài đặt OCR</CardTitle>
              <CardDescription>
                Tùy chỉnh cách hệ thống xử lý tài liệu
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Ngôn ngữ nhận dạng</Label>
                <Select 
                  value={uploadSettings.language}
                  onValueChange={(v) => setUploadSettings(s => ({ ...s, language: v }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="vi">Tiếng Việt</SelectItem>
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="mixed">Đa ngôn ngữ</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Loại văn bản</Label>
                <Select 
                  value={uploadSettings.documentType}
                  onValueChange={(v) => setUploadSettings(s => ({ ...s, documentType: v }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="law">Luật</SelectItem>
                    <SelectItem value="decree">Nghị định</SelectItem>
                    <SelectItem value="circular">Thông tư</SelectItem>
                    <SelectItem value="contract">Hợp đồng</SelectItem>
                    <SelectItem value="case">Hồ sơ vụ án</SelectItem>
                    <SelectItem value="other">Khác</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Không gian lưu trữ</Label>
                <Select 
                  value={uploadSettings.workspace}
                  onValueChange={(v: 'public' | 'private') => setUploadSettings(s => ({ ...s, workspace: v }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="private">Cá nhân (riêng tư)</SelectItem>
                    <SelectItem value="public">Công khai (thêm vào corpus)</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Tài liệu riêng tư chỉ dùng cho câu hỏi của bạn
                </p>
              </div>

              <div className="space-y-2">
                <Label>Embedding sau khi lưu</Label>
                <Select
                  value={uploadSettings.embeddingTarget}
                  onValueChange={(v: EmbeddingTarget) => setUploadSettings(s => ({ ...s, embeddingTarget: v }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Chưa embedding</SelectItem>
                    <SelectItem value="api">API embedding</SelectItem>
                    <SelectItem value="local">Local embedding</SelectItem>
                    <SelectItem value="both">Cả API và local</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Tài liệu riêng tư sẽ lưu index API/local riêng biệt.
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Hướng dẫn</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <p>
                <strong className="text-foreground">1. Tải lên:</strong> Chọn file PDF, 
                ảnh scan hoặc DOCX chứa văn bản pháp lý.
              </p>
              <p>
                <strong className="text-foreground">2. OCR:</strong> Hệ thống tự động 
                nhận dạng và trích xuất nội dung văn bản.
              </p>
              <p>
                <strong className="text-foreground">3. Xem lại:</strong> Kiểm tra và 
                chỉnh sửa nội dung đã nhận dạng nếu cần.
              </p>
              <p>
                <strong className="text-foreground">4. Sử dụng:</strong> Đặt câu hỏi 
                dựa trên tài liệu đã tải lên.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* OCR Review Panel */}
      {selectedUpload && (
        <OCRReviewPanel
          upload={selectedUpload}
          onClose={() => setSelectedUpload(null)}
          onSave={async (text) => {
            if (!confirmLowConfidence([selectedUpload])) return
            if (!(await canUseSelectedEmbedding())) return
            const response = await saveUploadText(selectedUpload.id, text, {
              embeddingTarget: uploadSettings.embeddingTarget,
              forceLowConfidence: true,
            })
            if (!response.success) {
              toast.error(response.error)
              return
            }
            setUploads(prev => prev.map(u => u.id === selectedUpload.id ? response.data : u))
            setSelectedUpload(null)
            toast.success('Đã lưu nội dung')
          }}
        />
      )}
    </div>
  )
}

function UploadItem({ 
  upload, 
  selected,
  onSelectedChange,
  onRemove,
  onReview 
}: { 
  upload: UploadedDocument
  selected: boolean
  onSelectedChange: (checked: boolean) => void
  onRemove: () => void
  onReview: () => void
}) {
  const statusConfig = {
    uploading: { label: 'Đang tải lên', color: 'text-muted-foreground', icon: Loader2 },
    processing: { label: 'Đang xử lý OCR', color: 'text-info', icon: Loader2 },
    ocr_complete: { label: 'Sẵn sàng xem lại', color: 'text-success', icon: CheckCircle2 },
    ready: { label: 'Đã sẵn sàng', color: 'text-success', icon: CheckCircle2 },
    failed: { label: 'Lỗi', color: 'text-destructive', icon: AlertCircle },
  }

  const config = statusConfig[upload.status]
  const StatusIcon = config.icon
  const isProcessing = upload.status === 'uploading' || upload.status === 'processing'
  const canReview = upload.status === 'ocr_complete' || upload.status === 'ready'

  const fileTypeIcons = {
    pdf: FileText,
    image: ImageIcon,
    docx: File,
  }
  const FileIcon = fileTypeIcons[upload.fileType]

  return (
    <div className="flex items-center gap-4 p-3 rounded-lg border border-border bg-card">
      <Checkbox
        checked={selected}
        onCheckedChange={(checked) => onSelectedChange(checked === true)}
        aria-label={`Chọn ${upload.fileName}`}
      />
      <div className="p-2 rounded-lg bg-muted">
        <FileIcon className="h-5 w-5 text-muted-foreground" />
      </div>
      
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{upload.fileName}</p>
        <div className="flex items-center gap-2 mt-1">
          <StatusIcon className={`h-3.5 w-3.5 ${config.color} ${isProcessing ? 'animate-spin' : ''}`} />
          <span className={`text-xs ${config.color}`}>{config.label}</span>
          {upload.confidence && (
            <Badge variant="outline" className="text-xs">
              {(upload.confidence * 100).toFixed(0)}% độ tin cậy
            </Badge>
          )}
        </div>
        {isProcessing && upload.ocrProgress !== undefined && (
          <Progress value={upload.ocrProgress} className="h-1 mt-2" />
        )}
        {upload.qualityWarning && (
          <p className="text-xs text-warning mt-2 line-clamp-2">{upload.qualityWarning}</p>
        )}
        {upload.status === 'failed' && upload.error && (
          <p className="text-xs text-destructive mt-2 line-clamp-2">{upload.error}</p>
        )}
      </div>

      <div className="flex items-center gap-1">
        {canReview && (
          <Button variant="ghost" size="sm" onClick={onReview}>
            <Eye className="h-4 w-4" />
          </Button>
        )}
        <Button variant="ghost" size="sm" onClick={onRemove}>
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

