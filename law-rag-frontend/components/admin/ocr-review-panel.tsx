'use client'

import { useState } from 'react'
import {
  Save, 
  FileText, 
  MessageSquare,
  AlertTriangle,
  CheckCircle2
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { UploadedDocument } from '@/lib/types'

interface OCRReviewPanelProps {
  upload: UploadedDocument
  onClose: () => void
  onSave: (text: string) => void
}

export function OCRReviewPanel({ upload, onClose, onSave }: OCRReviewPanelProps) {
  const [editedText, setEditedText] = useState(upload.extractedText || '')
  const [hasChanges, setHasChanges] = useState(false)

  const handleTextChange = (text: string) => {
    setEditedText(text)
    setHasChanges(text !== upload.extractedText)
  }

  const handleSave = () => {
    onSave(editedText)
  }

  const confidence = upload.confidence || 0
  const confidenceLevel = confidence >= 0.9 ? 'high' : confidence >= 0.7 ? 'medium' : 'low'

  return (
    <Dialog open onOpenChange={() => onClose()}>
      <DialogContent className="flex max-h-[92vh] w-[calc(100vw-2rem)] max-w-6xl flex-col overflow-hidden p-0 sm:max-w-6xl">
        <DialogHeader className="shrink-0 border-b px-6 py-5 pr-12">
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Xem lại kết quả OCR
          </DialogTitle>
          <DialogDescription>
            Kiểm tra và chỉnh sửa nội dung được nhận dạng từ {upload.fileName}
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <div className="grid min-h-0 gap-5 lg:grid-cols-[minmax(0,1fr)_280px]">
          {/* Text Editor */}
          <div className="flex min-w-0 flex-col">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">Nội dung đã nhận dạng</span>
              {hasChanges && (
                <Badge variant="outline" className="text-xs">
                  Có thay đổi
                </Badge>
              )}
            </div>
            <Textarea
              value={editedText}
              onChange={(e) => handleTextChange(e.target.value)}
              className="h-[58vh] min-h-[360px] resize-none overflow-auto whitespace-pre-wrap font-mono text-sm leading-6"
              placeholder="Nội dung văn bản sẽ hiển thị ở đây sau khi OCR hoàn tất..."
            />
          </div>

          {/* Side Panel */}
          <div className="min-w-0 space-y-4">
            {/* Confidence */}
            <div className="p-4 rounded-lg border border-border bg-muted/30">
              <h4 className="text-sm font-medium mb-3">Độ tin cậy OCR</h4>
              <div className="flex items-center gap-3">
                <div className={`
                  w-12 h-12 rounded-full flex items-center justify-center
                  ${confidenceLevel === 'high' ? 'bg-success/10 text-success' :
                    confidenceLevel === 'medium' ? 'bg-warning/10 text-warning' :
                    'bg-destructive/10 text-destructive'}
                `}>
                  {confidenceLevel === 'high' ? (
                    <CheckCircle2 className="h-6 w-6" />
                  ) : (
                    <AlertTriangle className="h-6 w-6" />
                  )}
                </div>
                <div>
                  <p className="text-2xl font-semibold">
                    {(confidence * 100).toFixed(0)}%
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {confidenceLevel === 'high' ? 'Chất lượng cao' :
                     confidenceLevel === 'medium' ? 'Cần kiểm tra' :
                     'Nên xem lại kỹ'}
                  </p>
                </div>
              </div>
            </div>

            {upload.qualityWarning && (
              <div className="p-4 rounded-lg border border-warning/40 bg-warning/10">
                <h4 className="text-sm font-medium mb-2">Cháº¥t lÆ°á»£ng tháº¥p</h4>
                <p className="text-xs text-muted-foreground">{upload.qualityWarning}</p>
              </div>
            )}

            {/* Tips */}
            <div className="p-4 rounded-lg border border-border bg-muted/30">
              <h4 className="text-sm font-medium mb-3">Gợi ý chỉnh sửa</h4>
              <ul className="space-y-2 text-xs text-muted-foreground">
                <li className="flex items-start gap-2">
                  <span className="text-primary">•</span>
                  Kiểm tra các số điều, khoản, điểm có chính xác không
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-primary">•</span>
                  Xem lại các từ viết tắt và thuật ngữ pháp lý
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-primary">•</span>
                  Đảm bảo số hiệu văn bản được nhận dạng đúng
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-primary">•</span>
                  Kiểm tra ngày tháng và các con số quan trọng
                </li>
              </ul>
            </div>

            {/* Actions Preview */}
            <div className="p-4 rounded-lg border border-border bg-muted/30">
              <h4 className="text-sm font-medium mb-3">Sau khi lưu</h4>
              <p className="text-xs text-muted-foreground mb-3">
                Bạn có thể sử dụng tài liệu này để:
              </p>
              <div className="space-y-2">
                <Button variant="outline" size="sm" className="w-full justify-start">
                  <MessageSquare className="h-4 w-4 mr-2" />
                  Hỏi đáp với tài liệu
                </Button>
              </div>
            </div>
          </div>
          </div>
        </div>

        <DialogFooter className="shrink-0 border-t px-6 py-4">
          <Button variant="outline" onClick={onClose}>
            Hủy
          </Button>
          <Button onClick={handleSave}>
            <Save className="h-4 w-4 mr-2" />
            Lưu và sử dụng
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
