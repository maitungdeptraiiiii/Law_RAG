'use client'

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Slider } from '@/components/ui/slider'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { RetrievalSettings, RetrievalMode, VectorBackend } from '@/lib/types'

interface RetrievalSettingsDrawerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  settings: RetrievalSettings
  onSettingsChange: (settings: RetrievalSettings) => void
}

export function RetrievalSettingsDrawer({
  open,
  onOpenChange,
  settings,
  onSettingsChange,
}: RetrievalSettingsDrawerProps) {
  const handleModeChange = (mode: RetrievalMode) => {
    onSettingsChange({ ...settings, mode })
  }

  const handleBackendChange = (vectorBackend: VectorBackend) => {
    onSettingsChange({ ...settings, vectorBackend })
  }

  const handleTopKChange = (value: number[]) => {
    onSettingsChange({ ...settings, topK: value[0] })
  }

  const handleQueryRewriteChange = (queryRewrite: boolean) => {
    onSettingsChange({ ...settings, queryRewrite })
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[400px] sm:w-[450px]">
        <SheetHeader>
          <SheetTitle>Cài đặt truy xuất nâng cao</SheetTitle>
          <SheetDescription>
            Điều chỉnh cách hệ thống tìm kiếm văn bản pháp luật. Các cài đặt mặc định 
            phù hợp cho hầu hết trường hợp.
          </SheetDescription>
        </SheetHeader>

        <div className="mt-8 space-y-8">
          {/* Retrieval Mode */}
          <div className="space-y-3">
            <Label htmlFor="retrieval-mode">Chế độ tìm kiếm</Label>
            <Select value={settings.mode} onValueChange={handleModeChange}>
              <SelectTrigger id="retrieval-mode">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="hybrid">
                  <div className="flex flex-col">
                    <span>Hybrid (Khuyến nghị)</span>
                    <span className="text-xs text-muted-foreground">Kết hợp BM25 và vector</span>
                  </div>
                </SelectItem>
                <SelectItem value="vector">
                  <div className="flex flex-col">
                    <span>Vector</span>
                    <span className="text-xs text-muted-foreground">Tìm kiếm theo ngữ nghĩa</span>
                  </div>
                </SelectItem>
                <SelectItem value="bm25">
                  <div className="flex flex-col">
                    <span>BM25</span>
                    <span className="text-xs text-muted-foreground">Tìm kiếm từ khóa truyền thống</span>
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Hybrid kết hợp cả hai phương pháp để có kết quả tốt nhất.
            </p>
          </div>

          {/* Vector Backend */}
          <div className="space-y-3">
            <Label htmlFor="vector-backend">Vector backend</Label>
            <Select value={settings.vectorBackend} onValueChange={handleBackendChange}>
              <SelectTrigger id="vector-backend">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="faiss">FAISS (Local)</SelectItem>
                <SelectItem value="atlas">MongoDB Atlas</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              FAISS nhanh hơn cho tập dữ liệu nhỏ, Atlas phù hợp cho production.
            </p>
          </div>

          {/* Top K */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>Số nguồn truy xuất (Top-K)</Label>
              <span className="text-sm font-medium">{settings.topK}</span>
            </div>
            <Slider
              value={[settings.topK]}
              onValueChange={handleTopKChange}
              min={1}
              max={10}
              step={1}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              Số lượng văn bản pháp luật được truy xuất để tổng hợp câu trả lời.
            </p>
          </div>

          {/* Query Rewrite */}
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <Label htmlFor="query-rewrite">Viết lại câu hỏi</Label>
              <p className="text-xs text-muted-foreground">
                AI sẽ tối ưu câu hỏi trước khi tìm kiếm
              </p>
            </div>
            <Switch
              id="query-rewrite"
              checked={settings.queryRewrite}
              onCheckedChange={handleQueryRewriteChange}
            />
          </div>

          {/* Info Box */}
          <div className="p-4 rounded-lg bg-muted/50 border border-border">
            <h4 className="text-sm font-medium mb-2">Gợi ý cài đặt</h4>
            <ul className="text-xs text-muted-foreground space-y-1.5">
              <li>• <strong>Câu hỏi cụ thể:</strong> BM25 hoặc Hybrid, Top-K = 3-5</li>
              <li>• <strong>Câu hỏi khái niệm:</strong> Vector hoặc Hybrid, Top-K = 5-7</li>
              <li>• <strong>Nghiên cứu sâu:</strong> Hybrid, Top-K = 8-10</li>
            </ul>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
