'use client'

import { useState, useEffect } from 'react'
import { 
  Search, 
  Filter, 
  FileText, 
  ChevronRight,
  ExternalLink,
  CheckCircle2,
  Clock,
  AlertCircle,
  Loader2
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { getDocuments, getDocument } from '@/lib/api'
import type { LegalDocument, DocumentStatus, DocumentType } from '@/lib/types'
import { format } from 'date-fns'
import { vi } from 'date-fns/locale'

export default function CorpusPage() {
  const [documents, setDocuments] = useState<LegalDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [selectedDocument, setSelectedDocument] = useState<LegalDocument | null>(null)
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)

  useEffect(() => {
    loadDocuments()
  }, [statusFilter, typeFilter, page])

  async function loadDocuments() {
    setLoading(true)
    try {
      const response = await getDocuments(page, 20, {
        status: statusFilter === 'all' ? undefined : statusFilter,
        type: typeFilter === 'all' ? undefined : typeFilter,
        search: searchQuery || undefined,
      })
      
      if (response.success) {
        setDocuments(response.data.items)
        setHasMore(response.data.hasMore)
      }
    } catch (error) {
      console.error('[v0] Error loading documents:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = () => {
    setPage(1)
    loadDocuments()
  }

  const typeLabels: Record<DocumentType, string> = {
    law: 'Luật',
    decree: 'Nghị định',
    circular: 'Thông tư',
    resolution: 'Nghị quyết',
    decision: 'Quyết định',
    guideline: 'Hướng dẫn',
    other: 'Khác',
  }

  const statusConfig: Record<DocumentStatus, { label: string; variant: 'default' | 'secondary' | 'outline' | 'destructive' }> = {
    crawled: { label: 'Đã thu thập', variant: 'secondary' },
    chunked: { label: 'Đã chia chunks', variant: 'outline' },
    indexed: { label: 'Đã index', variant: 'default' },
    failed: { label: 'Lỗi', variant: 'destructive' },
  }

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-semibold">Kho văn bản pháp luật</h1>
        <p className="text-muted-foreground mt-1">
          Duyệt và quản lý các văn bản pháp luật đã thu thập
        </p>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1 flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Tìm kiếm theo tên, số hiệu..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  className="pl-10"
                />
              </div>
              <Button onClick={handleSearch}>
                <Search className="h-4 w-4 mr-2" />
                Tìm
              </Button>
            </div>
            <div className="flex gap-2">
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder="Trạng thái" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tất cả trạng thái</SelectItem>
                  <SelectItem value="indexed">Đã index</SelectItem>
                  <SelectItem value="chunked">Đã chia chunks</SelectItem>
                  <SelectItem value="crawled">Đã thu thập</SelectItem>
                  <SelectItem value="failed">Lỗi</SelectItem>
                </SelectContent>
              </Select>
              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger className="w-[140px]">
                  <SelectValue placeholder="Loại văn bản" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tất cả loại</SelectItem>
                  <SelectItem value="law">Luật</SelectItem>
                  <SelectItem value="decree">Nghị định</SelectItem>
                  <SelectItem value="circular">Thông tư</SelectItem>
                  <SelectItem value="resolution">Nghị quyết</SelectItem>
                  <SelectItem value="decision">Quyết định</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Documents Table */}
      <Card>
        <CardHeader>
          <CardTitle>Danh sách văn bản</CardTitle>
          <CardDescription>
            {loading ? 'Đang tải...' : `${documents.length} văn bản`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : documents.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">Không tìm thấy văn bản nào</p>
            </div>
          ) : (
            <>
              <div className="rounded-lg border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[400px]">Tên văn bản</TableHead>
                      <TableHead>Số hiệu</TableHead>
                      <TableHead>Loại</TableHead>
                      <TableHead>Trạng thái</TableHead>
                      <TableHead>Chunks</TableHead>
                      <TableHead className="text-right">Thao tác</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {documents.map((doc) => (
                      <TableRow key={doc.id}>
                        <TableCell>
                          <div className="max-w-[380px]">
                            <p className="font-medium truncate">{doc.title}</p>
                            <p className="text-xs text-muted-foreground">
                              {doc.issuingAuthority} - {doc.issuedDate}
                            </p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                            {doc.documentNumber}
                          </code>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {typeLabels[doc.documentType]}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant={statusConfig[doc.status].variant}>
                            {statusConfig[doc.status].label}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {doc.chunkCount || 0}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedDocument(doc)}
                          >
                            <ChevronRight className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              
              {/* Pagination */}
              <div className="flex items-center justify-between mt-4">
                <p className="text-sm text-muted-foreground">
                  Trang {page}
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page === 1}
                    onClick={() => setPage(p => p - 1)}
                  >
                    Trước
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!hasMore}
                    onClick={() => setPage(p => p + 1)}
                  >
                    Sau
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Document Detail Dialog */}
      <DocumentDetailDialog
        document={selectedDocument}
        onClose={() => setSelectedDocument(null)}
        typeLabels={typeLabels}
        statusConfig={statusConfig}
      />
    </div>
  )
}

function DocumentDetailDialog({
  document,
  onClose,
  typeLabels,
  statusConfig,
}: {
  document: LegalDocument | null
  onClose: () => void
  typeLabels: Record<DocumentType, string>
  statusConfig: Record<DocumentStatus, { label: string; variant: string }>
}) {
  if (!document) return null

  return (
    <Dialog open={!!document} onOpenChange={() => onClose()}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="pr-8">{document.title}</DialogTitle>
          <DialogDescription>
            {document.documentNumber} - {typeLabels[document.documentType]}
          </DialogDescription>
        </DialogHeader>
        
        <ScrollArea className="flex-1 -mx-6 px-6">
          <div className="space-y-6 py-4">
            {/* Metadata */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">Cơ quan ban hành</p>
                <p className="text-sm">{document.issuingAuthority}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">Ngày ban hành</p>
                <p className="text-sm">{document.issuedDate}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">Ngày có hiệu lực</p>
                <p className="text-sm">{document.effectiveDate || 'N/A'}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">Trạng thái</p>
                <Badge variant={statusConfig[document.status].variant as 'default'}>
                  {statusConfig[document.status].label}
                </Badge>
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">Số chunks</p>
                <p className="text-sm">{document.chunkCount || 0}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">Thu thập lúc</p>
                <p className="text-sm">
                  {format(new Date(document.crawledAt), "dd/MM/yyyy HH:mm", { locale: vi })}
                </p>
              </div>
            </div>

            {/* Preview */}
            {document.previewText && (
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-2">Nội dung trích xuất</p>
                <div className="p-4 rounded-lg bg-muted/50 text-sm leading-relaxed">
                  {document.previewText}
                </div>
              </div>
            )}

            {/* Source Link */}
            {document.sourceUrl && (
              <a
                href={document.sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
              >
                <ExternalLink className="h-4 w-4" />
                Xem văn bản gốc
              </a>
            )}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  )
}
