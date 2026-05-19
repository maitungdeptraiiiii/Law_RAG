'use client'

import { motion } from 'framer-motion'
import { X, ExternalLink, FileText, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useState } from 'react'
import { formatSourceCitation, sourceDocumentLabel } from '@/lib/legal-citation'
import type { RetrievedSource } from '@/lib/types'

interface SourceEvidencePanelProps {
  sources: RetrievedSource[]
  onClose: () => void
}

export function SourceEvidencePanel({ sources, onClose }: SourceEvidencePanelProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const typeLabels: Record<string, string> = {
    law: 'Luật',
    decree: 'Nghị định',
    circular: 'Thông tư',
    resolution: 'Nghị quyết',
    decision: 'Quyết định',
    guideline: 'Hướng dẫn',
    other: 'Khác',
  }

  const originColors: Record<string, string> = {
    hybrid: 'bg-primary/10 text-primary',
    vector: 'bg-info/10 text-info',
    bm25: 'bg-accent/10 text-accent-foreground',
  }

  return (
    <motion.aside
      initial={{ x: '100%', opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: '100%', opacity: 0 }}
      transition={{ type: 'spring', damping: 25, stiffness: 200 }}
      className="w-96 border-l border-border bg-card flex flex-col min-h-0 overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center justify-between h-14 px-4 border-b border-border flex-shrink-0">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-accent" />
          <h3 className="font-semibold text-sm">Nguồn tham khảo</h3>
          <span className="text-xs text-muted-foreground">({sources.length})</span>
        </div>
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
          <X className="h-4 w-4" />
          <span className="sr-only">Đóng</span>
        </Button>
      </div>

      {/* Sources List */}
      <ScrollArea className="flex-1 min-h-0">
        <div className="p-4 space-y-3">
          {sources.map((source, index) => {
            const citation = formatSourceCitation(source)
            const documentLabel = sourceDocumentLabel(source)

            return (
            <div
              key={source.id}
              className="border border-border rounded-lg overflow-hidden bg-background"
            >
              {/* Source Header */}
              <button
                onClick={() => setExpandedId(expandedId === source.id ? null : source.id)}
                className="w-full p-4 text-left hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-7 h-7 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-semibold">
                    {index + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className="font-medium text-sm leading-tight mb-1 line-clamp-2">
                      {documentLabel}
                    </h4>
                    <div className="flex flex-wrap items-center gap-2">
                      {source.documentType && (
                        <span className="px-1.5 py-0.5 rounded text-xs bg-secondary text-secondary-foreground">
                          {typeLabels[source.documentType] || source.documentType}
                        </span>
                      )}
                      <span className={`px-1.5 py-0.5 rounded text-xs ${originColors[source.retrievalOrigin]}`}>
                        {source.retrievalOrigin}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {(source.relevanceScore * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{citation}</p>
                  </div>
                  <div className="flex-shrink-0">
                    {expandedId === source.id ? (
                      <ChevronUp className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                </div>
              </button>

              {/* Expanded Content */}
              {expandedId === source.id && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="border-t border-border"
                >
                  <div className="p-4 space-y-3">
                    {/* Chunk Text */}
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-2">Nội dung trích xuất:</p>
                      <div className="p-3 rounded-md bg-muted/50 text-sm leading-relaxed whitespace-pre-wrap">
                        {source.chunkText}
                      </div>
                    </div>

                    {/* Metadata */}
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="col-span-2">
                        <span className="text-muted-foreground">Căn cứ trích dẫn:</span>
                        <p className="font-medium leading-relaxed">{citation}</p>
                      </div>
                      {source.issuedDate && (
                        <div>
                          <span className="text-muted-foreground">Ngày ban hành:</span>
                          <p className="font-medium">{source.issuedDate}</p>
                        </div>
                      )}
                      <div>
                        <span className="text-muted-foreground">Độ liên quan:</span>
                        <p className="font-medium">{(source.relevanceScore * 100).toFixed(1)}%</p>
                      </div>
                    </div>

                    {/* Source Link */}
                    {source.sourceUrl && (
                      <a
                        href={source.sourceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
                      >
                        <ExternalLink className="h-3 w-3" />
                        Xem văn bản gốc
                      </a>
                    )}
                  </div>
                </motion.div>
              )}
            </div>
            )
          })}
        </div>
      </ScrollArea>

      {/* Footer */}
      <div className="p-4 border-t border-border bg-muted/30 flex-shrink-0">
        <p className="text-xs text-muted-foreground text-center leading-relaxed">
          Các nguồn được xếp hạng theo độ liên quan với câu hỏi của bạn. 
          Nhấn vào từng nguồn để xem chi tiết nội dung trích xuất.
        </p>
      </div>
    </motion.aside>
  )
}
