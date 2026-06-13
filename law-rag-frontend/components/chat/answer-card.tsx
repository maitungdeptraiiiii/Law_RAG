'use client'

import { useState } from 'react'
import { 
  Scale, 
  FileText, 
  AlertTriangle, 
  Copy, 
  Check, 
  ChevronDown,
  ExternalLink,
  Clock,
  Cpu
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { formatSourceCitation, sourceDocumentLabel, sourceShortReference } from '@/lib/legal-citation'
import { toast } from 'sonner'
import type { Message, RetrievedSource } from '@/lib/types'

interface AnswerCardProps {
  message: Message
  onViewSources?: (sources: RetrievedSource[]) => void
}

export function AnswerCard({ message, onViewSources }: AnswerCardProps) {
  const [copied, setCopied] = useState(false)
  const [sourcesExpanded, setSourcesExpanded] = useState(false)
  const [debugExpanded, setDebugExpanded] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    toast.success('Đã sao chép câu trả lời')
    setTimeout(() => setCopied(false), 2000)
  }

  const sources = message.sources || []
  const metadata = message.metadata
  const hasDebugMetadata = Boolean(
    metadata?.timings ||
    metadata?.retrievalQueryCount ||
    metadata?.retrievalInputChars ||
    metadata?.contextChars
  )

  return (
    <div className="space-y-4">
      {/* Main Answer */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        {/* Answer Content */}
        <div className="p-5">
          <div className="prose prose-sm max-w-none dark:prose-invert">
            <FormattedAnswer content={message.content} />
          </div>
        </div>

        {/* Sources Summary */}
        {sources.length > 0 && (
          <div className="border-t border-border">
            <Collapsible open={sourcesExpanded} onOpenChange={setSourcesExpanded}>
              <CollapsibleTrigger asChild>
                <button className="flex items-center justify-between w-full px-5 py-3 hover:bg-muted/50 transition-colors">
                  <div className="flex items-center gap-2 text-sm">
                    <FileText className="h-4 w-4 text-accent" />
                    <span className="font-medium">{sources.length} nguồn tham khảo</span>
                  </div>
                  <ChevronDown 
                    className={`h-4 w-4 text-muted-foreground transition-transform ${
                      sourcesExpanded ? 'rotate-180' : ''
                    }`}
                  />
                </button>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <div className="px-5 pb-4 space-y-2">
                  {sources.slice(0, 3).map((source, index) => (
                    <SourceBadge key={source.id} source={source} index={index} />
                  ))}
                  {sources.length > 3 && onViewSources && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onViewSources(sources)}
                      className="w-full mt-2"
                    >
                      Xem tất cả {sources.length} nguồn
                      <ExternalLink className="ml-2 h-3 w-3" />
                    </Button>
                  )}
                </div>
              </CollapsibleContent>
            </Collapsible>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-border bg-muted/30">
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            {metadata?.retrievalMode && (
              <span className="flex items-center gap-1">
                <Scale className="h-3 w-3" />
                {metadata.retrievalMode}
              </span>
            )}
            {metadata?.processingTimeMs && (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {(metadata.processingTimeMs / 1000).toFixed(1)}s
              </span>
            )}
            {metadata?.runtimeMode && (
              <span className="flex items-center gap-1">
                <Cpu className="h-3 w-3" />
                {metadata.runtimeMode}
              </span>
            )}
            {metadata?.modelUsed && (
              <span className="hidden items-center gap-1 sm:flex">
                {metadata.modelUsed}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {onViewSources && sources.length > 0 && (
              <Button 
                variant="ghost" 
                size="sm"
                onClick={() => onViewSources(sources)}
                className="h-7 text-xs"
              >
                <FileText className="h-3 w-3 mr-1" />
                Xem nguồn
              </Button>
            )}
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={handleCopy}
              className="h-7 text-xs"
            >
              {copied ? (
                <Check className="h-3 w-3 mr-1" />
              ) : (
                <Copy className="h-3 w-3 mr-1" />
              )}
              {copied ? 'Đã sao chép' : 'Sao chép'}
            </Button>
          </div>
        </div>

        {hasDebugMetadata && (
          <div className="border-t border-border bg-muted/20">
            <Collapsible open={debugExpanded} onOpenChange={setDebugExpanded}>
              <CollapsibleTrigger asChild>
                <button className="flex w-full items-center justify-between px-5 py-2 text-xs text-muted-foreground hover:bg-muted/40">
                  <span className="flex items-center gap-2">
                    <Cpu className="h-3 w-3" />
                    Debug timing
                  </span>
                  <ChevronDown
                    className={`h-3 w-3 transition-transform ${debugExpanded ? 'rotate-180' : ''}`}
                  />
                </button>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <DebugTiming metadata={metadata} />
              </CollapsibleContent>
            </Collapsible>
          </div>
        )}
      </div>
    </div>
  )
}

function formatMs(value?: number): string {
  if (typeof value !== 'number') return '-'
  if (value >= 1000) return `${(value / 1000).toFixed(1)}s`
  return `${value}ms`
}

function DebugTiming({ metadata }: { metadata: Message['metadata'] }) {
  const timings = metadata?.timings || {}
  const bm25Queries = timings.bm25Queries || []
  const vectorQueries = timings.vectorQueries || []
  const rows = [
    ['memory', timings.memoryUpdate],
    ['rewrite', timings.queryRewrite],
    ['retrieval', timings.retrieval],
    ['  pinned', timings.retrievalPinned],
    ['  bm25', timings.retrievalBm25],
    ['  vector', timings.retrievalVector],
    ['  fusion', timings.retrievalFusionRerank],
    ['  model rerank', timings.modelRerankMs],
    ['context', timings.contextBuild],
    ['final LLM', timings.finalLlm],
    ['total', timings.processingTotal || metadata?.processingTimeMs],
  ] as const

  return (
    <div className="grid gap-2 px-5 pb-3 text-xs text-muted-foreground sm:grid-cols-2">
      <div className="grid grid-cols-2 gap-x-3 gap-y-1">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <span>{label}</span>
            <span className="font-mono text-foreground">{formatMs(value)}</span>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1">
        <span>queries</span>
        <span className="font-mono text-foreground">
          {timings.retrievalActiveQueries ?? metadata?.retrievalQueryCount ?? '-'}
        </span>
        <span>bm25 sources</span>
        <span className="font-mono text-foreground">{timings.retrievalBm25Sources ?? '-'}</span>
        <span>extra vectors</span>
        <span className="font-mono text-foreground">{timings.retrievalExtraVectorDirs ?? '-'}</span>
        <span>vector cache</span>
        <span className="font-mono text-foreground">
          h:{timings.vectorAssetCacheHit ?? 0} m:{timings.vectorAssetCacheMiss ?? 0}
        </span>
        <span>reranker</span>
        <span className="font-mono text-foreground">
          {timings.modelRerankProvider
            ? `${timings.modelRerankProvider} ${timings.modelRerankDevice ?? '-'} ${timings.modelRerankCandidates ?? '-'}`
            : '-'}
        </span>
        <span>slowest bm25</span>
        <span className="font-mono text-foreground">
          {formatMs(Math.max(0, ...bm25Queries.map((item) => item.ms || 0)))}
        </span>
        <span>slowest vector</span>
        <span className="font-mono text-foreground">
          {formatMs(Math.max(0, ...vectorQueries.map((item) => item.ms || 0)))}
        </span>
        <span>retrieval chars</span>
        <span className="font-mono text-foreground">{metadata?.retrievalInputChars ?? '-'}</span>
        <span>context chars</span>
        <span className="font-mono text-foreground">{metadata?.contextChars ?? '-'}</span>
      </div>
      {metadata?.citationWarnings && metadata.citationWarnings.length > 0 && (
        <div className="rounded border border-warning/40 bg-warning/10 px-2 py-1 text-warning sm:col-span-2">
          {metadata.citationWarnings.map((warning) => (
            <div key={warning}>{warning}</div>
          ))}
        </div>
      )}
      {timings.modelRerankError && (
        <div className="rounded border border-warning/40 bg-warning/10 px-2 py-1 text-warning sm:col-span-2">
          model rerank fallback: {timings.modelRerankError}
        </div>
      )}
      {(bm25Queries.length > 0 || vectorQueries.length > 0) && (
        <div className="sm:col-span-2">
          {bm25Queries.length > 0 && (
            <DebugQueryList title="BM25 queries" items={bm25Queries} />
          )}
          {vectorQueries.length > 0 && (
            <DebugQueryList title="Vector queries" items={vectorQueries} showVectorParts />
          )}
        </div>
      )}
    </div>
  )
}

function DebugQueryList({
  title,
  items,
  showVectorParts = false,
}: {
  title: string
  items: Array<{
    ms?: number
    loadMs?: number
    embedMs?: number
    searchMs?: number
    metadataMs?: number
    chars?: number
    results?: number
    query?: string
  }>
  showVectorParts?: boolean
}) {
  return (
    <div className="mt-2 space-y-1">
      <div className="font-medium text-foreground">{title}</div>
      {items.map((item, index) => (
        <div key={`${title}-${index}`} className="rounded border border-border/70 bg-background/60 px-2 py-1">
          <div className="flex flex-wrap gap-x-3 gap-y-1 font-mono text-[11px] text-foreground">
            <span>#{index + 1}</span>
            <span>{formatMs(item.ms)}</span>
            <span>chars:{item.chars ?? '-'}</span>
            <span>results:{item.results ?? '-'}</span>
            {showVectorParts && (
              <>
                <span>load:{formatMs(item.loadMs)}</span>
                <span>embed:{formatMs(item.embedMs)}</span>
                <span>search:{formatMs(item.searchMs)}</span>
              </>
            )}
          </div>
          {item.query && (
            <div className="mt-1 truncate text-[11px] text-muted-foreground">{item.query}</div>
          )}
        </div>
      ))}
    </div>
  )
}

function FormattedAnswer({ content }: { content: string }) {
  // Split content into sections based on markdown-like headers
  const sections = content.split(/(?=##\s)/g)
  
  return (
    <div className="space-y-4">
      {sections.map((section, index) => {
        // Check if this is a header section
        const headerMatch = section.match(/^##\s+(.+)\n/)
        
        if (headerMatch) {
          const title = headerMatch[1]
          const body = section.replace(/^##\s+.+\n/, '').trim()
          
          // Determine icon based on title
          let icon = <Scale className="h-4 w-4 text-primary" />
          if (title.includes('Căn cứ') || title.includes('pháp lý')) {
            icon = <FileText className="h-4 w-4 text-accent" />
          } else if (title.includes('Lưu ý') || title.includes('thiếu') || title.includes('cần')) {
            icon = <AlertTriangle className="h-4 w-4 text-warning" />
          }
          
          return (
            <div key={index} className="flex gap-3">
              <div className="flex-shrink-0 mt-0.5">{icon}</div>
              <div className="flex-1 min-w-0">
                <h4 className="font-semibold text-sm mb-2">{title}</h4>
                <div className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
                  {formatBody(body)}
                </div>
              </div>
            </div>
          )
        }
        
        // Plain text section
        return (
          <div key={index} className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
            {formatBody(section)}
          </div>
        )
      })}
    </div>
  )
}

function formatBody(text: string): React.ReactNode {
  // Handle bold text with **
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={i} className="font-semibold text-foreground">
          {part.slice(2, -2)}
        </strong>
      )
    }
    return part
  })
}

function SourceBadge({ source, index }: { source: RetrievedSource; index: number }) {
  const typeLabels: Record<string, string> = {
    law: 'Luật',
    decree: 'Nghị định',
    circular: 'Thông tư',
    resolution: 'Nghị quyết',
    decision: 'Quyết định',
    guideline: 'Hướng dẫn',
    other: 'Khác',
  }
  const citation = formatSourceCitation(source)
  const documentLabel = sourceDocumentLabel(source)
  const shortReference = sourceShortReference(source)

  return (
    <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/50">
      <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-medium">
        {index + 1}
      </div>
      <div className="flex-1 min-w-0">
        <div className="min-w-0">
          <p className="text-sm font-medium leading-snug line-clamp-2">{documentLabel}</p>
          {shortReference && (
            <p className="mt-0.5 text-xs text-muted-foreground leading-relaxed">{shortReference}</p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2 mt-2">
          {source.documentType && (
            <span className="px-1.5 py-0.5 rounded text-xs bg-secondary text-secondary-foreground">
              {typeLabels[source.documentType] || source.documentType}
            </span>
          )}
          <span 
            className={`text-xs px-1.5 py-0.5 rounded ${
              source.retrievalOrigin === 'hybrid' 
                ? 'bg-primary/10 text-primary'
                : source.retrievalOrigin === 'vector'
                ? 'bg-info/10 text-info'
                : 'bg-accent/10 text-accent-foreground'
            }`}
          >
            {source.retrievalOrigin}
          </span>
          <span className="text-xs text-muted-foreground">
            {(source.relevanceScore * 100).toFixed(0)}%
          </span>
        </div>
        {!shortReference && (
          <p className="mt-1 text-xs text-muted-foreground leading-relaxed line-clamp-2">{citation}</p>
        )}
      </div>
    </div>
  )
}
