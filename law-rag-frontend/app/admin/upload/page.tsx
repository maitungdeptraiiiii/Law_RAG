'use client'

import { useState, useCallback } from 'react'
import { 
  Upload, 
  FileText, 
  Image as ImageIcon, 
  File,
  X,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Eye
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { toast } from 'sonner'
import { uploadDocument } from '@/lib/api'
import type { UploadedDocument, UploadStatus } from '@/lib/types'
import { OCRReviewPanel } from '@/components/admin/ocr-review-panel'

export default function UploadPage() {
  const [uploads, setUploads] = useState<UploadedDocument[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const [selectedUpload, setSelectedUpload] = useState<UploadedDocument | null>(null)
  const [uploadSettings, setUploadSettings] = useState({
    language: 'vi',
    documentType: 'other',
    workspace: 'private' as 'public' | 'private',
  })

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    
    const files = Array.from(e.dataTransfer.files)
    await processFiles(files)
  }, [])

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    await processFiles(files)
    e.target.value = '' // Reset input
  }

  const processFiles = async (files: File[]) => {
    const validFiles = files.filter(file => {
      const ext = file.name.split('.').pop()?.toLowerCase()
      return ['pdf', 'jpg', 'jpeg', 'png', 'docx', 'doc'].includes(ext || '')
    })

    if (validFiles.length !== files.length) {
      toast.error('Một số file không được hỗ trợ. Chỉ chấp nhận PDF, ảnh và DOCX.')
    }

    for (const file of validFiles) {
      // Create temporary upload entry
      const tempUpload: UploadedDocument = {
        id: `temp-${Date.now()}-${Math.random()}`,
        fileName: file.name,
        fileType: getFileType(file.name),
        fileSize: file.size,
        uploadedAt: new Date(),
        status: 'uploading',
        ocrProgress: 0,
      }
      
      setUploads(prev => [...prev, tempUpload])

      try {
        const response = await uploadDocument(file)
        if (response.success) {
          // Simulate OCR processing
          simulateOCRProgress(response.data.id)
          
          setUploads(prev => 
            prev.map(u => 
              u.id === tempUpload.id ? { ...response.data, status: 'processing' } : u
            )
          )
        }
      } catch (error) {
        setUploads(prev => 
          prev.map(u => 
            u.id === tempUpload.id ? { ...u, status: 'failed' } : u
          )
        )
        toast.error(`Lỗi tải lên: ${file.name}`)
      }
    }
  }

  const simulateOCRProgress = (uploadId: string) => {
    let progress = 0
    const interval = setInterval(() => {
      progress += Math.random() * 20
      if (progress >= 100) {
        progress = 100
        clearInterval(interval)
        
        setUploads(prev => 
          prev.map(u => 
            u.id === uploadId 
              ? { 
                  ...u, 
                  status: 'ocr_complete' as UploadStatus, 
                  ocrProgress: 100,
                  extractedText: mockExtractedText,
                  confidence: 0.92,
                } 
              : u
          )
        )
      } else {
        setUploads(prev => 
          prev.map(u => 
            u.id === uploadId ? { ...u, ocrProgress: progress } : u
          )
        )
      }
    }, 500)
  }

  const removeUpload = (id: string) => {
    setUploads(prev => prev.filter(u => u.id !== id))
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
                  accept=".pdf,.jpg,.jpeg,.png,.docx,.doc"
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
              <CardHeader>
                <CardTitle>Hàng đợi xử lý</CardTitle>
                <CardDescription>
                  {uploads.filter(u => u.status === 'ocr_complete').length} / {uploads.length} hoàn thành
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="max-h-[400px]">
                  <div className="space-y-3">
                    {uploads.map((upload) => (
                      <UploadItem 
                        key={upload.id} 
                        upload={upload}
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
          onSave={(text) => {
            setUploads(prev =>
              prev.map(u =>
                u.id === selectedUpload.id ? { ...u, extractedText: text, status: 'ready' } : u
              )
            )
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
  onRemove,
  onReview 
}: { 
  upload: UploadedDocument
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

const mockExtractedText = `QUỐC HỘI
________

Luật số: 91/2015/QH13

CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc
________________________

BỘ LUẬT DÂN SỰ

Căn cứ Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam;

Quốc hội ban hành Bộ luật Dân sự.

PHẦN THỨ NHẤT
QUY ĐỊNH CHUNG

Chương I
NHỮNG QUY ĐỊNH CHUNG

Điều 1. Phạm vi điều chỉnh

Bộ luật này quy định địa vị pháp lý, chuẩn mực pháp lý về cách ứng xử của cá nhân, pháp nhân; quyền, nghĩa vụ về nhân thân và tài sản của cá nhân, pháp nhân trong các quan hệ được hình thành trên cơ sở bình đẳng, tự do ý chí, độc lập về tài sản và tự chịu trách nhiệm (sau đây gọi chung là quan hệ dân sự).

Điều 2. Công nhận, tôn trọng, bảo vệ và bảo đảm quyền dân sự

1. Ở nước Cộng hòa xã hội chủ nghĩa Việt Nam, các quyền dân sự được công nhận, tôn trọng, bảo vệ và bảo đảm theo Hiến pháp và pháp luật.

2. Quyền dân sự chỉ có thể bị hạn chế theo quy định của luật trong trường hợp cần thiết vì lý do quốc phòng, an ninh quốc gia, trật tự, an toàn xã hội, đạo đức xã hội, sức khỏe của cộng đồng.`
