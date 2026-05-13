'use client'

import { useState } from 'react'
import { 
  Play, 
  Loader2,
  Clock,
  Sparkles,
  Zap
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { debugQuery } from '@/lib/api'
import { formatSourceCitation } from '@/lib/legal-citation'
import type { DebugQueryResponse, RetrievalMode, RetrievedSource } from '@/lib/types'

export default function DebugPage() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<DebugQueryResponse | null>(null)
  const [settings, setSettings] = useState({
    mode: 'hybrid' as RetrievalMode,
    queryRewrite: true,
    topK: 5,
  })

  const handleDebug = async () => {
    if (!query.trim() || loading) return
    
    setLoading(true)
    try {
      const response = await debugQuery({
        query: query.trim(),
        settings,
      })
      
      if (response.success) {
        setResult(response.data)
      }
    } catch (error) {
      console.error('[v0] Error debugging query:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-semibold">Debug truy xuất</h1>
        <p className="text-muted-foreground mt-1">
          Kiểm tra và phân tích quá trình truy xuất văn bản pháp luật
        </p>
      </div>

      <div className="grid lg:grid-cols-[1fr,400px] gap-6">
        {/* Query Input */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Câu truy vấn</CardTitle>
              <CardDescription>
                Nhập câu hỏi để xem chi tiết quá trình truy xuất
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ví dụ: Quy định về thuế thu nhập cá nhân khi bán nhà..."
                className="min-h-[120px] resize-none"
              />
              <Button onClick={handleDebug} disabled={!query.trim() || loading}>
                {loading ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Play className="h-4 w-4 mr-2" />
                )}
                Chạy debug
              </Button>
            </CardContent>
          </Card>

          {/* Results */}
          {result && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Kết quả truy xuất</CardTitle>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Clock className="h-4 w-4" />
                    {result.timings.total}ms
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {/* Query Rewrite */}
                {result.rewrittenQuery && (
                  <div className="mb-6 p-4 rounded-lg bg-muted/50 border border-border">
                    <div className="flex items-center gap-2 text-sm font-medium mb-2">
                      <Sparkles className="h-4 w-4 text-accent" />
                      Câu hỏi được viết lại
                      <span className="text-xs text-muted-foreground">
                        ({result.timings.queryRewrite}ms)
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground">{result.rewrittenQuery}</p>
                  </div>
                )}

                {/* Results Tabs */}
                <Tabs defaultValue="fused">
                  <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="fused">
                      Kết quả ({result.fusedResults.length})
                    </TabsTrigger>
                    <TabsTrigger value="bm25">
                      BM25 ({result.bm25Results.length})
                    </TabsTrigger>
                    <TabsTrigger value="vector">
                      Vector ({result.vectorResults.length})
                    </TabsTrigger>
                  </TabsList>
                  
                  <TabsContent value="fused" className="mt-4">
                    <DebugResultsList 
                      results={result.fusedResults} 
                      timing={result.timings.fusion}
                      label="Fusion"
                    />
                  </TabsContent>
                  
                  <TabsContent value="bm25" className="mt-4">
                    <DebugResultsList 
                      results={result.bm25Results} 
                      timing={result.timings.bm25Search}
                      label="BM25"
                    />
                  </TabsContent>
                  
                  <TabsContent value="vector" className="mt-4">
                    <DebugResultsList 
                      results={result.vectorResults} 
                      timing={result.timings.vectorSearch}
                      label="Vector"
                    />
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Settings Sidebar */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Cài đặt debug</CardTitle>
              <CardDescription>
                Tùy chỉnh tham số truy xuất
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Retrieval Mode */}
              <div className="space-y-2">
                <Label>Chế độ truy xuất</Label>
                <Select 
                  value={settings.mode} 
                  onValueChange={(v: RetrievalMode) => setSettings(s => ({ ...s, mode: v }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="hybrid">Hybrid</SelectItem>
                    <SelectItem value="vector">Vector only</SelectItem>
                    <SelectItem value="bm25">BM25 only</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Top K */}
              <div className="space-y-2">
                <Label>Top-K kết quả</Label>
                <Select 
                  value={settings.topK.toString()} 
                  onValueChange={(v) => setSettings(s => ({ ...s, topK: parseInt(v) }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[3, 5, 7, 10].map(k => (
                      <SelectItem key={k} value={k.toString()}>{k}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Query Rewrite */}
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Viết lại câu hỏi</Label>
                  <p className="text-xs text-muted-foreground">
                    AI tối ưu câu hỏi
                  </p>
                </div>
                <Switch
                  checked={settings.queryRewrite}
                  onCheckedChange={(v) => setSettings(s => ({ ...s, queryRewrite: v }))}
                />
              </div>
            </CardContent>
          </Card>

          {/* Timing Breakdown */}
          {result && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Zap className="h-4 w-4" />
                  Phân tích thời gian
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {result.timings.queryRewrite !== undefined && (
                    <TimingRow 
                      label="Query rewrite" 
                      time={result.timings.queryRewrite} 
                      total={result.timings.total}
                    />
                  )}
                  <TimingRow 
                    label="BM25 search" 
                    time={result.timings.bm25Search} 
                    total={result.timings.total}
                  />
                  <TimingRow 
                    label="Vector search" 
                    time={result.timings.vectorSearch} 
                    total={result.timings.total}
                  />
                  <TimingRow 
                    label="Result fusion" 
                    time={result.timings.fusion} 
                    total={result.timings.total}
                  />
                  <div className="pt-2 border-t">
                    <div className="flex justify-between text-sm font-medium">
                      <span>Tổng cộng</span>
                      <span>{result.timings.total}ms</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}

function DebugResultsList({ 
  results, 
  timing, 
  label 
}: { 
  results: RetrievedSource[]
  timing: number
  label: string
}) {
  const [expandedIds, setExpandedIds] = useState<string[]>([])

  if (results.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        Không có kết quả
      </div>
    )
  }

  const toggleExpanded = (sourceId: string) => {
    setExpandedIds((current) =>
      current.includes(sourceId)
        ? current.filter((id) => id !== sourceId)
        : [...current, sourceId],
    )
  }

  return (
    <ScrollArea className="h-[400px]">
      <div className="space-y-3 pr-4">
        <div className="flex items-center justify-between text-sm text-muted-foreground mb-2">
          <span>{label}: {results.length} kết quả</span>
          <span>{timing}ms</span>
        </div>
        {results.map((source, index) => (
          <div key={source.id} className="p-4 rounded-lg border border-border bg-card">
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-semibold">
                {index + 1}
              </div>
              <div className="flex-1 min-w-0 space-y-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-sm truncate">
                    {source.documentTitle}
                  </span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    source.retrievalOrigin === 'hybrid' 
                      ? 'bg-primary/10 text-primary'
                      : source.retrievalOrigin === 'vector'
                      ? 'bg-info/10 text-info'
                      : 'bg-accent/10 text-accent-foreground'
                  }`}>
                    {source.retrievalOrigin}
                  </span>
                </div>
                
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {formatSourceCitation(source)}
                </p>
                
                <button
                  type="button"
                  onClick={() => toggleExpanded(source.id)}
                  className="w-full text-left"
                >
                  <div
                    className={`p-2 rounded bg-muted/50 text-xs leading-relaxed whitespace-pre-wrap ${
                      expandedIds.includes(source.id) ? '' : 'line-clamp-3'
                    }`}
                  >
                    {source.chunkText}
                  </div>
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    {expandedIds.includes(source.id) ? 'Nhấn để thu gọn' : 'Nhấn để xem đầy đủ'}
                  </p>
                </button>
                
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  <span>Score: {(source.relevanceScore * 100).toFixed(1)}%</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </ScrollArea>
  )
}

function TimingRow({ label, time, total }: { label: string; time: number; total: number }) {
  const percentage = (time / total) * 100
  
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span>{time}ms</span>
      </div>
      <div className="h-1.5 bg-muted rounded-full overflow-hidden">
        <div 
          className="h-full bg-primary rounded-full transition-all"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  )
}
