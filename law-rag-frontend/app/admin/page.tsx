'use client'

import { useState, useEffect } from 'react'
import { 
  Database, 
  FileText, 
  Layers, 
  Activity,
  Play,
  RefreshCw,
  CheckCircle2,
  Clock,
  AlertCircle,
  Loader2,
  Cpu,
  Cloud,
  Server,
  KeyRound
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { 
  getCorpusStatus, 
  getJobs, 
  triggerCrawl, 
  triggerChunking, 
  triggerBM25Index, 
  triggerVectorIndex,
  getRuntimeStatus,
  updateRuntimeConfig,
  getLocalModels
} from '@/lib/api'
import type { CorpusStatus, LocalModel, PipelineJob, RuntimeMode, RuntimeStatus } from '@/lib/types'
import { formatDistanceToNow } from 'date-fns'
import { vi } from 'date-fns/locale'
import { toast } from 'sonner'

const REWRITE_MODEL_DESCRIPTIONS: Record<string, string> = {
  'qwen2.5:0.5b-instruct': 'Nhanh nhất, chất lượng rewrite yếu; chỉ nên dùng để thử tốc độ.',
  'qwen2.5:1.5b-instruct': 'Khuyến nghị cho rewrite: nhẹ hơn 7B, đủ tốt sau prompt ràng buộc.',
  'qwen2.5:3b-instruct': 'Cân bằng hơn nhưng tốn VRAM hơn; có thể chậm trên GPU 6GB.',
  'qwen2.5:7b-instruct': 'Chất lượng tốt hơn nhưng chậm, không nên dùng riêng cho rewrite nếu ưu tiên tốc độ.',
}

function rewriteModelDescription(modelId: string): string {
  return REWRITE_MODEL_DESCRIPTIONS[modelId] || 'Model local khả dụng từ Ollama/endpoint OpenAI-compatible.'
}

export default function AdminDashboardPage() {
  const [corpusStatus, setCorpusStatus] = useState<CorpusStatus | null>(null)
  const [jobs, setJobs] = useState<PipelineJob[]>([])
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatus | null>(null)
  const [selectedMode, setSelectedMode] = useState<RuntimeMode>('local')
  const [openaiApiKey, setOpenaiApiKey] = useState('')
  const [localLlmBaseUrl, setLocalLlmBaseUrl] = useState('http://127.0.0.1:11434/v1')
  const [localQueryRewriteModel, setLocalQueryRewriteModel] = useState('qwen2.5:1.5b-instruct')
  const [localModels, setLocalModels] = useState<LocalModel[]>([])
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [runtimeSaving, setRuntimeSaving] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  useEffect(() => {
    if (selectedMode !== 'local' || localModels.length === 0) return
    const selectedModelExists = localModels.some((model) => model.id === localQueryRewriteModel)
    if (selectedModelExists) return
    const preferredModel = localModels.find((model) => model.id === 'qwen2.5:1.5b-instruct') || localModels[0]
    setLocalQueryRewriteModel(preferredModel.id)
  }, [selectedMode, localModels, localQueryRewriteModel])

  async function loadData() {
    try {
      const [statusRes, jobsRes, runtimeRes] = await Promise.all([
        getCorpusStatus(),
        getJobs(),
        getRuntimeStatus(),
      ])
      
      if (statusRes.success) setCorpusStatus(statusRes.data)
      if (jobsRes.success) setJobs(jobsRes.data)
      if (runtimeRes.success) {
        setRuntimeStatus(runtimeRes.data)
        setSelectedMode(runtimeRes.data.mode)
        if (runtimeRes.data.localLlmBaseUrl) setLocalLlmBaseUrl(runtimeRes.data.localLlmBaseUrl)
        if (runtimeRes.data.queryRewriteModel) setLocalQueryRewriteModel(runtimeRes.data.queryRewriteModel)
      }
      const modelsRes = await getLocalModels()
      if (modelsRes.success) setLocalModels(modelsRes.data)
    } catch (error) {
      console.error('[v0] Error loading admin data:', error)
    } finally {
      setLoading(false)
    }
  }

  async function handleAction(action: 'crawl' | 'chunk' | 'bm25' | 'vector') {
    setActionLoading(action)
    try {
      let response
      switch (action) {
        case 'crawl':
          response = await triggerCrawl()
          break
        case 'chunk':
          response = await triggerChunking()
          break
        case 'bm25':
          response = await triggerBM25Index()
          break
        case 'vector':
          response = await triggerVectorIndex()
          break
      }
      
      if (response.success) {
        toast.success('Tác vụ đã được khởi động')
        loadData()
      }
    } catch {
      toast.error('Có lỗi xảy ra')
    } finally {
      setActionLoading(null)
    }
  }

  async function handleRuntimeSave() {
    setRuntimeSaving(true)
    try {
      const response = await updateRuntimeConfig({
        mode: selectedMode,
        openaiApiKey: selectedMode === 'openai' ? openaiApiKey.trim() || undefined : undefined,
        localLlmBaseUrl: selectedMode === 'local' ? localLlmBaseUrl.trim() || undefined : undefined,
        localQueryRewriteModel: selectedMode === 'local' ? localQueryRewriteModel.trim() || undefined : undefined,
      })
      if (response.success) {
        setRuntimeStatus(response.data)
        setSelectedMode(response.data.mode)
        setOpenaiApiKey('')
        toast.success('Đã cập nhật chế độ chạy')
        await loadData()
      } else {
        toast.error(response.error)
      }
    } catch {
      toast.error('Không cập nhật được chế độ chạy')
    } finally {
      setRuntimeSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Tổng quan hệ thống</h1>
          <p className="text-muted-foreground mt-1">
            Quản lý pipeline dữ liệu và theo dõi trạng thái hệ thống
          </p>
        </div>
        <Button variant="outline" onClick={loadData}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Làm mới
        </Button>
      </div>

      {runtimeStatus && (
        <Card>
          <CardHeader>
            <CardTitle>Chế độ chạy hiện tại</CardTitle>
            <CardDescription>
              Cấu hình backend đang được dùng cho chat model, embedding và thư mục vector index.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-5">
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <RuntimeInfo
                  icon={runtimeStatus.mode === 'local' ? <Cpu className="h-5 w-5" /> : <Cloud className="h-5 w-5" />}
                  label="Runtime"
                  value={runtimeStatus.mode === 'local' ? 'Local' : 'OpenAI API'}
                  detail={runtimeStatus.llmProvider}
                />
                <RuntimeInfo
                  icon={<Server className="h-5 w-5" />}
                  label="Model trả lời"
                  value={runtimeStatus.chatModel}
                  detail={runtimeStatus.localLlmBaseUrl || 'OpenAI API'}
                />
                <RuntimeInfo
                  icon={<Database className="h-5 w-5" />}
                  label="Embedding"
                  value={runtimeStatus.embeddingModel}
                  detail={runtimeStatus.embeddingProvider}
                />
                <RuntimeInfo
                  icon={<Activity className="h-5 w-5" />}
                  label="Vector index"
                  value={runtimeStatus.vectorIndex.built ? 'Sẵn sàng' : 'Chưa build'}
                  detail={`${runtimeStatus.vectorDir}${runtimeStatus.vectorIndex.chunkCount ? ` · ${runtimeStatus.vectorIndex.chunkCount.toLocaleString()} chunks` : ''}`}
                />
              </div>

              <div className="grid gap-4 border-t border-border pt-5 lg:grid-cols-[180px_minmax(220px,1fr)_minmax(220px,1fr)_minmax(220px,1fr)_auto]">
                <div className="space-y-2">
                  <Label htmlFor="runtime-mode">Chế độ</Label>
                  <Select value={selectedMode} onValueChange={(value) => setSelectedMode(value as RuntimeMode)}>
                    <SelectTrigger id="runtime-mode">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="local">Local</SelectItem>
                      <SelectItem value="openai">OpenAI API</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {selectedMode === 'local' && (
                  <div className="space-y-2">
                    <Label htmlFor="local-llm-base-url">Local LLM URL</Label>
                    <Input
                      id="local-llm-base-url"
                      value={localLlmBaseUrl}
                      onChange={(event) => setLocalLlmBaseUrl(event.target.value)}
                      placeholder="http://127.0.0.1:11434/v1"
                      autoComplete="off"
                    />
                    <p className="text-xs text-muted-foreground">
                      Endpoint OpenAI-compatible, ví dụ Ollama, LM Studio hoặc vLLM.
                    </p>
                  </div>
                )}
                {selectedMode === 'local' && (
                  <div className="space-y-2">
                    <Label htmlFor="local-query-rewrite-model">Model rewrite</Label>
                    <Select value={localQueryRewriteModel} onValueChange={setLocalQueryRewriteModel}>
                      <SelectTrigger id="local-query-rewrite-model">
                        <SelectValue placeholder="Chọn model rewrite" />
                      </SelectTrigger>
                      <SelectContent>
                        {localModels.length === 0 ? (
                          <SelectItem value={localQueryRewriteModel}>{localQueryRewriteModel}</SelectItem>
                        ) : (
                          localModels.map((model) => (
                            <SelectItem key={model.id} value={model.id}>
                              {model.name}
                            </SelectItem>
                          ))
                        )}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      {rewriteModelDescription(localQueryRewriteModel)}
                    </p>
                  </div>
                )}
                {selectedMode === 'openai' && (
                  <div className="space-y-2">
                    <Label htmlFor="openai-api-key">OpenAI API key</Label>
                    <div className="relative">
                      <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                      <Input
                        id="openai-api-key"
                        type="password"
                        value={openaiApiKey}
                        onChange={(event) => setOpenaiApiKey(event.target.value)}
                        placeholder={runtimeStatus.hasOpenaiApiKey ? 'Da co key trong .env' : 'sk-...'}
                        autoComplete="off"
                        className="pl-9"
                      />
                    </div>
                    <p className="text-xs font-medium">
                      {runtimeStatus.hasOpenaiApiKey ? 'OPENAI_API_KEY da duoc cau hinh' : 'Chua co OPENAI_API_KEY'}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      De trong neu chi muon chuyen sang OpenAI API ma khong doi key. Khi nhap key moi, backend se luu vao file .env.
                    </p>
                  </div>
                )}
                <div className="flex items-end">
                  <Button onClick={handleRuntimeSave} disabled={runtimeSaving}>
                    {runtimeSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Cập nhật
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatsCard
          icon={<Database className="h-5 w-5" />}
          title="Văn bản đã thu thập"
          value={corpusStatus?.crawledDocuments.toLocaleString() || '0'}
          subtitle={`/ ${corpusStatus?.totalDocuments.toLocaleString() || '0'} tổng`}
          trend={corpusStatus ? Math.round((corpusStatus.crawledDocuments / corpusStatus.totalDocuments) * 100) : 0}
        />
        <StatsCard
          icon={<Layers className="h-5 w-5" />}
          title="Chunks đã tạo"
          value={corpusStatus?.totalChunks.toLocaleString() || '0'}
          subtitle={`từ ${corpusStatus?.chunkedDocuments.toLocaleString() || '0'} văn bản`}
        />
        <StatsCard
          icon={<FileText className="h-5 w-5" />}
          title="BM25 Index"
          value={corpusStatus?.bm25IndexStatus.built ? 'Hoạt động' : 'Chưa có'}
          subtitle={corpusStatus?.bm25IndexStatus.lastUpdated 
            ? `Cập nhật ${formatDistanceToNow(new Date(corpusStatus.bm25IndexStatus.lastUpdated), { addSuffix: true, locale: vi })}`
            : 'Chưa cập nhật'
          }
          status={corpusStatus?.bm25IndexStatus.built ? 'success' : 'warning'}
        />
        <StatsCard
          icon={<Activity className="h-5 w-5" />}
          title="Vector Index"
          value={corpusStatus?.vectorIndexStatus.built ? 'Hoạt động' : 'Chưa có'}
          subtitle={corpusStatus?.vectorIndexStatus.lastUpdated 
            ? `Cập nhật ${formatDistanceToNow(new Date(corpusStatus.vectorIndexStatus.lastUpdated), { addSuffix: true, locale: vi })}`
            : 'Chưa cập nhật'
          }
          status={corpusStatus?.vectorIndexStatus.built ? 'success' : 'warning'}
        />
      </div>

      {/* Pipeline Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Điều khiển Pipeline</CardTitle>
          <CardDescription>
            Chạy các bước trong pipeline xử lý dữ liệu. Mỗi bước phụ thuộc vào bước trước đó.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <PipelineActionCard
              step={1}
              title="Thu thập văn bản"
              description="Crawl văn bản từ danh sách URL"
              icon={<Database className="h-5 w-5" />}
              loading={actionLoading === 'crawl'}
              onRun={() => handleAction('crawl')}
            />
            <PipelineActionCard
              step={2}
              title="Chia chunks"
              description="Phân đoạn văn bản thành chunks"
              icon={<Layers className="h-5 w-5" />}
              loading={actionLoading === 'chunk'}
              onRun={() => handleAction('chunk')}
            />
            <PipelineActionCard
              step={3}
              title="Xây dựng BM25"
              description="Tạo index BM25 cho tìm kiếm"
              icon={<FileText className="h-5 w-5" />}
              loading={actionLoading === 'bm25'}
              onRun={() => handleAction('bm25')}
            />
            <PipelineActionCard
              step={4}
              title="Xây dựng Vector"
              description="Tạo embeddings và FAISS index"
              icon={<Activity className="h-5 w-5" />}
              loading={actionLoading === 'vector'}
              onRun={() => handleAction('vector')}
            />
          </div>
        </CardContent>
      </Card>

      {/* Recent Jobs */}
      <Card>
        <CardHeader>
          <CardTitle>Lịch sử tác vụ</CardTitle>
          <CardDescription>
            Các tác vụ pipeline gần đây và trạng thái của chúng
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {jobs.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                Chưa có tác vụ nào được ghi nhận
              </p>
            ) : (
              jobs.map((job) => (
                <JobRow key={job.id} job={job} />
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function RuntimeInfo({
  icon,
  label,
  value,
  detail,
}: {
  icon: React.ReactNode
  label: string
  value: string
  detail: string
}) {
  return (
    <div className="rounded-lg border border-border bg-muted/30 p-4">
      <div className="mb-3 flex items-center gap-2 text-primary">
        {icon}
        <span className="text-xs font-medium uppercase text-muted-foreground">{label}</span>
      </div>
      <p className="truncate text-sm font-semibold">{value}</p>
      <p className="mt-1 truncate text-xs text-muted-foreground">{detail}</p>
    </div>
  )
}

function StatsCard({ 
  icon, 
  title, 
  value, 
  subtitle, 
  trend,
  status 
}: { 
  icon: React.ReactNode
  title: string
  value: string
  subtitle: string
  trend?: number
  status?: 'success' | 'warning' | 'error'
}) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div className="p-2 rounded-lg bg-primary/10 text-primary">
            {icon}
          </div>
          {status && (
            <div className={`w-2 h-2 rounded-full ${
              status === 'success' ? 'bg-success' : 
              status === 'warning' ? 'bg-warning' : 'bg-destructive'
            }`} />
          )}
        </div>
        <div className="mt-4">
          <p className="text-2xl font-semibold">{value}</p>
          <p className="text-sm text-muted-foreground mt-1">{title}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>
        </div>
        {trend !== undefined && (
          <div className="mt-3">
            <Progress value={trend} className="h-1.5" />
            <p className="text-xs text-muted-foreground mt-1">{trend}% hoàn thành</p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function PipelineActionCard({
  step,
  title,
  description,
  icon,
  loading,
  onRun,
}: {
  step: number
  title: string
  description: string
  icon: React.ReactNode
  loading: boolean
  onRun: () => void
}) {
  return (
    <div className="p-4 rounded-lg border border-border bg-muted/30">
      <div className="flex items-start justify-between mb-3">
        <div className="p-2 rounded-lg bg-primary/10 text-primary">
          {icon}
        </div>
        <span className="text-xs font-medium text-muted-foreground">Bước {step}</span>
      </div>
      <h4 className="font-medium text-sm">{title}</h4>
      <p className="text-xs text-muted-foreground mt-1 mb-4">{description}</p>
      <Button 
        size="sm" 
        variant="secondary" 
        className="w-full"
        onClick={onRun}
        disabled={loading}
      >
        {loading ? (
          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
        ) : (
          <Play className="h-4 w-4 mr-2" />
        )}
        Chạy
      </Button>
    </div>
  )
}

function JobRow({ job }: { job: PipelineJob }) {
  const typeLabels: Record<string, string> = {
    crawl: 'Thu thập văn bản',
    chunk: 'Chia chunks',
    index_bm25: 'Xây dựng BM25',
    index_vector: 'Xây dựng Vector',
  }

  const statusConfig: Record<PipelineJob['status'], {
    icon: typeof Clock
    color: string
    label: string
    animate?: boolean
  }> = {
    pending: { icon: Clock, color: 'text-muted-foreground', label: 'Đang chờ' },
    running: { icon: Loader2, color: 'text-info', label: 'Đang chạy', animate: true },
    completed: { icon: CheckCircle2, color: 'text-success', label: 'Hoàn thành' },
    failed: { icon: AlertCircle, color: 'text-destructive', label: 'Lỗi' },
  }

  const config = statusConfig[job.status]
  const StatusIcon = config.icon

  return (
    <div className="flex items-center gap-4 p-3 rounded-lg border border-border">
      <StatusIcon 
        className={`h-5 w-5 ${config.color} ${config.animate ? 'animate-spin' : ''}`} 
      />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{typeLabels[job.type] || job.type}</p>
        <p className="text-xs text-muted-foreground">
          {job.startedAt && formatDistanceToNow(new Date(job.startedAt), { addSuffix: true, locale: vi })}
        </p>
      </div>
      {job.status === 'running' && (
        <div className="w-24">
          <Progress value={job.progress} className="h-1.5" />
          <p className="text-xs text-muted-foreground text-right mt-1">{job.progress}%</p>
        </div>
      )}
      <span className={`text-xs font-medium ${config.color}`}>
        {config.label}
      </span>
    </div>
  )
}

